# SYN 1.3.2 — Continuous EPG and redesigned interface

This release consolidates the locally tested SYN 1.3b revisions 1–6.

## What's new

- **EPG vertical scrolling fixed (Rev6):** channel names and programme tracks share a real, continuous GTK4 vertical adjustment. Mouse-wheel scrolling works over both columns and can stop halfway through a channel row.
- **Touch-like programme timeline:** drag left/right with the mouse or use a horizontal wheel / trackpad; the time ruler follows the same timeline and extends towards earlier and later programmes.
- **EPG recording:** right-click a programme to schedule a DVR recording using its original XMLTV time boundaries. Favourite channels retain their original EPG data, including safe handling of duplicate channel entries.
- **Favourites:** outlined or filled-red hearts consistently replace stars, with a larger clickable area, scrollbar clearance and a subtle activation animation.
- **Settings:** separate Profile, Playback and Appearance pages; EPG refresh, MPV options, User-Agent selectors, themed appearance and a buffer slider.
- **Language:** fixes mixed Spanish/English labels in `es_ES`, `en_US` and `en_GB` without translating channel names or programme titles.
- **Desktop-aware DVR:** system-tray status and context menu on Plasma and compatible desktops; recording event notifications and an in-app REC indicator on GNOME.
- **Narrow windows:** better EPG clipping and responsive layout.

## Packages

Eight packages are built automatically by GitHub Actions: RPM, DEB, Arch/Pacman and Flatpak, each for **x86_64** and **aarch64 (ARM64)**, plus `SHA256SUMS`.

The DVR worker remains independent of the application window. The FFmpeg/libmpv audio-video pipeline is unchanged from SYN 1.3.1.

## Notes

The GTK4 vertical-scrolling fix was confirmed by the application owner on Fedora ARM64 in the local Rev6 Flatpak. Cross-distribution builds and any further acceptance checks are reported by the release workflow.
