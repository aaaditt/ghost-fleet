"""Stage 5: can Sentinel-1 imagery tell a laden tanker from one in ballast?

Labels (weak, from voyage context in the snapshot's own port calls):
  likely laden   - last port call before the image was a Russian oil export
                   terminal, and the next call is not one
  likely ballast - the next port call is an export terminal and the last was not
Everything else is unlabelled. These are assumptions about voyages, not draught
measurements; a tanker can also sail part-loaded or discharge by STS.

Features come only from the radar image of the tanker: every GFW radar
detection of our tankers (hull = the CNN's strongest peak) plus our own
confident matches (posterior >= 0.8), one per vessel per scene: peak and mean backscatter in VV and VH, VH/VV ratio,
bright-pixel area and a length estimate. Gross tonnage is included so the model
can normalise for hull size.

Evaluation: grouped 5-fold cross-validation by vessel (no vessel in both train
and test), out-of-fold ROC-AUC with a vessel-level bootstrap 95% CI, against the
majority-class baseline (AUC 0.5).

Pre-registered gate (fixed before results were seen, 2026-09-30): the dashboard
may show a per-vessel SAR cargo estimate only if the lower 95% CI bound of the
out-of-vessel AUC is at least 0.65 with at least 60 labelled observations from
at least 20 vessels. Otherwise cargo state stays UNKNOWN and the negative
result is published in the model card.

Usage: python -m ml.cargo
"""

import json
import math

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml import CACHE, SNAPSHOT, dataset as chipset, detector, matching, s1

EXPORT_TERMINALS = {"PRIMORSK", "UST LUGA", "VYSOTSK", "NOVOROSSIYSK", "TUAPSE", "KOZMINO", "NAKHODKA", "DE KASTRI"}
GATE = {"auc_ci_low": 0.65, "min_obs": 60, "min_vessels": 20}
OUT = CACHE / "reports" / "cargo.json"
FEATURES = ["vv_peak", "vh_peak", "vv_top10", "vh_top10", "ratio", "area_px", "length_m", "gt"]


def label(events, when):
    ports = [e for e in events if e["kind"] == "port_visit" and e.get("start")]
    before = [e for e in ports if (e["end"] or e["start"]) <= when]
    after = [e for e in ports if e["start"] > when]
    last = before[-1] if before else None
    nxt = after[0] if after else None
    is_exp = lambda e: e is not None and (e.get("port") or "").upper() in EXPORT_TERMINALS and e.get("port_flag") == "RUS"
    if last and is_exp(last) and not is_exp(nxt):
        return 1
    if nxt and is_exp(nxt) and last is not None and not is_exp(last):
        return 0
    return None


def features(db, trow, tcol, gt):
    r0, c0 = max(0, trow - 12), max(0, tcol - 12)
    win = db[:, r0:r0 + 24, c0:c0 + 24]
    vv, vh = win[0], win[1]
    bright = vv > (np.median(db[0]) + 10)
    rr, cc = np.nonzero(bright)
    length = 0.0
    if len(rr) >= 3:
        pts = np.stack([rr, cc], 1).astype(float)
        pts -= pts.mean(0)
        ev = np.linalg.eigvalsh(np.cov(pts.T))
        length = 10.0 * 4 * math.sqrt(max(ev[-1], 0))  # ~ full extent of a uniform bar
    top_vv = np.sort(vv.ravel())[-10:]
    top_vh = np.sort(vh.ravel())[-10:]
    return {"vv_peak": float(vv.max()), "vh_peak": float(vh.max()), "vv_top10": float(top_vv.mean()),
            "vh_top10": float(top_vh.mean()), "ratio": float(top_vh.mean() - top_vv.mean()),
            "area_px": float(bright.sum()), "length_m": length, "gt": float(gt or 0)}



def observations():
    """(imo, scene_time, db, target row, col) for every radar image of our tankers.

    Two sources: GFW detections of our tankers (detector dataset chips; the hull
    is the CNN's strongest peak) and our own confident matches (posterior >= 0.8).
    One observation per vessel per scene.
    """
    seen = set()
    net = detector.load_model("cpu")
    for r in chipset.load().query("label == 1 and ours").itertuples():
        chip = detector.load_chip(r.chip)
        p, row, col = detector.peak(net, chip)
        if p < 0.5 or (r.imo, r.scene) in seen:
            continue
        seen.add((r.imo, r.scene))
        yield r.imo, r.scene_time[:16], s1.to_db(chip), row, col, "gfw_detection"
    for r in matching.load()["rows"]:
        if not r["candidates"] or r["candidates"][0]["posterior"] < 0.8 or (r["imo"], r["scene"]) in seen:
            continue
        seen.add((r["imo"], r["scene"]))
        with np.load(matching.CHIPS / f"{r['chip']}.npz") as z:
            db = s1.to_db(z["chip"].astype(np.float32))
        t = r["candidates"][0]
        yield r["imo"], r["scene_time"][:16], db, t["row"], t["col"], "our_match"


def dataset():
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    vessels = {v["imo"]: v for v in snap["vessels"]}
    X, y, groups, meta = [], [], [], []
    for imo, when, db, row, col, src in observations():
        v = vessels[imo]
        lab = label(v["events"], when)
        if lab is None:
            continue
        f = features(db, row, col, v.get("gross_tonnage"))
        X.append([f[k] for k in FEATURES])
        y.append(lab)
        groups.append(imo)
        meta.append({"imo": imo, "time": when, "label": lab, "source": src, **f})
    return np.array(X), np.array(y), np.array(groups), meta


def vessel_bootstrap_auc(y, p, groups, n=2000, seed=7):
    rng = np.random.default_rng(seed)
    ids = np.unique(groups)
    idx = {g: np.nonzero(groups == g)[0] for g in ids}
    vals = []
    for _ in range(n):
        take = np.concatenate([idx[g] for g in rng.choice(ids, len(ids))])
        if y[take].min() == y[take].max():
            continue
        vals.append(roc_auc_score(y[take], p[take]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def run():
    X, y, groups, meta = dataset()
    n_vessels = len(set(groups))
    out = {"labels": "voyage context (weak): after a Russian export-terminal call = likely laden; "
                     "before one = likely ballast",
           "export_terminals": sorted(EXPORT_TERMINALS), "features": FEATURES,
           "observations": int(len(y)), "vessels": n_vessels,
           "laden": int(y.sum()) if len(y) else 0, "ballast": int((1 - y).sum()) if len(y) else 0,
           "gate": GATE, "models": {}}
    enough_classes = len(y) and 0 < y.sum() < len(y)
    if enough_classes and n_vessels >= 5:
        folds = GroupKFold(n_splits=min(5, n_vessels))
        models = {
            "logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")),
            "gradient_boosting": HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05,
                                                                class_weight="balanced"),
        }
        for name, model in models.items():
            oof = np.zeros(len(y))
            for tr, te in folds.split(X, y, groups):
                if y[tr].min() == y[tr].max():
                    oof[te] = y[tr].mean()
                    continue
                model.fit(X[tr], y[tr])
                oof[te] = model.predict_proba(X[te])[:, 1]
            auc = roc_auc_score(y, oof)
            out["models"][name] = {"auc_out_of_vessel": float(auc), "auc_ci95": vessel_bootstrap_auc(y, oof, groups)}
    best = max(out["models"].values(), key=lambda m: m["auc_ci95"][0], default=None)
    passed = bool(best and best["auc_ci95"][0] >= GATE["auc_ci_low"] and len(y) >= GATE["min_obs"]
                  and n_vessels >= GATE["min_vessels"])
    out["gate_passed"] = passed
    out["decision"] = ("Experimental SAR cargo signal may be shown with its uncertainty." if passed else
                       "No-go: imagery did not clear the pre-registered gate. Cargo state stays UNKNOWN.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({**out, "rows": meta}, indent=1))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    run()
