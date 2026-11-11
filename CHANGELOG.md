# Changelog

## [2.0.8] — 2026-11-11

### Improved
- Single-click tuning in the main TV channel list; clicking a channel again requests a fresh playback session.
- Right-click programme information in the EPG, including title, channel, time and synopsis, with the DVR scheduling action preserved.
- Windowed mini-player retains a 16:9 canvas while resizing the main window.
- Mini-player rounded corners (14 px), leaving fullscreen video unconstrained.

### Notes
- Reuses the existing GTK4/libmpv video renderer and DVR infrastructure.
- Builds for RPM, DEB, Pacman and Flatpak on x86_64 and aarch64.


## [1.3.6] — 2026-10-23

### Added
- **Nord Light and Nord Dark themes**, based on the Nord colour palette, with Frost and Aurora accent options.
- **Gruvbox Light and Gruvbox Dark themes**, with seven matching accent colours.
- **Pop-art channel artwork** for channels without a usable logo. Full-bleed tiles are generated consistently from each channel's name and category; official and custom logos always take priority.

### Improved
- **Electronic Programme Guide (EPG):** brighter, more colourful programme tiles with left-to-right gradients and readable text.
- **EPG navigation:** smoother press-and-drag horizontal panning, natural vertical scrolling, and less intrusive programme-grid rebuilding while live video is playing.
- **Appearance switching:** applying a theme or accent colour no longer unnecessarily reloads the channel list or interrupts playback.
- **Branding and layout:** refined SYN wordmark placement, sidebar spacing, title-bar artwork, and application icon presentation.
- **Localisation:** reviewed Spanish, US English and British English interface strings, including Settings, themes, the media catalogue, Timeshift, Cast and DVR. US/UK spelling and clock conventions remain distinct.

### Fixed
- EPG interaction could become sluggish or temporarily unresponsive while a channel was playing.
- Unnecessary channel-list reloads when saving appearance-only changes.
- Excessive empty space and inconsistent image sizing around sidebar and header branding.

### Notes
- Existing channel logos, playback features, DVR, Chromecast, profiles and user data are preserved.
- This release builds eight distribution packages through GitHub Actions and checks their SHA-256 hashes before publishing.
