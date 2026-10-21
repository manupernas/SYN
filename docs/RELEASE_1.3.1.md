# SYN 1.3.1 — Linux release

SYN 1.3.1 fixes automatic background recording service activation for Linux
distributions and standalone Flatpak bundles.

## Fixed

- **Updated icon:** the approved transparent multicolor TV test-card icon
  replaces the old icon throughout desktop launchers, app UI and recording tray.
- **Automatic DVR startup:** on the first app launch, SYN enables and starts
  `syn-dvr-worker.service` and `syn-dvr-tray.service` in the user's systemd session.
- **Native packages:** RPM, DEB and Arch packages ship both services and vendor
  user presets; SYN also activates them in the current session upon first launch.
- **Flatpak bundles:** first GUI launch installs and activates host user units
  through Flatpak's existing host spawn permission. No install-time hooks or
  manual `systemctl` commands are required.
- **No interrupted recordings:** an already running DVR worker is never
  restarted. A Flatpak will not overwrite a custom/native active worker.
- **REC safety:** SYN will not terminate live IPTV before the independent
  recorder heartbeat is confirmed. A clear warning replaces indefinite waiting.

## Downloads

The release requires **eight builds** (four formats on both architectures):

| Format | x86_64 | ARM64 |
| --- | --- | --- |
| Fedora / RPM | `syn-iptv-1.3.1-1.x86_64.rpm` | `syn-iptv-1.3.1-1.aarch64.rpm` |
| Debian / Ubuntu / DEB | `syn-iptv_1.3.1-1_amd64.deb` | `syn-iptv_1.3.1-1_arm64.deb` |
| Arch / Pacman | `syn-iptv-1.3.1-1-x86_64.pkg.tar.zst` | `syn-iptv-1.3.1-1-aarch64.pkg.tar.zst` |
| Flatpak | `SYN-1.3.1-x86_64.flatpak` | `SYN-1.3.1-aarch64.flatpak` |

Flatpak service setup runs on the **first GUI launch**, not inside its installer.
A compatible active systemd user session is necessary. If you already use a
native DVR worker or custom systemd services, they are not overwritten. Only
one recorder should handle a given configuration database at a time.

This patch changes no video codecs, playback engines, or stream credentials.
No IPTV playlists, channel details or provider secrets are packaged.

## Verification

CI checks source, verifies the nine new icon PNGs and creates eight architecture-specific packages. Successful
CI packaging does not replace real-world video and systemd service testing.
Checksum verification: `sha256sum -c SHA256SUMS.txt`.
