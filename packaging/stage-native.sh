#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="${1:?Uso: packaging/stage-native.sh /ruta/raiz-paquete}"
mkdir -p "$DEST/usr/share/syn" "$DEST/usr/bin" "$DEST/usr/share/applications" \
  "$DEST/usr/share/metainfo" "$DEST/usr/share/icons/hicolor" "$DEST/usr/lib/systemd/user"
install -m755 syn.py "$DEST/usr/share/syn/syn.py"
install -m644 syn_sources.py syn_i18n.py syn_dvr.py syn_service_setup.py syn_favoritos.py syn_settings_rev3.py syn_locale_rev3.py "$DEST/usr/share/syn/"
install -m644 syn_catalog.py syn_poster.py syn_reconnect.py syn_multistream.py syn_timeshift.py syn_fav_sort.py syn_cast_host.py syn_cast_autostart.py "$DEST/usr/share/syn/"
install -m644 syn_fallback_art.py syn_nord_palette.py syn_epg_pop.py syn_gruvbox_palette.py "$DEST/usr/share/syn/"
install -m644 syn_idle_screen.png "$DEST/usr/share/syn/syn_idle_screen.png"
mkdir -p "$DEST/usr/share/syn/branding"
cp -a branding/. "$DEST/usr/share/syn/branding/"
install -m755 instalar-servicio-cast.sh "$DEST/usr/bin/syn-cast-setup"
for lang in en_US en_GB; do
  install -Dm644 "locale/$lang/LC_MESSAGES/syn.mo" "$DEST/usr/share/locale/$lang/LC_MESSAGES/syn.mo"
done
cp -a icons/. "$DEST/usr/share/icons/hicolor/"
install -Dm644 com.mrseivane.Syn.metainfo.xml "$DEST/usr/share/metainfo/com.mrseivane.Syn.metainfo.xml"
# Nativo: no utilizar el launcher Flatpak ni un sandbox.
sed 's@^Exec=.*@Exec=syn@' com.mrseivane.Syn.desktop > "$DEST/usr/share/applications/com.mrseivane.Syn.desktop"
cat > "$DEST/usr/bin/syn" <<'EOS'
#!/bin/sh
set -eu
export LC_NUMERIC=C
export PYTHONPATH="/usr/share/syn${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3 /usr/share/syn/syn.py "$@"
EOS
cat > "$DEST/usr/bin/syn-dvr-worker" <<'EOS'
#!/bin/sh
set -eu
export LC_NUMERIC=C
export PYTHONPATH="/usr/share/syn${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3 /usr/share/syn/syn_dvr.py "$@"
EOS
chmod 755 "$DEST/usr/bin/syn" "$DEST/usr/bin/syn-dvr-worker"
cat > "$DEST/usr/bin/syn-cast-bridge" <<'EOS'
#!/bin/sh
set -eu
export PYTHONPATH="/usr/share/syn${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3 /usr/share/syn/syn_cast_host.py "$@"
EOS
chmod 755 "$DEST/usr/bin/syn-cast-bridge"
cat > "$DEST/usr/lib/systemd/user/syn-cast-bridge.service" <<'EOS'
[Unit]
Description=SYN Cast — Chromecast service bundled with SYN
After=network-online.target
[Service]
Type=exec
ExecStart=/usr/bin/syn-cast-bridge
Restart=on-failure
RestartSec=3
[Install]
WantedBy=default.target
EOS
cat > "$DEST/usr/lib/systemd/user/syn-dvr-worker.service" <<'EOS'
[Unit]
Description=SYN DVR - grabaciones programadas
Documentation=https://github.com/manupernas/SYN
[Service]
Type=exec
ExecStart=/usr/bin/syn-dvr-worker
Restart=on-failure
RestartSec=5
[Install]
WantedBy=default.target
EOS
# Vendor-wide activation for user sessions: Cast and DVR worker start at login.
# A user's existing ~/.config/systemd/user unit takes precedence over these.
# This does NOT restart any running recording during package installation.
mkdir -p "$DEST/usr/lib/systemd/user/default.target.wants"
ln -s ../syn-cast-bridge.service "$DEST/usr/lib/systemd/user/default.target.wants/syn-cast-bridge.service"
ln -s ../syn-dvr-worker.service "$DEST/usr/lib/systemd/user/default.target.wants/syn-dvr-worker.service"
# No IPTV playlists, profiles, passwords or recordings are installed.
find "$DEST" -type f | sort
