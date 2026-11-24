# pizero-tv suite — foundation + rebuild of the 12 modules

Approved 2026-11-23 ("yes. and make the design amazing not plain or boring").

## Intent
Turn the Pi Zero 2 W TV display into one coherent, beautiful ambient suite. Today it is
12 Gemini-written pygame scripts that mostly show invented data, share a generic
navy/cyan card look, overflow text, render missing glyphs as boxes, and in three cases
don't work at all (space blank, syshud all zeros, trippy crash). The user wants: (1) "the
app" — a proper foundation (controller that targets any Pi by hostname, splash screen
between modules, shared look), then (2) every existing module fixed: real data, and a
design that is "amazing, not plain or boring".

## Goals
- Every number on screen is real or explicitly marked unavailable (README rule:
  "Everything on screen is real, or it says it isn't").
- One distinctive visual language across all modules (below), readable from a couch.
- Switching modules never shows the desktop: a branded splash covers the gap.
- `tv` works locally on the Pi and remotely: `tv -H <host> <command>`.
- Fits a 415 MB Pi Zero 2 W: one module resident at a time; target ≤ 35% of one core
  and ≤ 70 MB RSS per module in steady state (sfdispatch measured ~30% / ~66 MB).
- Runs unattended for days (cycle mode), survives network loss and module crashes.

## Non-goals
- New modules (airwaves, certstream, kev, skywatch, wikipulse, terminal mirror) — next project.
- Casting, phone remote, web UI.
- Paid or keyed data sources (NASA DEMO_KEY is acceptable: it's public and rate-limited).

## Anti-goals
- Any simulated/fabricated data presented as real (attack counters, "decryption", canned
  flights/devices/headlines, placeholder prices).
- The SaaS-card look: every panel a rounded box. Tofu glyphs, clipped text, emoji.
- Location or other personal details in the public repo.

## Constraints
- Hardware: Pi Zero 2 W, 415 MB RAM (+414 MB swap, already ~200 MB used), VC4 GPU,
  labwc Wayland session on HDMI 1080p. Python 3.13, pygame 2.6.1, psutil, PyOpenGL and
  requests are installed. `pygame.display.set_mode` costs ~4.4 s on this Pi.
- Pi wifi drops long ssh sessions (brcmfmac SDIO errors): remote commands must be short
  and must not depend on the ssh session staying up.
- Repo is public (github.com/NPCmillionaire/pizero-tv).
- Archive, don't delete: the existing `~/tv` install on the Pi stays where it is.

## Approaches considered (how modules run)
1. **One long-running display host process (chosen).** A `tvd` daemon owns the single
   fullscreen pygame window and loads modules as in-process plugins. Switching is
   instant (no 4.4 s window creation, no desktop flash), the splash is just a scene the
   host draws while the next module starts, and memory is one interpreter + one module.
   Cost: a module bug can affect the host, so the host catches module exceptions, shows
   an error scene, and moves on; systemd restarts the host if it dies.
2. Separate process per module + separate splash process (what exists, plus a splash).
   Simple isolation, but every switch pays ~4–5 s of window creation for *both* splash
   and module, and two fullscreen windows race for stacking on labwc. Rejected: the
   splash would itself be the slow part.
3. Web dashboard in a kiosk browser. Rejected: Chromium on 415 MB is a non-starter.

## Architecture
```
bin/tv                  CLI (python). Local: talks to tvd over a unix socket.
                        Remote: `tv -H host ...` → `ssh host ~/pizero-tv/bin/tv ...`
tvd/  (tvkit/host.py)   the daemon: window, scene loop, module lifecycle, splash, cycle
tvkit/                  shared kit: theme, fonts, text/fit, chrome, widgets, fetch, config
modules/<name>/         one package per module: __init__.py exposes MODULE (a tvkit.Module)
systemd/tvd.service     user service; starts with the graphical session
deploy.sh <host>        rsync suite to <host>:~/pizero-tv, install service, restart
```
- **Module API** (`tvkit.Module`): `name`, `title` (spine text), `key` (spine color),
  `aliases`; `start(ctx)` (spawn fetchers), `update(now) -> bool` (data changed → rebuild
  static), `draw_static(surf)`, `draw_live(surf, t)` (animation only), `key(event)`,
  `stop()` (stop threads, drop surfaces). Host composes the static layer once per change
  and animates on top at adaptive FPS (24 during motion, 8 idle) — the pattern that took
  sfdispatch from 100% to ~30% CPU.
- **Discovery**: host and CLI import `modules/*/__init__.py` and read `MODULE`. Adding a
  module = adding a folder.
- **Control socket**: `$XDG_RUNTIME_DIR/pizero-tv.sock`, line protocol:
  `show <name>`, `next`, `cycle <sec> [names…]`, `stop` (standby scene), `status`
  (JSON: module, since, cycle, fps, rss), `screenshot <path>`, `reload`.
- **Splash**: drawn by the host on every switch: `legitbiz.research` wordmark, the
  incoming module's title and one-line description, and `github.com/NPCmillionaire/pizero-tv`.
  Held ≥ 1.2 s and until the incoming module reports ready (first data or 8 s,
  whichever first). The previous module is stopped before the next starts.
- **Failure scenes**: module `start/update/draw` raises → host logs the traceback, shows
  an "This screen crashed: <error>" scene for 10 s, then continues (next in cycle, or
  standby). Data failures are the module's job: the chrome badge shows
  live / stale (age) / offline.
- **Config**: `~/.config/pizero-tv/config.toml` on the Pi, never in the repo:
  `[place] name, lat, lon, timezone`, `[units] temp = "F"`, `[lan] subnet`,
  `[cycle] seconds, modules`. A committed `config.example.toml` uses San Francisco.
  Modules that need a location show "Set [place] in config.toml" if it's missing.
- sfdispatch is ported to the Module API too (its pure data layer is reused as-is).

## Visual language
Brief: an ambient wall for a tongue-in-cheek research outfit ("legitbiz.research") whose
one serious rule is honesty. It is read from across a room, in passing, often at night.

**Signature move — the spine.** Each module's name is set in Big Shoulders Display
ExtraBold, rotated 90°, running up the left edge at ~150 px cap height in the module's
key color, with a hairline separating it from the content. It identifies the screen from
across the room and gives the suite one unmistakable silhouette. This is where the
boldness goes; everything else is quiet.

**Color** (tokens in `tvkit/theme.py`):
| Token | Hex | Use |
|---|---|---|
| ground | `#0C1F24` | background (deep petrol, not black) |
| tide | `#133038` | hairlines, chart grids, track fills |
| bone | `#EEE6D3` | primary text and hero numerals |
| lichen | `#86A3A0` | secondary text, axes |
| sodium | `#FFA630` | default key / primary data line |
| coral | `#FF5A5F` | down / alert / emergency |
| seaglass | `#6FD6C5` | up / live / healthy |
Module key colors (spine + one accent per module): weather sodium, finance seaglass,
crypto `#F7C948` (gold), threatmap coral, space `#A88BFF` (violet), flights sodium,
news `#7FB2FF` (sky), syshud seaglass, lanradar `#8FE36B` (phosphor), sfdispatch coral;
art modules (matrix, retro, trippy) own their palettes and keep only the spine.

**Type** (bundled, OFL): Big Shoulders Display (static 800/600/400 instances cut from the
variable font) for the spine, hero numerals and big statements; IBM Plex Sans Condensed
(400/500/600) for all text; IBM Plex Mono only where columns must align (tables,
tickers, axis ticks). Sentence case everywhere except the spine. Scale (px at 720p):
hero 220–300 · display 56 · title 28 · body 20 · small 16 · micro 14. Minimum 14 px.

**Layout.** Content area x 190–1250. One hero element per module (the number or picture
you'd want from across the room), one primary visualization, and a quiet secondary rail.
Panels are not boxed: grouping comes from space, alignment, and occasional `tide`
hairlines. No drop shadows, no gradients as decoration, no border radius on layout.
Footer, bottom right, micro: status dot + `live` / `stale 12m` / `offline` and
`legitbiz.research`.

**Motion.** One entrance per module (hero numeral and chart settle in over ~600 ms after
the splash) and data-driven motion only (new pins, ticking values, sweeps that mean
something). Art modules are exempt.

## Module designs (what each becomes)
| Module | Hero | Data (verified reachable from the Pi 2026-11-23) | Notes |
|---|---|---|---|
| weather | current temp | Open-Meteo forecast (config place) | Drawn vector weather icons (no emoji); 24 h temp curve with precip bars; 7-day strip; sun arc with the sun's real position. |
| finance | S&P 500 level + day change | Yahoo chart API (`query1…/v8/finance/chart`) | Indices row, spotlight candles (cycles tickers on Space / every 30 s), sector tiles colored by real change with legible labels, VIX/10Y/DXY/gold/oil. Market-closed state shown. |
| crypto | BTC price | CoinGecko markets + OHLC + global; alternative.me Fear & Greed | Drop invented order-flow/liquidation/funding. Watchlist with 24 h range bars and numeric change. |
| threatmap | count of live botnet C2 servers | abuse.ch Feodo Tracker blocklist (IP, port, malware, country, first/last seen) | World map of real C2 locations by country, malware family breakdown, newest servers list. No fake arcs or attack rates. |
| space | ISS altitude/speed + where it is | wheretheiss.at; NOAA SWPC planetary Kp; SWPC solar wind (path to verify); NASA NeoWs (DEMO_KEY) | Ground track + day/night terminator; Kp bar history; nearest asteroid flyby today. Fix blank screen. |
| flights | aircraft count overhead | adsb.lol `/v2/point/{lat}/{lon}/{radius}` (config place) | Radar scope with real aircraft (callsign, type, altitude, speed, heading); spotlight strip cycles closest aircraft. |
| news | strongest quake today | USGS 2.5_day GeoJSON; Hacker News top stories | Quake map + list; real HN headlines with points/age; world clocks. No canned fallback. |
| syshud | CPU % | psutil (+ `vcgencmd` temp/throttle) | Real per-core load + 60 s history, memory/swap, temp, net rates, top processes, uptime. |
| lanradar | devices online | `ip neigh` + periodic ping sweep of `[lan] subnet`; reverse DNS/mDNS names; bundled OUI vendor table | Sonar with real devices; "new device" highlight when a MAC first appears. MACs never leave the Pi. |
| matrix | — (art) | none | Real katakana via a bundled CJK-capable font subset; remove the fake "decryption core" panel. |
| retro | — (art) | none | Keep the three modes; polish; spine added. |
| trippy | — (art) | none | Fix crash (drop missing `dash` import); GLSL shaders; must not hold the GL context across module switches in a way that breaks the host (render to a surface or run via the host's GL-safe path — builder's call after testing). |
| sfdispatch | (existing) | data.sf.gov gnap-fj3t | Port to Module API + new visual language. |

## Decided by the user
- Foundation first, then fix all 12 Gemini modules; real data or nothing.
- Splash shows `legitbiz.research` plus the repo link. Repo: github.com/NPCmillionaire/pizero-tv.
- The design must be distinctive ("amazing, not plain or boring").
- Proceed autonomously; show results at the end.

## Calls made by the designer (user may revisit)
- In-process host daemon instead of per-module processes (approach 1).
- The visual language above (spine, petrol/bone/sodium palette, Big Shoulders + Plex).
- Location lives only in the Pi's config file.
- Crypto drops order-flow/liquidation/funding metrics (no free honest source).
- Threatmap shows C2 infrastructure, not "attacks".

## Settled after builder review (designer's calls)
1. **Window / GL.** The host window is a plain 1280×720 surface with `pygame.SCALED`
   (GPU texture upscale to 1080p; no CPU scaling). trippy is **CPU-rendered with numpy
   (2.2.4 on the Pi) at 320×180** and blitted scaled ×4 with `pygame.transform.scale`
   (nearest) — no GL context. The old GLSL shaders are ported to numpy formulas.
2. **Resolution / spine.** Logical surface 1280×720. The spine is the module title as a
   single word rotated 90° (reads bottom-to-top), Big Shoulders 800 at the largest size
   ≤ 168 px whose rendered length fits 680 px — so long titles shrink instead of clip.
   Spine titles: WEATHER, MARKETS (finance), CRYPTO, THREATS, ORBIT (space), AIRSPACE
   (flights), SIGNAL (news), SYSTEM (syshud), LAN, MATRIX, OUTRUN (retro), TRIPPY, DISPATCH.
3. **Ready / blocking.** `Module.ready -> bool` is part of the API. `start()` must not
   block: network work runs on tvkit fetch threads. The host keeps animating the splash
   until `ready` or 8 s, then shows the module, which renders its own waiting / offline
   state.
4. **Verification.** Per module: unit tests for parsing (fixtures captured from the real
   endpoints) + a parametrized render smoke test under `SDL_VIDEODRIVER=dummy` that draws
   every state (waiting, live, stale, offline) and asserts no text exceeds its box. Then
   on the Pi: deploy, screenshot every module via `tv screenshot`, measure CPU/RSS with a
   detached script. The builder judges visuals from screenshots; the user sees them at the end.
5. **Cadence and cache.** Each module sets its own poll interval (≥ 60 s for public
   APIs; NASA NeoWs ≤ 1/hour; CoinGecko ≤ 3 calls/min total). tvkit caches the last good
   payload per source in `~/.cache/pizero-tv/<module>/<source>.json`; on start a cached
   payload is shown immediately, badged `stale <age>`, until fresh data arrives.
6. **Fonts.** Font binaries are committed under `tvkit/fonts/` with their licenses
   (OFL for Big Shoulders and Plex; Apache-2.0 for a katakana subset of Droid Sans
   Fallback, cut by `tools/build_fonts.py` with fontTools).
7. **Session / autostart.** `tvd` starts from `~/.config/autostart/pizero-tv.desktop`
   via `lwrespawn` (restarts on crash; inherits the labwc session's `WAYLAND_DISPLAY`).
   Nothing from the old `~/tv` autostarts. On install, `deploy.sh` runs the old
   `~/tv/tv stop`, moves the old `~/.local/bin` symlinks (tv, crypto, …) into
   `~/.local/bin/gemini-archive/`, and links `~/.local/bin/tv` → `~/pizero-tv/bin/tv`.
   `~/tv` itself is untouched.
8. **Cycle defaults / persistence.** The host persists `{mode, module, cycle}` in
   `~/.local/state/pizero-tv/state.json` and resumes it after a restart. First-ever
   start: cycle through all modules every `[cycle] seconds` (default 90).
9. **Hosts.** `-H <host>` is passed to ssh as-is (ssh config aliases like `pizero`);
   no discovery. Commands sent remotely return immediately (the socket call is short).
10. **LAN privacy.** lanradar and syshud screenshots are never committed to the repo
    (README images come from public-data modules only).

## Left to the builder
Exact layouts per module within the language above; chart styling details; icon
drawings; how trippy coexists with the host's GL context; OUI table trimming; socket
details; test fixtures.
