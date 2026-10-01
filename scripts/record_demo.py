"""Record the live Ghost Fleet demo path and convert it to docs/demo.gif.

Usage: python scripts/record_demo.py [--url https://ghost-fleet.vercel.app]
Needs: Playwright for Python with Chromium, and ffmpeg on PATH.
"""

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import ViewportSize, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo.gif"
SIZE: ViewportSize = {"width": 1280, "height": 800}


def record(url: str, video_dir: Path) -> Path:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        ctx = browser.new_context(viewport=SIZE, record_video_dir=str(video_dir), record_video_size=SIZE)
        page = ctx.new_page()
        page.goto(url + "?v=demo", wait_until="networkidle")
        page.wait_for_selector("body.ready #vessel-list button")
        page.wait_for_timeout(3000)                      # land on the globe
        page.click("#vessel-search")
        page.keyboard.type("longevity", delay=120)       # search a former name
        page.wait_for_timeout(900)
        page.click('#vessel-list button[data-imo="9240885"]')
        page.wait_for_timeout(2500)                      # map zooms to WOLF's activity
        rail = page.locator("#rail")
        for _ in range(6):                               # read the identity list
            rail.evaluate("el => el.scrollBy({top: 110, behavior: 'smooth'})")
            page.wait_for_timeout(450)
        page.wait_for_timeout(1200)
        rail.evaluate("el => el.scrollBy({top: el.querySelector('#d-matrix tr.row-radar').getBoundingClientRect().top"
                      " - el.getBoundingClientRect().top - 16, behavior: 'smooth'})")
        page.wait_for_timeout(3200)                      # radar evidence and WOLF's radar image
        page.click("#d-matrix [data-radar-pass]")       # fly in: the radar image on the satellite map
        page.wait_for_timeout(5500)
        page.click("#lens-blink")                        # optical versus radar
        page.wait_for_timeout(2600)
        page.click("#lens-blink")
        page.click("#lens-next")                         # the next pass of the same ship
        page.wait_for_timeout(2400)
        page.click("#replay-open")                       # historical evidence replay
        page.wait_for_timeout(1500)
        page.click("#replay-play")
        page.wait_for_timeout(6000)                      # a few months of recorded evidence
        page.click("#replay-exit")
        page.wait_for_timeout(1500)
        page.click("#btn-back")                          # back to the whole fleet
        page.wait_for_timeout(2200)
        assert page.video is not None
        video = page.video.path()
        ctx.close()
        browser.close()
    return Path(video)


def to_gif(src: Path, fps: int, width: int, colors: int) -> None:
    palette = src.with_suffix(".png")
    flt = f"fps={fps},scale={width}:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.6", "-i", str(src),
                    "-vf", f"{flt},palettegen=max_colors={colors}:stats_mode=diff", str(palette)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.6", "-i", str(src), "-i", str(palette),
                    "-lavfi", f"{flt}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                    str(OUT)], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://ghost-fleet.vercel.app/")
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is not on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        video = record(args.url.rstrip("/") + "/", Path(tmp))
        # The satellite basemap is photographic, so GIFs of it are heavy:
        # step down frame rate, width and palette until it fits.
        tiers = ((12, 960, 256), (10, 880, 192), (10, 800, 128), (8, 800, 128), (8, 720, 96), (6, 720, 96), (6, 640, 80), (5, 640, 64))
        for fps, width, colors in tiers:
            to_gif(video, fps, width, colors)
            size = OUT.stat().st_size
            print(f"docs/demo.gif  {fps} fps  {width}px  {colors} colours  {size / 1e6:.1f} MB")
            if size <= 8_000_000:
                break
        else:
            raise SystemExit("GIF is still over 8 MB; shorten the path or use the screenshot fallback")


if __name__ == "__main__":
    main()
