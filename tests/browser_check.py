"""End-to-end browser checks for the dashboard (not collected by pytest).

Serve the dashboard, then run:
    cd dashboard; python -m http.server 8765
    python tests/browser_check.py [--url http://localhost:8765/]

Runs desktop (1440x900), mobile (390x844) and reduced-motion (1280x800)
passes and exits non-zero on any failure. Screenshots go to
.cache/browser-shots/ (git-ignored). Needs Playwright with Chromium.
"""

import argparse
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

_args = argparse.ArgumentParser()
_args.add_argument("--url", default="http://localhost:8765/")
URL = _args.parse_args().url.rstrip("/") + "/"
OUT = Path(__file__).resolve().parents[1] / ".cache" / "browser-shots"
OUT.mkdir(parents=True, exist_ok=True)
results = []


def check(name, cond, info: object = ""):
    results.append((name, bool(cond), info))


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")


def run(pw, width, height, reduced, tag):
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": width, "height": height},
                              reduced_motion="reduce" if reduced else "no-preference")
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))

    # Normal map
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("#vessel-list button")
    check(f"{tag}: fleet markers drawn", page.locator(".leaflet-interactive").count() >= 276)
    check(f"{tag}: replay toggle visible", page.is_visible("#replay-open"))
    check(f"{tag}: no horizontal overflow (map)", not overflow(page))
    page.screenshot(path=str(OUT / f"{tag}-1-latest.png"))

    # Search by former name, open dossier
    page.fill("#vessel-search", "longevity")
    check(f"{tag}: search finds WOLF", page.locator('#vessel-list button[data-imo="9240885"]').count() == 1)
    page.click('#vessel-list button[data-imo="9240885"]')
    page.wait_for_selector("#view-dossier:not([hidden])")
    rows = page.locator("#d-matrix tbody tr")
    check(f"{tag}: matrix has 8 rows plus radar rows", rows.count() >= 8, rows.count())
    radar = page.inner_text("#d-matrix tr.row-radar") if page.locator("#d-matrix tr.row-radar").count() else ""
    check(f"{tag}: radar row observed", "Observed" in radar and "radar detection" in radar, radar)
    match = page.inner_text("#d-matrix tr.row-our_match") if page.locator("#d-matrix tr.row-our_match").count() else ""
    check(f"{tag}: our match is a model estimate", "Model estimate" in match, match)
    img_ok = page.evaluate("(() => { const i = document.querySelector('#d-matrix .ev-figure img'); if (!i) return false; "
                           "i.loading = 'eager'; return new Promise(r => { if (i.complete) r(i.naturalWidth > 0); "
                           "else { i.onload = () => r(true); i.onerror = () => r(false); } }); })()")
    check(f"{tag}: radar image loads", img_ok)
    check(f"{tag}: matrix total 75", page.inner_text("#d-total").strip() == "75", page.inner_text("#d-total"))
    check(f"{tag}: score 75", page.inner_text("#d-score").strip() == "75")
    cargo = page.inner_text("#d-matrix tr.row-cargo")
    check(f"{tag}: cargo row unknown", "Unavailable / unknown" in cargo and "Unknown." in cargo, cargo)
    check(f"{tag}: encounters not observed", "Not observed" in page.inner_text("#d-matrix tr.row-encounters"))
    check(f"{tag}: source links", page.locator("#d-sources a").count() == 2)
    check(f"{tag}: hash deep link", page.evaluate("location.hash") == "#imo=9240885")
    check(f"{tag}: track legend shown", "Loitering offshore" in page.inner_text(".key"))
    check(f"{tag}: no horizontal overflow (dossier)", not overflow(page))
    page.screenshot(path=str(OUT / f"{tag}-2-dossier.png"), full_page=(width < 500))
    page.locator(".matrix").screenshot(path=str(OUT / f"{tag}-2b-matrix.png"))

    # Event click in the dossier
    page.locator("#d-events button").first.click()
    page.wait_for_timeout(600)
    check(f"{tag}: event click zooms", page.evaluate("map.getZoom()") == 7)

    # Escape returns, focus goes back to the list button
    page.keyboard.press("Escape")
    check(f"{tag}: escape closes dossier", page.is_hidden("#view-dossier"))
    check(f"{tag}: focus returned to list", page.evaluate("document.activeElement.dataset.imo") == "9240885")
    page.fill("#vessel-search", "")

    # Replay via keyboard
    page.focus("#replay-open")
    page.keyboard.press("Enter")
    page.wait_for_selector("#replay:not([hidden])")
    check(f"{tag}: slider focused", page.evaluate("document.activeElement.id") == "replay-slider")
    check(f"{tag}: starts at latest month", "September 2026" in page.inner_text("#replay-period"))
    check(f"{tag}: fleet layer hidden", page.evaluate("!map.hasLayer(fleetLayer)"))
    n_last = page.evaluate("replay.index.observations(replay.index.months.at(-1)).length")
    check(f"{tag}: markers equal observations", page.locator(".leaflet-marker-pane .event-icon, path.leaflet-interactive").count() == n_last,
          (page.locator(".leaflet-marker-pane .event-icon, path.leaflet-interactive").count(), n_last))
    check(f"{tag}: list filtered to month", "Vessels with observations in September 2026" in page.inner_text("#vessels-title"))
    check(f"{tag}: next disabled at end", page.is_disabled("#replay-next"))
    page.keyboard.press("ArrowLeft")
    check(f"{tag}: arrow key steps back", "August 2026" in page.inner_text("#replay-period"), page.inner_text("#replay-period"))
    page.keyboard.press("Home")
    check(f"{tag}: Home to first month", "September 2025" in page.inner_text("#replay-period")
          and "partial" in page.inner_text("#replay-period"))
    check(f"{tag}: prev disabled at start", page.is_disabled("#replay-prev"))
    page.click("#replay-next")
    check(f"{tag}: next button", "October 2025" in page.inner_text("#replay-period"))
    check(f"{tag}: no overflow (replay)", not overflow(page))
    page.screenshot(path=str(OUT / f"{tag}-3-replay.png"), full_page=(width < 500))

    # Play / pause
    page.click("#replay-play")
    check(f"{tag}: play pressed", page.get_attribute("#replay-play", "aria-pressed") == "true")
    page.wait_for_timeout(3200 if reduced else 1700)
    period = page.inner_text("#replay-period")
    check(f"{tag}: play advanced", "October 2025" not in period, period)
    page.click("#replay-play")
    check(f"{tag}: pause", page.get_attribute("#replay-play", "aria-pressed") == "false")
    held = page.inner_text("#replay-period")
    page.wait_for_timeout(1800)
    check(f"{tag}: paused holds", page.inner_text("#replay-period") == held)

    # Reset to latest
    page.click("#replay-latest")
    check(f"{tag}: reset latest", "September 2026" in page.inner_text("#replay-period"))

    # Open a dossier from replay list, observations dim
    first = page.locator("#vessel-list button").first
    imo = first.get_attribute("data-imo")
    first.click()
    page.wait_for_selector("#view-dossier:not([hidden])")
    check(f"{tag}: dossier from replay", page.evaluate("location.hash") == f"#imo={imo}")
    check(f"{tag}: replay stays active", page.evaluate("replay.on") and page.is_visible("#replay"))
    page.screenshot(path=str(OUT / f"{tag}-4-replay-dossier.png"))
    page.click("#btn-back")

    # Open a dossier by clicking a replay marker on the map
    page.evaluate("window.scrollTo(0, 0); map.setView([25.4, 56.6], 8, {animate:false})")
    page.wait_for_timeout(300)
    pt = page.evaluate("""() => { const m = document.getElementById('map').getBoundingClientRect();
        for (const el of document.querySelectorAll('.leaflet-marker-pane .event-icon')) {
            const r = el.getBoundingClientRect(), x = r.x + r.width / 2, y = r.y + r.height / 2;
            if (x > m.left + 60 && x < m.right - 60 && y > m.top + 60 && y < m.bottom - 60
                && document.elementFromPoint(x, y)?.closest('.event-icon')) return [x, y];
        } return null; }""")
    check(f"{tag}: a replay marker is clickable", pt is not None)
    if pt:
        page.mouse.click(pt[0], pt[1])
        check(f"{tag}: marker click opens dossier", page.is_visible("#view-dossier"))
        page.click("#btn-back")

    # Empty month (synthetic): force an empty observation list
    page.evaluate("""() => { const o = replay.index.observations; replay.index.observations = () => []; setReplay(3);
                        window.__empty = document.getElementById('replay-counts').textContent + '|' + document.getElementById('vessel-list').textContent;
                        replay.index.observations = o; setReplay(3); }""")
    empty = page.evaluate("window.__empty")
    check(f"{tag}: empty month message", "No positioned observations" in empty and "No vessel has a positioned" in empty, empty)

    # Exit replay
    page.click("#replay-exit")
    check(f"{tag}: exit restores fleet", page.evaluate("map.hasLayer(fleetLayer) && !replay.on") and page.is_hidden("#replay"))
    check(f"{tag}: list restored", page.inner_text("#vessels-title") == "Vessels")

    # Deep link + vessel without positioned events
    page.goto(URL + "#imo=9308065", wait_until="networkidle")
    page.wait_for_selector("#view-dossier:not([hidden])")
    fresh = page.inner_text("#d-matrix tr.row-freshness")
    check(f"{tag}: no-position vessel freshness unknown", "Unavailable / unknown" in fresh, fresh)
    check(f"{tag}: no-position events empty", "No loitering" in page.inner_text("#d-events"))
    page.goto(URL + "#imo=9240885", wait_until="networkidle")
    page.wait_for_selector("#view-dossier:not([hidden])")
    check(f"{tag}: deep link opens WOLF", page.inner_text("#d-name") == "Wolf")
    # hashchange
    page.evaluate("location.hash = '#imo=9242223'")
    page.wait_for_timeout(200)
    gap = page.inner_text("#d-matrix tr.row-ais_gaps")
    check(f"{tag}: hashchange opens vessel with gap", "possible intentional disabling" in gap, gap)

    # Focus visibility on a replay button via Tab
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("#vessel-list button")
    page.focus("#replay-open")
    outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
    page.keyboard.press("Tab"); page.keyboard.press("Shift+Tab")
    outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
    check(f"{tag}: visible focus outline", outline == "solid", outline)
    if reduced:
        anim = page.evaluate("getComputedStyle(document.getElementById('view-monitor')).animationName")
        check(f"{tag}: reduced motion disables animation", anim == "none", anim)

    # Models page renders every figure from sar.json
    page.goto(URL + "models.html", wait_until="networkidle")
    page.wait_for_selector("#detector table")
    body = page.inner_text("#card")
    check(f"{tag}: models page tables", page.locator(".metrics").count() >= 3)
    check(f"{tag}: models page states the cargo no-go", "No-go" in body or "may be shown" in body)
    check(f"{tag}: models page names its reference", "not ground truth" in body)
    check(f"{tag}: no overflow (models)", not overflow(page))

    check(f"{tag}: no console errors", not errors, errors)
    browser.close()


with sync_playwright() as pw:
    run(pw, 1440, 900, False, "desktop")
    run(pw, 390, 844, False, "mobile")
    run(pw, 1280, 800, True, "reduced")

bad = [r for r in results if not r[1]]
for name, ok, info in results:
    print("PASS" if ok else "FAIL", name, "" if ok else info)
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
