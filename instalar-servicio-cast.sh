#!/usr/bin/env bash
# SYN CAST 6.2 — configure host bridge for native or Flatpak builds.
# Does not modify DVR, IPTV profiles, playlists or existing Cast services.
set -Eeuo pipefail
APP=com.mrseivane.Syn
DEST="$HOME/.local/lib/syn/syn_cast_host.py"
UNIT="$HOME/.config/systemd/user/syn-cast-bridge.service"
TOKEN="$HOME/.config/syn/cast-token"
[[ "$(id -u)" != 0 ]] || { echo 'No ejecutes este script como root ni con sudo.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Necesitas una sesión de systemd --user.' >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo 'Instala ffmpeg con libx264 y AAC en el anfitrión.' >&2; exit 1; }
python3 -c 'import pychromecast' 2>/dev/null || {
  echo 'No está instalado PyChromecast en Python del anfitrión.' >&2
  echo 'Fedora: sudo dnf install python3-chromecast' >&2
  echo 'Otras distribuciones: instala la distribución de PyChromecast apropiada.' >&2
  exit 1
}
for encoder in libx264 aac; do
  ffmpeg -hide_banner -encoders 2>/dev/null | grep -Eq "^[[:space:]]*[VAS][.A-Z0-9]{5}[[:space:]]+$encoder([[:space:]]|$)" || {
    echo "FFmpeg anfitrión no dispone de $encoder; no se instala el servicio." >&2; exit 1;
  }
done
if [[ -f "$UNIT" ]]; then
  if grep -Fq 'SYN CAST BETA6' "$UNIT" || grep -Fq 'SYN CAST 1.3.3' "$UNIT"; then
    echo 'Servicio Cast existente reconocido y preservado. No se reinicia.'
    echo 'Estado:'; systemctl --user is-active syn-cast-bridge.service || true
    exit 0
  fi
  echo 'Hay una unidad Cast no reconocida; no se sobrescribe.' >&2; exit 1
fi
[[ ! -e "$DEST" ]] || { echo "Ya existe un puente Cast en $DEST; no se sobrescribe." >&2; exit 1; }
mkdir -p "$(dirname "$DEST")" "$(dirname "$UNIT")" "$(dirname "$TOKEN")"
TMP="$(mktemp "$(dirname "$DEST")/.syn_cast_host.XXXXXXXX")"
trap 'rm -f -- "$TMP"' EXIT
if [[ -f /usr/share/syn/syn_cast_host.py ]]; then
  cp /usr/share/syn/syn_cast_host.py "$TMP"
elif command -v flatpak >/dev/null && flatpak info --user "$APP" >/dev/null 2>&1; then
  flatpak run --user --command=cat "$APP" /app/share/syn/syn_cast_host.py > "$TMP"
elif command -v flatpak >/dev/null && flatpak info --system "$APP" >/dev/null 2>&1; then
  flatpak run --system --command=cat "$APP" /app/share/syn/syn_cast_host.py > "$TMP"
else
  echo 'No aparece SYN 1.3.3 nativo ni Flatpak.' >&2; exit 1
fi
python3 -m py_compile "$TMP" || { echo 'Puente Cast inválido.' >&2; exit 1; }
if [[ ! -f "$TOKEN" ]]; then
python3 - "$TOKEN" <<'PY'
import secrets,os,sys
p=sys.argv[1]
with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:
    f.write(secrets.token_urlsafe(40)+'\n')
PY
fi
chmod 600 "$TOKEN"
install -m700 "$TMP" "$DEST"
cat > "$UNIT" <<'UNIT'
[Unit]
Description=SYN CAST 1.3.3 — bridge Chromecast on the host (independent of DVR)
After=network-online.target
[Service]
Type=simple
ExecStart=/usr/bin/python3 %h/.local/lib/syn/syn_cast_host.py
Restart=on-failure
RestartSec=3
[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now syn-cast-bridge.service
if ! systemctl --user is-active --quiet syn-cast-bridge.service; then
  echo 'No arrancó el puente Cast; revisa systemctl --user status syn-cast-bridge.service' >&2
  exit 1
fi
echo 'Puente Chromecast activado (Beta6.2 H.264/AAC). DVR intacto.'
echo 'Para transmisión LAN, el Chromecast debe alcanzar TCP 18977 en este equipo.'
