#!/usr/bin/env python3
"""Starts the detached macOS SYN Cast bridge without touching launchd or DVR.

The bridge uses the same authenticated loopback protocol already in SYN UI.
It stays alive after the GUI closes; no service is killed at startup.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

PRIVATE = Path.home() / 'Library' / 'Application Support' / 'SYN Alpha'
TOKEN = PRIVATE / 'cast-token'
PORT = 18976


def _ready():
    try:
        token = TOKEN.read_text('utf-8').strip()
        req = urllib.request.Request('http://127.0.0.1:18976',
            data=b'{"action":"status"}', method='POST',
            headers={'Content-Type':'application/json','X-Syn-Token':token})
        with urllib.request.urlopen(req,timeout=.6) as response:
            data=json.load(response)
            return isinstance(data,dict) and 'active' in data and not data.get('error')
    except Exception:
        return False


def ensure_running(source: Path):
    if _ready():
        return True
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
        probe.settimeout(.3)
        if probe.connect_ex(('127.0.0.1',PORT))==0:
            print('SYN Cast macOS: puerto 18976 ocupado por otro servicio; no se inicia otro.',file=sys.stderr)
            return False
    interpreter=PRIVATE / 'cast-venv' / 'bin' / 'python'
    host=source / 'syn_cast_host.py'
    if not interpreter.is_file() or not host.is_file():
        print('SYN Cast macOS: falta preparar PyChromecast o el puente.',file=sys.stderr)
        return False
    env=os.environ.copy()
    env['PATH']='/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
    # Detached and silent: no private IPTV URL should leak into logs.
    subprocess.Popen([str(interpreter),str(host)],stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        env=env,start_new_session=True,close_fds=True,cwd=str(source))
    for _ in range(16):
        if _ready():
            return True
        time.sleep(.15)
    print('SYN Cast macOS: el servicio aún no responde; abre el diagnóstico Alpha 5.',file=sys.stderr)
    return False
