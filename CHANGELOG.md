# Changelog

All notable changes to Ghost Fleet are recorded here. Versions follow semantic
versioning.

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
