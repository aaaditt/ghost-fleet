# Demo script and video shot list (about 5 minutes)

**The recorded video is ready:** https://ghost-fleet.vercel.app/watch.html
(4 min 45 s, 1080p, subtitles, 14 chapters). Its narration is in
`video/narration.json`, which follows this script's flow. Every figure comes
from `python scripts/figures.py`.

**The quickest live demo is the guided tour:** open
https://ghost-fleet.vercel.app/?tour=1. It runs the story hands-free in ten
captioned steps. Space pauses, the arrow keys step, Esc exits, and grabbing
the map pauses it. Use the script below to present by hand instead.

**Before you start**
- Open https://ghost-fleet.vercel.app in a clean browser window at about
  1440×900. Zoom 100%, bookmarks bar hidden. Let the globe load for a few
  seconds: it is WebGL with satellite imagery.
- In a second tab, open https://ghost-fleet.vercel.app/#imo=9240885&pass=2
  (WOLF's radar lens) as a backup, and a third with `/?tour=1`.
- Recording: OBS or the Windows Game Bar (Win+Alt+R). Use a headset mic and a
  quiet room. Move the mouse slowly and pause about one second after each
  click.

---

## 0:00–0:30 · The hook

**Screen:** the title card, or the globe, untouched.

> "A ship can turn off its beacon, but it cannot stop leaving a trail.
> Since 2022, a shadow fleet of old tankers has kept sanctioned Russian oil
> flowing by changing names, flags and radio identities. Oil traders need to
> know one thing: is that hidden supply growing or shrinking?"

## 0:30–0:55 · The globe

**Screen:** the globe of satellite imagery. Let it settle on the fleet.

> "Ghost Fleet answers that on one screen. 300 of the most-sanctioned tankers,
> a year of their movements, 276 of them here at their latest positions.
> Magenta marks the highest risk."

## 0:55–1:10 · The answer first

**Screen:** point at the headline, then run along the bars.

> "Activity fell 10% over the last three months: June to August against March
> to May, the bright bars against the grey ones."

**Caption:** *−10% active sanctioned tankers, Jun–Aug vs Mar–May*

## 1:10–1:25 · Where it is moving

**Screen:** scroll to *Busiest ports of call*. Fly the globe to Nakhodka, the
Baltic and Suez (scroll-zoom or double-click), then zoom back out.

> "Nakhodka in the Pacific, Primorsk and Ust-Luga on the Baltic, through Suez
> and Port Said. Those routes came straight out of the data."

## 1:25–2:00 · One ship's story

**Screen:** type `longevity` in the vessel search and click **Wolf**. Slowly
point down the numbered identity list.

> "Search a name this ship used last year, Longevity 7, and we get today's
> Wolf. Same hull, same IMO number. It started as the Danish Torm Gertrud,
> became East 1 in Hong Kong, Longevity 7 in Palau, then Wolf under the flag
> of landlocked Malawi, and in September, Aruba. Seven identities."

## 2:00–2:25 · The evidence matrix

**Screen:** scroll up to the score, then the evidence matrix. Zoom the globe
into the Gulf of Oman: the magenta rings are its loitering.

> "Its screening score of 75 isn't a black box. Each row gives the evidence,
> its source and the points it adds: 40 for the listings, 30 for identity
> switches, 5 for loitering. It idled offshore for up to two weeks at a time."

## 2:25–3:05 · Seen by satellite radar

**Screen:** scroll to *Radar (satellite) detections*, then *Our radar image
match*. Click **See it on the satellite map**: the globe flies down and lays
the radar image where it was taken. Click **Blink**.

> "A ship can switch off its tracker, but not its hull. Global Fishing
> Watch's satellite radar picked up 255 of these 300 tankers, eight times for
> the Wolf. Our own detector, on 147 radar scenes it had never seen, found 97%
> of the ships Global Fishing Watch found, with a third of the false alarms.
> And this is the radar image itself, on the map where it was taken. Blink,
> and the bright echo is the steel hull."

**Caption:** *Agreement with GFW's detector, not ground truth*

## 3:05–3:30 · Every radar pass

**Screen:** click **Play passes** in the lens, then **Radar gallery** and
scroll the filmstrip. Pick any pass to fly to it.

> "Every radar pass of the same ship through the year: seven for the Wolf.
> Across the fleet, 472 passes for 133 ships, each one you can open. Every
> match is a model estimate, never proof."

## 3:30–3:45 · Evidence replay

**Screen:** click **Historical evidence replay**, then **Play**.

> "You can go back in time. The replay steps through the year month by month:
> port calls, loitering and radar sightings, as recorded. It never draws a
> route or fills in the gaps."

Then click **Back to latest positions**.

## 3:45–4:10 · Honesty as a feature

**Screen:** the *Cargo state* row, then *Size and value*, then the source
links.

> "Nobody publishes whether these tankers are loaded, so we tested whether
> radar could tell, on 200 tanker images. It couldn't: a coin toss. So we say
> unknown. Values are ranges with their assumptions, and every vessel links
> back to its sources."

## 4:10–4:45 · Close

**Screen:** click **Back to overview**. The globe pulls back to the whole
fleet.

> "289 of these 300 switched identity, across 81 flags. Next: all 892 listed
> ships, and licensed draft data to turn this signal into barrels. Try the
> guided tour yourself. Ghost Fleet: the hidden fleet, made visible."

**End card:** *ghost-fleet.vercel.app/?tour=1 · github.com/aaaditt/ghost-fleet ·
Aadit Chandra & Abhishekh Verma*

---

## If something breaks live

- **The globe is blank or the tiles are slow:** keep talking. The panel,
  dossier and evidence matrix don't depend on the map.
- **WebGL is disabled on the presenting machine:** the map cannot draw. Play
  the video at `/watch.html`; every scene is the same product.
- **The site is unreachable:** run it locally with
  `cd dashboard; python -m http.server 8765`, then open `localhost:8765`.
- **Someone asks "is this live?"** "It's a dated snapshot, 30 September 2025
  to 27 September 2026. Refreshing it is one command."

## Likely judge questions

| Question | Answer |
|---|---|
| Is there real ML? | "Yes. A CNN vessel detector we trained on Sentinel-1 radar, a probabilistic matcher that finds a tanker in a radar image from its AIS position, and a cargo-state study. The Models page shows every result, including the one that failed." |
| How accurate is the detector? | "On 147 held-out radar scenes it agrees with Global Fishing Watch's detections at PR-AUC 0.991, versus 0.964 for classic CFAR. That is agreement with GFW, not ground truth: GFW's labels have their own errors, and we show those too." |
| Is the radar image really where you put it? | "Yes. Each image keeps its map transform from Sentinel-1, so its four corners are placed exactly. The ring is our model's match; the white dot is where AIS put the ship." |
| Can you tell if a tanker is loaded? | "No, and we tested it. Radar alone scored AUC 0.47 on unseen tankers, a coin toss, against a pass mark we fixed in advance. So cargo stays unknown." |
| Can you see ship-to-ship transfers? | "We flag possible side-by-side pairs for review. With 10 m pixels (about 20 m true resolution), one tanker's bright bow and bridge often look like two ships, so only 5 reviewed pairs are shown, as possible activity, never as a transfer." |
| Why did activity fall? | "The tool shows *that* it fell, not why: enforcement, seasonality, or ships moving to identities we haven't screened. That's what an analyst would investigate next." |
| Business model? | "A data feed and alerting for commodity desks and compliance teams, with licensed AIS, radar and sanctions data. The free sources we used are non-commercial." |
