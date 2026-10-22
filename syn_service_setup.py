#!/usr/bin/env python3
"""Idempotent, non-blocking SYN DVR service activation for native Linux and Flatpak.

Run when the GUI first opens, not during install scripts (which run as root or
inside the Flatpak sandbox). Never restart an already running recording worker.
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
UNITS = ('syn-dvr-worker.service', 'syn-dvr-tray.service')
_LOCK = threading.Lock()
_LAST_START = 0.0

# This script executes on the host *as the logged-in user*, through the
# already declared org.freedesktop.Flatpak access. It never uses sudo.
# Avoid replacing a competing native/custom worker or interrupting recordings.
_HOST_SETUP = r'''set -eu
app=com.mrseivane.Syn
flatpak_bin=$(command -v flatpak) || { echo 'flatpak unavailable on host' >&2; exit 2; }
command -v systemctl >/dev/null || { echo 'systemd unavailable on host' >&2; exit 2; }
systemctl --user show-environment >/dev/null || { echo 'no systemd user session' >&2; exit 2; }
# Never hijack the native recorder if both package formats are installed.
if [ -x /usr/bin/syn-dvr-worker ]; then
    echo 'SYN: native recording service installed; Flatpak will not replace it' >&2
    exit 3
fi
directory="$HOME/.config/systemd/user"
worker=syn-dvr-worker.service
tray=syn-dvr-tray.service
if systemctl --user is-active --quiet "$worker"; then
    current=$(systemctl --user show "$worker" --property=ExecStart --value 2>/dev/null || true)
    case "$current" in
        *"$app"*) : ;;
        *) echo 'SYN: another (possibly native) recorder is active; leaving it untouched' >&2; exit 3 ;;
    esac
fi
for unit in "$worker" "$tray"; do
    if [ -f "$directory/$unit" ] && ! grep -Fq "$app" "$directory/$unit"; then
        echo "SYN: existing custom service $unit; not overwriting" >&2
        exit 3
    fi
done
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
cat > "$directory/$tray" <<EOF
[Unit]
Description=SYN Flatpak recording indicator
After=graphical-session.target
[Service]
Type=exec
ExecStart=$flatpak_bin run --command=syn-dvr-tray $app
Restart=on-failure
RestartSec=5
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now "$worker" "$tray"
'''


def _native_user_override_exists():
    config = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    for name in UNITS:
        path = config / 'systemd' / 'user' / name
        if path.is_file() or path.is_symlink():
            # Preserve an explicitly installed user override, whether
            # Flatpak-owned or third-party, instead of managing its lifecycle.
            return True
    return False


def _run_native():
    if not shutil.which('systemctl'):
        return
    if _native_user_override_exists():
        print('SYN DVR: existing custom user services; native version will not replace them.', file=sys.stderr)
        return
    for unit in UNITS:
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'enable', '--now', unit],
                capture_output=True, text=True, timeout=20, check=False)
            if result.returncode:
                print(f'SYN DVR: could not activate {unit}: {result.stderr.strip()[:400]}', file=sys.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f'SYN DVR: systemd activation failed: {exc}', file=sys.stderr)


def _run_flatpak():
    if not shutil.which('flatpak-spawn'):
        print('SYN DVR: flatpak-spawn unavailable; cannot install host user services.', file=sys.stderr)
        return
    try:
        result = subprocess.run(
            ['flatpak-spawn', '--host', 'sh', '-c', _HOST_SETUP],
            capture_output=True, text=True, timeout=25, check=False)
        if result.returncode:
            print(f'SYN DVR: host service setup failed ({result.returncode}): '
                  f'{result.stderr.strip()[:450]}', file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f'SYN DVR: host service setup failed: {exc}', file=sys.stderr)


def _setup():
    # SYN_CAST_PLUG_AND_PLAY: zero-click Chromecast bootstrap; no host pip/ffmpeg.
    try:
        import syn_cast_autostart
        syn_cast_autostart.start_once()
    except Exception as exc:
        print('SYN Cast auto-start unavailable: ' + type(exc).__name__, file=sys.stderr)
    if Path('/.flatpak-info').exists():
        _run_flatpak()
    elif Path('/usr/share/syn/syn_service_setup.py').is_file():
        # Only distro packages have this path. Running source checkouts should
        # not automatically change a user's systemd configuration.
        _run_native()


def ensure_services_async():
    """Start setup in a daemon thread, no more than once every ten seconds."""
    global _LAST_START
    if os.environ.get('SYN_FIRST_RUN_PREVIEW') or os.environ.get('SYN_DISABLE_SERVICE_AUTOSTART'):
        return
    with _LOCK:
        now = time.monotonic()
        if _LAST_START and now - _LAST_START < 10:
            return
        _LAST_START = now
    threading.Thread(target=_setup, daemon=True, name='syn-dvr-autostart').start()
