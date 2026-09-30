/* Ghost Fleet — evidence logic with no DOM access, so the same code runs in
   the browser (window.GF) and in Node for tests (module.exports).

   evidenceRows(): the per-vessel Evidence Matrix, built only from snapshot
   fields. Points are copied from risk_breakdown; nothing is re-scored here.

   replayIndex(): the Historical evidence replay. Each observation is one
   dated, positioned event from the snapshot, listed under every calendar month
   its recorded time span overlaps (clipped to the snapshot window). Nothing is
   interpolated and no route is implied. */

(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    else root.GF = api;
})(typeof self !== "undefined" ? self : this, function () {

    const STATUS = {
        OBSERVED: { key: "observed", label: "Observed" },
        DERIVED: { key: "derived", label: "Derived from AIS" },
        NOT_OBSERVED: { key: "not-observed", label: "Not observed" },
        UNKNOWN: { key: "unknown", label: "Unavailable / unknown" },
    };

    // Map styling and wording per event kind. Encounters are included so the
    // dashboard reads them correctly if a future snapshot contains any.
    const KINDS = {
        port_visit: { label: "Port call", one: "port call", plural: "port calls" },
        loitering: { label: "Loitering offshore", one: "loitering event", plural: "loitering" },
        gap: { label: "AIS gap", one: "AIS gap", plural: "AIS gaps" },
        encounter: { label: "Apparent encounter (possible)", one: "apparent encounter", plural: "apparent encounters" },
    };

    // ── Formatting ──────────────────────────────────────────

    function parseIso(iso) {
        return new Date(iso.length <= 10 ? iso + "T00:00:00Z" : iso + "Z");
    }

    function fmtDate(iso, withYear = true) {
        if (!iso) return "—";
        return parseIso(iso).toLocaleDateString("en-GB", {
            day: "numeric", month: "short", year: withYear ? "numeric" : undefined, timeZone: "UTC",
        });
    }

    function fmtMonthLong(ym) {
        return parseIso(ym + "-01").toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
    }

    function fmtMonthShort(ym) {
        return parseIso(ym + "-01").toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
    }

    function fmtHours(h) {
        if (h == null) return "duration not recorded";
        if (h < 48) return `${Math.round(h)} h`;
        return `${Math.round(h / 24)} days`;
    }

    function titleCase(name) {
        return String(name || "").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
    }

    function plural(n, one, many) {
        return `${n.toLocaleString("en-GB")} ${n === 1 ? one : many || one + "s"}`;
    }

    function eventLabel(e) {
        if (e.kind === "port_visit") return `Port call, ${titleCase(e.port || "unnamed port")}`;
        if (e.kind === "loitering") return `Loitered offshore, ${fmtHours(e.hours)}`;
        if (e.kind === "gap") {
            return `AIS gap, ${fmtHours(e.hours)}` +
                (e.intentional === true ? " (GFW label: possible intentional disabling)" : "");
        }
        if (e.kind === "encounter") return `Apparent encounter with ${titleCase(e.partner || "another vessel")} (possible)`;
        return e.kind;
    }

    function isPositioned(e) {
        return e && e.start && typeof e.lat === "number" && typeof e.lon === "number";
    }

    // ── Evidence Matrix ─────────────────────────────────────

    function evidenceRows(v, window) {
        const b = v.risk_breakdown || {};
        const events = v.events || [];
        const lists = String(v.sanction_programs || "").split(";").filter(Boolean);
        const ais = (v.identity_history || []).filter((h) => h.source === "AIS");
        const flags = new Set(ais.map((h) => h.flag).filter(Boolean));
        const loiters = events.filter((e) => e.kind === "loitering" && e.hours != null);
        const gaps = events.filter((e) => e.kind === "gap");
        const labelled = gaps.filter((e) => e.intentional === true).length;
        const rows = [];

        rows.push({
            key: "sanctions",
            label: "Sanctions or watch-list listing",
            status: lists.length || v.sanctioned ? STATUS.OBSERVED : STATUS.UNKNOWN,
            detail: `Named on ${plural(lists.length, "source list")} collected by OpenSanctions` +
                (v.sanctioned ? ", including at least one formal sanctions designation." : ", tagged as shadow fleet."),
            source: "OpenSanctions",
            points: b.sanctions ?? 0,
            rule: v.sanctioned ? "30 for a shadow-fleet listing, plus 10 for a formal sanctions designation" : "30 for a shadow-fleet listing",
            lists,
        });

        const changes = v.identity_changes || 0;
        rows.push({
            key: "identity",
            label: "Identity or flag changes",
            status: !ais.length ? STATUS.UNKNOWN : changes ? STATUS.DERIVED : STATUS.NOT_OBSERVED,
            detail: !ais.length
                ? "No AIS identity found for this IMO, so changes cannot be counted."
                : changes
                    ? `${plural(changes, "switch", "switches")} across ${plural(ais.length, "AIS identity", "AIS identities")} and ${plural(flags.size, "flag")}, first seen ${fmtDate(ais[0].from)}.`
                    : `One AIS identity recorded (${titleCase(ais[0].name)}, ${ais[0].flag || "flag not recorded"}).`,
            source: "Global Fishing Watch identity records",
            points: b.identity ?? 0,
            rule: "10 per switch, up to 30",
        });

        const nLoiter = v.loitering_events || 0;
        const longest = loiters.length ? Math.max(...loiters.map((e) => e.hours)) : null;
        rows.push({
            key: "meetings",
            label: "Offshore loitering",
            status: nLoiter ? STATUS.DERIVED : STATUS.NOT_OBSERVED,
            detail: nLoiter
                ? `${plural(nLoiter, "loitering event")} in the window` +
                  (longest != null ? `; the longest kept in this snapshot lasted ${fmtHours(longest)}.` : ".") +
                  " An analyst lead: tankers also idle while waiting for orders or a berth. It does not show a ship-to-ship transfer."
                : "No loitering recorded in the window.",
            source: "Global Fishing Watch loitering events",
            points: b.meetings ?? 0,
            rule: "1 per 4 loitering events plus 3 per encounter, up to 15 (shared with encounters)",
            span: 2,
        });

        const nEnc = v.encounters || 0;
        rows.push({
            key: "encounters",
            label: "Encounters with other vessels",
            status: nEnc ? STATUS.DERIVED : STATUS.NOT_OBSERVED,
            detail: nEnc
                ? `${plural(nEnc, "apparent encounter")} recorded. Possible activity only: an encounter does not show that cargo moved between ships.`
                : "No encounter with another vessel recorded in the window. That is not proof none happened.",
            source: "Global Fishing Watch encounter events",
            points: null,
            sharedWith: "meetings",
        });

        const nGaps = v.ais_gaps || 0;
        rows.push({
            key: "ais_gaps",
            label: "AIS gaps",
            status: nGaps ? STATUS.DERIVED : STATUS.NOT_OBSERVED,
            detail: nGaps
                ? `${plural(nGaps, "AIS gap")} counted in the window` +
                  (labelled ? `; ${labelled} kept in this snapshot ${labelled === 1 ? "carries" : "carry"} GFW's "possible intentional disabling" label.` : ".") +
                  " Poor reception or equipment faults can also cause gaps."
                : "No qualifying AIS gap recorded in the window. That is not proof the transponder stayed on.",
            source: "Global Fishing Watch AIS-gap events",
            points: b.ais_gaps ?? 0,
            rule: "5 per gap, up to 15",
        });

        const nPorts = v.port_visits || 0;
        rows.push({
            key: "ports",
            label: "Port calls",
            status: nPorts ? STATUS.DERIVED : STATUS.NOT_OBSERVED,
            detail: nPorts ? `${plural(nPorts, "port call")} in the window.` : "No port call recorded in the window.",
            source: "Global Fishing Watch port visits",
            points: null,
        });

        let fresh = "No dated, positioned event in this window.";
        if (v.last_seen) {
            const days = window && window.end
                ? Math.max(0, Math.round((parseIso(window.end) - parseIso(v.last_seen.slice(0, 10))) / 864e5))
                : null;
            fresh = `Latest dated event with a position: ${fmtDate(v.last_seen)}` +
                (days != null ? `, ${plural(days, "day")} before the snapshot ends.` : ".") +
                " Where it is now is not known.";
        }
        rows.push({
            key: "freshness",
            label: "Latest observation",
            status: v.last_seen ? STATUS.OBSERVED : STATUS.UNKNOWN,
            detail: fresh,
            source: "Global Fishing Watch events",
            points: null,
        });

        const known = v.cargo_status && v.cargo_status !== "UNKNOWN";
        rows.push({
            key: "cargo",
            label: "Cargo state (loaded or empty)",
            status: known ? STATUS.DERIVED : STATUS.UNKNOWN,
            detail: known
                ? `${titleCase(v.cargo_status)}, ${Math.round((v.cargo_confidence || 0) * 100)}% confidence, from draft readings.`
                : "Unknown. The public data has no draft reading, so we do not guess whether it is loaded.",
            source: "Draft readings (not in public data)",
            points: null,
        });

        const total = rows.reduce((n, r) => n + (r.points || 0), 0);
        return { rows, total, matchesScore: total === v.risk_score };
    }

    // ── Historical evidence replay ──────────────────────────

    function monthKey(iso) {
        return iso.slice(0, 7);
    }

    function nextMonth(ym) {
        let [y, m] = ym.split("-").map(Number);
        m += 1;
        if (m > 12) { m = 1; y += 1; }
        return `${y}-${String(m).padStart(2, "0")}`;
    }

    function replayIndex(vessels, window) {
        const lo = window.start;                 // "YYYY-MM-DD"
        const hi = window.end + "T23:59";
        const byMonth = new Map();
        let first = null, last = null;

        for (const v of vessels) {
            (v.events || []).forEach((e, index) => {
                if (!isPositioned(e)) return;
                const from = e.start < lo ? lo : e.start;
                const endRaw = e.end && e.end > e.start ? e.end : e.start;
                const to = endRaw > hi ? hi : endRaw;
                if (from > to) return;           // entirely outside the window
                for (let ym = monthKey(from); ym <= monthKey(to); ym = nextMonth(ym)) {
                    if (!byMonth.has(ym)) byMonth.set(ym, []);
                    byMonth.get(ym).push({
                        imo: v.imo, index, kind: e.kind, lat: e.lat, lon: e.lon,
                        start: e.start, end: e.end, began: monthKey(e.start) === ym,
                    });
                }
                if (!first || monthKey(from) < first) first = monthKey(from);
                if (!last || monthKey(to) > last) last = monthKey(to);
            });
        }

        const months = [];
        if (first) for (let ym = first; ym <= last; ym = nextMonth(ym)) months.push(ym);
        return {
            months,
            observations: (ym) => byMonth.get(ym) || [],
            partial: (ym) => ym === monthKey(lo) || ym === monthKey(window.end),
        };
    }

    function summarise(obs) {
        const byKind = {};
        const imos = new Set();
        let began = 0;
        for (const o of obs) {
            byKind[o.kind] = (byKind[o.kind] || 0) + 1;
            imos.add(o.imo);
            if (o.began) began += 1;
        }
        return { count: obs.length, vessels: imos.size, began, byKind, imos };
    }

    return {
        STATUS, KINDS, evidenceRows, replayIndex, summarise, eventLabel, isPositioned,
        fmtDate, fmtMonthLong, fmtMonthShort, fmtHours, titleCase, plural,
    };
});
