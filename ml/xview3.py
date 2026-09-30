"""Optional independent evaluation against xView3-SAR / SARFish labels.

The labels are distributed by DIU after registration (https://iuu.xview.us);
they are not in this repository and were not available when the model card was
written. If you have them, this evaluates the detector and the CFAR baseline on
xView3 scenes read remotely from Planetary Computer (RTC item id = GRD product
id + "_rtc"), using xView3's own vessel labels as the reference.

Expected CSV columns (xView3 validation/public format):
  scene_id, detect_lat, detect_lon, is_vessel, confidence

Usage: python -m ml.xview3 path/to/validation.csv [--scenes 10] [--per-scene 60]
"""

import argparse
import json
import random

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score

from ml import CACHE, cfar, detector, s1
from ml.dataset import km

OUT = CACHE / "reports" / "xview3.json"


def run(csv_path, n_scenes=10, per_scene=60, seed=7):
    rng = random.Random(seed)
    lab = pd.read_csv(csv_path)
    lab = lab[lab.confidence.isin(["HIGH", "MEDIUM"])]
    net = detector.load_model("cpu")
    client = s1._client()
    ys, cnn, cf = [], [], []
    for sid in lab.scene_id.drop_duplicates().sample(frac=1, random_state=seed)[:n_scenes]:
        items = list(client.search(collections=[s1.COLLECTION], ids=[f"{sid}_rtc"]).items())
        if not items:
            continue
        sc = {"id": items[0].id, "item": items[0].to_dict(), "datetime": str(items[0].datetime)}
        g = lab[lab.scene_id == sid]
        vessels = g[g.is_vessel == True]  # noqa: E712
        pts = [(r.detect_lat, r.detect_lon, 1) for r in vessels.sample(min(len(vessels), per_scene // 2), random_state=seed).itertuples()]
        w, s, e, n = items[0].bbox
        allp = list(zip(g.detect_lat, g.detect_lon))
        while len(pts) < per_scene:
            lat, lon = rng.uniform(s, n), rng.uniform(w, e)
            if all(km(lat, lon, a, b) > 2 for a, b in allp):
                pts.append((lat, lon, 0))
        for lat, lon, y in pts:
            got = s1.read_chip(sc, lat, lon)
            if got is None:
                continue
            chip = got[0]
            if y == 0 and np.median(s1.to_db(chip)[0]) >= -13:
                continue
            with torch.no_grad():
                cnn.append(float(torch.sigmoid(net(torch.from_numpy(detector.normalise(chip))[None]))[0]))
            cf.append(cfar.chip_score(chip))
            ys.append(y)
    ys, cnn, cf = map(np.array, (ys, cnn, cf))
    out = {"reference": "xView3-SAR vessel labels (HIGH/MEDIUM confidence)", "chips": int(len(ys)),
           "positive": int(ys.sum()),
           "cnn_pr_auc": float(average_precision_score(ys, cnn)), "cfar_pr_auc": float(average_precision_score(ys, cf))}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--scenes", type=int, default=10)
    ap.add_argument("--per-scene", type=int, default=60)
    a = ap.parse_args()
    run(a.csv, a.scenes, a.per_scene)
