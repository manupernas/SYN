# SYN 1.3 — Linux release

SYN 1.3 brings live television, the electronic programme guide and recording controls together in a GTK4 desktop application for Linux.

## What's new

- **Shared-stream DVR playback:** record and watch the same channel through one provider connection. FFmpeg remuxes the incoming stream to an MKV recording and a local MPEG-TS output for libmpv, without transcoding.
- **Background recordings:** an independent DVR worker can keep recordings running after the SYN window closes, with reconnection handling and preserved recording segments where supported.
- **Recording indicator:** a GNOME-compatible StatusNotifierItem with a working D-Bus menu displays active recording channels and offers quick access to SYN and the recordings directory.
- **Improved EPG:** aligned channel/programme rows, coordinated vertical scrolling and smoother navigation.
- **Consistent DVR appearance:** the recording screen supports System, Light (pastel teal), Dark (graphite) and SYN Teal themes, including calendar, forms and recording lists.
- **User-service support:** `syn-dvr-worker.service` and `syn-dvr-tray.service` are supplied for background operation on systems with a compatible systemd user session.

## Downloads

This release requires **all eight builds to succeed**. Each download is specific to its CPU architecture.

| Distribution / format | Intel/AMD 64-bit | ARM64 |
| --- | --- | --- |
| Fedora / RPM | `syn-iptv-1.3.0-1.x86_64.rpm` | `syn-iptv-1.3.0-1.aarch64.rpm` |
| Debian / Ubuntu / DEB | `syn-iptv_1.3.0-1_amd64.deb` | `syn-iptv_1.3.0-1_arm64.deb` |
| Arch Linux / pacman | `syn-iptv-1.3.0-1-x86_64.pkg.tar.zst` | `syn-iptv-1.3.0-1-aarch64.pkg.tar.zst` |
| Flatpak bundle | `SYN-1.3.0-x86_64.flatpak` | `SYN-1.3.0-aarch64.flatpak` |

The native packages use the distribution's GTK4, PyGObject, libadwaita, FFmpeg and libmpv dependencies. Flatpak bundles use the GNOME runtime, which may need to be installed separately. **These files are GitHub Release downloads; this does not mean SYN is published on Flathub.**

## Installation

On the matching Linux distribution, install **only** the package for your architecture:

```bash
# Fedora
sudo dnf install ./syn-iptv-1.3.0-1.x86_64.rpm
# Debian / Ubuntu
sudo apt install ./syn-iptv_1.3.0-1_amd64.deb
# Arch Linux
sudo pacman -U ./syn-iptv-1.3.0-1-x86_64.pkg.tar.zst
# Flatpak — choose x86_64 or aarch64 to match your machine
flatpak --user install ./SYN-1.3.0-x86_64.flatpak
```

For systemd-based desktops, check which SYN DVR user service is already installed before switching package formats; do not run competing DVR workers against the same recording database. For **Flatpak**, configure the two user services after installation with `bash instalar-servicios-syn.sh` from the repository. The Flatpak bundle itself cannot execute a post-installation script. Do not restart a worker during an active recording. GNOME's recording indicator requires a StatusNotifierItem-compatible shell extension or system tray.

## Reliability and privacy

- Builds run on native x86_64 and aarch64 GitHub Actions runners; publication is blocked unless all eight packages exist and pass artifact checks. Cross-distro graphical playback still requires real-device validation.
- The `SHA256SUMS.txt` asset allows downloaded packages to be verified with `sha256sum -c SHA256SUMS.txt`.
- No channels, playlists, passwords, provider credentials, EPG data or recording files are included.
- Only record content you are authorised to access. Recording remains subject to provider limits and stream availability.

**Source:** https://github.com/manupernas/SYN
