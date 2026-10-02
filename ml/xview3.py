"""Independent evaluation against xView3-SAR vessel labels.

GFW's detections trained and scored our detector, so its 0.991 PR-AUC is
agreement with GFW. xView3-SAR (DIU, https://iuu.xview.us) is an independent
reference: vessels labelled by analysts and AIS on 2020 Sentinel-1 scenes from
other seas. Only the labels CSV is needed (a few MB). The imagery is read
remotely from Microsoft Planetary Computer, like the rest of ml/.

xView3 scene ids are anonymised; SARFish's correspondence table
(github.com/DIUx-xView/SARFish) maps them to Sentinel-1 GRD products, whose
Planetary Computer RTC item id is the product id without its last field plus
"_rtc".

Chips are 160 px (1.6 km) as in training. Positives are centred on HIGH or
MEDIUM confidence vessels; negatives are open water at least 2 km from any
xView3 detection. Scores are cached per scene, so an interrupted run resumes.

Usage: python -m ml.xview3 path/to/validation.csv [--scenes 20] [--per-scene 80]
"""

import argparse
import json
import random
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

from ml import CACHE, cfar, detector, s1
from ml.dataset import km

OUT = CACHE / "reports" / "xview3.json"
WORK = CACHE / "xview3"
MAP_URL = "https://raw.githubusercontent.com/DIUx-xView/SARFish/main/reference/labels/xView3_SLC_GRD_correspondences.csv"


def scene_map():
    """xView3 scene_id -> Planetary Computer RTC item id."""
    path = WORK / "correspondences.csv"
    if not path.exists():
        WORK.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MAP_URL, path)
    c = pd.read_csv(path)
    return {r.scene_id: r.GRD_product_identifier.rsplit("_", 1)[0] + "_rtc" for r in c.itertuples()}


def sample_points(g, bbox, per_scene, rng, seed):
    """Vessels (HIGH/MEDIUM), plus three times as many open-water candidates >= 2 km from every xView3
    detection: many land on land and are dropped, and score_scene balances the rest."""
    vessels = g[(g.is_vessel == True) & g.confidence.isin(["HIGH", "MEDIUM"])]  # noqa: E712
    take = vessels.sample(min(len(vessels), per_scene // 2), random_state=seed)
    pts = [(r.detect_lat, r.detect_lon, 1, float(r.distance_from_shore_km)) for r in take.itertuples()]
    w, s, e, n = bbox
    every = list(zip(g.detect_lat, g.detect_lon))
    tries = 0
    while len(pts) < 4 * len(take) and tries < 40000:
        tries += 1
        lat, lon = rng.uniform(s, n), rng.uniform(w, e)
        if all(km(lat, lon, a, b) > 2 for a, b in every):
            pts.append((lat, lon, 0, None))
    return pts


def score_scene(net, item, pts):
    sc = {"id": item.id, "item": item.to_dict(), "datetime": str(item.datetime)}

    def one(p):
        lat, lon, y, shore = p
        try:
            got = s1.read_chip(sc, lat, lon)
        except Exception:
            return None
        if got is None:
            return None
        chip = got[0]
        if y == 0 and np.median(s1.to_db(chip)[0]) >= -13:   # land or bright clutter, as in training
            return None
        with torch.no_grad():
            p_cnn = float(torch.sigmoid(net(torch.from_numpy(detector.normalise(chip))[None]))[0])
        return {"y": y, "cnn": p_cnn, "cfar": float(cfar.chip_score(chip)), "shore_km": shore}

    with ThreadPoolExecutor(8) as ex:
        got = [r for r in ex.map(one, pts) if r is not None]
    # Balance the classes per scene, so PR-AUC is comparable with the GFW test (a coin toss scores 0.5).
    pos, neg = [r for r in got if r["y"]], [r for r in got if not r["y"]]
    n = min(len(pos), len(neg))
    rnd = random.Random(item.id)
    return rnd.sample(pos, n) + rnd.sample(neg, n)


def boot_ci(y, s, n=1000, seed=0):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            vals.append(average_precision_score(y[i], s[i]))
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]


def at_threshold(y, s, t):
    tp = int(((s >= t) & (y == 1)).sum())
    fp = int(((s >= t) & (y == 0)).sum())
    fn = int(((s < t) & (y == 1)).sum())
    return {"threshold": round(float(t), 3), "precision": round(tp / max(tp + fp, 1), 3),
            "recall": round(tp / max(tp + fn, 1), 3), "tp": tp, "fp": fp, "fn": fn}


def run(csv_path, n_scenes=20, per_scene=80, seed=7):
    rng = random.Random(seed)
    lab = pd.read_csv(csv_path)
    ids = scene_map()
    net = detector.load_model("cpu")
    client = s1._client()
    WORK.mkdir(parents=True, exist_ok=True)
    scenes = [sid for sid in lab.scene_id.drop_duplicates().sample(frac=1, random_state=seed) if sid in ids][:n_scenes]
    rows = []
    for k, sid in enumerate(scenes, 1):
        cache = WORK / f"scores_{sid}_{per_scene}_balanced.json"
        if cache.exists():
            got = json.loads(cache.read_text())
        else:
            items = list(client.search(collections=[s1.COLLECTION], ids=[ids[sid]]).items())
            if not items:
                print(f"[{k}/{len(scenes)}] {sid}: no RTC item")
                continue
            got = score_scene(net, items[0], sample_points(lab[lab.scene_id == sid], items[0].bbox, per_scene, rng, seed))
            cache.write_text(json.dumps(got))
        rows += [dict(r, scene=sid) for r in got]
        print(f"[{k}/{len(scenes)}] {sid}: {len(got)} chips, {sum(r['y'] for r in got)} vessels")

    df = pd.DataFrame(rows)
    y, cnn, cf = df.y.values, df.cnn.values, df.cfar.values
    det = json.loads((CACHE / "reports" / "detector.json").read_text())
    pos = df[df.y == 1]
    t_cnn, t_cfar = det["cnn"]["at_val_threshold"]["threshold"], det["cfar"]["at_val_threshold"]["threshold"]
    bands = {"near shore (< 5 km)": pos.shore_km < 5, "offshore (>= 5 km)": pos.shore_km >= 5}
    out = {
        "reference": "xView3-SAR validation labels: HIGH/MEDIUM confidence vessels (independent of GFW); "
                     "negatives are open water >= 2 km from any xView3 detection; classes balanced per scene",
        "scenes": int(df.scene.nunique()), "chips": int(len(df)), "positive": int(y.sum()),
        "years": "2020 scenes (our detector was trained on 2025-26 GFW corridors)",
        "cnn": {"pr_auc": round(float(average_precision_score(y, cnn)), 3), "pr_auc_ci95": boot_ci(y, cnn),
                "roc_auc": round(float(roc_auc_score(y, cnn)), 3), "at_val_threshold": at_threshold(y, cnn, t_cnn)},
        "cfar": {"pr_auc": round(float(average_precision_score(y, cf)), 3), "pr_auc_ci95": boot_ci(y, cf),
                 "roc_auc": round(float(roc_auc_score(y, cf)), 3), "at_val_threshold": at_threshold(y, cf, t_cfar)},
        "recall_by_distance": {name: {"vessels": int(m.sum()),
                                      "cnn": round(float((pos[m].cnn >= t_cnn).mean()), 3) if m.any() else None,
                                      "cfar": round(float((pos[m].cfar >= t_cfar).mean()), 3) if m.any() else None}
                               for name, m in bands.items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--scenes", type=int, default=20)
    ap.add_argument("--per-scene", type=int, default=80)
    a = ap.parse_args()
    run(a.csv, a.scenes, a.per_scene)
