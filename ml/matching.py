"""Stage 3: associate our vessels' loitering events with targets in Sentinel-1 scenes.

For each (vessel, loitering event, scene) where the scene was acquired during
the event and covers its position, read a 3.2 km chip centred on the event
position and run our CNN. Heatmap peaks (after non-maximum suppression) are
the candidate targets. The posterior that candidate i is our vessel is

    w_i = p_i * N(d_i; sigma)        (detector confidence x distance likelihood)
    w_none = (1 - p_detect) * clutter  (vessel not seen / drifted out of the chip)
    P(i) = w_i / (sum_j w_j + w_none)

sigma reflects loitering drift and the event's position being a summary.
GFW's detections are *not* used to make the match. They are the reference:
if GFW matched a detection to this vessel's IMO on that day, we check whether
our top candidate lies within 1.2 km of it.

Unmatched GFW detections within 2 km of our matched target on the same day are
listed as "other radar targets nearby": context for review, never an identity.

Usage: python -m ml.matching [--max-per-event 2] [--workers 8]
"""

import argparse
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import torch
import torch.nn.functional as F

from ml import CACHE, SNAPSHOT, detector, gfw_sar, s1
from ml.dataset import km

CHIP = 320            # 3.2 km
SIGMA_M = 700.0       # loitering drift + event-position summary
P_DETECT = 0.85       # prior that a large tanker in the chip shows up as a target
CLUTTER = 0.02        # density-like constant for the "none" hypothesis
NMS_PX = 8            # 80 m: peaks closer than this are one target (heatmap is 1/4 res)
MIN_P = 0.2
OUT = CACHE / "reports" / "matching.json"
CHIPS = CACHE / "match_chips"


def triples(snapshot, cors, max_per_event):
    bbox = {c["id"]: c["bbox"] for c in cors}

    def corridor_of(lat, lon):
        for cid, (w, s, e, n) in bbox.items():
            if w <= lon < e and s <= lat < n:
                return cid
        return None

    window = snapshot["window"]
    cache = {}
    out = []
    for v in snapshot["vessels"]:
        for idx, e in enumerate(v["events"]):
            if e["kind"] != "loitering" or e.get("lat") is None:
                continue
            cid = corridor_of(e["lat"], e["lon"])
            if not cid:
                continue
            start, end = max(e["start"][:10], window["start"]), min((e["end"] or e["start"])[:10], window["end"])
            picked = []
            for qs, qe in gfw_sar.quarters(window["start"], window["end"]):
                if qe < start or qs > end:
                    continue
                key = (cid, qs, qe)
                if key not in cache:
                    cache[key] = s1.scenes(cid, bbox[cid], qs, qe)
                p = s1.Point(e["lon"], e["lat"])
                picked += [sc for sc in cache[key] if start <= sc["date"] <= end and sc["footprint"].contains(p)
                           and e["start"] <= sc["datetime"][:16] <= (e["end"] or e["start"])]
            # Spread picks across the event rather than taking the first few.
            picked.sort(key=lambda s: s["datetime"])
            if len(picked) > max_per_event:
                step = len(picked) / max_per_event
                picked = [picked[int(i * step)] for i in range(max_per_event)]
            for sc in picked:
                out.append({"imo": v["imo"], "event": idx, "lat": e["lat"], "lon": e["lon"], "corridor": cid,
                            "scene": sc, "date": sc["date"]})
    return out


def candidates(net, chip, meta):
    x = torch.from_numpy(detector.normalise(chip))[None]
    with torch.no_grad():
        h = torch.sigmoid(net.heatmap(x))[0]
    pooled = F.max_pool2d(h[None, None], NMS_PX // 2 * 2 + 1, stride=1, padding=NMS_PX // 2)[0, 0]
    rr, cc = torch.nonzero((h == pooled) & (h >= MIN_P), as_tuple=True)
    out = []
    for r, c in zip(rr.tolist(), cc.tolist()):
        row, col = r * 4 + 2, c * 4 + 2
        lat, lon = s1.pixel_to_lonlat(meta, row, col)
        d = 10.0 * math.hypot(row - CHIP / 2, col - CHIP / 2)
        out.append({"p": float(h[r, c]), "row": row, "col": col, "lat": lat, "lon": lon, "dist_m": d})
    return out


def posterior(cands):
    w = [c["p"] * math.exp(-0.5 * (c["dist_m"] / SIGMA_M) ** 2) for c in cands]
    w_none = (1 - P_DETECT) + CLUTTER
    total = sum(w) + w_none
    for c, wi in zip(cands, w):
        c["posterior"] = wi / total
    return w_none / total


def process(net, t):
    got = s1.read_chip(t["scene"], t["lat"], t["lon"], size=CHIP)
    if got is None:
        return None
    chip, meta = got
    cands = candidates(net, chip, meta)
    p_none = posterior(cands)
    cands.sort(key=lambda c: -c["posterior"])
    CHIPS.mkdir(parents=True, exist_ok=True)
    name = f"{t['imo']}_{t['scene']['id'][:40]}"
    np.savez_compressed(CHIPS / f"{name}.npz", chip=chip.astype(np.float16), meta=json.dumps(meta))
    return {"imo": t["imo"], "event": t["event"], "date": t["date"], "scene": t["scene"]["id"],
            "scene_time": t["scene"]["datetime"], "corridor": t["corridor"], "event_lat": t["lat"],
            "event_lon": t["lon"], "p_none": p_none, "candidates": cands[:6], "chip": name}


def reference(results, det):
    """Compare our top candidate with GFW's own match for the same IMO and day."""
    by = {k: g for k, g in det[det.matched].groupby(["imo", "date"])}
    unmatched = {k: g for k, g in det[~det.matched].groupby("date")}
    rows = []
    for r in results:
        g = by.get((r["imo"], r["date"]))
        top = r["candidates"][0] if r["candidates"] else None
        ref = None
        if g is not None:
            dists = [km(a, b, r["event_lat"], r["event_lon"]) for a, b in zip(g.lat, g.lon)]
            j = int(np.argmin(dists))
            ref = (float(g.lat.iloc[j]), float(g.lon.iloc[j]))
        hit = None
        if ref and top:
            hit = km(top["lat"], top["lon"], *ref) <= 1.2
        near = []
        if top and top["posterior"] >= 0.5:
            u = unmatched.get(r["date"])
            if u is not None:
                near = [(float(a), float(b)) for a, b in zip(u.lat, u.lon) if km(a, b, top["lat"], top["lon"]) <= 2.0]
        rows.append({**r, "gfw_match": ref, "top_hits_gfw": hit, "unmatched_nearby": near})
    return rows


def summarise(rows):
    with_ref = [r for r in rows if r["gfw_match"]]
    scored = [r for r in with_ref if r["candidates"]]
    conf = [r["candidates"][0]["posterior"] for r in scored]
    hits = [bool(r["top_hits_gfw"]) for r in scored]
    bins = []
    for lo, hi in ((0, .5), (.5, .8), (.8, 1.01)):
        sel = [h for c, h in zip(conf, hits) if lo <= c < hi]
        bins.append({"posterior": f"{lo:.1f}-{min(hi, 1):.1f}", "n": len(sel),
                     "agreement_with_gfw": (sum(sel) / len(sel)) if sel else None})
    return {
        "reference": "GFW's own AIS match for the same IMO and day (agreement, not ground truth)",
        "observations": len(rows),
        "vessels": len({r["imo"] for r in rows}),
        "with_gfw_match": len(with_ref),
        "top_candidate_agrees_within_1_2km": (sum(hits) / len(hits)) if hits else None,
        "no_candidate_found": sum(1 for r in with_ref if not r["candidates"]),
        "reliability": bins,
        "without_gfw_match": len(rows) - len(with_ref),
        "without_gfw_match_confident_target": sum(1 for r in rows if not r["gfw_match"] and r["candidates"]
                                                  and r["candidates"][0]["posterior"] >= 0.8),
        "params": {"chip_m": CHIP * 10, "sigma_m": SIGMA_M, "p_detect": P_DETECT, "min_peak": MIN_P},
    }


def run(max_per_event=2, workers=8):
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    cors = json.loads((CACHE / "corridors.json").read_text())
    ts = triples(snap, cors, max_per_event)
    print(f"{len(ts):,} vessel-scene observations to process")
    net = detector.load_model("cpu")
    results = []
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(process, net, t) for t in ts]
        for i, f in enumerate(as_completed(futs), 1):
            try:
                r = f.result()
            except Exception as err:
                r = None
                print("  failed:", str(err)[:120])
            if r:
                results.append(r)
            if i % 100 == 0:
                print(f"  {i}/{len(ts)}")
    rows = reference(results, gfw_sar.load())
    summary = summarise(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, default=float))
    print(json.dumps(summary, indent=1))
    return rows, summary


def load():
    return json.loads(OUT.read_text())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-event", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    run(a.max_per_event, a.workers)
