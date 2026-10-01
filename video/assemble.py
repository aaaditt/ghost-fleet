"""Assemble the demo video: scene clips + crossfades + narration + subtitles.

Reads video/build/scenes/*.mp4 (record_scenes.py) and video/build/audio/*.mp3
(make_voice.py). Writes:
  dashboard/media/ghost-fleet-demo.mp4   1080p30 H.264 + AAC, loudness-normalised
  dashboard/media/ghost-fleet-demo.srt   subtitles from the ElevenLabs timestamps
  dashboard/media/ghost-fleet-demo.vtt   the same, for the watch page's <track>
  dashboard/media/poster.jpg             video poster (also the README thumbnail)
The media is served by the live site (ghost-fleet.vercel.app/watch.html), so
browsers stream it instead of downloading a raw GitHub file.

Usage: python video/assemble.py [--crf 23]
"""

import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build"
MEDIA = ROOT / "dashboard" / "media"
OUT = MEDIA / "ghost-fleet-demo.mp4"
SRT = OUT.with_suffix(".srt")
VTT = OUT.with_suffix(".vtt")
POSTER = MEDIA / "poster.jpg"
XF = 0.8                    # crossfade between scenes, seconds
CHAPTERS = {
    "title": "Ghost Fleet", "problem": "The shadow fleet", "landing": "The globe",
    "trend": "The trend", "ports": "Where they call", "search": "Search a former name",
    "identities": "One hull, seven identities", "score": "The evidence matrix",
    "radar": "Seen by satellite radar", "passes": "Every radar pass", "replay": "Evidence replay",
    "honesty": "What we don't claim", "fleet": "The whole fleet", "close": "What's next",
}

PLAY_FONT = r"C\:/Windows/Fonts/seguisym.ttf"   # has the ▶ glyph; colon escaped for ffmpeg

_spec = importlib.util.spec_from_file_location("rs", HERE / "record_scenes.py")
assert _spec and _spec.loader
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)         # reuse lead(), length(), cue(), timings


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def chunks(text, limit=64):
    """Split narration into subtitle lines at sentence and clause breaks."""
    parts = re.split(r"(?<=[.?!:])\s+|(?<=,)\s+(?=\S)", text)
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + 1 + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        out.append(cur)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crf", type=int, default=23)
    args = parser.parse_args()

    order = [s["id"] for s in rs.SPEC["scenes"]]
    lengths = [rs.length(s) for s in order]
    starts, t = [], 0.0
    for L in lengths:
        starts.append(t)
        t += L - XF
    total = starts[-1] + lengths[-1]

    # ── video: crossfade chain ──
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for sid in order:
        cmd += ["-i", str(BUILD / "scenes" / f"{sid}.mp4")]
    for sid in order:
        cmd += ["-i", str(BUILD / "audio" / f"{sid}.mp3")]
    n = len(order)
    f, prev = [], "0:v"
    for i in range(1, n):
        label = f"v{i}"
        f.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={XF}:offset={starts[i]:.3f}[{label}]")
        prev = label
    f.append(f"[{prev}]fade=t=in:st=0:d=1.0,fade=t=out:st={total - 1.6:.3f}:d=1.6,format=yuv420p[vout]")

    # ── audio: each narration clip at its scene start + lead ──
    amix_in = []
    for i, sid in enumerate(order):
        delay = int(round((starts[i] + rs.lead(sid)) * 1000))
        f.append(f"[{n + i}:a]aresample=48000,adelay={delay}|{delay}[a{i}]")
        amix_in.append(f"[a{i}]")
    f.append(f"{''.join(amix_in)}amix=inputs={n}:normalize=0:dropout_transition=0,"
             f"apad=whole_dur={total:.3f},atrim=0:{total:.3f},"
             f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={total - 1.2:.3f}:d=1.2[aout]")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf), "-profile:v", "high",
            "-r", "30", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
            "-metadata", "title=Ghost Fleet — hidden oil supply, seen from the sea", str(OUT)]
    subprocess.run(cmd, check=True)

    # ── subtitles from character timestamps ──
    lines, k = [], 1
    for i, sid in enumerate(order):
        tm = rs.TIMINGS[sid]
        text = "".join(tm["chars"])
        base = starts[i] + rs.lead(sid)
        pos = 0
        for c in chunks(text):
            a = text.index(c, pos)
            b = a + len(c) - 1
            pos = b + 1
            lines.append(f"{k}\n{srt_time(base + tm['starts'][a])} --> {srt_time(base + tm['ends'][b] + 0.25)}\n{c}\n")
            k += 1
    SRT.write_text("\n".join(lines), encoding="utf-8")
    vtt = [re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", ln) for ln in lines]
    VTT.write_text("WEBVTT\n\n" + "\n".join(vtt), encoding="utf-8")

    # ── chapters for the watch page (scene start times in the final cut) ──
    (MEDIA / "chapters.json").write_text(json.dumps(
        [{"id": sid, "title": CHAPTERS[sid], "start": round(starts[i], 2)} for i, sid in enumerate(order)],
        indent=1), encoding="utf-8")

    # ── poster: WOLF's identities, with a play badge ──
    ident = order.index("identities")
    at = starts[ident] + rs.lead("identities") + rs.cue("identities", "Seven identities") + 1.5
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", str(OUT), "-frames:v", "1",
                    "-vf", "scale=1280:-1,drawbox=x=(iw-150)/2:y=(ih-150)/2:w=150:h=150:color=0x050c12@0.8:t=fill,"
                           f"drawtext=fontfile='{PLAY_FONT}':text='▶':fontcolor=white:fontsize=84:x=(w-text_w)/2+6:y=(h-text_h)/2",
                    "-q:v", "3", str(POSTER)], check=True)

    size = OUT.stat().st_size / 1e6
    print(f"{OUT.relative_to(ROOT)}  {total:.1f}s  {size:.1f} MB")
    print(f"{SRT.relative_to(ROOT)}  {k - 1} cues")
    print(f"{POSTER.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
