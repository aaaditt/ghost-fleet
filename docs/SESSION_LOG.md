# Session Log

This file is append-only. The handover document contains the latest project
snapshot; this log records how the project reached that state.

## 2026-09-29 — Repository bootstrap (v0.1.0)

**Objective:** Make `aaaditt/ghost-fleet` the shared source of truth and prepare
the existing pipeline for repeatable collaborative sessions.

**Decisions:** Use `main` as the initial shared branch, semantic versions stored
in `VERSION`, an append-only session log, and a living handover. Keep API tokens,
downloaded maritime data, Python caches, and generated outputs outside Git.

**Changed:** Added the existing `dark_fleet_pipeline.py`, repository metadata,
dependency declarations, setup and usage documentation, collaboration rules,
the changelog, and this handover system.

**Validation:** Created an isolated Python 3.11.9 virtual environment, installed
`requirements.txt`, compiled `dark_fleet_pipeline.py`, ran focused assertions for
risk scoring and cargo value, and confirmed `pip check` reports no broken
requirements in the isolated environment. Scanned tracked files for GitHub token
patterns; no credentials were found. A live API run was not possible without the
operator-provided dataset and token.

**Remaining:** An end-to-end run still needs a local Global Fishing Watch token
and current OpenSanctions maritime export. See `docs/HANDOVER.md` for prioritized
follow-up work.

## 2026-09-29 — Open Datasets & Machine Learning Research (v0.1.1)

**Objective:** Research open-source datasets, machine learning models, training requirements, empirical benchmarks, and inference latency/resource load for Ghost Fleet.

**Decisions:** Document a 3-tier model framework (Tier 1: Tabular Cargo Classifier, Tier 2: Evasion GNN, Tier 3: SAR Space Radar YOLOv8). Select NOAA MarineCadastre and Danish Maritime Authority (DMA) AIS as primary open training corpora for the cargo classifier, and DIU/GFW xView3-SAR for satellite radar detection.

**Changed:** Added `docs/DATASETS_AND_ML_RESEARCH.md`, updated `docs/PLANNING.md`, `README.md`, `VERSION`, and `CHANGELOG.md`.

**Validation:** Verified dataset download portals, confirmed licensing status (public domain / open data), and documented quantitative latency and hardware resource footprints for CPU/GPU serving.

**Remaining:** Implement a trained Scikit-Learn / LightGBM cargo classifier model weights file from a sample NOAA/DMA dataset slice for v0.2.0.

## 2026-09-29 — Concept clarification and implementation pause (v0.1.2)

**Objective:** Explain Ghost Fleet from first principles in one readable Markdown
document and prevent exploratory prototypes from determining the product before
the project owner provides direction.

**Decisions:** Set the project status to concept definition. Treat existing code,
dashboards, model descriptions, and performance claims as exploratory material.
Require explicit product-owner direction before further prototype or feature
development.

**Changed:** Added `docs/CONCEPT_OVERVIEW.md`; updated `README.md`, `AGENTS.md`,
`docs/HANDOVER.md`, `CHANGELOG.md`, and `VERSION`.

**Validation:** Reviewed the concept, planning, judge-review, dataset research,
handover, session, README, and changelog documents. Checked the new Markdown for
structure, internal consistency, unsupported certainty, and formatting errors.

**Remaining:** Review the concept overview with the project owner and capture the
selected primary user, first decision, scope, evidence standard, freshness need,
and immediate project objective in an approved product brief.

## 2026-09-30 — Trader-focused hackathon build (v0.2.0, in progress)

**Objective:** Turn Ghost Fleet into a submittable hackathon project today. The
submission needs a demo video, a live link, a write-up, a demo script, and a
pitch deck.

**Decisions:** The owner chose commodity/energy traders as the first user and a
map-first tracker as the first experience, using real GFW + OpenSanctions data.
The defaults are recorded in `docs/PRODUCT_BRIEF.md`: oil tankers only, a
directional-signal evidence standard, and a historical snapshot.

**Phase 0 (done):** Added `docs/PRODUCT_BRIEF.md`. Lifted the concept-definition
guardrail in `AGENTS.md` and `README.md`. Marked `docs/PLANNING.md`,
`docs/IDEA_MAP.md`, and `docs/JUDGE_REVIEW.md` as historical. Rewrote
`docs/HANDOVER.md` with a phase tracker.

**Validation:** Documentation only. Reviewed the diff and checked for secrets.

**Phase 1a (code done, waiting for token):** Rewrote `dark_fleet_pipeline.py`
against the real GFW v3 schema, verified against the official
`gfw-api-python-client` 1.4.0 models, and the real OpenSanctions export
(2026-09-29, 23,453 rows).
- Found: GFW vessel records carry no draft, speed, or vessel type. Public
  encounter types cover fishing, carrier, support, and bunker vessels only, so
  tanker-to-tanker transfers are unlikely to appear.
- Found: the OpenSanctions export has one row per source entity, with an
  `IMO` prefix. Rows are now merged by IMO and filtered on the `mare.shadow`
  tag (892 vessels, 772 sanctioned).
- Changed: evidence now comes from AIS gaps, loitering, port visits, encounters,
  and identity history across all AIS identities. Capacity and value are
  ranges from tonnage or length. Cargo state is `UNKNOWN` without draft. This
  fixes a bug where zero evidence reported 50% confidence. Added a monthly
  trend and provenance, a response cache, CLI flags, and `tests/test_pipeline.py`
  (7 offline tests). The fictional data is saved as `vessels.demo.json`.
- Validation: `python -m pytest -q` passed 7/7, and the loader ran on the real
  CSV. There has been no live GFW call yet because the token is still pending.

**Phase 1b (real data run, done):** The owner set the GFW token. It was
validated with one call (HTTP 200). A 3-vessel smoke test exposed two
pipeline bugs, both fixed and covered by tests:
- GFW splits one ship's history across several search entries. Only the
  first entry was used, which dropped most identities and events. All entries
  carrying the IMO are now merged (for example, EAST 1 → 7 identities: TORM
  GERTRUD/DNK…EAST 1/HKG → LONGEVITY 7/PLW → WOLF/MWI → WOLF/ABW).
- Identity changes double-counted (flag + MMSI per re-flag, and spacing
  variants of a name). They now count chronological AIS identity switches with
  normalised names.
- Verified: GFW gap and encounter endpoints return HTTP 200 with total=0 for
  these tankers over 2023–2026. That is a coverage limit, not an error, so
  evidence rests on loitering, port visits, and identity history.
- Rescaled "meetings" (loitering) points to 1 per 4 events. The old scale
  saturated for nearly every vessel. The partial first month is now dropped
  from the trend.
- Snapshot (window 2025-09-30 → 2026-09-27, 120 most-listed shadow-fleet
  vessels): 120/120 matched, 112 located, 92 scored ≥70, 0 API errors.
  3-month active-vessel trend: −13.1% (Jun–Aug vs Mar–May, hand-checked).
- Validation: `python -m pytest -q` passed 8/8. Full live run, then an offline
  rebuild from cache.

**Phase 2 (dashboard, done):** Rebuilt `dashboard/` on the real snapshot with a
nautical-chart design (Esri Ocean basemap, chart magenta for risk 70+,
Newsreader/Public Sans). The monitor view shows the trend headline, 12-month
bars, key figures, busiest ports, and a searchable list (matching former names
too). The dossier view shows the score breakdown, the AIS identity sequence,
the last 12 dated events plotted on the map, and size and value ranges. It
honestly marks cargo state as unknown. The page has a disclaimer and source
credits, SRI on Leaflet, escaped data strings, and a `#imo=` deep link.
Bugs found in browser testing and fixed:
- Aggregates (trend, ports) were computed after trimming events to 60 per
  vessel, which undercounted early months. They are now computed from all
  events. The corrected headline is **−15.3%** (Jun–Aug 232 vs Mar–May 274,
  hand-checked).
- Missing CSV cells wrote `NaN`, which is invalid JSON and broke the page load.
  They now become `null`, and the writer uses `allow_nan=False`.
- Port names were dropped because the raw API key is `port_visit`, not the
  client model's `portVisit` alias. All 1,335 displayed calls are now named.
- Removed the straight lines between event points, which implied routes across
  land. Fixed money formatting for single vessels.
Validation: `python -m pytest -q` passed 9/9. Playwright at 1440×900 and
390×844: no console errors, no horizontal scroll. Deep link, search (including
a former name), empty state, open and back all work.

**Phase 3 (deploy, done):** At the owner's request, deployed `dashboard/` to
Vercel as project `ghost-fleet` (static, no build) at
https://ghost-fleet.vercel.app. `vercel link` wrote `dashboard/.env.local`
(an OIDC token). It is git-ignored, and a new `dashboard/.vercelignore` keeps it
and the fictional `vessels.demo.json` out of the upload.
Validation: anonymous HTTP checks returned 200 for `/` and `/data/signal.json`,
and 404 for `/.env.local` and `/data/vessels.demo.json`. Per-deployment URLs
redirect to Vercel login (deployment protection); the production alias is
public. Playwright on the live site: the deep link `#imo=9240885` renders all
7 identities, 138 markers and loaded tiles, with 0 console errors. Screenshots
are saved to `docs/screenshot-*.png`.

**Phase 4 (submission materials, done):** Added `docs/submission/WRITEUP.md`,
`DEMO_SCRIPT.md` (a timed 3-minute script with a video shot list, captions,
fallbacks and judge Q&A) and `PITCH.md`. Built a 10-slide deck as a claude.ai
Slides artifact (https://claude.ai/artifact/9SscVdcfFiNjFdTEaZLmeL, private
until the owner shares it) using the dashboard's visual identity and the real
screenshots. Every figure was recomputed from the snapshot: 115/120 switched
identity, median 4 switches, 63 flags, 6 landlocked flags, 49 Russian-flagged.
Checked the script's claims against the data. Corrected one caption from
6 flags to 7.

**Phase 5 (close-out):** Version 0.2.0. Updated `CHANGELOG.md` and the README
(submission links, version). Rewrote `docs/HANDOVER.md`.

**Remaining:** The owner records the demo video, fills in team names on the
deck, shares or exports the deck, and submits.

## 2026-09-30 — 300-vessel snapshot, plan-gap fixes, licence, showcase README (v0.3.0)

**Objective:** Expand the snapshot to 300 vessels and redeploy. Check the
dashboard against the approved plan and fix the gaps. Add an open-source
licence. Make the README a showcase.

**Process:** Brainstorming → spec
(`docs/superpowers/specs/2026-09-30-snapshot-300-readme-design.md`) → plan
(`docs/superpowers/plans/2026-09-30-snapshot-300-readme.md`) → inline
execution, with the owner approving each stage.

**Decisions:**
- MIT licence (owner: MIT or Apache fine).
- 300 most-listed shadow-fleet vessels, same window.
- 30 events per vessel, plus compact JSON (the trim alone left 2.10 MB).
- GIF by live recording (approach A). The planned quality tiers exceeded
  8 MB on the photographic basemap, so lower tiers were added. Final: 10 fps,
  800px, 128 colours.
- Worked on `main`, per AGENTS.md.

**Plan cross-check:** The map-first layout with a sidebar matched the plan.
Three Phase 2 items had been missed and are now built: the no-position tag,
the loaded/ballast/unknown figure (as "Cargo state known 0 of 300"), and the
GFW vessel link. The URL format was verified in a browser.

**Figures (from `scripts/figures.py`):** 300 screened / 300 matched / 276
located / 234 scored 70+. Trend −10.1% (595 vs 662, hand-checked). 289
switched identity (124 five or more times). 81 flags. 11 landlocked flags
(Malawi 4, Mali 3, Zimbabwe 3, Botswana 1). 115 Russian-flagged. Value
$64–145 bn a year upper bound.

**Changed:** `dark_fleet_pipeline.py`, `tests/test_snapshot.py`,
`dashboard/{index.html,app.js,style.css,data/*}`, `scripts/figures.py`,
`scripts/record_demo.py`, `docs/demo.gif`, `docs/screenshot-*.png`,
`docs/submission/*`, `LICENSE`, `README.md`, `CHANGELOG.md`, `VERSION`,
`docs/HANDOVER.md`. Deck slides answer, product and fleet were republished.

**Validation:**
- `python -m pytest -q` → 12 passed.
- Live anonymous HTTP checks: `/` and `/data/signal.json` 200;
  `.env.local` and `vessels.demo.json` 404; the live signal shows 300 and
  −10.1.
- Playwright on the live site: headline "fell 10%", "0 of 300", "276 of
  300", 7 identities and a GFW link for 9240885, 0 console errors, no
  horizontal scroll at 390px.
- Local browser: 24/24 no-position vessels tagged; a no-position dossier
  opens.
- GIF: 6.9 MB and 14.7 s, with frames inspected.
- The README's local links all resolve, and the stale-figure grep is clean.

**Remaining:** The owner records the demo video, adds team names on the
deck, and submits.

**Final review (fresh reviewer):** 0 critical, 1 important (Botswana missing
from the dashboard's landlocked and flag-name lists). Two minors were
re-graded to important: the pipeline's default of 120 vessels, and the
mislabelled "full months" port-call figure. All three were fixed test-first
(`tests/test_dashboard_consistency.py`, 4 new tests, suite 16/16),
redeployed, and verified live: OSTRIA reads "Now flagged to Botswana, a
landlocked country". Six minors were deferred (see the handover).

## 2026-09-30 — Narrated pitch video (v0.4.0)

**Objective:** Record a smooth, unhurried, professionally voiced pitch and demo
video, and publish it with the repo and docs updated.

**Decisions:**
- One combined 3-minute pitch and demo video. Voice: ElevenLabs "Eric"
  (American, "smooth, trustworthy") on `eleven_v4`, at speed 0.95.
- One clip per scene. Each scene's length is the lead-in + its narration +
  a tail, and on-screen actions are triggered by the narration's character
  timestamps.
- Built with HTML/CSS animation plus an ffmpeg crossfade assembly instead of
  Remotion (fewer dependencies, same visual result).
- The video is hosted on the live site (`/watch.html`) because GitHub serves
  raw MP4s as downloads.

**Problems found and fixed:**
- Chrome's screencast gives only ~15 fps at 1080p. Pages now run at 1/3
  speed (JS clocks, timers, animation frames, CSS via CDP), are captured in
  real time, and are re-timed: ~45–50 fps of video time.
- The slow-time patch was applied twice per window, which made timers 9×
  slower and stalled the first full run at the ports scene. Fixed with a
  once-per-window guard and animation timestamps from the slowed clock,
  confirmed by measurement.
- The sidebar scroll helper returned a promise, so each scroll waited for
  itself before the planned pause, and later beats drifted past the cut.
  Scrolls are now fire-and-forget; the affected scenes were re-recorded and
  the beats checked on frames.

**Validation:**
- Narration: 11 clips, 168.9 s; levels consistent (mean about −24 dB, no
  clipping).
- Final mix: −16.6 LUFS integrated, −1.5 dBFS peak. Video: 1920×1080,
  30 fps, H.264 + AAC, 188.7 s, 44.0 MB.
- Frames checked at every scene and at specific cues (Magenta, Nakhodka,
  East One, thirty for, every vessel links).
- The live watch page plays: seeking to the "One hull, seven identities"
  chapter lands at 1:33, and the active subtitle matches the narration.
  0 console errors.
- Media served with correct types and range support. `.env.local` → 404.
- `python -m pytest -q` → 20 passed.

**Remaining:** The owner adds team names to the deck, rotates the ElevenLabs
key, and submits.

## 2026-09-30 — SAR + ML feasibility research (v0.4.1)

**Objective:** Determine whether SAR imagery and ML can credibly add physical
vessel detection, ship-to-ship activity screening, and laden/ballast inference
to Ghost Fleet. Produce research documentation only; do not change application
code.

**Research process:** Three parallel web-research tracks reviewed SAR physics
and freeboard observability, current data/access/licensing, and defensible ML
validation. The review used official ESA/Copernicus, Global Fishing Watch,
USCG/IMO, ICEYE, and Capella documentation plus primary peer-reviewed work on
xView3, AIS–SAR matching, PolSAR freeboard retrieval, vessel dimensions, and
STS candidate detection.

**Decisions:**
- SAR vessel detection and probabilistic AIS association are feasible now.
- An unmatched SAR detection is an analyst lead, not proof that AIS was
  intentionally disabled and not an identity by itself.
- Side-by-side geometry can generate possible STS candidates, but a single
  image cannot confirm cargo transfer or illegality.
- Routine Sentinel-1 IW GRD (about 20 m x 22 m true resolution, 10 m pixel
  spacing) is not a validated way to measure tanker freeboard or classify load
  state. High-resolution/polarimetric imagery plus independent labels is a
  research path, not a current feature.
- The first pilot should use GFW's existing matched/unmatched SAR layer before
  training a detector. Cargo-state research starts only after independent
  ground truth is available.

**Changed:** Rewrote `docs/DATASETS_AND_ML_RESEARCH.md`; added
`docs/SAR_ML_FEASIBILITY.md` and `docs/SAR_ML_PILOT_PLAN.md`; linked them from
the README; updated changelog, version, handover, and session log. No
application, pipeline, dashboard, test, or data-snapshot code changed.

**Validation:** `git diff --check` passed (with only existing line-ending
normalization notices); a programmatic check found no missing local Markdown
targets; the README badge and `VERSION` both report 0.4.1; a grep found none of
the removed unsupported benchmark claims; `python -m pytest -q` → 20 passed.

**Remaining:** If the owner authorizes implementation after the hackathon, run
only Stage 1 of the pilot first: a bounded, historical GFW SAR
matched/unmatched study in one approved corridor.

## 2026-09-30 — Evidence matrix, historical evidence replay, UI polish (v0.5.0)

**Objective:** Make each vessel's evidence transparent, add a replay of the
dated events already in the snapshot, and polish the UI without changing the
nautical-chart identity, the static architecture or the data sources.

**Data inspected first:** the snapshot has 7,032 events: 4,119 loitering,
2,903 port calls and 10 AIS gaps. All are dated and positioned. There are no
encounter events (`encounters` is 0 for all 300 vessels). Every gap event
carries GFW's `intentionalDisabling: true`. The pipeline keeps each vessel's
30 most recent events, and 192 vessels hit that cap, so monthly event counts
rise over the year as an artefact of trimming. 24 vessels have no positioned
event. All 300 vessels have `cargo_status` UNKNOWN, and every `risk_score`
equals the sum of its breakdown.

**Decisions:**
- No pipeline or schema change was needed.
- The matrix copies points from `risk_breakdown` and never re-scores. Loitering
  and encounters share the `meetings` component, shown as one merged points
  cell.
- Replay observations are grouped by overlap: an event appears in every
  calendar month its recorded span overlaps, clipped to the snapshot window.
  This is honest for long loitering and port stays, and it handles events
  that began before the window. The tooltips and counts separate events that
  "began earlier". The window-edge months are marked partial.
- The replay does not use "live", does not draw lines, and does not
  interpolate. It has no activity chart, because the trimming artefact would
  read as a trend. The visible note says the counts are not a trend.
- The replay legend shows only the kinds present in the data, so there is no
  encounter symbol today. Encounters keep "apparent … (possible)" wording in
  code for future snapshots.
- Keyboard and mobile access to replay observations goes through the vessel
  list, which filters to the selected month, rather than hundreds of
  focusable map markers.

**Changed:** `dashboard/evidence.js` (new), `dashboard/app.js`,
`dashboard/index.html`, `dashboard/style.css`,
`tests/test_evidence_frontend.py` (new), `video/record_scenes.py` (selector),
`README.md`, `CHANGELOG.md`, `VERSION`, `docs/HANDOVER.md`, this log.

**Validation:**
- `python -m pytest -q` → 39 passed (20 existing + 19 new; the new tests run
  `evidence.js` in Node 24).
- A Playwright script against `python -m http.server` passed 136/136 checks
  in three configurations: desktop 1440×900, mobile 390×844, and reduced
  motion at 1280×800. The checks covered the latest-position map, search by
  former name, the dossier matrix (WOLF 40 + 30 + 5 = 75, cargo unknown,
  encounters not observed, two source links), dossier event click, Escape
  with focus return, and keyboard replay entry (slider focus, Arrow/Home
  keys). They also covered prev/next and their disabled ends, play advancing,
  pause holding, "Latest month", opening a dossier from the replay list and
  from a map marker, a forced empty month, exit restoring the fleet map, deep
  links, hashchange, a vessel without positioned events, the visible focus
  outline, animations disabled under reduced motion, no horizontal overflow,
  and zero console errors.
- Screenshots of desktop and 390 px views were reviewed by eye. That review
  found and fixed a grid-placement bug that put vessel names on the right.

**Remaining:** Deploy (`vercel deploy --prod --cwd dashboard`). README
screenshots, `docs/demo.gif` and the pitch video still show the pre-0.5.0
dossier.

## 2026-09-30 to 2026-10-01 — Satellite radar + ML, media refresh (v0.6.0)

**Objective:** The owner asked for the "not implemented" ML list to be
built: SAR ingestion, GFW SAR detections, a detector, AIS-to-SAR matching, STS
image detection and a laden/ballast model. After that, deploy v0.5.0, commit
the browser test, and remake the README, screenshots, GIF, pitch deck,
scripts and narrated video for the new product.

**Constraints found by probing:**
- Hardware: a 4 GB GTX 1650 GPU, about 11 GB free disk and 16 GB RAM (the
  background jobs were twice stopped for low memory).
- GFW's 4Wings report API allows one concurrent report per token and cannot
  filter by `vessel_id`, so corridors are queried and filtered by IMO.
- Planetary Computer's `sentinel-1-rtc` allows anonymous windowed COG reads,
  about 1.7 s per 2 km chip.
- xView3/SARFish labels require DIU registration.
- No free draught data exists.

**Decisions:**
- Corridors are the 24 one-degree cells holding the most snapshot events.
- Detector labels are GFW detections, and every detector metric is reported
  as agreement with GFW, not ground truth. The split is by scene.
- The matcher never sees GFW's detections. GFW's own AIS match is the
  reference.
- STS candidates come from full-resolution component geometry (the CNN
  heatmap cannot resolve alongside pairs). All candidates go to visual
  review, and only reviewed pairs are shown.
- The cargo study uses voyage-context weak labels, and its gate was fixed
  before results (lower CI bound of AUC ≥ 0.65, ≥ 60 observations, ≥ 20
  vessels).
- Model outputs get a new *Model estimate* status and never add points to
  the screening score.

**Results:**
- 127,265 GFW detections; 255 of 300 tankers radar-detected.
- CNN test PR-AUC 0.991 (CI 0.986–0.995) against CFAR 0.964 on 147 held-out
  scenes. Recall on unmatched targets is 95.2% against 87.2%.
- A first model was trained on a dataset whose positive budget our own
  vessels had consumed, leaving only 9 unmatched test positives. That was
  caught, the dataset rebalanced to 1,308 unmatched positives, and the model
  retrained.
- Visual review of all 37 test disagreements: 4 "false alarms" show real
  unreported vessels, and 19 of 21 misses show no vessel in the chip
  (likely a same-day second pass).
- The matcher agrees with GFW 87% of the time, with agreement rising across
  probability bands (69%, 90%, 100%).
- Side-by-side: 338 candidates, 90 reviewed, 5 possible pairs. Rule
  precision is 3/30 and 2/60.
- Cargo study: 202 observations of 70 tankers, AUC 0.47 and 0.44. The gate
  failed, so cargo stays UNKNOWN.

**Media:**
- Narration regenerated for score, radar, replay and honesty (1,526
  characters; the other scenes were cached). The *score* line linking
  loitering to STS was dropped.
- Video: 4 min 8 s, 13 chapters, −16.6 LUFS, 45.9 MB at CRF 25.
- The recorder now streams frames to disk. Resumed runs open WOLF's dossier
  first.
- The video exposed a real layout bug: the page was 2,580 px tall in a
  1,080 px window. The caption overlay intercepting clicks made Playwright
  scroll the page. Both are fixed, and the browser check now asserts no
  vertical page overflow.
- Also refreshed: four README screenshots (`scripts/screenshots.py`), the
  GIF (7.8 MB), the write-up, pitch and demo script, and the pitch deck
  (version 6: new radar and models slides, four revised).

**Changed:**
- New: `ml/*`, `requirements-ml.txt`, `dashboard/data/sar.json`,
  `dashboard/media/sar/*.jpg` (118), `dashboard/models.html`,
  `dashboard/models.js`, `scripts/screenshots.py`,
  `tests/test_sar_evidence.py`, `docs/screenshot-radar.png`,
  `docs/screenshot-replay.png`.
- Modified: dashboard JS/CSS/HTML, `tests/browser_check.py`, video scripts
  and media, `scripts/figures.py`, `scripts/record_demo.py`, README,
  CHANGELOG, VERSION, the product brief (amendment), the pilot plan
  (status), submission docs, the handover and this log.

**Validation:**
- `python -m pytest -q` → 53 passed.
- `python tests/browser_check.py` → 159/159 locally. The live site passed
  157/157 before the overflow check was added; the final result is below.
- Frames were checked at every new narration cue, and the replay and radar
  scenes were re-recorded after fixes.
- Loudness was measured with ffmpeg ebur128.

**Remaining:**
- Obtain xView3 labels for an independent detector test.
- Widen radar coverage beyond 24 corridors.
- Parts of the Russian Pacific coast are rarely imaged by Sentinel-1.

## 2026-10-01 — v0.7.0: satellite globe, radar lens, tour

**Asked:** a more immersive live demo: real satellite imagery, the Sentinel-1
images shown on the map rather than single screenshots, and a better map.
Team names on the deck cover.

**Built:**
- `ml/build.py` writes 472 georeferenced radar passes (corners from each
  cached chip's UTM transform, target snapped to the brightest pixel) and
  `radar_passes.json`; no new downloads.
- Dashboard moved from Leaflet to MapLibre GL 5.24 on a globe with Esri
  imagery; night theme in `map.css`; radar lens, time-lapse and gallery in
  `radar.js`; guided tour in `tour.js`.
- Found and fixed while testing: `map.setPadding()` jumps the camera and
  cancelled flights, so padding now rides on each camera move; the tour
  crashed scheduling before its first step; requests cut off by navigation
  were logged as errors.
- Deck cover (version 7) names Aadit Chandra & Abhishekh Verma.
- Deployed to https://ghost-fleet.vercel.app; the browser check passed
  237/237 against the live site.

**Validation:**
- `python -m pytest -q` → 55 passed.
- `python tests/browser_check.py` → 237/237 on the runs after the last fix.
  Earlier runs intermittently logged aborted fetches as console errors;
  that was the navigation noise fixed above.
- Every tour step, the lens, gallery and mobile layout were checked in
  screenshots.

**Remaining:**
- Port the video scene scripts to MapLibre before re-recording the video.
- xView3 labels (owner); radar beyond 24 corridors.

## 2026-10-01 — v0.7.1: video, deck and docs for the globe

**Asked:** regenerate the README, pitch deck, video and everything else so it
matches the dark globe.

**Done:**
- Video re-recorded on the globe: 14 scenes (new *Every radar pass*), four
  narration clips re-voiced (landing, radar, passes, close), dark cards with
  the team names. 4 min 45 s, 45.6 MB at CRF 26, −16.6 LUFS.
- Recorder ported to MapLibre; GPU WebGL via ANGLE/D3D11 (about 28 fps at
  1080p against SwiftShader's crawl); tile-cache warm-up after the first run
  showed unloaded imagery in the ports and score flights.
- The first full recording was stopped by the host for low memory (0.6 GB
  free) after 12 of 14 scenes; the rest were recorded in short runs after the
  owner freed memory.
- Deck version 8 in the night theme; models and watch pages dark; write-up,
  demo script, pitch notes and README updated.

**Validation:** see the release commit (pytest, browser check locally and
live).
