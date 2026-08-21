# StarWave — Kodi repository

Add-on repository for the **StarWave** Kodi 21 "Omega" build.

## Install

In Kodi:

1. **Settings → System → Add-ons → Unknown sources → On**
2. **Settings → File Manager → Add source** → `https://strfck3r.github.io/starwave/` → name it `StarWave`
3. **Add-ons → Install from zip file** → `StarWave` → `repository.starwave` → the zip
4. **Add-ons → Install from repository → StarWave Repository → Program add-ons → StarWave Wizard** → Install
5. Open **StarWave Wizard** → **Install the StarWave build**

The wizard downloads the build, applies it, and closes Kodi. Reopen Kodi and you are on StarWave.

## What is here

| | |
|---|---|
| `addons.xml`, `addons.xml.md5` | The repository index Kodi reads |
| `repository.starwave/` | The repository add-on itself |
| `plugin.program.starwave.wizard/` | Installs the build |
| `skin.NTVaura/` | The StarWave skin |
| `resource.images.Aura/` | Wallpapers and splash images |
| `screensaver.picture.slideshow.Aura/` | Screensaver |
| `plugin.program.LegionHubs/` | Star Hubs — the setup / re-auth screen |
| `script.module.myaccounts/` | Accounts module |

The build payload the wizard downloads is attached to the [latest release](../../releases/latest).

Everything except the wizard and the repository comes from a build whose original maintainer
disappeared and whose server went offline. These are hosted so they remain installable.
