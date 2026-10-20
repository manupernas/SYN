#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:?versión}"
ARCH="${2:?x86_64 o aarch64}"
[[ "$ARCH" == x86_64 || "$ARCH" == aarch64 ]] || exit 2
ROOT="$(cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p dist
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user --noninteractive flathub org.gnome.Platform//49 org.gnome.Sdk//49
flatpak-builder --user --force-clean --repo="$ROOT/.flatpak-repo" \
  --install-deps-from=flathub "$ROOT/.flatpak-build" com.mrseivane.Syn.yml
flatpak build-bundle --arch="$ARCH" "$ROOT/.flatpak-repo" \
  "dist/SYN-${VERSION}-${ARCH}.flatpak" com.mrseivane.Syn
flatpak info --show-metadata "dist/SYN-${VERSION}-${ARCH}.flatpak" 2>/dev/null || true
test -s "dist/SYN-${VERSION}-${ARCH}.flatpak"
