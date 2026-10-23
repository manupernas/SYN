# SYN 2.0.1 — Linux

Polish release based on SYN 2.0.0.

## What's improved
- **Subtle left navigation rail:** in light themes, a gentle ~8% wash follows the chosen accent or theme; in dark themes, the rail is more muted and uses only a ~3.5% accent wash. System mode tracks the desktop's actual light/dark preference.
- **Chromecast in mini-player:** the Chromecast popover prefers opening above its button and keeps the hover-only controls mapped until the popup closes. Moving the pointer outside the player no longer makes the menu disappear.

## Unchanged
- GTK4 and libmpv player; fullscreen guide and EPG; user profiles and favourites.
- Background DVR and its recordings/worker; Chromecast Cast bridge and 720p/1080p choices.
- App ID `com.mrseivane.Syn`, data directories and native/Flatpak service integrations.

Release provides RPM, DEB, Pacman and Flatpak for x86_64 and aarch64 via the existing eight-package GitHub Actions workflow. SYN does not include IPTV subscriptions or streams.
