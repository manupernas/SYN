# SYN 1.3.3 — Chromecast, favourites and timeshift

**Official Linux release:** RPM, DEB, Arch Linux and Flatpak for ARM64/aarch64 and x86_64.

## Improvements

- Reorder favourites with drag-and-drop and a **visual preview of the entire channel pill**; an orange insertion marker indicates the destination.
- Save favourite order independently for each IPTV profile and apply it to the EPG, quick list and fullscreen channel selection.
- Chromecast streaming through a separate host service with **HLS H.264 Baseline + AAC-LC**, preserving the stable SYN CAST Beta 6.2 video path.
- A vivid mandarin-orange Cast button, with the Chromecast symbolic icon, in normal and fullscreen mode.
- Connection-aware casting with exclusive colourbars or parallel local viewing, respecting DVR reservations.
- Live timeshift, screenshots and reconnection improvements included from the approved local build.

## Chromecast works automatically on installation

**No terminal commands and no manual Cast-service setup.** Native RPM, DEB and
Pacman packages declare PyChromecast and FFmpeg as package-manager dependencies
and include an automatically activated systemd user service. Flatpak bundles
PyChromecast, x264 and FFmpeg internally and starts its own bridge using the
user's session on first app launch; it does not require host Python or ffmpeg.

Chromecast and the machine running SYN still require LAN discovery (mDNS) and
a network path for the receiver to reach TCP 18977; restrictive networks and
virtual-machine NAT can prevent discovery. This is a network prerequisite, not
an application installation step. No IPTV playlists or passwords are included.

## Cast 6.5 validated improvements

See [Cast 6.5 final notes](CAST_6_5_FINAL.md) for shared HLS, reliable zapping and rejoining, fixed light-theme icon, and 720p/1080p quality slider. 720p is recommended on Fedora virtualized. The user validated Cast, local playback and DVR; occasional start-up buffering may occur.
