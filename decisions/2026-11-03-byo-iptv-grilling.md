# Grilling record: bring-your-own IPTV in Kodi (StarWave Amendment A1)

grilled: done 2026-11-03 (owner, in the StarWave session; Morpheus asked, owner answered in his own words)
Milestone: charter Amendment A1 (brainiac 2c576c0). Plan: `plans/2026-11-03-byo-iptv.md`. Merged: `c4cd622` (wizard 5.10.0).
Inputs: seat consults 2026-11-03 - Link 55b6c62, Aegis 9894a12, Neo a430848, Trinity f507198, Brainiac 378216c; Aegis floor ba689ee.
Owner confirmed the summary below with: "Yes, do it for me, but don't add these favorites into the delivered build for the repo because my favorites will undoubtedly not be someone else's favourites."

## Decisions

| # | Question | Owner's answer |
|---|---|---|
| Q1 | Renew the Strong8K lines past 2026-11-17? | "I will be renewing both." Kill K1 does not fire. |
| Q2 | Who else uses these logins? | Owner only; each login is limited to one account and cannot be shared. |
| Q3 | Kodi writes the stream link (login inside) to its own `kodi.log` on playback | Accepted on the owner's devices; revisit before it is used on anyone else's device (e.g. via the ~/iptv relay). |
| Q4 / Q10 | Who is it for? | Available to anyone who installs StarWave, each typing their own provider login; none of the owner's logins ship. The owner's brothers may buy their own Strong8K line and set it up themselves. On-screen help only, no support promise; "tested with one provider" noted in the changelog. |
| Q5 | Is it worth building; how will we know? | Yes: live sports on the Deck. Measure: live TV watched in Kodi on the Deck at least weekly for 4 weeks; review around 2026-12-01 from the Deck's watch history. |
| Q6 | One line per device? | Yes: the Deck line is Kodi-on-Deck only, the Shield line stays in TiviMate; two logins that do not overlap. |
| Q7 | Thin guide coverage | Fine for now; "improving the guide should always be the goal" - continuous improvement. |
| Q8 | Fresh Wipe keeps saved logins | Recommendation accepted: Wipe All is how a device is handed over; Fresh Wipe keeps logins and says so. |
| Q9 | When to publish 5.10.0 to the fleet | This week, after a read-only Shield check (wake, screenshot, version, sleep) while nobody is watching. Push and publish each still need the owner's word at the time. |
| Q11 | First guide improvement | ~/iptv: teach the home guide the Strong8K channel names, starting with the owner's favourites (NBC Sports Boston, NESN, ESPN, NFL Network, RedZone, Boston locals), then widen. |
| Q12 | Brothers have no reachable guide | Build the provider's own guide option (wizard downloads the provider XMLTV, keeps only picked channels, stored beside the playlist, login never leaves the device) before a brother sets this up. The feature stays OFF unless a user turns it on; the owner will NOT turn it on in Kodi on his Shield (TiviMate there). |
| Q13 | The home guide runs on the Mac, not the home lab | Move the guide server (`com.iptv.epg-server` :8085 + `com.iptv.epg-refresh`) to the home lab, right after the Xtream relay (due 11/14), on the same sitting if it fits. Owner had assumed it already ran on the home lab. |
| Q14 | Favourites on the Deck | Set the owner's 7 (NBC Sports Boston, CBS 4 WBZ Boston, NFL Network, ESPN, CBS Sports Network, NESN, NFL RedZone) on the Deck through the wizard. Never in the delivered build: favourites live in the device's `live_tv/live_tv.json`, which no capture or backup includes. |

## Facts established during the grilling
- The two guides are not mixed: StarWave's free channels ("IPTV Merge", ch 1-770, own guide) and "My TV" (Strong8K, ch 1000+, home guide) are separate IPTV Simple instances shown side by side.
- Off by default is measured, not assumed: unconfigured = one silent file check at boot; Deck feature-off launch 4.41s vs 5.0s baseline.
- Home guide host: 192.168.0.10 is this Mac (launchd jobs above, set up 2026-10-13).

## Addendum (same day, owner ruling relayed by the TiviMate session)
- Audience widened from Q10: anyone who installs StarWave may use the generic provider setup, each with their own provider and login; off by default, no login shipped, on-screen help only, no support promise. Owner: "I agree with the recommendation."
- Terms: StarWave is the Kodi build; this feature is a generic provider setup; Strong8K is only the owner's own provider and login, never a property of StarWave.

## Risk acceptance (owner, 2026-11-04)
- Aegis consult 9894a12 items 6 and 7, for every user of the generic provider setup (not only the owner): (6) Kodi writes a user's stream link, login inside, to that user's own `kodi.log` on playback; (7) providers on plain HTTP send the login unencrypted. Mitigation shipped in 897cf39: the setup screens say "Don't share your Kodi log; your provider may send your login unencrypted." Owner, asked "Accept the two login risks for other users, with the on-screen warning as the mitigation?": "Accept both".
