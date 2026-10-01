# Changelog

All notable changes to Ghost Fleet are recorded here. Versions follow semantic
versioning.

## [0.7.1] - 2026-10-01

### Changed

- **Pitch video re-recorded on the globe** (4 min 45 s, 14 chapters,
  45.6 MB, −16.6 LUFS). A new *Every radar pass* scene shows the time-lapse
  and the radar gallery; the radar scene ends in the lens with a blink; the
  landing descends onto the globe; the close points to the guided tour.
  Narration re-voiced for four scenes. Cards, captions and cursor use the
  night theme, and the title and close cards name the team.
- `video/record_scenes.py` drives MapLibre (`vx.fly`), records with the GPU
  through ANGLE/D3D11, and warms the tile cache at every camera target first.
- Pitch deck (version 8) re-themed to the night palette, with the globe and
  the radar lens as its two images and current test counts.
- `models.html` and `watch.html` use the night theme; image credits name
  Esri World Imagery and Sentinel-1.
- `WRITEUP.md`, `DEMO_SCRIPT.md` and `PITCH.md` describe the globe, lens,
  time-lapse, gallery and tour; `scripts/figures.py` prints the radar-pass
  totals.

## [0.7.0] - 2026-10-01

### Added

- **Satellite globe.** The map moves from Leaflet to MapLibre GL 5.24 on a
  globe projection, with Esri World Imagery and labels (a dark basemap is a
  toggle). Vessels, events and the 24 radar corridors are GeoJSON layers;
  event symbols are drawn once on a canvas so they match the legend.
- **Radar lens.** Sentinel-1 images draped on the map at their true position
  from each chip's UTM transform, with the matched target ringed (model
  estimate), the AIS loitering position marked, an optical/radar opacity
  slider and a blink. Deep link `#imo=<imo>&pass=<n>`.
- **Radar time-lapse** through every pass matched to one ship, and a **radar
  gallery** of all 472 passes for 133 ships, filterable to confident matches
  or GFW agreement.
- **Guided tour** (`?tour=1` or the masthead button): ten captioned steps for
  live demos, ending on the team names. Space pauses, arrows step, Esc exits;
  grabbing the map pauses it; reduced motion cuts instead of flying.
- `dashboard/data/radar_passes.json` (195 KB) and 472 georeferenced pass
  images (`dashboard/media/sar/passes/`, 11 MB), written by `ml/build.py`
  from the cached chips with no new downloads. `sar.json` `our_match` gains
  `pass`.
- Two radar-pass tests (55 in total) and 78 new browser checks for the globe,
  lens, gallery and tour (237 in total).

### Changed

- The map page is a night edition of the Admiralty chart (`map.css`): a
  full-bleed globe with the rail and panels as floating glass. Other pages
  keep the light theme.
- README screenshots (two new: lens and gallery) and `docs/demo.gif`
  re-recorded against the new map; the deck cover carries the team names.

### Known gaps

- The pitch video and `video/record_scenes.py` still show and drive the
  v0.6 Leaflet map; the scene scripts need porting before re-recording.

## [0.6.0] - 2026-10-01

### Added

- **Satellite radar and ML** (`ml/`, `requirements-ml.txt`), built at the
  owner's explicit request:
  - Global Fishing Watch Sentinel-1 radar detections for the 24 one-degree
    corridors holding the most snapshot events: 127,265 detections, with 255
    of the 300 tankers matched by IMO.
  - Sentinel-1 RTC chips read remotely from Microsoft Planetary Computer.
  - A CA-CFAR baseline and a small CNN detector, evaluated on held-out
    scenes. CNN PR-AUC 0.991 against 0.964 for CFAR, with 95.2% recall on
    unmatched targets. These measure agreement with GFW, not ground truth.
    Every test disagreement was reviewed visually.
  - Event-to-radar matching with posteriors: the top target agrees with
    GFW's own match 87% of the time, and agreement rises across the
    probability bands.
  - A side-by-side candidate review queue: 5 possible pairs confirmed of 90
    reviewed, with the precision of each rule reported.
  - A pre-registered laden/ballast study. AUC 0.47 on unseen tankers, so it
    failed the gate and cargo stays UNKNOWN.
  - An xView3/SARFish evaluation adapter, for when the labels are licensed.
- `dashboard/data/sar.json` (151 KB) and 118 radar thumbnails
  (`dashboard/media/sar/`).
- Evidence matrix rows for radar detections, our radar image match (with its
  image), unmatched radar targets nearby, and possible side-by-side
  activity. A new status, *Model estimate*, applies to model outputs, which
  never add points to the score.
- Radar detections in the Historical evidence replay.
- A Models page (`models.html`) that renders every metric, reference, review
  and gate decision from `sar.json`.
- `tests/browser_check.py`, a committed 157-check Playwright run, plus 14
  radar consistency and wording tests (53 in total).
- A refreshed pitch video (about 4 min) with new *radar* and *replay*
  scenes and rewritten *score* and *honesty* narration. Also refreshed:
  README screenshots, GIF, write-up, demo script and a 12-slide pitch deck.

### Changed

- The product brief records the owner's 2026-09-30 amendment. The pilot
  plan notes which stages are implemented.
- The pitch narration no longer links loitering to ship-to-ship transfers.

### Fixed

- The desktop page was about 1,500 px taller than the window. Visually hidden
  link text escaped the rail's scroll area, so the page could scroll into an
  empty band. The rail now contains it, and a browser check guards against a
  regression.

## [0.5.0] - 2026-09-30

### Added

- **Evidence matrix** in the vessel dossier, which replaces the plain score
  list. Each row covers one kind of evidence: listing, identity/flag changes,
  offshore loitering, encounters, AIS gaps, port calls, latest observation
  and cargo state. Rows show a status (*Observed*, *Derived from AIS*, *Not
  observed*, *Unavailable / unknown*), the source, the scoring rule, and the
  points copied from the existing score breakdown. A status key explains the
  four labels. The OpenSanctions source list can be expanded in place.
- **Historical evidence replay** on the map. A monthly timeline covers the
  snapshot window, with play/pause, previous/next, a keyboard-operable
  slider, "Latest month" and "Back to latest positions". Each mark is one
  dated, positioned snapshot event. It is shown in every month its recorded
  span overlaps, and it links to that vessel's dossier. The vessel list
  filters to the selected month. A visible note says the replay is sparse
  recorded evidence, not a continuous track, and that the counts are not a
  trend.
- `dashboard/evidence.js`: DOM-free evidence and replay logic, shared by the
  browser and the tests.
- 19 tests (`tests/test_evidence_frontend.py`) that run the real JS in Node.
  They check that replay observations match an independent derivation from
  the snapshot, that matrix points equal the stored score and breakdown, that
  cargo stays unknown, that GFW's gap-intent wording appears only where the
  source labels a gap, and that the UI has no overclaiming wording.

### Changed

- Score labels: "AIS switched off" is now "AIS gaps", and "Loitering at sea"
  is now "Loitering and encounters", which matches what the component
  counts. The score formula is unchanged.
- AIS-gap events show GFW's "possible intentional disabling" label only where
  the source sets it. Long durations read in days.
- Map legend lists only event kinds present in the current view. Clearer map
  controls, focus, hover, empty and unknown states. Focus returns to the list
  after closing a dossier. `#imo=` deep links also work on hash change.
  Reduced-motion users get no transitions or animated map moves.
- The vessel list now places the name left and the score right explicitly
  (CSS grid auto-placement had swapped them).
- `video/record_scenes.py` highlights the new matrix rows instead of the
  removed `#d-parts` list.

## [0.4.1] - 2026-09-30

### Added

- An evidence-backed SAR + ML feasibility review separating deployable
  dark-vessel detection, research-grade STS screening, and experimental
  laden/ballast inference.
- A gated pilot plan covering data governance, detector reproduction,
  probabilistic AIS association, human-reviewed STS candidates, independent
  cargo-state labels, evaluation, and stop criteria.

### Changed

- Replaced uncited model-accuracy, training-time, latency, and throughput
  estimates in the datasets/ML research with verified source capabilities and
  explicit licensing, resolution, label, and ground-truth limitations.
- Documented that Sentinel-1 IW GRD has about 20 m x 22 m resolution despite
  10 m pixel spacing, and that it is not a validated freeboard or load-state
  sensor.

## [0.4.0] - 2026-09-30

### Added

- A narrated 3-minute pitch and demo video (1080p30, 3 min 9 s, 44 MB). It is
  served by the live site at `/watch.html`, with English subtitles, 11
  clickable chapters and a download link.
- A reproducible video pipeline in `video/`:
  - `make_voice.py`: ElevenLabs narration, one clip per scene, with character
    timestamps, cached by content.
  - `record_scenes.py`: frame-accurate 1080p capture of the live site and
    animated title cards. Actions are synced to the spoken words. Captures run
    in slow motion for smooth motion.
  - `assemble.py`: crossfades, fades, loudness normalisation to −16 LUFS,
    SRT/VTT subtitles, chapters and the poster.
- A README section with a clickable video poster; video links in the
  write-up, demo script and pitch outline.
- Media tests: the watch page's files exist, subtitles agree, chapters are
  ordered, and the video stays under GitHub's 50 MB warning size.

### Changed

- The README GIF, both screenshots and the deck's product slide were
  re-captured to show the "Port calls in the window" label.

## [0.3.0] - 2026-09-30

### Added

- MIT licence for the code. Data stays under OpenSanctions CC BY-NC 4.0 and
  Global Fishing Watch non-commercial terms.
- A 300-vessel snapshot: 276 located, trend −10% (Jun–Aug vs Mar–May).
- Dashboard: a "Cargo state known" figure (0 of 300 without draft data), a
  "No recent position" tag in the list, and a "View on Global Fishing Watch"
  link in each dossier.
- `scripts/figures.py`, the single source for every figure quoted in the docs
  and deck.
- `scripts/record_demo.py` and `docs/demo.gif`, a recording of the live site.
- A showcase README with badges, the demo GIF, a figures table, the
  EAST 1 → WOLF story, a Mermaid diagram and a limits table.
- Snapshot tests: valid JSON, consistent counts, trim, file size.

### Changed

- 30 events are kept per vessel, and `vessels.json` is written compact
  (1.44 MB, down from 2.79 MB). Aggregates are computed before trimming.
- Every figure in the write-up, demo script, pitch outline and deck was
  regenerated from the 300-vessel snapshot.
- The dashboard names Botswana, Nicaragua and Syria, and marks Botswana as
  landlocked, which matches the 11 quoted landlocked flags. The port-call
  figure is labelled "in the window" because the last month is partial.
- The pipeline defaults to `--max 300`, so a bare run can't shrink the live
  snapshot.

## [0.2.0] - 2026-09-30

### Added

- A product brief: a map-first "hidden supply monitor" for commodity and energy
  traders.
- A pipeline over real data. It reads the OpenSanctions shadow-fleet list
  (merged by IMO) and every Global Fishing Watch identity per vessel. It
  records dated loitering, port-call, AIS-gap and encounter events, a
  transparent risk score, capacity and value ranges, a monthly activity trend
  and the busiest ports. It adds a response cache, CLI flags
  (`--max/--start/--end/--offline`) and 9 offline tests.
- A committed real snapshot: 120 vessels, 30 Sep 2025 – 27 Sep 2026.
- A redesigned dashboard: a nautical-chart map, the trend headline, key
  figures and a searchable list, plus per-vessel dossiers with identity
  history and dated activity. It supports `#imo=` deep links.
- A live deployment at https://ghost-fleet.vercel.app.
- Submission materials in `docs/submission/`: write-up, demo script, pitch
  deck outline.

### Changed

- Cargo state is `UNKNOWN` with 0% confidence when no draft is available.
  Previously it reported 50% with no evidence.
- Identity changes count chronological AIS identity switches.
- Older planning documents are marked historical.

### Removed

- Random vessel positions in the dashboard. Fictional demo data moved to
  `dashboard/data/vessels.demo.json` and is not deployed.

## [0.1.2] - 2026-09-29

### Added

- A concept-first, plain-language guide covering the problem, terminology,
  proposed product, evidence sources, users, benefits, limitations, success
  criteria, and decisions required before implementation.
- A repository guardrail pausing further prototype development until the project
  owner selects the user, use case, and direction.

### Changed

- Reframed the README and handover around concept definition rather than the
  exploratory prototype.

## [0.1.1] - 2026-09-29

### Added

- Research documentation in `docs/DATASETS_AND_ML_RESEARCH.md` covering free & open-source datasets (NOAA MarineCadastre, Danish Maritime Authority AIS, DIU/GFW xView3-SAR), machine learning model feasibility (Cargo Load Classifier, Dark Vessel SAR Detector, GNN Evasion Network), empirical accuracy benchmarks, and inference latency/resource load constraints.
- Updated project planning references in `docs/PLANNING.md`.

## [0.1.0] - 2026-09-29

### Added

- Initial dark-fleet risk and economic signal pipeline.
- Project setup, dependency, collaboration, handover, and session documentation.
- Git exclusions for credentials, downloaded datasets, and generated outputs.
