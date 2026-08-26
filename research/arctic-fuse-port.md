# Research: Porting Sports + Live TV into Arctic Fuse

2026-08-25, external sources. For initiative (c) - shape before build.
Local facts (CLAUDE.md): Arctic Fuse 3 is ALREADY installed alongside
StarWave; switch mechanism exists (writes lookandfeel.skin, hard-exits);
config lives in arctic-fuse/, published as layouts/arctic-fuse-config.zip;
watch the settings-hash trap (same as skin.NTVaura.hash) and the
script.autoruns/TMDbHelper black-widget incident.

## Fundamentals
- Author jurialmunkey (also TMDbHelper + script.skinvariables). AF2
  archived/deprecated Jan 2026; AF3 (alpha, v3.2.x) is current
  (github.com/jurialmunkey/skin.arctic.fuse.3). Kodi v21 Omega minimum
  (xbmc.gui 5.17.0 per addon.xml). Deps: skinvariables, texturemaker,
  TMDbHelper. Distributed via jurialmunkey's own repo (needs "unknown
  sources" + any-repo updates).

## The architectural fact that shapes everything
AF does NOT use script.skinshortcuts (StarWave's menu system) - it uses
script.skinvariables. Menu data = self-contained human-readable JSON in
addon_data/script.skinvariables/nodes/skin.arctic.fuse*/ - hand-editable,
shareable by dropping the file in and restarting (forum pid=3172922).
So "overlay" is really a REBUILD of the two sections - mitigated by:
- AF's skinshortcuts IMPORT button (Skin Settings > Menus > Customise >
  Import) pulls labels/paths from another skin's skinshortcuts data
  (forum-sourced, flagged).
- What transfers cleanly: plugin:// widget paths, library nodes,
  favourites, ActivateWindow targets. What doesn't: widget styling,
  skinshortcuts templates/overrides (compiled per-skin).

## Port recipe (the durable shape)
1. Extract Sports + Live TV plugin:// paths from StarWave's skinshortcuts
   .DATA.xml.
2. Re-declare both as AF3 custom home items + widgets (GUI dialogs or
   direct JSON node edit).
3. Version the resulting nodes/skin.arctic.fuse.3/*.json as the build
   artifact (extend arctic-fuse-config.zip) - the AF-native equivalent of
   what skinshortcuts .DATA.xml is to StarWave.
- Live TV: AF has native PVR support - the phase-5 IPTV guide (iptv.merge
  + IPTV Simple) lights up AF's native TV section too; custom addon paths
  ride as widgets.
- Reference AF-based build: github.com/Bigmoco/TMDBase (AF2-based).

## Pitfalls
- Shield/Android: anecdotal stutter/crash reports on Shield TV 2019
  (heavy TMDbHelper widget rows are the usual cause) - limit per-row
  widgets; test on-device before committing the switch.
- Start on AF3 despite alpha (AF2 is dead). Forum claims are
  search-excerpt-sourced (kodi forum 403s fetchers) - verify the Import
  button on-device.
