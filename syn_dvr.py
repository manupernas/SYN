#!/usr/bin/env python3
"""DVR for SYN: independent FFmpeg recorder and persistent local scheduler.

All network streams are user supplied; no streams or credentials are bundled.
The DVR worker runs in an independent Flatpak instance where permitted.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid

APP_ID = 'com.mrseivane.Syn'
VLC_UA = 'VLC/3.0.21 LibVLC/3.0.21'
DATA = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'syn'
DB_PATH = DATA / 'dvr.json'
DB_LOCK = DATA / 'dvr-data.lock'
WORKER_LOCK = DATA / 'dvr-worker.lock'


def video_directory():
    """Use the host's XDG video directory, including localized paths (Vídeos)."""
    try:
        from gi.repository import GLib
        p = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS)
        if p:
            return Path(p) / 'SYN'
    except (ImportError, ValueError, AttributeError):
        pass
    for root in (Path.home() / 'Vídeos', Path.home() / 'Videos'):
        if root.is_dir():
            return root / 'SYN'
    return Path.home() / 'Videos' / 'SYN'


def filename_safe(value):
    value = re.sub(r'[\x00-\x1f\\/:*?"<>|]', '_', str(value))
    value = re.sub(r'\s+', ' ', value).strip(' ._')
    return (value or 'Canal')[:90]


def allowed_stream_url(url):
    parsed = urlparse(str(url))
    return parsed.scheme.lower() in ('http', 'https') and bool(parsed.netloc)


@contextmanager
def lock_file(path):
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        with os.fdopen(fd, 'r+') as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        pass


class DVRStore:
    def _read(self):
        try:
            db = json.loads(DB_PATH.read_text(encoding='utf-8'))
            if not isinstance(db, dict) or not isinstance(db.get('jobs', []), list):
                raise ValueError('Invalid DVR database')
            return db
        except (OSError, ValueError, TypeError):
            return {'jobs': [], 'folder': str(video_directory()), 'heartbeat': 0}

    def read(self):
        with lock_file(DB_LOCK):
            return self._read()

    def change(self, callback):
        with lock_file(DB_LOCK):
            db = self._read()
            result = callback(db)
            DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, tmp = tempfile.mkstemp(prefix='.dvr-', suffix='.json', dir=DATA)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(db, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(tmp, 0o600)
                os.replace(tmp, DB_PATH)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            return result

    def add(self, name, url, start, end=None, user_agent=VLC_UA, programme=None):
        if not allowed_stream_url(url):
            raise ValueError('La URL del canal debe ser HTTP o HTTPS.')
        start = float(start)
        if end is not None and float(end) <= start:
            raise ValueError('La hora final debe ser posterior a la inicial.')
        now = time.time()
        if end is not None and float(end) <= now:
            raise ValueError('La grabación ya habría terminado.')
        job = {'id': uuid.uuid4().hex[:14], 'channel': str(name),
               'url': str(url), 'start': start,
               'end': float(end) if end is not None else None,
               'user_agent': str(user_agent or VLC_UA),
               'status': 'scheduled', 'path': '', 'error': '',
               'stop_requested': False, 'created': now,
               'programme': str(programme or '')[:250]}
        self.change(lambda db: db.setdefault('jobs', []).append(job))
        return job

    def stop(self, job_id):
        def edit(db):
            for j in db.get('jobs', []):
                if j['id'] != job_id:
                    continue
                if j['status'] == 'scheduled':
                    j['status'] = 'cancelled'
                elif j['status'] == 'running':
                    j['stop_requested'] = True
                return True
            return False
        return self.change(edit)

    def choose_directory(self, folder):
        path = Path(folder).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise OSError('La carpeta de grabaciones no existe.')
        # Check write access inside Flatpak before persisting a destination.
        fd, temporary = tempfile.mkstemp(prefix='.syn-write-test-', dir=path)
        os.close(fd)
        os.unlink(temporary)
        self.change(lambda db: db.update(folder=str(path)))


def ffmpeg_command(job, path):
    """Copy streams without transcoding. VLC UA is applied before the input URL."""
    if not allowed_stream_url(job['url']):
        raise ValueError('Invalid stream URL')
    cmd = [shutil.which('ffmpeg') or '/app/bin/ffmpeg', '-hide_banner',
           '-loglevel', 'warning', '-nostdin', '-y',
           '-user_agent', str(job.get('user_agent') or VLC_UA),
           '-i', job['url'], '-map', '0:v:0?', '-map', '0:a?',
           '-c', 'copy']
    if job.get('end') is not None:
        duration = max(1, int(float(job['end']) - time.time()))
        cmd += ['-t', str(duration)]
    return cmd + ['-f', 'matroska', str(path)]


def notify_transient(message):
    """Brief desktop banner, deliberately NOT a persistent Gio.Notification.

    The default GNOME notification queue keeps a badge on the SYN icon. A
    transient host notification is only best-effort; the reliable signal is
    the on-screen heartbeat from a separate systemd-managed Flatpak worker.
    """
    if not Path('/.flatpak-info').exists() or not shutil.which('flatpak-spawn'):
        return False
    try:
        subprocess.Popen([
            'flatpak-spawn', '--host', 'notify-send', '--transient',
            '--expire-time=4500', '--urgency=low', '--app-name=SYN',
            'SYN DVR', str(message),
        ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def notify_recording_worker(message):
    """Only the independent scheduler announces start/finish; never fallback."""
    if threading.current_thread() is threading.main_thread():
        notify_transient(message)


def background_worker_confirmed(data=None, max_age=8):
    """Check an actual separate worker heartbeat (not a spawn attempt).

    worker_mode=background is only written by the foreground run_worker()
    invocation in syn-dvr-worker, never the GUI's former fallback thread.
    Avoid PID comparisons: different Flatpak namespaces may reuse numeric PIDs.
    """
    if data is None:
        data = DVRStore().read()
    try:
        heartbeat = float(data.get('heartbeat', 0))
        pid = int(data.get('worker_pid', 0))
    except (ValueError, TypeError, AttributeError):
        return False
    delta = time.time() - heartbeat
    return (data.get('worker_mode') == 'background' and pid > 0
            and 0 <= delta < max_age)


def _set_job(db, job_id, **updates):
    for job in db.get('jobs', []):
        if job.get('id') == job_id:
            job.update(updates)
            return


def run_worker(poll_seconds=2):
    """Only one scheduler is active across GUI and independently spawned Flatpaks."""
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(WORKER_LOCK, 'a+') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Retry from systemd when the old in-app worker still holds the lock.
            return 75
        store = DVRStore()
        active = {}
        # Recover jobs from a crashed DVR worker without claiming false success.
        def recover(db):
            for job in db.get('jobs', []):
                if job.get('status') == 'running':
                    job['status'] = 'interrupted'
                    job['error'] = 'El servicio de grabación se cerró inesperadamente.'
        store.change(recover)
        while True:
            now = time.time()
            data = store.read()
            for job in data.get('jobs', []):
                key = job['id']
                if key in active:
                    proc, output, log_handle, stopping = active[key]
                    done = proc.poll()
                    if done is None and (job.get('stop_requested') or (
                            job.get('end') and now >= float(job['end']))):
                        if not stopping:
                            proc.send_signal(signal.SIGINT)
                            active[key] = (proc, output, log_handle, now)
                        elif now - stopping > 12:
                            proc.kill()
                    if done is not None:
                        try:
                            log_handle.flush()
                            with open(log_handle.name, 'rb') as f:
                                f.seek(max(0, os.fstat(f.fileno()).st_size - 1800))
                                diagnostics = f.read().decode('utf-8', 'replace')
                        except OSError:
                            diagnostics = ''
                        log_handle.close()
                        if done == 0 or (stopping and output.exists() and output.stat().st_size > 0):
                            status, error = 'completed', ''
                        else:
                            status, error = 'failed', ('FFmpeg terminó con error: ' + diagnostics[-500:]).strip()
                        store.change(lambda d, k=key, s=status, e=error:
                                     _set_job(d, k, status=s, error=e, finished=time.time()))
                        notify_recording_worker(('Grabación terminada: ' if status == 'completed' else
                                                 'Error en la grabación: ') + job['channel'])
                        del active[key]
                    continue
                if job.get('status') != 'scheduled' or float(job.get('start', 0)) > now:
                    continue
                if job.get('end') and float(job['end']) <= now:
                    store.change(lambda d, k=key: _set_job(d, k, status='missed', error='El horario programado ya terminó.'))
                    continue
                try:
                    folder = Path(data.get('folder') or video_directory()).expanduser()
                    folder.mkdir(parents=True, exist_ok=True)
                    outname = filename_safe(job['channel']) + ' - ' + datetime.fromtimestamp(now).strftime('%Y-%m-%d %H-%M-%S') + ' - ' + key[:6] + '.mkv'
                    output = folder / outname
                    logname = DATA / ('dvr-' + key + '.log')
                    log_handle = open(logname, 'ab')
                    proc = subprocess.Popen(ffmpeg_command(job, output), stdin=subprocess.DEVNULL,
                                            stdout=subprocess.DEVNULL, stderr=log_handle)
                    active[key] = (proc, output, log_handle, None)
                    store.change(lambda d, k=key, p=str(output):
                                 _set_job(d, k, status='running', path=p, error='', stop_requested=False))
                    notify_recording_worker('● Grabación en curso: ' + job['channel'] +
                                            ' · continuará al cerrar la ventana de SYN.')
                except (OSError, ValueError) as exc:
                    store.change(lambda d, k=key, e=str(exc): _set_job(d, k, status='failed', error=e))
            # A fresh heartbeat alone cannot tell whether the worker will
            # survive the GTK window closing. Persist its owner and mode.
            worker_mode = ('background' if threading.current_thread() is threading.main_thread()
                           else 'embedded')
            store.change(lambda db: db.update(heartbeat=time.time(),
                                             worker_pid=os.getpid(), worker_mode=worker_mode))
            time.sleep(poll_seconds)


def ensure_worker(force_local=False):
    """Never start an embedded fallback that would die with the GUI.

    Background worker lifecycle is managed by systemd --user, installed and
    activated on the host. Retain force_local for backwards API compatibility.
    """
    return 'background' if background_worker_confirmed() else 'unavailable'


def recorded_files():
    data = DVRStore().read()
    folder = Path(data.get('folder') or video_directory())
    try:
        return sorted([f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in ('.mkv', '.ts', '.mp4')],
                      key=lambda f: f.stat().st_mtime, reverse=True)
    except OSError:
        return []


if __name__ == '__main__':
    sys.exit(run_worker())
