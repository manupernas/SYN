# SYN 1.3.5 — TV, CINE, SERIES and refreshed identity

**Release scope:** Linux x86_64 and ARM64/aarch64. GitHub-native package builds: RPM, DEB, Pacman and Flatpak for both architectures.

## Highlights

- New **PERFIL** library with TV / SERIES / CINE; live TV remains the default home screen.
- Film catalogue and series browser with episodes, Xtream-compatible VOD queries and labelled M3U group classification.
- Searchable, responsive cover grids, remote provider posters, private on-disk cover cache and original abstract cover placeholders.
- Consistent column widths, batched list loading and source-profile counts.
- Original **SYN colour-bars icon**, deployed in nine hicolor dimensions, and a light/dark-aware wordmark above the channel list.
- Polished four-theme support: System, Light, Dark and Teal, including GTK system-dark response and custom accent.
- Removal of the **system-tray service**. In-app DVR status and the independent recording worker remain.
- **Plug & play** packaging: bundled Cast components/FFmpeg for Flatpak; distribution dependencies declared for RPM/DEB/Pacman; first-launch background service setup on compatible `systemd --user` sessions.
- Improved installation instructions, architecture table and safeguards against duplicate user/system Flatpaks.

## Provider availability and limitations

Film/series catalogues depend on authorised M3U/Xtream sources, provider APIs and metadata. Xtream users may browse movies and seasons/episodes only if the provider supplies them. M3U channel classification relies on group labels and common episode markers, and may be incomplete. Nothing is bundled.

Chromecast requires reachable LAN devices and working local networking; VPNs/VM isolation and firewall rules can prevent discovery. Background recording requires a suitable user session and an awake computer. The application does not stop an existing recording worker on launch.

## Build and verification

Eight assets are published only when the tagged release workflow validates sources and all architecture-specific package jobs complete. Run source checks with `python3 -m pytest -q`.

## Upgrade note

For Flatpak, update the existing installation scope rather than creating a second user copy. If your current installation is system-wide, use `sudo flatpak install --system --reinstall ./SYN-1.3.5-<arch>.flatpak` and open with `flatpak run --system --branch=master com.mrseivane.Syn`. Avoid `--force-remove` and never delete `~/.var/app` to upgrade.
