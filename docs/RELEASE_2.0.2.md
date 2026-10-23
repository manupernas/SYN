# SYN 2.0.2 — Linux

Maintenance release: readable mini-player Chromecast popover across GTK themes.

## Fixes
- **Cast menu contrast:** the popup now has its own opaque, theme-matched surface and foreground colours. Previously, text inherited white from the video playback toolbar and became unreadable on the light menu.
- **Controls:** device selection and stop buttons use a dedicated style; the connection limit spinner and quality slider remain visible and legible.
- **Compact footprint:** modestly reduced internal margins and spacing. The menu continues to prefer opening upward and remains open after the pointer leaves the video.

## Unchanged
- Casting discovery, selection, 720p/1080p quality presets, stream sharing, FFmpeg DVR and recording service.
- Fullscreen EPG, video rendering, library, favourites, theme accent selection, Spanish/en_US/en_GB locales.
- App ID `com.mrseivane.Syn` and its profile/storage directories.

Build matrix: RPM, DEB, Pacman and Flatpak for x86_64 and aarch64. Use your own authorised IPTV sources.
