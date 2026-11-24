"""YouTube listings (yt-dlp --flat-playlist) and the mpv command line for video channels."""
import random, re
from dataclasses import dataclass

# Pi Zero 2 W: H.264 hardware decode in copy mode is the only path this mpv/labwc pairing supports;
# 480p keeps the copy + GL upload inside the CPU budget (720p ran out of time and dropped audio).
FORMAT = "bv*[height<=480][vcodec^=avc1]+ba/b[height<=480]"
OSD_GREEN = "#7CFF6B"
UNAVAILABLE = {"[Private video]", "[Deleted video]"}


@dataclass
class Entry:
    id: str
    title: str
    duration: int | None
    url: str


def parse_listing(p):
    out = []
    for e in p.get("entries") or []:
        if not e or not e.get("id") or (e.get("title") or "") in UNAVAILABLE:
            continue
        url = e.get("url") or f"https://www.youtube.com/watch?v={e['id']}"
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={e['id']}"
        out.append(Entry(e["id"], e.get("title") or e["id"], e.get("duration"), url))
    if not out:
        raise ValueError("listing has no playable videos")
    return out


def pick(entries, recent, seed=None):
    rng = random.Random(seed)
    fresh = [e for e in entries if e.id not in set(recent)]
    return rng.choice(fresh or entries)


def clean_title(t):
    return re.sub(r"\s+[-|–]\s+(Computerphile|Numberphile|Sixty Symbols)$", "", t).strip()


def mpv_args(entry, channel_no, title, ytdl, input_conf):
    return ["mpv", "--fs", "--really-quiet", "--no-terminal", "--hwdec=v4l2m2m-copy", "--vo=gpu",
            "--gpu-context=wayland", "--profile=fast", "--framedrop=vo", "--video-sync=audio",
            "--demuxer-max-bytes=24MiB", f"--ytdl-format={FORMAT}",
            # captions: the video's English subtitles, or YouTube's automatic ones
            "--sub-visibility=yes", "--slang=en,en-US,en-GB,en-orig", "--sub-font-size=46", "--sub-border-size=3",
            "--ytdl-raw-options-append=write-auto-subs=", "--ytdl-raw-options-append=sub-langs=en.*",
            f"--script-opts=ytdl_hook-ytdl_path={ytdl}", f"--input-conf={input_conf}",
            f"--osd-playing-msg=CH {channel_no:02d}  {title}\\n{clean_title(entry.title)}", "--osd-duration=3000",
            f"--osd-color={OSD_GREEN}", "--osd-align-x=right", "--osd-align-y=top", "--osd-font-size=40",
            "--keep-open=no", entry.url]


def input_conf(tv):
    lines = [f'UP run "{tv}" up', f'DOWN run "{tv}" down', f'PGUP run "{tv}" up', f'PGDWN run "{tv}" down',
             "q ignore", "Q ignore", "ESC ignore"]
    for d in range(10):
        lines += [f'{d} run "{tv}" digit {d}', f'KP{d} run "{tv}" digit {d}']
    return "\n".join(lines) + "\n"


def parse_json_lines(out):
    """yt-dlp -J with several URLs prints one JSON document per line; collect every entry."""
    import json
    entries = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries += json.loads(line).get("entries") or []
        except ValueError:
            continue
    return entries
