# Research: Automated IPTV Channel Audit (dead streams + sub-720p purge)

2026-08-25, external sources. For initiative (b) - shape before build.

## Health checking
- HEAD/GET checks unreliable (fake 200s); real validation = ffprobe against
  playlist + first segment: `ffprobe -v quiet -print_format json
  -show_format -show_streams <url>` (mpegflow.com ffprobe guide;
  github.com/ShouNLAK/Check-Online-IPTV detects fake-200s this way).
- Best-fit existing tools:
  - github.com/NewsGuyTor/IPTVChecker (Python, most complete): alive/dead,
    geoblock detection (403/451/426/401/423) with proxy confirmation,
    ffprobe codec/resolution/framerate, flags mislabeled resolution, 1-20
    workers, extended-timeout re-check, -split outputs
    working/dead/geoblocked playlists + CSV.
  - github.com/freearhey/iptv-checker (Node, iptv-org ecosystem):
    ffprobe-based, timeouts/parallelism/UA/referrer/retries.
- False positives: providers sniff User-Agent (iptv-checker issue #15);
  missing Referer/session tokens cause 403s; geoblocks look dead without
  proxy confirmation. Mitigation: replay the M3U's #EXTVLCOPT/#KODIPROP
  headers; classify 403/451 as blocked, not dead.

## Resolution
- ffprobe streams[].width/height (skip audio-only via codec_type). HLS
  master playlists carry per-variant RESOLUTION (optional in spec);
  "channel resolution" should mean the BEST variant: keep if max height
  >= 720. Metadata lies - trust decoded dimensions over labels
  (NewsGuyTor flags mismatches).

## Kodi/StarWave specifics
- IPTV Simple Client consumes M3U + XMLTV (kodi.wiki PVR IPTV Simple).
  Cleanest filter point: regenerate the M3U upstream, not Kodi's manual
  per-device channel manager.
- SlyGuy addons are API-driven, BUT iptv.merge merges their playlists/EPG
  into playlist.m3u8 + epg.xml (matthuisman.nz IPTV Merge) - THAT file is
  the auditable artifact. Caveat: entries pointing at plugin:// URLs
  resolve at play time and cannot be ffprobed directly - audit underlying
  HLS URLs where present, treat plugin:// entries separately.
- Proxy-layer option: github.com/euzu/tuliprox (ex m3u-filter) sits
  between sources and Kodi with a filter DSL + scheduled refresh
  (probe-based filtering unverified in its docs).

## Pipeline shape
Parse M3U (preserve KODIPROP/EXTVLCOPT) -> ffprobe per URL with those
headers -> classify {working, dead, geoblocked, audio-only, sub-720p} ->
emit filtered M3U + CSV. Defaults: 4-20 workers (keep LOW per provider -
connection caps), 10-60s timeouts, retries with backoff, second pass on
failures. Streams churn: re-audit on schedule (cron), regenerating the
playlist - matches iptv.merge's own scheduled-regen model.

## Legal note
Probing streams the owner legitimately accesses (FAST services like
Pluto/Samsung TV Plus via SlyGuy) = player-equivalent access; keep rates
player-like (provider connection caps/ToS). Don't circumvent geo/auth,
don't redistribute filtered playlists beyond personal devices.
