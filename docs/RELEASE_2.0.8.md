# SYN 2.0.8 — Linux · Channel interactions and 16:9 mini-player

## What's new

- **Single-click channel selection:** click a channel in the main TV list to start playback. Another activation of the same channel requests a restart of the stream.
- **Programme details in the EPG:** right-click a programme to view its title, channel, original EPG time range and synopsis. The **Schedule recording** action stays available in the same popover.
- **Consistent 16:9 windowed video:** resizing the SYN window no longer stretches the mini-player canvas to an arbitrary ratio. Video keeps its own native aspect ratio within the 16:9 canvas.
- **Rounded mini-player:** 14-pixel corners for the windowed player. Fullscreen remains edge-to-edge without rounded corners.

## Compatibility

- GTK4, libadwaita and libmpv playback engine unchanged.
- Existing IPTV profiles, custom logos, favourites, EPG data, Chromecast, timeshift and DVR formats preserved.
- No channels, playlists, credentials or recordings included.

## Downloads

- RPM: x86_64 / aarch64
- DEB: amd64 / arm64
- Arch Linux package (Pacman): x86_64 / aarch64
- Flatpak: x86_64 / aarch64

The release workflow validates the source, builds all eight packages and publishes SHA-256 checksums. The changes should be smoke-tested in GTK4 on Fedora before relying on them in production.
