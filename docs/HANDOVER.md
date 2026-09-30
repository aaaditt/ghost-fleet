# Project Handover

- Updated: 2026-09-30
- Version: 0.4.1
- Shared branch: `main`
- Licence: MIT (code). Data retains source-specific terms; OpenSanctions and
  Global Fishing Watch are non-commercial for this build.

## Current state

Ghost Fleet is a **map-first hidden-supply monitor for commodity and energy
traders** (see `docs/PRODUCT_BRIEF.md`). The hackathon application remains
unchanged in v0.4.1; this session added post-hackathon SAR/ML research only.

- **Live:** https://ghost-fleet.vercel.app. The demo vessel is
  `#imo=9240885` (EAST 1 → WOLF, 7 identities, score 75).
- **Snapshot:** 300 most-listed shadow-fleet vessels for 30 Sep 2025 –
  27 Sep 2026; 276 have a recent position. The headline is active vessels down
  10.1% (595 vs 662 vessel-months, Jun–Aug versus Mar–May).
- **Pipeline:** `dark_fleet_pipeline.py` uses OpenSanctions and Global Fishing
  Watch v3. Cargo state remains `UNKNOWN` because the current source records do
  not include usable draught evidence.
- **Dashboard:** static map-first site with fleet trend, ports, vessel search,
  identity histories, activity evidence, score explanations, and source links.
- **Pitch video:** https://ghost-fleet.vercel.app/watch.html, 3 min 9 s,
  1080p30 with subtitles and chapters.
- **Validation baseline:** 20 offline tests were passing before and after this
  documentation-only session.

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

1. Owner: add team names to the deck and complete the hackathon submission. If
   the form needs YouTube or Loom, upload
   `dashboard/media/ghost-fleet-demo.mp4`.
2. Owner: rotate the ElevenLabs API key that was previously pasted into chat.
   It is stored as a Windows user environment variable and is in no file.
3. If the owner authorizes post-hackathon SAR implementation, run only Stage 1
   first: one bounded historical corridor using GFW's matched/unmatched SAR
   detections. Do not start cargo-state model training yet.
4. Other post-hackathon work remains: screen all 892 listed vessels, validate
   the trend against published export estimates, and investigate commercial
   data licences.

## Setup

- Python 3.10+, then `python -m pip install -r requirements.txt`.
- `GFW_API_TOKEN` in the environment; keep it out of client code and Git.
- `maritime.csv` in the repo root from OpenSanctions.
- Offline rebuild:
  `python dark_fleet_pipeline.py --max 300 --offline --start 2025-09-30 --end 2026-09-27`.
- Tests: `python -m pytest -q`.
- Local dashboard: `cd dashboard; python -m http.server 8765`.
- Deploy: `vercel deploy --prod --cwd dashboard`; local Vercel configuration is
  git-ignored.
- GIF/video work additionally needs Playwright/Chromium and ffmpeg. Voice
  generation needs `ELEVENLABS_API_KEY` and the existing attribution.
- A future SAR pilot will need a Copernicus Data Space account/token and should
  keep raw imagery, tiles, model weights, caches, and credentials outside Git.

## Known risks

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
