#!/usr/bin/env bash
# SYN: repair a host GNOME icon-theme collision without changing the Flatpak.
set -Eeuo pipefail
APP='com.mrseivane.Syn'
USER_BASE="$HOME/.local/share/flatpak/exports/share"
SYSTEM_BASE='/var/lib/flatpak/exports/share'
NATIVE_BASE='/usr/share'

if command -v flatpak >/dev/null && flatpak info --user "$APP" >/dev/null 2>&1; then
  BASE="$USER_BASE"
elif command -v flatpak >/dev/null && flatpak info --system "$APP" >/dev/null 2>&1; then
  BASE="$SYSTEM_BASE"
elif command -v rpm >/dev/null && rpm -q syn-iptv >/dev/null 2>&1; then
  BASE="$NATIVE_BASE"
else
  echo 'SYN no está instalado o no se ha encontrado su ámbito (Flatpak/RPM).' >&2
  exit 1
fi

SRC="$BASE/applications/$APP.desktop"
ICON="$BASE/icons/hicolor/256x256/apps/$APP.png"
DEST="$HOME/.local/share/applications/$APP.desktop"
[[ -s "$SRC" && -s "$ICON" ]] || { echo "Falta el lanzador o el PNG: $SRC / $ICON" >&2; exit 2; }
mkdir -p -- "$(dirname "$DEST")"
if [[ -e "$DEST" ]]; then
  BACKUP="$DEST.respaldo-$(date +%Y%m%d-%H%M%S)"
  cp -p -- "$DEST" "$BACKUP"
  echo "Lanzador anterior guardado: $BACKUP"
fi
TEMP="$(mktemp "${DEST}.tmp.XXXXXX")"
trap 'rm -f -- "$TEMP"' EXIT
sed -E "s@^Icon=.*@Icon=$ICON@" "$SRC" > "$TEMP"
if ! grep -Fxq "Icon=$ICON" "$TEMP"; then
  echo 'El lanzador no tiene una línea Icon= válida; no se modifica.' >&2
  exit 3
fi
chmod 644 "$TEMP"
mv -f -- "$TEMP" "$DEST"
trap - EXIT
printf 'OK: %s\n' "$DEST"
printf 'Icono aplicado: %s\n' "$ICON"
echo 'Si el dock no cambia de inmediato, cierra sesión en GNOME y vuelve a entrar.'
echo 'No se han modificado perfiles, favoritos, grabaciones ni archivos del Flatpak.'
