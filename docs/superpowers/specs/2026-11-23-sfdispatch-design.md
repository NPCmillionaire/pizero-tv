# sfdispatch — SF police dispatch map module

Approved 2026-11-23.

## Intent
A pizero-tv module that maps live public-safety activity for a big city with
open data. Many US agencies encrypt police radio, so
the module uses San Francisco's published SFPD CAD feed instead — no SDR needed.
Glanceable: "what's happening across the city right now, and what's serious."

## Goals
- Real data only. When the feed is unreachable, say so (stale/offline badge),
  never show placeholder calls.
- Street map of SF with calls dropping in as they arrive; priority A stands out.
- Side queue of most recent calls; bottom stats: call types 24h, busiest
  neighborhoods, median dispatch time by priority.
- Smooth on a Pi Zero 2 W at 1280x720, 30 FPS, < ~60 MB RSS.

## Non-goals
- Radio/audio, transcription, the SDR (separate future project).
- Fire/EMS live (SF fire data lags ~15h). Seattle as a second city: later.
- The shared UI kit / module discovery / splash / remote CLI (foundation
  project) — this module must not depend on them, but should be easy to port.

## Anti-goals
- Fake or simulated data of any kind.
- Text overlap, clipped edges, missing-glyph boxes (the existing modules' faults).

## Data
- `https://data.sf.gov/resource/gnap-fj3t.json` (Socrata, no key). ~1,650
  calls/day, refreshed ~10 min, ~15 min lag. Fields used: `cad_number`,
  `received_datetime`, `dispatch_datetime`, `onscene_datetime`,
  `call_type_final_desc`, `priority_final`, `intersection_name`,
  `intersection_point`, `analysis_neighborhood`, `police_district`.
  Sensitive calls arrive without location — count them, don't plot them.
- Timestamps are SF local time (America/Los_Angeles).
- Basemap: OSM major roads (Overpass) + SF Analysis Neighborhoods boundaries,
  fetched once on the Mac by a build script and committed as compact
  pre-projected JSON. The Pi never hits Overpass.

## Approaches considered
1. **SFPD CAD open data (chosen)** — richest live-ish data with coordinates and
   priority; one city.
2. Seattle Fire 911 — fresher (~8 min) but fire/EMS only; police data delayed.
3. Radio + Whisper transcription — works locally but police is often encrypted;
   much bigger build. Deferred.

## Design
- Layout (1280x720): header bar (title, 24h count, data age), map left
  (~860x520), live queue right, three stat panels bottom, footer
  "legitbiz.research".
- Fetch thread polls every 60 s for calls received in the last 24 h (incremental
  by `received_datetime`), dedupes on `cad_number`.
- New batch is replayed in received-time order over the poll interval so
  pins drop continuously instead of in jumps. Pins ripple on arrival, fade over
  ~60 min; priority A stays bright red and pulses, B amber, C dim cyan.
- Basemap pre-rendered once to a Surface; per frame only pins and UI redraw.
- Bundled font: DejaVu Sans / Sans Mono (installed on the Pi; full glyph
  coverage for what we draw). No emoji.
- Keys: Q/Esc quit, Space cycles a highlighted call in the queue.

## Left to the builder
Exact colors, panel sizes, road-class line weights, neighborhood glow styling.
