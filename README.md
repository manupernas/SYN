# SYN · IPTV, Cinema & DVR for Linux

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/syn-readme-banner-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="docs/brand/syn-readme-banner-light.png">
    <img src="docs/brand/syn-readme-banner.png" alt="SYN — new colour-bar icon and SYN wordmark" width="640">
  </picture>
</p>

<p align="center">
  <strong>Your TV, films, series, programme guide and recordings — in one GTK4 desktop app.</strong><br>
  <em>Tu televisión, películas, series, guía y grabaciones — en una sola aplicación para Linux.</em>
</p>

<p align="center">
  <a href="https://github.com/manupernas/SYN/releases">Download / Descargar</a> ·
  <a href="https://github.com/manupernas/SYN/actions">Builds</a> ·
  <a href="https://github.com/manupernas/SYN/issues">Issues</a> ·
  <a href="docs/RELEASE_2.0.1.md">What's new in SYN 2.0.1</a>
</p>

**SYN 2.0.1** is a desktop IPTV player for Linux, written in Python with **GTK4, libadwaita and libmpv**, with an independent FFmpeg DVR, an interactive XMLTV EPG and a **TV · SERIES · CINEMA** library. It plays content from your own authorised **M3U** playlists and **Xtream-compatible** accounts. It never supplies channels or subscriptions.

The new interface uses the approved **icono_3** colour-bars icon in every launcher and package, plus the new SYN wordmark in light and dark variants. It offers **System, Light, Dark, SYN Teal, Nord Light/Dark and Gruvbox Light/Dark** themes, with optional custom accent colours. SYN starts on **live TV**, not the library landing page.

> [!IMPORTANT]
> **Bring your own legal IPTV sources.** SYN does not include playlists, credentials, channels or media. Films, series, artwork and EPG depend on what **your provider actually supplies**. SYN is distributed through GitHub Releases and **is not currently listed on Flathub**.

### Updated in SYN 2.0.1

SYN now keeps the left navigation rail gently tinted with the active accent in light themes and more muted in dark themes. In the mini-player, the Chromecast popup opens above its button when possible and stays usable when the pointer moves outside the video area. The recorder, Cast backend and playback engine are unchanged.

### New in SYN 2.0.0

The new three-zone GTK4 interface places navigation, channels and live video/EPG side by side.
A fullscreen EPG overlays the player without interrupting playback, and the compact player
supports freely resizable proportions after its initial 16:9 presentation. Controls and
their soft gradient appear on pointer hover, while a monochrome retro test card appears
when no channel is playing. Redesigned profile avatars, refined channel fallback artwork,
and all original DVR, Chromecast, recording scheduler, timeshift and library capabilities
are retained. The UI uses Spanish, English (US) and English (UK) based on the system locale.

**SYN 1.3.7** was the previous stable release; its source is retained in the
`backup/syn-1.3.7-before-v2` branch.

### Previously in 1.3.7

The GTK4 category/profile dropdown popovers now match the selected theme; the EPG time axis is legible on light themes. New SYN wordmarks from the project library appear in the sidebar and README. The **icono_3** icon is included at nine hicolor resolutions in native and Flatpak packages.

## At a glance

| TV & EPG | Films & Series | Recordings & Cast |
| --- | --- | --- |
| Live channel browser, per-profile favourites, category search, guide timeline and fullscreen playback | Dedicated **PERFIL → CINE / SERIES** library, searchable cover grids, series/season/episode navigation | Instant and scheduled **DVR** recordings, background worker, timeshift, PNG captures and Chromecast |

### Television

- **Live TV with libmpv:** embedded player, fullscreen, zapping and channel information without launching another application.
- **Multiple profiles:** switch between M3U files, remote M3U playlists and Xtream-compatible accounts.
- **Channels and favourites:** categories, search, channel logos, heart toggles and drag-and-drop favourite ordering, including the EPG and fullscreen channel selector.
- **Interactive EPG:** XMLTV/XMLTV.gz sources, programme details, timeline scrolling and navigation. Schedule a recording directly from a programme's context menu where EPG information is available.
- **Stream controls:** source/API User-Agent separate from playback, automatic reconnection, volume, screenshots and timeshift on compatible streams.

### New in 1.3.5: films, series and your library

Click **◎ PERFIL** to open the TV / SERIES / CINE selection. Normal startup still opens TV.

- **Cinema:** dedicated searchable film grid with poster art, titles and provider categories.
- **Series:** dedicated series grid and an episode browser with seasons/episodes for compatible Xtream catalogues.
- **Xtream catalogues:** SYN requests the provider's VOD and series APIs (`get_vod_streams`, `get_series`, `get_series_info`) **only when supported**.
- **M3U discovery:** entries clearly labelled as films or series by their groups/paths can appear in the corresponding library. Recognisable episode labels (for example `S01E01` or `1x02`) may be grouped under the same series. Other entries remain in TV to avoid misclassifying channels.
- **Resilient covers:** uses images supplied by the provider, caches them independently of TV logos, and displays original typographic/abstract artwork when no poster is available.
- **Designed for large libraries:** initial batches of cards, search and **Show more** help keep the interface responsive.

> **Provider compatibility:** VOD/series features are conditional; a TV-only M3U or Xtream subscription will not magically gain a film or series catalogue. Not all playlist naming conventions can be classified automatically.

### DVR, Chromecast and desktop integration

- **Record now:** the red REC button starts a separate FFmpeg capture, generally stream-copying (`-c copy`) without video re-encoding when possible.
- **Scheduled recording:** use the DVR planner (date/time/channel) or an available EPG programme; view and open recorded files from within SYN.
- **Background DVR:** the independent `syn-dvr-worker` is started/configured automatically on compatible `systemd --user` sessions and can continue after closing the window. It is **not** tied to the system tray.
- **Chromecast:** discover reachable devices and send streams using SYN's bundled Cast bridge, with 720p/1080p transcoding profiles where needed. The Flatpak bundles its Cast Python dependencies and FFmpeg encoder; native packages declare required dependencies.
- **No system tray icon:** `syn-dvr-tray` was removed in 1.3.5. The REC status remains inside the application.
- **Custom appearance:** adaptive System/Light/Dark/Teal themes, user accent colour, original icon, light/dark wordmark, channel logos, English (US/UK) and Spanish locale handling.

**Plug & play means:** install **one** matching package, launch SYN, add your source and use it. No separate Cast or DVR installation scripts are required on supported desktops. A working internet/LAN connection, provider account/playlist, compatible codecs and (for persistent background jobs) an active systemd user session are still needed. Some distributions, firewalls, VMs or Chromecast devices may require normal network configuration.

## Screenshots

<!-- SYN_SCREENSHOT_GALLERY_200 -->
<p align="center">
  <a href="docs/screenshots/2.0.0/01-tv-epg-light.png"><img src="docs/screenshots/2.0.0/01-tv-epg-light.png" width="940" alt="Live TV and embedded programme guide"></a>
</p>
<p align="center"><strong>Live TV and embedded EPG</strong> · Browse channels and schedules alongside the player</p>

<table>
  <tr>
    <td align="center" valign="top"><a href="docs/screenshots/2.0.0/02-guide-dark.png"><img src="docs/screenshots/2.0.0/02-guide-dark.png" width="440" alt="Full programme guide in dark mode"></a><br><strong>Full programme guide in dark mode</strong></td>
    <td align="center" valign="top"><a href="docs/screenshots/2.0.0/03-cinema-dark.png"><img src="docs/screenshots/2.0.0/03-cinema-dark.png" width="440" alt="Cinema library and visual catalogue"></a><br><strong>Cinema library and visual catalogue</strong></td>
  </tr>
  <tr>
    <td align="center" valign="top"><a href="docs/screenshots/2.0.0/04-dvr-light.png"><img src="docs/screenshots/2.0.0/04-dvr-light.png" width="440" alt="Schedule recordings and browse the DVR library"></a><br><strong>Schedule recordings and browse the DVR library</strong></td>
    <td align="center" valign="top"><a href="docs/screenshots/2.0.0/05-appearance-dark.png"><img src="docs/screenshots/2.0.0/05-appearance-dark.png" width="440" alt="Appearance settings and custom accent colours"></a><br><strong>Appearance settings and custom accent colours</strong></td>
  </tr>
</table>

*Actual SYN 2.0 screenshots in English (US). The local recording directory has been obscured for privacy. SYN does not provide TV channels or subscriptions.*

## Download: choose the right package

Get the **2.0.1** release assets from **[GitHub Releases](https://github.com/manupernas/SYN/releases)**. The project builds eight packages: four formats × two CPU architectures.

| Your Linux system | File extension | Architecture label | Installer |
| --- | --- | --- | --- |
| Fedora | `.rpm` | `x86_64` or `aarch64` | DNF |
| Ubuntu / Debian | `.deb` | `amd64` (Intel/AMD) or `arm64` (ARM) | APT |
| Arch / EndeavourOS | `.pkg.tar.zst` | `x86_64` or `aarch64` | Pacman |
| Other distributions / sandboxed | `.flatpak` | `x86_64` or `aarch64` | Flatpak |

**Architecture check:** run `uname -m`. `x86_64` means Intel/AMD 64-bit. `aarch64` means ARM64; Debian package names call that `arm64` and Intel/AMD `amd64`. **Never install an ARM package on x86_64 or vice versa.**

### Fedora (RPM)

Download the file matching your architecture, e.g. `syn-iptv-2.0.1-1.aarch64.rpm`, open a terminal in the Downloads directory and run:

```bash
sudo dnf install ./syn-iptv-2.0.1-1.*.rpm
```

DNF resolves package dependencies. Start **SYN** from the app launcher or run `syn`.

### Debian / Ubuntu (DEB)

Download the matching `amd64` or `arm64` DEB, then:

```bash
sudo apt install ./syn-iptv_2.0.1-1_*.deb
```

APT resolves dependencies. Start **SYN** from the app launcher or run `syn`. Required runtime libraries must be available in your distribution's repositories.

### Arch Linux / EndeavourOS (Pacman)

Download the matching `x86_64` or `aarch64` package, then:

```bash
sudo pacman -U ./syn-iptv-2.0.1-1-*.pkg.tar.zst
```

Pacman resolves packages available in your configured repositories. Start **SYN** from the app launcher or run `syn`. Some ARM-specific distributions may need equivalent dependencies in their own repositories.

### Flatpak (Fedora, Debian, Arch and others)

1. Install **Flatpak** from your distribution's package manager if you don't already have it.
2. Download `SYN-2.0.1-x86_64.flatpak` or `SYN-2.0.1-aarch64.flatpak`, matching `uname -m`.
3. Install the bundle and start SYN:

```bash
flatpak install --user ./SYN-2.0.1-*.flatpak
flatpak run com.mrseivane.Syn
```

If the GNOME runtime is missing, Flatpak can offer to install it (an internet connection and a configured runtime remote may be required). **This is a GitHub bundle, not a Flathub listing.** Flatpak app ID: `com.mrseivane.Syn`.

**Already installed system-wide?** To update that installation instead of creating a second user copy, use:

```bash
sudo flatpak install --system --reinstall ./SYN-2.0.1-*.flatpak
flatpak run --system --branch=master com.mrseivane.Syn
```

**Avoid duplicate installations:** do not install both `--user` and `--system` unless you intentionally need separate copies; the default launcher may otherwise select the wrong one. Check using `flatpak list --app --columns=application,branch,installation`.

<details>
<summary><strong>Instalación rápida en español</strong></summary>

Descarga el archivo de **SYN 2.0.1** para tu distribución y procesador desde [Releases](https://github.com/manupernas/SYN/releases). Comprueba `uname -m`: `x86_64` es Intel/AMD y `aarch64` es ARM64 (en DEB aparece como `arm64`). Ejecuta **solo uno** de estos comandos desde la carpeta donde esté el archivo descargado:

```bash
# Fedora
sudo dnf install ./syn-iptv-2.0.1-1.*.rpm

# Debian / Ubuntu
sudo apt install ./syn-iptv_2.0.1-1_*.deb

# Arch / EndeavourOS
sudo pacman -U ./syn-iptv-2.0.1-1-*.pkg.tar.zst

# Flatpak — instalación de usuario
flatpak install --user ./SYN-2.0.1-*.flatpak
flatpak run com.mrseivane.Syn
```

**Plug & play:** al abrir SYN, añade tu perfil M3U o Xtream. No hace falta ejecutar ningún script adicional para el DVR ni para Chromecast; los servicios se preparan automáticamente en escritorios compatibles. Los catálogos CINE y SERIES aparecen únicamente si tu proveedor los ofrece. Las grabaciones en segundo plano requieren que el sistema siga encendido y una sesión de usuario adecuada.

</details>

## Services, recording safety and limitations

The independent background services are **`syn-dvr-worker.service`** (recordings) and **`syn-cast-bridge.service`** (Chromecast). There is **no `syn-dvr-tray.service`** in 1.3.5. SYN prepares/manages the needed services when it starts, without restarting an already active recording.

```bash
systemctl --user status syn-dvr-worker.service syn-cast-bridge.service
```

On Linux systems without `systemd --user` or with restricted Flatpak portals, the background service may be unavailable; TV playback can still work. Closing a window is not the same as logging out: logout, suspend, shutdown, unstable network connections and IPTV provider connection limits can interrupt a capture. Chromecast discovery usually needs direct LAN access; bridged/isolated VMs can block multicast discovery.

## Build from source (developers)

```bash
git clone https://github.com/manupernas/SYN.git
cd SYN
python3 -m pytest -q
bash construir-flatpak.sh
flatpak run com.mrseivane.Syn
```

The source build requires Git, `flatpak-builder`, the GNOME runtime/SDK and network access to dependencies. **You do not need to run the old `instalar-servicios-syn.sh` or `instalar-servicio-cast.sh` after installation.** These are not end-user installation steps.

The GitHub Actions release workflow produces RPM, DEB, Pacman and Flatpak binaries independently for **x86_64** and **aarch64**. A GitHub Release is published only after all eight build jobs succeed. See [the release notes](docs/RELEASE_2.0.1.md).

## Privacy, legal use and licence

SYN stores profiles, playlist configuration, local favourites and recordings on your own machine. Do not commit private provider URLs, login credentials, `profiles.json`, `dvr.json`, playlist files or recordings. Stream only content that you are authorised to access and record.

Project code, documentation, packaging and artwork have included AI assistance; the project is maintained and tested by its developer. Licensed under the **[MIT License](LICENSE)**.

### GNOME dock: if an older icon persists

SYN includes the approved `icono_3` at nine icon sizes for both native and Flatpak packages. Some GNOME icon themes or stale launchers can still override an application icon by name, even though the application grid displays the updated artwork. On affected desktops, run the optional host-side helper from this repository:

```bash
bash packaging/reparar_icono_gnome.sh
```

It safely backs up any existing per-user launcher, creates an override using the exported icon's absolute path, and leaves IPTV profiles, favourites, credentials and recordings unchanged. You may need to sign out and back into GNOME to refresh the dock.
