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
