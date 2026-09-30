"""Build the detector dataset: Sentinel-1 chips labelled from GFW SAR detections.

Positives: a chip centred on a GFW detection cell, cut from the Sentinel-1
scene acquired that day over that point. Our 300 vessels' matched detections
are always included; other matched and unmatched detections are sampled.

Negatives: chips at random points in the same scene and corridor, at least
2 km from every GFW detection that day, and over open water (median VV below
-13 dB, which excludes land and most port clutter).

Known label noise, stated in the model card: GFW misses some small vessels
(so a negative can contain one), and a detection cell is ~1 km, so a positive
chip is centred on the cell, not the hull.

Every chip records its scene id; train/val/test are split by scene.

Usage: python -m ml.dataset [--pos 2500] [--neg 2500] [--workers 8]
"""

import argparse
import hashlib
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from ml import CACHE, SNAPSHOT, gfw_sar, s1

CHIPS = CACHE / "chips"
INDEX = CACHE / "chips.csv"
WATER_DB = -13.0
MIN_SEP_KM = 2.0


def split_of(scene_id):
    h = int(hashlib.sha1(scene_id.encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else "val" if h < 85 else "test"


def km(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111.2
    dx = (lon2 - lon1) * 111.2 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def quarter_of(date, window):
    for start, end in gfw_sar.quarters(window["start"], window["end"]):
        if start <= date <= end:
            return start, end
    return None


def plan(det, cors, window, n_pos, n_neg, seed=7):
    rng = random.Random(seed)
    ours = {v["imo"] for v in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["vessels"]}
    det = det.copy()
    det["ours"] = det.imo.isin(ours)
    bbox = {c["id"]: c["bbox"] for c in cors}

    # Positives: all of ours, then half matched / half unmatched from the rest.
    pos = [det[det.ours]]
    rest = det[~det.ours]
    k = max(0, n_pos - len(pos[0]))
    for part, frac in ((rest[rest.matched], 0.5), (rest[~rest.matched], 0.5)):
        pos.append(part.sample(min(len(part), int(k * frac)), random_state=seed))
    pos = pd.concat(pos).drop_duplicates(["date", "lat", "lon"])

    jobs = []
    scene_cache = {}
    by_day = {key: g for key, g in det.groupby(["corridor", "date"])}
    for r in pos.itertuples():
        q = quarter_of(r.date, window)
        if not q:
            continue
        key = (r.corridor, q)
        if key not in scene_cache:
            scene_cache[key] = s1.scenes(r.corridor, bbox[r.corridor], *q)
        sc = s1.scene_for(scene_cache[key], r.lat, r.lon, r.date)
        if sc:
            jobs.append({"label": 1, "lat": r.lat, "lon": r.lon, "date": r.date, "corridor": r.corridor,
                         "matched": r.matched, "imo": r.imo, "ours": r.ours, "scene": sc})

    # Negatives: random open-water points in scenes that already hold positives.
    pos_scenes = list({(j["corridor"], j["scene"]["id"]): j for j in jobs}.values())
    per_scene = max(1, math.ceil(n_neg / max(1, len(pos_scenes))))
    for j in pos_scenes:
        w, s, e, n = bbox[j["corridor"]]
        day = by_day.get((j["corridor"], j["date"]))
        pts = list(zip(day.lat, day.lon)) if day is not None else []
        made, tries = 0, 0
        while made < per_scene and tries < per_scene * 20:
            tries += 1
            lat, lon = rng.uniform(s, n), rng.uniform(w, e)
            if not j["scene"]["footprint"].contains(s1.Point(lon, lat)):
                continue
            if any(km(lat, lon, a, b) < MIN_SEP_KM for a, b in pts):
                continue
            jobs.append({"label": 0, "lat": lat, "lon": lon, "date": j["date"], "corridor": j["corridor"],
                         "matched": False, "imo": "", "ours": False, "scene": j["scene"]})
            made += 1
    return jobs


def fetch(job):
    name = hashlib.sha1(f"{job['scene']['id']}|{job['lat']:.4f}|{job['lon']:.4f}".encode()).hexdigest()[:16]
    path = CHIPS / f"{name}.npz"
    if not path.exists():
        got = s1.read_chip(job["scene"], job["lat"], job["lon"])
        if got is None:
            return None
        chip, meta = got
        np.savez_compressed(path, chip=chip.astype(np.float16), meta=json.dumps(meta))
    with np.load(path) as z:
        vv_db = s1.to_db(z["chip"].astype(np.float32))[0]
    water = float(np.median(vv_db)) < WATER_DB
    if job["label"] == 0 and not water:
        return None  # land or port clutter: not an open-water negative
    return {"chip": name, "label": job["label"], "lat": job["lat"], "lon": job["lon"], "date": job["date"],
            "corridor": job["corridor"], "matched": job["matched"], "imo": job["imo"], "ours": job["ours"],
            "scene": job["scene"]["id"], "scene_time": job["scene"]["datetime"], "water": water,
            "split": split_of(job["scene"]["id"])}


def build(n_pos=2500, n_neg=2500, workers=8):
    det = gfw_sar.load()
    cors = json.loads((CACHE / "corridors.json").read_text())
    window = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["window"]
    jobs = plan(det, cors, window, n_pos, n_neg)
    print(f"{len(jobs):,} chips planned ({sum(j['label'] for j in jobs):,} positive)")
    CHIPS.mkdir(parents=True, exist_ok=True)
    rows, done = [], 0
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(fetch, j) for j in jobs]
        for f in as_completed(futs):
            done += 1
            try:
                r = f.result()
            except Exception as err:  # a failed read drops one chip, not the run
                r = None
                print("  read failed:", str(err)[:120])
            if r:
                rows.append(r)
            if done % 250 == 0:
                print(f"  {done:,}/{len(jobs):,}")
    idx = pd.DataFrame(rows)
    idx.to_csv(INDEX, index=False)
    print(idx.groupby(["split", "label"]).size().to_string())
    return idx


def load():
    return pd.read_csv(INDEX, dtype={"imo": str}, keep_default_na=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", type=int, default=2500)
    ap.add_argument("--neg", type=int, default=2500)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    build(a.pos, a.neg, a.workers)
