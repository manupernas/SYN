#!/usr/bin/env python3
"""SYN 1.3.5c: DVR worker + Cast auto-start; NO system tray service.

The recorder is managed independently and is never restarted by GUI startup.
The obsolete syn-dvr-tray is deliberately neither created nor enabled.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

APP = 'com.mrseivane.Syn'
UNITS = ('syn-dvr-worker.service',)
_LOCK = threading.Lock()
_LAST_START = 0.0

_HOST_SETUP = r'''set -eu
app=com.mrseivane.Syn
flatpak_bin=$(command -v flatpak) || { echo 'flatpak unavailable on host' >&2; exit 2; }
command -v systemctl >/dev/null || { echo 'systemd unavailable on host' >&2; exit 2; }
systemctl --user show-environment >/dev/null || { echo 'no systemd user session' >&2; exit 2; }
if [ -x /usr/bin/syn-dvr-worker ]; then
    echo 'SYN: native recording service installed; Flatpak will not replace it' >&2
    exit 3
fi
directory="$HOME/.config/systemd/user"
worker=syn-dvr-worker.service
if systemctl --user is-active --quiet "$worker"; then
    current=$(systemctl --user show "$worker" --property=ExecStart --value 2>/dev/null || true)
    case "$current" in
        *"$app"*) : ;;
        *) echo 'SYN: other recorder already active; leaving it untouched' >&2; exit 3 ;;
    esac
fi
if [ -f "$directory/$worker" ] && ! grep -Fq "$app" "$directory/$worker"; then
    echo 'SYN: existing custom worker service; not overwriting' >&2
    exit 3
fi
mkdir -p "$directory"
cat > "$directory/$worker" <<EOF
[Unit]
Description=SYN Flatpak background recorder
After=network-online.target
[Service]
Type=exec
ExecStart=$flatpak_bin run --command=syn-dvr-worker $app
Restart=on-failure
RestartPreventExitStatus=75
RestartSec=5
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now "$worker"
# Upgrade migration: retire ONLY SYN's obsolete tray service, not the DVR worker.
legacy="$directory/syn-dvr-tray.service"
if [ -f "$legacy" ] && grep -Eq 'syn-dvr-tray|com\.mrseivane\.Syn' "$legacy"; then
    systemctl --user disable --now syn-dvr-tray.service >/dev/null 2>&1 || true
    rm -f -- "$legacy"
    systemctl --user daemon-reload
fi
'''


def _native_user_override_exists():
    config = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return any((config / 'systemd' / 'user' / name).exists() for name in UNITS)


def _run_native():
    if not shutil.which('systemctl'):
        return
    try:
        check = subprocess.run(['systemctl','--user','show','syn-dvr-tray.service',
                                '--property=ExecStart','--value'], capture_output=True,
                               text=True, timeout=3, check=False)
        if check.returncode == 0 and ('syn-dvr-tray' in check.stdout or 'syn_dvr_tray.py' in check.stdout):
            subprocess.run(['systemctl','--user','disable','--now','syn-dvr-tray.service'],
                           capture_output=True, timeout=6, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass
    if _native_user_override_exists():
        return
    for unit in UNITS:
        try:
            result = subprocess.run(['systemctl', '--user', 'enable', '--now', unit],
                                    capture_output=True, text=True, timeout=20, check=False)
            if result.returncode:
                print('SYN DVR: could not activate worker: ' + result.stderr.strip()[:240], file=sys.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print('SYN DVR: service activation failed: ' + str(exc), file=sys.stderr)


def _run_flatpak():
    if not shutil.which('flatpak-spawn'):
        print('SYN DVR: flatpak-spawn unavailable', file=sys.stderr)
        return
    try:
        result = subprocess.run(['flatpak-spawn', '--host', 'sh', '-c', _HOST_SETUP],
                                capture_output=True, text=True, timeout=25, check=False)
        if result.returncode:
            print('SYN DVR: host worker setup failed: ' + result.stderr.strip()[:260], file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print('SYN DVR: host worker setup failed: ' + str(exc), file=sys.stderr)


def _setup():
    try:
        import syn_cast_autostart
        syn_cast_autostart.start_once()
    except Exception as exc:
        print('SYN Cast auto-start unavailable: ' + type(exc).__name__, file=sys.stderr)
    if Path('/.flatpak-info').exists():
        _run_flatpak()
    elif Path('/usr/share/syn/syn_service_setup.py').is_file():
        _run_native()


def ensure_services_async():
    """Idempotent, nonblocking; never touches the recorder on a foreground redraw."""
    global _LAST_START
    if os.environ.get('SYN_FIRST_RUN_PREVIEW') or os.environ.get('SYN_DISABLE_SERVICE_AUTOSTART'):
        return
    with _LOCK:
        now = time.monotonic()
        if _LAST_START and now - _LAST_START < 10:
            return
        _LAST_START = now
    threading.Thread(target=_setup, daemon=True, name='syn-dvr-autostart').start()
