"""
Ghost Fleet — Hidden Supply Monitor pipeline
============================================
Builds a dated, evidence-backed snapshot of sanctioned tanker activity for
commodity and energy traders.

  1. OpenSanctions maritime CSV  -> sanctioned / sanctions-linked vessels (IMO, name)
  2. Global Fishing Watch v3 API -> AIS identity history, AIS gaps, loitering,
                                    port visits and encounters (with dates + positions)
  3. Estimation layer            -> transparent risk score, capacity and value ranges,
                                    monthly activity trend for the trader view

Every output is a directional estimate, not proof of wrongdoing.

BEFORE RUNNING:
  1. python -m pip install -r requirements.txt
  2. Get a free GFW API token: https://globalfishingwatch.org/our-apis/tokens
     and set it:  $env:GFW_API_TOKEN = "..."
  3. Download the OpenSanctions maritime export
     (https://www.opensanctions.org/datasets/maritime/) and save it as maritime.csv

Usage:
  python dark_fleet_pipeline.py [--max 300] [--start 2025-10-01] [--end 2026-09-29]

Raw API responses are cached under .cache/gfw/ so reruns are fast and offline-safe.

LICENSING (state this in the pitch):
  - GFW APIs: non-commercial use; attribution required.
  - OpenSanctions bulk data: CC BY-NC 4.0; businesses need a data licence.
"""

import argparse
import datetime
import hashlib
import json
import math
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GFW_TOKEN = os.environ.get("GFW_API_TOKEN", "")
GFW_BASE = "https://gateway.api.globalfishingwatch.org/v3"
HEADERS = {"Authorization": f"Bearer {GFW_TOKEN}"}
CACHE_DIR = Path(".cache/gfw")

MARITIME_CSV_PATH = "maritime.csv"
DASHBOARD_DATA_DIR = Path("dashboard/data")

# Brent crude reference price (USD/barrel). Static and configured — update on
# demo day. Used only for rough value ranges.
BRENT_CRUDE_USD_PER_BARREL = 78.50

MAX_VESSELS = 300  # matches the committed snapshot; a bare run must not shrink it
# Events kept per vessel in the dashboard file. Aggregates use every event.
EVENTS_PER_VESSEL = 30

EVENT_DATASETS = {
    "gap": "public-global-gaps-events:latest",
    "loitering": "public-global-loitering-events:latest",
    "port_visit": "public-global-port-visits-events:latest",
    "encounter": "public-global-encounters-events:latest",
}

# OpenSanctions risk tags: "mare.shadow" marks its shadow-fleet list,
# "sanction" marks a vessel named on at least one sanctions programme.
SHADOW_TAG = "mare.shadow"
SANCTION_TAG = "sanction"


# ---------------------------------------------------------------------------
# GFW HTTP with on-disk cache
# ---------------------------------------------------------------------------
def gfw_get(path: str, params: dict, offline: bool = False) -> dict | None:
    """GET a GFW endpoint, caching the JSON body by URL + params."""
    key = hashlib.sha1(json.dumps([path, params], sort_keys=True).encode()).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    if offline:
        return None
    if not GFW_TOKEN:
        raise SystemExit("GFW_API_TOKEN is not set (see the header of this file).")

    for attempt in range(4):
        r = requests.get(f"{GFW_BASE}/{path}", headers=HEADERS, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(2 ** attempt * 5)
            continue
        if r.status_code != 200:
            print(f"  ! GFW {path} -> HTTP {r.status_code}: {r.text[:160]}")
            return None
        body = r.json()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(body), encoding="utf-8")
        return body
    print(f"  ! GFW {path} -> rate limited, giving up")
    return None


# ---------------------------------------------------------------------------
# Step 1: Load sanctioned / sanctions-linked vessels
# ---------------------------------------------------------------------------
def load_sanctioned_vessels(csv_path: str, max_rows: int = MAX_VESSELS) -> pd.DataFrame:
    """Shadow-fleet vessels from the OpenSanctions maritime export, most-listed first.

    The export has one row per source entity, so a ship named by several lists
    appears several times. Rows are merged by IMO before filtering."""
    df = pd.read_csv(csv_path, low_memory=False)
    rows = df[(df["type"] == "VESSEL") & df["imo"].notna()].copy()
    rows["imo"] = (rows["imo"].astype(str).str.split(";").str[0]
                   .str.replace("IMO", "", regex=False).str.strip())

    def union(values: pd.Series) -> str:
        return ";".join(sorted({t for v in values.dropna() for t in str(v).split(";") if t}))

    shadow_ids = rows.loc[rows["id"].notna() & rows["risk"].fillna("").str.contains(SHADOW_TAG, regex=False)]
    vessels = rows.groupby("imo").agg(
        caption=("caption", "first"),
        flag=("flag", "first"),
        risk=("risk", union),
        datasets=("datasets", union),
    ).reset_index()
    # Link to the shadow-fleet entity page where there is one.
    vessels = vessels.merge(shadow_ids.drop_duplicates("imo")[["imo", "id", "url"]], on="imo", how="left")

    vessels = vessels[vessels["risk"].str.contains(SHADOW_TAG, regex=False)].copy()
    vessels["_sanctioned"] = vessels["risk"].str.contains(SANCTION_TAG, regex=False)
    vessels["_lists"] = vessels["datasets"].str.count(";") + 1
    vessels["_imo_num"] = pd.to_numeric(vessels["imo"], errors="coerce")
    # Rank: sanctioned first, then by how many lists name the vessel, then newer
    # IMO numbers (sea-going tankers rather than old river craft).
    vessels = vessels.sort_values(["_sanctioned", "_lists", "_imo_num"], ascending=False)
    return vessels.head(max_rows)


# ---------------------------------------------------------------------------
# Step 2: Resolve each IMO to a GFW vessel and its identity history
# ---------------------------------------------------------------------------
def gfw_search_vessel(imo: str, offline: bool = False) -> dict | None:
    """Merge every GFW identity that carries this IMO into one record.

    GFW often splits a ship's history across several search entries (one per
    re-flag or MMSI change), so taking only the first entry loses the evasion
    pattern we are looking for. Identities without this IMO are dropped: they
    may be a different ship reusing the same MMSI."""
    body = gfw_get("vessels/search", {
        "query": imo,
        "datasets[0]": "public-global-vessel-identity:latest",
    }, offline)
    merged = {"selfReportedInfo": [], "registryInfo": []}
    for entry in (body or {}).get("entries", []):
        for key in merged:
            merged[key].extend(i for i in entry.get(key, []) if str(i.get("imo") or "") == imo)
    return merged if merged["selfReportedInfo"] or merged["registryInfo"] else None


def normalise_name(name: str | None) -> str | None:
    return "".join(ch for ch in name.upper() if ch.isalnum()) if name else None


def identity_history(vessel_record: dict) -> list[dict]:
    """Every AIS / registry identity the vessel has used, oldest first."""
    rows = []
    for source, key in (("AIS", "selfReportedInfo"), ("Registry", "registryInfo")):
        for info in vessel_record.get(key, []):
            rows.append({
                "source": source,
                "name": info.get("shipname"),
                "flag": info.get("flag"),
                "mmsi": info.get("ssvid"),
                "from": (info.get("transmissionDateFrom") or "")[:10] or None,
                "to": (info.get("transmissionDateTo") or "")[:10] or None,
            })
    return sorted(rows, key=lambda r: r["from"] or "")


def count_identity_changes(vessel_record: dict) -> int:
    """Number of times the vessel switched AIS identity (name, flag or MMSI),
    in time order. One re-flag counts once even if the MMSI changed with it.
    Name / flag hopping is a documented shadow-fleet evasion pattern."""
    ais = [h for h in identity_history(vessel_record) if h["source"] == "AIS"]
    changes = 0
    for prev, cur in zip(ais, ais[1:]):
        if (normalise_name(prev["name"]), prev["flag"], prev["mmsi"]) !=            (normalise_name(cur["name"]), cur["flag"], cur["mmsi"]):
            changes += 1
    return changes


def gfw_vessel_ids(vessel_record: dict) -> list[str]:
    return [i["id"] for i in vessel_record.get("selfReportedInfo", []) if i.get("id")]


def vessel_dimensions(vessel_record: dict) -> tuple[float | None, float | None]:
    """(gross tonnage, length in metres) from registry records, if published."""
    gt = length = None
    for info in vessel_record.get("registryInfo", []):
        gt = gt or info.get("tonnageGt")
        length = length or info.get("lengthM")
    return gt, length


# ---------------------------------------------------------------------------
# Step 3: Behaviour events (AIS gaps, loitering, port visits, encounters)
# ---------------------------------------------------------------------------
def fetch_events(vessel_ids: list[str], kind: str, start: str, end: str,
                 offline: bool = False, page_size: int = 100, max_pages: int = 5) -> list[dict]:
    if not vessel_ids:
        return []
    params: dict[str, str | int] = {f"vessels[{i}]": vid for i, vid in enumerate(vessel_ids)}
    params.update({"datasets[0]": EVENT_DATASETS[kind], "start-date": start,
                   "end-date": end, "limit": page_size})
    events = []
    for page in range(max_pages):
        body = gfw_get("events", {**params, "offset": page * page_size}, offline)
        entries = (body or {}).get("entries", [])
        events.extend(entries)
        if len(entries) < page_size:
            break
    return [compact_event(kind, e) for e in events]


def compact_event(kind: str, e: dict) -> dict:
    """Keep only what the dashboard evidence timeline needs."""
    pos = e.get("position") or {}
    out = {
        "kind": kind,
        "start": (e.get("start") or "")[:16] or None,
        "end": (e.get("end") or "")[:16] or None,
        "lat": pos.get("lat"),
        "lon": pos.get("lon"),
    }
    if kind == "gap":
        g = e.get("gap") or {}
        out["hours"] = g.get("durationHours")
        out["intentional"] = g.get("intentionalDisabling")
    elif kind == "loitering":
        out["hours"] = (e.get("loitering") or {}).get("totalTimeHours")
    elif kind == "port_visit":
        visit = e.get("port_visit") or e.get("portVisit") or {}  # raw API uses port_visit
        anch = visit.get("startAnchorage") or {}
        out["port"] = anch.get("name") or anch.get("topDestination") or anch.get("id")
        out["port_flag"] = anch.get("flag")
    elif kind == "encounter":
        other = ((e.get("encounter") or {}).get("vessel") or {})
        out["partner"] = other.get("name")
        out["partner_flag"] = other.get("flag")
    return out


def latest_position(events: list[dict]) -> tuple[float | None, float | None, str | None]:
    located = [e for e in events if e.get("lat") is not None and e.get("start")]
    if not located:
        return None, None, None
    last = max(located, key=lambda e: e["start"])
    return last["lat"], last["lon"], last["start"]


# ---------------------------------------------------------------------------
# Step 4: Transparent risk score
# ---------------------------------------------------------------------------
def compute_risk_score(sanctioned: bool, identity_changes: int,
                       dark_gaps: int, loitering: int, encounters: int = 0) -> tuple[int, dict]:
    """Additive, capped, explainable. Every vessel here is on a shadow-fleet list
    (+30); a formal sanctions designation adds 10 more. Returns (score, breakdown)."""
    breakdown = {
        "sanctions": 40 if sanctioned else 30,
        "identity": min(identity_changes * 10, 30),
        "ais_gaps": min(dark_gaps * 5, 15),
        # Offshore loitering is common for these tankers (median ~20 events/yr
        # in the 2026-09 snapshot), so 1 point per 4 events; full marks at 60+.
        "meetings": min(loitering // 4 + encounters * 3, 15),
    }
    return min(sum(breakdown.values()), 100), breakdown


# ---------------------------------------------------------------------------
# Step 5: Capacity and value ranges
# ---------------------------------------------------------------------------
BARRELS_PER_TONNE = 7.33
# Tanker deadweight is roughly 1.6-1.9x gross tonnage.
DWT_PER_GT = (1.6, 1.9)
# Fallback by length class (low, high barrels of crude-equivalent cargo).
LENGTH_CLASSES = [
    (300, (1_900_000, 2_200_000), "VLCC"),
    (250, (900_000, 1_100_000), "Suezmax"),
    (220, (600_000, 800_000), "Aframax/LR2"),
    (180, (350_000, 550_000), "Panamax/LR1"),
    (0, (200_000, 350_000), "MR/small tanker"),
]
UNKNOWN_CAPACITY = (300_000, 1_100_000)


def estimate_cargo_barrels(gross_tonnage: float | None, length_m: float | None) -> dict:
    """Capacity range for one full cargo, with the basis used."""
    if gross_tonnage:
        low, high = (int(gross_tonnage * f * BARRELS_PER_TONNE) for f in DWT_PER_GT)
        return {"low": low, "high": high, "basis": f"gross tonnage {int(gross_tonnage):,} GT"}
    if length_m:
        for min_len, rng, label in LENGTH_CLASSES:
            if length_m >= min_len:
                return {"low": rng[0], "high": rng[1], "basis": f"length {length_m:.0f} m ({label})"}
    return {"low": UNKNOWN_CAPACITY[0], "high": UNKNOWN_CAPACITY[1], "basis": "no size data (wide default range)"}


def estimate_cargo_value_usd(barrels: int, price_per_barrel: float = BRENT_CRUDE_USD_PER_BARREL) -> float:
    return barrels * price_per_barrel


def estimate_annual_voyages(port_visits: int, window_days: int) -> tuple[float, float]:
    """Loaded voyages per year: about half of port calls are loading calls.
    With no observed calls, assume 4-8 voyages a year."""
    if port_visits <= 0 or window_days <= 0:
        return 4.0, 8.0
    per_year = (port_visits / 2) * 365 / window_days
    per_year = min(max(per_year, 2.0), 12.0)
    return round(per_year * 0.7, 1), round(per_year * 1.3, 1)


# ---------------------------------------------------------------------------
# Step 6: Cargo state (heuristic, draft-based)
# ---------------------------------------------------------------------------
# A loaded tanker sits deeper in the water. This rule-based classifier uses
# published draft thresholds. It is NOT a trained model. The public GFW
# identity data carries no draft, so for this snapshot it will usually and
# honestly return UNKNOWN.
VESSEL_DRAFT_THRESHOLDS = {
    "crude_oil_tanker":      {"loaded_min": 18.0, "ballast_max": 10.0, "max_draft": 22.5},
    "oil_tanker":            {"loaded_min": 14.0, "ballast_max": 8.0,  "max_draft": 17.0},
    "product_tanker":        {"loaded_min": 10.0, "ballast_max": 6.0,  "max_draft": 13.0},
    "unknown":               {"loaded_min": 12.0, "ballast_max": 7.0,  "max_draft": 15.0},
}
LOADED_SPEED_RANGE = (8.0, 13.0)
BALLAST_SPEED_RANGE = (12.0, 16.0)


class CargoLoadClassifier:
    """Returns (status, confidence, features). status is LOADED | BALLAST | UNKNOWN."""

    def classify(self, draft_m: float | None, speed_knots: float | None,
                 vessel_type: str = "unknown") -> tuple:
        t = VESSEL_DRAFT_THRESHOLDS.get(vessel_type, VESSEL_DRAFT_THRESHOLDS["unknown"])
        features = {"draft_m": draft_m, "speed_knots": speed_knots, "vessel_type": vessel_type}
        if draft_m is None:
            return ("UNKNOWN", 0.0, features)  # no draft -> no claim

        score, evidence = 0.0, 1
        if draft_m >= t["loaded_min"]:
            score += 0.7
        elif draft_m <= t["ballast_max"]:
            score -= 0.7
        else:
            mid = (t["loaded_min"] + t["ballast_max"]) / 2
            score += 0.3 * (draft_m - mid) / (t["loaded_min"] - mid)
        if speed_knots is not None:
            evidence += 1
            if LOADED_SPEED_RANGE[0] <= speed_knots <= LOADED_SPEED_RANGE[1]:
                score += 0.2
            elif speed_knots > BALLAST_SPEED_RANGE[0]:
                score -= 0.2
        score /= max(evidence * 0.5, 1.0)

        confidence = round(1.0 / (1.0 + math.exp(-abs(score) * 2)), 2)
        if score > 0.3:
            return ("LOADED", confidence, features)
        if score < -0.3:
            return ("BALLAST", confidence, features)
        return ("UNKNOWN", 0.0, features)


cargo_classifier = CargoLoadClassifier()


# ---------------------------------------------------------------------------
# Step 7: Trader signal — snapshot + monthly trend
# ---------------------------------------------------------------------------
def monthly_series(vessels: list[dict], start: str, end: str) -> list[dict]:
    """Per month: events by kind and the number of distinct active vessels."""
    counts = defaultdict(Counter)
    active = defaultdict(set)
    for v in vessels:
        for e in v.get("events", []):
            if not e.get("start"):
                continue
            month = e["start"][:7]
            counts[month][e["kind"]] += 1
            active[month].add(v["imo"])

    first = datetime.date.fromisoformat(start)
    if first.day > 1:  # skip a partial first month; it would understate activity
        first = (first.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    months, cur = [], first
    last = datetime.date.fromisoformat(end)
    while cur <= last:
        months.append(cur.strftime("%Y-%m"))
        cur = (cur.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)

    return [{
        "month": m,
        "active_vessels": len(active[m]),
        "ais_gaps": counts[m]["gap"],
        "loitering": counts[m]["loitering"],
        "port_visits": counts[m]["port_visit"],
        "encounters": counts[m]["encounter"],
    } for m in months]


def generate_market_signal(vessels: list[dict], start: str, end: str) -> dict:
    high_risk = [v for v in vessels if v["risk_score"] >= 70]
    status = Counter(v["cargo_status"] for v in high_risk)
    series = monthly_series(vessels, start, end)

    # Trend: last 3 full months vs the 3 before, on active vessels.
    recent = sum(m["active_vessels"] for m in series[-4:-1])
    prior = sum(m["active_vessels"] for m in series[-7:-4])
    trend_pct = round((recent - prior) / prior * 100, 1) if prior else None

    return {
        "signal_date": datetime.date.today().isoformat(),
        "window": {"start": start, "end": end},
        "brent_crude_usd": BRENT_CRUDE_USD_PER_BARREL,
        "vessels_screened": len(vessels),
        "vessels_matched": sum(1 for v in vessels if v["gfw_match"]),
        "vessels_located": sum(1 for v in vessels if v.get("_lat") is not None),
        "high_risk_vessels": len(high_risk),
        "vessels_loaded": status.get("LOADED", 0),
        "vessels_ballast": status.get("BALLAST", 0),
        "vessels_unknown": status.get("UNKNOWN", 0),
        "est_single_cargo_barrels": {
            "low": sum(v["est_cargo_barrels"]["low"] for v in high_risk),
            "high": sum(v["est_cargo_barrels"]["high"] for v in high_risk),
        },
        "est_annual_flow_usd": {
            "low": round(sum(v["est_annual_flow_usd"]["low"] for v in high_risk)),
            "high": round(sum(v["est_annual_flow_usd"]["high"] for v in high_risk)),
        },
        "activity_trend_3m_pct": trend_pct,
        "monthly": series,
        "top_ports": [{"port": p, "calls": n} for p, n in Counter(
            e["port"] for v in vessels for e in v.get("events", [])
            if e["kind"] == "port_visit" and e.get("port")).most_common(10)],
        "provenance": {
            "sanctions": "OpenSanctions maritime dataset (CC BY-NC 4.0)",
            "behaviour": "Global Fishing Watch API v3 (non-commercial)",
            "price": f"Static Brent reference ${BRENT_CRUDE_USD_PER_BARREL}/bbl",
            "note": "Directional estimates only. Not proof of wrongdoing or trading advice.",
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def clean(value):
    """pandas uses NaN for missing cells; JSON needs null."""
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else value


def analyse_vessel(row: pd.Series, start: str, end: str, offline: bool) -> dict:
    row = row.map(clean)
    imo = row["imo"]
    base = {
        "imo": imo,
        "name": row.get("caption") or row.get("name") or "UNKNOWN",
        "opensanctions_id": row.get("id"),
        "sanctioned": bool(row.get("_sanctioned")),
        "flag_listed": row.get("flag"),
        "sanction_programs": str(row.get("datasets") or ""),
        "opensanctions_url": row.get("url"),
    }
    window_days = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days

    record = gfw_search_vessel(imo, offline)
    if record is None:
        score, breakdown = compute_risk_score(base["sanctioned"], 0, 0, 0)
        cap = estimate_cargo_barrels(None, None)
        return {**base, "gfw_match": False, "risk_score": score, "risk_breakdown": breakdown,
                "cargo_status": "UNKNOWN", "cargo_confidence": 0.0,
                "est_cargo_barrels": cap, "est_annual_flow_usd": annual_flow(cap, 0, window_days),
                "identity_history": [], "events": [], "_lat": None, "_lng": None}

    ids = gfw_vessel_ids(record)
    events = []
    for kind in EVENT_DATASETS:
        events.extend(fetch_events(ids, kind, start, end, offline))
    events.sort(key=lambda e: e["start"] or "")

    kinds = Counter(e["kind"] for e in events)
    dark_gaps = sum(1 for e in events if e["kind"] == "gap" and e.get("intentional") is not False)
    history = identity_history(record)
    changes = count_identity_changes(record)
    score, breakdown = compute_risk_score(base["sanctioned"], changes, dark_gaps, kinds["loitering"], kinds["encounter"])

    gt, length = vessel_dimensions(record)
    cap = estimate_cargo_barrels(gt, length)
    status, conf, _ = cargo_classifier.classify(None, None)  # no public draft feed
    lat, lng, seen = latest_position(events)
    latest = history[-1] if history else {}

    return {
        **base,
        "gfw_match": True,
        "gfw_vessel_id": ids[0] if ids else None,
        "current_name": latest.get("name"),
        "current_flag": latest.get("flag"),
        "identity_changes": changes,
        "ais_gaps": dark_gaps,
        "loitering_events": kinds["loitering"],
        "port_visits": kinds["port_visit"],
        "encounters": kinds["encounter"],
        "risk_score": score,
        "risk_breakdown": breakdown,
        "cargo_status": status,
        "cargo_confidence": conf,
        "gross_tonnage": gt,
        "length_m": length,
        "est_cargo_barrels": cap,
        "est_annual_flow_usd": annual_flow(cap, kinds["port_visit"], window_days),
        "identity_history": history,
        "events": events,  # full list; trimmed only when written (see EVENTS_PER_VESSEL)
        "_lat": lat,
        "_lng": lng,
        "last_seen": seen,
    }


def annual_flow(cap: dict, port_visits: int, window_days: int) -> dict:
    v_low, v_high = estimate_annual_voyages(port_visits, window_days)
    return {
        "low": round(estimate_cargo_value_usd(cap["low"]) * v_low),
        "high": round(estimate_cargo_value_usd(cap["high"]) * v_high),
        "voyages_per_year": [v_low, v_high],
    }


def main():
    today = datetime.date.today()
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--csv", default=MARITIME_CSV_PATH)
    parser.add_argument("--max", type=int, default=MAX_VESSELS)
    parser.add_argument("--start", default=(today - datetime.timedelta(days=365)).isoformat())
    parser.add_argument("--end", default=(today - datetime.timedelta(days=3)).isoformat())
    parser.add_argument("--offline", action="store_true", help="use cached API responses only")
    args = parser.parse_args()

    vessels = load_sanctioned_vessels(args.csv, args.max)
    print(f"Screening {len(vessels)} sanctioned vessels, {args.start} -> {args.end}")

    results = []
    for n, (_, row) in enumerate(vessels.iterrows(), 1):
        v = analyse_vessel(row, args.start, args.end, args.offline)
        results.append(v)
        print(f"  [{n:>3}/{len(vessels)}] {v['imo']} {str(v['name'])[:28]:<28} "
              f"match={v['gfw_match']!s:<5} score={v['risk_score']:>3} events={len(v['events'])}")

    results.sort(key=lambda v: v["risk_score"], reverse=True)
    signal = generate_market_signal(results, args.start, args.end)  # uses all events
    for v in results:
        v["events"] = v["events"][-EVENTS_PER_VESSEL:]  # most recent evidence only

    flat = pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, (list, dict))} for r in results])
    flat.to_csv("dark_fleet_risk_scores.csv", index=False)

    DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)
    # allow_nan=False: NaN is not valid JSON and breaks the dashboard.
    (DASHBOARD_DATA_DIR / "signal.json").write_text(json.dumps(signal, indent=2, allow_nan=False), encoding="utf-8")
    (DASHBOARD_DATA_DIR / "vessels.json").write_text(json.dumps({
        "generated": signal["signal_date"],
        "window": signal["window"],
        "data_kind": "real",
        "vessels": results,
    }, separators=(",", ":"), default=str, allow_nan=False), encoding="utf-8")  # compact: machine-read, keeps page load light

    print(f"\nMatched {signal['vessels_matched']}/{signal['vessels_screened']}, "
          f"located {signal['vessels_located']}, high-risk {signal['high_risk_vessels']}, "
          f"3-month activity trend {signal['activity_trend_3m_pct']}%")
    print("Saved -> dashboard/data/vessels.json, dashboard/data/signal.json, dark_fleet_risk_scores.csv")


if __name__ == "__main__":
    main()
