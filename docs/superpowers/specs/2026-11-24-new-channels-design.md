# New channels: MINER, MOST WANTED, REGISTRY, TERMINAL, and four psychedelic ones

Approved 2026-11-24 ("miner, terminal, most wanted and registry. make some other trippy
psychedelic ones"; wallet given; XMRig on arch restarted with its API on the LAN).

## Intent
More channels, each its own station, same rules: real data or it says so, no text off
screen, cheap enough for a Pi Zero 2 W.

## Channels
- **MINER** (power-plant control panel: analog gauges, annunciator lamps). XMRig's restricted
  HTTP API on arch (`/2/summary`, bearer token): hashrate 10 s / 60 s / 15 m, accepted and
  rejected shares, pool, uptime, huge pages, CPU threads. MoneroOcean's public API for the
  wallet (`/miner/<wallet>/stats`, `/chart/hashrate`): pool-side hashrate, amount due,
  paid, and XMR/USD from CoinGecko for the dollar value. Config: `[miner] url, token, wallet`.
  The wallet and token live only in the Pi's config.toml.
- **MOST WANTED** (wanted-poster board). CISA Known Exploited Vulnerabilities JSON, polled
  every 6 h. Posters for the newest additions: CVE, vendor and product, the vulnerability
  name, a short description, date added, patch deadline, and a "used by ransomware" stamp
  when CISA says Known. A count of entries added in the last 30 days.
- **REGISTRY** (detective's case file). The aircraft AIRSPACE sees, looked up by Mode S hex
  in the FAA registry (MASTER + ACFTREF from the govint-data `faa` release). The Pi keeps
  a compact lookup file built from it (only the columns shown), refreshed weekly. One
  aircraft at a time: registration, owner name and type (individual, corporation,
  government...), city and state, manufacturer and model, year built, engine, airworthiness
  date; plus what it's doing now (altitude, speed, distance). Non-US aircraft say they're
  outside the FAA registry.
- **TERMINAL** (public-access cable). `tv mirror` on any machine runs your shell in a
  pseudo-terminal, shows it as normal, and streams the output to the Pi over ssh; the
  channel renders it with a real terminal emulator (pyte) and tunes in automatically while
  a mirror is connected. Nothing is stored. When no mirror is connected the channel says
  how to start one.
- **Psychedelic**: LIQUID (1960s oil-wheel light show: metaballs in saturated dye colors),
  MANDALA (rotating symmetric line art that changes order), FRACTAL (a morphing Julia set in
  acid palettes), DREAM (video feedback: the frame zoomed, rotated and color-shifted into
  itself). numpy at low resolution, scaled up; about 10 FPS.

## Constraints
- Memory: each channel under ~20 MB beyond the host; REGISTRY's lookup file is read with
  a bisect over a sorted file, not loaded whole.
- The art channels may use full screen (no spine), like TRIPPY.

## Calls made by the designer
- Channel order: MINER after SYSTEM, MOST WANTED after THREATS, REGISTRY after AIRSPACE,
  TERMINAL before the video channels, the four art channels after TRIPPY.
- XMRig's API is published on arch's LAN address only, with a random access token
  (`~/xmrig/.api-token` on arch); restricted mode, so it is read-only.
