# Ghost Fleet — hidden oil supply, seen from the sea

**Live demo:** https://ghost-fleet.vercel.app
**Repository:** https://github.com/aaaditt/ghost-fleet
**Start here:** https://ghost-fleet.vercel.app/#imo=9240885
**Pitch video (4 min):** https://ghost-fleet.vercel.app/watch.html
**Models and their results:** https://ghost-fleet.vercel.app/models.html

> A ship can turn off its beacon, but it cannot stop leaving a trail.

## Inspiration

Since 2022, a "shadow fleet" of ageing tankers has kept sanctioned Russian oil
moving. These ships change names, re-flag to registries that barely exist, and
switch their radio identity. Some are now flagged to landlocked countries.
The oil still reaches the market, and oil traders need to know whether that
hidden supply is growing or shrinking. The data to answer that is public, but
it is scattered across sanctions lists and vessel-tracking records that do not
talk to each other.

## What it does

Ghost Fleet is a map-first monitor for commodity and energy traders. It answers
one question: **is hidden, sanctions-linked oil supply rising or falling, and
where is it moving?**

- **The trend.** The panel leads with a plain sentence. In this snapshot,
  sanctioned tanker activity fell 10% in the last three months (Jun–Aug vs
  Mar–May), shown over 12 months of bars.
- **The map.** 276 shadow-fleet tankers sit at their latest observed
  positions, clustered at the Baltic terminals, the Black Sea, Suez, the
  Gulf, Singapore and the Russian Far East.
- **Where they call.** The busiest ports are Nakhodka, Suez, Port Said,
  Primorsk and Ust-Luga: the export routes you would expect.
- **The dossier.** Selecting a vessel shows the evidence behind its score:
  every identity it has used, in order, and its recent dated activity on the
  map. For example, EAST 1 has sailed as TORM GERTRUD (Denmark), EAST 1 (Hong
  Kong), LONGEVITY 7 (Palau), and WOLF under Malawi and then Aruba flags. It
  has also spent up to two weeks at a time idling at sea.
- **The evidence matrix.** Every piece of evidence has its own row with its
  source, its status (*Observed*, *Derived from AIS*, *Not observed*,
  *Unavailable / unknown* or *Model estimate*) and the points it adds.
- **Seen by satellite radar.** Global Fishing Watch's Sentinel-1 radar
  detected 255 of the 300 tankers. Our own detector finds each tanker in the
  radar image taken while AIS placed it loitering, and the dossier shows that
  image.
- **Historical evidence replay.** Step month by month through the year's
  port calls, loitering and radar sightings, exactly as recorded, with no
  routes drawn and no gaps filled.
- **Honest numbers.** The risk score is additive and visible (listing +
  identity switches + loitering + AIS gaps); radar and model outputs never
  change it. Size and value are shown as
  ranges with their assumptions. Where the data cannot tell whether a tanker
  is loaded, the dossier says "unknown" instead of guessing.

### What the snapshot shows

| | |
|---|---|
| Shadow-fleet vessels screened | 300 (most-listed first; all 300 matched to tracking data) |
| Switched identity at least once | 289; median 4 switches, 124 switched 5+ times |
| Different flags used across all identities | 81 |
| Currently flagged to a landlocked country | 11 (Malawi ×4, Mali ×3, Zimbabwe ×3, Botswana ×1) |
| Now flagged to Russia | 115 |
| 3-month activity trend | −10% |

## How we built it

1. **Who is in the fleet.** We used the OpenSanctions maritime dataset (23,453
   records) and its shadow-fleet tag. The export has one row per source list,
   so we merge rows by IMO number. That gives 892 shadow-fleet vessels, 772
   of them formally sanctioned. We rank by how many lists name each ship.
2. **What they did.** For each IMO we query the Global Fishing Watch v3 API.
   We collect *every* AIS identity carrying that IMO, then pull a year of
   dated, positioned events for all of them: loitering at sea, port visits,
   AIS gaps and encounters.
3. **Scoring and estimates.** The pipeline computes a transparent score, size
   ranges from gross tonnage, and a monthly activity series. It writes a dated
   JSON snapshot.
4. **Satellite radar and ML** (`ml/`).
   - *Radar detections.* We pulled 127,265 GFW Sentinel-1 detections for the
     24 one-degree corridors where these tankers spend the most time. We read
     1.6 km image chips straight from Copernicus Sentinel-1 RTC on Microsoft
     Planetary Computer, without downloading whole scenes.
   - *Detector.* We trained a small CNN (about 120k parameters, a 4 GB
     laptop GPU, 6 minutes) on 7,948 chips labelled by GFW's detections.
     Split by radar scene, on 147 unseen scenes it reaches PR-AUC 0.991 and
     finds 97% of GFW's ships. A classical CFAR detector reaches 0.964, with
     about three times the false alarms. These are agreement with GFW, not
     ground truth.
   - *Matching.* Using the tanker's AIS loitering position, we score every
     detected target by confidence and distance, allowing for "not seen".
     Without looking at GFW's detections, our top target agrees with GFW's
     own match 87% of the time.
   - *Cargo state.* We tested whether radar alone can tell laden from
     ballast, with voyage-context labels and a pass mark fixed in advance.
     On unseen tankers it scored AUC 0.47, a coin toss. It failed, and cargo
     stays unknown.
5. **The dashboard.** A static page (Leaflet on an Esri bathymetric basemap)
   reads the snapshot. It is styled after a nautical chart: magenta overprint
   for hazards, italic serif for vessel names. It is deployed on Vercel.

The code is Python (pandas, requests) with plain HTML, CSS and JavaScript. It
has no build step, no backend and no API keys in the browser. The ML code is
PyTorch, scikit-learn and rasterio. 53 offline tests cover the pipeline, the
evidence logic and the radar file, and a 157-check browser test covers the
site on desktop, mobile and reduced motion.

## Challenges we ran into

- **Tracking data splits one ship into many.** Global Fishing Watch often
  stores each re-flag or radio-ID change as a separate record. Our first
  version only read the first record, which hid the very behaviour we were
  looking for. Merging every record that shares the IMO turned EAST 1 from
  "one identity" into seven.
- **Public data has blind spots.** The free tracking data has no draft
  readings, so we cannot see whether a tanker is loaded. It also has almost no
  tanker-to-tanker encounter or AIS-gap events. We verified with direct API
  calls that these are coverage gaps, not errors. We rebuilt the evidence
  around what is observable (loitering at sea, port calls and identity
  history) and state the gaps on screen.
- **Keeping the headline honest.** Browser testing caught an aggregation bug:
  trimming events for page size before computing the trend undercounted early
  months. We fixed it, re-derived the figure, and checked it by hand.

- **Our detector first learned the wrong thing.** Our own tankers' 2,328
  radar detections filled the positive budget, so the first model saw only 9
  "dark" (unmatched) test targets and caught 4. Rebalancing to 1,308
  unmatched examples lifted dark-target recall to 95%, against 87% for CFAR.
- **Radar with 10 m pixels (about 20 m true resolution) blurs pairs of ships.** Automatic side-by-side
  detection flagged 338 images, but on review most were one tanker whose
  bright bow, bridge and sidelobes look like two objects. Only 5 reviewed
  pairs are shown, as possible activity.

## Accomplishments we're proud of

- Every number on the screen traces to a public source and a dated snapshot.
- The per-vessel dossier makes a flag-hopping pattern obvious in seconds.
- We say "unknown" where the data is silent, and we publish the model
  that failed.

## What we learned

The evasion signal is in identity history, not position: names, flags and
radio IDs. Positions tell you where a ship is. Identity history tells you what
it is trying to hide. Radar adds physical presence, but not everything:
freely available Sentinel-1 radar (10 m pixels) cannot tell a loaded tanker from an empty one, and
a pre-registered test is how we found that out rather than guessing.

## Limitations

- A sanctions listing, a score or an idle period at sea is **not proof of
  wrongdoing**. This is a prioritisation and market-context tool, not advice.
- The trend counts active listed vessels, not barrels moved.
- Value figures are an upper bound: hull capacity × estimated voyages × a
  static Brent price of $78.50. They are not observed cargo.
- The data covers 300 of 892 listed vessels, from a one-year snapshot rather
  than a live feed.
- Radar evidence covers 24 corridors and only days Sentinel-1 imaged them.
  Parts of the Russian Pacific coast are rarely imaged. Detector and matcher
  scores measure agreement with Global Fishing Watch, not ground truth. The
  side-by-side review was done by Claude (an AI model), not an expert
  analyst.
- OpenSanctions (CC BY-NC 4.0) and Global Fishing Watch are licensed for
  non-commercial use. A commercial product would need licensed AIS and
  sanctions data.

## Licence

Code: MIT. Data: under its sources' terms (OpenSanctions CC BY-NC 4.0,
Global Fishing Watch non-commercial).

## What's next

1. Screen all 892 vessels and refresh the snapshot daily.
2. Add draft data from a licensed AIS provider to estimate loaded vs. ballast
   state and turn activity into a barrels-based signal.
3. Evaluate the detector on independent xView3-SAR labels (`ml/xview3.py`
   is ready once the labels are licensed), and extend radar coverage beyond
   the 24 corridors.
4. Validate the trend against published export estimates with trader users.
