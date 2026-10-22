#!/usr/bin/env bash
# Compatibility helper for source developers. End-users need no manual setup.
# Never stop or restart an active DVR recording.
set -Eeuo pipefail
[[ "$(id -u)" != 0 ]] || { echo 'Run as regular user, not sudo.' >&2; exit 2; }
APP=com.mrseivane.Syn
FP="$(command -v flatpak)" || { echo 'Flatpak is required'; exit 2; }
if flatpak info --user "$APP" master >/dev/null 2>&1; then
  SCOPE='--user'
elif flatpak info --system "$APP" master >/dev/null 2>&1; then
  SCOPE='--system'
else
  echo 'SYN is not installed as Flatpak.' >&2; exit 2
fi
DEST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$DEST"
FILE="$DEST/syn-dvr-worker.service"
if systemctl --user is-active --quiet syn-dvr-worker.service; then
  echo 'DVR worker is already active; leaving it untouched.'
  exit 0
fi
if [[ -f "$FILE" ]] && ! grep -Fq 'com.mrseivane.Syn' "$FILE"; then
  echo 'Existing custom DVR worker; not overwriting.' >&2; exit 2
fi
cat > "$FILE" <<EOF
[Unit]
Description=SYN Flatpak DVR worker
After=network-online.target
[Service]
Type=exec
ExecStart=$FP run $SCOPE --branch=master --command=syn-dvr-worker $APP
Restart=on-failure
RestartPreventExitStatus=75
RestartSec=5
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now syn-dvr-worker.service
