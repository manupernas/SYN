"""Runtime initialization and non-destructive DVR setup for standalone SYN 1.0.

Shipped inside Contents/Resources. Never reads or exports IPTV credentials.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import plistlib
import subprocess

RESOURCES = Path(__file__).resolve().parent
CONTENTS = RESOURCES.parent
APP = CONTENTS.parent
LABEL = 'com.mrseivane.syn.dvr'
LEGACY_LABEL = 'com.mrseivane.syn.alpha.dvr'


def prepare_runtime():
    """Provide relocatable GDK-Pixbuf loader cache before importing Gtk."""
    if os.environ.get('SYN_STANDALONE') != '1':
        return
    template = RESOURCES / 'gdk-pixbuf.loaders.template'
    if not template.is_file():
        return
    data = template.read_text('utf-8').replace('__SYN_APP_PATH__', str(APP))
    cache = Path.home() / 'Library/Caches/SYN'
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    digest = hashlib.sha256(str(APP).encode('utf-8')).hexdigest()[:12]
    filename = cache / ('pixbuf-' + digest + '.cache')
    if not filename.is_file() or filename.read_text('utf-8') != data:
        tmp = cache / (filename.name + f'.{os.getpid()}.tmp')
        tmp.write_text(data, encoding='utf-8')
        tmp.chmod(0o600)
        tmp.replace(filename)
    os.environ['GDK_PIXBUF_MODULE_FILE'] = str(filename)
    os.environ['GDK_PIXBUF_MODULEDIR'] = str(
        RESOURCES / 'lib/gdk-pixbuf-2.0/2.10.0/loaders')


def ensure_dvr_agent():
    """Install the bundled worker on clean Macs, never competing with legacy DVR.

    The old Alpha service is deliberately preserved if present. This function
    never bootouts/kills a running worker: DVR jobs must not be interrupted.
    """
    if os.environ.get('SYN_STANDALONE') != '1':
        return False
    binary = CONTENTS / 'MacOS/SYN'
    worker = RESOURCES / 'mac_dvr_worker.py'
    ffmpeg = RESOURCES / 'bin/ffmpeg'
    if not all(x.is_file() for x in (binary, worker, ffmpeg)):
        return False
    uid = os.getuid()
    scope = f'gui/{uid}'
    # If the Alpha worker exists, do not start another worker on the same DB.
    for old in (LEGACY_LABEL,):
        if subprocess.run(['/bin/launchctl', 'print', f'{scope}/{old}'],
                          capture_output=True, timeout=5).returncode == 0:
            return False
    agents = Path.home() / 'Library/LaunchAgents'
    agents.mkdir(parents=True, exist_ok=True, mode=0o700)
    plist = agents / (LABEL + '.plist')
    desired = {
        'Label': LABEL,
        'ProgramArguments': [str(binary), '--syn-dvr-worker'],
        'RunAtLoad': True,
        'KeepAlive': {'SuccessfulExit': False},
        'ProcessType': 'Background',
        'LimitLoadToSessionType': 'Aqua',
        'ThrottleInterval': 10,
    }
    # Do not overwrite or restart an agent already installed with another path:
    # it might be handling a recording at this moment.
    if plist.exists():
        return False
    tmp = agents / (LABEL + f'.{os.getpid()}.tmp')
    try:
        tmp.write_bytes(plistlib.dumps(desired))
        tmp.chmod(0o600)
        try:
            with tmp.open('rb') as source, plist.open('xb') as target:
                target.write(source.read())
            plist.chmod(0o600)
        except FileExistsError:
            return False
        result = subprocess.run(['/bin/launchctl', 'bootstrap', scope, str(plist)],
                                capture_output=True, timeout=10)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as error:
        print('SYN DVR: no se pudo registrar servicio:', error)
        return False
    finally:
        tmp.unlink(missing_ok=True)
