#!/usr/bin/env python3
"""SYN Cast automatically starts with the app (native or Flatpak).

No privileged operations, no user installation steps and no modification of DVR.
Uses systemd --user if available and falls back to an in-sandbox process.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import urllib.request

APP = 'com.mrseivane.Syn'
CAST_PORT = 18976
TOKEN = Path.home() / '.config/syn/cast-token'
_LOCK = threading.Lock()
_STARTED = False


def ensure_token():
    TOKEN.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(str(TOKEN), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        output.write(secrets.token_urlsafe(40) + '\n')


def bridge_is_ready(timeout=0.5):
    try:
        token = TOKEN.read_text('utf-8').strip()
        if len(token) < 32:
            return False
        request = urllib.request.Request(
            f'http://127.0.0.1:{CAST_PORT}',
            data=b'{"action":"status"}',
            headers={'Content-Type': 'application/json', 'X-Syn-Token': token},
            method='POST',
        )
        with urllib.request.urlopen(request, timeout=timeout) as result:
            response = json.loads(result.read(8192))
        return isinstance(response, dict) and not response.get('error')
    except (OSError, ValueError, TimeoutError):
        return False


# On the HOST, only Flatpak and systemd are necessary. There is no dependence
# on host Python, PyChromecast, ffmpeg, pip, or a user's working directory.
_FLATPAK_UNIT_SCRIPT = r'''set -eu
app=com.mrseivane.Syn
unit=syn-cast-bridge.service
folder="$HOME/.config/systemd/user"
command -v systemctl >/dev/null || exit 5
systemctl --user show-environment >/dev/null || exit 5
flatpak_bin=$(command -v flatpak) || exit 5
# Never replace a native service, custom unit, or existing working beta bridge.
if [ -f "$folder/$unit" ] && ! grep -Fq 'SYN-CAST-FLATPAK-MANAGED' "$folder/$unit"; then
    exit 3
fi
mkdir -p "$folder"
cat > "$folder/$unit" <<EOF
[Unit]
Description=SYN-CAST-FLATPAK-MANAGED — Chromecast bridge included in SYN
After=network-online.target
[Service]
Type=exec
ExecStart=$flatpak_bin run --command=syn-cast-bridge $app
Restart=on-failure
RestartSec=3
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
# start, not restart: an existing stream must NEVER be interrupted.
systemctl --user enable "$unit" >/dev/null
systemctl --user start "$unit"
'''


def _spawn_from_package():
    source = Path('/app/share/syn/syn_cast_host.py')
    if not source.exists():
        source = Path('/usr/share/syn/syn_cast_host.py')
    if not source.is_file():
        return False
    env = os.environ.copy()
    if Path('/.flatpak-info').exists():
        env['PYTHONPATH'] = '/app/share/syn/vendor:/app/share/syn' + (
            ':' + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    subprocess.Popen([sys.executable, str(source)],
                     env=env, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)
    return True


# SYN 1.3.4: retire only the exact known temporary Mi Box V2 override.
# Existing custom/non-SYN overrides must remain untouched.
_LEGACY_CAST_MIGRATION = r'''set -eu
unit=syn-cast-bridge.service
drop="$HOME/.config/systemd/user/${unit}.d/50-syn-mibox-recovery.conf"
[ -f "$drop" ] || exit 0
grep -Fq 'syn-cast-mibox-recovery/current/syn_cast_host.py' "$drop" || exit 0
# Never replace another vendor/user unit.
systemctl --user cat "$unit" | grep -Fq 'SYN-CAST-FLATPAK-MANAGED' || exit 0
backup="$HOME/.local/share/syn/legacy-cast-backups"
mkdir -p "$backup"
mv -- "$drop" "$backup/50-syn-mibox-recovery.$(date +%Y%m%d%H%M%S).conf"
systemctl --user daemon-reload
systemctl --user stop "$unit" || true
# The old Flatpak launcher occasionally left an orphan occupying 18976.
# Kill only this identified SYN bridge, never an unrelated process.
if command -v ss >/dev/null 2>&1; then
  for pid in $(ss -H -ltnp '( sport = :18976 )' 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true); do
    cmd=$(ps -p "$pid" -o args= 2>/dev/null || true)
    case "$cmd" in *'/app/share/syn/syn_cast_host.py'*) kill "$pid" 2>/dev/null || true;; esac
  done
fi
systemctl --user reset-failed "$unit" >/dev/null 2>&1 || true
systemctl --user start "$unit"
'''


def _retire_known_local_cast_patch():
    if not Path('/.flatpak-info').exists() or not shutil.which('flatpak-spawn'):
        return
    # Probe live bridge. If a Cast stream is active, let it finish untouched.
    try:
        token = TOKEN.read_text('utf-8').strip()
        req = urllib.request.Request(
            f'http://127.0.0.1:{CAST_PORT}',
            data=b'{"action":"status"}', method='POST',
            headers={'Content-Type':'application/json','X-Syn-Token':token})
        with urllib.request.urlopen(req,timeout=1.5) as response:
            if json.load(response).get('active'):
                return
    except (OSError, ValueError, TimeoutError):
        pass  # The old bridge may already be stopped or crash-looping.
    try:
        result=subprocess.run(
            ['flatpak-spawn','--host','sh','-c',_LEGACY_CAST_MIGRATION],
            capture_output=True, timeout=12, check=False)
        if result.returncode:
            print('SYN Cast: temporary override migration needs attention '
                  f'({result.returncode}).',file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired):
        print('SYN Cast: temporary override migration timed out.',file=sys.stderr)


def start_once():
    """Intended to run in the existing asynchronous service-setup thread."""
    global _STARTED
    if os.environ.get('SYN_DISABLE_SERVICE_AUTOSTART') or os.environ.get('SYN_FIRST_RUN_PREVIEW'):
        return
    with _LOCK:
        if _STARTED:
            return
        _STARTED = True
    try:
        ensure_token()
        _retire_known_local_cast_patch()
        if bridge_is_ready():
            return  # The user may still be streaming with the previous working beta.
        if Path('/.flatpak-info').exists():
            if shutil.which('flatpak-spawn'):
                try:
                    result = subprocess.run(
                        ['flatpak-spawn', '--host', 'sh', '-c', _FLATPAK_UNIT_SCRIPT],
                        capture_output=True, text=True, timeout=15, check=False)
                    if result.returncode == 0:
                        return
                except (OSError, subprocess.TimeoutExpired):
                    pass
            # No systemd in the host session? Still zero-click while SYN runs.
            _spawn_from_package()
        else:
            if (Path('/usr/lib/systemd/user/syn-cast-bridge.service').exists()
                    and shutil.which('systemctl')):
                try:
                    result = subprocess.run(
                        ['systemctl', '--user', 'start', 'syn-cast-bridge.service'],
                        capture_output=True, timeout=10, check=False)
                    if result.returncode == 0:
                        return
                except (OSError, subprocess.TimeoutExpired):
                    pass
            _spawn_from_package()
    except Exception as exc:
        # Avoid leaking stream addresses or tokens into the terminal.
        print('SYN Cast could not start automatically: ' + type(exc).__name__, file=sys.stderr)
