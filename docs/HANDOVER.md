# Project Handover

- Updated: 2026-10-01
- Version: 0.7.0
- Shared branch: `main`
- Licence: MIT (code). Data retains source-specific terms; OpenSanctions and
  Global Fishing Watch are non-commercial. Sentinel-1 is Copernicus data via
  Microsoft Planetary Computer.

## Current state

Ghost Fleet is a **map-first hidden-supply monitor for commodity and energy
traders** (`docs/PRODUCT_BRIEF.md`). v0.6.0 added satellite radar and ML,
built at the owner's explicit request of 2026-09-30, which is recorded as an
amendment in the brief. v0.7.0 (owner's request of 2026-10-01) makes the
demo immersive: a satellite globe, radar images draped on the map, per-ship
radar time-lapse, a fleet radar gallery and a guided tour.

- **Live:** https://ghost-fleet.vercel.app. Deployed and verified with
  `python tests/browser_check.py --url https://ghost-fleet.vercel.app/`.
  - Demo vessel: `#imo=9240885` (EAST 1 → WOLF, 7 identities, score 75,
    8 radar detections, 7 radar passes). `#imo=9240885&pass=2` opens its
    radar lens.
  - Live demo: `/?tour=1` runs the guided tour.
  - Models page: `/models.html`. Pitch video: `/watch.html`, 4 min 8 s with
    13 chapters.
- **Snapshot:** 300 most-listed shadow-fleet vessels, 30 Sep 2025 –
  27 Sep 2026. 276 have a position. Activity is down 10.1% (Jun–Aug vs
  Mar–May). Cargo state is UNKNOWN for all.
- **Dashboard:** static vanilla JS and MapLibre GL 5.24 (globe, Esri
  World Imagery). `app.js` map/dossier/replay, `radar.js` lens, time-lapse
  and gallery, `tour.js` guided tour, `map.css` the night theme over
  `style.css`.
  - The evidence matrix has statuses Observed, Derived from AIS, Not
    observed, Unavailable / unknown, and Model estimate.
  - Radar rows and thumbnails come from `data/sar.json`; draped radar
    passes from `data/radar_passes.json` (472 passes, 133 ships).
  - The historical evidence replay includes radar detections.
  - The logic is DOM-free in `evidence.js`, shared with the tests.
- **Radar + ML (`ml/`):**

  | Stage | Module | Result | Reference |
  |---|---|---|---|
  | GFW SAR detections | `gfw_sar` | 127,265 rows in 24 corridors; 255/300 tankers detected | observed (GFW) |
  | Sentinel-1 chips | `s1`, `dataset` | 7,948 chips, split by scene | — |
  | Detector | `cfar`, `detector` | CNN PR-AUC 0.991 (CI 0.986–0.995) vs CFAR 0.964; unmatched recall 95.2% vs 87.2% | agreement with GFW |
  | Matching | `matching` | 87% agreement; agreement rises with posterior | GFW's own AIS match |
  | Side-by-side | `sts` | 5 possible pairs from 90 reviewed; rule precision 3/30 and 2/60 | review by Claude, not an expert |
  | Cargo state | `cargo` | AUC 0.47 on unseen tankers; gate failed; cargo stays UNKNOWN | voyage-context weak labels |
  | Independent test | `xview3` | Not run: labels need DIU registration | xView3 labels |

- **Validation baseline:**
  - `python -m pytest -q` → 55 passed.
  - Browser check → 237/237 locally, on desktop, 390 px mobile and reduced
    motion (Chromium with SwiftShader WebGL).

## Immediate next tasks

1. Owner: submit. The deck cover now names the team
   (https://claude.ai/artifact/9SscVdcfFiNjFdTEaZLmeL, version 7). If a form
   needs YouTube or Loom, upload `dashboard/media/ghost-fleet-demo.mp4`.
2. Port `video/record_scenes.py` to the MapLibre API (`flyTo({center,
   zoom})`, no `setView`/`flyToBounds`) before re-recording the pitch video,
   which still shows the v0.6 map.
3. Register with DIU for xView3-SAR labels, then run `python -m ml.xview3
   <labels.csv>` for an evaluation not built on GFW's own outputs.
4. Widen radar beyond the 24 corridors, and screen all 892 listed vessels.
5. For cargo state, licensed AIS draught or high-resolution/polarimetric SAR
   with independent labels is needed. Free Sentinel-1 failed the
   pre-registered test.

## Setup

- Pipeline and dashboard: Python 3.10+, `python -m pip install -r
  requirements.txt`, `GFW_API_TOKEN`, `maritime.csv` from OpenSanctions.
- ML: `python -m pip install -r requirements-ml.txt` plus PyTorch
  (cu121 was used on a 4 GB GTX 1650). Then run, in order:
  `ml.gfw_sar` → `ml.dataset` → `ml.detector train|eval` → `ml.matching` →
  `ml.sts queue` (fill `review.csv`) → `ml.sts summary` → `ml.cargo` →
  `ml.build`.
  - Caches, chips and weights are in `.cache/ml/` (git-ignored; about 1 GB).
  - GFW reports run one at a time, so the full fetch takes about an hour.
- Tests: `python -m pytest -q`. The frontend tests need Node.js.
  `tests/browser_check.py` needs Playwright and a local server
  (`cd dashboard; python -m http.server 8765`).
- Media, against the live site by default (`--url http://localhost:8765`
  for a local build):
  - `python scripts/screenshots.py`
  - `python scripts/record_demo.py`
  - `python video/make_voice.py` (needs `ELEVENLABS_API_KEY`; cached per
    scene)
  - `python video/record_scenes.py`. It can resume with `--only`, and
    mid-story runs open WOLF's dossier first.
  - `python video/assemble.py --crf 25`, which keeps the MP4 under 50 MB.
- Deploy: `vercel deploy --prod --cwd dashboard`.

## Known risks

- Detector and matcher metrics measure agreement with GFW, whose labels
  have their own errors: near-shore exclusions and possibly a different
  same-day pass. They are not accuracy against ground truth.
- The detector was trained on GFW detections from these corridors and dates.
  Performance elsewhere (other sea states, the near shore, small craft) is
  untested.
- Radar coverage is uneven. Parts of the Russian Pacific coast (Nakhodka
  corridors) have few or no Sentinel-1 scenes.
- Side-by-side labels come from an AI reviewer at 10 m pixels (about 20 m
  true resolution). They are "possible side-by-side activity", never
  transfers.
- An unmatched radar target is not a vessel with AIS switched off. It can be
  a small craft, infrastructure or a false detection.
- Replay counts rise over the year partly because each vessel keeps only
  its 30 most recent events. The UI says the counts are not a trend.
- The machine running this work had low memory. Long background jobs were
  stopped twice. The recorder now streams frames to disk.
- A listing, score, detection or match is not proof of wrongdoing or trading
  advice.
- The basemap is Esri World Imagery under its attribution terms; heavy
  public use may need an ArcGIS account. Radar passes are 11 MB of static
  JPEGs, loaded only when viewed.
- `dashboard/.env.local` holds a Vercel OIDC token. It is git-ignored and
  excluded from deployments.
