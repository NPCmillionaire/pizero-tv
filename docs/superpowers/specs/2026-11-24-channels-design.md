# Channels — TV channel feel + video channels

Approved 2026-11-24 ("yeah build it that way, and add more modules… youtube shorts…
computerphile, etc").

## Intent
Switching screens should feel like flipping channels on a TV, not loading an app. And the
suite gains video channels that play YouTube (Shorts, Computerphile, and any channel the
user adds).

## Channel feel (as proposed and approved)
- Every module has a fixed channel number: its position in the default order, from 01.
  Channel 00 is a new **guide** listing every channel, its blurb, and the repo link
  `github.com/NPCmillionaire/pizero-tv`.
- `tv up`, `tv down`, `tv <number>` (and `tv ch <n>`); keyboard Up/Down and digit keys.
  Two digits typed within 1.2 s form one channel number.
- Switch transition: ~0.4 s of analog static with a rolling bar, then the new channel
  appears immediately (it shows its own waiting state if data isn't in yet). Replaces the
  splash card.
- On-screen display: green `CH 04  MARKETS` top-right for 3 s after every switch, fading.
- Station ID: `legitbiz.research` stays bottom-right on every channel (existing footer).
- Cycle mode is channel surfing: same transition.

## Video channels
- Built-in: **COMPUTERPHILE** (random from the channel's latest uploads) and **SHORTS**
  (random Shorts from a configurable list of channels; default science/engineering
  creators). More via config:
  ```toml
  [[video]]
  name = "numberphile"
  title = "NUMBERPHILE"
  url = "https://www.youtube.com/@numberphile/videos"
  ```
- Playback: mpv fullscreen (Wayland, hardware H.264 decode in v4l2m2m-copy mode, ≤480p avc1 via yt-dlp —
  measured on the Pi: 720p and zero-copy paths don't work with this mpv/labwc), English captions on,
  launched by the module; when a video ends the next random one starts. Switching away
  kills mpv. The host stops redrawing while an external player owns the screen.
  The channel OSD is shown by mpv itself (`--osd-playing-msg`). Up/Down/digits inside
  mpv run `tv up/down/<n>` so the remote still works.
- Listings come from `yt-dlp --flat-playlist -J`, cached 6 h on disk; the module shows a
  "tuning in / now playing <title>" card while mpv starts.
- Requires `mpv` (apt) and a current `yt-dlp` (standalone binary in `~/.local/bin`;
  Debian's packaged one is too old for YouTube). `deploy.sh` checks and says what's missing.

## Constraints
- Pi Zero 2 W memory: mpv + host must fit; host drops to 2 FPS and draws nothing while
  mpv plays.
- Real or nothing: if YouTube or mpv fails, the channel says so (no placeholder video).

## Calls made by the designer
- Default Shorts sources: @veritasium, @SmarterEveryDay, @minutephysics, @TomScottGo,
  @StandUpMaths (user can replace in config).
- Registry accepts `MODULES = [...]` so one package can provide several channels.
- Channel numbers follow `order`; video channels come after the data channels, art last.
