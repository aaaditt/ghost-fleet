# Ghost Fleet: Product Brief

- Approved by: project owner, 2026-09-30
- Status: **Hackathon build, trader-focused**
- Supersedes the "decisions to make" list in `CONCEPT_OVERVIEW.md` §18

## The one question we answer

> **Is hidden, sanctions-linked oil supply rising or falling, and where is it
> moving?**

Ghost Fleet gives a commodity or energy trader a map and a trend of activity
by sanctioned tankers. Every number comes with its evidence, its
assumptions, and a confidence level.

## Decisions

| Decision | Choice |
|---|---|
| First user | Commodity / energy trader (oil desk analyst) |
| First decision improved | Direction and location of hidden sanctioned oil supply |
| Scope | Sanctioned or sanctions-linked **oil tankers** in known shadow-fleet corridors |
| Evidence standard | Directional research signal, not proof of wrongdoing |
| Data freshness | Historical snapshot (about the last 12 months), refreshed by rerunning the pipeline |
| Immediate objective | Hackathon submission (2026-09-30) |
| First experience | Map-first tracker with a "Hidden Supply Monitor" signal panel |

## Data sources

- **OpenSanctions maritime dataset:** which vessels are sanctioned or linked
  to sanctions (IMO, name, flag, programmes).
- **Global Fishing Watch API:** vessel identity history and ship-to-ship
  encounter events with positions and dates.
- **Configured Brent price:** a static reference for rough value ranges.

Both data sources have non-commercial terms. The hackathon build credits both
and makes no commercial use of them.

## What the trader sees

1. A map of sanctioned tankers at their most recently observed positions,
   plus ship-to-ship encounter locations.
2. A monthly trend of encounters and active sanctioned tankers.
3. The split between loaded, ballast, and unknown cargo states, where evidence
   exists.
4. Per-vessel evidence: identity changes, dated encounters, and source links.
5. Value **ranges** with their assumptions shown.

## Non-goals for this build

- No claim of proof, accuracy figures, or validated model performance.
- No live AIS streaming. The data is a dated snapshot.
- ~~No trained SAR/computer-vision model.~~ Superseded by the owner's
  explicit request on 2026-09-30 (see "Amendment" below).
- No trading advice.

## Success criterion

In about three minutes, a trader can see where sanctioned tanker activity is
concentrated and whether it is trending up or down. They can then open one
vessel and understand exactly which evidence produced its score.

## Amendment, 2026-09-30: satellite radar and ML

The project owner explicitly requested the SAR/ML capabilities that were
previously out of scope (vessel detection, AIS-to-radar matching, side-by-side
screening, cargo-state modelling). They are built in `ml/` (v0.6.0) under the
same evidence standard:

- Radar and model outputs are evidence rows with the status *Model estimate*
  and a probability. They never change the transparent screening score.
- Every metric names its reference. Detector and matcher figures are
  agreement with Global Fishing Watch, not ground truth.
- Cargo state stays UNKNOWN unless a model passes a pass mark fixed before
  testing. The radar cargo model failed it (AUC 0.47), and the failure is
  published on the Models page.
- Possible side-by-side pairs are shown only after review, and never as a
  transfer.
