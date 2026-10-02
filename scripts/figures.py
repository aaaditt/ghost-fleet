"""Every figure quoted in the submission materials, from the committed snapshot."""
import json
import statistics
from collections import Counter

V = json.load(open("dashboard/data/vessels.json", encoding="utf-8"))["vessels"]
S = json.load(open("dashboard/data/signal.json", encoding="utf-8"))
LAND = {"MLI", "MWI", "ZWE", "MNG", "SWZ", "BOL", "AFG", "AND", "ARM", "AUT", "AZE", "BDI", "BFA", "BLR",
        "BTN", "BWA", "CAF", "CHE", "CZE", "ETH", "HUN", "KAZ", "KGZ", "LAO", "LIE", "LSO", "LUX", "MDA",
        "MKD", "NER", "NPL", "PRY", "RWA", "SMR", "SRB", "SSD", "SVK", "TCD", "TJK", "TKM", "UGA", "UZB",
        "VAT", "ZMB", "XKX"}
ch = [v.get("identity_changes", 0) for v in V]
m = S["monthly"]
recent = sum(x["active_vessels"] for x in m[-4:-1])
prior = sum(x["active_vessels"] for x in m[-7:-4])
out = {
    "screened": S["vessels_screened"], "matched": S["vessels_matched"], "located": S["vessels_located"],
    "high_risk": S["high_risk_vessels"],
    "trend_pct": S["activity_trend_3m_pct"], "recent_3m": recent, "prior_3m": prior,
    "trend_check_pct": round((recent - prior) / prior * 100, 1),
    "monthly_active": [x["active_vessels"] for x in m],
    "switched_any": sum(c >= 1 for c in ch), "switched_5plus": sum(c >= 5 for c in ch),
    "median_switches": statistics.median(ch),
    "flags_used": len({h["flag"] for v in V for h in v["identity_history"] if h["flag"]}),
    "landlocked_now": dict(Counter(v.get("current_flag") for v in V if v.get("current_flag") in LAND)),
    "russia_now": sum(v.get("current_flag") == "RUS" for v in V),
    "median_lists": statistics.median(len(v["sanction_programs"].split(";")) for v in V),
    "port_calls_full_months": sum(x["port_visits"] for x in m),
    "top_ports": [(p["port"], p["calls"]) for p in S["top_ports"][:6]],
    "flow_bn": [round(S["est_annual_flow_usd"]["low"] / 1e9), round(S["est_annual_flow_usd"]["high"] / 1e9)],
    "east1": next(({"score": v["risk_score"], "ids": sum(h["source"] == "AIS" for h in v["identity_history"])}
                   for v in V if v["imo"] == "9240885"), None),
}
# Radar (SAR) evidence and model results, from dashboard/data/sar.json (built by ml/)
R = json.load(open("dashboard/data/sar.json", encoding="utf-8"))
M = R["models"]
wolf = R["vessels"]["9240885"]
out["radar"] = {
    "corridors": len(R["coverage"]["corridors"]),
    "vessels_detected": sum(1 for v in R["vessels"].values() if v["radar"]["detections"]),
    "detections_of_our_vessels": sum(v["radar"]["detections"] for v in R["vessels"].values()),
    "vessels_with_our_match": sum(1 for v in R["vessels"].values() if "our_match" in v),
    "reviewed_side_by_side": sum(1 for v in R["vessels"].values() for x in v.get("side_by_side", []) if x["label"] == "side_by_side"),
    "detector_test": {k: {"pr_auc": round(M["detector"][k]["pr_auc"], 3),
                          "precision": round(M["detector"][k]["at_val_threshold"]["precision"], 3),
                          "recall": round(M["detector"][k]["at_val_threshold"]["recall"], 3)} for k in ("cnn", "cfar")},
    "detector_test_scenes": M["detector"]["counts"]["test"]["scenes"],
    "unmatched_recall": {k: round(v, 3) for k, v in M["detector"]["by_group"]["unmatched"].items()},
    "matching_agreement": round(M["matching_summary"]["top_candidate_agrees_within_1_2km"], 3),
    "matching_observations": M["matching_summary"]["observations"],
    "cargo_auc": {k: round(v["auc_out_of_vessel"], 2) for k, v in M["cargo_summary"]["models"].items()},
    "cargo_gate_passed": M["cargo_summary"]["gate_passed"],
    "wolf": {"detections": wolf["radar"]["detections"], "first": wolf["radar"]["first"], "last": wolf["radar"]["last"],
             "our_match": {k: wolf["our_match"][k] for k in ("date", "time", "posterior", "offset_m", "gfw_agrees")}},
}
# Radar passes draped on the globe, from dashboard/data/radar_passes.json (built by ml/build.py)
P = json.load(open("dashboard/data/radar_passes.json", encoding="utf-8"))["vessels"]
wolf_passes = P.get("9240885", [])
out["radar_passes"] = {
    "passes": sum(map(len, P.values())),
    "ships": len(P),
    "confident": sum(p["confident"] for ps in P.values() for p in ps),
    "wolf": {"passes": len(wolf_passes), "confident": sum(p["confident"] for p in wolf_passes),
             "first": wolf_passes[0]["date"] if wolf_passes else None, "last": wolf_passes[-1]["date"] if wolf_passes else None},
}
x3 = M.get("xview3")
if x3:
    out["xview3"] = {"scenes": x3["scenes"], "chips": x3["chips"],
                     **{k: {"pr_auc": x3[k]["pr_auc"], "precision": x3[k]["at_val_threshold"]["precision"],
                            "recall": x3[k]["at_val_threshold"]["recall"]} for k in ("cnn", "cfar")},
                     "recall_by_distance": x3["recall_by_distance"]}
print(json.dumps(out, indent=1, ensure_ascii=False))
