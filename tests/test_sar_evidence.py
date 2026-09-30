"""The radar (SAR) evidence file must stay consistent with the snapshot and honest in wording.

dashboard/data/sar.json is built by `python -m ml.build` from research outputs
that are not committed. These tests check the committed file on its own.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"
SAR_PATH = DASH / "data" / "sar.json"
SNAP = json.loads((DASH / "data" / "vessels.json").read_text(encoding="utf-8"))
VESSELS = {v["imo"]: v for v in SNAP["vessels"]}

pytestmark = pytest.mark.skipif(not SAR_PATH.exists(), reason="sar.json not built")


@pytest.fixture(scope="module")
def sar():
    return json.loads(SAR_PATH.read_text(encoding="utf-8"))


def test_every_vessel_is_a_snapshot_vessel(sar):
    assert set(sar["vessels"]) == set(VESSELS)


def test_radar_points_are_dated_inside_the_window_and_inside_a_corridor(sar):
    boxes = [c["bbox"] for c in sar["coverage"]["corridors"]]
    for imo, rec in sar["vessels"].items():
        r = rec["radar"]
        assert r["days"] <= r["detections"] or r["detections"] == 0
        for date, lat, lon in r["points"]:
            assert SNAP["window"]["start"] <= date <= SNAP["window"]["end"], imo
            assert any(w <= lon <= e and s <= lat <= n for w, s, e, n in boxes), imo


def test_our_matches_have_probabilities_and_existing_images(sar):
    for imo, rec in sar["vessels"].items():
        m = rec.get("our_match")
        if not m:
            continue
        assert 0.5 <= m["posterior"] <= 1 and 0 <= m["detector_p"] <= 1
        assert (DASH / m["image"]).exists(), m["image"]
        assert m["gfw_agrees"] in (True, False, None)


def test_side_by_side_labels_come_from_review(sar):
    allowed = {"side_by_side", "single_hull", "unclear", "not_a_vessel"}
    for rec in sar["vessels"].values():
        for c in rec.get("side_by_side", []):
            assert c["label"] in allowed


def test_cargo_stays_unknown_unless_the_gate_passed(sar):
    gate = (sar["models"].get("cargo_summary") or {}).get("gate_passed", False)
    if not gate:
        assert all(rec["cargo"] is None for rec in sar["vessels"].values())
    assert all(v["cargo_status"] == "UNKNOWN" for v in VESSELS.values())


def test_models_report_their_reference(sar):
    det = sar["models"]["detector"]
    assert "not ground truth" in det["reference"]
    assert "scene" in det["split"]
    assert "not ground truth" in sar["models"]["matching_summary"]["reference"]


def test_radar_rows_never_change_the_score_and_replay_uses_only_sar_points(sar):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    driver = r"""
const GF = require(process.argv[1]);
const snap = require(process.argv[2]);
const sar = require(process.argv[3]);
const bad = snap.vessels.filter((v) => !GF.evidenceRows(v, snap.window, sar).matchesScore).map((v) => v.imo);
const idx = GF.replayIndex(snap.vessels, snap.window, sar);
const radar = [];
for (const ym of idx.months) for (const o of idx.observations(ym)) if (o.kind === "sar") radar.push([o.imo, o.index, o.start, o.lat, o.lon]);
const rows = {};
for (const v of snap.vessels) rows[v.imo] = GF.evidenceRows(v, snap.window, sar).rows.map((r) => [r.key, r.status.label, r.points]);
process.stdout.write(JSON.stringify({ bad, radar, rows }));
"""
    out = subprocess.run([node, "-e", driver, str(DASH / "evidence.js"), str(DASH / "data" / "vessels.json"), str(SAR_PATH)],
                         capture_output=True, text=True, encoding="utf-8", check=True)
    res = json.loads(out.stdout)
    assert res["bad"] == []
    expected = {(imo, i, d, la, lo) for imo, rec in sar["vessels"].items()
                for i, (d, la, lo) in enumerate(rec["radar"]["points"])}
    assert {tuple(x) for x in res["radar"]} == expected
    for imo, rows in res["rows"].items():
        for key, status, points in rows:
            if key in ("radar", "our_match", "nearby", "side_by_side"):
                assert points is None, (imo, key)
            if key in ("our_match", "side_by_side"):
                assert status == "Model estimate", (imo, key)


UI = "\n".join((DASH / f).read_text(encoding="utf-8") for f in ("models.html", "models.js", "evidence.js", "index.html"))


@pytest.mark.parametrize("pattern", [
    r"\b(sts|ship-to-ship) transfer (occurred|confirmed|detected)",
    r"confirmed (sts|ship-to-ship|transfer)",
    r"(dark|unmatched) (vessel|target)s? (prove|confirm)",
    r"\b(accuracy|accurate) of \d",
    r"state[- ]of[- ]the[- ]art",
    r"validated (model|accuracy|performance)",
    r"\blive (tracking|data|feed|ais|radar)",
])
def test_model_wording_makes_no_unsupported_claim(pattern):
    assert not re.search(pattern, UI, re.I), pattern
