#!/usr/bin/env bash
set -euo pipefail
FORMAT="${1:?rpm, deb o pacman}"
VERSION="${2:?versión, p.ej. 1.2.2}"
ARCH="${3:?x86_64 o aarch64}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Versión inválida' >&2; exit 2; }
[[ "$ARCH" == x86_64 || "$ARCH" == aarch64 ]] || exit 2
[[ "$FORMAT" == rpm || "$FORMAT" == deb || "$FORMAT" == pacman ]] || exit 2
ROOT="$(cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
command -v fpm >/dev/null || { echo 'Instala fpm (gem install fpm).' >&2; exit 2; }
mkdir -p dist
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
bash packaging/stage-native.sh "$STAGING" >/dev/null
case "$FORMAT" in
  rpm)
    case "$ARCH" in x86_64) pkgarch=x86_64;; aarch64) pkgarch=aarch64;; esac
    outfile="dist/syn-iptv-${VERSION}-1.${pkgarch}.rpm"
    deps=(python3 python3-gobject gtk4 libadwaita mpv-libs ffmpeg python3-chromecast)
    ;;
  deb)
    case "$ARCH" in x86_64) pkgarch=amd64;; aarch64) pkgarch=arm64;; esac
    outfile="dist/syn-iptv_${VERSION}-1_${pkgarch}.deb"
    deps=(python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 libmpv2 ffmpeg python3-pychromecast)
    ;;
  pacman)
    pkgarch="$ARCH"
    outfile="dist/syn-iptv-${VERSION}-1-${pkgarch}.pkg.tar.zst"
    deps=(python python-gobject gtk4 libadwaita mpv ffmpeg python-pychromecast)
    ;;
esac
args=(-s dir -t "$FORMAT" -n syn-iptv -v "$VERSION" --iteration 1 -a "$pkgarch"
  --description 'SYN IPTV: reproductor GTK4 con EPG y DVR independiente'
  --license MIT --url 'https://github.com/manupernas/SYN'
  --maintainer 'manupernas <120756979+manupernas@users.noreply.github.com>'
  --vendor 'Mr. Seivane' -C "$STAGING" -p "$ROOT/$outfile")
for dep in "${deps[@]}"; do args+=(--depends "$dep"); done
[[ "$FORMAT" == pacman ]] && args+=(--pacman-compression zstd)
fpm "${args[@]}" .
test -s "$outfile"
case "$FORMAT" in
  rpm) rpm -qp --qf '%{NAME} %{ARCH}\n' "$outfile";;
  deb) dpkg-deb -f "$outfile" Package Architecture;;
  pacman) bsdtar -xOf "$outfile" .PKGINFO | grep -E '^(pkgname|arch) = ';;
esac
printf 'Construido: %s\n' "$outfile"
