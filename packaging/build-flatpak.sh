#!/usr/bin/env bash
# Build one local, native-architecture Flatpak bundle.
set -euo pipefail
VERSION="${1:?Expected version (e.g. 1.3.0)}"
ARCH="${2:?Expected x86_64 or aarch64}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Invalid release version' >&2; exit 2; }
[[ "$ARCH" == x86_64 || "$ARCH" == aarch64 ]] || { echo 'Invalid architecture' >&2; exit 2; }
[[ "$(uname -m)" == "$ARCH" ]] || { echo "Native runner required: $(uname -m) != $ARCH" >&2; exit 2; }
ROOT="$(cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p dist
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user --noninteractive flathub org.gnome.Platform//49 org.gnome.Sdk//49
flatpak-builder --user --arch="$ARCH" --force-clean --default-branch=master \
  --repo="$ROOT/.flatpak-repo" --install-deps-from=flathub \
  "$ROOT/.flatpak-build" com.mrseivane.Syn.yml
flatpak build-bundle --arch="$ARCH" \
  --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
  "$ROOT/.flatpak-repo" "dist/SYN-${VERSION}-${ARCH}.flatpak" com.mrseivane.Syn master
test -s "dist/SYN-${VERSION}-${ARCH}.flatpak"
echo "Flatpak ready: dist/SYN-${VERSION}-${ARCH}.flatpak"
