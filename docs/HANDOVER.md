# Project Handover

- Updated: 2026-09-30
- Version: 0.5.0
- Shared branch: `main`
- Licence: MIT (code). Data retains source-specific terms; OpenSanctions and
  Global Fishing Watch are non-commercial for this build.

## Current state

Ghost Fleet is a **map-first hidden-supply monitor for commodity and energy
traders** (see `docs/PRODUCT_BRIEF.md`). v0.5.0 added an evidence matrix and a
historical evidence replay to the dashboard. The pipeline and snapshot schema
are unchanged.

- **Live:** https://ghost-fleet.vercel.app. The demo vessel is
  `#imo=9240885` (EAST 1 → WOLF, 7 identities, score 75). **The live site
  still serves v0.4.x until someone runs `vercel deploy --prod --cwd
  dashboard`.**
- **Snapshot:** 300 most-listed shadow-fleet vessels for 30 Sep 2025 –
  27 Sep 2026; 276 have a recent position. The headline is active vessels down
  10.1% (595 vs 662 vessel-months, Jun–Aug versus Mar–May).
- **Pipeline:** `dark_fleet_pipeline.py` uses OpenSanctions and Global Fishing
  Watch v3. Cargo state remains `UNKNOWN` because the current source records do
  not include usable draught evidence.
- **Dashboard:** static site with vanilla JS and Leaflet. It shows the fleet
  trend, ports, vessel search, identity histories and source links, plus:
  - **Evidence matrix** (dossier). One row per evidence type, each with a
    status (Observed / Derived from AIS / Not observed / Unavailable /
    unknown), the source, the scoring rule, and points copied from
    `risk_breakdown`.
  - **Historical evidence replay** (map). A monthly slider over the window.
    Each mark is one dated, positioned snapshot event, shown in every month
    its span overlaps. It draws no routes and does no interpolation.
  - The logic lives in `dashboard/evidence.js`, DOM-free and shared with the
    Node-backed tests.
- **Pitch video:** https://ghost-fleet.vercel.app/watch.html, 3 min 9 s,
  1080p30 with subtitles and chapters. It shows the pre-0.5.0 dossier.
- **Validation baseline:** 39 offline tests pass. The browser behaviour was
  checked with a 136-point Playwright script (desktop, 390 px mobile, reduced
  motion). That script is not in the repo.

## SAR + ML research conclusion

The new research is split across:

- `docs/SAR_ML_FEASIBILITY.md` — capability assessment and evidence;
- `docs/SAR_ML_PILOT_PLAN.md` — staged experiments and go/no-go gates;
- `docs/DATASETS_AND_ML_RESEARCH.md` — verified data, access, terms, labels,
  resolution, and ground-truth constraints.

Main decisions:

1. SAR vessel detection and probabilistic AIS association are feasible today.
2. A GFW matched/unmatched SAR study is the best first prototype and needs no
   new model training.
3. Side-by-side vessel geometry is useful for possible STS candidates, but
   does not confirm cargo transfer or wrongdoing.
4. Routine Sentinel-1 IW GRD is about 20 m x 22 m resolution, despite 10 m
   pixel spacing. It is not a validated sensor for metre-scale tanker
   freeboard or laden/ballast classification.
5. Cargo-state research needs high-resolution and/or suitable polarimetric SAR,
   repeated observations, vessel-specific context, independent load/draught
   labels, held-out-vessel evaluation, calibrated confidence, and `UNKNOWN`.
6. Earlier uncited accuracy, latency, compute, and GNN claims were removed.

These findings do not change the approved brief's non-goal: the current
hackathon build has no trained SAR/computer-vision model.

## Immediate next work

1. Deploy v0.5.0: `vercel deploy --prod --cwd dashboard`, then spot-check
   `#imo=9240885` and the replay on the live URL.
2. Optional: refresh `docs/screenshot-dossier.png`,
   `docs/screenshot-overview.png` and `docs/demo.gif`
   (`python scripts/record_demo.py`) so they show the matrix and replay
   button. If the video is re-recorded, `video/record_scenes.py` already
   targets the new matrix rows.
3. Owner: add team names to the deck and complete the hackathon submission. If
   the form needs YouTube or Loom, upload
   `dashboard/media/ghost-fleet-demo.mp4`.
4. Owner: rotate the ElevenLabs API key that was previously pasted into chat.
   It is stored as a Windows user environment variable and is in no file.
5. If the owner authorizes post-hackathon SAR implementation, run only Stage 1
   first: one bounded historical corridor using GFW's matched/unmatched SAR
   detections. Do not start cargo-state model training yet.
6. Other post-hackathon work remains: screen all 892 listed vessels, validate
   the trend against published export estimates, and investigate commercial
   data licences.

## Setup

- Python 3.10+, then `python -m pip install -r requirements.txt`.
- `GFW_API_TOKEN` in the environment; keep it out of client code and Git.
- `maritime.csv` in the repo root from OpenSanctions.
- Offline rebuild:
  `python dark_fleet_pipeline.py --max 300 --offline --start 2025-09-30 --end 2026-09-27`.
- Tests: `python -m pytest -q`. The frontend tests need Node.js on PATH and
  skip cleanly without it.
- Local dashboard: `cd dashboard; python -m http.server 8765`.
- Deploy: `vercel deploy --prod --cwd dashboard`; local Vercel configuration is
  git-ignored.
- GIF/video work additionally needs Playwright/Chromium and ffmpeg. Voice
  generation needs `ELEVENLABS_API_KEY` and the existing attribution.
- A future SAR pilot will need a Copernicus Data Space account/token and should
  keep raw imagery, tiles, model weights, caches, and credentials outside Git.

## Known risks

- Replay counts rise over the year partly because each vessel keeps only its
  30 most recent events (192 of 300 hit the cap). The UI says the counts are
  not a trend. Keep that note if the replay is changed, or raise
  `EVENTS_PER_VESSEL` knowing it grows the snapshot (the phone-size test
  allows up to 1.8 MB).
- The snapshot has no encounter events. The matrix shows encounters as "Not
  observed", which does not mean none occurred.
- AIS-gap intent wording depends on GFW's `intentionalDisabling` field. It is
  a model label, shown as "possible".

- GFW has little tanker encounter/AIS-gap activity in the current snapshot and
  no usable draught. Current cargo state is correctly unknown.
- An unmatched SAR detection is not a known vessel identity and not evidence of
  intentional AIS disabling.
- An AIS encounter or two side-by-side SAR targets do not prove that cargo was
  transferred.
- Sentinel-1 nominal revisit is not continuous monitoring or guaranteed
  coverage of every area at the desired time/mode.
- AIS draught is manually entered and cannot serve as unquestioned ground
  truth. Using it as both model input and test label would be circular.
- xView3 is useful for object detection/length research, not tanker cargo-state
  labels; its geography and fishing orientation create domain shift.
- GFW API use is non-commercial. Commercial SAR has contract-specific tasking,
  derived-data, model-training, and redistribution rights and no assumed public
  price.
- The activity trend counts active listed vessels, not barrels; value figures
  are capacity upper bounds.
- The snapshot covers 300 of 892 vessels and ranks by listing count.
- A listing, score, detection, match, or estimate is not proof of wrongdoing or
  trading advice.
- `dashboard/.env.local` contains a Vercel OIDC token. It is git-ignored and
  excluded from deployments.
