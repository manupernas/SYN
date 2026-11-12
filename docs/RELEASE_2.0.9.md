# SYN 2.0.9 — Linux · Colourful EPG and Dracula / Alucard Classic

## What's new

- **10-colour programme guide:** the EPG no longer repeats one background colour for every event on a channel. Programme tiles advance through ten rich pastel / pop-art left-to-right gradients, while white labels remain readable. The programme's colour stays the same when the guide scrolls or refreshes.
- **Dracula Classic (dark)** — the official deep `#282A36` background, complementary surfaces, and seven matching accent swatches.
- **Alucard Classic (light)** — the official warm `#FFFBEB` background, dark foreground, and seven matching accent swatches.
- **Accent controls:** choose red, orange, yellow, green, cyan, purple or pink in **Settings → Appearance**. Custom hex accents remain available.
- **Complete integration:** GTK4 windows, library and channel list, Settings, popovers, EPG chrome and DVR appearance use the selected theme; the programme tiles retain their own colourful palette.
- **Native and Flatpak packages:** the new theme module is installed in every supported format.

## Packages

GitHub Actions builds **eight packages**: RPM, DEB, Pacman and Flatpak for both `x86_64` and `aarch64` (ARM64), plus `SHA256SUMS.txt`. The release is published only when all eight packages pass the build checks.

On Arch Linux, EndeavourOS and other compatible Arch-based distributions, SYN is also available from [AUR](https://aur.archlinux.org/packages/syn-iptv):

```bash
yay -S syn-iptv
# Or: paru -S syn-iptv
```

The AUR update runs after successful GitHub publication when the configured workflow is enabled. Flatpak bundles on GitHub are **not** a Flathub listing.

## Compatibility and privacy

- Uses GTK4, libadwaita, libmpv and FFmpeg, with users' own authorised M3U or Xtream-compatible IPTV sources.
- Preserves the existing application ID `com.mrseivane.Syn`, profiles, favourites, custom artwork and recording settings.
- No channels, subscriptions, provider credentials, playlists or recording data are included.
- No changes to streaming playback, Chromecast, timeshift or the FFmpeg DVR engine.
