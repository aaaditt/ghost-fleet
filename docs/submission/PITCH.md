# Pitch deck

**Deck:** https://claude.ai/artifact/9SscVdcfFiNjFdTEaZLmeL. It is shared by link,
and exports to PowerPoint or PDF from Share › Export.
**Narrated pitch video:** https://ghost-fleet.vercel.app/watch.html

Twelve slides, about 4 minutes. Speaker notes are in each slide. The live demo
follows `DEMO_SCRIPT.md` and replaces slides 5–8 when presenting in person.

| # | Slide | Point to land |
|---|---|---|
| 1 | Ghost Fleet | Hidden oil supply, seen from the sea. |
| 2 | A ship can turn off its beacon | Rename, re-flag, swap radio IDs: how the shadow fleet hides. |
| 3 | The trader's question | Is hidden supply rising or falling, and where? |
| 4 | −10% | Active sanctioned tankers, Jun–Aug vs Mar–May (595 vs 662). |
| 5 | One screen | The live product: trend, map, busiest ports, dossiers. |
| 6 | One hull, seven identities | EAST 1 → WOLF; Malawi is landlocked; the evidence matrix explains 40 + 30 + 5. |
| 7 | Seen by satellite radar | 255 of 300 tankers radar-detected; the Wolf's Sentinel-1 image, 4 Mar 2026. |
| 8 | What our models can, and can't, do | Detector 97% (PR-AUC 0.991 vs CFAR 0.964); matcher 87%; cargo AUC 0.47, a coin toss, so unknown. |
| 9 | It isn't one ship | 289 of 300 switched identity; 81 flags; 11 landlocked; 115 now Russian. |
| 10 | How it works | OpenSanctions → Global Fishing Watch → dated snapshot → radar and our models. |
| 11 | What we don't claim | Not proof, no loaded state (radar failed the test), agreement not ground truth, not live. |
| 12 | What's next | All 892 ships daily; draft data to barrels; independent radar labels. |

**Before presenting, fill in:** `[Team names]` on the cover.

Every figure comes from the 2026-09-30 snapshot in `dashboard/data/`
(`python scripts/figures.py`), including the radar and model results in
`dashboard/data/sar.json`.
