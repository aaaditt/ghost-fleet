# Verified SAR, AIS, and ML Data Sources

*Reviewed 2026-09-30. This replaces the earlier uncited benchmark estimates in
this file. Product capabilities, availability, and terms can change; verify
them again before an implementation or commercial decision.*

## Purpose

This is the source catalogue for the proposed post-hackathon SAR research in
Ghost Fleet. It records what each source actually supplies, what it does not
supply, and how it could support an experiment. It does **not** claim model
accuracy, operating cost, or production readiness.

The project-level conclusions are in [SAR and ML feasibility](SAR_ML_FEASIBILITY.md),
and the proposed experiment is in [the pilot plan](SAR_ML_PILOT_PLAN.md).

## Data-source decision table

| Source | What is available | Useful for | Important constraint | Decision |
|---|---|---|---|---|
| Copernicus Sentinel-1 | Free C-band SAR, including GRD and SLC products; APIs and catalogue access | Wide-area historical screening, reproducing vessel detection, building an acquisition catalogue | Common IW GRD resolution is about 20 m x 22 m despite 10 m pixel spacing; scheduled coverage is not continuous observation | Use for the open pilot and detection research |
| Global Fishing Watch SAR detections | API/download dataset of SAR detections, with matched/unmatched status and vessel identity where matched | Fastest route to a dark-vessel evidence layer without processing raw scenes | Detection is not identity, intent, cargo state, or proof; API is non-commercial | Use first for a no-training prototype |
| xView3-SAR | 991 analysis-ready Sentinel-1 scenes with 243,018 labels, AIS/VMS matching, wind and bathymetry context | Reproduce and evaluate maritime-object detection and length estimation | Built for detection and fishing/non-fishing characterization, not tanker load state or STS-transfer confirmation | Use for detector benchmarking, not cargo-state labels |
| SARFish | Corresponding Sentinel-1 GRD and SLC products and xView3-derived tasks | Compare detected imagery with phase-preserving complex data | Full dataset is multi-terabyte; terms and storage needs must be reviewed before download | Start only with its sample |
| AIS Message 5 / licensed AIS history | Manually entered present draught, dimensions, destination, identity | Weak labels and covariates for cargo-state research; temporal vessel matching | Draught can be stale, wrong, absent, or manipulated; the GFW records used by Ghost Fleet do not expose it | Never treat it as independent truth |
| Commercial high-resolution SAR | Sub-metre to few-metre products, targeted tasking, archive search | Detailed vessel separation, height/freeboard research, higher-frequency monitoring | Paid, narrow scenes at the finest modes, sensor/domain shift, contract-specific reuse rights | Consider only after the open-data gates pass |

## 1. Copernicus Sentinel-1

Sentinel-1 is a day/night, cloud-penetrating C-band SAR mission. The current
operational constellation is Sentinel-1C and Sentinel-1D. Copernicus makes
Sentinel products available free of charge to public, scientific, and
commercial users. Catalogue and processing interfaces include STAC, OData,
Sentinel Hub, openEO, and S3-style access.

For the common Interferometric Wide Swath products:

| Product | Resolution | Pixel spacing | What that means here |
|---|---:|---:|---|
| IW GRD high resolution | 20 m x 22 m | 10 m x 10 m | A 250 m tanker spans several resolution cells in length but only a few across its beam. Pixel spacing is not true resolution. |
| IW SLC | roughly 2.7–3.5 m slant range x 22 m azimuth | 2.3 m x 14.1 m | Preserves complex phase, but remains strongly anisotropic and is not ordinary map imagery. |

Sentinel-1 supports single or dual polarisation, such as VV+VH, not full
quad-polarimetry. This matters because a published freeboard-retrieval result
uses polarimetric scattering quantities that are not directly equivalent to
ordinary Sentinel-1 GRD inputs.

The constellation has a nominal six-day repeat pattern, but this is not a
promise that every sea area is imaged every six days in the desired mode,
geometry, or polarisation. A pilot must query actual archive coverage and
acquisition plans for each area of interest.

- [ESA Sentinel-1 facts and figures](https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Sentinel-1/Facts_and_figures)
- [Copernicus Sentinel-1 collection and access overview](https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-1)
- [Sentinel-1 GRD processing and catalogue fields](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S1GRD.html)
- [STAC catalogue documentation](https://documentation.dataspace.copernicus.eu/APIs/STAC.html)
- [Sentinel-1 product resolutions](https://sentiwiki.copernicus.eu/web/s1-products)
- [Sentinel-1 mission and polarisation description](https://sentiwiki.copernicus.eu/web/s1-mission)
- [Copernicus Data Space terms](https://dataspace.copernicus.eu/terms-and-conditions)

## 2. Global Fishing Watch

The GFW v3 4Wings API lists `public-global-sar-presence:latest`, described as
industrial-vessel detections derived from Sentinel-1 imagery and deep-learning
classification. The data currently cover 2017 onward, with updates dependent on
satellite passes. Filters include whether a detection matched AIS; matched
records can carry a GFW vessel ID. The downloadable form has richer fields than
the map API, including length and detection/matching scores.

This is the lowest-friction useful SAR path for Ghost Fleet:

1. Query detections within a small corridor and date range.
2. Separate AIS-matched and unmatched detections.
3. Link matched GFW vessel IDs to existing vessel records.
4. Show the SAR observation time, match status, and source as evidence.
5. Call unmatched objects **unmatched SAR detections**, not “sanctions evaders.”

GFW cautions that inferred activity events are estimates. Its AIS encounter
definition uses modelled positions, proximity, duration, speed, and distance
from anchorage; it is a lead, not confirmation that cargo moved.

The API terms are CC BY-NC 4.0/non-commercial, require attribution, and state
request limits. Those terms fit the current hackathon research but not an
assumed commercial deployment.

- [GFW SAR detection dataset and API fields](https://globalfishingwatch.org/our-apis/documentation/docs/v3/4wings)
- [GFW SAR download release](https://globalfishingwatch.org/platform-update/2024-may-data-download-portal-new-dataset-released-featuring-vessel-detections-from-sentinel-1-sar/)
- [SAR detection interaction example](https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/examples/interaction/interaction-example2)
- [GFW data caveats](https://globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/data-caveats)
- [GFW licence, attribution, and rate limits](https://globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits)

## 3. xView3-SAR and SARFish

The peer-reviewed xView3-SAR release contains 991 Sentinel-1 scenes covering
43.2 million km² and 243,018 labels assembled from automated SAR detections,
probabilistic AIS/VMS matching, and manual annotation. The competition tasks are
maritime-object detection, vessel classification, fishing-vessel
classification, and vessel-length estimation. The paper notes that
medium-resolution SAR can make vessels, rocks, and infrastructure look similar,
and that visual inspection may not distinguish fishing from non-fishing
vessels.

Therefore xView3 is suitable for:

- reproducing a detector baseline;
- learning SAR preprocessing and scene tiling;
- measuring detection and length-estimation performance on held-out scenes;
- testing robustness by geography, coast distance, wind, and target size.

It is **not** a laden/ballast dataset. It supplies neither freeboard nor cargo
state labels, and its “dark” concept means an SAR detection without an adequate
AIS/VMS match—not a finding of illegal conduct.

SARFish adds paired GRD/SLC access for related tasks. Its public repository says
the full compressed set is about 3.3 TB and the uncompressed set about 6.5 TB;
the sample is still several gigabytes. Use the sample before approving the full
storage and compute commitment.

- [xView3-SAR paper](https://proceedings.neurips.cc/paper_files/paper/2022/file/f4d4a021f9051a6c18183b059117e8b5-Paper-Datasets_and_Benchmarks.pdf)
- [xView3 challenge and dataset](https://iuu.xview.us/)
- [Official xView3 reference implementation](https://github.com/DIUx-xView/xview3-reference)
- [SARFish repository and documented sizes](https://github.com/DIUx-xView/SARFish)

The xView3 site describes the data as free/open, but the currently linked data
terms are not reliably available. Before redistributing data or model weights,
capture and review the terms presented during download. An open-source code
licence does not automatically license accompanying imagery or labels.

## 4. AIS draught and ground truth

AIS Class A Message 5 contains “maximum present static draught” in 0.1 m units.
IMO guidance says the officer of the watch manually enters draught at the start
of a voyage and amends it when required. The same guidance says AIS integrity
checks do not validate the quality or accuracy of ship-sensor inputs.

Consequences for ML:

- AIS draught can be a useful noisy feature or weak label.
- A timestamp-aligned draught change around a terminal call can help select
  candidate loaded and ballast examples.
- It cannot validate that an independent SAR model has discovered true cargo
  state if the same AIS field is also used to build the labels.
- Strong validation needs independent records such as terminal/port loading
  documentation, surveyor or vessel loading-computer records, or controlled
  visual readings of draught marks, with appropriate access rights.

- [USCG description of AIS Message 5](https://www.navcen.uscg.gov/ais-class-a-static-voyage-message-5)
- [IMO AIS operational guidance, including manual draught entry](https://www.navcen.uscg.gov/sites/default/files/pdf/ais/references/IMO_A1106_29_Revised_guidelines.pdf)

## 5. Commercial SAR

Commercial providers resolve much more detail than routine Sentinel-1 wide
swath products. Current published specifications include:

- ICEYE modes from sub-metre Spot/Dwell through 3 m Strip to wider Scan modes
  at lower resolution.
- Capella detected and complex products with sub-metre Spotlight modes and
  roughly metre-class Stripmap products.

These specifications make a targeted height/freeboard or side-by-side-vessel
experiment more plausible, but resolution alone does not validate a cargo-state
model. Collection geometry, polarisation, calibration, sea state, vessel
orientation, motion, and label quality still determine whether the inference
works. Public list pricing was not found; tasking, archive access, derived-data
rights, and latency require provider quotes and licence review.

Both providers make small open-data collections available for format and
pipeline testing, but those samples are not a source of chosen tanker/time
pairs or load-state labels.

- [ICEYE imaging modes](https://www.iceye.com/defense-and-intelligence/imaging-modes)
- [ICEYE product documentation](https://sar.iceye.com/latest/)
- [ICEYE open data](https://sar.iceye.com/6.0.6/opendata/opendata/)
- [Capella SAR data modes and formats](https://www.capellaspace.com/solution/sar-data)
- [Capella product guide](https://support.capellaspace.com/sar-imagery-products-guide)
- [Capella open-data access](https://support.capellaspace.com/how-do-i-access-capellas-open-data)

## 6. Claims removed from the previous version

The previous document gave exact accuracy, F1, latency, training-time, memory,
and throughput figures without a traceable experiment or citation. It also
described an AIS cargo classifier as “production” and implied the current code
already used a draft/speed heuristic. Those claims have been removed because:

- benchmark scores depend on a named dataset split, metric, threshold, hardware,
  preprocessing, and task definition;
- xView3 does not benchmark tanker load state;
- its published scores cannot be treated as expected Ghost Fleet performance;
- OpenSanctions and GFW events do not provide confirmed oil-transfer labels for
  the proposed GNN;
- the current Ghost Fleet snapshot honestly reports cargo state as unknown when
  evidence is absent.

Any future number belongs in a reproducible experiment report containing the
dataset version, split policy, code revision, metrics, confidence intervals,
failure analysis, hardware, and exact command used to produce it.
