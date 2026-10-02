"""Write dashboard/data/sar.json and radar thumbnails from the research outputs.

Per vessel (only what the evidence supports):
  radar          GFW Sentinel-1 detections matched to this IMO in the studied corridors
  studied        whether any of the vessel's loitering events fell in a corridor
  our_match      best observation where OUR detector + matcher found the vessel,
                 with posterior, GFW agreement, and a thumbnail
  nearby         unmatched GFW radar targets within 2 km of that match (same day)
  side_by_side   reviewed side-by-side candidates (possible, never "transfer")
  cargo          experimental estimate only if the cargo gate passed; else null

Also copies the model reports (metrics, references, gates) under "models".

Usage: python -m ml.build
"""

import csv
import datetime
import json

import numpy as np
from PIL import Image, ImageDraw

from ml import CACHE, ROOT, SNAPSHOT, gfw_sar, matching, s1, sts

OUT = ROOT / "dashboard" / "data" / "sar.json"
MEDIA = ROOT / "dashboard" / "media" / "sar"
PASSES = MEDIA / "passes"
PASSES_OUT = ROOT / "dashboard" / "data" / "radar_passes.json"
REPORTS = CACHE / "reports"


def snap(db, cand):
    """The heatmap is 40 m coarse: snap the target to the brightest pixel within 80 m of its peak."""
    t = dict(cand)
    y0, x0 = max(0, t["row"] - 8), max(0, t["col"] - 8)
    win = db[y0:t["row"] + 9, x0:t["col"] + 9]
    dy, dx = np.unravel_index(int(np.argmax(win)), win.shape)
    t["row"], t["col"] = y0 + int(dy), x0 + int(dx)
    return t


def thumb(row, path, half=48):
    with np.load(matching.CHIPS / f"{row['chip']}.npz") as z:
        db = s1.to_db(z["chip"].astype(np.float32))[0]
    t = snap(db, row["candidates"][0])
    r0 = min(max(0, t["row"] - half), db.shape[0] - 2 * half)
    c0 = min(max(0, t["col"] - half), db.shape[1] - 2 * half)
    crop = db[r0:r0 + 2 * half, c0:c0 + 2 * half]
    img = Image.fromarray(((np.clip(crop, -25, 5) + 25) / 30 * 255).astype(np.uint8))
    img = img.resize((288, 288), Image.LANCZOS).convert("RGB")
    d = ImageDraw.Draw(img)
    s = 288 / (2 * half)
    x, y = (t["col"] - c0 + 0.5) * s, (t["row"] - r0 + 0.5) * s
    d.ellipse([x - 22, y - 22, x + 22, y + 22], outline=(163, 22, 95), width=3)
    # 500 m scale bar, bottom left
    bar = 50 * s
    d.line([12, 272, 12 + bar, 272], fill=(248, 250, 250), width=3)
    d.text((12, 254), "500 m", fill=(248, 250, 250))
    MEDIA.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=80, optimize=True, progressive=True)


def corners(meta, shape):
    """Outer pixel edges of a chip as [lon, lat], clockwise from top-left (MapLibre image-source order)."""
    h, w = shape
    return [[round(lon, 6), round(lat, 6)]
            for lat, lon in (s1.pixel_to_lonlat(meta, r, c) for r, c in ((-.5, -.5), (-.5, w - .5), (h - .5, w - .5), (h - .5, -.5)))]


def overlay(row, path):
    """Full matching chip as a plain greyscale radar image, for draping on the map at its true position.

    No ring is burned in: the dashboard draws the matched target itself.
    Returns the chip's corners and the snapped target position."""
    with np.load(matching.CHIPS / f"{row['chip']}.npz") as z:
        db = s1.to_db(z["chip"].astype(np.float32))[0]
        meta = json.loads(str(z["meta"]))
    img = Image.fromarray(((np.clip(db, -25, 5) + 25) / 30 * 255).astype(np.uint8))
    PASSES.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=78, optimize=True, progressive=True)
    t = snap(db, row["candidates"][0])
    lat, lon = s1.pixel_to_lonlat(meta, t["row"], t["col"])
    return corners(meta, db.shape), (round(lat, 5), round(lon, 5))


def passes_for(rows, imo):
    """Every radar pass where our detector found a candidate near the vessel's loitering event."""
    out = []
    for i, r in enumerate(sorted(rows, key=lambda r: (r["date"], r["scene_time"]))):
        t = r["candidates"][0]
        name = f"{imo}_{i:02d}.jpg"
        box, (lat, lon) = overlay(r, PASSES / name)
        out.append({
            "date": r["date"], "time": r["scene_time"][11:16], "scene": r["scene"],
            "image": f"media/sar/passes/{name}", "corners": box,
            "target": {"lat": lat, "lon": lon, "posterior": round(t["posterior"], 2),
                       "detector_p": round(t["p"], 2), "offset_m": round(t["dist_m"])},
            "event": {"lat": r["event_lat"], "lon": r["event_lon"]},
            "gfw_agrees": r["top_hits_gfw"], "confident": t["posterior"] >= 0.8,
        })
    return out


def read_json(name):
    p = REPORTS / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def build():
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    det = gfw_sar.load()
    cors = json.loads((CACHE / "corridors.json").read_text())
    mrows = matching.load()["rows"]

    reviewed = {}
    if sts.REVIEW.exists():
        for r in csv.DictReader(open(sts.REVIEW)):
            if r["label"]:
                reviewed.setdefault(r["imo"], []).append({"date": r["date"], "label": r["label"], "id": r["id"],
                                                           "sep_m": float(r["sep_m"]), "posterior": float(r["top_posterior"])})
    cargo = read_json("cargo")
    cargo_ok = bool(cargo and cargo.get("gate_passed"))

    studied = {r["imo"] for r in mrows}
    for f in list(MEDIA.glob("*.png")) + list(MEDIA.glob("*.jpg")) + list(PASSES.glob("*.jpg")):
        f.unlink()
    vessels = {}
    passes = {}
    for v in snap["vessels"]:
        imo = v["imo"]
        mine = det[(det.imo == imo) & det.matched].sort_values("date")
        rec = {"studied": imo in studied or len(mine) > 0,
               "radar": {"detections": int(mine.detections.sum()), "days": int(mine.date.nunique()),
                         "first": mine.date.min() if len(mine) else None,
                         "last": mine.date.max() if len(mine) else None,
                         "points": [[r.date, r.lat, r.lon] for r in mine.drop_duplicates("date").itertuples()][:40]}}
        rows = [r for r in mrows if r["imo"] == imo and r["candidates"]]
        if rows:
            passes[imo] = passes_for(rows, imo)
        # Show a confident match GFW independently confirms, where one exists.
        best = max(rows, key=lambda r: (r["candidates"][0]["posterior"] >= 0.5, r["candidates"][0]["posterior"] >= 0.8, r["top_hits_gfw"] is True,
                                        r["candidates"][0]["posterior"], r["date"]), default=None)
        if best and best["candidates"][0]["posterior"] >= 0.5:
            t = best["candidates"][0]
            name = f"{imo}.jpg"
            thumb(best, MEDIA / name)
            rec["our_match"] = {
                "date": best["date"], "time": best["scene_time"][11:16], "scene": best["scene"],
                "posterior": round(t["posterior"], 2), "detector_p": round(t["p"], 2),
                "offset_m": round(t["dist_m"]), "lat": round(t["lat"], 4), "lon": round(t["lon"], 4),
                "gfw_agrees": best["top_hits_gfw"], "image": f"media/sar/{name}",
                "observations": len(rows),
                "confident": sum(1 for r in rows if r["candidates"][0]["posterior"] >= 0.8),
                "pass": next(i for i, p in enumerate(passes[imo]) if p["scene"] == best["scene"]
                             and p["target"]["posterior"] == round(t["posterior"], 2)),
            }
            rec["nearby"] = {"unmatched_targets": len(best["unmatched_nearby"]), "radius_km": 2.0, "date": best["date"]}
        if imo in reviewed:
            rec["side_by_side"] = reviewed[imo]
        rec["cargo"] = None
        if cargo_ok:
            pass  # filled only if the gate passes; see ml/cargo.py
        vessels[imo] = rec

    out = {
        "generated": datetime.date.today().isoformat(),
        "window": snap["window"],
        "sources": {
            "detections": "Global Fishing Watch public-global-sar-presence (Sentinel-1), non-commercial use",
            "imagery": "Copernicus Sentinel-1 RTC via Microsoft Planetary Computer",
        },
        "coverage": {"corridors": [{"id": c["id"], "bbox": c["bbox"]} for c in cors],
                     "note": "Radar evidence covers only these 1-degree corridors, and only when Sentinel-1 imaged them."},
        "models": {k: read_json(k) for k in ("detector", "matching_summary", "sts", "cargo_summary", "xview3")},
        "vessels": vessels,
    }
    m = read_json("matching")
    out["models"]["matching_summary"] = m["summary"] if m else None
    out["models"]["detector_review"] = read_json("detector_review")
    if cargo:
        out["models"]["cargo_summary"] = {k: v for k, v in cargo.items() if k != "rows"}
    OUT.write_text(json.dumps(out, separators=(",", ":"), default=float))
    PASSES_OUT.write_text(json.dumps({
        "generated": out["generated"], "imagery": out["sources"]["imagery"],
        "note": "Sentinel-1 VV backscatter, 10 m pixels, about 3.2 km across. Targets are model estimates, not proof.",
        "vessels": passes}, separators=(",", ":"), default=float))
    print(f"radar_passes.json: {PASSES_OUT.stat().st_size / 1024:.0f} KB; "
          f"{sum(map(len, passes.values()))} passes for {len(passes)} vessels")
    n =sum(1 for x in vessels.values() if x["radar"]["detections"])
    print(f"sar.json: {OUT.stat().st_size / 1024:.0f} KB; {n} vessels with GFW radar detections; "
          f"{sum(1 for x in vessels.values() if 'our_match' in x)} with our image match")
    return out


if __name__ == "__main__":
    build()
