"""SYN 1.3.2 timeshift beta 2: loopback HLS + seekable VOD snapshots.

Only local 127.0.0.1 traffic is exposed. IPTV credentials are sent to a
child over stdin and are never passed in the supervisor command line.
The existing independent DVR recorder is not imported or modified here.
"""
from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote
import json
import os
import re
import secrets
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

MAX_HISTORY = 120
MAX_DISK_BYTES = 512 * 1024 * 1024
MAX_READY_SECONDS = 45
SEGMENT_SECONDS = 2
_SEGMENT_NAME = re.compile(r'^part-\d+\.ts$')


def stream_allowed(url):
    parts = urlsplit(str(url))
    return parts.scheme.lower() in ('http', 'https') and bool(parts.netloc)


def command(url, user_agent, directory, history=MAX_HISTORY, ffmpeg=None):
    if not stream_allowed(url):
        raise ValueError('Timeshift requiere una señal IPTV HTTP o HTTPS.')
    directory = Path(directory)
    return [ffmpeg or shutil.which('ffmpeg') or '/app/bin/ffmpeg',
            '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
            '-user_agent', str(user_agent or 'VLC/3.0.21 LibVLC/3.0.21'),
            '-i', str(url), '-map', '0:v:0?', '-map', '0:a:0?', '-c', 'copy',
            '-f', 'hls', '-hls_segment_type', 'mpegts',
            '-hls_time', str(SEGMENT_SECONDS),
            '-hls_list_size', str(max(8, int(history / SEGMENT_SECONDS) + 3)),
            '-hls_delete_threshold', '2',
            '-hls_flags', 'delete_segments+omit_endlist+temp_file',
            '-hls_segment_filename', str(directory / 'part-%06d.ts'),
            str(directory / 'live.m3u8')]


def _read_segments(playlist):
    """Return only completed FFmpeg-generated local TS segments and durations."""
    try:
        lines = Path(playlist).read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        return []
    segments = []
    length = None
    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF:'):
            try:
                length = float(line[8:].split(',', 1)[0])
            except ValueError:
                length = None
        elif not line.startswith('#') and length is not None:
            if _SEGMENT_NAME.fullmatch(line) and 0 < length < 120:
                file = Path(playlist).parent / line
                if file.is_file() and file.stat().st_size:
                    segments.append((file, length))
            length = None
    return segments


def playlist_seconds(playlist):
    return min(MAX_HISTORY, sum(duration for _, duration in _read_segments(playlist)))


def make_snapshot(playlist, directory, seconds_back):
    """Write a *closed, seekable* HLS playlist: never seek on moving live HLS.

    Segment hardlinks pin a consistent view while FFmpeg rotates the live ring.
    This uses no transcoding and copies no media bytes on normal Linux FSs.
    """
    history = _read_segments(playlist)
    if not history:
        raise RuntimeError('Todavía no hay segmentos de televisión grabados.')
    requested = min(MAX_HISTORY, max(2, float(seconds_back)))
    selected = []
    accumulated = 0.0
    for file, duration in reversed(history):
        selected.append((file, duration))
        accumulated += duration
        if accumulated >= requested:
            break
    if accumulated + 1 < requested:
        raise RuntimeError('Todavía no hay suficiente vídeo para retroceder.')
    selected.reverse()
    snap_name = 'replay-' + secrets.token_hex(7)
    snapdir = Path(directory) / snap_name
    snapdir.mkdir(mode=0o700)
    body = ['#EXTM3U', '#EXT-X-VERSION:3',
            '#EXT-X-PLAYLIST-TYPE:VOD',
            '#EXT-X-TARGETDURATION:' + str(max(1, int(max(d for _, d in selected) + .999))),
            '#EXT-X-MEDIA-SEQUENCE:0']
    try:
        for i, (file, duration) in enumerate(selected):
            target = snapdir / ('part-%06d.ts' % i)
            try:
                os.link(file, target)
            except OSError:
                shutil.copyfile(file, target)
            body.extend((f'#EXTINF:{duration:.6f},', target.name))
        body.append('#EXT-X-ENDLIST')
        listing = snapdir / 'replay.m3u8'
        listing.write_text('\n'.join(body) + '\n', encoding='utf-8')
        return snap_name + '/replay.m3u8', accumulated
    except Exception:
        shutil.rmtree(snapdir, ignore_errors=True)
        raise


class TimeshiftSession:
    def __init__(self, root=None):
        base = Path(root or os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'syn' / 'timeshift'
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        try: base.chmod(0o700)
        except OSError: pass
        self.directory = Path(tempfile.mkdtemp(prefix='session-', dir=str(base)))
        self.playlist = self.directory / 'live.m3u8'
        self.server_info = self.directory / 'http.json'
        self.process = None
        self.started = 0.0
        self._stopped = False
        self._origin = None
        self._snapshot_duration = 0.0
        self._snapshot_created = 0.0

    def start(self, url, user_agent):
        if self.process:
            raise RuntimeError('Ya hay un timeshift activo.')
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), '--supervise'],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            self.process.stdin.write((json.dumps({'url': url, 'agent': user_agent,
                            'directory': str(self.directory)}) + '\n').encode())
            self.process.stdin.flush()
        except (OSError, ValueError):
            self.stop()
            raise
        self.started = time.monotonic()
        return self.playlist

    def _base_url(self):
        try:
            data = json.loads(self.server_info.read_text(encoding='utf-8'))
            port, token = int(data['port']), str(data['token'])
            if 1 <= port <= 65535 and re.fullmatch(r'[a-f0-9]{36}', token):
                return f'http://127.0.0.1:{port}/{token}/'
        except (OSError, ValueError, TypeError, KeyError):
            pass
        return ''

    def live_url(self):
        base = self._base_url()
        return base + 'live.m3u8' if base else ''

    def snapshot_back(self, seconds_back):
        base = self._base_url()
        if not base:
            raise RuntimeError('El servidor HLS local no está preparado.')
        path, length = make_snapshot(self.playlist, self.directory, seconds_back)
        self._snapshot_duration = length
        self._snapshot_created = time.monotonic()
        return base + path, length

    def ready(self):
        return (self.process is not None and self.process.poll() is None
                and bool(self.live_url()) and len(_read_segments(self.playlist)) >= 2)

    def error(self):
        if self.process is None:
            return 'No se ha iniciado el capturador de vídeo.'
        if self.process.poll() is not None:
            return ('El capturador se ha cerrado (código %s). '
                    'Comprueba el canal y el User-Agent VLC.' % self.process.returncode)
        if time.monotonic() - self.started > MAX_READY_SECONDS and not self.ready():
            return 'La señal no ha generado segmentos HLS después de 45 segundos.'
        if self.disk_bytes() > MAX_DISK_BYTES:
            return 'El timeshift ha superado el límite de 512 MiB.'
        return ''

    def disk_bytes(self):
        try:
            counted = set()
            total = 0
            for path in self.directory.rglob('*'):
                if not path.is_file():
                    continue
                stat = path.stat()
                identity = (stat.st_dev, stat.st_ino)
                if identity not in counted:
                    total += stat.st_size
                    counted.add(identity)
            return total
        except OSError:
            return MAX_DISK_BYTES + 1

    def available_seconds(self):
        return playlist_seconds(self.playlist)

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        proc = self.process
        if proc is not None:
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
                proc.wait(timeout=2.5)
            except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
                if proc.poll() is None:
                    try: os.killpg(proc.pid, signal.SIGTERM)
                    except (ProcessLookupError, OSError): pass
                    try: proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired: pass
        self.process = None
        shutil.rmtree(self.directory, ignore_errors=True)


def _serve(path, port_info):
    root = Path(path)
    token = secrets.token_hex(18)
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def translate_path(self, url_path):
            parts = unquote(urlsplit(url_path).path).split('/')
            if len(parts) < 3 or parts[1] != token:
                return str(root / 'not-allowed')
            rest = parts[2:]
            if not rest or len(rest) > 2 or any(x in ('', '.', '..') for x in rest):
                return str(root / 'not-allowed')
            if len(rest) == 1 and rest[0] != 'live.m3u8':
                return str(root / 'not-allowed')
            if len(rest) == 2:
                if not re.fullmatch(r'replay-[0-9a-f]{14}', rest[0]):
                    return str(root / 'not-allowed')
                if rest[1] != 'replay.m3u8' and not re.fullmatch(r'part-\d{6}\.ts', rest[1]):
                    return str(root / 'not-allowed')
            # Also allow live segment names at root.
            return str(root.joinpath(*rest))

        def do_GET(self):
            # FFmpeg live.m3u8 refers to part-XXXXXX.ts at the root.
            parts = unquote(urlsplit(self.path).path).split('/')
            if len(parts) == 3 and parts[1] == token and _SEGMENT_NAME.fullmatch(parts[2]):
                self.path = '/' + token + '/' + parts[2]
                return self._serve_live_segment(root / parts[2])
            return super().do_GET()

        def _serve_live_segment(self, file):
            try:
                with file.open('rb') as stream:
                    self.send_response(200)
                    self.send_header('Content-Type', 'video/mp2t')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Content-Length', str(file.stat().st_size))
                    self.end_headers()
                    shutil.copyfileobj(stream, self.wfile)
            except OSError:
                self.send_error(404)

        def end_headers(self):
            if self.path.endswith('.m3u8'):
                self.send_header('Cache-Control', 'no-store')
            super().end_headers()

        def log_message(self, *args):
            return  # No local URLs in logs.

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    port_info.write_text(json.dumps({'port': server.server_port, 'token': token}), encoding='utf-8')
    thread = threading.Thread(target=server.serve_forever, name='syn-ts-local-hls', daemon=True)
    thread.start()
    return server


def _supervise():
    try:
        config = json.loads(sys.stdin.buffer.readline().decode('utf-8'))
        root = Path(config['directory']).resolve(strict=True)
        args = command(config['url'], config.get('agent'), root)
    except (ValueError, KeyError, TypeError, UnicodeError, OSError):
        return 2
    server = _serve(root, root / 'http.json')
    try:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError:
        server.shutdown(); server.server_close()
        return 3
    try:
        while True:
            code = proc.poll()
            if code is not None:
                return code if code else 0
            ready, _, _ = select.select([sys.stdin.buffer], [], [], 0.25)
            if ready and not os.read(sys.stdin.fileno(), 1):
                return 0
    finally:
        if proc.poll() is None:
            try: os.killpg(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, OSError): pass
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, OSError): pass
                proc.wait()
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    sys.exit(_supervise() if '--supervise' in sys.argv else 2)
