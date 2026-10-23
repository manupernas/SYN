# SYN 1.3.7 — Theme consistency and new branding

Release date: 2026-10-23

## Fixed
- GTK4 dropdown popovers, including category and profile menus, now follow the selected Light, Dark, SYN Teal, Nord or Gruvbox palette rather than inheriting an unrelated dark popup background. System keeps the host GTK theme.
- EPG time-axis hour labels are readable against light backgrounds, using a theme-aware Cairo text colour. The EPG geometry, timeline and playback pipeline are unchanged.

## New visual identity
- Updated header/sidebar SYN wordmark using the **logo_dark.png** and **logo_light.png** assets from the user's project library, cropped to their visible content and switched automatically with the colour scheme.
- Updated README artwork for both GitHub light and dark modes.
- All launcher and dock icons in RPM, DEB, Pacman and Flatpak now derive from the approved **icono_3.png** in the SYN project library, with nine correctly sized hicolor PNGs.
- The native packages ship a desktop entry plus AppStream metadata with a stock icon name to aid recognition by compatible software centres.

## Distribution
- Linux x86_64 and ARM64/aarch64 packages: RPM, DEB, Arch Linux/pacman and Flatpak.
- The application, recordings, playlist data, networking, DVR and streaming code are unchanged aside from visual branding and the previously validated GTK4/EPG corrections.

Note: Whether a locally downloaded RPM appears in GNOME Software's Installed list depends on the distribution's package-management and AppStream integration. `sudo dnf remove syn-iptv` always remains available on Fedora.

For GNOME icon-theme conflicts, the optional helper `packaging/reparar_icono_gnome.sh` uses the correct installed PNG without changing application data.
