# SYN 1.3.4 — Chromecast plug and play

**Release:** eight Linux packages: RPM, DEB, Pacman and Flatpak for x86_64 and ARM64/aarch64.

## Chromecast reliability and quality

- **Mi Box / Android TV:** when a receiver does not fetch the HLS manifest after LOAD, retry without opening a second IPTV provider connection; ignore stale IDLE/ERROR events until the device really requests the stream.
- **1080p:** Full HD output 6300 kbps target, 7500 kbps max, 14000 kbps VBV; H.264 Main/CABAC, deblock, fast x264 preset, 25 fps and faster initial HLS segments.
- **720p:** existing 2500 kbps H.264 Baseline configuration is unchanged.
- **Startup diagnostics:** identify encoder speeds that cannot sustain playback instead of hiding indefinite buffering.
- **One shared provider stream:** local and Chromecast continue using the same HLS relay; DVR reservations retain priority.

## Plug and play

All eight packages ship the Chromecast bridge. Flatpak includes FFmpeg/x264 and PyChromecast; native packages declare the respective system dependencies. SYN starts its own user-level Cast service automatically on launch, with no terminal setup needed. For upgrading a Flatpak with the known local Mi Box V2 recovery override, SYN retires only that recognised temporary override when no Cast session is active; unrelated services and DVR are not modified.

Network access and mDNS discovery to the Chromecast still require both devices on a compatible LAN. The project ships no IPTV credentials, playlists or proprietary streams.

This source integrates patches verified on Mi Box 4 under Fedora ARM64. GitHub Actions must still build and validate all eight packages before a release is published.
