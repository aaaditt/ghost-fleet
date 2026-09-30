"""The Evidence Matrix and Historical evidence replay must reflect the snapshot exactly.

Runs the real dashboard/evidence.js in Node (skipped if Node is missing) and
checks its output against an independent Python reading of vessels.json.
"""

import calendar
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"
SNAPSHOT = json.loads((DASH / "data" / "vessels.json").read_text(encoding="utf-8"))
VESSELS = SNAPSHOT["vessels"]
WINDOW = SNAPSHOT["window"]

DRIVER = r"""
const GF = require(process.argv[1]);
const snap = require(process.argv[2]);
const idx = GF.replayIndex(snap.vessels, snap.window);
const replay = {};
for (const ym of idx.months) replay[ym] = idx.observations(ym);
const matrix = {};
for (const v of snap.vessels) matrix[v.imo] = GF.evidenceRows(v, snap.window);
process.stdout.write(JSON.stringify({ months: idx.months, replay, matrix }));
"""


@pytest.fixture(scope="module")
def js():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    out = subprocess.run(
        [node, "-e", DRIVER, str(DASH / "evidence.js"), str(DASH / "data" / "vessels.json")],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(out.stdout)


def months_overlapped(start, end):
    """Independent re-derivation: calendar months an event's span overlaps, clipped to the window."""
    lo, hi = WINDOW["start"], WINDOW["end"] + "T23:59"
    s = max(start, lo)
    e = min(end if end and end > start else start, hi)
    if s > e:
        return []
    y, m = int(s[:4]), int(s[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= e[:7]:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def test_every_replay_observation_is_a_dated_positioned_snapshot_event(js):
    by_imo = {v["imo"]: v for v in VESSELS}
    for ym, observations in js["replay"].items():
        for o in observations:
            e = by_imo[o["imo"]]["events"][o["index"]]
            assert e["start"] and all(isinstance(e[k], (int, float)) and not isinstance(e[k], bool) for k in ("lat", "lon"))
            assert (o["kind"], o["lat"], o["lon"], o["start"]) == (e["kind"], e["lat"], e["lon"], e["start"])
            assert ym in months_overlapped(e["start"], e["end"])


def test_replay_contains_every_positioned_event_and_nothing_else(js):
    expected = set()
    for v in VESSELS:
        for i, e in enumerate(v["events"]):
            if e.get("start") and e.get("lat") is not None and e.get("lon") is not None:
                expected |= {(ym, v["imo"], i) for ym in months_overlapped(e["start"], e["end"])}
    got = [(ym, o["imo"], o["index"]) for ym, obs in js["replay"].items() for o in obs]
    assert len(got) == len(set(got)), "an observation is listed twice in one month"
    assert set(got) == expected


def test_replay_timeline_is_monthly_contiguous_and_inside_the_window(js):
    months = js["months"]
    assert months[0] == WINDOW["start"][:7] and months[-1] == WINDOW["end"][:7]
    for a, b in zip(months, months[1:]):
        y, m = int(a[:4]), int(a[5:])
        assert b == (f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}")


def test_matrix_points_agree_with_the_stored_score_and_breakdown(js):
    for v in VESSELS:
        m = js["matrix"][v["imo"]]
        scored = {r["key"]: r["points"] for r in m["rows"] if r["points"] is not None}
        assert scored == v["risk_breakdown"], v["imo"]
        assert m["total"] == v["risk_score"] and m["matchesScore"], v["imo"]


def test_cargo_state_stays_unknown_without_draft_evidence(js):
    assert all(v["cargo_status"] == "UNKNOWN" for v in VESSELS)
    for imo, m in js["matrix"].items():
        cargo = next(r for r in m["rows"] if r["key"] == "cargo")
        assert cargo["status"]["label"] == "Unavailable / unknown", imo
        assert cargo["points"] is None


def test_matrix_labels_absent_evidence_as_not_observed(js):
    for v in VESSELS:
        rows = {r["key"]: r for r in js["matrix"][v["imo"]]["rows"]}
        if v["encounters"] == 0:
            assert rows["encounters"]["status"]["label"] == "Not observed"
        if v["ais_gaps"] == 0:
            assert rows["ais_gaps"]["status"]["label"] == "Not observed"
        if not v["last_seen"]:
            assert rows["freshness"]["status"]["label"] == "Unavailable / unknown"


def test_gap_intent_wording_only_where_the_source_labels_it(js):
    for v in VESSELS:
        gap = next(r for r in js["matrix"][v["imo"]]["rows"] if r["key"] == "ais_gaps")
        labelled = any(e["kind"] == "gap" and e.get("intentional") is True for e in v["events"])
        assert ("intentional" in gap["detail"]) == labelled, v["imo"]
        if labelled:
            assert "possible intentional disabling" in gap["detail"]


def test_partial_months_are_the_window_edges():
    # The window rarely starts on the 1st or ends on the last day; the UI flags both.
    end = WINDOW["end"]
    last_day = calendar.monthrange(int(end[:4]), int(end[5:7]))[1]
    assert WINDOW["start"][8:] != "01" or int(end[8:]) < last_day


UI_TEXT = "\n".join((DASH / f).read_text(encoding="utf-8") for f in ("index.html", "app.js", "evidence.js"))

OVERCLAIMS = [
    r"\blive (tracking|data|feed|ais|position)",
    r"real[- ]time",
    r"confirmed (sts|ship-to-ship|transfer)",
    r"(sts|ship-to-ship) transfer (occurred|confirmed|detected)",
    r"ghost-flow",
    r"continuous(ly)? track(ing|ed)\b",
    r"\b(ml|machine[- ]learning|model)[- ]?(predicted|inferred|classified) cargo",
    r"ais (switched|turned) off",
    r"(went|goes|going) dark",
    r"proves? (wrongdoing|evasion|guilt)",
]


@pytest.mark.parametrize("pattern", OVERCLAIMS)
def test_ui_wording_makes_no_unsupported_claim(pattern):
    assert not re.search(pattern, UI_TEXT, re.I), pattern


def test_replay_explains_that_it_is_sparse_and_not_a_trend():
    html = (DASH / "index.html").read_text(encoding="utf-8")
    assert "Historical evidence replay" in html
    assert "not a continuous track" in html
    assert "never joined or interpolated" in html
    assert "not a trend" in html
