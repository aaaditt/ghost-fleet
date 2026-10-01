/* Ghost Fleet — radar lens, per-ship time-lapse and fleet radar gallery.
   Drapes Sentinel-1 radar images (data/radar_passes.json, built by
   `python -m ml.build`) on the globe at their true position, with the target
   our model matched to the ship. Targets are model estimates, never proof.
   Uses the globals of app.js (map, byImo, selectedImo, openDossier, …). */

const PASSES_URL = "data/radar_passes.json";
const lens = { data: null, loading: null, imo: null, i: -1, timer: null, blink: null, mix: 0.9, ring: null, spot: null };

function loadPasses() {
    lens.loading ||= fetch(PASSES_URL).then((r) => (r.ok ? r.json() : null)).catch(() => null)
        .then((d) => (lens.data = d));
    return lens.loading;
}

function passesOf(imo) {
    return lens.data?.vessels?.[imo] || [];
}

function fmtPassDate(p) {
    return `${fmtDate(p.date)} · ${p.time} UTC`;
}

const pct = (x) => `${Math.round(x * 100)}%`;

// ── Map layers ──────────────────────────────────────────────

function radarLayers(p) {
    const box = { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[...p.corners, p.corners[0]]] } };
    if (map.getSource("radar")) {
        map.getSource("radar").updateImage({ url: p.image, coordinates: p.corners });
        map.getSource("radar-box").setData(box);
        return;
    }
    map.addSource("radar", { type: "image", url: p.image, coordinates: p.corners });
    map.addLayer({ id: "radar", type: "raster", source: "radar",
        paint: { "raster-opacity": lens.mix, "raster-fade-duration": 0, "raster-resampling": "linear" } }, "events");
    map.addSource("radar-box", { type: "geojson", data: box });
    map.addLayer({ id: "radar-box", type: "line", source: "radar-box",
        paint: { "line-color": MARK.radar, "line-width": 1.5, "line-opacity": 0.9 } }, "events");
}

function marker(cls, title) {
    const el = document.createElement("div");
    el.className = cls;
    el.title = title;
    return new maplibregl.Marker({ element: el });
}

function setMix(x) {
    lens.mix = x;
    if (map.getLayer("radar")) map.setPaintProperty("radar", "raster-opacity", x);
}

// ── Lens ────────────────────────────────────────────────────

// Called by openDossier: offer the radar passes for this vessel, if any.
function radarDossier(v) {
    radarClear();
    loadPasses().then(() => {
        if (selectedImo !== v.imo || replay.on) return;
        const ps = passesOf(v.imo);
        if (!ps.length) return;
        lens.imo = v.imo;
        renderLensShell(v, ps);
        $("lens").hidden = false;
        $("lens").classList.add("teaser");
        padMap();
    });
}

function renderLensShell(v, ps) {
    const conf = ps.filter((p) => p.confident).length;
    $("lens").innerHTML = `
        <div class="lens-head">
            <h2 id="lens-title"><span class="lens-eyebrow">Sentinel-1 radar</span> ${esc(vesselName(v))}</h2>
            <button type="button" class="lens-close" id="lens-close" aria-label="Close the radar lens">&times;</button>
        </div>
        <div class="lens-teaser">
            <p>${plural(ps.length, "radar pass", "radar passes")} near this ship's loitering positions, ${conf} with a confident match.</p>
            <button type="button" class="lens-go" id="lens-go">Fly to the radar image</button>
        </div>
        <div class="lens-body">
            <p class="lens-when" id="lens-when"></p>
            <p class="lens-facts" id="lens-facts"></p>
            <div class="lens-controls">
                <label class="lens-mix">
                    <span>Optical</span>
                    <input type="range" id="lens-mix" min="0" max="100" value="${Math.round(lens.mix * 100)}" aria-label="Radar image opacity">
                    <span>Radar</span>
                </label>
                <button type="button" id="lens-blink" aria-pressed="false">Blink</button>
                <span class="lens-steps">
                    <button type="button" id="lens-prev" aria-label="Previous radar pass">&#8249;</button>
                    <button type="button" id="lens-play" class="lens-play" aria-pressed="false">Play passes</button>
                    <button type="button" id="lens-next" aria-label="Next radar pass">&#8250;</button>
                </span>
            </div>
            <ol class="lens-strip" id="lens-strip" aria-label="Radar passes">${ps.map((p, i) => `
                <li><button type="button" data-pass="${i}" aria-label="Pass ${i + 1}: ${esc(fmtPassDate(p))}, match ${pct(p.target.posterior)}">
                    <img src="${esc(p.image)}" width="64" height="64" loading="lazy" alt="">
                    <span>${esc(fmtDate(p.date))}</span>
                    <i class="${p.confident ? "conf" : "unsure"}" aria-hidden="true"></i>
                </button></li>`).join("")}
            </ol>
            <p class="lens-note">Sentinel-1 VV radar backscatter: 10 m pixels, 3.2 km across, draped at its true position.
                Bright means a strong echo, typically a steel hull. <b class="k-ring">Ring</b>: the target our model matched to this ship.
                <b class="k-spot">Dot</b>: the loitering position from AIS. <span id="lens-scene"></span></p>
        </div>`;
    $("lens-close").onclick = () => radarClear();
    $("lens-go").onclick = () => showPass(v.imo, sar?.vessels[v.imo]?.our_match?.pass ?? 0);
    $("lens-mix").oninput = (e) => { stopBlink(); setMix(e.target.value / 100); };
    $("lens-blink").onclick = () => (lens.blink ? stopBlink() : startBlink());
    $("lens-prev").onclick = () => { stopLensPlay(); showPass(lens.imo, lens.i - 1, { ms: 1400 }); };
    $("lens-next").onclick = () => { stopLensPlay(); showPass(lens.imo, lens.i + 1, { ms: 1400 }); };
    $("lens-play").onclick = () => (lens.timer ? stopLensPlay() : playPasses());
    $("lens-strip").onclick = (e) => {
        const b = e.target.closest("button[data-pass]");
        if (b) { stopLensPlay(); showPass(lens.imo, Number(b.dataset.pass), { ms: 1400 }); }
    };
}

// Show one radar pass: drape the image, ring the target, fly the camera in.
async function showPass(imo, i, opts = {}) {
    await loadPasses();
    const ps = passesOf(imo);
    if (!ps.length || replay.on) return false;
    i = Math.max(0, Math.min(ps.length - 1, i));
    const p = ps[i];
    if (lens.imo !== imo || !$("lens").innerHTML) {
        lens.imo = imo;
        renderLensShell(byImo.get(imo), ps);
    }
    lens.i = i;
    closeGallery();
    radarLayers(p);
    (lens.ring ||= marker("radar-ring", "Radar target matched to this ship (model estimate)")).setLngLat([p.target.lon, p.target.lat]).addTo(map);
    (lens.spot ||= marker("radar-spot", "Loitering position from AIS")).setLngLat([p.event.lon, p.event.lat]).addTo(map);
    lens.ring.getElement().classList.remove("pulse");
    void lens.ring.getElement().offsetWidth; // restart the pulse
    lens.ring.getElement().classList.add("pulse");

    $("lens").hidden = false;
    $("lens").classList.remove("teaser");
    padMap();
    const near = map.getZoom() > 11 && map.getCenter().distanceTo(new maplibregl.LngLat(p.target.lon, p.target.lat)) < 4000;
    if (opts.fly !== false) {
        map.flyTo({ center: [p.target.lon, p.target.lat], zoom: opts.zoom ?? 14.2, pitch: opts.pitch ?? 48, bearing: opts.bearing ?? -12,
            ...motion(near ? 900 : (opts.ms ?? 4200)) });
    }

    $("lens-when").textContent = `Pass ${i + 1} of ${ps.length} · ${fmtPassDate(p)}`;
    $("lens-facts").innerHTML = `<span class="status st-model">Model estimate</span>
        ${pct(p.target.posterior)} match · ${p.target.offset_m.toLocaleString("en-GB")} m from the loitering position ·
        GFW radar ${p.gfw_agrees === true ? "agrees" : p.gfw_agrees === false ? "does not agree" : "has no detection here"}`;
    $("lens-scene").innerHTML = `Scene <code>${esc(p.scene)}</code>`;
    $("lens-prev").disabled = i === 0;
    $("lens-next").disabled = i === ps.length - 1;
    document.querySelectorAll("#lens-strip button").forEach((b) => {
        const on = Number(b.dataset.pass) === i;
        b.setAttribute("aria-current", String(on));
        if (on) b.scrollIntoView({ block: "nearest", inline: "center" });
    });
    $("key-mode").textContent = `Radar pass, ${fmtDate(p.date)}`;
    document.body.classList.add("lensing");
    const hash = `#imo=${imo}&pass=${i}`;
    if (location.hash !== hash) history.replaceState(null, "", hash);
    return true;
}

function playPasses(ms = REDUCED_MOTION.matches ? 3200 : 2600) {
    const ps = passesOf(lens.imo);
    if (!ps.length) return;
    if (lens.i >= ps.length - 1 || lens.i < 0) showPass(lens.imo, 0, { ms: 1400 });
    $("lens-play").textContent = "Pause";
    $("lens-play").setAttribute("aria-pressed", "true");
    lens.timer = setInterval(() => {
        if (lens.i >= ps.length - 1) return stopLensPlay();
        showPass(lens.imo, lens.i + 1, { ms: 1600 });
    }, ms);
}

function stopLensPlay() {
    clearInterval(lens.timer);
    lens.timer = null;
    if ($("lens-play")) {
        $("lens-play").textContent = "Play passes";
        $("lens-play").setAttribute("aria-pressed", "false");
    }
}

function startBlink(ms = 650) {
    const base = lens.mix || 0.9;
    let on = false;
    $("lens-blink")?.setAttribute("aria-pressed", "true");
    lens.blink = setInterval(() => {
        on = !on;
        if (map.getLayer("radar")) map.setPaintProperty("radar", "raster-opacity", on ? 0 : base);
    }, ms);
}

function stopBlink() {
    clearInterval(lens.blink);
    lens.blink = null;
    $("lens-blink")?.setAttribute("aria-pressed", "false");
    setMix(lens.mix);
}

// Remove the radar overlay and markers; hide the lens.
function radarClear() {
    stopLensPlay();
    stopBlink();
    for (const id of ["radar", "radar-box"]) {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
    }
    lens.ring?.remove();
    lens.spot?.remove();
    lens.imo = null;
    lens.i = -1;
    document.body.classList.remove("lensing");
    $("lens").hidden = true;
    $("lens").innerHTML = "";
    padMap();
    if (location.hash.includes("&pass=")) history.replaceState(null, "", location.hash.replace(/&pass=\d+/, ""));
}

// ── Gallery: every radar pass across the fleet ─────────────

const gallery = { conf: false, gfw: false };

function allPasses() {
    const out = [];
    for (const [imo, ps] of Object.entries(lens.data?.vessels || {})) {
        if (!byImo.has(imo)) continue;
        ps.forEach((p, i) => out.push({ imo, i, p }));
    }
    return out.sort((a, b) => b.p.date.localeCompare(a.p.date) || a.imo.localeCompare(b.imo));
}

async function openGallery() {
    await loadPasses();
    if (!lens.data) return;
    if (replay.on) closeReplay();
    radarClear();
    $("gallery").hidden = false;
    $("gallery-open").setAttribute("aria-expanded", "true");
    document.body.classList.add("galleried");
    renderGallery();
    padMap();
    $("gallery-list").querySelector("button")?.focus({ preventScroll: true });
}

function closeGallery() {
    if ($("gallery").hidden) return;
    $("gallery").hidden = true;
    $("gallery-open").setAttribute("aria-expanded", "false");
    document.body.classList.remove("galleried");
    padMap();
}

function renderGallery() {
    const all = allPasses();
    const rows = all.filter(({ p }) => (!gallery.conf || p.confident) && (!gallery.gfw || p.gfw_agrees === true));
    const ships = new Set(rows.map((r) => r.imo)).size;
    $("gallery-count").textContent = `${plural(rows.length, "radar pass", "radar passes")} of ${plural(ships, "ship")}, newest first`;
    $("gallery-list").innerHTML = rows.map(({ imo, i, p }) => `
        <li><button type="button" data-imo="${esc(imo)}" data-pass="${i}">
            <img src="${esc(p.image)}" width="112" height="112" loading="lazy" alt="">
            <span class="g-name">${esc(vesselName(byImo.get(imo)))}</span>
            <span class="g-meta">${esc(fmtDate(p.date))} · ${pct(p.target.posterior)}${p.gfw_agrees === true ? " · GFW agrees" : ""}</span>
        </button></li>`).join("") || `<li class="empty">No pass matches these filters.</li>`;
}

$("gallery-open").addEventListener("click", () => ($("gallery").hidden ? openGallery() : closeGallery()));
$("gallery-close").addEventListener("click", closeGallery);
$("gallery-conf").addEventListener("change", (e) => { gallery.conf = e.target.checked; renderGallery(); });
$("gallery-gfw").addEventListener("change", (e) => { gallery.gfw = e.target.checked; renderGallery(); });
$("gallery-list").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-imo]");
    if (!b) return;
    closeGallery();
    if (selectedImo !== b.dataset.imo || $("view-dossier").hidden) openDossier(b.dataset.imo);
    showPass(b.dataset.imo, Number(b.dataset.pass));
});
