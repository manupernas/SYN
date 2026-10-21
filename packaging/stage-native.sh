#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="${1:?Uso: packaging/stage-native.sh /ruta/raiz-paquete}"
mkdir -p "$DEST/usr/share/syn" "$DEST/usr/bin" "$DEST/usr/share/applications" \
  "$DEST/usr/share/metainfo" "$DEST/usr/share/icons/hicolor" "$DEST/usr/lib/systemd/user"
install -m755 syn.py "$DEST/usr/share/syn/syn.py"
install -m644 syn_sources.py syn_i18n.py syn_dvr.py syn_dvr_tray.py "$DEST/usr/share/syn/"
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
cat > "$DEST/usr/bin/syn-dvr-tray" <<'EOS'
#!/bin/sh
set -eu
export LC_NUMERIC=C
export SYN_NATIVE_PACKAGE=1
export PYTHONPATH="/usr/share/syn${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3 /usr/share/syn/syn_dvr_tray.py "$@"
EOS
chmod 755 "$DEST/usr/bin/syn" "$DEST/usr/bin/syn-dvr-worker" "$DEST/usr/bin/syn-dvr-tray"
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
cat > "$DEST/usr/lib/systemd/user/syn-dvr-tray.service" <<'EOS'
[Unit]
Description=SYN DVR - recording status indicator
After=graphical-session.target
[Service]
Type=exec
ExecStart=/usr/bin/syn-dvr-tray
Restart=on-failure
RestartSec=5
[Install]
WantedBy=default.target
EOS
# Vendor-wide activation for user sessions: both user services start at login.
# A user's existing ~/.config/systemd/user unit takes precedence over these.
# This does NOT restart any running recording during package installation.
mkdir -p "$DEST/usr/lib/systemd/user/default.target.wants"
ln -s ../syn-dvr-worker.service "$DEST/usr/lib/systemd/user/default.target.wants/syn-dvr-worker.service"
ln -s ../syn-dvr-tray.service "$DEST/usr/lib/systemd/user/default.target.wants/syn-dvr-tray.service"
# No IPTV playlists, profiles, passwords or recordings are installed.
find "$DEST" -type f | sort
