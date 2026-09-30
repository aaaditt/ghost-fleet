"""Record every scene of the demo video at 1920x1080.

Each scene lasts LEAD + its narration + TAIL seconds, and its on-screen
actions fire when the narrator reaches the matching phrase (from the
ElevenLabs character timestamps in video/build/timings.json). Frames come
from Chrome's screencast, so animations are captured at full quality.

Usage: python video/record_scenes.py [--only landing,trend] [--url https://ghost-fleet.vercel.app/]
Writes video/build/scenes/<scene>.mp4
"""

import argparse
import asyncio
import base64
import json
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
FRAMES = BUILD / "frames"
SCENES = BUILD / "scenes"
W, H = 1920, 1080
LEAD, TAIL = 0.8, 1.4
# Chrome's screencast delivers ~15 fps at 1080p. Pages run at 1/SLOW speed
# (JS clocks, timers, animation frames and CSS animations), are captured in
# real time, and the frames are re-timed by 1/SLOW: ~45 fps of video time.
SLOW = 3
CARD_LEAD = {"title": 1.8}          # let the title settle before the voice
CARD_TAIL = {"close": 4.0}          # hold the end card

TIMINGS = json.loads((BUILD / "timings.json").read_text(encoding="utf-8"))
SPEC = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))


def lead(sid): return CARD_LEAD.get(sid, LEAD)
def length(sid): return lead(sid) + TIMINGS[sid]["duration"] + CARD_TAIL.get(sid, TAIL)


def cue(sid, phrase, nth=1):
    """Seconds from the narration start at which `phrase` begins."""
    text = "".join(TIMINGS[sid]["chars"])
    i = -1
    for _ in range(nth):
        i = text.find(phrase, i + 1)
        if i < 0:
            raise KeyError(f"{sid}: phrase not in narration: {phrase!r}")
    return TIMINGS[sid]["starts"][i]


# ── Overlays injected into the live site ──────────────────────────────
OVERLAY_JS = r"""
() => {
  const css = document.createElement('style');
  css.textContent = `
    #vx-cursor { position: fixed; left: 0; top: 0; width: 26px; height: 26px; margin: -13px 0 0 -13px;
      border-radius: 50%; border: 2.5px solid #1c2a35; background: rgba(248,250,250,.55);
      box-shadow: 0 2px 10px rgba(28,42,53,.25); z-index: 99999; pointer-events: none; opacity: 0;
      transition: transform 1.1s cubic-bezier(.45,.05,.25,1), opacity .5s ease; }
    #vx-cursor.press { animation: vxpress .45s ease; }
    @keyframes vxpress { 50% { box-shadow: 0 0 0 12px rgba(163,22,95,.25); } }
    #vx-ring { position: fixed; z-index: 99998; pointer-events: none; border: 3px solid #a3165f; border-radius: 6px;
      box-shadow: 0 0 0 6px rgba(163,22,95,.14); opacity: 0;
      transition: left .8s cubic-bezier(.45,.05,.25,1), top .8s cubic-bezier(.45,.05,.25,1),
                  width .8s cubic-bezier(.45,.05,.25,1), height .8s cubic-bezier(.45,.05,.25,1), opacity .5s ease; }
    #vx-cap { position: fixed; left: 40px; bottom: 90px; z-index: 99997; max-width: 900px; pointer-events: none; padding: 18px 26px 18px 24px;
      background: rgba(248,250,250,.96); border-left: 6px solid #a3165f; color: #1c2a35;
      font: 500 30px/1.3 "Public Sans", sans-serif; box-shadow: 0 8px 30px rgba(28,42,53,.18);
      opacity: 0; transform: translateY(18px); transition: opacity .7s ease, transform .9s cubic-bezier(.2,.7,.2,1); }
    #vx-cap.in { opacity: 1; transform: none; }
    #vx-cap small { display: block; margin-top: 4px; font-size: 21px; font-weight: 400; color: #55686f; }
    #rail { scroll-behavior: auto !important; }
  `;
  document.head.appendChild(css);
  for (const id of ['vx-cursor', 'vx-ring', 'vx-cap']) {
    const d = document.createElement('div'); d.id = id; document.body.appendChild(d);
  }
  window.vx = {
    cursorTo(x, y) { const c = document.getElementById('vx-cursor'); c.style.opacity = 1; c.style.transform = `translate(${x}px, ${y}px)`; },
    cursorToEl(sel, dx = 0.5, dy = 0.5) {
      const r = document.querySelector(sel).getBoundingClientRect();
      this.cursorTo(r.left + r.width * dx, r.top + r.height * dy);
    },
    press() { const c = document.getElementById('vx-cursor'); c.classList.remove('press'); void c.offsetWidth; c.classList.add('press'); },
    hideCursor() { document.getElementById('vx-cursor').style.opacity = 0; },
    ring(sel, pad = 8) {
      const g = document.getElementById('vx-ring');
      if (!sel) { g.style.opacity = 0; return; }
      const r = document.querySelector(sel).getBoundingClientRect();
      Object.assign(g.style, { left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + 2 * pad}px`,
                               height: `${r.height + 2 * pad}px`, opacity: 1 });
    },
    caption(html) {
      const c = document.getElementById('vx-cap');
      if (!html) { c.classList.remove('in'); return; }
      if (c.classList.contains('in')) { c.classList.remove('in'); setTimeout(() => { c.innerHTML = html; c.classList.add('in'); }, 450); }
      else { c.innerHTML = html; c.classList.add('in'); }
    },
    scrollRail(target, seconds) {          // eased scroll of the sidebar; target = px or selector.
                                           // Fire-and-forget: the scene script's own pause sets the timing.
      const rail = document.getElementById('rail');
      const to = typeof target === 'number' ? target
        : rail.scrollTop + document.querySelector(target).getBoundingClientRect().top - rail.getBoundingClientRect().top - 24;
      const from = rail.scrollTop, t0 = performance.now(), ms = seconds * 1000;
      const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      (function step(now) {
        const k = Math.min(1, (now - t0) / ms);
        rail.scrollTop = from + (to - from) * ease(k);
        if (k < 1) requestAnimationFrame(step);
      })(t0);
    },
  };
  // Leaflet: make every camera move a slow, smooth flight.
  const fit = map.fitBounds.bind(map);
  map.fitBounds = (b, o) => map.flyToBounds(b, { ...(o || {}), duration: 3.2, easeLinearity: 0.15 });
  const setView = map.setView.bind(map);
  map.setView = (c, z) => map.flyTo(c, z, { duration: 2.6, easeLinearity: 0.15 });
}
"""


SLOW_TIME_JS = """
(() => {
  if (window.__vxSlow) return;          // init scripts can run more than once per window
  window.__vxSlow = true;
  const S = %d;
  const pn = performance.now.bind(performance), p0 = pn();
  const dn = Date.now, d0 = dn();
  performance.now = () => p0 + (pn() - p0) / S;
  Date.now = () => d0 + (dn() - d0) / S;
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = cb => raf(() => cb(performance.now()));   // same slowed clock
  const st = window.setTimeout.bind(window), si = window.setInterval.bind(window);
  window.setTimeout = (f, ms, ...a) => st(f, (ms || 0) * S, ...a);
  window.setInterval = (f, ms, ...a) => si(f, (ms || 0) * S, ...a);
})();
""" % SLOW


async def slow_page(browser):
    """A 1920x1080 page whose clocks, timers, rAF and CSS animations run at 1/SLOW speed."""
    page = await browser.new_page(viewport={"width": W, "height": H})
    await page.add_init_script(SLOW_TIME_JS)
    cdp = await page.context.new_cdp_session(page)
    await cdp.send("Animation.enable")
    await cdp.send("Animation.setPlaybackRate", {"playbackRate": 1 / SLOW})
    return page, cdp


class Recorder:
    """Collects screencast frames with their capture timestamps.

    Each frame is written to disk as it arrives (a 1080p scene can hold
    thousands of JPEGs); only (timestamp, path) pairs stay in memory.
    """

    def __init__(self, cdp):
        self.cdp, self.frames, self.t0 = cdp, [], None
        self.stopped = False
        self.raw = FRAMES / "_raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        for f in self.raw.glob("*.jpg"):
            f.unlink()

    async def start(self):
        self.cdp.on("Page.screencastFrame", self._on_frame)
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92,
                                                     "maxWidth": W, "maxHeight": H, "everyNthFrame": 1})
        await asyncio.sleep(0.4)
        self.t0 = time.time()

    def _on_frame(self, ev):
        path = self.raw / f"r{len(self.frames):06d}.jpg"
        path.write_bytes(base64.b64decode(ev["data"]))
        self.frames.append((ev["metadata"]["timestamp"], path))
        if not self.stopped:
            asyncio.ensure_future(self._ack(ev["sessionId"]))

    async def _ack(self, session_id):
        try:
            await self.cdp.send("Page.screencastFrameAck", {"sessionId": session_id})
        except Exception:
            pass  # the page may already be closed after the last frame

    async def wait_until(self, seconds):
        """Wait until `seconds` of VIDEO time have passed since the scene started."""
        delay = self.t0 + seconds * SLOW - time.time()
        if delay > 0:
            await asyncio.sleep(delay)

    async def sleep(self, seconds):
        await asyncio.sleep(seconds * SLOW)

    async def stop(self, sid, total):
        await self.wait_until(total + 0.1)
        self.stopped = True
        await self.cdp.send("Page.stopScreencast")
        write_video(sid, self.frames, self.t0, total)


def write_video(sid, frames, t0, total):
    """Frames at their real timestamps -> constant 30 fps H.264 clip of exactly `total` seconds."""
    out_dir = FRAMES / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.jpg"):
        f.unlink()
    frames = [((ts - t0) / SLOW + t0, data) for ts, data in frames]   # wall clock -> video time
    before = [f for f in frames if f[0] <= t0]
    kept = ([before[-1]] if before else []) + [f for f in frames if t0 < f[0] <= t0 + total]
    if not kept:
        raise SystemExit(f"{sid}: no frames captured")
    lines = []
    for n, (ts, data) in enumerate(kept):
        name = f"f{n:05d}.jpg"
        (out_dir / name).write_bytes(data.read_bytes() if isinstance(data, Path) else data)
        start = max(ts - t0, 0.0)
        end = (kept[n + 1][0] - t0) if n + 1 < len(kept) else total
        lines.append(f"file '{name}'\nduration {max(end - start, 0.001):.4f}")
    lines.append(f"file 'f{len(kept) - 1:05d}.jpg'")
    (out_dir / "list.txt").write_text("\n".join(lines), encoding="utf-8")
    SCENES.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(out_dir / "list.txt"),
                    "-vf", f"fps=30,scale={W}:{H}:flags=lanczos,format=yuv420p", "-t", f"{total:.3f}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "14", str(SCENES / f"{sid}.mp4")], check=True)
    print(f"  {sid:<11} {total:5.1f}s  {len(kept)} frames")


# ── Scene scripts ─────────────────────────────────────────────────────
# Each receives the page, the recorder and helpers; `at(phrase)` waits
# until the narrator reaches that phrase in this scene.

async def scene_landing(page, rec, at):
    await page.evaluate("map.flyTo([40, 52], 3.35, {duration: 16, easeLinearity: 0.05})")
    await at("three hundred")
    await page.evaluate("vx.caption('300 most-sanctioned shadow-fleet tankers<small>OpenSanctions + a year of Global Fishing Watch tracking</small>')")
    await at("Two hundred and seventy-six")
    await page.evaluate("vx.caption('276 located at their latest observed position')")
    await at("Magenta")
    await page.evaluate("vx.caption('Magenta: risk score 70 or higher')")


async def scene_trend(page, rec, at):
    await page.evaluate("vx.cursorToEl('#headline', 0.3, 0.5)")
    await at("fell ten percent")
    await page.evaluate("vx.ring('#headline', 12)")
    await page.evaluate("vx.caption('−10% active sanctioned tankers<small>June–August vs March–May: 595 vs 662 vessel-months</small>')")
    await at("The bars")
    await page.evaluate("vx.ring('.trend', 10); vx.cursorToEl('#trend-svg', 0.62, 0.3)")


async def scene_ports(page, rec, at):
    await page.evaluate("vx.caption(''); vx.ring(null)")
    await page.evaluate("vx.scrollRail('.figures', 2.4)")
    await rec.sleep(2.6)
    await page.evaluate("vx.ring('.figures', 10)")
    await at("where these tankers")
    await page.evaluate("vx.scrollRail('.ports', 2.2)")
    await rec.sleep(2.3)
    await page.evaluate("vx.ring('.ports', 10)")
    await at("Nakhodka")
    await page.evaluate("map.flyTo([42.8, 132.9], 5, {duration: 2.6}); vx.caption('Nakhodka · Pacific')")
    await at("Primorsk")
    await page.evaluate("map.flyTo([60.0, 28.4], 5, {duration: 2.8}); vx.caption('Primorsk and Ust-Luga · Baltic')")
    await at("Suez")
    await page.evaluate("map.flyTo([30.6, 32.4], 5, {duration: 2.8}); vx.caption('Suez and Port Said · on the way to Asia')")
    await at("We didn't")
    await page.evaluate("map.flyTo([42, 45], 3, {duration: 3}); vx.caption('Routes straight from the data, not drawn in')")


async def scene_search(page, rec, at):
    await page.evaluate("vx.caption(''); vx.ring(null)")
    await page.evaluate("vx.scrollRail('.vessels', 2.2)")
    await rec.sleep(2.3)
    await page.evaluate("vx.cursorToEl('#vessel-search', 0.25, 0.5)")
    await at("Search that old name")
    await page.evaluate("vx.press()")
    await page.click("#vessel-search")
    await page.keyboard.type("longevity", delay=170 * SLOW)
    await rec.sleep(0.6)
    await page.evaluate("vx.ring('#vessel-list li', 4); vx.cursorToEl('#vessel-list button', 0.3, 0.5)")
    await at("what it is called today")
    await page.evaluate("vx.caption('Search a former name: Longevity 7 → today’s Wolf')")


async def scene_identities(page, rec, at):
    await page.evaluate("vx.caption(''); vx.ring(null); vx.press()")
    await page.click('#vessel-list button[data-imo="9240885"]')
    await rec.sleep(0.4)
    await page.evaluate("vx.hideCursor()")
    await at("It began life")
    await page.evaluate("vx.scrollRail('#d-identities', 2.4)")
    await rec.sleep(2.5)
    for phrase, n in (("Torm Gertrud", 1), ("East One", 4), ("Longevity Seven", 5), ("Malawi", 6), ("Aruba", 7)):
        await at(phrase)
        await page.evaluate(f"vx.ring('#d-identities li:nth-child({n})', 6)")
        if phrase == "Malawi":
            await page.evaluate("vx.caption('Malawi: a landlocked flag')")
        if phrase == "Aruba":
            await page.evaluate("vx.caption('Now: Wolf, flagged to Aruba, since 7 September 2026')")
    await at("Seven identities")
    await page.evaluate("vx.ring('#d-identities', 8); vx.caption('7 identities · 7 flags · 1 hull<small>IMO 9240885, named on 10 sanctions and watch lists</small>')")


async def scene_score(page, rec, at):
    await page.evaluate("vx.caption(''); vx.ring(null)")
    await page.evaluate("vx.scrollRail(0, 2.4)")
    await rec.sleep(2.5)
    await page.evaluate("vx.ring('.score', 10)")
    await at("The evidence matrix")
    await page.evaluate("vx.scrollRail('#matrix-title', 2.0)")
    await rec.sleep(2.1)
    await page.evaluate("vx.ring('#d-matrix', 6); vx.caption('Every row: the evidence, its source, its status, its points')")
    for phrase, n in (("Forty points", 1), ("thirty for", 2), ("five for", 3)):
        await at(phrase)
        await page.evaluate(f"vx.ring('#d-matrix tbody tr:nth-child({n})', 5)")
    await at("The map shows")
    await page.evaluate("vx.caption(''); vx.ring(null); map.flyTo([25.2, 56.9], 7, {duration: 3.2})")
    await at("up to two weeks")
    await page.evaluate("vx.caption('Idled offshore for up to 14 days at a time<small>Loitering events, summer 2026 (open circles)</small>')")


async def scene_radar(page, rec, at):
    await page.evaluate("vx.caption(''); vx.ring(null)")
    await page.evaluate("vx.scrollRail('#d-matrix tr.row-radar', 2.4)")
    await rec.sleep(2.5)
    await at("two hundred and fifty-five")
    await page.evaluate("vx.ring('#d-matrix tr.row-radar', 5); vx.caption('255 of 300 tankers seen by satellite radar<small>Sentinel-1 detections matched to AIS by Global Fishing Watch · 8 for the Wolf</small>')")
    await at("We trained our own detector")
    await page.evaluate("vx.ring('#d-matrix tr.row-our_match', 5)")
    await at("On a hundred and forty-seven")
    await page.evaluate("vx.caption('Our detector, 147 unseen radar scenes: 97% of GFW’s ships found<small>False alarms 16 vs 46 for classic CFAR · agreement with GFW, not ground truth</small>')")
    await at("Here it is")
    await page.evaluate("vx.scrollRail('#d-matrix .ev-figure', 1.6)")
    await rec.sleep(1.7)
    await page.evaluate("vx.ring('#d-matrix .ev-figure img', 4); map.flyTo([25.7995, 56.8934], 8, {duration: 2.4})")
    await page.evaluate("vx.caption('The Wolf, 4 March 2026, 14:16 UTC<small>Radar target 255 m from its AIS loitering position · match probability 0.85</small>')")


async def scene_replay(page, rec, at):
    await page.evaluate("vx.caption(''); vx.ring(null); map.flyTo([33, 50], 3.4, {duration: 3})")
    await page.evaluate("document.getElementById('vx-cap').style.bottom = '300px'")   # clear the replay strip
    await page.evaluate("vx.cursorToEl('#replay-open', 0.5, 0.5)")
    await at("go back in time")
    await page.evaluate("vx.press()")
    await page.click("#replay-open")
    await rec.sleep(0.8)
    await page.evaluate("vx.ring('#replay', 4); vx.cursorToEl('#replay-play', 0.5, 0.5)")
    await at("month by month")
    await page.evaluate("vx.press()")
    await page.click("#replay-play")
    await page.evaluate("vx.hideCursor(); vx.ring(null)")
    await at("exactly as they were recorded")
    await page.evaluate("vx.caption('Port calls · loitering · radar sightings, month by month')")
    await at("never draws a route")
    await page.evaluate("vx.ring('.replay-note', 6); vx.caption('Recorded evidence only<small>No routes drawn, no gaps filled in</small>')")
    await at("What you see")
    await rec.sleep(2.2)
    await page.evaluate("vx.caption(''); vx.ring(null)")
    await page.click("#replay-exit")
    await page.evaluate("document.getElementById('vx-cap').style.bottom = ''")


async def scene_honesty(page, rec, at):
    await page.evaluate("vx.caption(''); vx.ring(null)")
    await page.evaluate("vx.scrollRail('#d-matrix tr.row-cargo', 2.4)")
    await rec.sleep(2.5)
    await at("whether these tankers are loaded")
    await page.evaluate("vx.ring('#d-matrix tr.row-cargo', 5)")
    await at("no better than a coin toss")
    await page.evaluate("vx.caption('Radar vs loaded-or-empty: AUC 0.47, a coin toss<small>202 images of 70 tankers · pre-registered test failed · cargo stays unknown</small>')")
    await at("Values are ranges")
    await page.evaluate("vx.caption(''); vx.scrollRail('#d-size', 2.2)")
    await rec.sleep(2.3)
    await page.evaluate("vx.ring('#d-size', 8)")
    await at("every vessel links")
    await page.evaluate("vx.scrollRail('#d-sources', 1.6)")
    await rec.sleep(1.7)
    await page.evaluate("vx.ring('#d-sources', 8); vx.caption('Straight to OpenSanctions and Global Fishing Watch')")


async def scene_fleet(page, rec, at):
    await page.evaluate("vx.caption(''); vx.ring(null); vx.scrollRail(0, 1.8)")
    await rec.sleep(1.9)
    await page.evaluate("vx.cursorToEl('#btn-back', 0.5, 0.5)")
    await rec.sleep(1.3)
    await page.evaluate("vx.press()")
    await page.click("#btn-back")
    await page.evaluate("vx.hideCursor(); map.flyTo([38, 62], 2.7, {duration: 6, easeLinearity: 0.1})")
    await at("Two hundred and eighty-nine")
    await page.evaluate("vx.caption('289 of 300 switched identity')")
    await at("eighty-one flags")
    await page.evaluate("vx.caption('81 flags between them · 11 landlocked today<small>Malawi 4 · Mali 3 · Zimbabwe 3 · Botswana 1</small>')")


NEEDS_DOSSIER = {"score", "radar", "replay", "honesty", "fleet"}
SITE_SCENES = {"landing": scene_landing, "trend": scene_trend, "ports": scene_ports, "search": scene_search,
               "identities": scene_identities, "score": scene_score, "radar": scene_radar, "replay": scene_replay,
               "honesty": scene_honesty, "fleet": scene_fleet}
CARD_CUES = {"title": ["A ship", "But it cannot"], "problem": ["shadow fleet", "rename", "flags of convenience", "radio identities", "is that hidden supply"],
             "close": ["all eight hundred", "licensed draft data", "Ghost Fleet.", "The hidden fleet"]}


async def record_card(browser, sid):
    page, cdp = await slow_page(browser)
    await page.goto((HERE / "cards.html").as_uri() + f"?card={sid}", wait_until="networkidle")
    await page.evaluate("document.fonts.ready")
    rec = Recorder(cdp)
    await rec.start()
    cues = {p: cue(sid, p) for p in CARD_CUES.get(sid, [])}
    await page.evaluate("([c, l]) => play(c, l)", [cues, lead(sid)])
    await rec.stop(sid, length(sid))
    await page.close()


async def record_site(browser, url, sids):
    """Site scenes run in one continuous session so state carries over (like a real demo)."""
    page, cdp = await slow_page(browser)
    await page.goto(url + "?v=video", wait_until="load")
    await page.wait_for_selector("#vessel-list button")
    await page.evaluate("document.fonts.ready")
    await page.wait_for_timeout(4000 * SLOW)             # let the basemap tiles settle
    await page.evaluate(OVERLAY_JS)
    if sids[0] in NEEDS_DOSSIER:       # resuming mid-story: open the Wolf as the earlier scenes left it
        await page.evaluate("openDossier('9240885')")
        await page.wait_for_timeout(5000 * SLOW)
    for sid in sids:
        rec = Recorder(cdp)
        await rec.start()
        lead_s = lead(sid)

        async def at(phrase, _sid=sid, _rec=rec, _lead=lead_s):
            await _rec.wait_until(_lead + cue(_sid, phrase))

        await SITE_SCENES[sid](page, rec, at)
        await rec.stop(sid, length(sid))
        cdp.remove_listener("Page.screencastFrame", rec._on_frame)
    await page.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    parser.add_argument("--url", default="https://ghost-fleet.vercel.app/")
    args = parser.parse_args()
    order = [s["id"] for s in SPEC["scenes"]]
    only = [s for s in args.only.split(",") if s] or order
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--force-device-scale-factor=1", "--hide-scrollbars"])
        for sid in [s for s in order if s in only and s not in SITE_SCENES]:
            await record_card(browser, sid)
        site = [s for s in order if s in only and s in SITE_SCENES]
        if site:
            await record_site(browser, args.url.rstrip("/") + "/", site)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
