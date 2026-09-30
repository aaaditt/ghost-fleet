# Demo script and video shot list (about 4 minutes)

**The recorded video is ready:** https://ghost-fleet.vercel.app/watch.html
(4 min 8 s, 1080p, subtitles, 13 chapters). Its narration is in `video/narration.json`,
which follows this script's flow. Every figure comes from
`python scripts/figures.py`.

Use the script below to present live, or to re-record by hand.

**Before you start**
- Open https://ghost-fleet.vercel.app in a clean browser window at about
  1440×900. Zoom 100%, bookmarks bar hidden.
- In a second tab, open https://ghost-fleet.vercel.app/#imo=9240885 as a
  backup, and a third with https://ghost-fleet.vercel.app/models.html.
- Recording: OBS or the Windows Game Bar (Win+Alt+R). Use a headset mic and a
  quiet room. Move the mouse slowly and pause about one second after each
  click.

---

## 0:00–0:25 · The hook

**Screen:** the overview, untouched. Let the map sit.

> "A ship can turn off its beacon, but it cannot stop leaving a trail.
> Since 2022, a shadow fleet of old tankers has kept sanctioned Russian oil
> flowing by changing names, flags and radio identities. Oil traders need to
> know one thing: is that hidden supply growing or shrinking?"

## 0:25–0:55 · The answer first

**Screen:** point at the headline, then run along the bars from March to
August.

> "Ghost Fleet answers that in one line. Across 300 of the most-sanctioned
> shadow-fleet tankers, activity fell 10% over the last three months: June to
> August against March to May, the dark bars against the grey ones."

**Caption:** *−10% active sanctioned tankers, Jun–Aug vs Mar–May*

## 0:55–1:15 · Where it is moving

**Screen:** scroll to *Busiest ports of call*, then sweep across the map.

> "Nakhodka in the Pacific, Primorsk and Ust-Luga on the Baltic, through Suez
> and Port Said. Those routes came straight out of the data."

## 1:15–2:00 · One ship's story

**Screen:** type `longevity` in the vessel search and click **Wolf**. Slowly
point down the numbered identity list.

> "Search a name this ship used last year, Longevity 7, and we get today's
> Wolf. Same hull, same IMO number. It started as the Danish Torm Gertrud,
> became East 1 in Hong Kong, Longevity 7 in Palau, then Wolf under the flag
> of landlocked Malawi, and in September, Aruba. Seven identities."

## 2:00–2:25 · The evidence matrix

**Screen:** scroll up to the score, then the evidence matrix.

> "Its screening score of 75 isn't a black box. Each row of the evidence
> matrix gives the evidence, its source, whether it was observed or derived,
> and the points it adds: 40 for the listings, 30 for identity switches, 5
> for loitering. It idled offshore for up to two weeks at a time this summer."

## 2:25–3:00 · Seen by satellite radar

**Screen:** scroll to *Radar (satellite) detections*, then *Our radar image
match* and its image.

> "A ship can switch off its tracker, but not its hull. Global Fishing
> Watch's satellite radar picked up 255 of these 300 tankers, eight times for
> the Wolf. We trained our own detector on those images. On 147 radar scenes
> it had never seen, it found 97% of the ships Global Fishing Watch found,
> with a third of the false alarms of the classic method. Here it finds the
> Wolf in the Gulf of Oman, right where its tracking data placed it."

**Caption:** *Agreement with GFW's detector, not ground truth*

## 3:00–3:20 · Evidence replay

**Screen:** click **Historical evidence replay**, then **Play**.

> "You can go back in time. The replay steps through the year month by month:
> port calls, loitering and radar sightings, as recorded. It never draws a
> route or fills in the gaps."

Then click **Back to latest positions**.

## 3:20–3:40 · Honesty as a feature

**Screen:** the *Cargo state* row, then *Size and value*, then the source
links.

> "Nobody publishes whether these tankers are loaded, so we tested whether
> radar could tell, on 200 tanker images. It couldn't: a coin toss. So we say
> unknown. Values are ranges with their assumptions, and every vessel links
> back to its sources."

## 3:40–4:00 · Close

**Screen:** click **Back to overview**. The whole fleet reappears.

> "289 of these 300 switched identity, across 81 flags. Next: all 892 listed
> ships, and licensed draft data to turn this signal into barrels. Ghost
> Fleet: the hidden fleet, made visible."

**End card:** *ghost-fleet.vercel.app · github.com/aaaditt/ghost-fleet*

---

## If something breaks live

- **The map tiles are slow:** keep talking. The panel and dossier don't
  depend on the tiles.
- **The site is unreachable:** run it locally with
  `cd dashboard; python -m http.server 8765`, then open `localhost:8765`.
- **Someone asks "is this live?"** "It's a dated snapshot, 30 September 2025
  to 27 September 2026. Refreshing it is one command."

## Likely judge questions

| Question | Answer |
|---|---|
| Is there real ML? | "Yes. A CNN vessel detector we trained on Sentinel-1 radar, a probabilistic matcher that finds a tanker in a radar image from its AIS position, and a cargo-state study. The Models page shows every result, including the one that failed." |
| How accurate is the detector? | "On 147 held-out radar scenes it agrees with Global Fishing Watch's detections at PR-AUC 0.991, versus 0.964 for classic CFAR. That is agreement with GFW, not ground truth: GFW's labels have their own errors, and we show those too." |
| Can you tell if a tanker is loaded? | "No, and we tested it. Radar alone scored AUC 0.47 on unseen tankers, a coin toss, against a pass mark we fixed in advance. So cargo stays unknown." |
| Can you see ship-to-ship transfers? | "We flag possible side-by-side pairs for review. With 10 m pixels (about 20 m true resolution), one tanker's bright bow and bridge often look like two ships, so only 5 reviewed pairs are shown, as possible activity, never as a transfer." |
| Why did activity fall? | "The tool shows *that* it fell, not why: enforcement, seasonality, or ships moving to identities we haven't screened. That's what an analyst would investigate next." |
| Business model? | "A data feed and alerting for commodity desks and compliance teams, with licensed AIS, radar and sanctions data. The free sources we used are non-commercial." |
