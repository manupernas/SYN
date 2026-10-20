#!/usr/bin/env bash
set -euo pipefail
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -f "$TARGET/com.mrseivane.Syn.yml" ]]; then
  echo 'Uso: bash actualizar-flatpak-existente.sh /ruta/a/las/fuentes-Flatpak-SYN' >&2
  exit 2
fi
if [[ "$(realpath "$SRC")" == "$(realpath "$TARGET")" ]]; then
  bash "$SRC/construir-flatpak.sh"; exit
fi
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$TARGET/syn-backups/$STAMP"
mkdir -p "$BACKUP"
for file in syn.py syn_sources.py syn_i18n.py syn-flatpak com.mrseivane.Syn.yml com.mrseivane.Syn.desktop com.mrseivane.Syn.metainfo.xml construir-flatpak.sh; do
  [[ ! -f "$TARGET/$file" ]] || cp -p "$TARGET/$file" "$BACKUP/"
done
for file in syn.py syn_sources.py syn_i18n.py com.mrseivane.Syn.yml com.mrseivane.Syn.desktop com.mrseivane.Syn.metainfo.xml; do
  install -m 644 "$SRC/$file" "$TARGET/$file"
done
for file in syn-flatpak construir-flatpak.sh; do
  install -m 755 "$SRC/$file" "$TARGET/$file"
done
mkdir -p "$TARGET/locale/en_US/LC_MESSAGES" "$TARGET/locale/en_GB/LC_MESSAGES"
cp -a "$SRC/locale/en_US/LC_MESSAGES/syn.mo" "$TARGET/locale/en_US/LC_MESSAGES/syn.mo"
cp -a "$SRC/locale/en_GB/LC_MESSAGES/syn.mo" "$TARGET/locale/en_GB/LC_MESSAGES/syn.mo"
mkdir -p "$TARGET/icons"
cp -a "$SRC/icons/." "$TARGET/icons/"
(cd "$TARGET" && python3 -m py_compile syn.py syn_sources.py)
echo "Copia del código anterior: $BACKUP"
cd "$TARGET"
flatpak kill com.mrseivane.Syn 2>/dev/null || true
bash construir-flatpak.sh
printf '\n=== VERSIÓN INSTALADA ===\n'
flatpak run com.mrseivane.Syn --version
