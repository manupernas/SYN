"""Experimental LibVLC 3 decoder for the SYN GTK4 macOS player.

The display path intentionally uses Gdk.MemoryTexture, keeping GTK overlays,
EPG, Cast and DVR intact. It is a CPU-copy test bench, NOT native NSView or the
final performance path. GTK main-thread work is delivered via GLib.idle_add.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import struct
import threading
import time
import zlib


VideoLock = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p))
VideoUnlock = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p))
VideoDisplay = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p)
VideoFormat = C.CFUNCTYPE(C.c_uint, C.POINTER(C.c_void_p), C.c_void_p,
                           C.POINTER(C.c_uint), C.POINTER(C.c_uint),
                           C.POINTER(C.c_uint), C.POINTER(C.c_uint))
VideoCleanup = C.CFUNCTYPE(None, C.c_void_p)


def vlc_library():
    """Prefer the bundled official VideoLAN app runtime over a system install."""
    base = Path(__file__).resolve()
    resources = base.parents[1] if base.parent.name == 'source' else base.parent
    candidates = [
        os.environ.get('SYN_LIBVLC_PATH', ''),
        str(resources.parent / 'MacOS/lib/libvlc.dylib'),
        str(resources.parent / 'MacOS/libvlc.dylib'),
        str(resources / 'vlc/lib/libvlc.dylib'),
        '/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib',
        '/Applications/VLC.app/Contents/MacOS/libvlc.dylib',
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError('libVLC no encontrada dentro de SYN.app ni en /Applications/VLC.app')


def png_rgba_from_bgra(dst, width, height, bgra):
    """Snapshot PNG without PIL, subprocesses, or an external video process."""
    src = memoryview(bgra)
    pitch = width * 4
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)
        row = src[y * pitch:(y + 1) * pitch]
        # libVLC RV32 on little endian: B,G,R,X. Produce opaque RGBA.
        for i in range(0, pitch, 4):
            scanlines.extend((row[i + 2], row[i + 1], row[i], 255))
    def chunk(tag, data):
        return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag + data))
    output = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6, 0, 0, 0))
              + chunk(b'IDAT', zlib.compress(scanlines, 3)) + chunk(b'IEND', b''))
    Path(dst).write_bytes(output)


class NativeVlc:
    """Duck-type adapter for the stable SYN NativeMpv contract."""

    engine = 'libVLC experimental (GTK memory output)'

    def __init__(self, GLib, Gdk, picture, player_options=None):
        self.GLib, self.Gdk, self.picture = GLib, Gdk, picture
        self.player_options = player_options or {}
        self.closed = False
        self.ctx = C.c_void_p()
        self._libGL = None
        self.active_url = ''
        self.active_name = ''
        self.on_status = None
        self._is_paused = False
        self._awaiting_load = False
        self._syn_reconnect_buffering = False
        self._syn_reconnect_seeking = False
        self._syn_ts_playback_time = None
        self._render_count = 0
        self._last_frame_at = time.monotonic()
        self._width = self._height = 0
        self._buffer = None
        self._buffer_size = 0
        self._frame_guard = threading.Lock()
        self._latest = None
        self._snapshot = None
        self._idle_pending = False
        self._last_delivered_at = 0.0
        self._error = ''
        self._instance = self._mp = None
        self.libpath = vlc_library()
        root = self.libpath.parent.parent
        plugins = root / 'plugins'
        if plugins.is_dir():
            os.environ['VLC_PLUGIN_PATH'] = str(plugins)
        # macOS/VideoLAN: libvlc.dylib may refer to @rpath/libvlccore.dylib.
        # Load libvlccore FIRST, as the maintained python-vlc Mac loader does.
        # Retain both library handles for the entire player lifetime.
        core_path = self.libpath.parent / 'libvlccore.dylib'
        if not core_path.is_file():
            raise FileNotFoundError('VLC runtime incompleto: falta ' + str(core_path))
        try:
            self._core = C.CDLL(str(core_path), mode=C.RTLD_GLOBAL)
        except OSError as exc:
            raise RuntimeError('No se puede cargar libvlccore: ' + str(exc)) from exc
        try:
            self.lib = C.CDLL(str(self.libpath), mode=C.RTLD_GLOBAL)
        except OSError as exc:
            raise RuntimeError('No se puede cargar libvlc: ' + str(exc)) from exc
        self._bind()
        options = [b'--no-video-title-show', b'--no-osd', b'--quiet',
                   b'--no-media-library', b'--no-snapshot-preview']
        # libVLC may return NULL when its plugins are missing or the runtime
        # cannot load its dependencies. Keep the stable mpv fallback available.
        argv = (C.c_char_p * len(options))(*options)
        self._instance = self.lib.libvlc_new(len(options), argv)
        if not self._instance:
            raise RuntimeError('libvlc_new() devolvió NULL; plugins=' +
                               str(plugins) + ' (exists=' + str(plugins.is_dir()) + ')')
        try:
            self._mp = self.lib.libvlc_media_player_new(self._instance)
            if not self._mp:
                raise RuntimeError('libVLC no pudo crear MediaPlayer')
            self._init_callbacks()
        except Exception:
            if self._mp:
                self.lib.libvlc_media_player_release(self._mp)
            self.lib.libvlc_release(self._instance)
            raise

    def _bind(self):
        l = self.lib
        def sig(name, restype, *args):
            f = getattr(l, name)
            f.restype, f.argtypes = restype, list(args)
        p, cp, ui, i = C.c_void_p, C.c_char_p, C.c_uint, C.c_int
        sig('libvlc_new', p, i, C.POINTER(cp))
        sig('libvlc_release', None, p)
        sig('libvlc_media_player_new', p, p)
        sig('libvlc_media_player_release', None, p)
        sig('libvlc_media_new_location', p, p, cp)
        sig('libvlc_media_release', None, p)
        sig('libvlc_media_player_set_media', None, p, p)
        sig('libvlc_media_add_option', None, p, cp)
        sig('libvlc_media_player_play', i, p)
        sig('libvlc_media_player_stop', None, p)
        sig('libvlc_media_player_set_pause', None, p, i)
        sig('libvlc_audio_set_volume', i, p, i)
        sig('libvlc_media_player_get_time', C.c_longlong, p)
        sig('libvlc_media_player_is_playing', i, p)
        sig('libvlc_video_set_callbacks', None, p, VideoLock, VideoUnlock, VideoDisplay, p)
        sig('libvlc_video_set_format_callbacks', None, p, VideoFormat, VideoCleanup)

    def _init_callbacks(self):
        @VideoFormat
        def setup(_opaque, chroma, width, height, pitches, lines):
            if self.closed:
                return 0
            try:
                w, h = int(width[0]), int(height[0])
                if min(w, h) < 2:
                    return 0
                # Constrain memory copies in this *first* experimental build.
                limit = min(1.0, 1920 / w, 1080 / h)
                w, h = max(2, int(w * limit)), max(2, int(h * limit))
                w += w % 2
                h += h % 2
                size = w * h * 4
                self._buffer = C.create_string_buffer(size)
                self._buffer_size = size
                self._width, self._height = w, h
                C.memmove(chroma, b'RV32', 4)
                width[0], height[0] = w, h
                pitches[0], lines[0] = w * 4, h
                return 1
            except Exception as exc:
                self._error = 'Error al reservar búfer VLC: ' + str(exc)
                return 0

        @VideoCleanup
        def cleanup(_opaque):
            # Do not drop the ctypes allocation from the decoding thread while
            # callbacks might still refer to it. It is reused until shutdown.
            return

        @VideoLock
        def lock(_opaque, planes):
            if self.closed or self._buffer is None:
                planes[0] = None
                return None
            planes[0] = C.cast(self._buffer, C.c_void_p).value
            return None

        @VideoUnlock
        def unlock(_opaque, _picture, _planes):
            return

        @VideoDisplay
        def display(_opaque, _picture):
            if self.closed or not self._buffer or not self.active_url:
                return
            now = time.monotonic()
            # Stop GTK upload churn on high-fps broadcast streams. This limit
            # is only for the diagnostic CPU-copy renderer, not VLC decoding.
            if now - self._last_delivered_at < (1 / 30):
                return
            self._last_delivered_at = now
            try:
                data = C.string_at(self._buffer, self._buffer_size)
                with self._frame_guard:
                    self._latest = (self._width, self._height, data)
                    pending = self._idle_pending
                    self._idle_pending = True
                if not pending:
                    self.GLib.idle_add(self._deliver_frame)
            except Exception as exc:
                self._error = str(exc)

        self._cb_format, self._cb_cleanup = setup, cleanup
        self._cb_lock, self._cb_unlock, self._cb_display = lock, unlock, display
        self.lib.libvlc_video_set_callbacks(self._mp, lock, unlock, display, None)
        self.lib.libvlc_video_set_format_callbacks(self._mp, setup, cleanup)

    def _deliver_frame(self):
        with self._frame_guard:
            frame = self._latest
            self._latest = None
            self._idle_pending = False
        if self.closed or frame is None:
            return False
        w, h, data = frame
        if not self.active_url:
            return False
        # RV32 is B,G,R,X on little-endian macOS. The X byte is padding.
        try:
            fmt = (self.Gdk.MemoryFormat.B8G8R8X8
                   if hasattr(self.Gdk.MemoryFormat, 'B8G8R8X8')
                   else self.Gdk.MemoryFormat.B8G8R8A8)
            blob = self.GLib.Bytes.new(data)
            texture = self.Gdk.MemoryTexture.new(w, h, fmt, blob, w * 4)
            self.picture.set_paintable(texture)
            self.picture.set_visible(True)
            self._snapshot = frame
            self._render_count += 1
            self._last_frame_at = time.monotonic()
            if self._awaiting_load:
                self._awaiting_load = False
                if self.on_status:
                    self.on_status('Reproduciendo · VLC', False)
        except Exception as exc:
            self._error = 'Gdk.MemoryTexture: ' + str(exc)
            if self.on_status:
                self.on_status('VLC: '+self._error, True)
        return False

    def initialize_opengl(self, _queue_draw):
        self._libGL = C.CDLL('/System/Library/Frameworks/OpenGL.framework/OpenGL')
        self._libGL.glClearColor.argtypes = [C.c_float] * 4
        self._libGL.glClear.argtypes = [C.c_uint]
        self.ctx = C.c_void_p(1)  # compatibility: libVLC is not an mpv GL context
        self.picture.set_visible(False)

    def render(self, _width, _height):
        # GLArea remains a black background while Gdk.Picture owns VLC pixels.
        if self._libGL:
            self._libGL.glClearColor(0., 0., 0., 1.)
            self._libGL.glClear(0x00004000)

    def play(self, channel):
        if self.closed:
            return
        url = str(channel.url)
        self.stop()
        self.active_url, self.active_name = url, channel.name
        self._awaiting_load = True
        self._syn_reconnect_buffering = False
        self._is_paused = False
        self.picture.set_paintable(None)
        self.picture.set_visible(False)
        media = self.lib.libvlc_media_new_location(self._instance, url.encode('utf-8'))
        if not media:
            self._awaiting_load = False
            raise RuntimeError('libVLC no pudo abrir la URL del canal')
        try:
            # Respect the existing SYN Xtream/M3U user-agent setting.
            ua = str(self.player_options.get('user_agent', 'Predeterminado'))
            agent = ({'VLC': 'VLC/3.0.23 LibVLC/3.0.23',
                      'Safari': 'Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15',
                      'Firefox': 'Mozilla/5.0 Firefox/128.0',
                      'Personalizado': str(self.player_options.get('custom_ua', ''))}
                     .get(ua, ''))
            if agent and '\r' not in agent and '\n' not in agent:
                self.lib.libvlc_media_add_option(media, (':http-user-agent=' + agent).encode('utf-8'))
            self.lib.libvlc_media_player_set_media(self._mp, media)
        finally:
            self.lib.libvlc_media_release(media)
        status = self.lib.libvlc_media_player_play(self._mp)
        if status != 0:
            self._awaiting_load = False
            raise RuntimeError('libVLC no pudo iniciar la reproducción')

    def stop(self):
        if self._mp and not self.closed:
            self.lib.libvlc_media_player_stop(self._mp)
        self.active_url = ''
        self._awaiting_load = False
        self._syn_ts_playback_time = None
        with self._frame_guard:
            self._latest = None
            self._snapshot = None
        if self.picture:
            self.picture.set_visible(False)
            self.picture.set_paintable(None)

    def toggle_pause(self):
        self._is_paused = not self._is_paused
        if self._mp:
            self.lib.libvlc_media_player_set_pause(self._mp, int(self._is_paused))

    def paused(self):
        return self._is_paused

    def volume(self, value):
        if self._mp and not self.closed:
            self.lib.libvlc_audio_set_volume(self._mp, int(value))

    def playback_position(self):
        if not self.active_url or self._awaiting_load or not self._mp:
            return None
        v = self.lib.libvlc_media_player_get_time(self._mp)
        return v / 1000 if v >= 0 else None

    def video_dimensions(self):
        return (self._width, self._height) if self.active_url and not self._awaiting_load and self._width else None

    def video_display_dimensions(self):
        return self.video_dimensions()

    def screenshot_to_file(self, destination, callback):
        frame = self._snapshot
        if frame is None:
            self.GLib.idle_add(callback, -1, 'Todavía no hay imagen VLC')
            return False
        try:
            w, h, pixels = frame
            png_rgba_from_bgra(destination, w, h, pixels)
            self.GLib.idle_add(callback, 0, '')
            return True
        except (OSError, ValueError) as exc:
            self.GLib.idle_add(callback, -1, str(exc))
            return False

    def write_diag(self):
        from tempfile import gettempdir
        p = Path(gettempdir()) / 'SYN_VLC_BETA_Diagnostico.txt'
        p.write_text('Motor: libVLC (beta GTK memory)\nBiblioteca: '
                     + str(self.libpath) + '\nProblema: ' + self._error + '\n', encoding='utf-8')
        return str(p)

    def free_renderer(self):
        self.ctx = C.c_void_p()

    def shutdown(self):
        if self.closed:
            return
        self.stop()
        self.closed = True
        self.free_renderer()
        # Keep ctypes video callbacks alive until libVLC has finished stopping.
        if self._mp:
            self.lib.libvlc_media_player_release(self._mp)
            self._mp = None
        if self._instance:
            self.lib.libvlc_release(self._instance)
            self._instance = None
