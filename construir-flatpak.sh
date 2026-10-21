#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v flatpak-builder >/dev/null; then echo 'Instala flatpak-builder.' >&2; exit 1; fi
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user --noninteractive flathub org.gnome.Platform//49 org.gnome.Sdk//49
flatpak-builder --user --install --force-clean --install-deps-from=flathub \
  "$HOME/.cache/syn-flatpak-build" com.mrseivane.Syn.yml
echo 'SYN GTK actualizado. Abre: flatpak run com.mrseivane.Syn'

# SYN 1.3: instalar/habilitar servicios de usuario solo en sesión interactiva.
if systemctl --user show-environment >/dev/null 2>&1; then
  bash ./instalar-servicios-syn.sh
else
  echo 'Sin sesión systemd --user: instala servicios en una sesión gráfica con bash instalar-servicios-syn.sh'
fi
