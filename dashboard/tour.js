/* Ghost Fleet — guided tour for live demos.
   Start with ?tour=1 or the "Guided tour" button. Space pauses, the arrow
   keys step, Esc exits. Each step sets the camera and the panels, shows a
   caption, then waits; the presenter can let it run or drive it by hand.
   Uses the globals of app.js and radar.js. */

const SHOWCASE = "9240885"; // WOLF: listed, 7 radar passes, GFW agrees on the match

const tour = { on: false, step: -1, paused: false, timer: null, spin: null, gen: 0 };

function spinGlobe(on) {
    cancelAnimationFrame(tour.spin);
    tour.spin = null;
    if (!on || REDUCED_MOTION.matches) return;
    let last = performance.now();
    const turn = (t) => {
        const c = map.getCenter();
        map.jumpTo({ center: [c.lng + (t - last) * 0.004, c.lat] });
        last = t;
        tour.spin = requestAnimationFrame(turn);
    };
    tour.spin = requestAnimationFrame(turn);
}

function wolf() {
    return byImo.get(SHOWCASE);
}

function bestPass() {
    return sar?.vessels[SHOWCASE]?.our_match?.pass ?? 0;
}

function resetPanels() {
    stopLensPlay();
    stopBlink();
    if (replay.on) closeReplay();
    closeGallery();
}

// Each step: title (small), text (caption), hold (ms before auto-advance), run().
const STEPS = [
    {
        title: "Ghost Fleet",
        text: () => `${vessels.length} tankers named on sanctions lists, watched from orbit.`,
        hold: 6500,
        run() {
            resetPanels();
            if (!$("view-dossier").hidden) closeDossier();
            map.flyTo({ center: [40, 22], zoom: 1.7, pitch: 0, bearing: 0, ...motion(2500) });
            setTimeout(() => tour.on && tour.step === 0 && spinGlobe(true), REDUCED_MOTION.matches ? 0 : 2600);
        },
    },
    {
        title: "The fleet",
        text: () => {
            const high = vessels.filter((v) => v.risk_score >= HIGH_RISK).length;
            return `Each dot is a tanker's latest AIS position. The ${high} glowing magenta ones score ${HIGH_RISK}+ on our screening.`;
        },
        hold: 7000,
        run() {
            spinGlobe(false);
            map.flyTo({ center: [50, 26], zoom: 2.9, pitch: 20, bearing: 0, ...motion(3500) });
        },
    },
    {
        title: "Where we looked with radar",
        text: () => `The dashed boxes are the ${sar?.coverage.corridors.length ?? 24} one-degree corridors where these ships loiter most. ` +
            "Sentinel-1 radar sees ships at night and through cloud, whether or not their AIS is on.",
        hold: 8000,
        run() {
            map.setPaintProperty("corridors", "line-opacity", 0.9);
            map.flyTo({ center: [56.3, 25.9], zoom: 6.3, pitch: 35, bearing: -8, ...motion(4500) });
        },
        leave() { map.setPaintProperty("corridors", "line-opacity", 0.4); },
    },
    {
        title: () => vesselName(wolf()),
        text: () => {
            const v = wolf();
            return `Score ${v.risk_score}. Named on sanctions lists, ${plural(v.identity_changes, "identity switch", "identity switches")}. ` +
                "These marks are its dated loitering, port calls and AIS gaps.";
        },
        hold: 8000,
        run() {
            if (selectedImo !== SHOWCASE || $("view-dossier").hidden) openDossier(SHOWCASE);
            else drawTrack(wolf());
        },
    },
    {
        title: () => { const p = passesOf(SHOWCASE)[bestPass()]; return p ? `Sentinel-1 · ${fmtPassDate(p)}` : "Sentinel-1"; },
        text: () => {
            const p = passesOf(SHOWCASE)[bestPass()];
            return p ? `The radar image, draped on the satellite map where it was taken. The ring is the ship our model matched: ` +
                `${pct(p.target.posterior)} probability, ${p.target.offset_m} m from the loitering position. A model estimate, not proof.` : "";
        },
        hold: 9500,
        async run() {
            setMix(0);
            await showPass(SHOWCASE, bestPass(), { ms: 5000 });
            fadeMix(0.9, REDUCED_MOTION.matches ? 0 : 2500, 2500);
        },
    },
    {
        title: "Optical versus radar",
        text: "Blinking between the optical satellite map and the radar pass. The bright echo with the cross-shaped sidelobes is a steel hull.",
        hold: 7000,
        run() {
            map.easeTo({ bearing: 20, pitch: 55, ...motion(7000) });
            startBlink(700);
        },
        leave() { stopBlink(); },
    },
    {
        title: "Every pass, one ship",
        text: () => `${plural(passesOf(SHOWCASE).length, "radar pass", "radar passes")} matched to ${vesselName(wolf())} over the year. ` +
            "Each one is a separate satellite overpass. Magenta dots mark confident matches.",
        hold: () => passesOf(SHOWCASE).length * 2200 + 1500,
        async run() {
            await showPass(SHOWCASE, 0, { ms: 2000 });
            playPasses(2200);
        },
        leave() { stopLensPlay(); },
    },
    {
        title: "Across the fleet",
        text: () => {
            const ps = Object.values(lens.data?.vessels || {});
            return `${ps.reduce((n, p) => n + p.length, 0)} radar passes for ${ps.length} ships, each one you can open on the map.`;
        },
        hold: 7500,
        async run() {
            await openGallery();
            map.flyTo({ center: [58, 22], zoom: 3, pitch: 0, bearing: 0, ...motion(3500) });
        },
        leave() { closeGallery(); },
    },
    {
        title: "Twelve months of evidence",
        text: "Every dated event and radar detection in the snapshot, month by month. Sparse evidence, never joined into invented tracks.",
        hold: 10000,
        run() {
            if ($("view-dossier").hidden === false) closeDossier();
            openReplay();
            setReplay(0);
            replay.speed = REDUCED_MOTION.matches ? 1500 : 750;
            playReplay();
        },
        leave() { replay.speed = 0; stopReplay(); },
    },
    {
        title: "Ghost Fleet",
        text: "Aadit Chandra & Abhishekh Verma · ghost-fleet.vercel.app",
        hold: 0,
        end: true,
        run() {
            resetPanels();
            map.flyTo({ center: [52, 22], zoom: 1.8, pitch: 0, bearing: 0, ...motion(3000) });
            setTimeout(() => tour.on && STEPS[tour.step]?.end && spinGlobe(true), REDUCED_MOTION.matches ? 0 : 3100);
        },
    },
];

const val = (x) => (typeof x === "function" ? x() : x);

function fadeMix(to, ms, delay = 0) {
    const from = lens.mix, t0 = performance.now() + delay, gen = tour.gen;
    const tick = (t) => {
        if (gen !== tour.gen && tour.on) return;
        const k = ms ? Math.min(1, Math.max(0, (t - t0) / ms)) : 1;
        setMix(from + (to - from) * k);
        if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
}

async function goStep(i) {
    if (i < 0 || i >= STEPS.length) return;
    clearTimeout(tour.timer);
    STEPS[tour.step]?.leave?.();
    spinGlobe(false);
    const gen = ++tour.gen;
    tour.step = i;
    const s = STEPS[i];
    $("tour").classList.toggle("tour-end", Boolean(s.end));
    $("tour-title").textContent = val(s.title);
    $("tour-text").textContent = "";
    $("tour-dots").innerHTML = STEPS.map((_, k) => `<i class="${k === i ? "on" : k < i ? "done" : ""}"></i>`).join("");
    $("tour-prev").disabled = i === 0;
    $("tour-next").disabled = i === STEPS.length - 1;
    await s.run();
    if (gen !== tour.gen) return;
    $("tour-title").textContent = val(s.title);
    $("tour-text").textContent = val(s.text);
    schedule();
}

function schedule() {
    clearTimeout(tour.timer);
    if (!STEPS[tour.step]) return;
    const hold = val(STEPS[tour.step].hold);
    if (!tour.paused && hold) tour.timer = setTimeout(() => goStep(tour.step + 1), hold);
}

function pauseTour(p = !tour.paused) {
    tour.paused = p;
    $("tour-pause").textContent = p ? "Resume" : "Pause";
    $("tour-pause").setAttribute("aria-pressed", String(p));
    if (p) clearTimeout(tour.timer);
    else schedule();
}

function startTour() {
    if (tour.on || !vessels.length) return;
    tour.on = true;
    document.body.classList.add("touring");
    $("tour").hidden = false;
    pauseTour(false);
    loadPasses().then(() => goStep(0));
    $("tour-pause").focus({ preventScroll: true });
}

function endTour() {
    if (!tour.on) return;
    clearTimeout(tour.timer);
    STEPS[tour.step]?.leave?.();
    spinGlobe(false);
    tour.gen++;
    tour.on = false;
    tour.step = -1;
    document.body.classList.remove("touring");
    $("tour").hidden = true;
    if (new URLSearchParams(location.search).has("tour")) history.replaceState(null, "", location.pathname + location.hash);
    $("tour-start").focus({ preventScroll: true });
}

$("tour-start").addEventListener("click", startTour);
$("tour-exit").addEventListener("click", endTour);
$("tour-pause").addEventListener("click", () => pauseTour());
$("tour-prev").addEventListener("click", () => goStep(tour.step - 1));
$("tour-next").addEventListener("click", () => goStep(tour.step + 1));
document.addEventListener("keydown", (e) => {
    if (!tour.on || e.target.matches("input, textarea")) return;
    if (e.key === "Escape") endTour();
    else if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); goStep(tour.step + 1); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); goStep(tour.step - 1); }
    else if (e.key === " " && !e.target.matches("button")) { e.preventDefault(); pauseTour(); }
});
// A user grabbing the map pauses the tour instead of fighting it.
map.on("mousedown", () => tour.on && !tour.paused && pauseTour(true));
map.on("touchstart", () => tour.on && !tour.paused && pauseTour(true));
document.addEventListener("gf:ready", () => {
    if (new URLSearchParams(location.search).has("tour")) startTour();
});
