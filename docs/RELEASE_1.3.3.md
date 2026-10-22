# SYN 1.3.3 — Chromecast, favourites and timeshift

**Official Linux release:** RPM, DEB, Arch Linux and Flatpak for ARM64/aarch64 and x86_64.

## Improvements

- Reorder favourites with drag-and-drop and a **visual preview of the entire channel pill**; an orange insertion marker indicates the destination.
- Save favourite order independently for each IPTV profile and apply it to the EPG, quick list and fullscreen channel selection.
- Chromecast streaming through a separate host service with **HLS H.264 Baseline + AAC-LC**, preserving the stable SYN CAST Beta 6.2 video path.
- A vivid mandarin-orange Cast button, with the Chromecast symbolic icon, in normal and fullscreen mode.
- Connection-aware casting with exclusive colourbars or parallel local viewing, respecting DVR reservations.
- Live timeshift, screenshots and reconnection improvements included from the approved local build.

## Important: Chromecast setup on fresh installations

**Casting requires a separate host service.** Install host Python PyChromecast and FFmpeg with `libx264` / `aac`, then run `bash instalar-servicio-cast.sh` as your normal user. Native packages also install the helper as `syn-cast-setup`. It refuses to replace an existing Cast service. It does not touch recordings. The Chromecast must reach the host on TCP 18977; a VM may require bridged networking or firewall configuration.

- Fedora: `sudo dnf install python3-chromecast` and then `syn-cast-setup` for the native package, or run the helper from this repository for Flatpak.
- On other distributions install an equivalent PyChromecast host package.
- The app includes **no** channels, subscription, streaming URLs, user profiles, credentials or DVR recordings.

Chromecast was user-tested successfully on Fedora ARM64 using the Beta 6.2 transcoding mode. Other distros and receivers still need testing. The package build matrix runs offline verification; it does not constitute hardware compatibility testing.
