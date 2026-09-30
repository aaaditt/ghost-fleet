"""Capture the README screenshots from the live site (1440x900).

Usage: python scripts/screenshots.py [--url https://ghost-fleet.vercel.app]
Writes docs/screenshot-{overview,dossier,radar,replay}.png. Needs Playwright.
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parents[1] / "docs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://ghost-fleet.vercel.app")
    url = ap.parse_args().url.rstrip("/") + "/"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.goto(url, wait_until="networkidle")
        page.wait_for_selector("#vessel-list button")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(DOCS / "screenshot-overview.png"))

        page.goto(url + "#imo=9240885", wait_until="networkidle")
        page.wait_for_selector("#view-dossier:not([hidden])")
        page.wait_for_timeout(2500)
        page.evaluate("""(() => { const rail = document.getElementById('rail');
            const t = document.getElementById('matrix-title');
            rail.scrollTop += t.getBoundingClientRect().top - rail.getBoundingClientRect().top - 24; })()""")
        page.wait_for_timeout(500)
        page.screenshot(path=str(DOCS / "screenshot-dossier.png"))

        page.evaluate("""(() => { const rail = document.getElementById('rail');
            const row = document.querySelector('#d-matrix tr.row-radar');
            rail.scrollTop += row.getBoundingClientRect().top - rail.getBoundingClientRect().top - 16; })()""")
        page.wait_for_timeout(800)
        page.screenshot(path=str(DOCS / "screenshot-radar.png"))

        page.click("#btn-back")
        page.click("#replay-open")
        page.evaluate("setReplay(replay.index.months.indexOf('2026-07')); map.setView([33, 52], 3, {animate: false})")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(DOCS / "screenshot-replay.png"))
        browser.close()
    print("docs/screenshot-{overview,dossier,radar,replay}.png")


if __name__ == "__main__":
    main()
