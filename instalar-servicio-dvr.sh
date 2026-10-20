#!/usr/bin/env bash
# Install only a systemd user unit. Never touch an existing running recording.
set -euo pipefail
APP=com.mrseivane.Syn
UNIT=syn-dvr-worker.service
if ! command -v systemctl >/dev/null || ! command -v flatpak >/dev/null; then
  echo 'Se requieren systemd y Flatpak.' >&2; exit 2
fi
if ! flatpak info --user "$APP" >/dev/null 2>&1; then
  echo 'Primero instala SYN como Flatpak de usuario: bash construir-flatpak.sh' >&2; exit 2
fi
FPAK="$(command -v flatpak)"
mkdir -p "$HOME/.config/systemd/user"
FILE="$HOME/.config/systemd/user/$UNIT"
if [[ -e "$FILE" ]] && systemctl --user is-active --quiet "$UNIT"; then
  echo 'El servicio DVR ya está activo. No se reemplaza ni reinicia: podrían estar grabándose programas.'
  exit 0
fi
cat > "$FILE" <<EOF
[Unit]
Description=SYN DVR · programador de grabaciones
Documentation=https://github.com/manupernas/SYN
[Service]
Type=exec
ExecStart=$FPAK run --user --command=syn-dvr-worker $APP
Restart=on-failure
RestartSec=3
TimeoutStopSec=12
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now "$UNIT"
echo 'Estado real del servicio:'
systemctl --user show "$UNIT" -p ActiveState -p SubState -p Result --no-pager
