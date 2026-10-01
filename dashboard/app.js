/* Ghost Fleet — Hidden Supply Monitor
   Reads the pipeline snapshot (data/vessels.json, data/signal.json) and draws
   a chart of shadow-fleet tankers, a per-vessel evidence dossier, and a
   historical evidence replay on a MapLibre globe. Open a vessel directly
   with #imo=<number>, and a radar pass with #imo=<number>&pass=<n>.
   Evidence and replay logic lives in evidence.js (window.GF); the radar
   lens, time-lapse and gallery in radar.js; the guided tour in tour.js. */

const DATA_URL = "data/vessels.json";
const SIGNAL_URL = "data/signal.json";
const SAR_URL = "data/sar.json"; // optional: radar evidence (see ml/)
const HIGH_RISK = 70;
const HOME = { center: [52, 24], zoom: 2.1 };
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

const { fmtDate, fmtMonthLong, fmtMonthShort, titleCase, eventLabel, plural } = GF;

const FLAG_NAMES = {
    RUS: "Russia", CMR: "Cameroon", OMN: "Oman", SLE: "Sierra Leone", GNQ: "Equatorial Guinea",
    PAN: "Panama", COM: "Comoros", MLI: "Mali", MOZ: "Mozambique", ABW: "Aruba", BRB: "Barbados",
    GUY: "Guyana", ZWE: "Zimbabwe", GIN: "Guinea", BES: "Bonaire", MWI: "Malawi", LBR: "Liberia",
    GMB: "Gambia", DEU: "Germany", PLW: "Palau", COK: "Cook Islands", HKG: "Hong Kong",
    SGP: "Singapore", MHL: "Marshall Islands", DNK: "Denmark", CYP: "Cyprus", GAB: "Gabon",
    MLT: "Malta", GRC: "Greece", LVA: "Latvia", LTU: "Lithuania", NOR: "Norway", TGO: "Togo",
    KNA: "St Kitts & Nevis", BHS: "Bahamas", PRT: "Portugal", VCT: "St Vincent", TZA: "Tanzania",
    HND: "Honduras", BLZ: "Belize", MNG: "Mongolia", CHN: "China", IND: "India", ARE: "UAE",
    IRN: "Iran", TUR: "Türkiye", VNM: "Vietnam", KHM: "Cambodia", MDV: "Maldives", STP: "São Tomé",
    SWZ: "Eswatini", BOL: "Bolivia", BWA: "Botswana", NIC: "Nicaragua", SYR: "Syria", BEN: "Benin", DJI: "Djibouti", VUT: "Vanuatu", TUV: "Tuvalu",
};
const LANDLOCKED = new Set(["MLI", "MWI", "ZWE", "BWA", "MNG", "SWZ", "BOL"]);

const SCORE_PARTS = [
    { key: "sanctions", label: "Listing", color: "#ff4fa3" },
    { key: "identity", label: "Identity switches", color: "#e3eaed" },
    { key: "meetings", label: "Loitering and encounters", color: "#8ea3ac" },
    { key: "ais_gaps", label: "AIS gaps", color: "#4f6570" },
];

let vessels = [];
let byImo = new Map();
let snapshot = null;
let sar = null;
let selectedImo = null;
let lastTrigger = null;

const replay = { index: null, on: false, i: 0, timer: null, speed: 0, drawn: 0, imos: new Set(), perVessel: new Map() };

// ── Helpers ─────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function flagName(code) {
    return FLAG_NAMES[code] || code || "unknown flag";
}

function fmtMonth(ym) {
    return new Date(ym + "-01T00:00:00Z").toLocaleDateString("en-GB", { month: "short", timeZone: "UTC" });
}

function fmtUsdRange(low, high) {
    if (high >= 1e9) {
        const d = high >= 1e10 ? 0 : 1;
        return `$${(low / 1e9).toFixed(d)}–${(high / 1e9).toFixed(d)} bn`;
    }
    return `$${Math.round(low / 1e6)}–${Math.round(high / 1e6)}m`;
}

function fmtBarrels(n) {
    return n >= 1e6 ? (n / 1e6).toFixed(1) + "m" : Math.round(n / 1e3) + "k";
}

function vesselName(v) {
    return titleCase(v.current_name || v.name);
}

// ── Map ─────────────────────────────────────────────────────
// MapLibre GL on a globe. Vessels and events are GeoJSON sources drawn on
// the canvas; the rail floats over the right of the map, so the camera is
// padded to keep targets in the visible part.

const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/";
const tiles = (path, maxzoom = 19) => ({ type: "raster", tiles: [`${ESRI}${path}/MapServer/tile/{z}/{y}/{x}`], tileSize: 256, maxzoom });
const MARK = { hazard: "#ff4fa3", light: "#f4f7f8", dark: "#0b151c", radar: "#7fd8ff" };
const BASEMAPS = { satellite: ["sat", "sat-labels"], dark: ["dark", "dark-labels"] };

const map = new maplibregl.Map({
    container: "map",
    center: HOME.center,
    zoom: HOME.zoom,
    minZoom: 1,
    maxZoom: 17.5,
    attributionControl: { compact: true },
    style: {
        version: 8,
        projection: { type: "globe" },
        sky: {
            "sky-color": "#06121b", "horizon-color": "#1d4a63", "fog-color": "#0a1a24",
            "sky-horizon-blend": 0.6, "horizon-fog-blend": 0.5, "fog-ground-blend": 0.4,
            "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 1, 8, 0],
        },
        sources: {
            sat: { ...tiles("World_Imagery"), attribution: "Imagery: Esri, Maxar, Earthstar Geographics" },
            "sat-labels": tiles("Reference/World_Boundaries_and_Places"),
            dark: { ...tiles("Canvas/World_Dark_Gray_Base", 16), attribution: "Esri, HERE, Garmin" },
            "dark-labels": tiles("Canvas/World_Dark_Gray_Reference", 16),
        },
        layers: [
            { id: "space", type: "background", paint: { "background-color": "#050c12" } },
            { id: "sat", type: "raster", source: "sat", paint: { "raster-saturation": -0.15, "raster-contrast": 0.05 } },
            { id: "sat-labels", type: "raster", source: "sat-labels", paint: { "raster-opacity": 0.75 } },
            { id: "dark", type: "raster", source: "dark", layout: { visibility: "none" } },
            { id: "dark-labels", type: "raster", source: "dark-labels", layout: { visibility: "none" } },
        ],
    },
});
map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
const mapReady = new Promise((resolve) => map.on("load", resolve));
// Requests cut off by leaving the page are not errors; report anything else.
let leaving = false;
window.addEventListener("pagehide", () => (leaving = true));
window.addEventListener("beforeunload", () => (leaving = true));
map.on("error", (e) => leaving || console.error(e.error || e));

// Legend swatch and map symbol for each event kind; one source for both.
const KIND_SWATCH = { port_visit: "square", loitering: "ring", gap: "ring-dashed", encounter: "diamond", sar: "cross" };

// Draw each event symbol once on a canvas, matching the CSS swatches in the key.
function addEventIcons() {
    const px = 2, size = 16;
    const draw = (name, paint) => {
        const c = document.createElement("canvas");
        c.width = c.height = size * px;
        const g = c.getContext("2d");
        g.scale(px, px);
        g.translate(size / 2, size / 2);
        paint(g);
        map.addImage(name, g.getImageData(0, 0, c.width, c.height), { pixelRatio: px });
    };
    const halo = (g, w) => { g.lineWidth = w + 2; g.strokeStyle = "rgba(5,12,18,0.75)"; g.stroke(); };
    draw("square", (g) => { g.fillStyle = MARK.light; g.strokeStyle = MARK.dark; g.lineWidth = 1.5; g.fillRect(-4, -4, 8, 8); g.strokeRect(-4, -4, 8, 8); });
    draw("ring", (g) => { g.beginPath(); g.arc(0, 0, 5, 0, 2 * Math.PI); halo(g, 2.2); g.lineWidth = 2.2; g.strokeStyle = MARK.hazard; g.stroke(); });
    draw("ring-dashed", (g) => { g.beginPath(); g.arc(0, 0, 5, 0, 2 * Math.PI); halo(g, 1.6); g.setLineDash([2, 2]); g.lineWidth = 1.6; g.strokeStyle = MARK.light; g.stroke(); });
    draw("diamond", (g) => { g.rotate(Math.PI / 4); g.fillStyle = MARK.dark; g.strokeStyle = MARK.hazard; g.lineWidth = 2; g.fillRect(-4, -4, 8, 8); g.strokeRect(-4, -4, 8, 8); });
    draw("cross", (g) => { g.beginPath(); g.moveTo(-6, 0); g.lineTo(6, 0); g.moveTo(0, -6); g.lineTo(0, 6); halo(g, 2); g.lineWidth = 2; g.strokeStyle = MARK.radar; g.stroke(); });
}

const EMPTY = { type: "FeatureCollection", features: [] };
const point = (lon, lat, props) => ({ type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: props });

function addDataLayers() {
    addEventIcons();
    map.addSource("corridors", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "corridors", type: "line", source: "corridors",
        paint: { "line-color": MARK.radar, "line-width": 1, "line-opacity": 0.4, "line-dasharray": [3, 2] } });
    map.addSource("events", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "events", type: "symbol", source: "events",
        layout: { "icon-image": ["get", "icon"], "icon-allow-overlap": true, "icon-ignore-placement": true },
        paint: { "icon-opacity": ["case", ["get", "dim"], 0.3, 1] } });
    map.addSource("vessels", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "vessel-glow", type: "circle", source: "vessels", filter: ["get", "high"],
        paint: { "circle-radius": 11, "circle-color": MARK.hazard, "circle-blur": 1, "circle-opacity": 0.55 } });
    map.addLayer({ id: "vessels", type: "circle", source: "vessels",
        paint: {
            "circle-radius": ["case", ["get", "high"], 5.5, 4.5],
            "circle-color": ["case", ["get", "high"], MARK.hazard, MARK.light],
            "circle-stroke-color": ["case", ["get", "high"], MARK.light, MARK.dark],
            "circle-stroke-width": 1.5,
        } });

    const tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: "map-tip" });
    for (const id of ["vessels", "events"]) {
        map.on("mousemove", id, (e) => {
            const f = e.features[0];
            map.getCanvas().style.cursor = f.properties.imo ? "pointer" : "";
            tip.setLngLat(f.geometry.coordinates).setHTML(f.properties.tip).addTo(map);
        });
        map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; tip.remove(); });
        map.on("click", id, (e) => {
            const imo = e.features[0].properties.imo;
            if (imo) openDossier(String(imo));
        });
    }
}

function setBasemap(name) {
    for (const [key, ids] of Object.entries(BASEMAPS)) {
        for (const id of ids) map.setLayoutProperty(id, "visibility", key === name ? "visible" : "none");
    }
    document.querySelectorAll("#basemap button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.base === name)));
}

// Keep camera targets clear of the floating rail and bottom panel on wide screens.
// The padding rides along with each camera move (see motion()): map.setPadding()
// would jump the camera and cancel a flight in progress.
const WIDE = window.matchMedia("(min-width: 861px)");
let PAD = { top: 0, left: 0, right: 0, bottom: 0 };
function padMap() {
    const panel = ["lens", "gallery", "replay"].map($).find((el) => !el.hidden);
    PAD = WIDE.matches
        ? { top: 50, left: 0, right: $("rail").offsetWidth + 24, bottom: panel ? panel.offsetHeight + 12 : 0 }
        : { top: 0, left: 0, right: 0, bottom: 0 };
}

function motion(ms = 2400) {
    return { duration: REDUCED_MOTION.matches ? 0 : ms, essential: true, padding: PAD };
}

function go(lon, lat, zoom, opts = {}) {
    map.flyTo({ center: [lon, lat], zoom, pitch: 0, bearing: 0, ...motion(opts.ms), ...opts });
}

function goHome() {
    go(HOME.center[0], HOME.center[1], HOME.zoom);
}

function eventFeature(e, props) {
    return point(e.lon, e.lat, { icon: KIND_SWATCH[e.kind], kind: e.kind, dim: false, ...props });
}

function setEvents(features) {
    map.getSource("events")?.setData({ type: "FeatureCollection", features });
}

function showFleet(on) {
    for (const id of ["vessels", "vessel-glow"]) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
}

function fleetShown() {
    return map.getLayoutProperty("vessels", "visibility") !== "none";
}

// Dim every vessel but one (or none, with imo = null).
function focusVessel(imo) {
    const op = imo ? ["case", ["==", ["get", "imo"], imo], 1, 0.25] : 1;
    map.setPaintProperty("vessels", "circle-opacity", op);
    map.setPaintProperty("vessels", "circle-stroke-opacity", op);
    map.setPaintProperty("vessel-glow", "circle-opacity", imo ? ["case", ["==", ["get", "imo"], imo], 0.55, 0.1] : 0.55);
}

function setEventKey(kinds) {
    const order = ["port_visit", "loitering", "gap", "encounter", "sar"];
    $("key-events").innerHTML = order.filter((k) => kinds.has(k))
        .map((k) => `<span><i class="${KIND_SWATCH[k]}"></i>${esc(GF.KINDS[k].label)}</span>`).join("");
}

function drawVessels() {
    map.getSource("vessels").setData({
        type: "FeatureCollection",
        features: vessels.filter((v) => v._lat != null).map((v) => point(v._lng, v._lat, {
            imo: v.imo,
            high: v.risk_score >= HIGH_RISK,
            tip: `<b>${esc(vesselName(v))}</b><br>Score ${v.risk_score} · last seen ${fmtDate(v.last_seen)}`,
        })),
    });
    if (!sar) return;
    map.getSource("corridors").setData({
        type: "FeatureCollection",
        features: sar.coverage.corridors.map(({ id, bbox: [w, s, e, n] }) => ({
            type: "Feature", properties: { id },
            geometry: { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] },
        })),
    });
}

function drawTrack(v) {
    const pts = v.events.filter(GF.isPositioned);
    if (!pts.length) return clearTrack();
    // Points only: events are sparse snapshots, and a line between them
    // would imply a route (often straight across land) the ship never sailed.
    setEvents(pts.map((e) => eventFeature(e, { tip: `${fmtDate(e.start)}<br>${esc(eventLabel(e))}` })));
    focusVessel(v.imo);
    setEventKey(new Set(pts.map((e) => e.kind)));
    document.body.classList.add("tracking");
    $("key-mode").textContent = `${vesselName(v)}: dated events`;
    const b = new maplibregl.LngLatBounds();
    for (const e of pts) b.extend([e.lon, e.lat]);
    const m = motion();
    const padding = Object.fromEntries(Object.entries(m.padding).map(([k, x]) => [k, x + 60]));
    map.fitBounds(b, { maxZoom: 6, pitch: 0, bearing: 0, ...m, padding });
}

function clearTrack() {
    focusVessel(null);
    document.body.classList.remove("tracking");
    if (!replay.on) {
        setEvents([]);
        setEventKey(new Set());
        $("key-mode").textContent = "Latest positions";
    }
}

// ── Historical evidence replay ──────────────────────────────

function openReplay() {
    if (!replay.index || !replay.index.months.length) return;
    radarClear();
    closeGallery();
    replay.on = true;
    clearTrack();
    showFleet(false);
    document.body.classList.add("replaying");
    $("replay").hidden = false;
    $("replay-open").hidden = true;
    $("replay-open").setAttribute("aria-expanded", "true");
    padMap();
    go(48, 26, 2.4);
    setReplay(replay.index.months.length - 1);
    $("replay-slider").focus();
}

function closeReplay() {
    stopReplay();
    replay.on = false;
    setEvents([]);
    showFleet(true);
    document.body.classList.remove("replaying");
    $("replay").hidden = true;
    $("replay-open").hidden = false;
    $("replay-open").setAttribute("aria-expanded", "false");
    padMap();
    renderList($("vessel-search").value);
    const v = selectedImo && byImo.get(selectedImo);
    if (v && v._lat != null) {
        drawTrack(v);
        radarDossier(v);
    } else {
        clearTrack();
        goHome();
    }
    $("replay-open").focus();
}

function setReplay(i) {
    const { months, observations, partial } = replay.index;
    replay.i = Math.max(0, Math.min(months.length - 1, i));
    const ym = months[replay.i];
    const obs = observations(ym);
    const sum = GF.summarise(obs);

    replay.imos = sum.imos;
    replay.perVessel = new Map();
    for (const o of obs) {
        const counts = replay.perVessel.get(o.imo) || {};
        counts[o.kind] = (counts[o.kind] || 0) + 1;
        replay.perVessel.set(o.imo, counts);
    }

    const slider = $("replay-slider");
    slider.value = replay.i;
    slider.setAttribute("aria-valuetext", fmtMonthLong(ym));
    $("replay-prev").disabled = replay.i === 0;
    $("replay-next").disabled = replay.i === months.length - 1;
    $("replay-latest").disabled = replay.i === months.length - 1;

    let note = "";
    if (partial(ym)) {
        note = ym === snapshot.window.start.slice(0, 7)
            ? ` (partial: the snapshot starts ${fmtDate(snapshot.window.start)})`
            : ` (partial: the snapshot ends ${fmtDate(snapshot.window.end)})`;
    }
    $("replay-period").innerHTML = `${esc(fmtMonthLong(ym))}<small>${esc(note)}</small>`;
    $("replay-counts").innerHTML = sum.count
        ? `<b>${plural(sum.count, "observation")}</b> from <b>${plural(sum.vessels, "vessel")}</b>` +
          ` <span class="replay-kinds">${Object.keys(GF.KINDS).filter((k) => sum.byKind[k])
              .map((k) => `${sum.byKind[k].toLocaleString("en-GB")} ${GF.KINDS[k].plural}`).join(" · ")}` +
          `${sum.count > sum.began ? ` · ${plural(sum.count - sum.began, "began earlier", "began earlier")}` : ""}</span>`
        : "No positioned observations recorded in this month.";

    drawReplayMarkers(obs);
    setEventKey(new Set(Object.keys(sum.byKind)));
    $("key-mode").textContent = `Recorded in ${fmtMonthShort(ym)}`;
    if ($("view-dossier").hidden) renderList($("vessel-search").value);
}

function drawReplayMarkers(obs) {
    const features = obs.map((o) => {
        const v = byImo.get(o.imo);
        const e = o.radar ? { kind: "sar", start: o.start, end: o.end, lat: o.lat, lon: o.lon } : v.events[o.index];
        const range = e.end && e.end.slice(0, 10) !== e.start.slice(0, 10)
            ? `${fmtDate(e.start)} – ${fmtDate(e.end)}` : fmtDate(e.start);
        return eventFeature(e, {
            imo: o.imo,
            dim: Boolean(selectedImo && o.imo !== selectedImo),
            tip: `<b>${esc(vesselName(v))}</b><br>${esc(eventLabel(e))}<br>${range}` +
                (o.began ? "" : "<br><i>Began before this month</i>"),
        });
    });
    // Later features draw on top: put the selected vessel's marks last.
    features.sort((a, b) => Number(b.properties.dim) - Number(a.properties.dim));
    setEvents(features);
    replay.drawn = features.length;
}

function playReplay() {
    const last = replay.index.months.length - 1;
    if (replay.i >= last) setReplay(0);
    $("replay-play").textContent = "Pause";
    $("replay-play").setAttribute("aria-pressed", "true");
    $("replay-status").setAttribute("aria-live", "off"); // don't announce every step while playing
    replay.timer = setInterval(() => {
        if (replay.i >= last) return stopReplay();
        setReplay(replay.i + 1);
    }, replay.speed || (REDUCED_MOTION.matches ? 2500 : 1500));
}

function stopReplay() {
    clearInterval(replay.timer);
    replay.timer = null;
    $("replay-play").textContent = "Play";
    $("replay-play").setAttribute("aria-pressed", "false");
    $("replay-status").setAttribute("aria-live", "polite");
}

function stepReplay(delta) {
    stopReplay();
    setReplay(replay.i + delta);
}

// ── Monitor view ────────────────────────────────────────────

function renderMonitor(signal, meta) {
    $("snapshot").textContent =
        `Snapshot of ${fmtDate(meta.window.start)} – ${fmtDate(meta.window.end)}, built ${fmtDate(meta.generated)}`;

    const trend = signal.activity_trend_3m_pct;
    if (trend == null) {
        $("headline").textContent = "Not enough months of data yet to call a trend.";
    } else {
        const dir = trend < 0 ? "fell" : "rose";
        $("headline").textContent =
            `Sanctioned tanker activity ${dir} ${Math.abs(trend).toFixed(0)}% in the last three months.`;
    }
    renderTrend(signal.monthly);

    const ports = signal.monthly.reduce((n, m) => n + m.port_visits, 0);
    $("fig-tracked").textContent = `${signal.vessels_located} of ${signal.vessels_screened}`;
    $("fig-high").textContent = signal.high_risk_vessels;
    $("fig-ports").textContent = ports.toLocaleString("en-GB");
    const known = vessels.filter((v) => v.cargo_status !== "UNKNOWN").length;
    $("fig-cargo").textContent = `${known} of ${vessels.length}`;
    $("fig-cargo-note").textContent = known
        ? "Estimated from draft readings where available."
        : "Public tracking data has no draft readings, so no vessel's load is inferred.";
    const flow = signal.est_annual_flow_usd;
    $("fig-value").textContent = `${fmtUsdRange(flow.low, flow.high)} a year`;
    $("fig-value-note").textContent =
        `Upper bound for the ${signal.high_risk_vessels} vessels scored ${HIGH_RISK}+: hull capacity × estimated voyages × ` +
        `Brent at $${signal.brent_crude_usd}. Loaded state is not observed, so real cargo is lower.`;

    renderPorts(signal.top_ports);
    renderList("");
}

function renderTrend(series) {
    const svg = $("trend-svg");
    const w = svg.clientWidth || 350, h = 96, top = 16, base = h - 18;
    const max = Math.max(...series.map((m) => m.active_vessels), 1);
    const bw = w / series.length;
    const n = series.length;
    // The headline compares the last 3 full months (n-4..n-2) with the 3 before.
    const recent = new Set([n - 4, n - 3, n - 2]);
    const prior = new Set([n - 7, n - 6, n - 5]);

    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.innerHTML = series.map((m, i) => {
        const bh = ((base - top) * m.active_vessels) / max;
        const cls = recent.has(i) ? "bar recent" : prior.has(i) ? "bar prior" : "bar";
        const x = i * bw + 2;
        return `<rect class="${cls}" x="${x}" y="${base - bh}" width="${bw - 4}" height="${bh}"><title>${fmtMonth(m.month)}: ${m.active_vessels} tankers</title></rect>` +
            (recent.has(i) || prior.has(i) ? `<text class="value" x="${x + (bw - 4) / 2}" y="${base - bh - 4}" text-anchor="middle">${m.active_vessels}</text>` : "") +
            `<text x="${x + (bw - 4) / 2}" y="${h - 4}" text-anchor="middle">${fmtMonth(m.month).slice(0, 1)}</text>`;
    }).join("");
    $("trend-caption").textContent =
        `Tankers with recorded activity each month, ${fmtMonth(series[0].month)} to ${fmtMonth(series[n - 1].month)}. ` +
        `The headline compares the bright bars with the grey ones. The latest month is incomplete.`;
}

function renderPorts(topPorts) {
    $("port-list").innerHTML = topPorts
        .map((p) => `<li><span>${esc(titleCase(p.port))}</span><span>${p.calls}</span></li>`).join("");
}

function replayMeta(imo) {
    const counts = replay.perVessel.get(imo) || {};
    return Object.keys(GF.KINDS).filter((k) => counts[k])
        .map((k) => `${counts[k]} ${counts[k] === 1 ? GF.KINDS[k].one : GF.KINDS[k].plural}`).join(" · ");
}

function renderList(query) {
    const q = query.trim().toLowerCase();
    const pool = replay.on ? vessels.filter((v) => replay.imos.has(v.imo)) : vessels;
    const rows = pool.filter((v) => !q || v.imo.includes(q) ||
        v.identity_history.some((h) => (h.name || "").toLowerCase().includes(q)) ||
        String(v.name).toLowerCase().includes(q));

    $("vessels-title").textContent = replay.on
        ? `Vessels with observations in ${fmtMonthLong(replay.index.months[replay.i])} (${pool.length})`
        : "Vessels";

    let empty = `No vessel matches “${esc(query)}”. Try a former name or the 7-digit IMO.`;
    if (replay.on && !pool.length) empty = "No vessel has a positioned observation in this month.";
    else if (replay.on) empty = `No vessel observed this month matches “${esc(query)}”.`;

    $("vessel-list").innerHTML = rows.length ? rows.map((v) => `
        <li><button type="button" data-imo="${esc(v.imo)}">
            <span class="v-name">${esc(vesselName(v))}</span>
            <span class="v-score ${v.risk_score >= HIGH_RISK ? "high" : ""}" aria-label="Score ${v.risk_score}">${v.risk_score}</span>
            <span class="v-meta">IMO ${esc(v.imo)} · ${replay.on ? esc(replayMeta(v.imo))
                : `${esc(flagName(v.current_flag))} · ${v.identity_changes} identity switches${v._lat == null ? ' · <span class="v-nopos">No recent position</span>' : ""}`}</span>
        </button></li>`).join("")
        : `<li class="empty">${empty}</li>`;
}

// ── Dossier view ────────────────────────────────────────────

function renderScore(v) {
    const score = $("d-score");
    score.textContent = v.risk_score;
    score.className = "score-number" + (v.risk_score >= HIGH_RISK ? " high" : "");
    const b = v.risk_breakdown;
    const parts = SCORE_PARTS.filter((p) => b[p.key] > 0);
    const bar = $("d-bar");
    bar.innerHTML = parts
        .map((p) => `<span style="width:${b[p.key]}%;background:${p.color}" title="${p.label}: ${b[p.key]}"></span>`).join("");
    bar.setAttribute("role", "img");
    bar.setAttribute("aria-label", `Score ${v.risk_score} of 100: ` + parts.map((p) => `${p.label} ${b[p.key]}`).join(", "));
    $("d-sum").textContent = parts.length
        ? parts.map((p) => `${p.label} ${b[p.key]}`).join(" + ") + ` = ${v.risk_score}. A screening score, not a finding of wrongdoing.`
        : "No scored evidence.";
}

function renderMatrix(v) {
    const { rows, total, matchesScore } = GF.evidenceRows(v, snapshot.window, sar);
    const cell = (r) => {
        if (r.sharedWith) return "";
        const span = r.span ? ` rowspan="${r.span}"` : "";
        if (r.points == null) return `<td class="pts"${span}><span class="pts-none">Not scored</span></td>`;
        return `<td class="pts"${span}><b class="${r.points ? "" : "pts-zero"}">${r.points ? "+" + r.points : "0"}</b></td>`;
    };
    $("d-matrix").tBodies[0].innerHTML = rows.map((r) => `
        <tr class="row-${esc(r.key)}${r.span ? " row-shared" : ""}${r.sharedWith ? " row-shared-end" : ""}">
            <th scope="row">
                <span class="ev-label">${esc(r.label)}</span>
                <span class="ev-detail">${esc(r.detail)}</span>
                <span class="ev-source">Source: ${esc(r.source)}${r.rule ? ` · Scoring: ${esc(r.rule)}` : ""}</span>
                ${r.image ? `<figure class="ev-figure"><img src="${esc(r.image)}" width="288" height="288" loading="lazy"
                    alt="${esc(r.caption)}"><figcaption>${esc(r.caption)}</figcaption></figure>
                    <button type="button" class="ev-map" data-radar-pass>See it on the satellite map</button>` : ""}
                ${r.lists && r.lists.length ? `<details class="ev-lists"><summary>Show the ${r.lists.length} source lists</summary>
                    <ul>${r.lists.map((l) => `<li><code>${esc(l)}</code></li>`).join("")}</ul></details>` : ""}
            </th>
            <td><span class="status st-${r.status.key}">${esc(r.status.label)}</span></td>
            ${cell(r)}
        </tr>`).join("");
    $("d-matrix").onclick = (ev) => {
        const m = ev.target.closest("[data-radar-pass]") && sar?.vessels[v.imo]?.our_match;
        if (m) showPass(v.imo, m.pass);
    };
    $("d-total").innerHTML = matchesScore
        ? `<b>${total}</b>`
        : `<b>${v.risk_score}</b> <span class="pts-none">(rows sum to ${total})</span>`;
}

function renderSources(v) {
    const n = String(v.sanction_programs || "").split(";").filter(Boolean).length;
    const links = [];
    if (v.opensanctions_url) links.push(`<a class="source-link" href="${esc(v.opensanctions_url)}" target="_blank" rel="noopener">See the listings on OpenSanctions<span class="visually-hidden"> (opens in a new tab)</span></a>`);
    if (v.gfw_vessel_id) links.push(`<a class="source-link" href="https://globalfishingwatch.org/map/vessel/${encodeURIComponent(v.gfw_vessel_id)}" target="_blank" rel="noopener">View on Global Fishing Watch<span class="visually-hidden"> (opens in a new tab)</span></a>`);
    $("d-sources").innerHTML = `Named on ${n} lists. ${links.join(" ")}`;
}

function openDossier(imo) {
    const v = byImo.get(imo);
    if (!v) return;
    selectedImo = imo;
    if (location.hash !== "#imo=" + imo) history.replaceState(null, "", "#imo=" + imo);

    $("d-name").textContent = vesselName(v);
    const flag = v.current_flag;
    $("d-now").textContent = v.last_seen
        ? `IMO ${v.imo}. Now flagged to ${flagName(flag)}${LANDLOCKED.has(flag) ? ", a landlocked country" : ""}. Last seen ${fmtDate(v.last_seen)}.`
        : `IMO ${v.imo}. No position recorded in this window.`;

    renderScore(v);
    renderMatrix(v);
    renderSources(v);

    const ais = v.identity_history.filter((h) => h.source === "AIS");
    $("d-identities").innerHTML = ais.length ? ais.map((h) => `
        <li><span class="id-name">${esc(titleCase(h.name))}</span>
        <span class="id-meta">${esc(flagName(h.flag))} · MMSI ${esc(h.mmsi)} · ${fmtDate(h.from)} – ${fmtDate(h.to)}</span></li>`).join("")
        : `<li class="empty">No AIS identity found for this IMO.</li>`;

    const recent = v.events.slice(-12).reverse();
    $("d-events").innerHTML = recent.length ? recent.map((e, i) => `
        <li><time datetime="${esc(e.start)}">${fmtDate(e.start)}</time>
        ${GF.isPositioned(e) ? `<button type="button" data-event="${i}" aria-label="${esc(eventLabel(e))}, show on map">${esc(eventLabel(e))}</button>` : esc(eventLabel(e))}</li>`).join("")
        : `<li class="empty">No loitering, port calls or AIS gaps with a date and position recorded in this window.</li>`;
    $("d-events").onclick = (ev) => {
        const i = ev.target.closest("button[data-event]")?.dataset.event;
        if (i != null) go(recent[i].lon, recent[i].lat, 7);
    };

    const cap = v.est_cargo_barrels, flow = v.est_annual_flow_usd;
    $("d-size").textContent =
        `Carries about ${fmtBarrels(cap.low)}–${fmtBarrels(cap.high)} barrels per load (from ${cap.basis}). ` +
        `At ${flow.voyages_per_year[0]}–${flow.voyages_per_year[1]} loaded voyages a year, that is ` +
        `${fmtUsdRange(flow.low, flow.high)} of oil a year if every voyage sailed full.`;
    $("d-cargo").textContent = v.cargo_status === "UNKNOWN"
        ? "unknown. Public data has no draft reading, so we do not guess whether it is loaded."
        : `${v.cargo_status.toLowerCase()} (${Math.round(v.cargo_confidence * 100)}% confidence)`;

    $("view-monitor").hidden = true;
    $("view-dossier").hidden = false;
    $("rail").scrollTop = 0;
    if (replay.on) drawReplayMarkers(replay.index.observations(replay.index.months[replay.i]));
    else if (v._lat != null) drawTrack(v);
    else clearTrack();
    if (!replay.on) radarDossier(v);
    $("d-name").focus({ preventScroll: true });
}

function closeDossier() {
    selectedImo = null;
    history.replaceState(null, "", location.pathname + location.search);
    $("view-dossier").hidden = true;
    $("view-monitor").hidden = false;
    radarClear();
    if (replay.on) {
        setReplay(replay.i);
    } else {
        clearTrack();
        goHome();
    }
    const back = lastTrigger && document.querySelector(`#vessel-list button[data-imo="${lastTrigger}"]`);
    (back || $("vessel-search")).focus({ preventScroll: !back });
}

// ── Boot ────────────────────────────────────────────────────

function openFromHash() {
    const m = location.hash.match(/imo=(\d{7})(?:&pass=(\d+))?/);
    if (!m || !byImo.has(m[1])) return;
    if (m[1] !== selectedImo || $("view-dossier").hidden) openDossier(m[1]);
    if (m[2] != null) showPass(m[1], Number(m[2]));
}

async function load() {
    try {
        const [vr, sr] = await Promise.all([fetch(DATA_URL), fetch(SIGNAL_URL)]);
        if (!vr.ok || !sr.ok) throw new Error(`HTTP ${vr.status}/${sr.status}`);
        snapshot = await vr.json();
        const signal = await sr.json();
        sar = await fetch(SAR_URL).then((r) => (r.ok ? r.json() : null)).catch(() => null);
        vessels = snapshot.vessels;
        byImo = new Map(vessels.map((v) => [v.imo, v]));
        await mapReady;
        addDataLayers();
        padMap();
        map.setPadding(PAD);
        drawVessels();
        renderMonitor(signal, snapshot);

        replay.index = GF.replayIndex(vessels, snapshot.window, sar);
        const { months } = replay.index;
        if (months.length) {
            const slider = $("replay-slider");
            slider.max = months.length - 1;
            $("replay-first").textContent = fmtMonthShort(months[0]);
            $("replay-last").textContent = fmtMonthShort(months[months.length - 1]);
            $("replay-open").hidden = false;
        }
        openFromHash();
        document.body.classList.add("ready");
        document.dispatchEvent(new Event("gf:ready"));
    } catch (err) {
        $("headline").textContent = "The snapshot could not be loaded.";
        $("view-monitor").insertAdjacentHTML("afterbegin",
            `<p class="status-msg">Could not read ${DATA_URL} (${esc(err.message)}). Serve the dashboard folder over HTTP, ` +
            `for example <code>python -m http.server</code>, and run the pipeline if the data files are missing.</p>`);
    } finally {
        $("rail").removeAttribute("aria-busy");
    }
}

$("vessel-search").addEventListener("input", (e) => renderList(e.target.value));
$("vessel-list").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-imo]");
    if (!btn) return;
    lastTrigger = btn.dataset.imo;
    openDossier(btn.dataset.imo);
});
$("btn-back").addEventListener("click", closeDossier);
$("replay-open").addEventListener("click", openReplay);
$("replay-exit").addEventListener("click", closeReplay);
$("replay-prev").addEventListener("click", () => stepReplay(-1));
$("replay-next").addEventListener("click", () => stepReplay(1));
$("replay-latest").addEventListener("click", () => { stopReplay(); setReplay(replay.index.months.length - 1); });
$("replay-play").addEventListener("click", () => (replay.timer ? stopReplay() : playReplay()));
$("replay-slider").addEventListener("input", (e) => { stopReplay(); setReplay(Number(e.target.value)); });
$("replay-skip").addEventListener("click", (e) => {
    e.preventDefault();
    if (!$("view-dossier").hidden) closeDossier();
    const first = document.querySelector("#vessel-list button") || $("vessel-search");
    first.scrollIntoView({ block: "center", ...(REDUCED_MOTION.matches ? {} : { behavior: "smooth" }) });
    first.focus({ preventScroll: true });
});
$("basemap").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-base]");
    if (b) setBasemap(b.dataset.base);
});
WIDE.addEventListener("change", padMap);
window.addEventListener("resize", padMap);
window.addEventListener("hashchange", openFromHash);
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("view-dossier").hidden && !document.body.classList.contains("touring")) closeDossier();
});

load();
