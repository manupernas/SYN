# SYN - iptv & dvr

<p align="center">
  <img src="icons/256x256/apps/com.mrseivane.Syn.png" alt="SYN application icon" width="160">
</p>

<p align="center">
  <strong>Live television, a proper programme guide, and recordings — in one native Linux app.</strong>
</p>

<p align="center">
  <a href="https://github.com/manupernas/SYN/releases">Download releases</a> ·
  <a href="https://github.com/manupernas/SYN/actions">Build status</a> ·
  <a href="https://github.com/manupernas/SYN/issues">Report an issue</a>
</p>

**SYN** is a modern IPTV and DVR application built with **Python, GTK4, libadwaita and libmpv**. It supports your own M3U playlists and Xtream-compatible services, XMLTV programme guides, and recording live television using FFmpeg without re-encoding.

Designed for the Linux desktop, including GNOME and KDE Plasma. The interface supports Spanish, US English and British English, with light, dark and system appearance options.

> [!NOTE]
> SYN does **not** include television channels, IPTV subscriptions, playlists, or access credentials. Bring your own authorised sources. SYN is **not currently available on Flathub**.

## Screenshots

<table>
  <tr>
    <th>Live TV &amp; channels</th>
    <th>Programme guide</th>
    <th>Appearance &amp; settings</th>
  </tr>
  <tr>
    <td><a href="docs/screenshots/01-player-en.png"><img src="docs/screenshots/01-player-en.png" alt="SYN live TV and channel browser" width="310"></a></td>
    <td><a href="docs/screenshots/02-guide-en.png"><img src="docs/screenshots/02-guide-en.png" alt="SYN electronic programme guide" width="310"></a></td>
    <td><a href="docs/screenshots/03-settings-en.png"><img src="docs/screenshots/03-settings-en.png" alt="SYN settings window" width="310"></a></td>
  </tr>
</table>

Click a screenshot to view it at full size.

## Features

- **Integrated live TV:** video playback through libmpv, with channel browsing, categories and favourites.
- **M3U & Xtream:** local M3U files, remote playlists and Xtream-compatible profiles.
- **XMLTV EPG:** an interactive timeline, programme information and channel navigation.
- **Record now:** a compact red REC button starts an independent FFmpeg recording (`-c copy`, without transcoding).
- **Schedule recordings:** choose a channel, date and time, or **right-click a programme in the EPG** to schedule its actual broadcast time.
- **Recording library:** browse and play recordings inside SYN, locate their files and choose where new recordings are saved.
- **Background DVR:** a separate `systemd --user` service can continue recording after the SYN window closes.
- **Separate User-Agents:** configure the source/API User-Agent independently of video playback; recording uses the VLC User-Agent.
- **Desktop integration:** configurable appearance, channel logos and multilingual interface.

## Download & install

**Get the packages from [GitHub Releases](https://github.com/manupernas/SYN/releases).** Choose the file matching both your Linux distribution and CPU architecture.

| Linux distribution | Native package | CPU architectures |
| --- | --- | --- |
| **Fedora** | `.rpm` | x86_64, aarch64 (ARM64) |
| **Debian / Ubuntu** | `.deb` | amd64, arm64 |
| **Arch Linux / EndeavourOS** | `.pkg.tar.zst` | x86_64, aarch64 |

These **six native packages** form the required release set. GitHub Actions builds them for both architectures. **Flatpak** (`.flatpak`) and **AppImage** (`.AppImage`) are experimental, architecture-specific additional downloads: they appear in a release **only when both architecture builds for that format succeed**. Check the actual release assets rather than assuming an optional format is available.

To install a downloaded native package, use the appropriate command:

```bash
# Fedora — run from the directory containing your downloaded RPM
sudo dnf install ./syn-iptv-*.rpm

# Debian / Ubuntu — use the downloaded DEB instead
sudo apt install ./syn-iptv_*.deb

# Arch Linux — use the downloaded Pacman package instead
sudo pacman -U ./syn-iptv-*.pkg.tar.zst
```

Run **only the command for your distribution**, and download **only the package for your CPU architecture**. Native builds use your distribution's GTK4, PyGObject, libadwaita, libmpv and FFmpeg dependencies. Successful CI packaging does not substitute for testing every desktop and video driver.

### Flatpak (when included in a release)

Flatpak bundles are **not universal across CPU architectures**. Download the matching `x86_64` or `aarch64` file, then install it:

```bash
flatpak --user install ./SYN-1.2.2-x86_64.flatpak
flatpak run com.mrseivane.Syn
```

Replace the example filename with the actual asset. These bundles use the GNOME runtime; **SYN is not listed on Flathub**. For a source build, see [Building from source](#building-from-source).

## DVR in the background: systemd user service

SYN's GUI and its recording worker are separate. Playback uses **libmpv**, while the DVR worker records with **FFmpeg**; you can change channels or close the window without stopping an ongoing or scheduled recording **provided the background service is installed and running**.

After installing an **RPM, DEB or Pacman** package, enable the included user service:

```bash
systemctl --user daemon-reload
systemctl --user enable --now syn-dvr-worker.service
systemctl --user is-active syn-dvr-worker.service
```

The last command should print `active`. For logs and troubleshooting:

```bash
systemctl --user status syn-dvr-worker.service
journalctl --user -u syn-dvr-worker.service -n 50 --no-pager
```

For a **Flatpak installation**, use the helper included in this repository instead of the native service launcher:

```bash
bash instalar-servicio-dvr.sh
systemctl --user is-active syn-dvr-worker.service
```

Run the helper from a checkout of this repository, after installing SYN as a **user Flatpak**.

**Important:** the native and Flatpak installations use the same service name, `syn-dvr-worker.service`. Do not install or activate competing DVR workers. If you are switching package formats, inspect `systemctl --user cat syn-dvr-worker.service` and finish any ongoing recordings before changing the service. Background recording still requires the user service to be running and the computer to remain powered on and awake; it is not guaranteed across logout, suspend or shutdown.

## Building from source

Clone the repository and use the included development Flatpak manifest:

```bash
git clone https://github.com/manupernas/SYN.git
cd SYN
bash construir-flatpak.sh
bash instalar-servicio-dvr.sh
flatpak run com.mrseivane.Syn
```

This requires Flatpak, `flatpak-builder`, Git and the necessary GNOME runtime/SDK. The manifest uses local source files and is **not a ready-to-submit Flathub manifest**. You can also find a native development installer in `instalar.sh`.

## Development & release notes

The current DVR source version is **1.2.2**. It adds integrated recording, EPG scheduling, the independent worker and a separate User-Agent for Xtream/M3U source requests versus playback.

- [DVR 1.2.2 technical notes](docs/NOTAS_DVR_1.2.2.md)
- [Release notes](docs/RELEASE_1.2.2.md)
- [GitHub Actions](https://github.com/manupernas/SYN/actions) — native builds are required; experimental formats are optional

Run automated tests with:

```bash
python3 -m pytest -q
```

Automated tests and package builds do not guarantee that video playback works on every combination of Linux distribution, graphics driver and display server.

## Privacy, legal notice & license

Your playlists, Xtream credentials, EPG data and DVR recordings are user-owned local data. **Never commit account credentials, private stream URLs, recordings or `profiles.json` / `dvr.json` to Git.** Use only content you are authorised to access and record.

Parts of the code, documentation, packaging and application icon were created with generative AI assistance; the project is maintained and tested by its developer.

Licensed under the **MIT License** — see [LICENSE](LICENSE).
