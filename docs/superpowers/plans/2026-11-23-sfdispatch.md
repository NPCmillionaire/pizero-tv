# sfdispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pizero-tv module that maps live SFPD dispatched calls on a street map of San Francisco.

**Architecture:** Pure-Python data layer (`feed.py`, `replay.py`, `geo.py`) unit-tested on the Mac; a pygame front end (`sfdispatch.py`) that runs on the Pi with a background fetch thread. The basemap is pre-built on the Mac from OSM + SF neighborhoods into a committed, pre-projected JSON so the Pi only draws polylines.

**Tech Stack:** Python 3.13, pygame 2.6.1 (Pi), requests, pytest (Mac only). Data: Socrata `data.sf.gov/resource/gnap-fj3t.json`, Overpass API (build time only), SF Analysis Neighborhoods (`data.sf.gov/resource/j2bu-swwd.geojson`).

**Spec:** `docs/superpowers/specs/2026-11-23-sfdispatch-design.md`

## Global Constraints
- Real data only; no placeholder/simulated calls anywhere, including on fetch failure.
- 1280x720 logical surface, 30 FPS, `pygame.SCALED`, target < ~60 MB RSS on Pi Zero 2 W.
- Fonts: DejaVu Sans / DejaVu Sans Mono via `pygame.font.Font(path)` from `/usr/share/fonts/truetype/dejavu/`. No emoji.
- No text may overflow its panel: every drawn string goes through one `fit(font, text, max_w)` ellipsis helper.
- Footer text exactly `legitbiz.research`.
- Socrata timestamps are naive America/Los_Angeles; compare using `zoneinfo.ZoneInfo("America/Los_Angeles")`.
- Module lives at `modules/sfdispatch/`; entry file `modules/sfdispatch/sfdispatch.py` (matches `tv`'s `<name>/<name>.py` convention).
- Must not depend on the future foundation kit.
- Mac dev env: `uv venv --python 3.13 .venv && uv pip install pytest pygame==2.6.1 requests` (Homebrew default is 3.15, which lacks pygame wheels); `.venv/` in `.gitignore`. Set up in Task 1.

## Review Focus
1. Feed unreachable at startup → header shows `OFFLINE`, map draws with no pins, no crash, retries every 60 s. (Task 2 test `test_poll_failure_sets_offline`.)
2. Feed reachable but `data_loaded_at` older than 30 min → `STALE` badge with age. (Task 2 test `test_staleness`.)
3. Calls with missing or out-of-SF coordinates (sensitive calls, `0,0`) → counted in stats, never plotted. (Task 1 test `test_outside_bbox`, Task 2 test `test_parse_no_location`.)
4. Socrata's default 1000-row page truncates the ~1,700-call 24 h backlog → URL must carry `$limit=5000`. (Task 2 test `test_build_url`.)
5. Long call types / intersections (e.g. `SUTTER ST \ VAN NESS AVE`) overflow panels → `fit()` truncates with `…`. (Task 4 test `test_fit_truncates`.)

---

### Task 1: Projection + basemap

**Files:**
- Create: `modules/sfdispatch/geo.py`
- Create: `tools/build_sf_basemap.py`
- Create: `modules/sfdispatch/basemap.json` (generated, committed)
- Test: `tests/sfdispatch/test_geo.py`
- Create: `tests/conftest.py` (adds `modules/sfdispatch` to `sys.path`)

**Interfaces:**
- Produces: `BBOX = (-122.515, 37.705, -122.355, 37.815)` (lon_min, lat_min, lon_max, lat_max); `Projector(rect: tuple[int,int,int,int])` with `.to_px(lon: float, lat: float) -> tuple[int,int] | None` (None outside BBOX) — equirectangular with x scaled by `cos(37.76°)`, aspect-preserving, centered in `rect`.
- Produces: `basemap.json` = `{"bbox": [...], "roads": {"motorway": [[[lon,lat],...],...], "primary": [...], "secondary": [...]}, "hoods": [{"name": str, "rings": [[[lon,lat],...]]}]}` — coordinates rounded to 5 dp, simplified (drop points < ~15 m apart). Target file < 1.5 MB.

- [ ] **Step 1: Write failing tests** — `test_corners_inside_rect` (BBOX corners project inside `rect=(0,0,860,520)`), `test_aspect_preserved` (projected width/height ratio == geographic ratio × cos(lat) within 1%), `test_outside_bbox` (`to_px(0,0) is None`, `to_px(-122.42, 37.90) is None`).
- [ ] **Step 2: Run** `pytest tests/sfdispatch/test_geo.py -v` → FAIL (import error).
- [ ] **Step 3: Implement `geo.py`.**
- [ ] **Step 4: Run tests** → PASS.
- [ ] **Step 5: Write `tools/build_sf_basemap.py`** — Overpass query for `highway~"^(motorway|trunk|primary|secondary)$"` within BBOX (trunk folds into `primary`), plus neighborhoods GeoJSON; writes `modules/sfdispatch/basemap.json`. Run it on the Mac.
- [ ] **Step 6: Verify** `python3 -c "import json;d=json.load(open('modules/sfdispatch/basemap.json'));print(len(d['hoods']), {k:len(v) for k,v in d['roads'].items()})"` → ~41 hoods, non-zero counts for all three road classes; file < 1.5 MB.
- [ ] **Step 7: Commit** `feat(sfdispatch): projection and SF basemap`.

### Task 2: Feed — fetch, parse, dedupe, stats

**Files:**
- Create: `modules/sfdispatch/feed.py`
- Test: `tests/sfdispatch/test_feed.py`

**Interfaces:**
- Produces: `@dataclass Call: cad: str; received: datetime; dispatched: datetime|None; type: str; priority: str; place: str; hood: str; lon: float|None; lat: float|None` (aware datetimes, LA tz; `priority` one of `"A","B","C"` else `"?"`; `type` title-cased).
- Produces: `parse_call(raw: dict) -> Call | None` (None only if `cad_number` or `received_datetime` missing).
- Produces: `build_url(since: datetime) -> str` — base URL from env `SFD_URL` if set, else `https://data.sf.gov/resource/gnap-fj3t.json`; `$where=received_datetime > '<iso naive LA>'`, `$order=received_datetime ASC`, `$limit=5000`.
- Produces: `class Feed: __init__(fetch=requests_get_json, clock=now_la)`; `.poll() -> list[Call]` returns only newly seen calls (dedupe on `cad`), prunes calls older than 24 h, updates `.status` ∈ `{"LIVE","STALE","OFFLINE"}` and `.data_age: timedelta|None` from max `data_loaded_at`. Never raises. `.calls: list[Call]`.
- Produces: `stats(calls: list[Call]) -> Stats` with `.total: int`, `.unplotted: int`, `.top_types: list[tuple[str,int]]` (5), `.top_hoods: list[tuple[str,int]]` (5), `.median_dispatch: dict[str, timedelta]` (per A/B/C, ignoring calls without `dispatched`).

- [ ] **Step 1: Write failing tests** using the real sample record from the spec session (cad `263272725`, `SUTTER ST \ VAN NESS AVE`, Nob Hill, priority C):
  - `test_parse_basic` — fields map; `lon == -122.421758104`; `received.tzinfo` is LA.
  - `test_parse_no_location` — record without `intersection_point` → Call with `lon is None`.
  - `test_build_url` — contains `%24limit=5000` (or `$limit=5000`) and `received_datetime ASC`.
  - `test_dedupe` — two polls returning the same record → second `poll()` returns `[]`, `len(feed.calls) == 1`.
  - `test_prune_24h` — call received 25 h before `clock()` is dropped after poll.
  - `test_poll_failure_sets_offline` — `fetch` raises → `poll() == []`, `status == "OFFLINE"`, existing calls kept.
  - `test_staleness` — `data_loaded_at` 45 min before clock → `"STALE"`; 10 min → `"LIVE"`.
  - `test_stats` — median dispatch for A computed from 3 calls (60 s, 120 s, 600 s → 120 s); unplotted counts location-less calls.
- [ ] **Step 2: Run** `pytest tests/sfdispatch/test_feed.py -v` → FAIL.
- [ ] **Step 3: Implement `feed.py`.** First poll uses `since = clock() - 24h`; later polls use the max `received` seen.
- [ ] **Step 4: Run tests** → PASS.
- [ ] **Step 5: Live smoke** `python3 -c "import sys;sys.path.insert(0,'modules/sfdispatch');import feed;f=feed.Feed();n=f.poll();print(len(n),f.status,f.data_age)"` → ~1,500–1,800 calls, `LIVE`.
- [ ] **Step 6: Commit** `feat(sfdispatch): SFPD feed parsing, dedupe, stats`.

### Task 3: Replay scheduler

**Files:**
- Create: `modules/sfdispatch/replay.py`
- Test: `tests/sfdispatch/test_replay.py`

**Interfaces:**
- Consumes: `Call` (Task 2).
- Produces: `schedule(batch: list[Call], start: float, window: float) -> list[tuple[float, Call]]` — spreads the batch over `[start, start+window)` proportional to gaps in `received`, preserving order; single call → `start`; empty → `[]`.
- Produces: `class Replayer: .add(batch, now: float, initial: bool)` (initial backlog is revealed immediately, already-aged, no ripple), `.due(now: float) -> list[Call]` pops calls whose time has come.

- [ ] **Step 1: Write failing tests** — `test_order_preserved`, `test_spread_within_window` (all times in `[start, start+60)`), `test_proportional_gaps` (received 0 s, 10 s, 40 s with window 60 → offsets 0, 13.5, 54: offset = (received − first)/span × 0.9 × window; second gap is 3× the first within 1%), `test_initial_immediate` (`add(..., initial=True)` → all due at `now`), `test_due_pops_once`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(sfdispatch): batch replay scheduler`.

### Task 4: Pygame front end

**Files:**
- Create: `modules/sfdispatch/sfdispatch.py`
- Create: `modules/sfdispatch/ui.py` (fonts, `fit`, colors, panel helper)
- Test: `tests/sfdispatch/test_ui.py`

**Interfaces:**
- Consumes: `Projector`, `BBOX` (Task 1); `Feed`, `stats`, `Call` (Task 2); `Replayer` (Task 3).
- Produces: `ui.fit(font, text: str, max_w: int) -> str`.

- [ ] **Step 1: Write failing test** `test_fit_truncates` — with `SDL_VIDEODRIVER=dummy`, DejaVu Sans 16: `fit(f, "SUTTER ST \\ VAN NESS AVE"*3, 120)` ends with `…` and renders ≤ 120 px; short string returned unchanged.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement `ui.py`.** **Step 4: Run** → PASS.
- [ ] **Step 5: Implement `sfdispatch.py`.** Layout: header 0–56 (title `SF DISPATCH // SFPD CAD`, `{total} calls 24h`, status badge `LIVE · data {m}m old` / `STALE · {m}m` amber / `OFFLINE` red); map rect `(20,72,860,520)` with basemap pre-rendered once (hood fills faint, hood borders, roads by class weight); queue `(900,72,360,520)` newest 12; bottom panels y=604–696: call types, busiest hoods, median dispatch A/B/C; footer `legitbiz.research` bottom-right. Pins: ripple 1.5 s on reveal; alpha fades linearly over 60 min; A = red pulsing radius 6, B = amber 4, C = dim cyan 3. Fetch thread calls `feed.poll()` every 60 s and hands new calls to the replayer (window 60 s; first poll `initial=True`). Keys Q/Esc quit, Space advances highlight through queue (highlighted pin gets a ring). Draw at 30 FPS.
- [ ] **Step 6: Local run** on the Mac (`python3 modules/sfdispatch/sfdispatch.py`) — window shows map + pins, no exceptions for 2 min.
- [ ] **Step 7: Commit** `feat(sfdispatch): pygame front end`.

### Task 5: Deploy to pizero

**Files:**
- Create: `deploy.sh` (rsync `modules/<name>/` → `<host>:~/tv/modules/<name>/`, excluding logs/__pycache__; `HOST=${1:-pizero}`)
- Modify (on Pi): `~/tv/tv` — add `sfdispatch` to `ALL_MODULES`, the module `case` pattern, and help text (back up to `~/tv/tv.bak-sfdispatch` first).

- [ ] **Step 1:** `./deploy.sh pizero sfdispatch`; apply the `tv` edits.
- [ ] **Step 2: Verify** `ssh pizero 'tv sfdispatch; sleep 20; tv status; tv screenshot /tmp/sfd.png'`, pull screenshot, inspect: map, pins, no overlap/clipping, badge `LIVE`. RSS from `tv status` < 60 MB; CPU < 25%.
- [ ] **Step 3: Offline check** — run with `SFD_URL=http://127.0.0.1:9/` override (read in `feed.py`) and confirm `OFFLINE` badge, no crash.
- [ ] **Step 4: Commit** `feat: deploy script; sfdispatch on pizero`.
