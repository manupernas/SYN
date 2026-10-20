# SYN

**SYN** is a modern IPTV player for Linux, built with **GTK4**, **libadwaita**, and **libmpv**. It supports M3U playlists, Xtream-compatible providers, and XMLTV electronic programme guides (EPG).

SYN is currently an independently developed project and **is not yet available on Flathub**.

## Features

- Integrated video playback through libmpv.
- M3U playlists from local files or URLs.
- Xtream-compatible source profiles (bring your own provider).
- XMLTV EPG and channel browsing.
- Channel favourites and per-channel logos.
- Light, dark, and system-based appearance; customizable accent colour.
- Restores the last selected view, including favourites.
- Interface localisation: Spanish, US English, and British English.

## Requirements

Linux with a GTK4-capable desktop. Flatpak is the recommended packaging method for now. **ARM64 (`aarch64`) has been tested in Fedora; `x86_64` still requires testing.**

To build from this source tree, install `flatpak-builder` and the required Flatpak runtime/SDK. The included development manifest `com.mrseivane.Syn.yml` fetches additional multimedia dependencies during preparation.

```sh
bash construir-flatpak.sh
flatpak run com.mrseivane.Syn
```

The current manifest uses a local `dir` source and is **for local development**. It is **not a ready-to-submit Flathub manifest**.

A native Linux installer (`instalar.sh`) is also included for supported distributions, but Flatpak is the main installation method.

## Testing

With Python and `pytest` installed:

```sh
python3 -m pytest -q
```

The 1.0.2b source bundle passed 126 automated tests and 15 subtests in the preparation environment. These tests do not replace graphical tests on Fedora/Wayland or testing on other architectures.

## Privacy and content

SYN does **not** provide IPTV subscriptions, playlists, streams, or copyrighted media. Users must provide their own authorised sources. Do not add personal M3U files, account credentials, local configuration, or access tokens to Git.

## Generative AI disclosure

Parts of the code, documentation, development packaging and app icon were created with generative AI assistance. The project is maintained and tested by its developer. Any eventual Flathub submission will need to comply with Flathub's current disclosure and manifest-authorship rules.

## License

MIT — see [LICENSE](LICENSE).

---

### Español

**SYN** es un reproductor IPTV para Linux con GTK4 y libmpv. Admite listas M3U, fuentes compatibles con Xtream, guía EPG XMLTV, favoritos y temas visuales. **Aún no está publicado en Flathub.** Para empezar, consulta la compilación Flatpak descrita arriba.

**Proyecto:** https://github.com/manupernas/SYN
