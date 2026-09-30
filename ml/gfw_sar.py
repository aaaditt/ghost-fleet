"""Stage 1: Global Fishing Watch SAR vessel detections for the snapshot's corridors.

Corridors are the 1-degree cells holding the most positioned snapshot events
(the areas where these tankers actually spend time). For each corridor we pull
GFW's `public-global-sar-presence` report grouped by vessel, one quarter at a
time, and keep one row per detection-cell-day:

    date, lat, lon, detections, matched, imo, vessel_id, ship_name, flag, geartype, corridor

`matched` means GFW associated the radar detection with an AIS-broadcasting
vessel. Unmatched means no AIS match was found; it is not proof that a vessel
disabled AIS. Positions are GFW's 0.01-degree cell centres (about 1 km).

Usage: python -m ml.gfw_sar [--cells 24] [--offline]
Raw responses are cached in .cache/ml/gfw_sar/ (git-ignored).
"""

import argparse
import datetime
import gzip
import hashlib
import json
import math
import os
import time
from collections import Counter, defaultdict

import pandas as pd
import requests

from ml import CACHE, SNAPSHOT

DATASET = "public-global-sar-presence:latest"
REPORT_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
RAW = CACHE / "gfw_sar"
OUT = CACHE / "sar_detections.csv.gz"


def load_snapshot():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def corridors(snapshot, n_cells=24):
    """Top 1-degree cells by positioned events. Returns [{id, bbox, events, vessels}]."""
    events, vessels = Counter(), defaultdict(set)
    for v in snapshot["vessels"]:
        for e in v["events"]:
            if e.get("lat") is None or e.get("lon") is None:
                continue
            cell = (math.floor(e["lat"]), math.floor(e["lon"]))
            events[cell] += 1
            vessels[cell].add(v["imo"])
    out = []
    for (lat, lon), n in events.most_common(n_cells):
        out.append({
            "id": f"{lat:+03d}{lon:+04d}",
            "bbox": [lon, lat, lon + 1, lat + 1],  # west, south, east, north
            "events": n,
            "vessels": len(vessels[(lat, lon)]),
        })
    return out


def quarters(start, end):
    s = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    while s <= e:
        q_end = min(e, (pd.Timestamp(s) + pd.offsets.QuarterEnd(0)).date())
        yield s.isoformat(), q_end.isoformat()
        s = q_end + datetime.timedelta(days=1)


def fetch(bbox, start, end, offline=False):
    w, s, e, n = bbox
    params = {
        "spatial-resolution": "HIGH", "temporal-resolution": "DAILY",
        "datasets[0]": DATASET, "date-range": f"{start},{end}",
        "format": "JSON", "group-by": "VESSEL_ID", "spatial-aggregation": "false",
    }
    body = {"geojson": {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}}
    key = hashlib.sha1(json.dumps([params, body], sort_keys=True).encode()).hexdigest()[:20]
    path = RAW / f"{key}.json.gz"
    if path.exists():
        return json.loads(gzip.decompress(path.read_bytes()))
    if offline:
        return None
    token = os.environ.get("GFW_API_TOKEN")
    if not token:
        raise SystemExit("GFW_API_TOKEN is not set (or pass --offline to use the cache).")
    for attempt in range(5):
        r = requests.post(REPORT_URL, params=params, json=body, timeout=300,
                          headers={"Authorization": f"Bearer {token}"})
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(json.dumps(data).encode()))
        return data
    r.raise_for_status()


def rows_from(data, corridor_id):
    for entry in data.get("entries", []):
        for rows in entry.values():
            for x in rows or []:
                yield {
                    "date": x["date"],
                    "lat": round(float(x["lat"]), 3),
                    "lon": round(float(x["lon"]), 3),
                    "detections": int(x.get("detections") or 1),
                    "matched": bool(x.get("vesselId")),
                    "imo": x.get("imo") or "",
                    "vessel_id": x.get("vesselId") or "",
                    "ship_name": x.get("shipName") or "",
                    "flag": x.get("flag") or "",
                    "geartype": x.get("geartype") or "",
                    "corridor": corridor_id,
                }


def build(n_cells=24, offline=False):
    snap = load_snapshot()
    cors = corridors(snap, n_cells)
    frames = []
    for c in cors:
        for start, end in quarters(snap["window"]["start"], snap["window"]["end"]):
            data = fetch(c["bbox"], start, end, offline)
            if data is None:
                print(f"  {c['id']} {start}: not cached, skipped")
                continue
            df = pd.DataFrame(rows_from(data, c["id"]))
            frames.append(df)
            print(f"  {c['id']} {start}..{end}: {len(df):,} rows")
    det = pd.concat(frames, ignore_index=True)
    # A cell on a corridor edge can appear in two queries; keep one copy.
    det = det.drop_duplicates(["date", "lat", "lon", "vessel_id", "matched"])
    CACHE.mkdir(parents=True, exist_ok=True)
    det.to_csv(OUT, index=False, compression="gzip")
    (CACHE / "corridors.json").write_text(json.dumps(cors, indent=1))
    ours = det[det.imo.isin({v["imo"] for v in snap["vessels"]})]
    print(f"{len(det):,} detection rows; matched {det.matched.mean():.0%}; "
          f"{ours.imo.nunique()} of our vessels detected ({len(ours):,} rows)")
    return det


def load():
    return pd.read_csv(OUT, dtype={"imo": str, "vessel_id": str}, keep_default_na=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=int, default=24)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    build(a.cells, a.offline)
