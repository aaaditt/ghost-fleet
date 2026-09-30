# SAR + ML build, then media refresh (v0.6.0)

- Requested by: project owner, 2026-09-30 ("build the full ML list", deploy and
  regenerate narration once verified).
- Supersedes the product brief's non-goal "no trained SAR/CV model" for this
  build, by the owner's explicit request. Honesty rules still apply: no model
  output is proof, and every metric states what it was measured against.

## Verified constraints (probed 2026-09-30)

| Constraint | Finding | Consequence |
|---|---|---|
| GPU | GTX 1650, 4 GB | Small CNNs only; train on 64–96 px chips |
| Disk | ~11 GB free | No full scenes. Windowed COG reads; cache capped at ~2 GB |
| Imagery | Planetary Computer `sentinel-1-rtc`, anonymous, 10 m UTM COGs; 2 km window in ~1.7 s | Chips on demand |
| GFW SAR | `public-global-sar-presence` report API; `vesselId`, `imo`, `matched`, 0.01° cells; `entryTimestamp` equals the S1 scene time | Detections can be tied to an exact scene; our vessels matched by IMO |
| GFW filter | `vessel_id` filter not supported in reports | Query corridors, filter client-side by IMO |
| xView3 / SARFish labels | Behind DIU registration | Not used; adapter accepts the CSV if the owner registers |
| Draught | Not in any free source | Cargo labels can only be weak (voyage context) |

## Deliverables and how each is made honest

1. **SAR detection ingestion** (`ml/gfw_sar.py`). Corridors are derived from
   the snapshot's event clusters. Fetch matched and unmatched detections per
   corridor per month into `.cache/ml/`. Output per vessel: radar detections
   matched to its IMO, with scene times.
2. **SAR imagery ingestion** (`ml/s1.py`). STAC search plus windowed VV/VH
   chip reads, cached as float16 `.npz`.
3. **Vessel detector** (`ml/detector.py`, `ml/cfar.py`). A CA-CFAR baseline
   and a small CNN presence and localisation model.
   - Positives are chips centred on GFW detections in their exact scene.
     Negatives are open-water chips from the same scenes with no detection
     within 2 km.
   - The split is by scene, and never by chip. Metrics are P/R/F1 and PR-AUC
     against GFW on held-out scenes, compared with CFAR, plus a visually
     reviewed sample.
   - Stated limit: this measures agreement with GFW's detector, not ground
     truth.
4. **AIS-to-SAR association** (`ml/matching.py`).
   - For each of our vessels' loitering or port events that overlaps a
     scene, score candidate detections using a distance likelihood (sigma
     from event drift and cell size) against local clutter density. The
     output is a match probability and its alternatives.
   - Evaluation: agreement with GFW's own matching on held-out scenes, plus a
     reliability table.
   - Unmatched detections near a vessel are reported as leads, with the
     search radius and time stated.
5. **Side-by-side / possible-STS candidates** (`ml/sts.py`).
   - For scenes during loitering events, detect separate hulls. A candidate is
     two targets within 250 m, or one elongated target with two peaks.
   - All candidates form an image review queue. Any positives quoted come
     only from reviewed chips, and are labelled "possible side-by-side",
     never "STS transfer".
6. **Cargo-state study** (`ml/cargo.py`).
   - Weak labels: after a call at a Russian crude export terminal and before
     the next port call, the vessel is "likely laden". Before arriving at an
     export terminal, it is "likely ballast".
   - Features: SAR chip statistics and length from the detector.
   - Baselines: majority class, and voyage context without imagery.
   - Grouped-by-vessel CV, AUC with bootstrap CI.
   - Go/no-go: the dashboard shows a SAR cargo estimate only if imagery beats
     the no-image baseline out-of-vessel with a CI above it. Otherwise cargo
     stays UNKNOWN and the model card reports the negative result.
7. **Integration**.
   - `dashboard/data/sar.json` holds per-vessel radar evidence, matches, leads
     and candidates, plus a metrics summary.
   - New matrix rows: radar detections, unmatched detections nearby, and
     side-by-side candidates. The cargo row changes only if the gate in
     item 6 passes.
   - SAR marks are added to the replay, and a "Models" page (model card) is
     added.
   - Tests check data consistency and wording.
8. **Operational gaps**. Commit the Playwright browser check as
   `tests/browser_check.py`, opt-in, and deploy.
9. **Media**.
   - Figures script update, README, screenshots, `docs/demo.gif`, and the
     submission write-up, pitch and demo script.
   - New narration via ElevenLabs (only changed scenes cost characters), a
     re-recorded video, and a deploy.

## Execution order (each ends green before the next)

1. Commit the browser check; deploy v0.5.0 (closes review gaps).
2. `ml/` scaffolding, corridors, GFW SAR ingestion and per-vessel evidence.
3. S1 chips, dataset, CFAR and CNN, evaluation.
4. Association, leads, STS candidates and the review queue.
5. Cargo study and gate decision.
6. `sar.json`, dashboard integration, model card page, tests, browser check.
7. Docs, figures, README, screenshots, GIF, submission docs.
8. Narration, video, deploy, session close-out (v0.6.0).

## Out of repo / not committed

Chips, scene caches, raw GFW responses and model weights (checksums go in
the model card). Committed: code, `sar.json`, a handful of illustrative PNG
chips for the dossier/README, and reports.
