/* Models page: renders every figure from data/sar.json so the card cannot drift from the data. */

const $ = (id) => document.getElementById(id);
const pct = (x) => (x == null ? "—" : `${Math.round(x * 100)}%`);
const f2 = (x) => (x == null ? "—" : x.toFixed(2));
const ci = (c) => (c ? `${f2(c[0])}–${f2(c[1])}` : "—");

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function table(head, rows) {
    return `<table class="metrics"><thead><tr>${head.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead>
        <tbody>${rows.map((r) => `<tr>${r.map((c, i) => i === 0 ? `<th scope="row">${esc(c)}</th>` : `<td class="num">${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function render(sar) {
    const m = sar.models;
    const nDet = Object.values(sar.vessels).filter((v) => v.radar.detections).length;
    $("coverage").textContent =
        `Window ${sar.window.start} to ${sar.window.end}. Radar evidence covers ${sar.coverage.corridors.length} one-degree corridors ` +
        `where these tankers spend the most time, and only days when Sentinel-1 imaged them. ${nDet} of ${Object.keys(sar.vessels).length} ` +
        `tankers have at least one GFW radar detection matched to their IMO there.`;

    const d = m.detector;
    if (d) {
        const row = (name, x) => [name, f2(x.pr_auc), ci(x.pr_auc_ci95), pct(x.at_val_threshold.precision), pct(x.at_val_threshold.recall)];
        $("detector").innerHTML = table(["Test scenes", "PR-AUC", "95% CI", "Precision", "Recall"],
            [row("Our CNN", d.cnn), row("CFAR baseline", d.cfar)]) +
            `<p class="ref">${d.counts.test.chips.toLocaleString("en-GB")} test chips (${d.counts.test.positive.toLocaleString("en-GB")} with a vessel) ` +
            `from ${d.counts.test.scenes} held-out scenes; trained on ${d.counts.train.chips.toLocaleString("en-GB")} chips from ${d.counts.train.scenes} scenes. ` +
            `Precision and recall use the threshold chosen on the validation scenes. The CNN's strongest response falls within 800 m of GFW's ` +
            `detection cell centre for ${pct(d.cnn.peak_within_800m_of_cell_centre)} of test vessels.</p>`;
        const rv = m.detector_review;
        if (rv) {
            $("detector").innerHTML += `<p class="ref">Every test disagreement was inspected by eye (${esc(rv.reviewer)}). ` +
                `Of ${rv.false_alarms.total} false alarms, ${rv.false_alarms.vessel_clearly_visible} clearly show a vessel GFW did not report and ` +
                `${rv.false_alarms.coast_or_land_clutter} are coastline clutter. Of ${rv.misses.total} misses, ${rv.misses.target_visible} show a visible ` +
                `target; in the rest no vessel is visible, most likely because the chip came from a different pass that day. ` +
                `The headline figures are left as measured.</p>`;
        }
    }

    const s = m.matching_summary;
    if (s) {
        $("matching").innerHTML = table(["Match probability", "Observations", "Agrees with GFW"],
            s.reliability.map((b) => [b.posterior, String(b.n), pct(b.agreement_with_gfw)])) +
            `<p class="ref">${s.observations.toLocaleString("en-GB")} image observations of ${s.vessels} tankers. Where GFW also matched the ` +
            `tanker that day (${s.with_gfw_match}), our top target lay within 1.2 km of GFW's for ${pct(s.top_candidate_agrees_within_1_2km)}. ` +
            `Agreement rises with match probability, so the probabilities rank matches usefully. They are conservative, not calibrated: ` +
            `even the lowest band agrees with GFW more often than its probability suggests.</p>`;
    }

    const t = m.sts;
    if (t) {
        const labels = Object.entries(t.labels || {}).map(([k, n]) => `${n} ${k.replace(/_/g, " ")}`).join(", ");
        const br = t.by_rule || {};
        const rule = (k, name) => br[k] ? `${name}: ${br[k].side_by_side} of ${br[k].reviewed} reviewed` : "";
        $("sts").innerHTML = `<p>${t.candidates} candidate images; ${t.reviewed} reviewed: ${esc(labels || "none")}.</p>` +
            `<p>Confirmed pairs by rule: ${esc([rule("two_targets", "two hulls within 250 m"), rule("wide_target", "one unusually wide target")].filter(Boolean).join("; "))}. ` +
            `At 10 m pixels a single tanker's bright bow, bridge and sidelobes often look like two objects, so the automatic rule is not reliable ` +
            `on its own; only reviewed pairs are shown on the map. ${esc(t.sampling || "")}.</p>` +
            `<p class="ref">Reviewer: ${esc(t.reviewer)}. ${esc(t.wording)}.</p>`;
    }

    const c = m.cargo_summary;
    if (c) {
        const rows = Object.entries(c.models || {}).map(([k, x]) => [k.replace(/_/g, " "), f2(x.auc_out_of_vessel), ci(x.auc_ci95)]);
        $("cargo").innerHTML = (rows.length ? table(["Model", "AUC (unseen vessels)", "95% CI"], rows) : "") +
            `<p><span class="verdict ${c.gate_passed ? "go" : "nogo"}">${esc(c.decision)}</span></p>` +
            `<p class="ref">${c.observations} labelled observations of ${c.vessels} tankers (${c.laden} likely laden, ${c.ballast} likely ballast). ` +
            `Pass mark: lower 95% bound of AUC at least ${c.gate.auc_ci_low}, with at least ${c.gate.min_obs} observations from ${c.gate.min_vessels} vessels. ` +
            `An AUC of 0.5 is a coin toss.</p>`;
    }
    const x = m.xview3;
    if (x) {
        const f3 = (y) => (y == null ? "—" : y.toFixed(3));
        const row = (name, v) => [name, f3(v.pr_auc), (v.pr_auc_ci95 ? `${f3(v.pr_auc_ci95[0])}–${f3(v.pr_auc_ci95[1])}` : "—"), pct(v.at_val_threshold.precision), pct(v.at_val_threshold.recall)];
        const dist = Object.entries(x.recall_by_distance || {}).map(([k, v]) => [k, String(v.vessels), pct(v.cnn), pct(v.cfar)]);
        $("xview3").innerHTML = table(["xView3 scenes", "PR-AUC", "95% CI", "Precision", "Recall"], [row("Our CNN", x.cnn), row("CFAR baseline", x.cfar)]) +
            table(["Recall by distance from shore", "Vessels", "Our CNN", "CFAR"], dist) +
            `<p class="ref">${x.chips.toLocaleString("en-GB")} chips (${x.positive.toLocaleString("en-GB")} with a vessel) from ${x.scenes} xView3 validation ` +
            `scenes, ${esc(x.years)}. Thresholds are the ones chosen on our own validation scenes, not tuned here. ${esc(x.reference)}.</p>`;
    }
    $("card").removeAttribute("aria-busy");
}

fetch("data/sar.json")
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .then(render)
    .catch((err) => { $("coverage").textContent = `The model report could not be loaded (${err.message}).`; });
