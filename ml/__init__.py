"""Ghost Fleet SAR + ML research code.

Stages (see docs/superpowers/plans/2026-09-30-sar-ml-build-and-media.md):
  corridors   -> areas of interest derived from the snapshot's own events
  gfw_sar     -> Global Fishing Watch SAR detections (matched / unmatched)
  s1          -> Sentinel-1 RTC chips from Microsoft Planetary Computer
  detector    -> CA-CFAR baseline and a small CNN, evaluated by scene
  matching    -> event-to-SAR association with probabilities
  sts         -> side-by-side (possible STS) candidates for review
  cargo       -> laden/ballast feasibility study with a go/no-go gate
  build       -> dashboard/data/sar.json and the model card figures

Nothing here is proof of wrongdoing. Every metric states its reference.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "ml"
SNAPSHOT = ROOT / "dashboard" / "data" / "vessels.json"
