#!/usr/bin/env bash
# SYN 1.3 · Instala los 2 servicios de usuario sin detener grabaciones.
set -Eeuo pipefail
APP=com.mrseivane.Syn
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
[[ "$(id -u)" != 0 ]] || { echo 'Ejecuta SIN sudo.' >&2; exit 1; }
command -v flatpak >/dev/null || { echo 'Falta flatpak.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Falta systemd.' >&2; exit 1; }
flatpak info --user "$APP" >/dev/null 2>&1 || { echo 'Instala SYN antes de crear los servicios.' >&2; exit 1; }
FP="$(command -v flatpak)"
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/syn-dvr-worker.service" <<UNIT
[Unit]
Description=SYN DVR · programador de grabaciones
After=network-online.target
[Service]
Type=exec
ExecStart=$FP run --user --command=syn-dvr-worker $APP
Restart=on-failure
RestartPreventExitStatus=75
RestartSec=5
TimeoutStopSec=12
[Install]
WantedBy=default.target
UNIT
cat > "$UNIT_DIR/syn-dvr-tray.service" <<UNIT
[Unit]
Description=SYN DVR · indicador de grabación
After=graphical-session.target
[Service]
Type=exec
ExecStart=$FP run --user --command=syn-dvr-tray $APP
Restart=on-failure
RestartSec=5
[Install]
WantedBy=default.target
UNIT
# Sincroniza cambios, habilita las unidades para siguientes inicios,
# pero NO reinicia el motor de grabación mientras haya una grabación.
systemctl --user daemon-reload
systemctl --user enable syn-dvr-worker.service syn-dvr-tray.service >/dev/null
for service in syn-dvr-worker.service syn-dvr-tray.service; do
  if systemctl --user is-active --quiet "$service"; then
    echo "$service: ya activo; no se reinicia."
  else
    systemctl --user reset-failed "$service" || true
    systemctl --user start "$service"
  fi
done
systemctl --user show syn-dvr-worker.service -p ActiveState -p SubState -p UnitFileState
systemctl --user show syn-dvr-tray.service -p ActiveState -p SubState -p UnitFileState
