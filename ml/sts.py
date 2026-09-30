"""Stage 4: side-by-side (possible ship-to-ship) candidates for human review.

A candidate is a matched observation (our vessel's target has posterior >= 0.5)
with a second distinct target within 250 m. Two hulls moored alongside can
also merge into one blob; at 10 m pixels a pair is only resolvable when the
returns stay separate, so this generator misses many true pairs.

Candidates are rendered as PNG crops into a review queue. Only reviewed labels
are ever quoted, and the product wording is "possible side-by-side activity",
never "ship-to-ship transfer": anchorage queues, bunkering, tugs and rafted
vessels all look alike from orbit.

Usage:
  python -m ml.sts queue      # write candidates + review crops
  python -m ml.sts summary    # after filling review.csv
"""

import argparse
import csv
import json
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from ml import CACHE, matching, s1

PAIR_M = 250.0
WIDE_M = 70.0   # a laden VLCC/Aframax beam is ~35-60 m; two alongside roughly double it
MIN_P = 0.5
QUEUE = CACHE / "sts"
REVIEW = QUEUE / "review.csv"
OUT = CACHE / "reports" / "sts.json"


def shape_of(row, half=30):
    """Bright components near the matched target at full 10 m resolution."""
    with np.load(matching.CHIPS / f"{row['chip']}.npz") as z:
        db = s1.to_db(z["chip"].astype(np.float32))[0]
    t = row["candidates"][0]
    r0, c0 = max(0, t["row"] - half), max(0, t["col"] - half)
    win = db[r0:r0 + 2 * half, c0:c0 + 2 * half]
    mask = win > (np.median(db) + 10)
    lab, n = ndimage.label(mask)
    comps = []
    for i in range(1, n + 1):
        rr, cc = np.nonzero(lab == i)
        if len(rr) < 4:
            continue
        pts = np.stack([rr, cc], 1).astype(float)
        cy, cx = pts.mean(0)
        ev = np.linalg.eigvalsh(np.cov((pts - pts.mean(0)).T)) if len(rr) > 2 else np.array([0.0, 0.0])
        comps.append({"row": cy + r0, "col": cx + c0, "px": int(len(rr)),
                      "length_m": 10 * 4 * math.sqrt(max(ev[-1], 0)), "width_m": 10 * 4 * math.sqrt(max(ev[0], 0))})
    return comps


def pairs(rows):
    """Two hulls within PAIR_M, or one target wide enough to be two hulls alongside."""
    out = []
    for r in rows:
        if not r["candidates"] or r["candidates"][0]["posterior"] < MIN_P:
            continue
        comps = sorted(shape_of(r), key=lambda c: -c["px"])
        if not comps:
            continue
        main = comps[0]
        near = [c for c in comps[1:] if c["px"] >= 6
                and 10 * math.hypot(c["row"] - main["row"], c["col"] - main["col"]) <= PAIR_M]
        wide = main["width_m"] >= WIDE_M and main["length_m"] >= 120
        if near or wide:
            t = {**r["candidates"][0], "row": int(main["row"]), "col": int(main["col"])}
            out.append({**r, "top": t, "partners": [{"row": int(c["row"]), "col": int(c["col"])} for c in near],
                        "reason": "two_targets" if near else "wide_target", "main": main})
    return out


def render(r, path, half=40):
    with np.load(matching.CHIPS / f"{r['chip']}.npz") as z:
        db = s1.to_db(z["chip"].astype(np.float32))[0]
    t = r["top"]
    r0, c0 = max(0, t["row"] - half), max(0, t["col"] - half)
    crop = db[r0:r0 + 2 * half, c0:c0 + 2 * half]
    img = Image.fromarray(((np.clip(crop, -25, 5) + 25) / 30 * 255).astype(np.uint8)).resize((320, 320), Image.NEAREST).convert("RGB")
    d = ImageDraw.Draw(img)
    sx = 320 / (2 * half)
    for c, col in [(t, (163, 22, 95))] + [(p, (240, 240, 240)) for p in r["partners"]]:
        x, y = (c["col"] - c0) * sx, (c["row"] - r0) * sx
        d.ellipse([x - 12, y - 12, x + 12, y + 12], outline=col, width=2)
    img.save(path)


def queue():
    rows = matching.load()["rows"]
    cands = pairs(rows)
    QUEUE.mkdir(parents=True, exist_ok=True)
    with open(REVIEW, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "imo", "date", "scene", "top_posterior", "reason", "partners", "sep_m", "width_m", "label", "note"])
        for i, r in enumerate(cands):
            cid = f"sts{i:03d}"
            render(r, QUEUE / f"{cid}.png")
            sep = min((10.0 * math.hypot(p["row"] - r["top"]["row"], p["col"] - r["top"]["col"]) for p in r["partners"]),
                      default=0.0)
            w.writerow([cid, r["imo"], r["date"], r["scene"], f"{r['top']['posterior']:.2f}", r["reason"], len(r["partners"]), f"{sep:.0f}",
                        f"{r['main']['width_m']:.0f}", "", ""])
    (QUEUE / "candidates.json").write_text(json.dumps(cands, default=float))
    print(f"{len(cands)} side-by-side candidates from {len(rows)} observations -> {QUEUE}")


def summary():
    labels = list(csv.DictReader(open(REVIEW)))
    reviewed = [r for r in labels if r["label"]]
    counts = {}
    for r in reviewed:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    out = {"candidates": len(labels), "reviewed": len(reviewed), "labels": counts,
           "reviewer": "Claude (AI model) viewing 10 m Sentinel-1 crops; not an expert analyst",
           "rule": f"a second bright hull within {PAIR_M:.0f} m of our matched tanker, or one target at least {WIDE_M:.0f} m wide, at 10 m resolution",
           "wording": "possible side-by-side activity; not evidence that cargo moved",
           "by_rule": {rule: {"reviewed": sum(1 for r in reviewed if r["reason"] == rule),
                              "side_by_side": sum(1 for r in reviewed if r["reason"] == rule and r["label"] == "side_by_side"),
                              "candidates": sum(1 for r in labels if r["reason"] == rule)}
                       for rule in ("two_targets", "wide_target")},
           "sampling": "all two-target candidates and a random 60 of the wide-target candidates were reviewed"}
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["queue", "summary"])
    queue() if ap.parse_args().cmd == "queue" else summary()
