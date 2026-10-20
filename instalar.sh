#!/usr/bin/env bash
# Instalador nativo multiplataforma de SYN 3.8.13
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ID='com.mrseivane.Syn'
DEST="$HOME/.local/share/syn"
DESKTOP="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor"

echo 'SYN 3.8.13 · Instalación nativa para Linux'
if [[ ! -f "$ROOT/syn.py" || ! -f "$ROOT/syn_sources.py" ]]; then
  echo 'Error: descomprime todos los archivos del ZIP antes de instalar.' >&2
  exit 1
fi
if [[ -e /etc/arch-release ]]; then
  packages=(python-gobject gtk4 libadwaita mpv)
  if command -v pacman >/dev/null; then sudo pacman -S --needed --noconfirm "${packages[@]}"; fi
elif command -v dnf >/dev/null; then
  sudo dnf install -y python3-gobject gtk4 libadwaita mpv-libs
elif command -v apt-get >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 libmpv2
else
  echo 'Instalación sin paquete automático: necesitas Python GI, GTK4, libadwaita y libmpv.'
  echo 'Si prefieres, utiliza el paquete Flatpak incluido.'
fi
install -d -m 755 "$DEST" "$DESKTOP" "$HOME/.local/bin"
if [[ -f "$DEST/syn.py" ]]; then
  cp -p "$DEST/syn.py" "$DEST/syn-previo.py"
fi
install -m 755 "$ROOT/syn.py" "$DEST/syn.py"
install -m 644 "$ROOT/syn_sources.py" "$DEST/syn_sources.py"
install -m 644 "$ROOT/syn_i18n.py" "$DEST/syn_i18n.py"
for locale in en_US en_GB; do
  install -Dm644 "$ROOT/locale/$locale/LC_MESSAGES/syn.mo"     "$DEST/locale/$locale/LC_MESSAGES/syn.mo"
done
install -m 755 "$ROOT/lanzar-syn" "$HOME/.local/bin/syn"
for size in 16 24 32 48 64 96 128 256 512; do
  icon_dir="$ICONS/${size}x${size}/apps"
  install -d -m 755 "$icon_dir"
  install -m 644 "$ROOT/icons/${size}x${size}/apps/${APP_ID}.png" "$icon_dir/${APP_ID}.png"
done
rm -f "$ICONS/scalable/apps/${APP_ID}.svg"
install -m 644 "$ROOT/${APP_ID}.desktop" "$DESKTOP/${APP_ID}.desktop"
# Sustituir wrapper para instalaciones nativas manteniendo un Exec absoluto:
sed -i "s#^Exec=.*#Exec=$HOME/.local/bin/syn#" "$DESKTOP/${APP_ID}.desktop"
python3 -m py_compile "$DEST/syn.py" "$DEST/syn_sources.py" "$DEST/syn_i18n.py"
if command -v update-desktop-database >/dev/null; then
  update-desktop-database "$DESKTOP" 2>/dev/null || true
fi
echo '✓ SYN 3.8.13 instalado. Tus perfiles y la configuración anterior permanecen intactos.'
echo '✓ Abre SYN desde el menú de aplicaciones.'
