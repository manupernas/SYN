#!/usr/bin/env python3
"""SYN 1.0: traducciones, temas y controles estabilizados.

La ruta estable GTK GLArea/libmpv de IPTV Integrado v1.7 se conserva.
La configuración del reproductor solo cambia cuando el usuario lo solicita.
"""
from __future__ import annotations

import argparse
import configparser
import colorsys
import datetime as dt
import ctypes as C
import ctypes.util
import faulthandler
import json
import locale
import tempfile
import os
import queue
import re
import sys
import threading
import time
import unicodedata
from collections import deque
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
if __import__('sys').platform == 'darwin':
    from syn_mac_worker import DaemonWorkerPool
import syn_sources as sources
import syn_catalog
import syn_poster
import syn_dvr

# SYN_MAC_576C_NATIVE_NOTIFICATION
# Avisos transitorios de la interfaz; el servicio DVR permanece sin cambios.
if sys.platform == 'darwin':
    _syn_previous_transient_576c = getattr(syn_dvr, 'notify_transient', None)
    if callable(_syn_previous_transient_576c):
        def _syn_native_transient_576c(message):
            from pathlib import Path
            import subprocess
            native = (Path.home() / 'Library' / 'Application Support' /
                      'SYN-Mac' / 'Notifications' / 'SYN Notifications.app')
            if native.is_dir():
                try:
                    result = subprocess.run(
                        ['/usr/bin/open', '-g', '-n', '-a', str(native),
                         '--args', 'SYN', str(message)],
                        capture_output=True, text=True, timeout=4)
                    if result.returncode == 0:
                        return None
                except (OSError, subprocess.TimeoutExpired):
                    pass
            return _syn_previous_transient_576c(message)
        syn_dvr.notify_transient = _syn_native_transient_576c
import syn_reconnect
import syn_multistream
import syn_timeshift
import syn_favoritos
import syn_fav_sort
import synplus_layout
import syn_service_setup
from syn_i18n import translate as tr, format_time, format_day_time, LANGUAGE, locale_description
from pathlib import Path
from syn_macos_gl import gl_proc_address as _syn_macos_gl_proc
from urllib.parse import urlsplit

# Clean video-only PNG filenames; never place channel URLs in paths.
def syn_capture_filename(value):
    return (re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', str(value or 'Canal'))
            .strip(' ._') or 'Canal')[:75]

APP_ID = "com.mrseivane.Syn"
APP_TITLE = "SYN"
SYN_VERSION = "1.0.0"
SYN_PORTAL_BUILD = "1.3.6"
CONFIG_DIR = sources.APP_CONFIG
CONFIG_PATH = sources.CONFIG_FILE
LOG_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "syn"
LOG_PATH = LOG_DIR / "ultimo-error.txt"
HANG_PATH = LOG_DIR / "ultimo-bloqueo.txt"
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


@dataclass(frozen=True)
class Channel:
    name: str
    group: str
    url: str
    logo: str = ""

    @property
    def favorite_id(self):
        return f"{self.group}|{self.name}"


def display_channel_name(raw):
    """Nombre corto SOLO para la interfaz; no cambia el ID del canal ni el EPG.

    Conserva HD/FHD/UHD/4K y no elimina nombres que empiezan por 'ES'
    (por ejemplo ESPORTS). Quita prefijos de país típicos de listas IPTV.
    """
    title = str(raw or '').strip()
    # Puede llegar como '[ES]', '|ES|', '(ES)' o 'ES -' antes del nombre.
    prefix = re.compile(r'^\s*(?:\[\s*ES\s*\]|\(\s*ES\s*\)|\|\s*ES\s*\||ES\s*[-|:])\s*', re.I)
    for _ in range(3):
        updated = prefix.sub('', title, count=1)
        if updated == title:
            break
        title = updated.lstrip(' |:-')
    return title or str(raw or '').strip() or 'Sin nombre'


def logo_canvas_offset(canvas_width, canvas_height, image_width, image_height):
    """Center within a fixed canvas without changing intrinsic layout dimensions."""
    return (max(0.0, (canvas_width - image_width) / 2.0),
            max(0.0, (canvas_height - image_height) / 2.0))


def logo_contrast_variant(pixels):
    """Fondo claro cuando predomina un logo oscuro, y viceversa.

    Evita que un logotipo azul oscuro quede perdido sobre azul de igual
    luminosidad; ignora el espacio transparente externo.
    """
    total = weighted = 0.0
    for r, g, b, a in pixels:
        if a < 72:
            continue
        weight = a / 255.0
        # Luminancia perceptual aproximada, adecuada para elegir paleta.
        luminance = (0.2126*r + 0.7152*g + 0.0722*b) / 255.0
        weighted += luminance * weight
        total += weight
    if not total:
        return 'dark'
    return 'dark' if weighted / total >= .52 else 'light'


def normalize_accent_hex(raw):
    """Un color seguro para CSS; vacío = seguir el acento del escritorio."""
    color = str(raw or '').strip()
    if not color:
        return ''
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError(tr('El realce debe estar vacío o tener formato #RRGGBB (ej.: #279B91).'))
    return color.upper()


def accent_css(hex_color):
    """Anula el realce exclusivamente para SYN, sin alterar temas ajenos."""
    color = normalize_accent_hex(hex_color)
    if not color:
        return ''
    r,g,b = (int(color[i:i+2], 16) / 255 for i in (1,3,5))
    def linear(c): return c / 12.92 if c <= .04045 else ((c + .055)/1.055) ** 2.4
    luminosity = .2126*linear(r) + .7152*linear(g) + .0722*linear(b)
    fg = '#101818' if luminosity > .34 else '#FFFFFF'
    return f"""
    :root {{ --accent-bg-color: {color}; --accent-fg-color: {fg}; --accent-color: {color}; }}
    window.iptv-tv button.iptv-accent,
    window.iptv-tv button.iptv-accent:hover,
    window.iptv-tv togglebutton:checked,
    window.iptv-tv button:checked,
    window.syn-settings-window button.iptv-accent {{
        background-color: {color}; border-color: {color}; color: {fg};
    }}
    window.iptv-tv button.iptv-accent label,
    window.iptv-tv togglebutton:checked label {{ color: {fg}; }}
    window.iptv-tv scale highlight,
    window.iptv-tv progressbar progress,
    window.iptv-tv levelbar block.filled {{ background-color: {color}; }}
    window.iptv-tv selection, window.syn-settings-window selection,
    window.iptv-tv entry selection, window.syn-settings-window entry selection {{
        background-color: {color}; color: {fg};
    }}
    window.iptv-tv .iptv-icon {{ color: {color}; }}
    """


def logo_color_bucket(pixels):
    """Devuelve la familia de color *del propio logo*, nunca la complementaria.

    Ignora transparencia, blancos, negros y tonos grises. Así La 1 azul
    usa una pastilla azul y 24 Horas naranja, sin caer en marrones apagados.
    """
    weights = [0.0] * 12
    for r, g, b, a in pixels:
        if a < 80:
            continue
        h, l, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if saturation < .20 or l < .09 or l > .95:
            continue
        idx = round(h * 12) % 12
        weights[idx] += saturation ** 1.5 * min(1., a / 255.)
    return max(range(12), key=lambda i: weights[i]) if max(weights) > 0 else 6


def logo_pill_css(dark=False, pastel=False, teal=False):
    """Tonos de marca vivos, adaptados al tema sin cambiar la geometría."""
    lightness = .83 if pastel else (.35 if dark and not teal else .43)
    saturation = .54 if pastel else (.64 if dark and not teal else .72)
    result = []
    for i in range(12):
        r, g, b = colorsys.hls_to_rgb(i / 12, lightness, saturation)
        rgb = '#' + ''.join(f'{round(v * 255):02x}' for v in (r, g, b))
        stroke = 'rgba(14,57,59,.19)' if pastel else 'rgba(255,255,255,.18)'
        result.append(f'.syn-logo-pill-h{i} {{ background-color: {rgb}; border-color: {stroke}; }}')
        # Contraste de luminosidad sin cambiar de familia cromática.
        for variant, luminance, chroma in (
            ('light', .85 if pastel else .78, .62),
            ('dark', .29 if pastel else .21, .70),
        ):
            rr, gg, bb = colorsys.hls_to_rgb(i / 12, luminance, chroma)
            tone = '#' + ''.join(f'{round(v*255):02x}' for v in (rr,gg,bb))
            result.append(f'.syn-logo-pill-h{i}-{variant} {{ background-color: {tone}; border-color: {stroke}; }}')
    return '\n'.join(result)


def logo_visible_bounds(pixels, width, height, stride, channels, alpha_threshold=28):
    """Recorta solo la transparencia real; evita recortar logos opacos/JPG.

    Retorna (x, y, ancho, alto) con un pequeño margen protector. Es una
    función pura para poder probar los PNG sin arrancar GTK/Wayland.
    """
    if width <= 0 or height <= 0 or channels != 4:
        return (0, 0, max(0, width), max(0, height))
    x0, y0, x1, y1 = width, height, -1, -1
    for y in range(height):
        offset = y * stride
        for x in range(width):
            if pixels[offset + x * channels + 3] >= alpha_threshold:
                x0 = min(x0, x)
                y0 = min(y0, y)
                x1 = max(x1, x)
                y1 = max(y1, y)
    if x1 < x0:
        return (0, 0, width, height)
    margin = max(1, round(max(x1 - x0 + 1, y1 - y0 + 1) * .035))
    x0 = max(0, x0 - margin)
    y0 = max(0, y0 - margin)
    x1 = min(width - 1, x1 + margin)
    y1 = min(height - 1, y1 + margin)
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)



def fitted_logo_size(width, height, max_width=108, max_height=38):
    """Escala el *contenido visible* de un logo hasta la caja disponible.

    No prohíbe ampliar originales pequeños: antes la cota 1.0 en el
    factor de escala hacía que un logo de 24x12 quedase microscópico.
    Mantiene la relación de aspecto y nunca excede el interior de la
    pastilla fija de 120x46 (padding incluido).
    """
    if width <= 0 or height <= 0 or max_width <= 0 or max_height <= 0:
        return (0, 0)
    factor = min(max_width / width, max_height / height)
    return (min(max_width, max(1, round(width * factor))),
            min(max_height, max(1, round(height * factor))))


def find_host_gtk4_css(home, gtk_name='', dark=False):
    """Localiza CSS GTK4/libadwaita real, no interpreta temas GTK3 como GTK4."""
    home = Path(home)
    roots = [home / '.config' / 'gtk-4.0']
    name = str(gtk_name or '').strip().split(':')[0]
    # El instalador -l de Colloid deja gtk.css/gtk-dark.css en ~/.config/gtk-4.0.
    # Si no existe, permitimos una instalación GTK4 de tema a nivel usuario.
    if name and name not in ('.','..') and re.fullmatch(r'[a-zA-Z0-9_.+-]{1,120}', name):
        roots += [home / '.themes' / name / 'gtk-4.0',
                  home / '.local' / 'share' / 'themes' / name / 'gtk-4.0']
    for root in roots:
        paths = ([root / 'gtk-dark.css', root / 'gtk.css'] if dark
                 else [root / 'gtk.css'])
        for file in paths:
            try:
                if file.is_file() and file.stat().st_size < 2_000_000:
                    return file
            except OSError:
                continue
    return None


def host_gtk_settings(home):
    """Lee la preferencia GTK publicada por el escritorio anfitrión.

    En Flatpak, Gtk.Settings puede devolver Adwaita aunque el usuario haya
    seleccionado Colloid/Terafox fuera del contenedor. Los settings.ini
    accesibles permiten identificar el tema; no interpretamos estilos Qt.
    """
    home = Path(home)
    for version in ('4.0', '3.0'):
        path = home / '.config' / ('gtk-' + version) / 'settings.ini'
        cfg = configparser.ConfigParser(interpolation=None)
        try:
            if path.is_file():
                cfg.read(path, encoding='utf-8')
                if cfg.has_section('Settings'):
                    name = cfg.get('Settings', 'gtk-theme-name', fallback='')
                    dark = cfg.getboolean('Settings', 'gtk-application-prefer-dark-theme', fallback=False)
                    if name or dark:
                        return name, dark
        except (OSError, ValueError, configparser.Error):
            pass
    return '', False


def gtk_theme_prefers_dark(theme_name, prefer_dark=False):
    """Detecta temas GTK con variante oscura: Colloid-Dark-Teal, Adwaita:dark, etc.

    Se usa como respaldo de la preferencia del portal XDG, no para copiar
    arbitrariamente CSS de temas GTK3 o colores de aplicaciones Qt.
    """
    return bool(prefer_dark or re.search(r"(?:^|[-_:])dark(?:$|[-_:])", str(theme_name or "").lower()))


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.casefold()) if not unicodedata.combining(c))


def read_m3u(path):
    found, meta = [], None
    with open(path, "r", encoding="utf-8-sig", errors="replace") as stream:
        for raw in stream:
            line = raw.strip()
            if line.startswith("#EXTINF"):
                attrs = dict(ATTR_RE.findall(line))
                name = line.rsplit(",", 1)[-1].strip() if "," in line else ""
                meta = (name or attrs.get("tvg-name") or "Sin nombre",
                        attrs.get("group-title") or "Otros", attrs.get("tvg-logo", ""))
            elif line and not line.startswith("#"):
                if meta and urlsplit(line).scheme.lower() in {"http", "https", "rtsp", "rtmp", "udp", "mms"}:
                    found.append(Channel(meta[0], meta[1], line, meta[2]))
                meta = None
    return found


def read_settings():
    try:
        obj = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(obj):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(CONFIG_PATH)


def find_m3u(cli_path):
    settings = read_settings()
    for candidate in (cli_path, os.environ.get("IPTV_PLAYLIST"), settings.get("playlist"),
                      "~/Vídeos/alacarta.m3u", "~/Videos/alacarta.m3u"):
        if candidate and Path(candidate).expanduser().is_file():
            return Path(candidate).expanduser().resolve()
    return None


def sanitize_line(line, url):
    line = line.strip()
    if url:
        line = line.replace(url, "[URL PRIVADA]")
    parts = urlsplit(url)
    if parts.netloc:
        line = line.replace(parts.netloc, "[SERVIDOR PRIVADO]")
    for part in parts.path.split("/"):
        if len(part) >= 8 or part.isdigit():
            line = line.replace(part, "[DATO PRIVADO]")
    return re.sub(r"(?i)(?:https?|rtsp|rtmp|udp)://[^\s\"'<>]+", "[URL PRIVADA]", line)[:700]


# ctypes: definiciones exactas de mpv/render.h y mpv/render_gl.h.
# No depende de pip, PyOpenGL, X11 ni del paquete python-mpv.
class RenderParam(C.Structure):
    _fields_ = [("type", C.c_int), ("data", C.c_void_p)]


GetProc = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_char_p)
UpdateCb = C.CFUNCTYPE(None, C.c_void_p)
# Firma real GLsync glFenceSync(GLenum condition, GLbitfield flags).
FenceSync = C.CFUNCTYPE(C.c_void_p, C.c_uint, C.c_uint)


class GLInit(C.Structure):
    _fields_ = [("get_proc_address", GetProc), ("get_proc_address_ctx", C.c_void_p)]


class GLFbo(C.Structure):
    _fields_ = [("fbo", C.c_int), ("w", C.c_int), ("h", C.c_int), ("internal_format", C.c_int)]


class MpvEvent(C.Structure):
    _fields_ = [("event_id", C.c_int), ("error", C.c_int),
                ("reply_userdata", C.c_uint64), ("data", C.c_void_p)]


class MpvLog(C.Structure):
    _fields_ = [("prefix", C.c_char_p), ("level", C.c_char_p),
                ("text", C.c_char_p), ("log_level", C.c_int)]


class MpvEndFile(C.Structure):
    _fields_ = [("reason", C.c_int), ("error", C.c_int),
                ("playlist_entry_id", C.c_int), ("playlist_insert_id", C.c_int)]


class NativeMpv:
    def __init__(self, GLib, player_options=None):
        self.GLib = GLib
        self.player_options = player_options or {}
        library = os.environ.get("SYN_MACOS_LIBMPV") or ctypes.util.find_library("mpv")
        if not library:
            raise RuntimeError("No está instalada libmpv. Ejecuta: sudo dnf install mpv-libs")
        self.lib = C.CDLL(library)
        self._bind()
        # GTK respeta el idioma del sistema, pero libmpv exige LC_NUMERIC=C.
        # En una sesión española (decimal con coma), mpv_create() devuelve NULL.
        # Fijarlo justo antes de crear el reproductor evita que GTK lo restablezca.
        try:
            locale.setlocale(locale.LC_NUMERIC, "C")
        except locale.Error as exc:
            raise RuntimeError(f"No se pudo establecer LC_NUMERIC=C: {exc}") from exc
        self.ptr = self.lib.mpv_create()
        if not self.ptr:
            actual = locale.setlocale(locale.LC_NUMERIC)
            raise RuntimeError(
                f"No se pudo crear libmpv (LC_NUMERIC={actual}). "
                "Ejecuta desde Ghostty para ver los detalles."
            )
        self.ctx = C.c_void_p()
        self.closed = False
        self.active_url = ""
        self.active_name = ""
        self.logs = deque(maxlen=32)
        self.on_status = None
        self._lock = threading.Lock()
        self._callback_pending = False
        self._frame_callback = None
        # No llamar a mpv_get_property, mpv_command ni mpv_set_property
        # desde el hilo GTK que ejecuta mpv_render_context_render.
        self._control_queue = queue.Queue()
        self._stop_controls = threading.Event()
        self._control_thread = None
        self._dimensions = None
        self._display_dimensions = None
        self._syn_ts_playback_time = None
        self._syn_reconnect_buffering = False
        self._syn_reconnect_seeking = False
        self._awaiting_load = False
        self._is_paused = False
        self._last_frame_at = time.monotonic()
        self._render_count = 0
        self._watchdog_logged = False
        self._stop_watchdog = threading.Event()
        self._watchdog_thread = None
        self._proc_callback = None
        self._fence_noop = None
        self._gl_init = None
        self._gl_api_name = None
        self._libGL = None
        self._libEGL = None
        self._event_thread = None
        self._stop_events = threading.Event()

        try:
            self._check(self.lib.mpv_set_option_string(self.ptr, b"vo", b"libmpv"), "opción de vídeo")
            # MPV settings are read on startup. Default means NO overriding
            # network/media flags; this is the known-working Fedora setup.
            opt = self.player_options
            ua = opt.get('user_agent', 'Predeterminado')
            presets = {
                'VLC': 'VLC/3.0.21 LibVLC/3.0.21',
                'Firefox': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
                'Safari': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
                'Personalizado': str(opt.get('custom_ua','')).strip(),
            }
            if ua in presets and presets[ua]:
                self._check(self.lib.mpv_set_option_string(self.ptr, b'user-agent', presets[ua].encode()), 'User-Agent')
            for key, choices in (
                ('hwdec', ('no', 'auto', 'auto-safe')),
                ('cache', ('yes', 'no', 'auto')),
                ('video-sync', ('audio', 'display-resample'))):
                setting_key = 'video_sync' if key == 'video-sync' else key
                value = str(opt.get(setting_key, 'Predeterminado'))
                if value in choices:
                    self._check(self.lib.mpv_set_option_string(self.ptr, key.encode(), value.encode()), key)
            try: megabytes = int(opt.get('demuxer_mb') or 0)
            except (ValueError, TypeError): megabytes = 0
            if 1 <= megabytes <= 1024:
                self._check(self.lib.mpv_set_option_string(self.ptr, b'demuxer-max-bytes', f'{megabytes}MiB'.encode()), 'búfer de MPV')
            # Mantener la petición de red ORIGINAL: no establecer user-agent, referrer ni HLS -> TS.
            self._check(self.lib.mpv_initialize(self.ptr), "inicialización de MPV")
            self.lib.mpv_request_log_messages(self.ptr, b"warn")
            self._event_thread = threading.Thread(target=self._read_events, name="libmpv-events", daemon=True)
            self._event_thread.start()
            self._control_thread = threading.Thread(target=self._control_loop, name="libmpv-control", daemon=True)
            self._control_thread.start()
            self._watchdog_thread = threading.Thread(target=self._watchdog_loop, name="iptv-render-watchdog", daemon=True)
            self._watchdog_thread.start()
        except Exception:
            self.lib.mpv_terminate_destroy(self.ptr)
            self.ptr = None
            raise

    def _bind(self):
        l = self.lib
        l.mpv_create.argtypes = []; l.mpv_create.restype = C.c_void_p
        l.mpv_set_option_string.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p]; l.mpv_set_option_string.restype = C.c_int
        l.mpv_initialize.argtypes = [C.c_void_p]; l.mpv_initialize.restype = C.c_int
        l.mpv_command.argtypes = [C.c_void_p, C.POINTER(C.c_char_p)]; l.mpv_command.restype = C.c_int
        l.mpv_get_property.argtypes = [C.c_void_p, C.c_char_p, C.c_int, C.c_void_p]; l.mpv_get_property.restype = C.c_int
        l.mpv_set_property.argtypes = [C.c_void_p, C.c_char_p, C.c_int, C.c_void_p]; l.mpv_set_property.restype = C.c_int
        l.mpv_error_string.argtypes = [C.c_int]; l.mpv_error_string.restype = C.c_char_p
        l.mpv_terminate_destroy.argtypes = [C.c_void_p]; l.mpv_terminate_destroy.restype = None
        l.mpv_wait_event.argtypes = [C.c_void_p, C.c_double]; l.mpv_wait_event.restype = C.POINTER(MpvEvent)
        l.mpv_request_log_messages.argtypes = [C.c_void_p, C.c_char_p]; l.mpv_request_log_messages.restype = C.c_int
        l.mpv_render_context_create.argtypes = [C.POINTER(C.c_void_p), C.c_void_p, C.POINTER(RenderParam)]
        l.mpv_render_context_create.restype = C.c_int
        l.mpv_render_context_set_update_callback.argtypes = [C.c_void_p, UpdateCb, C.c_void_p]
        l.mpv_render_context_set_update_callback.restype = None
        l.mpv_render_context_update.argtypes = [C.c_void_p]; l.mpv_render_context_update.restype = C.c_uint64
        l.mpv_render_context_render.argtypes = [C.c_void_p, C.POINTER(RenderParam)]; l.mpv_render_context_render.restype = C.c_int
        l.mpv_render_context_free.argtypes = [C.c_void_p]; l.mpv_render_context_free.restype = None

    def _check(self, result, operation):
        if result < 0:
            desc = self.lib.mpv_error_string(result).decode("utf-8", "replace")
            raise RuntimeError(f"Fallo en {operation}: {desc}")

    def _mpv_command(self, *args):
        # Solo desde el hilo de control, nunca desde Gtk.GLArea::render.
        buf = (C.c_char_p * (len(args) + 1))(*(str(arg).encode("utf-8") for arg in args), None)
        return self.lib.mpv_command(self.ptr, buf)

    def command(self, *args):
        if self.closed or not self.ptr:
            return -1
        self._control_queue.put(("command", args))
        return 0  # El error real se notifica asíncronamente.

    def screenshot_to_file(self, destination, callback):
        # Never call mpv_command from GTK's GL rendering/main thread.
        # Deliver the actual libmpv result on GLib, not just queued status.
        if self.closed or not self.ptr:
            return False
        self._control_queue.put(("screenshot_file", (str(destination), callback)))
        return True

    def _control_loop(self):
        # Las llamadas normales a libmpv se hacen fuera del hilo de render.
        # Nunca utilizamos un lock que el hilo OpenGL necesite adquirir.
        next_poll = time.monotonic()
        while not self._stop_controls.is_set():
            try:
                task = self._control_queue.get(timeout=0.15)
            except queue.Empty:
                task = None
            if self._stop_controls.is_set():
                break
            if task:
                operation, args = task
                try:
                    if operation == "command":
                        err = self._mpv_command(*args)
                    elif operation == "screenshot_file":
                        filename, callback = args
                        err = self._mpv_command('screenshot-to-file', filename, 'video')
                        message = (self.lib.mpv_error_string(err).decode('utf-8', 'replace')
                                   if err < 0 else '')
                        self.GLib.idle_add(callback, err, message)
                    elif operation == "volume":
                        value = C.c_double(float(args[0]))
                        err = self.lib.mpv_set_property(self.ptr, b"volume", 5, C.byref(value))
                    else:
                        continue
                    if err < 0:
                        self.GLib.idle_add(self._notify, "MPV: " + self.lib.mpv_error_string(err).decode("utf-8", "replace"), True)
                except Exception as exc:
                    self.GLib.idle_add(self._notify, "Error de control de MPV: " + str(exc), True)

            if self.active_url and not self._awaiting_load and time.monotonic() >= next_poll:
                width, height = C.c_longlong(), C.c_longlong()
                w = self.lib.mpv_get_property(self.ptr, b"video-params/w", 4, C.byref(width))
                h = self.lib.mpv_get_property(self.ptr, b"video-params/h", 4, C.byref(height))
                self._dimensions = (width.value, height.value) if w >= 0 and h >= 0 and width.value > 0 and height.value > 0 else None
                # Corrected DISPLAY aspect (e.g. 1440x1080 broadcast 16:9).
                # Two integer reads on the existing 800ms libmpv worker.
                display_w, display_h = C.c_longlong(), C.c_longlong()
                result_dw = self.lib.mpv_get_property(self.ptr, b'video-params/dw', 4, C.byref(display_w))
                result_dh = self.lib.mpv_get_property(self.ptr, b'video-params/dh', 4, C.byref(display_h))
                self._display_dimensions = (
                    (display_w.value, display_h.value)
                    if result_dw >= 0 and result_dh >= 0 and min(display_w.value, display_h.value) > 0
                    else self._dimensions
                )
                position = C.c_double(0)
                result = self.lib.mpv_get_property(self.ptr, b'time-pos', 5, C.byref(position))
                self._syn_ts_playback_time = float(position.value) if result >= 0 else None
                # MPV_FORMAT_FLAG = 3. Snapshot consumed by GTK later.
                flag = C.c_int(0)
                res = self.lib.mpv_get_property(self.ptr, b'paused-for-cache', 3, C.byref(flag))
                self._syn_reconnect_buffering = bool(flag.value) if res >= 0 else False
                flag = C.c_int(0)
                res = self.lib.mpv_get_property(self.ptr, b'seeking', 3, C.byref(flag))
                self._syn_reconnect_seeking = bool(flag.value) if res >= 0 else False
                next_poll = time.monotonic() + 0.8
            elif not self.active_url:
                self._dimensions = None
                self._display_dimensions = None
                self._syn_ts_playback_time = None
                self._syn_reconnect_buffering = False
                self._syn_reconnect_seeking = False
                next_poll = time.monotonic() + 0.8

    def _watchdog_loop(self):
        # Si la interfaz se bloquea en una función GL, el hilo de diagnóstico
        # puede seguir ejecutándose y guardar las pilas SIN credenciales.
        while not self._stop_watchdog.wait(2):
            if (not self.active_url or self._is_paused or self._watchdog_logged
                    or self._render_count == 0):
                continue
            if time.monotonic() - self._last_frame_at < 8:
                continue
            self._watchdog_logged = True
            try:
                LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
                # Abrir en modo privado desde el principio (umask del proceso).
                fd = os.open(HANG_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as out:
                    os.chmod(HANG_PATH, 0o600)
                    out.write("IPTV Integrado: más de 8 segundos sin dibujar vídeo.\n")
                    out.write(f"Canal: {self.active_name}\nFotogramas dibujados: {self._render_count}\n")
                    if os.path.isdir("/proc/self/fd"):
                        out.write(f"Descriptores abiertos: {len(os.listdir('/proc/self/fd'))}\n")
                    out.write("Diagnóstico de hilos (sin direcciones IPTV):\n")
                    out.flush()
                    faulthandler.dump_traceback(file=out, all_threads=True)
            except OSError:
                pass

    def _read_events(self):
        while not self._stop_events.is_set():
            evptr = self.lib.mpv_wait_event(self.ptr, 0.25)
            if not evptr or self._stop_events.is_set():
                break
            event = evptr.contents
            if event.event_id == 2 and event.data:  # MPV_EVENT_LOG_MESSAGE
                msg = C.cast(event.data, C.POINTER(MpvLog)).contents
                if msg.text:
                    with self._lock:
                        self.logs.append(sanitize_line(msg.text.decode("utf-8", "replace"), self.active_url))
            elif event.event_id == 8:  # MPV_EVENT_FILE_LOADED
                # video-params may still describe the preceding DVR recording.
                # Only poll dimensions after this media file has loaded.
                self._dimensions = None
                self._display_dimensions = None
                self._awaiting_load = False
                self.GLib.idle_add(self._notify, "Reproduciendo", False)
            elif event.event_id == 7 and event.data:  # MPV_EVENT_END_FILE
                end = C.cast(event.data, C.POINTER(MpvEndFile)).contents
                if end.reason == 4:  # MPV_END_FILE_REASON_ERROR
                    self.GLib.idle_add(self._notify, "Error al cargar el canal. Consulta el diagnóstico.", True)

    def _notify(self, message, failed):
        if not self.closed and self.on_status:
            self.on_status(message, failed)
        return False

    def initialize_opengl(self, queue_draw):
        self._libGL = C.CDLL("/System/Library/Frameworks/OpenGL.framework/OpenGL")
        self._libGL.glGetIntegerv.argtypes = [C.c_uint, C.POINTER(C.c_int)]
        self._libGL.glGetIntegerv.restype = None
        self._libGL.glClearColor.argtypes = [C.c_float] * 4
        self._libGL.glClear.argtypes = [C.c_uint]
        self._libEGL = None  # Quartz/OpenGL has no EGL

        # mpv 0.41 llama glFenceSync() tras cada fotograma integrado, pero
        # puede no liberar los GLsync creados (issue #17217). En v1.5
        # ocultábamos por completo el símbolo, lo que hacía que el cargador
        # de OpenGL rechazase el contexto con MPV_ERROR_UNSUPPORTED.
        #
        # Ahora conservamos un puntero de función ABI-compatible y hacemos
        # que devuelva GLsync NULL. El propio mpv 0.41 comprueba `if (fence)`
        # antes de guardar la fence: así NO crea fences/FDs y el cargador
        # puede inicializarse. Solo afecta a los símbolos que libmpv nos
        # solicita, no al OpenGL de GTK. Es un workaround reversible.
        # Desactivar: IPTV_ENABLE_GL_FENCES=1 antes del comando.
        @FenceSync
        def no_fence_sync(_condition, _flags):
            return None

        self._fence_noop = no_fence_sync  # Mantener el callback vivo.

        @GetProc
        def get_proc(_ctx, name):
            if name == b"glFenceSync" and os.environ.get("IPTV_ENABLE_GL_FENCES") != "1":
                return C.cast(self._fence_noop, C.c_void_p).value
            address = _syn_macos_gl_proc(self._libGL, name)
            if not address:
                # Algunas plataformas no exportan símbolos GL básicos por eglGetProcAddress.
                try:
                    address = C.cast(getattr(self._libGL, name.decode("ascii")), C.c_void_p).value
                except (AttributeError, UnicodeDecodeError):
                    address = None
            return address or None

        @UpdateCb
        def callback(_ctx):
            # Se ejecuta desde hilos internos de MPV. No invocar ninguna API
            # mpv_render_* ni de GTK aquí; avisar al loop principal solamente.
            with self._lock:
                if self.closed or self._callback_pending:
                    return
                self._callback_pending = True
            self.GLib.idle_add(schedule_redraw, priority=self.GLib.PRIORITY_HIGH_IDLE)

        def schedule_redraw():
            with self._lock:
                self._callback_pending = False
            if not self.closed and self.ctx.value:
                queue_draw()  # GTK emitirá render con el contexto GL activo.
            return False

        self._proc_callback = get_proc  # ctypes callbacks MUST remain alive.
        self._frame_callback = callback
        self._gl_init = GLInit(get_proc, None)
        # MPV_RENDER_PARAM_API_TYPE (tipo char*) exige la dirección
        # del texto "opengl", NO la dirección de un char**. La v1.1
        # enviaba un puntero de más, provocando MPV_ERROR_NOT_IMPLEMENTED.
        # Conservamos el buffer mientras viva el contexto de renderizado.
        self._gl_api_name = C.create_string_buffer(b"opengl")
        params = (RenderParam * 3)(
            RenderParam(1, C.cast(self._gl_api_name, C.c_void_p)),
            RenderParam(2, C.cast(C.pointer(self._gl_init), C.c_void_p)),
            RenderParam(0, None),
        )
        self._check(self.lib.mpv_render_context_create(C.byref(self.ctx), self.ptr, params), "renderizado OpenGL")
        self.lib.mpv_render_context_set_update_callback(self.ctx, self._frame_callback, None)

    def render(self, width, height):
        if not self.ctx.value or self.closed:
            return
        # Solo se llama desde Gtk.GLArea::render, que ha hecho current el
        # MISMO contexto OpenGL utilizado al crear el renderizador. En v1.3
        # se llamaba mpv_render_context_update desde un idle sin contexto:
        # comportamiento indefinido, especialmente con VirGL/Wayland.
        self.lib.mpv_render_context_update(self.ctx)
        framebuffer = C.c_int(0)
        self._libGL.glGetIntegerv(0x8CA6, C.byref(framebuffer))  # GL_DRAW_FRAMEBUFFER_BINDING
        fbo = GLFbo(framebuffer.value, max(1, width), max(1, height), 0)
        flip = C.c_int(1)
        # La función render() no debe dormir esperando al instante de
        # presentación: bloquearía la UI completa dentro de GTK/Wayland.
        no_wait = C.c_int(0)
        params = (RenderParam * 4)(
            RenderParam(3, C.cast(C.pointer(fbo), C.c_void_p)),
            RenderParam(4, C.cast(C.pointer(flip), C.c_void_p)),
            RenderParam(12, C.cast(C.pointer(no_wait), C.c_void_p)),
            RenderParam(0, None),
        )
        result = self.lib.mpv_render_context_render(self.ctx, params)
        if result < 0:
            # No hacer otra llamada a libmpv desde el hilo de render.
            self.GLib.idle_add(self._notify, f"Error de renderizado MPV ({result})", True)
        else:
            self._last_frame_at = time.monotonic()
            self._render_count += 1
            self._watchdog_logged = False

    def play(self, channel):
        self._awaiting_load = True
        self.active_url = channel.url
        self.active_name = channel.name
        self._dimensions = None
        self._display_dimensions = None
        self._syn_ts_playback_time = None
        self._syn_reconnect_buffering = False
        self._syn_reconnect_seeking = False
        self._is_paused = False
        self._render_count = 0
        self._last_frame_at = time.monotonic()
        self._watchdog_logged = False
        with self._lock:
            self.logs.clear()
        self._check(self.command("loadfile", channel.url, "replace"), "apertura de canal")

    def stop(self):
        self._awaiting_load = True
        self.command("stop")
        self.active_url = ""
        self._dimensions = None
        self._display_dimensions = None
        self._is_paused = False

    def paused(self):
        return self._is_paused

    def toggle_pause(self):
        if self.active_url:
            self._is_paused = not self._is_paused
            self.command("cycle", "pause")

    def volume(self, val):
        if not self.closed and self.ptr:
            self._control_queue.put(("volume", (val,)))

    def playback_position(self):
        # Snapshot del hilo de control de mpv, nunca una llamada GTK síncrona.
        return self._syn_ts_playback_time

    def video_dimensions(self):
        # Snapshot actualizado por el hilo de control: no bloquea GTK.
        return (self._dimensions if not self.closed and self.active_url
                and not self._awaiting_load else None)

    def video_display_dimensions(self):
        # Snapshot inmutable del hilo de control: refleja el PAR/DAR real.
        # GTK lee solamente la tupla; NO llama sincrónicamente a libmpv.
        if self.closed or not self.active_url or self._awaiting_load:
            return None
        return self._display_dimensions or self._dimensions

    def write_diag(self):
        with self._lock:
            recent = list(self.logs)
        if not recent:
            recent = ["No se ha recibido información de error de libmpv."]
        LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Nunca guardar URL, usuario ni contraseña de M3U.
        text = "Canal: " + self.active_name + "\nMotor: libmpv nativo (sin User-Agent)\n\n" + "\n".join(recent) + "\n"
        LOG_PATH.write_text(text, encoding="utf-8")
        LOG_PATH.chmod(0o600)
        return text

    def free_renderer(self):
        if self.ctx.value:
            self.lib.mpv_render_context_set_update_callback(self.ctx, UpdateCb(), None)
            self.lib.mpv_render_context_free(self.ctx)
            self.ctx = C.c_void_p()

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self._stop_events.set()
        self._stop_controls.set()
        self._stop_watchdog.set()
        self._control_queue.put(None)
        # No destruir el handle mientras los lectores lo estén usando.
        for worker in (self._control_thread, self._event_thread, self._watchdog_thread):
            if worker:
                worker.join(timeout=2.0)
        if any(worker and worker.is_alive() for worker in (self._control_thread, self._event_thread, self._watchdog_thread)):
            # Más seguro dejar la limpieza al cierre del proceso que causar
            # un use-after-free en caso de bloqueo grave del driver.
            return
        if self.ptr:
            self.lib.mpv_terminate_destroy(self.ptr)
            self.ptr = None



def epg_window_segments(programmes, start, duration_minutes=300):
    """Segmentos de EPG recortados a la ventana temporal, incluyendo huecos.

    (inicio, fin, titulo, descripcion, disponible). Los intervalos se recortan,
    no se duplican y nunca se representan fuera de la ventana visible.
    """
    end = start + dt.timedelta(minutes=duration_minutes)
    cursor = start
    rows = []
    ordered = sorted((p for p in programmes if len(p) >= 3 and p[1] > start and p[0] < end), key=lambda p: p[0])
    for item in ordered:
        a, b = max(item[0], start, cursor), min(item[1], end)
        if b <= a: continue
        if a > cursor:
            rows.append((cursor, a, 'Programación no disponible', '', False))
        rows.append((a, b, str(item[2]), str(item[3]) if len(item) > 3 else '', True))
        cursor = b
        if cursor >= end: break
    if cursor < end:
        rows.append((cursor, end, 'Programación no disponible', '', False))
    return rows


def epg_floor_hour(when):
    return when.replace(minute=0, second=0, microsecond=0)


def epg_time_label(start, end):
    return f"{format_time(start)}–{format_time(end)}"


# Arrancamos mostrando programación ANTERIOR a la hora actual. La v3.7.2
# reducía el pasado a seis minutos: eso eliminaba casi todos los bloques
# previos, en lugar de llenar visualmente el lado izquierdo de la guía.
EPG_LOOKBACK_MINUTES = 90
EPG_NOW_FRACTION = 0.45

# Anchos VISIBLES reales de la guía; nunca se permite que el contenido los ensanche.
GUIDE_CATEGORIES_WIDTH = 158
GUIDE_CHANNEL_WIDTH = 174


def epg_initial_start(when, lookback_minutes=EPG_LOOKBACK_MINUTES):
    """Ventana temporal con 90 min de programación pasada antes de «Ahora»."""
    return when.replace(second=0, microsecond=0) - dt.timedelta(minutes=lookback_minutes)


def epg_minutes_scale(viewport_width, lookback_minutes=EPG_LOOKBACK_MINUTES,
                      now_fraction=EPG_NOW_FRACTION):
    """Dimensiona el pasado al 45% del ancho visible de la parrilla.

    «Ahora» deja a la izquierda los bloques de programas anteriores y
    mantiene a la derecha espacio suficiente para los siguientes.
    """
    if viewport_width <= 0 or lookback_minutes <= 0:
        raise ValueError('El ancho y el intervalo deben ser positivos')
    if not 0 < now_fraction < 1:
        raise ValueError('now_fraction debe estar entre cero y uno')
    return max(1.0, min(26.0, viewport_width * now_fraction / lookback_minutes))


def epg_axis_sections(start, duration_minutes=300, tick_minutes=30):
    """Franjas del eje de tiempo, alineadas con las medias horas del reloj."""
    if duration_minutes <= 0 or tick_minutes <= 0:
        raise ValueError('Duración y paso deben ser positivos')
    end = start + dt.timedelta(minutes=duration_minutes)
    cursor = start
    intervals = []
    while cursor < end:
        midnight = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        since_midnight = int((cursor-midnight).total_seconds() // 60)
        next_tick_min = (since_midnight // tick_minutes + 1) * tick_minutes
        boundary = min(end, midnight + dt.timedelta(minutes=next_tick_min))
        # El primer tramo parcial no inventa una marca horaria fuera de sitio.
        aligned = (since_midnight % tick_minutes == 0 and cursor.second == 0)
        intervals.append((cursor if aligned else None, (boundary-cursor).total_seconds()/60))
        cursor = boundary
    return intervals


def epg_x_at(instant, start, pixels_per_minute):
    """Posición X absoluta de una hora en la parrilla (nunca relativa a widgets previos)."""
    if pixels_per_minute <= 0:
        raise ValueError('La escala temporal debe ser positiva')
    return int(round((instant - start).total_seconds() / 60.0 * pixels_per_minute))


def epg_geometry(programmes, start, pixels_per_minute, duration_minutes=300):
    """Coordenadas absolutas de los segmentos EPG y sus huecos sin datos."""
    return [(epg_x_at(a, start, pixels_per_minute),
             max(1, epg_x_at(b, start, pixels_per_minute) - epg_x_at(a, start, pixels_per_minute)),
             a, b, title, description, available)
            for a, b, title, description, available in epg_window_segments(
                programmes, start, duration_minutes)]




# SYN_207_LIGHT_POPOVER: validated Fedora Flatpak light surfaces.
def light_surface_css(theme, system_dark=False):
    """Keep the standalone settings window and detached popovers coherent.

    Dark themes (including dark System) are *intentionally* untouched.
    """
    schemes = {
        # background, foreground, surface, stroke, hover, selected, accent
        'system': ('@window_bg_color', '@window_fg_color', '@view_bg_color',
                   'alpha(@window_fg_color,.16)', 'alpha(@window_fg_color,.08)',
                   'alpha(@accent_bg_color,.16)', '@accent_bg_color'),
        'light': ('#f1f8f6', '#17413b', '#f8fffc', '#bfdcd1', '#ddf1eb', '#b8e7da', '#177e79'),
        'nord-light': ('#eceff4', '#293b4c', '#ffffff', '#c7d1dc', '#dae6f0', '#c6d9e8', '#416a93'),
        'gruvbox-light': ('#fbf1c7', '#3c3836', '#fff9e9', '#d5c8aa', '#f0e5cb', '#e5d5b5', '#346a68'),
    }
    if theme not in schemes or (theme == 'system' and system_dark):
        return ''
    bg, fg, surface, stroke, hover, selected, accent = schemes[theme]
    css = f"""
    /* Root, native client-side titlebar and Close button of Settings.
       This is separate from the video window; host dark GTK USER CSS otherwise
       takes precedence over SYN's light APPLICATION theme. */
    window.syn-settings-window {{
      background-image:none; background-color:{bg}; color:{fg};
    }}
    window.syn-settings-window > headerbar,
    window.syn-settings-window headerbar,
    window.syn-settings-window .titlebar,
    window.syn-settings-window .default-decoration,
    window.syn-settings-window headerbar windowhandle {{
      background-image:none; background-color:{bg}; color:{fg};
      border-color:{stroke}; box-shadow:none;
    }}
    window.syn-settings-window headerbar label,
    window.syn-settings-window headerbar image,
    window.syn-settings-window .titlebar label,
    window.syn-settings-window .titlebar image {{
      color:{fg}; opacity:1; text-shadow:none;
    }}
    window.syn-settings-window windowcontrols button,
    window.syn-settings-window headerbar button,
    window.syn-settings-window .titlebar button {{
      background-image:none; background-color:transparent;
      border:0; box-shadow:none; color:{fg};
    }}
    window.syn-settings-window windowcontrols button:hover,
    window.syn-settings-window headerbar button:hover,
    window.syn-settings-window .titlebar button:hover {{
      background-image:none; background-color:{hover}; color:{fg};
    }}
    window.syn-settings-window windowcontrols button image,
    window.syn-settings-window .titlebar button image {{ color:{fg}; }}
    window.syn-settings-window .syn-pref-header,
    window.syn-settings-window .syn-pref-footer {{
      background-image:none; background-color:{bg}; color:{fg};
      border-color:{stroke};
    }}
    window.syn-settings-window .syn-pref-heading,
    window.syn-settings-window .syn-pref-header image,
    window.syn-settings-window .syn-pref-section-title {{
      color:{fg}; opacity:1; text-shadow:none;
    }}
    /* Detached popover and DropDown windows do not inherit their parent's CSS. */
    popover, popover.background, popover.menu {{ color:{fg}; }}
    popover > contents,
    popover.background > contents,
    popover.menu > contents {{
      background-image:none; background-color:{surface}; color:{fg};
      border:1px solid {stroke}; border-radius:12px;
      box-shadow:0 7px 24px rgba(0,0,0,.16);
    }}
    popover listview, popover listbox,
    popover scrolledwindow, popover viewport,
    popover listview row, popover listbox row {{
      background-image:none; background-color:{surface}; color:{fg};
    }}
    popover listview row:hover,
    popover listview row:focus,
    popover listbox row:hover,
    popover listbox row:focus {{
      background-color:{hover}; color:{fg};
    }}
    popover listview row:selected,
    popover listview row:selected:hover,
    popover listbox row:selected,
    popover listbox row:selected:hover {{
      background-color:{selected}; color:{fg};
    }}
    popover > contents label,
    popover > contents image,
    popover > contents modelbutton,
    popover > contents modelbutton label,
    popover listview row label,
    popover listbox row label {{
      color:{fg}; opacity:1; text-shadow:none;
    }}
    popover button.flat, popover modelbutton {{
      background-image:none; background-color:transparent; color:{fg};
      box-shadow:none;
    }}
    popover button.flat:hover, popover modelbutton:hover {{
      background-image:none; background-color:{hover}; color:{fg};
    }}
    popover entry, popover searchentry,
    popover entry text, popover searchentry text {{
      color:{fg}; background-color:{surface}; border-color:{stroke};
    }}
    popover scrollbar slider {{ background-color:{accent}; }}
    """
    # Keep Cast's separately approved styling; global popover selectors must
    # not override it after moving this patch to a higher GTK USER priority.
    return css + synplus_layout.cast_popover_css(theme)


def syn_popup_theme_css(theme):
    """Theme every GTK4 popover surface (including detached DropDown popups).

    Deliberately empty in Sistema: the host GTK theme remains authoritative.
    The provider using this CSS is installed above host USER priority.
    """
    palettes = {
        'light': ('#f8fffc', '#164d43', '#d4efe6', '#a9dfd0', '#acd9cd', '#80b7a9'),
        'dark': ('#252931', '#edf0f5', '#3b4350', '#4d5c70', '#555c68', '#7b8595'),
        'teal': ('#10332f', '#f1faf5', '#24534b', '#2e6e5f', '#315c55', '#6db5a1'),
        'nord-light': ('#ECEFF4', '#2E3440', '#D8DEE9', '#D8DEE9', '#C6CFDA', '#4C566A'),
        'nord-dark': ('#434C5E', '#ECEFF4', '#4C566A', '#5E81AC', '#4C566A', '#88C0D0'),
        'gruvbox-light': ('#fbf1c7', '#3c3836', '#d5c4a1', '#d5c4a1', '#bdae93', '#7c6f64'),
        'gruvbox-dark': ('#504945', '#ebdbb2', '#665c54', '#7c6f64', '#7c6f64', '#a89984'),
    }
    if theme not in palettes:
        return ''
    bg, fg, hover, selected, border, scroll = palettes[theme]
    return f"""
    /* GTK4 DropDown menus are GtkPopover surfaces, often detached in Wayland.
       Do not scope them under window.iptv-tv or dropdown ancestors. */
    popover, popover.background, popover.menu {{ color: {fg}; }}
    popover > contents, popover.background > contents,
    popover.menu > contents {{
        background-color: {bg}; color: {fg};
        border: 1px solid {border}; border-radius: 12px;
    }}
    popover listview, popover listbox, popover scrolledwindow,
    popover listview row, popover listbox row {{
        background-color: {bg}; color: {fg};
    }}
    popover listview row:hover, popover listbox row:hover,
    popover listview row:focus, popover listbox row:focus {{
        background-color: {hover}; color: {fg};
    }}
    popover listview row:selected, popover listbox row:selected,
    popover listview row:selected:hover, popover listbox row:selected:hover {{
        background-color: {selected}; color: {fg};
    }}
    popover listview row label, popover listview row image,
    popover listbox row label, popover modelbutton,
    popover modelbutton label, popover button label {{ color: {fg}; }}
    popover scrollbar slider {{ background-color: {scroll}; }}
    popover entry, popover searchentry {{
        background-color: {bg}; color: {fg}; border-color: {border};
    }}
    popover entry text, popover searchentry text {{ color: {fg}; }}
    """


def epg_axis_ink(theme):
    """Return (grid RGBA, hour-label RGBA) for the actual EPG background.

    Sistema retains SYN's dark cinematic guide even on a light desktop.
    Only the three explicit *light* themes use a dark hour-label ink.
    """
    if theme == 'light':
        return ((.19, .42, .37, .34), (.10, .27, .24, 1.0))
    if theme == 'nord-light':
        return ((.30, .35, .43, .34), (.18, .20, .25, 1.0))
    if theme == 'gruvbox-light':
        return ((.48, .43, .32, .34), (.24, .22, .21, 1.0))
    return ((.58, .80, .75, .35), (.82, .94, .91, .98))



def run_gui(playlist):
    # Compatibilidad selectiva con Parallels/VirGL. No imponer flags a
    # todas las distribuciones, GPUs y compositores por defecto.
    def is_parallels():
        for name in ('/sys/class/dmi/id/product_name', '/sys/class/dmi/id/sys_vendor',
                     '/sys/devices/virtual/dmi/id/product_name'):
            try:
                if 'parallels' in Path(name).read_text(errors='ignore').lower():
                    return True
            except OSError:
                pass
        return False
    compat = os.environ.get('SYN_COMPAT_GL', 'auto').lower()
    if os.environ.get('IPTV_GDK_DEFAULT') != '1' and (compat == '1' or (compat == 'auto' and is_parallels())):
        flags = [x.strip() for x in os.environ.get("GDK_DISABLE", "").split(",") if x.strip()]
        for feature in ("dmabuf", "vulkan"):
            if feature not in flags:
                flags.append(feature)
        os.environ["GDK_DISABLE"] = ",".join(flags)
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk, Adw, Gdk, Gio, GLib, Pango, GdkPixbuf
    except (ImportError, ValueError) as exc:
        print(f"Instala python3-gobject, gtk4 y libadwaita: {exc}", file=sys.stderr)
        return 1

    from syn_epg_pop import epg_gradient_css

    TEAL_CSS = """
    /* TEAL: petróleo profundo / mandarina, heredando la identidad SYN. */
    window.iptv-tv .syn-portal-root {background:#091f20; color:#f1faf6;}
    window.iptv-tv .syn-portal-top {background:#10332f; border-bottom:1px solid #285650;}
    window.iptv-tv .syn-portal-title,window.iptv-tv .syn-portal-hero,
    window.iptv-tv .syn-portal-tile-title {color:#f7fffb;}
    window.iptv-tv .syn-portal-kicker {color:#f0af78;}
    window.iptv-tv button.syn-portal-tile {background-image:linear-gradient(145deg,#183c3a,#102728); background-color:#123633; border:1px solid #315c55; color:#effbf6;}
    window.iptv-tv button.syn-portal-tile:hover {background-color:#24534b; border-color:#ffc38b;}
    window.iptv-tv .syn-portal-orb {background:#205b51;border-color:#75c9b4;}
    window.iptv-tv .syn-portal-orb-icon {color:#b6f8e3;}
    window.iptv-tv .syn-portal-orb-series {background:#533c2e;border-color:#eeb17b;}
    window.iptv-tv .syn-portal-orb-series .syn-portal-orb-icon {color:#ffc391;}
    window.iptv-tv .syn-portal-orb-movies {background:#333451;border-color:#b9a5e2;}
    window.iptv-tv .syn-portal-orb-movies .syn-portal-orb-icon {color:#d7c8ff;}
    window.iptv-tv .syn-portal-counter {color:#ffb57c;}
    window.iptv-tv button.syn-portal-poster-card {background:#143331; border-color:#31584f; color:#f6fffb;}
    window.iptv-tv button.syn-portal-poster-card:hover {background:#1c4742;border-color:#eab07b;}
    window.iptv-tv .syn-portal-poster {background:#1a4442;}
    window.iptv-tv, .iptv-surface { background: #0a201d; color: #f1faf5; }
    .iptv-header { background: #10332e; border-bottom: 1px solid #24544a; }
    .iptv-heading { font-size: 19px; font-weight: 800; color: #f6fbf8; }
    .iptv-subtitle { font-size: 12px; color: #9ac2b4; }
    .iptv-sidebar { background: #0d2825; border-right: 1px solid #28534a; }
    .iptv-search { background: #193d36; border-radius: 12px; }
    .iptv-dropdown { background: #193d36; border-radius: 10px; }
    .iptv-list { background: transparent; }
    .iptv-row { background: #13332f; border-radius: 10px; margin: 2px 6px; }
    .iptv-row:hover { background: #1c4942; }
    .iptv-row:selected { background: #24594f; outline: 1px solid #e69d65; }
    .iptv-channel { color: #f4faf7; font-size: 13px; font-weight: 700; }
    .iptv-group { color: #98bbae; font-size: 11px; }
    .iptv-icon { color: #eea66e; }
    .iptv-toolbar { background: #112d2a; border-top: 1px solid #24544a; }
    .iptv-accent { background: #f0a269; color: #182824; border-radius: 10px; font-weight: 800; }
    .iptv-accent:hover { background: #ffc291; }
    .iptv-info { color: #b6cfc7; font-size: 12px; }
    .iptv-video { background: #000; }
    /* El divisor nunca debe reservar píxeles ni dibujar una banda
       cuando la barra lateral está oculta en pantalla completa. */
    paned.iptv-fullscreen-paned > separator {
        min-width: 0; border: none; box-shadow: none; background: transparent;
    }
    .iptv-placeholder { color: #a7c8bb; font-size: 16px; font-weight: 600; }
    .iptv-details { color: #99b9ac; font-size: 12px; }
    window.iptv-tv button:not(.iptv-accent),
    window.iptv-tv dropdown, window.iptv-tv entry,
    window.iptv-tv searchentry {
      background-color: #193d36; color: #f2fbf7;
      border: 1px solid #2c6256; border-radius: 10px;
    }
    window.iptv-tv button:hover { background-color: #245449; }
    window.iptv-tv button.iptv-accent {
      background: #f0a269; color: #182824; border-color: #f0a269;
    }
    window.iptv-tv scale highlight { background-color: #f0a269; }

/* SYN Teal/Petróleo: saturated teal surface, orange accents, legible type. */
window.iptv-tv .syn-portal-root { background: #112e30; color: #f4fdfa; }
window.iptv-tv .syn-portal-top {background: #163639; border-bottom: 1px solid #386261;}
window.iptv-tv .syn-portal-kicker {color:#83d8cd;}
window.iptv-tv .syn-portal-title {color:#fff;}
window.iptv-tv button.syn-portal-poster-card {background:#18383a; border-color:#3d6060; color:#f4fdfa;}
window.iptv-tv button.syn-portal-poster-card:hover {background:#24504d; border-color:#ffb67f;}
window.iptv-tv .syn-portal-poster-name {color:#f7fffc;}
window.iptv-tv .syn-portal-poster-group {color:#c2dbd7;}

/* SYN 1.3.5c: poster grid fixes; preserve host GTK theme in Sistema. */
window.iptv-tv .syn-portal-void { font-size: 44px; font-weight: 900; opacity: .45; margin-bottom: 6px; }
window.iptv-tv flowbox.syn-portal-gallery { padding: 12px 0; }
window.iptv-tv button.syn-portal-poster-card { min-width: 170px; min-height: 290px; transition: border-color 180ms ease, background-color 180ms ease; }
window.iptv-tv .syn-portal-poster-name { font-weight: 770; }

"""

    # Por defecto usamos CSS nativo de GTK/libadwaita. Solo el tema teal
    # aplica los colores de marca. Esta base es necesaria para que el OSD
    # del televisor sea legible independientemente del tema de GNOME/KDE.
    BASE_CSS = """
    /* SYN 1.3.5b — portada y cartelera: sistema hereda GTK/libadwaita. */
    window.iptv-tv .syn-portal-root {
      background-color: @window_bg_color;
      color: @window_fg_color;
    }
    window.iptv-tv .syn-portal-top {
      background-color: alpha(@card_bg_color, 0.55);
      border-bottom: 1px solid alpha(@window_fg_color, 0.12);
      padding: 17px 25px;
    }
    window.iptv-tv .syn-portal-kicker {
      font-size: 10px; letter-spacing: 2px; font-weight: 850;
      color: @accent_color;
    }
    window.iptv-tv .syn-portal-title {
      font-weight: 850; font-size: 26px; color: @window_fg_color;
    }
    window.iptv-tv .syn-portal-hero {
      font-size: 32px; font-weight: 900; color: @window_fg_color;
    }
    window.iptv-tv .syn-portal-subtitle,
    window.iptv-tv .syn-portal-muted {font-size: 12px; opacity: 0.66;}
    window.iptv-tv button.syn-portal-tile {
      background-image: linear-gradient(145deg, alpha(@accent_color,.13), alpha(@card_bg_color,.72));
      background-color: @card_bg_color;
      border-radius: 25px;
      border: 1px solid alpha(@window_fg_color,.14);
      color: @window_fg_color;
      padding: 21px 13px;
      box-shadow: 0 4px 16px alpha(black,.12);
    }
    window.iptv-tv button.syn-portal-tile:hover {
      background-color: alpha(@accent_color,.2);
      border-color: alpha(@accent_color,.64);
      box-shadow: 0 9px 24px alpha(black,.17);
    }
    window.iptv-tv .syn-portal-orb {
      border-radius: 100px;
      border: 2px solid alpha(@accent_color,.35);
      background: alpha(@accent_color,.12);
    }
    window.iptv-tv .syn-portal-orb-series { background: alpha(#dd955a,.15); border-color: alpha(#dd955a,.54); }
    window.iptv-tv .syn-portal-orb-movies { background: alpha(#8f83d0,.15); border-color: alpha(#8f83d0,.50); }
    window.iptv-tv .syn-portal-orb-icon { font-size: 49px; font-weight: 650; color: @accent_color; }
    window.iptv-tv .syn-portal-orb-series .syn-portal-orb-icon { color: #cb8c42; }
    window.iptv-tv .syn-portal-orb-movies .syn-portal-orb-icon { color: #9d8bd9; }
    window.iptv-tv .syn-portal-tile-title { font-size: 23px; font-weight: 900; color: @window_fg_color; }
    window.iptv-tv .syn-portal-counter { font-size: 17px; font-weight: 800; color: @accent_color; }
    window.iptv-tv .syn-portal-tile-foot { font-size: 11px; opacity: .70; }
    window.iptv-tv button.syn-portal-poster-card {
      border: 1px solid alpha(@window_fg_color,.12);
      background-color: alpha(@card_bg_color,.68);
      border-radius: 17px; padding: 8px;
      color: @window_fg_color;
      box-shadow: 0 4px 12px alpha(black,.13);
    }
    window.iptv-tv button.syn-portal-poster-card:hover {
      border-color: alpha(@accent_color,.65);
      background-color: alpha(@accent_color,.13);
    }
    window.iptv-tv .syn-portal-poster {
      border-radius: 12px; background-color: alpha(@window_fg_color,.07);
      border: 1px solid alpha(@window_fg_color,.12);
    }
    window.iptv-tv .syn-portal-poster-fallback { opacity: .30; }
    window.iptv-tv .syn-portal-poster-name { font-size: 12px; font-weight: 780; }
    window.iptv-tv .syn-portal-poster-group { font-size: 10px; opacity: .64; }
    window.iptv-tv .syn-portal-empty { font-size: 20px; font-weight: 730; }
    window.iptv-tv button.syn-portal-back {border-radius: 12px;}
    window.iptv-tv .syn-portal-search {border-radius: 12px;}
    /* Colores de interfaz heredados de GTK4/libadwaita, no de una paleta fija. */
    .syn-dvr-page { background-color: @window_bg_color; padding: 14px 18px; }
    .syn-dvr-rec { min-height: 27px; min-width: 27px; padding: 0 4px;
      border-radius: 6px; color: #e72f48; font-size: 17px; font-weight: 900; }
    .syn-dvr-rec:hover { color: #ff5368; }
    .iptv-accent { background-color: var(--accent-bg-color);
                   color: var(--accent-fg-color);
                   border-radius: 10px; font-weight: 800; }
    .iptv-icon { color: var(--accent-color); }
    /* SYN 3.2: scrims independientes, no bloques que tapen la imagen. */
    .syn-fs-dim { background-color: rgba(0, 0, 0, 0.12); }
    .syn-fs-scrim-top {
      background-image: linear-gradient(to bottom,
         rgba(0, 12, 14, 0.79) 0%, rgba(0, 12, 14, 0.35) 50%, rgba(0, 12, 14, 0) 100%);
    }
    .syn-fs-scrim-bottom {
      background-image: linear-gradient(to top,
         rgba(0, 12, 14, 0.92) 0%, rgba(0, 12, 14, 0.66) 40%, rgba(0, 12, 14, 0) 100%);
    }
    .syn-fs-top { background: transparent; padding: 0; margin: 24px; border: none; }
    .syn-fs-top button {
      background-color: rgba(4, 30, 33, 0.38);
      border: 1px solid rgba(240, 255, 251, 0.23);
      border-radius: 12px;
      color: #ffffff;
      box-shadow: none;
      min-height: 37px;
      min-width: 39px;
    }
    .syn-fs-top button:hover, .syn-fs-top button:focus {
      background-color: rgba(21, 84, 78, 0.75);
      border-color: rgba(255, 255, 255, 0.68);
    }
    .syn-fs-bottom { background: transparent; border: none;
                     padding: 0 4px 14px 4px; margin: 24px 28px; }
    .syn-fs-channel { color: #ffffff; font-size: 30px; font-weight: 800;
                      text-shadow: 0 2px 8px rgba(0, 0, 0, 0.45); }
    .syn-fs-epg { color: #d7ede7; font-size: 14px;
                  text-shadow: 0 1px 5px rgba(0, 0, 0, 0.60); }
    /* SYN: degradado direccional a pantalla completa, no tarjeta opaca. */
    .syn-zap-backdrop {
      background-image: linear-gradient(to left,
        rgba(4, 26, 29, 0.96) 0%,
        rgba(5, 29, 32, 0.92) 42%,
        rgba(5, 34, 36, 0.62) 67%,
        rgba(5, 34, 36, 0.16) 89%,
        rgba(5, 34, 36, 0.00) 100%);
      border: none;
      box-shadow: none;
      border-radius: 0;
    }
    .syn-zap-panel {
      background: transparent;
      border: none;
      box-shadow: none;
      border-radius: 0;
      color: #f5fffa;
    }
    .syn-zap-title { color: #fafffc; font-size: 22px; font-weight: 850; }
    .syn-zap-eyebrow { color: #8ce0cb; font-size: 10px; font-weight: 800; letter-spacing: 1.4px; }
    .syn-zap-subtitle { color: #a9cfc6; font-size: 12px; }
    .syn-zap-search, .syn-zap-category {
      background: rgba(255,255,255,0.09); color: #f9fffd;
      border: 1px solid rgba(255,255,255,0.16); border-radius: 12px;
      min-height: 37px;
    }
    .syn-zap-search text { color: #ffffff; }
    .syn-zap-row {
      background: rgba(255,255,255,0.025); border: 1px solid transparent;
      border-radius: 13px; margin: 3px 2px; padding: 1px;
      color: #f7fffc;
    }
    .syn-zap-row:hover { background: rgba(112, 231, 193, 0.14); }
    .syn-zap-row.syn-zap-playing {
      background: rgba(38, 147, 120, 0.26);
      border-color: rgba(137, 246, 211, 0.56);
    }
    .syn-zap-name { color: #f6fffc; font-weight: 750; font-size: 13px; }
    .syn-zap-group { color: #aacac2; font-size: 11px; }
    .syn-zap-live { background: #36bb92; color: #062923;
      border-radius: 9px; font-size: 10px; font-weight: 900; padding: 3px 6px; }
    .syn-zap-divider { background: rgba(223,255,245,0.12); min-height: 1px; }
    .syn-zap-panel button { color: #f9fffd; border-radius: 10px; }
    .syn-zap-panel button:hover { background: rgba(120,235,206,0.20); }
    .syn-zap-panel checkbutton { color: #e4f6ee; }
    .syn-zap-panel scrollbar slider { background: rgba(192,247,229,0.4); }
    .syn-fs-next { color: #b5dcd0; font-size: 13px;
                   text-shadow: 0 1px 5px rgba(0,0,0,0.55); }
    .syn-fs-volume { border-radius: 12px; padding: 6px 10px;
                     background-color: rgba(4, 30, 33, 0.24); }
    .syn-fs-volume image { color: #f8fffd; }
    .syn-fs-bottom scale { color: #f2fffc; }
    /* SYN 3.7: guía cinematográfica integrada sobre el vídeo. */
    .syn-guide-backdrop {
      background: rgba(3, 13, 20, 0.88); color: #f0f8f7;
    }
    .syn-guide-header { padding: 16px 20px 12px 20px;
      background: rgba(10, 39, 42, 0.74);
      border-bottom: 1px solid rgba(180, 237, 217, .14); }
    .syn-guide-title { color: #f8fffd; font-size: 23px; font-weight: 850; }
    .syn-guide-muted { color: #a8c9c5; font-size: 12px; }
    .syn-epg-launcher { font-weight: 700; }
    .syn-guide-head-button { background: rgba(190,255,234,.11);
      border: 1px solid rgba(190,255,234,.20); border-radius: 11px;
      color: white; min-height: 34px; }
    .syn-guide-categories { background: rgba(6,26,29,0.72);
      border-right: 1px solid rgba(190,255,234,.1); }
    .syn-guide-cat { color: #bcd8d2; border-radius: 10px;
      background: transparent; margin: 2px 5px; padding: 8px 8px; }
    .syn-guide-cat:hover { background: rgba(97,205,176,.14); }
    .syn-guide-cat.active { background: rgba(65,171,143,.30); color: #fff;
      border-left: 3px solid #f3aa73; }
    .syn-guide-channel { background: rgba(10,38,43,.96);
      border: 0; color: #fff; padding: 0;
      box-shadow: inset -1px 0 rgba(153,226,200,.14), inset 0 -1px rgba(11,34,38,.95); }
    .syn-guide-channel-name { color: #fff; font-size: 11px; font-weight: 700; }
    .syn-guide-channel-playing { background: rgba(27,98,81,.8); }
    .syn-guide-axis { background: rgba(8,30,34,.95);
      border-bottom: 1px solid rgba(180, 237, 217, .22); }
    .syn-guide-tick { color: #a6c9c3; font-size: 12px; padding: 8px 12px;
      border-left: 1px solid rgba(180,237,217,.12); }
    .syn-guide-track { background: #091d22; border: 0; padding: 0;
      box-shadow: inset 0 -1px rgba(10,30,32,.9); }
    .syn-guide-program { border: 1px solid rgba(9,31,40,.94);
      border-radius: 9px; color: #fff; padding: 0; margin: 0; }
    .syn-guide-program:hover { border-color: #d4fff2; }
    .syn-guide-program-0 { background: #2b4c50; }
    .syn-guide-program-1 { background: #563f55; }
    .syn-guide-program-2 { background: #3c4a66; }
    .syn-guide-program-3 { background: #534c34; }
    .syn-guide-program-4 { background: #2a5349; }
    .syn-guide-program-5 { background: #544044; }
    .syn-guide-current { border-color: rgba(255,184,123,.92);
      box-shadow: inset 0 0 0 1px rgba(255,184,123,.5); }
    .syn-guide-gap { background: #1b2b34; color: #a1b2b5;
      border-radius: 6px; margin: 0; }
    .syn-guide-time { color: #beded7; font-size: 10px; }
    .syn-guide-program-name { font-size: 12px; font-weight: 650; color: white; }
    .syn-guide-now-line { background: rgba(255,174,106,.94); min-width: 2px; }
    .syn-guide-footer { padding: 10px 18px; background: rgba(9,35,39,.91);
      color: #a4cbc2; border-top: 1px solid rgba(204,255,236,.13); }
    .syn-guide-search { background: rgba(212,255,240,.10);
      border-radius: 11px; color: white; }
    /* SYN 3.2: bienvenida deliberadamente independiente del tema del sistema. */
    .syn-welcome-bg {
      background-image: linear-gradient(132deg, #071d20 0%, #11534e 50%, #1b8173 100%);
      color: #f6fffd;
    }
    .syn-welcome-kicker { color: #abf2d9; font-size: 12px; font-weight: 800; letter-spacing: 1.8px; }
    .syn-welcome-title { color: #ffffff; font-size: 33px; font-weight: 900; }
    .syn-welcome-subtitle { color: #d5f0e8; font-size: 15px; }
    .syn-welcome-card {
      background-color: rgba(3, 22, 24, .48); border: 1px solid rgba(194, 245, 228, .32);
      border-radius: 17px; padding: 17px; color: #fff;
      box-shadow: 0px 3px 12px rgba(0,0,0,.10);
    }
    .syn-welcome-card:hover, .syn-welcome-card:focus {
      background-color: rgba(16, 78, 72, .85);
      border-color: #ffb870;
    }
    .syn-welcome-card-title { color: #fff; font-size: 17px; font-weight: 800; }
    .syn-welcome-card-subtitle { color: #c5e4d9; font-size: 12px; }
    .syn-welcome-symbol { color: #ffbe81; }
    .syn-welcome-hero { background: transparent; }
    .syn-welcome-body { background-color: #102b2a; color: #f4fffb; }
    .syn-welcome-body label { color: #f3fcfa; }
    .syn-welcome-body entry, .syn-welcome-body passwordentry {
      background-color: #1d4944; color: #fff; border-radius: 11px; min-height: 38px;
    }
    .syn-welcome-cta { background-color: #f5ac71; color: #162c28;
      font-weight: 800; border-radius: 12px; min-height: 42px; }
    .syn-welcome-cta:hover { background-color: #ffca99; }
    .syn-welcome-muted { color: #b3d6cc; font-size: 12px; }
    .syn-brand-logo { margin-right: 8px; }
    .syn-logo-pill { min-height: 36px; border-radius: 11px;
       border: 1px solid rgba(255,255,255,.15); padding: 2px 5px; }
    window.iptv-tv .syn-logo-pill.syn-art-fullbleed {
        padding: 0; border: 0; min-height: 0; min-width: 0;
        border-radius: 11px;
    }
    .syn-logo-fallback { font-size: 10px; font-weight: 850; }
    .syn-channel-display-name { font-size: 12px; font-weight: 600; opacity: .84; }
    .syn-favorite-display-name { font-size: 11px; font-weight: 650; opacity: .82; }
    .syn-unified-channel-row { min-height: 0; }
    .syn-channel-logo-picture { margin: 0; padding: 0; background: transparent; border: none; box-shadow: none; }
    .syn-favorite-heart { opacity: .83; padding: 0; margin: 0;
      min-width: 0; min-height: 0; background: transparent; }
    .syn-favorite-heart:hover { opacity: 1; }
    .syn-favorite-display-name { font-size: 11px; font-weight: 600; opacity: .78; }
    .syn-row-heart { padding: 2px; min-width: 28px; min-height: 28px; }


/* SYN 1.3.5c / CARTELERA C – system theme follows GTK4/libadwaita. */
window.iptv-tv .syn-portal-root { background-color: @window_bg_color; color: @window_fg_color; }
window.iptv-tv .syn-portal-top {
  background-color: alpha(@card_bg_color, .80);
  border-bottom: 1px solid alpha(@window_fg_color, .12);
  padding: 18px 26px;
}
window.iptv-tv .syn-portal-kicker { color: @accent_color; font-weight: 900; letter-spacing: 2px; }
window.iptv-tv .syn-portal-title { font-weight: 900; font-size: 28px; }
window.iptv-tv button.syn-portal-poster-card {
  background-color: alpha(@card_bg_color, .87);
  border: 1px solid alpha(@window_fg_color, .13);
  border-radius: 16px; padding: 7px;
  box-shadow: 0 3px 12px alpha(black,.13);
}
window.iptv-tv button.syn-portal-poster-card:hover {
  border-color: @accent_color; background-color: alpha(@accent_color,.12);
  box-shadow: 0 9px 20px alpha(black,.20);
}
window.iptv-tv .syn-portal-poster {border-radius: 11px; border: none;}
window.iptv-tv .syn-portal-art-kicker { color: rgba(255,255,255,.94); font-size: 10px; letter-spacing: 1.4px; font-weight: 850; }
window.iptv-tv .syn-portal-art-name { color: #fff; font-weight: 900; font-size: 17px; text-shadow: 0 2px 7px rgba(0,0,0,.47); }
window.iptv-tv .syn-portal-art-line { background-color: #ffab69; border-radius: 4px; }
window.iptv-tv button.syn-portal-more { border-radius: 32px; min-height: 42px; padding: 8px 24px; }

/* SYN 1.3.5c: poster grid fixes; preserve host GTK theme in Sistema. */
window.iptv-tv .syn-portal-void { font-size: 44px; font-weight: 900; opacity: .45; margin-bottom: 6px; }
window.iptv-tv flowbox.syn-portal-gallery { padding: 12px 0; }
window.iptv-tv button.syn-portal-poster-card { min-width: 170px; min-height: 290px; transition: border-color 180ms ease, background-color 180ms ease; }
window.iptv-tv .syn-portal-poster-name { font-weight: 770; }

"""

    # Paletas exclusivas: no depender de un CSS oscuro ya cargado por el host.
    # El fondo del vídeo y los scrims de fullscreen permanecen cinematográficos.
    FAVORITE_GEOMETRY_CSS = """
    window.iptv-tv button.syn-dvr-rec,
    window.iptv-tv button.syn-dvr-action-record,
    window.iptv-tv button.syn-dvr-rec:hover,
    window.iptv-tv button.syn-dvr-action-record:hover {
      background-color: #d82e46; background-image: none;
      color: #ffffff; border-color: #a91c32;
      box-shadow: none; font-weight: 800;
    }
    window.iptv-tv button.syn-dvr-rec.syn-dvr-recording {
      background-color: #f01835; border: 2px solid #ffffff;
    }
    window.iptv-tv label.syn-dvr-indicator {
      color: #f33e58; font-weight: 900; font-size: 12px;
    }
    @keyframes syn-guide-arrive {
      from { opacity: .68; }
      to { opacity: 1; }
    }
    window.iptv-tv .syn-guide-program.syn-guide-soft-arrival {
      animation: syn-guide-arrive 170ms ease-out 1;
    }
    window.iptv-tv .syn-guide-program {
      transition: background-color 160ms ease, border-color 160ms ease;
    }
    window.iptv-tv row.syn-unified-channel-row { min-height: 0; padding: 0; }
    window.iptv-tv picture.syn-channel-logo-picture {
      min-width: 0; min-height: 0; margin: 0; padding: 0;
      background: transparent; border: none; box-shadow: none;
    }
    /* Dedicated 40px hit area; the text and the scrollbar never share it. */
    window.iptv-tv button.syn-favorite-heart {
      min-width: 40px; min-height: 40px;
      padding: 0; margin: 0;
      border: 0; border-radius: 12px;
      background: transparent; background-image: none;
      color: #b8ceca; font-size: 24px; font-weight: 700;
      box-shadow: none;
    }
    window.iptv-tv button.syn-favorite-heart:hover {
      background: alpha(#8caeb1, 0.16); color: #f1fffd;
    }
    window.iptv-tv button.syn-favorite-heart.syn-heart-active,
    window.iptv-tv button.syn-favorite-heart.syn-heart-active:hover {
      background: alpha(#ef334b, 0.10); color: #ed334b;
    }
    @keyframes syn-heart-shake {
      0%   { transform: translateX(0px) scale(1); }
      24%  { transform: translateX(-2px) scale(1.18); }
      45%  { transform: translateX(2px) scale(1.10); }
      67%  { transform: translateX(-1px) scale(1.06); }
      100% { transform: translateX(0px) scale(1); }
    }
    window.iptv-tv button.syn-heart-animate {
      animation: syn-heart-shake 260ms ease-out 1;
    }
    window.iptv-tv button.syn-heart-filter:checked,
    window.iptv-tv button.syn-favorite-filter:checked,
    window.iptv-tv button.syn-heart-filter:checked:hover,
    window.iptv-tv button.syn-favorite-filter:checked:hover,
    window.iptv-tv label.syn-heart-active,
    window.iptv-tv .syn-guide-cat.active .syn-guide-favorites-heart {
      color: #ed334b;
    }
    """

    LIGHT_CSS = """
    /* CLARO: fondo crema-teal y alto contraste, sin tarjetas oscuras. */
    window.iptv-tv .syn-portal-root {background:#eff9f6;color:#184d45;}
    window.iptv-tv .syn-portal-top {background:#daf3ec;border-color:#b7dcd1;}
    window.iptv-tv .syn-portal-title,window.iptv-tv .syn-portal-hero,
    window.iptv-tv .syn-portal-tile-title {color:#163f39;}
    window.iptv-tv .syn-portal-kicker {color:#197f70;}
    window.iptv-tv button.syn-portal-tile {background-image:linear-gradient(145deg,#ffffff,#e1f4ee);background-color:#f9fffd;border-color:#beded5;color:#184940;box-shadow:0 5px 14px alpha(#38685b,.12);}
    window.iptv-tv button.syn-portal-tile:hover {background-color:#d9f2e8;border-color:#4ea592;}
    window.iptv-tv .syn-portal-orb {background:#d8f3e8;border-color:#52b6a2;}
    window.iptv-tv .syn-portal-orb-icon {color:#238778;}
    window.iptv-tv .syn-portal-orb-series {background:#fff0e2;border-color:#d78b58;}
    window.iptv-tv .syn-portal-orb-series .syn-portal-orb-icon {color:#be7238;}
    window.iptv-tv .syn-portal-orb-movies {background:#eeeaff;border-color:#9b8ac9;}
    window.iptv-tv .syn-portal-orb-movies .syn-portal-orb-icon {color:#7869b4;}
    window.iptv-tv .syn-portal-counter {color:#237c6b;}
    window.iptv-tv button.syn-portal-poster-card {background:#ffffff;color:#17453c;border-color:#d0e8e0;}
    window.iptv-tv button.syn-portal-poster-card:hover {background:#def4ed;border-color:#479b87;}
    window.iptv-tv .syn-portal-poster {background:#dcefe8;}
    window.iptv-tv, window.syn-settings-window, .iptv-surface { background: #eff9f7; color: #194942; }
    .iptv-header { background: #d9f3ed; border-bottom: 1px solid #afdad0; }
    .iptv-heading { color: #124f47; font-weight: 800; }
    .iptv-subtitle, .iptv-info, .iptv-details, .iptv-group { color: #426d68; }
    .iptv-sidebar { background: #e3f5f1; border-right: 1px solid #b9ddd5; }
    .iptv-search, .iptv-dropdown { background: #ffffff; color: #1c5951; border-radius: 12px; }
    .iptv-row { background: #f9fefc; border: 1px solid #d5eae5; border-radius: 11px; margin: 2px 6px; }
    .iptv-row:hover { background: #d3eee7; }
    .iptv-row:selected { background: #a7dcd0; border-color: #3a9a8c; }
    .iptv-channel { color: #19463f; }
    .iptv-toolbar { background: #e4f6f1; border-top: 1px solid #b9ddd5; }
    .iptv-icon { color: #238f80; }
    .iptv-accent { background: #4cb3a4; color: #fff; }
    window.iptv-tv button:not(.iptv-accent), window.syn-settings-window button,
    window.iptv-tv dropdown, window.iptv-tv entry, window.syn-settings-window entry,
    window.syn-settings-window dropdown, window.iptv-tv searchentry {
      background: #f6fffc; color: #185149; border: 1px solid #afdad0; border-radius: 10px;
    }
    window.iptv-tv button:hover, window.syn-settings-window button:hover { background: #d0eee7; }
    window.iptv-tv button.iptv-accent { background: #43a698; color: #fff; }
    window.iptv-tv scale highlight { background-color: #43a698; }
    .syn-logo-pill { color: #123f3d; }
    .syn-guide-backdrop { background: rgba(227,248,243,.96); color: #144941; }
    .syn-guide-header, .syn-guide-axis { background: #d4ede6; border-color: #a9d3c9; }
    .syn-guide-categories { background: #e6f6f1; }
    .syn-guide-channel { background: #d5eee7; color: #1c5249; }
    .syn-guide-channel-playing { background: #9bd1c2; }
    .syn-guide-track { background: #e0f3ee; }
    .syn-guide-cat, .syn-guide-channel-name, .syn-guide-title,
    .syn-guide-time, .syn-guide-muted { color: #18564b; }
    .syn-guide-footer { background: #d4efe7; color: #2a6358; }
    .syn-guide-program { border-color: #b3d7ce; color: #1d4842; }
    .syn-guide-program-0 { background: #d0e6df; }
    .syn-guide-program-1 { background: #ead7e6; }
    .syn-guide-program-2 { background: #d7e3f3; }
    .syn-guide-program-3 { background: #f0e4cb; }
    .syn-guide-program-4 { background: #d0efdd; }
    .syn-guide-program-5 { background: #efd9d7; }
    .syn-guide-program-name { color: #16483f; }
    .syn-guide-gap { background: #ecf8f3; color: #487a70; }
    .syn-guide-current { border-color: #248e7b; }
    .syn-guide-now-line { background: #268f7d; }
    .syn-zap-backdrop { background-image: linear-gradient(to left,rgba(211,241,233,.97),rgba(219,246,240,.92) 55%,transparent 100%); }
    .syn-zap-title, .syn-zap-name, .syn-zap-group,
    .syn-zap-subtitle, .syn-zap-eyebrow { color: #154d44; }
    .syn-zap-row:hover { background: rgba(48,152,128,.13); }
    .syn-zap-row.syn-zap-playing { background: rgba(42,150,129,.22); border-color: #4fac96; }

    /* SYN 3.8.11: el modo Claro debe cubrir todas las capas, no solo la ventana. */
    window.iptv-tv, window.syn-settings-window,
    window.iptv-tv .iptv-surface, window.iptv-tv .iptv-list,
    window.iptv-tv listbox, window.iptv-tv scrolledwindow,
    window.syn-settings-window scrolledwindow {
      color: #184b43;
    }
    window.iptv-tv .iptv-list { background: #e3f5f1; }
    window.iptv-tv .iptv-row label, window.iptv-tv .iptv-channel,
    window.iptv-tv .syn-channel-display-name,
    window.iptv-tv .syn-favorite-display-name { color: #164940; }
    window.iptv-tv .iptv-row:selected label { color: #124d42; }
    window.iptv-tv .iptv-info, window.iptv-tv .iptv-details,
    window.iptv-tv .iptv-group { color: #47756c; }
    window.iptv-tv button.iptv-accent label { color: #ffffff; }
    window.iptv-tv .syn-epg-launcher,
    window.iptv-tv .syn-guide-head-button,
    window.iptv-tv .syn-guide-cat {
      background: #def3ed; color: #22574d;
      border: 1px solid #badfd5;
    }
    window.iptv-tv .syn-guide-head-button:hover,
    window.iptv-tv .syn-guide-cat:hover { background: #bde8db; }
    window.iptv-tv .syn-guide-cat.active {
      background: #a6dccc; color: #185145; border-left: 3px solid #278f7e;
    }
    window.iptv-tv .syn-guide-backdrop,
    window.iptv-tv .syn-guide-categories,
    window.iptv-tv .syn-guide-header,
    window.iptv-tv .syn-guide-axis,
    window.iptv-tv .syn-guide-track,
    window.iptv-tv .syn-guide-channel,
    window.iptv-tv .syn-guide-footer { color: #194d43; }
    window.iptv-tv .syn-guide-track { background: #e3f3ee; }
    window.iptv-tv .syn-guide-channel { border-color: #c1ded7; }
    window.iptv-tv .syn-guide-search,
    window.iptv-tv .syn-zap-search,
    window.iptv-tv .syn-zap-category {
      background: #f8fffd; color: #194f45;
      border: 1px solid #b8dcd2;
    }
    window.iptv-tv .syn-guide-search text,
    window.iptv-tv .syn-zap-search text { color: #194f45; }
    window.iptv-tv .syn-guide-program-name,
    window.iptv-tv .syn-guide-time { color: #174c42; }
    window.iptv-tv .syn-zap-panel { color: #194d43; }
    window.iptv-tv .syn-zap-row {
      background: rgba(244,255,250,.55); color: #194d43;
      border-color: rgba(69,148,130,.13);
    }
    window.iptv-tv .syn-zap-name,
    window.iptv-tv .syn-zap-group,
    window.iptv-tv .syn-zap-eyebrow,
    window.iptv-tv .syn-zap-title,
    window.iptv-tv .syn-zap-subtitle { color: #174f45; }
    window.iptv-tv .syn-zap-panel button,
    window.iptv-tv .syn-zap-panel checkbutton {
      color: #20584c; background: rgba(248,255,252,.42);
    }
    window.iptv-tv .syn-zap-panel button:hover { background: rgba(164,224,206,.80); }
    window.iptv-tv .syn-zap-live { background: #38a995; color: #fff; }
    window.iptv-tv .syn-zap-panel scrollbar slider,
    window.iptv-tv .syn-guide-backdrop scrollbar slider { background: #80baad; }
    window.iptv-tv .syn-fs-top button {
      background: rgba(230,250,244,.76); color: #164c43;
      border-color: rgba(20,110,91,.40);
    }
    window.iptv-tv .syn-fs-top button:hover { background: #cbf0e4; }
    window.iptv-tv .syn-fs-volume {
      background: rgba(225,247,239,.78); color: #185148;
    }
    window.iptv-tv .syn-fs-volume image { color: #185148; }
    window.iptv-tv .syn-fs-channel, window.iptv-tv .syn-fs-epg,
    window.iptv-tv .syn-fs-next { color: #ffffff; }
    /* La legibilidad del título sobre el vídeo se mantiene mediante scrim. */
    window.iptv-tv .syn-fs-scrim-bottom {
      background-image: linear-gradient(to top,
        rgba(9,38,34,.87) 0%, rgba(9,38,34,.45) 50%, transparent 100%);
    }
    /* Bienvenida y formularios también respetan el tema pastel. */
    window.iptv-tv .syn-welcome-bg {
      background-image: linear-gradient(132deg, #e9faf4 0%, #d7f1e9 55%, #b7e5d8 100%);
      color: #164b41;
    }
    window.iptv-tv .syn-welcome-kicker,
    window.iptv-tv .syn-welcome-title,
    window.iptv-tv .syn-welcome-subtitle,
    window.iptv-tv .syn-welcome-card-title,
    window.iptv-tv .syn-welcome-card-subtitle,
    window.iptv-tv .syn-welcome-muted { color: #1e554a; }
    window.iptv-tv .syn-welcome-card {
      background: rgba(252,255,253,.76); color: #174b40;
      border-color: #9fcfbe;
    }
    window.iptv-tv .syn-welcome-card:hover { background: #c6eddf; border-color: #4da895; }
    window.iptv-tv .syn-welcome-body { background: #e6f7f1; color: #164b41; }
    window.iptv-tv .syn-welcome-body label { color: #164b41; }
    window.iptv-tv .syn-welcome-body entry,
    window.iptv-tv .syn-welcome-body passwordentry {
      background: #f9fffc; color: #194d43; border-color: #b1dbcf;
    }
    window.iptv-tv .syn-welcome-cta { background: #4bae9c; color: #fff; }

    /* SYN 3.8.12: los Gtk.DropDown tienen un popover separado con su propia
       superficie, contenidos y filas. El CSS de window.syn-settings-window
       no garantiza colorear ese popup, especialmente con CSS GTK4 oscuro
       del anfitrión. Estas reglas SOLO se cargan en el modo Claro. */
    dropdown > button,
    dropdown > button > box,
    dropdown > button label,
    dropdown > button arrow {
      color: #164d43;
    }
    dropdown > button {
      background: #f8fffc;
      color: #164d43;
      border: 1px solid #acd9cd;
      border-radius: 10px;
    }
    dropdown > button:hover { background: #e1f6ee; }

    /* El popover puede dibujarse en otra superficie nativa de Wayland.
       No depender de que herede window.syn-settings-window. */
    popover.background { color: #154a40; }
    popover.background > contents {
      background: #f8fffc;
      color: #154a40;
      border: 1px solid #a4d2c5;
      border-radius: 10px;
      box-shadow: 0 5px 18px rgba(18, 76, 65, 0.13);
    }
    popover.background listview,
    popover.background scrolledwindow {
      background: #f8fffc;
      color: #154a40;
    }
    popover.background listview row {
      background: #f8fffc;
      color: #154a40;
    }
    popover.background listview row:hover,
    popover.background listview row:focus {
      background: #d4efe6;
      color: #123f36;
    }
    popover.background listview row:selected,
    popover.background listview row:selected:hover {
      background: #a9dfd0;
      color: #103f36;
    }
    popover.background listview row label,
    popover.background listview row image {
      color: #154a40;
    }
    popover.background listview row:hover label,
    popover.background listview row:focus label,
    popover.background listview row:selected label,
    popover.background listview row:selected:hover label {
      color: #103f36;
    }
    popover.background scrollbar slider { background: #80b7a9; }
    popover.background entry,
    popover.background searchentry {
      background: #ffffff;
      color: #154a40;
      border: 1px solid #a4d2c5;
    }
    popover.background entry text,
    popover.background searchentry text { color: #154a40; }


/* SYN Light: porcelain/soft teal with proper dark contrast. */
window.iptv-tv .syn-portal-root {background:#eaf7f3; color:#173e37;}
window.iptv-tv .syn-portal-top {background:#d8eee7; border-bottom:1px solid #a6d2c5;}
window.iptv-tv .syn-portal-kicker {color:#247d70;}
window.iptv-tv .syn-portal-title {color:#17443c;}
window.iptv-tv button.syn-portal-poster-card {background:#ffffff; border-color:#bddfd3; color:#19473d;}
window.iptv-tv button.syn-portal-poster-card:hover {background:#f3fffb; border-color:#299b84;}
window.iptv-tv .syn-portal-poster-name {color:#153d35;}
window.iptv-tv .syn-portal-poster-group {color:#527f73;}

/* SYN 1.3.5c: poster grid fixes; preserve host GTK theme in Sistema. */
window.iptv-tv .syn-portal-void { font-size: 44px; font-weight: 900; opacity: .45; margin-bottom: 6px; }
window.iptv-tv flowbox.syn-portal-gallery { padding: 12px 0; }
window.iptv-tv button.syn-portal-poster-card { min-width: 170px; min-height: 290px; transition: border-color 180ms ease, background-color 180ms ease; }
window.iptv-tv .syn-portal-poster-name { font-weight: 770; }

"""
    DARK_CSS = """
    /* OSCURO: gris antracita neutro, sin forzar la paleta petróleo. */
    window.iptv-tv .syn-portal-root {background:#17191d;color:#f5f5f6;}
    window.iptv-tv .syn-portal-top {background:#22252a;border-color:#373b41;}
    window.iptv-tv .syn-portal-title,window.iptv-tv .syn-portal-hero,
    window.iptv-tv .syn-portal-tile-title {color:#f5f5f6;}
    window.iptv-tv .syn-portal-kicker {color:#f2ab73;}
    window.iptv-tv button.syn-portal-tile {background-image:linear-gradient(145deg,#2d3035,#1d2024);background-color:#25272c;border-color:#42454b;color:#f4f4f6;}
    window.iptv-tv button.syn-portal-tile:hover {background-color:#32363c;border-color:#f2b177;}
    window.iptv-tv .syn-portal-orb {background:#273e40;border-color:#5aaba5;}
    window.iptv-tv .syn-portal-orb-icon {color:#8bd8cd;}
    window.iptv-tv .syn-portal-orb-series {background:#4a352d;border-color:#df9a6f;}
    window.iptv-tv .syn-portal-orb-series .syn-portal-orb-icon {color:#efb285;}
    window.iptv-tv .syn-portal-orb-movies {background:#333044;border-color:#9383c3;}
    window.iptv-tv .syn-portal-orb-movies .syn-portal-orb-icon {color:#c5b7ef;}
    window.iptv-tv .syn-portal-counter {color:#e6a66f;}
    window.iptv-tv button.syn-portal-poster-card {background:#26282d;color:#f6f6f7;border-color:#414349;}
    window.iptv-tv button.syn-portal-poster-card:hover {background:#35383d;border-color:#efb078;}
    window.iptv-tv .syn-portal-poster {background:#33363b;}
    /* SYN 1.0: paleta grafito coherente; nunca heredar contraste del tema GTK anfitrión.
       Este proveedor SOLO se carga en el modo dark, no en Sistema, Claro o Teal. */
    window.iptv-tv, window.syn-settings-window, window.iptv-tv .iptv-surface {
      background: #111316; color: #edf0f4;
    }
    .iptv-header { background: #1a1c21; color: #f2f3f7;
      border-bottom: 1px solid #333841; }
    .iptv-heading, .iptv-channel { color: #f3f4f8; }
    .iptv-subtitle, .iptv-info, .iptv-details, .iptv-group { color: #b2b8c3; }
    .iptv-sidebar { background: #171a20; border-right: 1px solid #353a43; }
    .iptv-search, .iptv-dropdown { background: #262a32; color: #f3f4f8; }
    .iptv-row { background: #22262d; border: 1px solid #343a44;
      border-radius: 10px; margin: 2px 6px; }
    .iptv-row:hover { background: #343944; }
    .iptv-row:selected { background: #3e4654; border-color: #a6adba; }
    .iptv-toolbar { background: #191c23; border-top: 1px solid #333841; }
    .iptv-icon { color: #d0d5df; }
    .iptv-accent { background: #d0d6df; color: #17191f; }

    /* Inputs, switches, spinbuttons, check/radio y controles de las dos ventanas. */
    window.iptv-tv button:not(.iptv-accent), window.syn-settings-window button,
    window.iptv-tv dropdown, window.iptv-tv entry,
    window.syn-settings-window entry, window.syn-settings-window dropdown,
    window.iptv-tv searchentry, window.syn-settings-window searchentry,
    window.syn-settings-window passwordentry, window.syn-settings-window spinbutton {
      background: #292d35; color: #edf0f5;
      border: 1px solid #505663; border-radius: 10px;
    }
    window.iptv-tv button:hover, window.syn-settings-window button:hover {
      background: #404652; color: #ffffff;
    }
    window.iptv-tv button:active, window.syn-settings-window button:active {
      background: #505765; color: #ffffff;
    }
    window.iptv-tv button:disabled, window.syn-settings-window button:disabled {
      color: #969eae; background: #22262c; border-color: #393e47;
    }
    window.iptv-tv button.iptv-accent,
    window.syn-settings-window button.suggested-action {
      background: #cdd4dd; color: #171a20; border-color: #cdd4dd;
    }
    window.iptv-tv button.iptv-accent label,
    window.syn-settings-window button.suggested-action label { color: #171a20; }
    window.iptv-tv scale highlight { background-color: #c4cbd7; }
    window.syn-settings-window label, window.syn-settings-window .iptv-heading {
      color: #eef1f5;
    }
    window.syn-settings-window .iptv-details { color: #bbc1ca; }
    window.syn-settings-window entry text, window.syn-settings-window passwordentry text,
    window.iptv-tv entry text, window.iptv-tv searchentry text { color: #f4f6fa; }
    window.syn-settings-window entry selection, window.iptv-tv entry selection {
      background-color: #6e7c91; color: #ffffff;
    }
    window.iptv-tv scrollbar slider,
    window.syn-settings-window scrollbar slider { background: #666e7d; }
    window.iptv-tv scrollbar slider:hover,
    window.syn-settings-window scrollbar slider:hover { background: #a0a9b7; }
    window.iptv-tv separator, window.syn-settings-window separator {
      background: #414651; color: #414651;
    }
    window.iptv-tv .iptv-list, window.iptv-tv listbox,
    window.iptv-tv scrolledwindow, window.syn-settings-window scrolledwindow {
      color: #eef1f5;
    }
    window.iptv-tv .iptv-list { background: #171a20; }
    window.iptv-tv .iptv-row label, window.iptv-tv .iptv-channel,
    window.iptv-tv .syn-channel-display-name,
    window.iptv-tv .syn-favorite-display-name { color: #e6eaf0; }
    window.iptv-tv .iptv-row:selected label { color: #ffffff; }

    /* Menú desplegable GTK4: se renderiza en popover propio en Wayland.
       Igual que la corrección probada del tema Claro, con valores dark. */
    dropdown > button, dropdown > button > box,
    dropdown > button label, dropdown > button arrow { color: #f1f3f8; }
    dropdown > button {
      background: #292d35; color: #f1f3f8;
      border: 1px solid #505663; border-radius: 10px;
    }
    dropdown > button:hover { background: #404652; color: #ffffff; }
    dropdown > button:disabled { color: #a2a8b2; background: #22262c; }
    popover.background { color: #edf0f5; }
    popover.background > contents {
      background: #252931; color: #edf0f5;
      border: 1px solid #555c68; border-radius: 10px;
      box-shadow: 0 6px 20px rgba(0, 0, 0, .55);
    }
    popover.background listview, popover.background scrolledwindow {
      background: #252931; color: #edf0f5;
    }
    popover.background listview row { background: #252931; color: #edf0f5; }
    popover.background listview row:hover, popover.background listview row:focus {
      background: #3b4350; color: #ffffff;
    }
    popover.background listview row:selected,
    popover.background listview row:selected:hover {
      background: #4d5c70; color: #ffffff;
    }
    popover.background listview row label, popover.background listview row image {
      color: #edf0f5;
    }
    popover.background listview row:hover label,
    popover.background listview row:focus label,
    popover.background listview row:selected label,
    popover.background listview row:selected:hover label { color: #ffffff; }
    popover.background scrollbar slider { background: #7b8595; }
    popover.background entry, popover.background searchentry {
      background: #171b21; color: #f2f4f8; border: 1px solid #566070;
    }
    popover.background entry text, popover.background searchentry text { color: #f2f4f8; }

    /* Guía EPG: encabezados, categorías, filas, búsqueda y hora actual. */
    .syn-guide-backdrop { background: rgba(10,11,15,.95); color: #e8ecf3; }
    .syn-guide-header, .syn-guide-axis {
      background: #1c2027; color: #e8ecf3; border-color: #424957;
    }
    .syn-guide-categories { background: #181c23; color: #e8ecf3; }
    .syn-guide-track { background: #181c23; }
    .syn-guide-channel { background: #20252e; color: #f1f3f7; border-color: #393f48; }
    .syn-guide-channel-playing { background: #404d5c; }
    .syn-guide-cat, .syn-guide-channel-name, .syn-guide-title,
    .syn-guide-time, .syn-guide-muted { color: #e1e6ef; }
    .syn-guide-cat { background: #242a33; border-color: #444a55; }
    .syn-guide-cat:hover { background: #3a4250; }
    .syn-guide-cat.active { background: #475467; color: #ffffff;
      border-left: 3px solid #cdd5df; }
    .syn-guide-head-button, .syn-epg-launcher {
      background: #303641; color: #f0f3f8; border: 1px solid #505966;
    }
    .syn-guide-head-button:hover { background: #465061; }
    .syn-guide-footer { background: #1d222b; color: #bac5d3; border-color: #404855; }
    .syn-guide-program { border-color: #1c222b; color: #f4f5f8; }
    .syn-guide-program-0 { background: #343941; }
    .syn-guide-program-1 { background: #45404b; }
    .syn-guide-program-2 { background: #394557; }
    .syn-guide-program-3 { background: #4c4338; }
    .syn-guide-program-4 { background: #354c46; }
    .syn-guide-program-5 { background: #493c43; }
    .syn-guide-program-name { color: #f1f3f8; }
    .syn-guide-gap { background: #202630; color: #aab3c2; }
    .syn-guide-current { border-color: #d7dee8; }
    .syn-guide-now-line { background: #dee4ee; }
    .syn-guide-search, .syn-zap-search, .syn-zap-category {
      background: #272e39; color: #f2f4f8; border: 1px solid #515c6a;
    }
    .syn-guide-search text, .syn-zap-search text { color: #f2f4f8; }
    .syn-guide-backdrop scrollbar slider { background: #7b8595; }

    /* Zapping y fullscreen: controles legibles sin cambiar el vídeo ni scrims. */
    .syn-zap-backdrop { background-image: linear-gradient(to left,
      rgba(12,15,20,.98),rgba(15,18,24,.89) 52%,transparent 100%); }
    .syn-zap-panel { color: #e9edf4; }
    .syn-zap-eyebrow, .syn-zap-subtitle { color: #bac4d2; }
    .syn-zap-title, .syn-zap-name, .syn-zap-group { color: #f0f3f8; }
    .syn-zap-row { background: rgba(46,54,67,.62); color: #edf0f4;
      border-color: rgba(128,141,162,.20); }
    .syn-zap-row:hover { background: #373f4d; }
    .syn-zap-row.syn-zap-playing { background: #4d5a6f; border-color: #bfcbdc; }
    .syn-zap-live { background: #cbd3df; color: #161a22; }
    .syn-zap-panel button, .syn-zap-panel checkbutton {
      background: rgba(47,54,67,.75); color: #edf0f5;
    }
    .syn-zap-panel button:hover { background: #515c6e; }
    .syn-zap-panel scrollbar slider { background: #8994a3; }
    .syn-fs-top button {
      background: rgba(33,39,49,.86); color: #f1f3f8;
      border: 1px solid rgba(209,217,229,.45);
    }
    .syn-fs-top button:hover { background: rgba(72,82,99,.93); }
    .syn-fs-volume { background: rgba(34,40,49,.84); color: #f0f3f8; }
    .syn-fs-volume image { color: #f0f3f8; }
    .syn-fs-channel, .syn-fs-epg, .syn-fs-next { color: #ffffff; }

    /* Primer arranque y configuración, incluyendo todos los campos. */
    .syn-welcome-bg { background-image: linear-gradient(132deg,
      #11161d 0%, #242d37 52%, #354152 100%); color: #eff2f6; }
    .syn-welcome-kicker, .syn-welcome-title,
    .syn-welcome-subtitle, .syn-welcome-muted { color: #e3e9f1; }
    .syn-welcome-card { background: rgba(35,43,54,.82); color: #edf0f5;
      border: 1px solid #5b6676; }
    .syn-welcome-card:hover { background: #394657; border-color: #cbd4df; }
    .syn-welcome-card-title { color: #ffffff; }
    .syn-welcome-card-subtitle { color: #c5cedb; }
    .syn-welcome-symbol { color: #d6dce5; }
    .syn-welcome-body { background: #1c232c; color: #eff2f7; }
    .syn-welcome-body label { color: #e8ebf1; }
    .syn-welcome-body entry, .syn-welcome-body passwordentry {
      background: #2b343f; color: #f0f2f7; border: 1px solid #566171;
    }
    .syn-welcome-cta { background: #cbd4df; color: #171b21; }
    .syn-welcome-cta:hover { background: #e1e5ee; }

/* SYN Dark: graphite, no forced teal wash. */
window.iptv-tv .syn-portal-root {background:#191b21; color:#f7f7fa;}
window.iptv-tv .syn-portal-top {background:#22252b; border-bottom:1px solid #44464c;}
window.iptv-tv .syn-portal-kicker {color:#e7ae80;}
window.iptv-tv .syn-portal-title {color:#f7f7fa;}
window.iptv-tv button.syn-portal-poster-card {background:#292c31; border-color:#4b4d54; color:#f7f7fa;}
window.iptv-tv button.syn-portal-poster-card:hover {background:#34373f; border-color:#efb47e;}
window.iptv-tv .syn-portal-poster-name {color:#f5f5f7;}
window.iptv-tv .syn-portal-poster-group {color:#bdc0ca;}

/* SYN 1.3.5c: poster grid fixes; preserve host GTK theme in Sistema. */
window.iptv-tv .syn-portal-void { font-size: 44px; font-weight: 900; opacity: .45; margin-bottom: 6px; }
window.iptv-tv flowbox.syn-portal-gallery { padding: 12px 0; }
window.iptv-tv button.syn-portal-poster-card { min-width: 170px; min-height: 290px; transition: border-color 180ms ease, background-color 180ms ease; }
window.iptv-tv .syn-portal-poster-name { font-weight: 770; }

"""

    # SYN_DVR_FOUR_THEMES_127: paletas aisladas para la pantalla DVR.
    # Sistema no inventa colores: utiliza @window_* y @card_* de GTK/libadwaita.
    # Los otros tres modos heredan las decisiones de color del resto de SYN.
    DVR_PALETTES = {
        'system': {
            'bg':'@window_bg_color', 'fg':'@window_fg_color',
            'card':'@card_bg_color', 'muted':'alpha(@window_fg_color, .70)',
            'stroke':'alpha(@window_fg_color, .18)',
            'button':'@card_bg_color', 'hover':'alpha(@window_fg_color, .12)',
            'accent':'@accent_bg_color', 'accent_fg':'@accent_fg_color',
            'selected':'alpha(@accent_bg_color, .20)',
            'selected_fg':'@window_fg_color',
            'scroll':'alpha(@window_fg_color, .36)',
            'error':'#d04755',
        },
        'teal': {
            'bg':'#0b2522', 'fg':'#f1faf6',
            'card':'#173b35', 'muted':'#b2d1c6',
            'stroke':'#3b7063', 'button':'#1d4a42',
            'hover':'#286457', 'accent':'#f0a269',
            'accent_fg':'#172a25', 'selected':'#31675a',
            'selected_fg':'#fafffc', 'scroll':'#508d7c',
            'error':'#ff9aa8',
        },
        'light': {
            'bg':'#eff9f7', 'fg':'#194942',
            'card':'#fafffc', 'muted':'#4a7069',
            'stroke':'#b9ddd5', 'button':'#f6fffc',
            'hover':'#d0eee7', 'accent':'#43a698',
            'accent_fg':'#ffffff', 'selected':'#b8e7da',
            'selected_fg':'#174b41', 'scroll':'#83bcaf',
            'error':'#ae3649',
        },
        'dark': {
            'bg':'#111316', 'fg':'#edf0f4',
            'card':'#22262d', 'muted':'#bcc3ce',
            'stroke':'#424956', 'button':'#292d35',
            'hover':'#404652', 'accent':'#cdd4dd',
            'accent_fg':'#171a20', 'selected':'#4d5869',
            'selected_fg':'#ffffff', 'scroll':'#747f90',
            'error':'#ff9eaa',
        },
    }

    def dvr_palette_css(which):
        """Genera CSS GTK4 a partir de la paleta, sin alterar estilos ajenos."""
        p = DVR_PALETTES[which]
        css = r"""
        window.iptv-tv .syn-dvr-page {
          background-color: %%BG%%; color: %%FG%%;
        }
        window.iptv-tv .syn-dvr-page label,
        window.iptv-tv .syn-dvr-page .heading {
          color: %%FG%%;
        }
        window.iptv-tv .syn-dvr-page .dim-label {
          color: %%MUTED%%;
        }
        window.iptv-tv .syn-dvr-page .error {
          color: %%ERROR%%;
        }
        /* Recuadro de grabaciones, listas GTK4 y scrollbar. */
        window.iptv-tv .syn-dvr-page list.boxed-list {
          background-color: %%CARD%%; color: %%FG%%;
          border: 1px solid %%STROKE%%; border-radius: 11px;
        }
        window.iptv-tv .syn-dvr-page list.boxed-list > row {
          background-color: transparent; color: %%FG%%;
          border-bottom: 1px solid %%STROKE%%;
        }
        window.iptv-tv .syn-dvr-page list.boxed-list > row:last-child {
          border-bottom: 0;
        }
        window.iptv-tv .syn-dvr-page list.boxed-list > row:hover {
          background-color: %%HOVER%%;
        }
        window.iptv-tv .syn-dvr-page list.boxed-list > row label { color: %%FG%%; }
        window.iptv-tv .syn-dvr-page list.boxed-list > row .dim-label { color: %%MUTED%%; }
        window.iptv-tv .syn-dvr-page scrolledwindow,
        window.iptv-tv .syn-dvr-page viewport {
          color: %%FG%%; background-color: transparent;
        }
        window.iptv-tv .syn-dvr-page scrollbar slider {
          background-color: %%SCROLL%%;
        }
        /* Acciones: botones, campos y selector de canal. */
        window.iptv-tv .syn-dvr-page button,
        window.iptv-tv .syn-dvr-page entry,
        window.iptv-tv .syn-dvr-page dropdown > button {
          background-color: %%BUTTON%%; color: %%FG%%;
          border: 1px solid %%STROKE%%; border-radius: 9px;
        }
        window.iptv-tv .syn-dvr-page button:hover,
        window.iptv-tv .syn-dvr-page dropdown > button:hover {
          background-color: %%HOVER%%; color: %%FG%%;
        }
        window.iptv-tv .syn-dvr-page button label,
        window.iptv-tv .syn-dvr-page dropdown > button label,
        window.iptv-tv .syn-dvr-page entry text { color: %%FG%%; }
        window.iptv-tv .syn-dvr-page entry selection {
          background-color: %%ACCENT%%; color: %%ACCENT_FG%%;
        }
        /* Desplegable del canal: GTK puede crearlo en una superficie propia. */
        dropdown.syn-dvr-channel-picker popover.background > contents {
          background-color: %%CARD%%; color: %%FG%%;
          border: 1px solid %%STROKE%%; border-radius: 10px;
        }
        dropdown.syn-dvr-channel-picker popover listview,
        dropdown.syn-dvr-channel-picker popover scrolledwindow,
        dropdown.syn-dvr-channel-picker popover listview row {
          background-color: %%CARD%%; color: %%FG%%;
        }
        dropdown.syn-dvr-channel-picker popover listview row:hover,
        dropdown.syn-dvr-channel-picker popover listview row:focus {
          background-color: %%HOVER%%; color: %%FG%%;
        }
        dropdown.syn-dvr-channel-picker popover listview row:selected {
          background-color: %%SELECTED%%; color: %%SELECTED_FG%%;
        }
        dropdown.syn-dvr-channel-picker popover listview row label {
          color: %%FG%%;
        }
        dropdown.syn-dvr-channel-picker popover listview row:selected label {
          color: %%SELECTED_FG%%;
        }
        window.iptv-tv .syn-dvr-page button:disabled,
        window.iptv-tv .syn-dvr-page dropdown:disabled { opacity: .52; }
        /* Calendario: GtkCalendar no hereda correctamente el primer plano
           del GtkBox con algunos estilos de GTK4 instalados en el host. */
        window.iptv-tv .syn-dvr-page calendar.view {
          background-color: %%CARD%%; color: %%FG%%;
          border: 1px solid %%STROKE%%; border-radius: 11px;
        }
        window.iptv-tv .syn-dvr-page calendar header,
        window.iptv-tv .syn-dvr-page calendar grid {
          background-color: transparent; color: %%FG%%;
        }
        window.iptv-tv .syn-dvr-page calendar header label,
        window.iptv-tv .syn-dvr-page calendar grid label {
          color: %%FG%%;
        }
        window.iptv-tv .syn-dvr-page calendar grid label.day-name,
        window.iptv-tv .syn-dvr-page calendar grid label.other-month {
          color: %%MUTED%%;
        }
        window.iptv-tv .syn-dvr-page calendar grid label.today:not(:selected) {
          box-shadow: inset 0 0 0 1px %%ACCENT%%;
          border-radius: 7px;
        }
        window.iptv-tv .syn-dvr-page calendar grid label:selected {
          background-color: %%ACCENT%%; color: %%ACCENT_FG%%;
          border-radius: 7px;
        }
        window.iptv-tv .syn-dvr-page calendar header button {
          background-color: %%BUTTON%%; color: %%FG%%;
          border-color: %%STROKE%%;
        }
        /* El botón de programar es la acción principal de esta pantalla. */
        window.iptv-tv .syn-dvr-page button.syn-dvr-schedule-action {
          background-color: %%ACCENT%%; color: %%ACCENT_FG%%;
          border-color: %%ACCENT%%;
        }
        window.iptv-tv .syn-dvr-page button.syn-dvr-schedule-action label {
          color: %%ACCENT_FG%%;
        }
        window.iptv-tv .syn-dvr-page button.syn-dvr-schedule-action:hover {
          background-color: %%ACCENT%%; opacity: .88;
        }
        """
        for key, value in p.items():
            css = css.replace('%%' + key.upper() + '%%', value)
        if '%%' in css:
            raise ValueError('Marcador CSS DVR sin reemplazar: ' + which)
        return css

    def brand_icon(size=36):
        """SYN app icon at the exact requested size, including the standalone DMG."""
        if sys.platform == 'darwin':
            # macOS bundles the real PNG at Contents/Resources/source/branding.
            # Never fall back to a missing Linux hicolor icon in the welcome.
            art = Path(__file__).resolve().parent / 'branding' / 'icono_3.png'
            if art.is_file():
                try:
                    pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        str(art), int(size), int(size), True)
                    image = Gtk.Image.new_from_pixbuf(pix)
                    image.set_halign(Gtk.Align.CENTER)
                    image.set_valign(Gtk.Align.CENTER)
                    image.set_size_request(size, size)
                    return image
                except (GLib.Error, OSError):
                    pass
            # If damaged or missing, show the wordmark instead of a broken icon.
            placeholder = Gtk.Label(label='SYN')
            placeholder.add_css_class('syn-welcome-kicker')
            placeholder.set_size_request(size, size)
            return placeholder
        pixel = 32 if size <= 40 else (128 if size <= 150 else 256)
        relative = f'icons/hicolor/{pixel}x{pixel}/apps/{APP_ID}.png'
        paths = [
            Path('/app/share') / relative,
            Path('/usr/share/icons/hicolor') / f'{pixel}x{pixel}/apps/{APP_ID}.png',
            Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / relative,
            Path(__file__).resolve().parent / f'icons/{pixel}x{pixel}/apps/{APP_ID}.png',
        ]
        for path in paths:
            if path.is_file():
                picture = Gtk.Picture.new_for_filename(str(path))
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)
                picture.set_size_request(size, size)
                picture.set_valign(Gtk.Align.CENTER)
                picture.set_halign(Gtk.Align.CENTER)
                return picture
        icon = Gtk.Image.new_from_icon_name(APP_ID)
        icon.set_pixel_size(size)
        return icon

    def welcome_symbol(kind, size=37):
        """Independent of icon packs; inherits the active welcome CSS ink."""
        area = Gtk.DrawingArea()
        area.set_content_width(size)
        area.set_content_height(size)
        area.set_size_request(size, size)
        area.set_can_target(False)
        area.add_css_class('syn-welcome-symbol')

        def paint(widget, cr, width, height):
            if min(width, height) <= 0:
                return
            # GTK4 uses CSS foreground color, so light/dark/custom themes work.
            ink = (widget.get_color() if hasattr(widget, 'get_color')
                   else widget.get_style_context().get_color())
            cr.save()
            try:
                cr.translate((width - min(width, height))/2,
                             (height - min(width, height))/2)
                cr.scale(min(width, height)/37.0, min(width, height)/37.0)
                cr.set_source_rgba(ink.red, ink.green, ink.blue, ink.alpha)
                cr.set_line_width(2.5)
                cr.set_line_cap(1)
                cr.set_line_join(1)
                if kind == 'file':
                    # A folded document with two playlist lines.
                    cr.move_to(10, 4); cr.line_to(23, 4)
                    cr.line_to(29, 10); cr.line_to(29, 32)
                    cr.line_to(10, 32); cr.close_path(); cr.stroke()
                    cr.move_to(23, 4); cr.line_to(23, 10); cr.line_to(29, 10); cr.stroke()
                    for y in (17, 23, 29):
                        cr.move_to(15, y); cr.line_to(24, y); cr.stroke()
                elif kind == 'url':
                    # Two interconnected links; no system icon required.
                    cr.save()
                    cr.translate(18.5, 18.5); cr.rotate(-0.785398)
                    for y in (-7, 7):
                        cr.new_sub_path(); cr.arc(-4, y-3, 4, 3.14159, 4.71239)
                        cr.arc(4, y-3, 4, 4.71239, 6.28319)
                        cr.arc(4, y+3, 4, 0, 1.5708)
                        cr.arc(-4, y+3, 4, 1.5708, 3.14159)
                        cr.close_path(); cr.stroke()
                    cr.restore()
                elif kind == 'xtream':
                    # Server with a connected streaming signal.
                    cr.move_to(7, 13); cr.line_to(7, 29)
                    cr.line_to(26, 29); cr.line_to(26, 13)
                    cr.close_path(); cr.stroke()
                    cr.move_to(12, 20); cr.line_to(17, 20); cr.stroke()
                    cr.arc(22, 20, 1.2, 0, 6.28318); cr.fill()
                    cr.arc(30, 9, 4, 3.45, 5.99); cr.stroke()
                    cr.arc(30, 9, 8, 3.45, 5.99); cr.stroke()
                elif kind == 'next':
                    cr.move_to(13, 9); cr.line_to(24, 18.5)
                    cr.line_to(13, 28); cr.stroke()
                elif kind == 'back':
                    cr.move_to(24, 9); cr.line_to(13, 18.5)
                    cr.line_to(24, 28); cr.stroke()
            finally:
                cr.restore()
        area.set_draw_func(paint)
        return area

    class MpvArea(Gtk.GLArea):
        def __init__(self):
            super().__init__()
            self.set_hexpand(True)
            self.set_vexpand(True)
            self.set_auto_render(False)
            self.add_css_class("iptv-video")
            if hasattr(self, "set_allowed_apis"):
                self.set_allowed_apis(Gdk.GLAPI.GL)
            self.player = None
            self.problem = ""
            self._resize_redraw_pending = False
            self._resize_quiet_until = 0.0
            self._last_size = (0, 0)
            self._resize_timer = 0
            self.set_focusable(True)
            self.connect("realize", self.on_realize)
            self.connect("render", self.on_render)
            self.connect("resize", self.on_resize)
            self.connect("unrealize", self.on_unrealize)

        def on_realize(self, *_):
            self.make_current()
            if self.get_error() is not None:
                self.problem = "GTK no pudo inicializar OpenGL en esta VM."
                return
            try:
                self.player = NativeMpv(GLib, player_options=self.get_root().player_options if self.get_root() else {})
                self.player.initialize_opengl(self.queue_render)
                def notify_ready():
                    if self.get_root():
                        self.get_root().player_ready()
                    return False
                GLib.idle_add(notify_ready)
            except Exception as exc:
                self.problem = str(exc)
                if self.player:
                    if self.player.ctx.value:
                        self.player.free_renderer()
                    self.player.shutdown()
                    self.player = None
                def notify_error():
                    if self.get_root():
                        self.get_root().player_failed(self.problem)
                    return False
                GLib.idle_add(notify_error)

        def on_render(self, _area, _context):
            # Gtk.GLArea activa su propio contexto GL para este callback.
            factor = self.get_scale_factor()
            width = self.get_width() * factor
            height = self.get_height() * factor
            if width < 2 or height < 2:
                return True

            # Durante un redimensionamiento GTK puede reasignar el FBO decenas
            # de veces por segundo. No entregamos FBOs transitorios a libmpv;
            # eso evita reconfiguraciones de GPU/fences mientras Wayland cambia
            # la geometría. Se muestra negro hasta estabilizar el tamaño.
            now = time.monotonic()
            if now < self._resize_quiet_until:
                if self.player and self.player._libGL:
                    self.player._libGL.glClearColor(0.0, 0.0, 0.0, 1.0)
                    self.player._libGL.glClear(0x00004000)  # GL_COLOR_BUFFER_BIT
                return True
            if self.player and self.player.ctx.value:
                self.player.render(width, height)
            return True

        def on_resize(self, _area, _width, _height):
            # Una sola petición de redibujado TRAS 160ms sin cambios de tamaño.
            # Nunca recrear el contexto OpenGL, ni renderizar mientras oscila.
            size = (_width, _height)
            if size == self._last_size:
                return
            self._last_size = size
            self._resize_quiet_until = time.monotonic() + 0.160
            if not self._resize_timer:
                self._resize_timer = GLib.timeout_add(180, self._after_resize)

        def _after_resize(self):
            remaining = self._resize_quiet_until - time.monotonic()
            if remaining > 0:
                return True  # reintentar cuando deje de cambiar el tamaño
            self._resize_timer = 0
            if self.get_realized():
                self.queue_render()
            return False

        def on_unrealize(self, *_):
            if self._resize_timer:
                GLib.source_remove(self._resize_timer)
                self._resize_timer = 0
            if self.player:
                self.make_current()
                self.player.free_renderer()
                self.player.shutdown()
                self.player = None

    class IPTVWindow(Adw.ApplicationWindow):
        def __init__(self, app):
            super().__init__(application=app, title=APP_TITLE, default_width=1280, default_height=776)
            self.add_css_class("iptv-tv")
            self.playlist = playlist
            self.cfg = sources.load_config()
            # No inventar listas ni perfiles en el primer inicio. Hasta guardar
            # una fuente válida, el perfil es solo un marcador EN MEMORIA.
            self._needs_welcome = not bool(self.cfg['profiles'])
            self._welcome_window = None
            if self._needs_welcome:
                self.profile = sources.default_profile(None)
                self.profile.update(name=tr('Sin configurar'), source='')
                self.cfg['profiles'] = [self.profile]
                self.cfg['selected'] = self.profile['id']
            else:
                self.profile = next((p for p in self.cfg['profiles'] if p.get('id') == self.cfg.get('selected')), self.cfg['profiles'][0])
            self.player_options = dict(self.cfg.get('player', {}))
            self.favorites = set(self.profile.get('favorites', []))
            self.settings = {'favorites': list(self.favorites)}
            self.guide, self.epg_aliases = {}, {}
            self._source_generation = 0
            self._logo_pool = (DaemonWorkerPool(max_workers=4, thread_name_prefix='syn-logo')
                               if sys.platform == 'darwin' else
                               ThreadPoolExecutor(max_workers=4, thread_name_prefix='syn-logo'))
            self._logo_requested = set()
            self.channels = []
            self.filtered = []
            self.category_names = ["Todas las categorías"]
            self.current = None
            self._instant_recording_id = None
            self._dvr_playing_file = False
            self._dvr_return_channel = None
            self.dvr_store = syn_dvr.DVRStore()
            self._syn_ts_session = None
            self._syn_ts_poll_id = 0
            self._syn_ts_seek_debounce = 0
            self._syn_ts_ready = False
            self._syn_ts_loading = False
            self._syn_ts_offset = 0.0
            self._syn_ts_ui_guard = False
            self._syn_ts_snapshot_mode = False
            self._syn_ts_snapshot_length = 0.0
            self._syn_ts_snapshot_started = 0.0
            # Enable worker + tray on first GUI launch (never block GTK).
            syn_service_setup.ensure_services_async()
            self.fullscreen_mode = False
            self._fullscreen_target = None
            self._fullscreen_timeout_id = 0
            self._saved_paned_position = 335
            self.pending_channel = None
            # Diseño adaptable, sin reparentar GLArea ni tocar libmpv.
            self.compact_sidebar = False
            self.compact_controls = False
            self._last_window_width = 0
            self._last_video_width = 0
            # SYN_STARTUP_VIDEO_16_9_ONCE: una única petición de tamaño.
            self._syn_startup_ratio_pending = True
            self._tiny_header = False
            self.fs_osd_visible = False
            self.fs_osd_timer = 0
            self.guide_open = False
            self._restore_ui = self.cfg.get('last_ui', {})
            if not isinstance(self._restore_ui, dict):
                self._restore_ui = {}
            self.guide_start = epg_initial_start(dt.datetime.now().astimezone(), lookback_minutes=120)
            self.guide_category_name = syn_favoritos.ALL_CATEGORY
            self.guide_page = 0
            self.guide_search_timer = 0
            self._guide_virtual_first = -1
            self._guide_virtual_total = -1
            self._guide_virtual_timer = 0
            self._guide_rebase_timer = 0
            self._guide_render_busy = False
            self._guide_reset_vertical = True
            self._guide_open_initial = True
            self._guide_center_after_render = False
            self._guide_dragging = False
            self._guide_drag_last = 0.0
            self._guide_drag_until = 0.0
            self._guide_soft_arrival = False

            base = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            base.add_css_class("iptv-surface")
            self.set_content(base)

            self.header = Adw.HeaderBar()
            self.header.add_css_class("iptv-header")
            brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
            # SYN_135D_APP_ICON: icono_3 in the actual header.
            # SYN_135D_R3: bounded 40x28 PNG, Gtk.Picture preserves real rendered size.
            # Beta5: Gtk.Picture con PNG REAL de 46×28; sin Gtk.Image ni tamaño intrínseco gigante.
            syn_brand_icon = Gtk.Picture.new_for_filename(str(Path(__file__).resolve().parent / 'branding' / 'icono_header_ui.png'))
            syn_brand_icon.set_content_fit(Gtk.ContentFit.CONTAIN)
            syn_brand_icon.set_can_shrink(True)
            syn_brand_icon.set_size_request(50, 30)
            brand.append(syn_brand_icon)
            title = Gtk.Label(xalign=0)
            title.set_markup('<b>SYN</b>')
            title.add_css_class("iptv-heading")
            self.header_title = title
            brand.append(title)
            self.header.set_title_widget(brand)
            open_list = Gtk.Button.new_from_icon_name("document-open-symbolic")
            open_list.set_tooltip_text(tr("Abrir una lista M3U"))
            open_list.connect("clicked", self.open_playlist)
            self.header.pack_start(open_list)
            self.profile_picker = Gtk.DropDown.new_from_strings([p['name'] for p in self.cfg['profiles']])
            self.profile_picker.set_tooltip_text(tr('Seleccionar perfil'))
            self.profile_picker.set_selected(self.cfg['profiles'].index(self.profile))
            self.profile_picker.connect('notify::selected', self.change_profile)
            self.header.pack_start(self.profile_picker)
            self.syn_profile_button = Gtk.Button(label='◎  PERFIL')
            self.syn_profile_button.add_css_class('syn-portal-launcher')
            self.syn_profile_button.set_tooltip_text('Tu perfil · TV, SERIES y CINE')
            self.syn_profile_button.connect('clicked', lambda *_: self._syn_portal_show('home'))
            self.header.pack_start(self.syn_profile_button)
            welcome_btn = Gtk.Button.new_from_icon_name('list-add-symbolic')
            welcome_btn.set_tooltip_text(tr('Añadir una fuente IPTV (M3U o Xtream)'))
            welcome_btn.connect('clicked', self.show_welcome)
            self.header.pack_start(welcome_btn)
            logo_btn = Gtk.Button.new_from_icon_name('insert-image-symbolic')
            logo_btn.set_tooltip_text(tr('Personalizar logo del canal seleccionado (PNG/JPG/WebP)'))
            logo_btn.connect('clicked', self.choose_custom_logo)
            self.header.pack_start(logo_btn)
            settings_btn = Gtk.Button.new_from_icon_name('emblem-system-symbolic')
            settings_btn.set_tooltip_text(tr('Ajustes · perfiles, fuentes, MPV y EPG'))
            settings_btn.connect('clicked', self.open_settings)
            self.header.pack_end(settings_btn)
            self.epg_btn = Gtk.Button(label=tr('▦ Guía EPG'))
            self.epg_btn.set_tooltip_text(tr('Abrir la guía visual de programación (G)'))
            self.epg_btn.add_css_class('syn-epg-launcher')
            self.epg_btn.connect('clicked', self.show_guide)
            self.header.pack_end(self.epg_btn)
            self.dvr_nav_button = Gtk.Button(label='DVR')
            self.dvr_nav_button.set_tooltip_text(tr('Calendario, programación y grabaciones'))
            self.dvr_nav_button.connect('clicked', self.toggle_dvr_view)
            self.header.pack_end(self.dvr_nav_button)
            self.dvr_recording_indicator = Gtk.Label(label='● REC')
            self.dvr_recording_indicator.add_css_class('syn-dvr-indicator')
            self.dvr_recording_indicator.set_tooltip_text(tr('SYN DVR está grabando en segundo plano'))
            self.dvr_recording_indicator.set_visible(False)
            self.header.pack_end(self.dvr_recording_indicator)
            # El selector compacto tiene su propia lista; así la barra lateral
            # puede ocultarse SIN desplazar/reparentar el renderizador OpenGL.
            self.channel_menu = Gtk.MenuButton(label=tr("☰ Canales"))
            self.channel_menu.set_tooltip_text(tr("Mostrar canales y buscar emisoras"))
            self.channel_menu.set_visible(False)
            self.header.pack_start(self.channel_menu)
            self.build_compact_channel_menu()
            refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
            refresh.connect("clicked", lambda *_: self.load_channels())
            refresh.set_tooltip_text(tr("Recargar lista"))
            self.header.pack_end(refresh)
            base.append(self.header)

            self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
            self.paned.set_wide_handle(True)
            self.paned.set_shrink_start_child(False)
            self.paned.set_shrink_end_child(True)
            self.paned.set_position(335)
            # Una lista nunca debe quedar recortada si el usuario arrastra
            # el divisor. Mantener >=280px o mostrar el menú compacto.
            self.paned.connect('notify::position', self._enforce_sidebar_width)
            self.paned.set_vexpand(True)
            # Keep Gtk.GLArea realised while viewing the DVR planner.
            # Gtk.Stack unmapping the player can lose the mpv/GL context.
            self.main_stack = Gtk.Overlay()
            self.main_stack.set_vexpand(True)
            self.main_stack.set_child(self.paned)
            base.append(self.main_stack)
            self._syn_portal_build()

            self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
            self.sidebar.add_css_class("iptv-sidebar")
            self.sidebar.set_size_request(280, -1)
            self.sidebar.set_margin_start(0)
            self.sidebar.set_margin_bottom(0)
            self.paned.set_start_child(self.sidebar)

            # SYN_135D_WORDMARK: branding above the channel search.
            # SYN_135D_R3: bounded 180x65 PNG shown at real size, not 16px icon size.
            # Beta5: logo 194×77 recortado realmente, con aire deliberado alrededor.
            self.syn_wordmark = Gtk.Picture.new_for_filename(str(Path(__file__).resolve().parent / 'branding' / 'logo_dark_ui.png'))
            self.syn_wordmark.set_content_fit(Gtk.ContentFit.CONTAIN)
            self.syn_wordmark.set_can_shrink(True)
            self.syn_wordmark.set_size_request(206, 108)
            self.syn_wordmark.set_halign(Gtk.Align.START)
            self.syn_wordmark.set_valign(Gtk.Align.START)
            self.syn_wordmark.set_margin_start(19)
            self.syn_wordmark.set_margin_top(5)
            # BETA6: altura fija de la zona de marca, independiente de la
            # altura natural de Gtk.Picture y del tamaño de la ventana.
            # No modifica la imagen física 194×77 ni su margen horizontal.
            self.syn_wordmark.set_margin_bottom(0)
            self.syn_wordmark.set_vexpand(False)
            self._syn_brand_band = Gtk.Overlay()
            self._syn_brand_band.set_hexpand(True)
            self._syn_brand_band.set_vexpand(False)
            self._syn_brand_band_spacer = Gtk.Box()
            self._syn_brand_band_spacer.set_size_request(-1, 122)
            self._syn_brand_band.set_child(self._syn_brand_band_spacer)
            self._syn_brand_band.add_overlay(self.syn_wordmark)
            self._syn_brand_band.set_measure_overlay(self.syn_wordmark, False)
            self._syn_brand_band.set_clip_overlay(self.syn_wordmark, True)
            self.sidebar.append(self._syn_brand_band)
            Adw.StyleManager.get_default().connect(
                'notify::dark', lambda *_: self._syn_135d_refresh_wordmark())
            self._syn_135d_refresh_wordmark()

            self.search = Gtk.SearchEntry(placeholder_text=tr("Buscar canales…"))
            self.search.set_margin_start(12)
            self.search.set_margin_end(12)
            self.search.set_margin_top(5)
            self.search.add_css_class("iptv-search")
            self.search.connect("search-changed", lambda *_: self.render_list())
            self.search.connect("activate", lambda *_: self.play_selected())
            self.sidebar.append(self.search)

            filter_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            filter_row.set_margin_start(12)
            filter_row.set_margin_end(12)
            self.sidebar.append(filter_row)
            self.category = Gtk.DropDown.new_from_strings([tr('Todas las categorías') if c == 'Todas las categorías' else c for c in self.category_names])
            self.category.add_css_class("iptv-dropdown")
            self.category.set_hexpand(True)
            self.category.connect("notify::selected", lambda *_: (self.render_list(), self._syn_sync_visible_guide_scope()))
            filter_row.append(self.category)
            self.favs = Gtk.ToggleButton(label="♡")
            self.favs.add_css_class('syn-heart-filter')
            self.favs.set_tooltip_text(tr("Solo favoritos"))
            self.favs.connect('toggled', lambda btn: (
                btn.set_label('♥' if btn.get_active() else '♡'), self.render_list(), self._syn_sync_visible_guide_scope()))
            filter_row.append(self.favs)
            # Restore the exact filter the user last left open (not just TV/EPG).
            if self._restore_ui.get('favorites') is True:
                self.favs.set_active(True)

            self.scroller = Gtk.ScrolledWindow()
            self.scroller.set_vexpand(True)
            self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            self.sidebar.append(self.scroller)
            self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, activate_on_single_click=False)
            self.listbox.add_css_class("iptv-list")
            self.listbox.connect("row-activated", lambda _lst, row: self.start_channel(row.channel))
            self.scroller.set_child(self.listbox)
            self.count = Gtk.Label(xalign=0, label="")
            self.count.add_css_class("iptv-info")
            self.count.set_margin_start(15)
            self.count.set_margin_bottom(12)
            self.sidebar.append(self.count)

            video_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            video_column.set_hexpand(True)
            video_column.set_vexpand(True)
            self.paned.set_end_child(video_column)

            self.area = MpvArea()
            self.overlay = Gtk.Overlay()
            self.overlay.set_child(self.area)
            self.overlay.set_hexpand(True)
            self.overlay.set_vexpand(True)
            video_column.append(self.overlay)
            self.blank_label = Gtk.Label(label=tr("▣\n\nSelecciona un canal para empezar"), justify=Gtk.Justification.CENTER)
            self.blank_label.add_css_class("iptv-placeholder")
            self.blank_label.set_halign(Gtk.Align.CENTER)
            self.blank_label.set_valign(Gtk.Align.CENTER)
            self.blank_label.set_can_target(False)
            self.overlay.add_overlay(self.blank_label)
            self._syn_idle_build()
            self._syn_capture_setup()
            self.build_fullscreen_osd()
            self.build_epg_guide()
            self._syn_reconnect_build()
            if self._restore_ui.get('guide') is True:
                GLib.idle_add(self.set_guide_open, True)
            video_click = Gtk.GestureClick.new()
            video_click.set_button(1)
            video_click.connect("released", self.on_video_click)
            self.area.add_controller(video_click)

            details = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            self.details = details
            details.set_margin_start(18)
            details.set_margin_end(18)
            details.set_margin_top(12)
            details.set_margin_bottom(9)
            video_column.append(details)
            self.program_label = Gtk.Label(label=tr('EPG: sin datos'), xalign=0)
            self.program_label.add_css_class('iptv-details')
            self.program_label.set_ellipsize(Pango.EllipsizeMode.END)
            self.program_label.set_margin_start(18)
            self.program_label.set_margin_end(18)
            self.program_label.set_margin_bottom(5)
            video_column.append(self.program_label)
            self.now_playing = Gtk.Label(label=tr("Sin reproducción"), xalign=0)
            self.now_playing.set_hexpand(True)
            self.now_playing.set_ellipsize(Pango.EllipsizeMode.END)
            self.now_playing.add_css_class("iptv-channel")
            details.append(self.now_playing)
            self.resolution = Gtk.Label(label="", xalign=1)
            self.resolution.add_css_class("iptv-details")
            self.resolution.set_ellipsize(Pango.EllipsizeMode.END)
            self.resolution.set_max_width_chars(25)
            details.append(self.resolution)
            self.dvr_back_btn = Gtk.Button(label='↩ Volver al directo')
            self.dvr_back_btn.set_tooltip_text(tr('Regresar al último canal en directo'))
            self.dvr_back_btn.set_visible(False)
            self.dvr_back_btn.connect('clicked', self.dvr_back_to_live)
            details.append(self.dvr_back_btn)

            self.toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
            self.toolbar.add_css_class("iptv-toolbar")
            video_column.append(self.toolbar)
            # Grid permite reorganizar los controles sin forzar un ancho
            # mínimo enorme en el reproductor cuando la ventana es pequeña.
            self.strip = Gtk.Grid()
            self.strip.set_column_spacing(9)
            self.strip.set_row_spacing(6)
            self.strip.set_margin_start(12)
            self.strip.set_margin_end(12)
            self.strip.set_margin_top(9)
            self.strip.set_margin_bottom(9)
            self.toolbar.append(self.strip)
            self.play_button = Gtk.Button(label=tr("▶  Reproducir"))
            self.play_button.add_css_class("iptv-accent")
            self.play_button.connect("clicked", lambda *_: self.play_selected())
            self.pause_button = Gtk.Button(label=tr("⏸ Pausa"))
            self.pause_button.set_sensitive(False)
            self.pause_button.connect("clicked", self.pause)
            stop = Gtk.Button.new_from_icon_name("media-playback-stop-symbolic")
            stop.set_tooltip_text(tr("Detener el canal"))
            stop.connect("clicked", self.stop)
            self.rec_button = Gtk.Button(label='●')
            self.rec_button.add_css_class('syn-dvr-rec')
            self.rec_button.set_size_request(27, 27)
            self.rec_button.set_tooltip_text(tr('Grabar canal actual'))
            self.rec_button.connect('clicked', self.toggle_instant_record)
            self.shot_button = Gtk.Button()
            self.shot_button.set_child(self._syn_capture_icon(on_black=True))
            self.shot_button.set_tooltip_text('Capturar fotograma PNG')
            self.shot_button.connect('clicked', self._syn_capture_take)
            volume_icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic")
            self.volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
            self.volume.set_value(100)
            self.volume.set_size_request(90, -1)
            self.volume.set_draw_value(False)
            self.volume.connect("value-changed", lambda scale: self.area.player.volume(scale.get_value()) if self.area.player else None)
            info = Gtk.Button(label="ⓘ")
            info.set_tooltip_text(tr("Resolución real de la señal"))
            info.connect("clicked", self.show_info)
            full = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic")
            full.set_tooltip_text(tr("Pantalla completa · F"))
            full.connect("clicked", self.toggle_fullscreen)
            self.toolbar_widgets = (self.play_button, self.pause_button, stop,
                                    self.rec_button, self.shot_button, volume_icon,
                                    self.volume, info, full)
            self._arrange_toolbar(compact=False)
            self.cast_button = Gtk.ToggleButton()
            self.cast_button.add_css_class('syn-cast-button')
            self.cast_button.set_child(self._syn_cast_make_icon())
            self._syn_cast_apply_orange_style()
            self.cast_button.set_tooltip_text('Retransmitir por Chromecast')
            self.cast_button.connect('toggled', self._syn_cast_menu)
            self._syn_cast_target_uuid = None
            self._syn_cast_device_name = ''
            self._syn_cast_only = False
            self._syn_cast_busy = False
            self._arrange_toolbar(compact=False)
            GLib.timeout_add(1600, self._syn_cast_restore)
            GLib.timeout_add_seconds(5, self._syn_cast_watch)

            self.footer = Gtk.Label(label=tr("Doble clic en canal para reproducir · Espacio pausa · F pantalla completa · Esc salir de pantalla completa"), xalign=0)
            self.footer.add_css_class("iptv-details")
            self.footer.set_ellipsize(Pango.EllipsizeMode.END)
            self.footer.set_max_width_chars(70)
            self.footer.set_margin_end(16)
            self.footer.set_margin_start(16)
            self.footer.set_margin_top(7)
            self.footer.set_margin_bottom(10)
            video_column.append(self.footer)
            self.status = Gtk.Label(label="", xalign=0)
            self.status.add_css_class("iptv-details")
            self.status.set_ellipsize(Pango.EllipsizeMode.END)
            self.status.set_margin_start(16)
            self.status.set_margin_end(16)
            self.status.set_margin_bottom(10)
            video_column.append(self.status)

            self.build_dvr_page()
            self.main_stack.add_overlay(self.dvr_view)
            self.dvr_view.set_visible(False)
            GLib.timeout_add_seconds(3, self.dvr_refresh)
            GLib.timeout_add_seconds(1, self._syn_follow_dvr)
            GLib.idle_add(lambda: (self.dvr_refresh(force=True), False)[1])
            syn_dvr.ensure_worker()
            GLib.timeout_add_seconds(8, self.dvr_worker_check)

            self._keys = Gtk.EventControllerKey.new()
            self._keys.connect("key-pressed", self.key_press)
            self.add_controller(self._keys)
            self.connect("close-request", self.closing)
            # Wayland aplica fullscreen de forma asíncrona. Escuchamos el
            # estado real, también si GNOME lo cambia desde fuera de la app.
            self.connect("notify::fullscreened", self.fullscreen_changed)
            GLib.timeout_add(1000, self.poll_resolution)
            # GTK4 no emite size-allocate como GTK3. Una comprobación muy
            # ligera de ancho, cada 180ms, evita tocar GLArea/GL mientras
            # Wayland envía varios tamaños durante el arrastre.
            GLib.timeout_add(180, self._check_responsive_layout)
            # SYNPLUS_WORKBENCH: activate the user-approved three-column mockup.
            # All GTK widgets are moved BEFORE the first window presentation.
            synplus_layout.install_synplus_layout(
                self, Gtk, GLib, video_column, base, brand,
                (open_list, welcome_btn, logo_btn, settings_btn, refresh,
                 self.epg_btn, self.dvr_nav_button, self.syn_profile_button))
            if self._needs_welcome:
                self.status.set_text(tr('SYN · Elige una fuente para empezar'))
                self.blank_label.set_text(tr('Bienvenido a SYN\n\nConfigura tu primera lista para empezar'))
                GLib.idle_add(self.show_welcome)
            else:
                self.load_channels()

        # SYN_135D_BRANDING: select the right logo for the actual GTK4 color scheme.
        def _syn_135d_refresh_wordmark(self):
            # The GTK theme manager drives system/light/dark/teal and changes live.
            dark = Adw.StyleManager.get_default().get_dark()
            name = 'logo_light.png' if dark else 'logo_dark.png'
            self.syn_wordmark.set_filename(str(Path(__file__).resolve().parent / 'branding' / ('logo_light_ui.png' if dark else 'logo_dark_ui.png')))

        # SYN_135B_PORTAL: independent navigation surface; video GLArea stays realized.
        def _syn_portal_build(self):
            self._syn_movies = []
            self._syn_series = []
            self._syn_catalog_busy = False
            self._syn_catalog_errors = []
            # Movie covers cannot starve live-TV channel-logo downloads.
            self._syn_poster_pool = (DaemonWorkerPool(max_workers=4, thread_name_prefix='syn-poster')
                                     if sys.platform == 'darwin' else
                                     ThreadPoolExecutor(max_workers=4, thread_name_prefix='syn-poster'))
            self._syn_portal_mode = 'home'
            self._syn_portal_pending_search = 0
            self._syn_portal_items = []
            self._syn_portal_back_to = 'home'
            self._syn_portal_loading_episodes = False
            self._syn_portal = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self._syn_portal.add_css_class('syn-portal-root')
            self._syn_portal.set_hexpand(True)
            self._syn_portal.set_vexpand(True)
            self._syn_portal.set_halign(Gtk.Align.FILL)
            self._syn_portal.set_valign(Gtk.Align.FILL)
            self.main_stack.add_overlay(self._syn_portal)
            self.main_stack.set_clip_overlay(self._syn_portal, True)

            top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
            top.add_css_class('syn-portal-top')
            self._syn_portal_back = Gtk.Button(label='←  TV')
            self._syn_portal_back.add_css_class('syn-portal-back')
            self._syn_portal_back.connect('clicked', self._syn_portal_go_back)
            top.append(self._syn_portal_back)
            heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            heading.set_hexpand(True)
            kicker = Gtk.Label(label='SYN  /  TU BIBLIOTECA', xalign=0)
            kicker.add_css_class('syn-portal-kicker')
            heading.append(kicker)
            self._syn_portal_title = Gtk.Label(label='Tu entretenimiento', xalign=0)
            self._syn_portal_title.add_css_class('syn-portal-title')
            self._syn_portal_title.set_ellipsize(Pango.EllipsizeMode.END)
            heading.append(self._syn_portal_title)
            top.append(heading)
            self._syn_portal_search = Gtk.SearchEntry(placeholder_text=tr('Buscar títulos…'))
            self._syn_portal_search.set_size_request(220, -1)
            self._syn_portal_search.add_css_class('syn-portal-search')
            self._syn_portal_search.connect('search-changed', self._syn_portal_search_changed)
            self._syn_portal_search.set_visible(False)
            top.append(self._syn_portal_search)
            self._syn_portal.append(top)

            self._syn_portal_stack = Gtk.Stack()
            self._syn_portal_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            self._syn_portal_stack.set_transition_duration(230)
            self._syn_portal_stack.set_hexpand(True)
            self._syn_portal_stack.set_vexpand(True)
            self._syn_portal.append(self._syn_portal_stack)

            home_scroll = Gtk.ScrolledWindow()
            home_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            home = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=25)
            home.set_valign(Gtk.Align.CENTER)
            home.set_halign(Gtk.Align.CENTER)
            home.set_hexpand(True)
            home.set_margin_start(22)
            home.set_margin_end(22)
            home.set_margin_top(35)
            home.set_margin_bottom(36)
            label = Gtk.Label(label=tr('¿Qué te apetece ver?'))
            label.add_css_class('syn-portal-hero')
            home.append(label)
            subtitle = Gtk.Label(label='Todo tu contenido, en un solo lugar')
            subtitle.add_css_class('syn-portal-subtitle')
            home.append(subtitle)
            tiles = Gtk.FlowBox()
            tiles.set_halign(Gtk.Align.CENTER)
            tiles.set_selection_mode(Gtk.SelectionMode.NONE)
            tiles.set_homogeneous(True)
            tiles.set_max_children_per_line(3)
            tiles.set_min_children_per_line(1)
            tiles.set_column_spacing(20)
            tiles.set_row_spacing(20)
            home.append(tiles)
            self._syn_portal_counters = {}
            for kind, title, icon, text in (
                    ('tv', 'TV', '▣', 'Canales en directo'),
                    ('series', 'SERIES', '▥', 'Tus historias favoritas'),
                    ('movies', 'CINE', '◉', 'Una película para cada momento')):
                button = Gtk.Button()
                button.add_css_class('syn-portal-tile')
                button.add_css_class('syn-portal-tile-' + kind)
                button.set_size_request(210, 275)
                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11)
                content.set_halign(Gtk.Align.CENTER)
                content.set_valign(Gtk.Align.CENTER)
                circle = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                circle.add_css_class('syn-portal-orb')
                circle.add_css_class('syn-portal-orb-' + kind)
                circle.set_halign(Gtk.Align.CENTER)
                circle.set_valign(Gtk.Align.CENTER)
                circle.set_size_request(102, 102)
                symbol = Gtk.DrawingArea()
                symbol.set_content_width(68)
                symbol.set_content_height(68)
                symbol.set_halign(Gtk.Align.CENTER)
                symbol.set_valign(Gtk.Align.CENTER)
                symbol.set_vexpand(True)
                symbol.set_draw_func(lambda area, cr, width, height, item=kind:
                                     self._syn_portal_draw_icon(cr, width, height, item))
                circle.append(symbol)
                content.append(circle)
                main_label = Gtk.Label(label=title)
                main_label.add_css_class('syn-portal-tile-title')
                content.append(main_label)
                counter = Gtk.Label(label='—')
                counter.add_css_class('syn-portal-counter')
                content.append(counter)
                self._syn_portal_counters[kind] = counter
                foot = Gtk.Label(label=text)
                foot.add_css_class('syn-portal-tile-foot')
                content.append(foot)
                button.set_child(content)
                button.connect('clicked', lambda _btn, target=kind: self._syn_portal_open(target))
                tiles.append(button)
            note = Gtk.Label(label=tr('Selecciona una categoría para explorar tu contenido'))
            note.add_css_class('syn-portal-subtitle')
            home.append(note)
            home_scroll.set_child(home)
            self._syn_portal_stack.add_named(home_scroll, 'home')

            gallery_scroll = Gtk.ScrolledWindow()
            gallery_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            self._syn_portal_gallery = Gtk.FlowBox()
            self._syn_portal_gallery.set_selection_mode(Gtk.SelectionMode.NONE)
            self._syn_portal_gallery.set_homogeneous(True)
            self._syn_portal_gallery.set_halign(Gtk.Align.CENTER)
            self._syn_portal_gallery.set_valign(Gtk.Align.START)
            self._syn_portal_gallery.set_max_children_per_line(7)
            self._syn_portal_gallery.set_min_children_per_line(1)
            self._syn_portal_gallery.set_column_spacing(20)
            self._syn_portal_gallery.set_row_spacing(20)
            self._syn_portal_gallery.set_margin_top(24)
            self._syn_portal_gallery.set_margin_bottom(24)
            self._syn_portal_gallery.set_margin_start(18)
            self._syn_portal_gallery.set_margin_end(18)
            # The footer is OUTSIDE FlowBox: it cannot stretch a single column.
            self._syn_portal_gallery_scroll = gallery_scroll
            self._syn_portal_visible_limit = 48
            gallery_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            gallery_container.set_hexpand(True)
            gallery_container.append(self._syn_portal_gallery)
            self._syn_portal_more = Gtk.Button(label=tr('Ver más títulos'))
            self._syn_portal_more.add_css_class('syn-portal-more')
            self._syn_portal_more.set_halign(Gtk.Align.CENTER)
            self._syn_portal_more.set_margin_top(8)
            self._syn_portal_more.set_margin_bottom(24)
            self._syn_portal_more.connect('clicked', self._syn_portal_load_more)
            gallery_container.append(self._syn_portal_more)
            gallery_scroll.set_child(gallery_container)
            self._syn_portal_stack.add_named(gallery_scroll, 'gallery')
            self._syn_portal_update_counters()
            self._syn_portal.set_visible(False)

        def _syn_portal_draw_icon(self, cr, width, height, kind):
            # Three original vector emblems, crisp under any GTK/Wayland scale.
            theme = self.cfg.get('theme', 'system')
            light = theme == 'light' or (theme == 'system' and not Adw.StyleManager.get_default().get_dark())
            colors = {'tv': (0.12, 0.53, 0.46) if light else (0.61, 0.96, 0.85),
                      'series': (0.68, 0.35, 0.18) if light else (1.0, 0.72, 0.46),
                      'movies': (0.40, 0.32, 0.68) if light else (0.77, 0.71, 1.0)}
            r, g, b = colors.get(kind, colors['tv'])
            cr.save()
            cr.scale(max(1, width) / 100.0, max(1, height) / 100.0)
            cr.set_source_rgb(r, g, b)
            cr.set_line_width(4.2)
            cr.set_line_join(1)
            cr.set_line_cap(1)
            if kind == 'tv':
                cr.rectangle(13, 26, 74, 48); cr.stroke()
                cr.move_to(41, 75); cr.line_to(41, 84); cr.line_to(59, 84); cr.line_to(59, 75); cr.stroke()
                cr.move_to(23, 18); cr.line_to(34, 25); cr.move_to(77, 18); cr.line_to(66, 25); cr.stroke()
                cr.arc(75, 62, 3, 0, 6.283); cr.fill()
            elif kind == 'series':
                cr.rectangle(26, 18, 57, 60); cr.stroke()
                cr.rectangle(16, 27, 57, 58); cr.stroke()
                cr.move_to(30, 41); cr.line_to(61, 41); cr.move_to(30, 52); cr.line_to(56, 52); cr.stroke()
                cr.move_to(34, 66); cr.line_to(44, 60); cr.line_to(44, 73); cr.close_path(); cr.fill()
            else:
                cr.arc(50, 50, 33, 0, 6.283); cr.stroke()
                cr.arc(50, 50, 7, 0, 6.283); cr.stroke()
                import math
                for i in range(5):
                    angle = i * (2 * math.pi / 5) - math.pi / 2
                    cr.arc(50 + 20 * math.cos(angle), 50 + 20 * math.sin(angle), 5, 0, 6.283)
                    cr.fill()
                cr.move_to(75, 73); cr.line_to(89, 85); cr.stroke()
            cr.restore()

        def _syn_portal_update_counters(self):
            if not hasattr(self, '_syn_portal_counters'):
                return
            self._syn_portal_counters['tv'].set_text(f'{len(self.channels):,}'.replace(',', '.') + ' canales')
            if self._syn_catalog_busy:
                self._syn_portal_counters['movies'].set_text('Cargando…')
                self._syn_portal_counters['series'].set_text('Cargando…')
            else:
                self._syn_portal_counters['movies'].set_text(
                    'No disponible' if 'movies' in self._syn_catalog_errors else
                    f'{len(self._syn_movies):,}'.replace(',', '.') + ' películas')
                self._syn_portal_counters['series'].set_text(
                    'No disponible' if 'series' in self._syn_catalog_errors else
                    f'{len(self._syn_series):,}'.replace(',', '.') + ' series')

        def _syn_portal_show(self, mode='home'):
            if self.fullscreen_mode or self.is_fullscreen():
                self.unfullscreen()
            if self.guide_open:
                self.set_guide_open(False)
            if getattr(self, 'dvr_view', None) is not None and self.dvr_view.get_visible():
                self.dvr_view.set_visible(False)
                self.dvr_nav_button.set_label('DVR')
            self._syn_portal.set_visible(True)
            self._syn_portal_open(mode)

        def _syn_portal_hide(self):
            if self._syn_portal.get_visible():
                self._syn_portal.set_visible(False)
                self._syn_portal_search.set_text('')

        def _syn_portal_open(self, mode='home'):
            if mode == 'tv':
                self._syn_portal_hide()
                return
            self._syn_portal_mode = mode
            self._syn_portal_search.set_visible(mode != 'home')
            self._syn_portal_visible_limit = 48
            self._syn_portal_search.set_text('')
            self._syn_portal_title.set_text({'home': 'Tu entretenimiento',
                                             'movies': 'Cine', 'series': 'Series',
                                             'episodes': getattr(self, '_syn_portal_series_name', 'Episodios')}.get(mode, 'Biblioteca'))
            self._syn_portal_back.set_label('←  TV' if mode == 'home' else '←  PERFIL' if mode != 'episodes' else '←  SERIES')
            self._syn_portal_stack.set_visible_child_name('home' if mode == 'home' else 'gallery')
            if mode != 'home':
                self._syn_portal_render_gallery()

        def _syn_portal_go_back(self, *_):
            if self._syn_portal_mode == 'episodes':
                self._syn_portal_open('series')
            elif self._syn_portal_mode == 'home':
                self._syn_portal_hide()
            else:
                self._syn_portal_open('home')

        def _syn_portal_search_changed(self, *_):
            if self._syn_portal_mode != 'home':
                self._syn_portal_visible_limit = 48
                self._syn_portal_render_gallery()

        def _syn_portal_render_gallery(self):
            gallery = self._syn_portal_gallery
            while (child := gallery.get_first_child()) is not None:
                gallery.remove(child)
            mode = self._syn_portal_mode
            if mode == 'movies':
                items = self._syn_movies
            elif mode == 'series':
                items = self._syn_series
            else:
                items = getattr(self, '_syn_portal_episodes', [])
            query = self._syn_portal_search.get_text().strip().casefold()
            if query:
                items = [item for item in items if query in (item['name'] + ' ' + item.get('group', '')).casefold()]
            self._syn_portal_items = items
            if not items:
                self._syn_portal_more.set_visible(False)
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
                box.set_valign(Gtk.Align.CENTER)
                box.set_halign(Gtk.Align.CENTER)
                box.set_margin_top(80)
                emblem = Gtk.Label(label='SYN  /  ∅')
                emblem.add_css_class('syn-portal-void')
                box.append(emblem)
                text = ('Cargando episodios…' if mode == 'episodes' and self._syn_portal_loading_episodes else
                        'Buscando en Xtream…' if self._syn_catalog_busy else
                        'No hay títulos en esta categoría' if not query else 'Sin coincidencias')
                label = Gtk.Label(label=text)
                label.add_css_class('syn-portal-empty')
                box.append(label)
                if mode in self._syn_catalog_errors:
                    msg = Gtk.Label(label=tr('No se pudo consultar el catálogo del servidor. Revisa tu fuente Xtream.'))
                    msg.add_css_class('syn-portal-muted')
                    box.append(msg)
                gallery.append(box)
                return
            # 48 covers are built initially; scroll + "Ver más" load the next batch.
            # Every child is homogeneous, so a title cannot widen one column.
            count = min(len(items), getattr(self, '_syn_portal_visible_limit', 48))
            self._syn_portal_more.set_visible(count < len(items))
            if count < len(items):
                self._syn_portal_more.set_label(tr('Ver más títulos') + f'  ·  {count} ' + tr('de') + f' {len(items)}')
            import hashlib
            for item in items[:count]:
                button = Gtk.Button()
                button.add_css_class('syn-portal-poster-card')
                button.set_size_request(170, 290)
                button.set_hexpand(False)
                button.set_halign(Gtk.Align.CENTER)
                button.set_valign(Gtk.Align.START)
                layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
                layout.set_size_request(148, -1)
                layout.set_hexpand(False)
                layout.set_halign(Gtk.Align.CENTER)
                picframe = Gtk.Overlay()
                picframe.set_size_request(148, 211)
                picframe.set_overflow(Gtk.Overflow.HIDDEN)
                picframe.add_css_class('syn-portal-poster')
                art = Gtk.DrawingArea()
                art.set_size_request(148, 211)
                art.set_content_width(148)
                art.set_content_height(211)
                color_id = hashlib.sha256((item['name'] + '|' + item.get('group', '')).encode('utf-8')).digest()
                art.set_draw_func(lambda _area, cr, w, h, seed=color_id:
                                  self._syn_portal_draw_poster_art(cr, w, h, seed))
                picframe.set_child(art)

                # Designed typographic movie poster. It remains visible when the
                # IPTV provider has no cover, serves >1MiB, or rejects downloads.
                fallback = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                fallback.set_halign(Gtk.Align.FILL)
                fallback.set_valign(Gtk.Align.FILL)
                fallback.set_vexpand(True)
                fallback.set_margin_start(12)
                fallback.set_margin_end(12)
                fallback.set_margin_top(12)
                fallback.set_margin_bottom(16)
                fallback.set_can_target(False)
                caption = Gtk.Label(label='SYN  /  ' + ('SERIES' if mode == 'series' else 'EPISODIO' if mode == 'episodes' else 'CINE'))
                caption.add_css_class('syn-portal-art-kicker')
                caption.set_halign(Gtk.Align.START)
                fallback.append(caption)
                spacer = Gtk.Box()
                spacer.set_vexpand(True)
                fallback.append(spacer)
                # Keep the poster copy brief: unbounded line count is safe
                # inside the fixed frame; Gtk.Label:lines could widen a column.
                art_title = item['name']
                if len(art_title) > 52:
                    art_title = art_title[:51].rstrip() + '…'
                headline = Gtk.Label(label=art_title)
                headline.set_wrap(True)
                headline.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                headline.set_justify(Gtk.Justification.CENTER)
                headline.set_ellipsize(Pango.EllipsizeMode.END)
                headline.set_width_chars(9)
                headline.set_max_width_chars(13)
                headline.set_size_request(122, -1)
                headline.add_css_class('syn-portal-art-name')
                fallback.append(headline)
                separator = Gtk.Box()
                separator.add_css_class('syn-portal-art-line')
                separator.set_halign(Gtk.Align.CENTER)
                separator.set_size_request(28, 3)
                separator.set_margin_top(12)
                fallback.append(separator)
                picframe.add_overlay(fallback)

                image = Gtk.Picture()
                image.set_content_fit(Gtk.ContentFit.COVER)
                image.set_size_request(148, 211)
                image.set_hexpand(True)
                image.set_vexpand(True)
                image.set_halign(Gtk.Align.FILL)
                image.set_valign(Gtk.Align.FILL)
                image.set_visible(False)
                picframe.add_overlay(image)
                layout.append(picframe)
                name = Gtk.Label(label=item['name'])
                name.set_width_chars(1)
                name.set_max_width_chars(17)
                name.set_size_request(148, -1)
                name.set_ellipsize(Pango.EllipsizeMode.END)
                name.set_xalign(0)
                name.set_tooltip_text(item['name'])
                name.add_css_class('syn-portal-poster-name')
                layout.append(name)
                genre = item.get('group', '')
                year = item.get('year', '')
                desc = (year + '  ·  ' if year and year.isdecimal() else '') + genre
                category = Gtk.Label(label=desc)
                category.set_width_chars(1)
                category.set_max_width_chars(17)
                category.set_size_request(148, -1)
                category.set_ellipsize(Pango.EllipsizeMode.END)
                category.set_xalign(0)
                category.add_css_class('syn-portal-poster-group')
                layout.append(category)
                button.set_child(layout)
                button.connect('clicked', lambda _btn, selected=item: self._syn_portal_select(selected))
                gallery.append(button)
                options = item.get('poster_options') or ([item['poster']] if item.get('poster') else [])
                if options:
                    self._syn_portal_load_poster(options, image)

        def _syn_portal_draw_poster_art(self, cr, width, height, seed):
            """Locally drawn cinematic cover when remote art is missing.

            Six tonal moods, each with item-specific position/geometry. No web
            metadata, stock image or fake official movie cover is required.
            """
            palettes = [
                ((.055, .18, .20), (.21, .51, .50), (.94, .60, .35)),
                ((.13, .12, .23), (.45, .30, .62), (.98, .66, .48)),
                ((.12, .20, .26), (.35, .49, .65), (.98, .76, .46)),
                ((.17, .12, .16), (.57, .30, .38), (.97, .66, .45)),
                ((.08, .21, .17), (.25, .46, .37), (.88, .68, .41)),
                ((.16, .17, .26), (.32, .36, .58), (.83, .68, .90)),
            ]
            base, middle, flare = palettes[seed[0] % len(palettes)]
            cr.save()
            cr.scale(max(1, width) / 148.0, max(1, height) / 211.0)
            cr.set_source_rgb(*base)
            cr.paint()
            cr.set_source_rgba(*middle, .48)
            cr.move_to(0, 28)
            cr.line_to(148, 0)
            cr.line_to(148, 102)
            cr.line_to(0, 139)
            cr.close_path()
            cr.fill()
            cx, cy = 42 + seed[1] % 60, 42 + seed[2] % 42
            cr.set_source_rgba(*flare, .31)
            cr.arc(cx, cy, 38 + seed[3] % 30, 0, 6.283185)
            cr.fill()
            cr.set_source_rgba(*flare, .42)
            cr.arc(cx, cy, 22 + seed[4] % 14, 0, 6.283185)
            cr.fill()
            cr.set_source_rgba(1, 1, 1, .17)
            for i in range(12):
                x = 8 + (seed[(i % 20) + 5] * 13 + i * 31) % 134
                y = 11 + (seed[(i % 20) + 7] * 7 + i * 19) % 120
                cr.arc(x, y, .6 + (i % 3) * .3, 0, 6.283185)
                cr.fill()
            # Abstract cut-paper landscape and a small cinematic horizon.
            cr.set_source_rgba(.025, .075, .10, .44)
            cr.move_to(0, 118)
            for i, y in ((26, 110), (59, 125), (93, 98), (123, 113), (148, 105)):
                cr.line_to(i, y + seed[9] % 18)
            cr.line_to(148, 211)
            cr.line_to(0, 211)
            cr.close_path()
            cr.fill()
            cr.set_source_rgba(.015, .045, .08, .50)
            cr.rectangle(0, 143, 148, 68)
            cr.fill()
            cr.set_source_rgba(*flare, .63)
            cr.rectangle(14, 184, 38 + seed[6] % 45, 2)
            cr.fill()
            cr.restore()

        def _syn_portal_load_poster(self, options, picture):
            """Poster-specific 6 MiB loader, nonblocking and quietly cached."""
            ua = sources.metadata_user_agent(self.player_options)
            def worker():
                try:
                    file = syn_poster.get_poster(options, user_agent=ua)
                    if file is None:
                        return
                    def complete():
                        if picture.get_parent() is None:
                            return False
                        try:
                            # GTK4 decodes JPEG/PNG/WebP using the loader available in Flatpak.
                            picture.set_filename(str(file))
                            picture.set_visible(True)
                        except (GLib.Error, OSError, ValueError):
                            pass
                        return False
                    GLib.idle_add(complete)
                except (OSError, ValueError, RuntimeError):
                    pass
            self._syn_poster_pool.submit(worker)

        def _syn_portal_load_more(self, *_):
            self._syn_portal_visible_limit += 48
            scroll = self._syn_portal_gallery_scroll
            old_y = scroll.get_vadjustment().get_value()
            self._syn_portal_render_gallery()
            GLib.idle_add(lambda: (scroll.get_vadjustment().set_value(old_y), False)[1])

        def _syn_portal_select(self, item):
            if item.get('kind') == 'series':
                self._syn_portal_series_name = item['name']
                if 'children' in item:
                    self._syn_portal_episodes = item['children']
                    self._syn_portal_open('episodes')
                    return
                profile = dict(self.profile)
                token = self._source_generation
                target = item.get('id')
                self._syn_portal_episodes = []
                self._syn_portal_loading_episodes = True
                self._syn_portal_open('episodes')
                def worker():
                    try:
                        episodes = syn_catalog.episodes_for_xtream(
                            profile, target, sources.metadata_user_agent(self.player_options))
                        GLib.idle_add(self._syn_portal_episodes_loaded, token, episodes, False)
                    except (OSError, ValueError, KeyError, TypeError):
                        GLib.idle_add(self._syn_portal_episodes_loaded, token, [], True)
                threading.Thread(target=worker, daemon=True, name='syn-episodes').start()
                return
            url = item.get('url')
            if not url:
                return
            ch = Channel(item['name'], item.get('group', 'Cine'), url, item.get('poster', ''))
            self._syn_portal_hide()
            self.start_channel(ch)

        def _syn_portal_episodes_loaded(self, token, episodes, failed):
            if token != self._source_generation:
                return False
            self._syn_portal_episodes = episodes
            self._syn_portal_loading_episodes = False
            if failed:
                self._syn_catalog_errors = list(set(self._syn_catalog_errors + ['episodes']))
            if self._syn_portal_mode == 'episodes' and self._syn_portal.get_visible():
                self._syn_portal_render_gallery()
            return False

        def _syn_portal_catalog_refresh(self):
            self._syn_movies = list(getattr(self, '_syn_local_movies', []))
            self._syn_series = list(getattr(self, '_syn_local_series', []))
            self._syn_catalog_errors = []
            self._syn_catalog_busy = self.profile.get('type') == 'xtream'
            self._syn_portal_update_counters()
            if not self._syn_catalog_busy:
                if self._syn_portal.get_visible() and self._syn_portal_mode != 'home':
                    self._syn_portal_render_gallery()
                return
            token = self._source_generation
            profile = dict(self.profile)
            ua = sources.metadata_user_agent(self.player_options)
            def worker():
                try:
                    movies, series, errs = syn_catalog.load_xtream_catalog(profile, ua)
                except (OSError, ValueError, KeyError, TypeError):
                    movies, series, errs = [], [], ['movies', 'series']
                GLib.idle_add(self._syn_portal_catalog_loaded, token, movies, series, errs)
            threading.Thread(target=worker, daemon=True, name='syn-vod-catalog').start()

        def _syn_portal_catalog_loaded(self, token, movies, series, errs):
            if token != self._source_generation:
                return False
            self._syn_movies = movies
            self._syn_series = series
            self._syn_catalog_errors = errs
            self._syn_catalog_busy = False
            self._syn_portal_update_counters()
            if self._syn_portal.get_visible() and self._syn_portal_mode in ('movies', 'series'):
                self._syn_portal_render_gallery()
            return False

        def build_dvr_page(self):
            """Embedded DVR screen: no modal/pop-up, and no mpv reparenting."""
            self.dvr_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            self.dvr_view.add_css_class('syn-dvr-page')
            self.dvr_view.set_hexpand(True)
            self.dvr_view.set_vexpand(True)
            self.dvr_view.set_halign(Gtk.Align.FILL)
            self.dvr_view.set_valign(Gtk.Align.FILL)
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            back = Gtk.Button(label='← TV')
            back.connect('clicked', self.toggle_dvr_view)
            head.append(back)
            title = Gtk.Label(label=tr('DVR · Grabaciones'), xalign=0)
            title.add_css_class('title-1')
            title.set_hexpand(True)
            head.append(title)
            self.dvr_view.append(head)
            # Open the recording's real folder in the host file manager through
            # the desktop's default handler (Flatpak portal when available).
            open_folder = Gtk.Button.new_from_icon_name('folder-open-symbolic')
            open_folder.set_tooltip_text(tr('Abrir carpeta de grabaciones'))
            open_folder.connect('clicked', lambda *_: self.dvr_open_folder())
            head.append(open_folder)
            choose_folder = Gtk.Button(label=tr('Elegir carpeta…'))
            choose_folder.set_tooltip_text(tr('Cambiar la carpeta donde se guardan las grabaciones'))
            choose_folder.connect('clicked', self.dvr_choose_folder)
            head.append(choose_folder)

            split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
            split.set_vexpand(True)
            split.set_wide_handle(True)
            self.dvr_view.append(split)

            planner_scroll = Gtk.ScrolledWindow()
            planner_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            planner_scroll.set_size_request(335, -1)
            planner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            planner.set_margin_start(8)
            planner.set_margin_end(20)
            planner.set_margin_top(10)
            planner.set_margin_bottom(12)
            planner_scroll.set_child(planner)
            split.set_start_child(planner_scroll)
            split.set_position(370)

            section = Gtk.Label(label=tr('Programar una grabación'), xalign=0)
            section.add_css_class('title-3')
            planner.append(section)
            planner.append(Gtk.Label(label=tr('Fecha'), xalign=0))
            self.dvr_calendar = Gtk.Calendar()
            planner.append(self.dvr_calendar)
            planner.append(Gtk.Label(label=tr('Canal'), xalign=0))
            self.dvr_channel_dropdown = Gtk.DropDown.new_from_strings(['Cargando canales…'])
            self.dvr_channel_dropdown.add_css_class('syn-dvr-channel-picker')
            self.dvr_channel_dropdown.set_enable_search(True)
            planner.append(self.dvr_channel_dropdown)
            planner.append(Gtk.Label(label=tr('Horario (24 h)'), xalign=0))
            times = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            now = dt.datetime.now() + dt.timedelta(minutes=5)
            self.dvr_start_entry = Gtk.Entry()
            self.dvr_start_entry.set_text(now.strftime('%H:%M'))
            self.dvr_start_entry.set_max_length(5)
            self.dvr_start_entry.set_width_chars(6)
            self.dvr_start_entry.set_tooltip_text(tr('Inicio: HH:MM'))
            self.dvr_end_entry = Gtk.Entry()
            self.dvr_end_entry.set_text((now + dt.timedelta(hours=1)).strftime('%H:%M'))
            self.dvr_end_entry.set_max_length(5)
            self.dvr_end_entry.set_width_chars(6)
            self.dvr_end_entry.set_tooltip_text(tr('Fin: HH:MM'))
            times.append(Gtk.Label(label=tr('De')))
            times.append(self.dvr_start_entry)
            times.append(Gtk.Label(label=tr('a')))
            times.append(self.dvr_end_entry)
            planner.append(times)
            planned = Gtk.Button(label=tr('Programar grabación'))
            planned.add_css_class('suggested-action')
            planned.add_css_class('syn-dvr-schedule-action')
            planned.connect('clicked', self.dvr_schedule)
            planner.append(planned)
            instant = Gtk.Button(label=tr('● Grabar canal seleccionado ahora'))
            instant.add_css_class('syn-dvr-action-record')
            instant.connect('clicked', self.dvr_record_selected)
            planner.append(instant)
            planner.append(Gtk.Label(label=tr('Se utiliza FFmpeg sin recodificar y User-Agent VLC.'),
                                     xalign=0, wrap=True))

            library = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            library.set_margin_start(16)
            library.set_margin_end(8)
            library.set_margin_top(10)
            split.set_end_child(library)
            library_title = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            title2 = Gtk.Label(label=tr('Programadas y grabadas'), xalign=0)
            title2.add_css_class('title-3')
            title2.set_hexpand(True)
            library_title.append(title2)
            refresh = Gtk.Button.new_from_icon_name('view-refresh-symbolic')
            refresh.set_tooltip_text(tr('Actualizar grabaciones'))
            refresh.connect('clicked', lambda *_: self.dvr_refresh(force=True))
            library_title.append(refresh)
            library.append(library_title)
            self.dvr_folder_label = Gtk.Label(xalign=0)
            self.dvr_folder_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            library.append(self.dvr_folder_label)
            scroller = Gtk.ScrolledWindow()
            scroller.set_vexpand(True)
            library.append(scroller)
            self.dvr_recording_list = Gtk.ListBox()
            self.dvr_recording_list.set_selection_mode(Gtk.SelectionMode.NONE)
            self.dvr_recording_list.add_css_class('boxed-list')
            scroller.set_child(self.dvr_recording_list)
            self.dvr_feedback = Gtk.Label(label='', xalign=0, wrap=True)
            self.dvr_view.append(self.dvr_feedback)
            self.dvr_service_label = Gtk.Label(label=tr('Servicio DVR: comprobando…'), xalign=0, wrap=True)
            self.dvr_service_label.add_css_class('dim-label')
            self.dvr_view.append(self.dvr_service_label)
            self.dvr_worker_check()  # immediate status on first opening
            self.dvr_refresh(force=True)

        def dvr_open_folder(self, filepath=None):
            # Gtk.FileLauncher utiliza el portal OpenURI en Flatpak. Con un
            # archivo abre su carpeta original; sin él abre el directorio
            # de destino. No requiere ejecutar Nautilus desde el sandbox.
            try:
                if filepath:
                    target = Path(filepath).expanduser()
                    if not target.is_file():
                        raise FileNotFoundError('La grabación ya no está disponible.')
                else:
                    db = self.dvr_store.read()
                    target = Path(db.get('folder') or syn_dvr.video_directory()).expanduser()
                    if not target.is_dir():
                        raise FileNotFoundError('La carpeta de grabaciones todavía no existe.')
                launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(str(target)))
                def finished(task, result):
                    try:
                        if filepath:
                            task.open_containing_folder_finish(result)
                        else:
                            task.launch_finish(result)
                    except GLib.Error as exc:
                        self.dvr_feedback.set_text('No se pudo abrir el gestor de archivos: ' + str(exc))
                if filepath:
                    launcher.open_containing_folder(self, None, finished)
                else:
                    launcher.launch(self, None, finished)
            except (OSError, GLib.Error, ValueError) as exc:
                self.dvr_feedback.set_text('No se pudo abrir la carpeta: ' + str(exc))

        def dvr_choose_folder(self, *_):
            dialog = Gtk.FileDialog(title='Elegir carpeta para grabaciones SYN')
            try:
                stored = Path(self.dvr_store.read().get('folder') or syn_dvr.video_directory())
                if stored.is_dir():
                    dialog.set_initial_folder(Gio.File.new_for_path(str(stored)))
            except (OSError, ValueError):
                pass
            dialog.select_folder(self, None, self.dvr_folder_selected)

        def dvr_folder_selected(self, dialog, result):
            try:
                location = dialog.select_folder_finish(result)
                folder = location.get_path() if location else None
                if not folder:
                    raise ValueError('El portal no ha proporcionado una carpeta local.')
                self.dvr_store.choose_directory(folder)
                self.dvr_refresh(force=True)
                self.dvr_feedback.set_text('Carpeta de grabaciones: ' + folder)
            except GLib.Error as exc:
                if not exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED):
                    self.dvr_feedback.set_text('No se pudo seleccionar la carpeta: ' + str(exc))
            except (OSError, ValueError) as exc:
                self.dvr_feedback.set_text('No se pudo cambiar la carpeta: ' + str(exc))

        def dvr_record_epg_program(self, channel, clipped_start, clipped_end, programme_title):
            # epg_geometry() clips programme times to the visible viewport.
            # Use original programme bounds from XMLTV, not the clipped block.
            programmes = self._guide_programmes_for(channel)
            match = next((p for p in programmes
                          if len(p) >= 3 and p[0] <= clipped_start < p[1]
                          and str(p[2]) == programme_title), None)
            if match is None:
                self.guide_count.set_text('No encuentro el horario original del programa en la EPG.')
                return
            start, end = match[0], match[1]
            now = dt.datetime.now().astimezone()
            if end <= now:
                self.guide_count.set_text('Este programa ya ha terminado y no se puede programar.')
                return
            start = max(start, now)
            try:
                self.dvr_enqueue(channel, start.timestamp(), end.timestamp(), programme=programme_title)
                self.guide_count.set_text('● DVR programado: ' + programme_title + ' · ' +
                                          format_time(start) + '–' + format_time(end))
            except (ValueError, OSError) as exc:
                self.guide_count.set_text('DVR: ' + str(exc))

        def dvr_epg_context_menu(self, target, channel, clipped_start, clipped_end, programme_title):
            # A context popover is appropriate for right-click; DVR main view
            # itself remains embedded, never in a separate window.
            old = getattr(self, '_dvr_epg_popover', None)
            if old:
                old.popdown()
                old.unparent()
            popover = Gtk.Popover()
            popover.set_parent(target)
            popover.set_has_arrow(True)
            popover.set_position(Gtk.PositionType.BOTTOM)
            button = Gtk.Button(label=tr('● Programar grabación'))
            button.add_css_class('syn-dvr-action-record')
            button.set_margin_top(7)
            button.set_margin_bottom(7)
            button.set_margin_start(7)
            button.set_margin_end(7)
            button.connect('clicked', lambda *_: (
                self.dvr_record_epg_program(channel, clipped_start, clipped_end, programme_title),
                popover.popdown()))
            popover.set_child(button)
            self._dvr_epg_popover = popover
            popover.popup()

        def dvr_back_to_live(self, *_):
            live = getattr(self, '_dvr_return_channel', None)
            self._dvr_playing_file = False
            self.dvr_back_btn.set_visible(False)
            if live and syn_dvr.allowed_stream_url(live.url):
                self.start_channel(live)
            else:
                self.stop()

        def dvr_notify_on_exit(self):
            # No persistent notification/badge. Only a transient banner on
            # VERIFIED independent worker status, never the old ambiguous one.
            data = self.dvr_store.read()
            if not syn_dvr.background_worker_confirmed(data):
                return
            recording = sum(j.get('status') == 'running' for j in data.get('jobs', []))
            scheduled = sum(j.get('status') == 'scheduled' for j in data.get('jobs', []))
            if recording:
                syn_dvr.notify_transient(f'{recording} grabación(es) siguen en segundo plano.')
            elif scheduled:
                syn_dvr.notify_transient(f'{scheduled} grabación(es) programadas · servicio DVR activo.')

        def toggle_dvr_view(self, *_):
            self._syn_portal_hide()
            show_dvr = not self.dvr_view.get_visible()
            self.dvr_view.set_visible(show_dvr)
            self.dvr_nav_button.set_label('← TV' if show_dvr else 'DVR')
            if show_dvr:
                self.dvr_refresh(force=True)

        def dvr_update_channels(self):
            if not hasattr(self, 'dvr_channel_dropdown'):
                return
            names = [display_channel_name(ch.name) for ch in self.channels]
            self.dvr_channel_dropdown.set_model(Gtk.StringList.new(names or ['Sin canales']))
            if self.current:
                for i, ch in enumerate(self.channels):
                    if ch.url == self.current.url:
                        self.dvr_channel_dropdown.set_selected(i)
                        break

        def dvr_chosen_channel(self):
            index = self.dvr_channel_dropdown.get_selected()
            if not 0 <= index < len(self.channels):
                raise ValueError('Selecciona un canal de tu lista IPTV.')
            return self.channels[index]

        def dvr_enqueue(self, channel, start=None, end=None, programme=None):
            # Do not stop playback before the independent recorder is ready.
            if not syn_dvr.background_worker_confirmed():
                syn_service_setup.ensure_services_async()
                raise OSError('El grabador DVR está iniciándose o no está disponible. '
                              'Prueba REC de nuevo en unos segundos.')
            # A user recording the currently playing channel must not open TWO
            # IPTV connections, even briefly. Pause live first, then wait for DVR.
            player = self.area.player
            paused = bool(player and self.current and self.current.url == channel.url
                          and player.active_url == channel.url
                          and (start is None or float(start) <= time.time() + 3))
            if paused:
                player.stop()
            try:
                job = self.dvr_store.add(channel.name, channel.url,
                                         time.time() if start is None else start,
                                         end, syn_dvr.VLC_UA, programme=programme,
                                         profile_id=self.profile.get('id'),
                                         max_connections=syn_multistream.profile_limit(self.profile))
            except Exception:
                if paused:
                    player.play(channel)
                raise
            syn_dvr.ensure_worker()
            if getattr(self, '_syn_ts_session', None) and (start is None or float(start) <= time.time() + 3):
                self._syn_ts_stop(restore=False)
            self._syn_enforce_connection_limit()
            self.dvr_refresh(force=True)
            return job

        def dvr_record_selected(self, *_):
            try:
                ch = self.dvr_chosen_channel()
                self.dvr_enqueue(ch)
                self.dvr_feedback.set_text(tr('Grabación inmediata solicitada: ') + display_channel_name(ch.name))
            except (OSError, ValueError) as exc:
                self.dvr_feedback.set_text('DVR: ' + str(exc))

        def dvr_schedule(self, *_):
            try:
                ch = self.dvr_chosen_channel()
                caldate = self.dvr_calendar.get_date()
                datestr = '%04d-%02d-%02d' % (caldate.get_year(), caldate.get_month(), caldate.get_day_of_month())
                start_text = self.dvr_start_entry.get_text().strip()
                end_text = self.dvr_end_entry.get_text().strip()
                start = dt.datetime.strptime(datestr + ' ' + start_text, '%Y-%m-%d %H:%M').astimezone()
                end = dt.datetime.strptime(datestr + ' ' + end_text, '%Y-%m-%d %H:%M').astimezone()
                if end <= start:
                    end += dt.timedelta(days=1)
                self.dvr_enqueue(ch, start.timestamp(), end.timestamp())
                self.dvr_feedback.set_text(tr('Grabación programada: ') +
                                           start.strftime('%d/%m/%Y %H:%M') + ' – ' + end.strftime('%H:%M'))
            except (OSError, ValueError) as exc:
                self.dvr_feedback.set_text('No se pudo programar: ' + str(exc))

        def toggle_instant_record(self, *_):
            if self._instant_recording_id:
                self.dvr_store.stop(self._instant_recording_id)
                self._instant_recording_id = None
                self.rec_button.set_label('●')
                self.rec_button.remove_css_class('syn-dvr-recording')
                self.rec_button.set_tooltip_text(tr('Grabar ahora'))
                self.status.set_text(tr('DVR: deteniendo grabación…'))
                return
            if not self.current:
                self.status.set_text(tr('DVR: reproduce un canal antes de grabar.'))
                return
            try:
                job = self.dvr_enqueue(self.current)
                self._instant_recording_id = job['id']
                self.rec_button.set_label('■')
                self.rec_button.add_css_class('syn-dvr-recording')
                self.rec_button.set_tooltip_text(tr('Detener grabación'))
                self.status.set_text(tr('DVR: grabación solicitada de ') + display_channel_name(self.current.name))
            except (ValueError, OSError) as exc:
                self.status.set_text('DVR: ' + str(exc))

        def dvr_stop_job(self, job_id):
            self.dvr_store.stop(job_id)
            self.dvr_refresh(force=True)

        def dvr_play_file(self, filepath):
            path = Path(filepath)
            if not path.is_file():
                self.dvr_feedback.set_text(tr('El archivo ya no está disponible: ') + path.name)
                return
            self.dvr_view.set_visible(False)
            self.dvr_nav_button.set_label('DVR')
            if not getattr(self, '_dvr_playing_file', False) and self.current and syn_dvr.allowed_stream_url(self.current.url):
                self._dvr_return_channel = self.current
            self._dvr_playing_file = True
            self.dvr_back_btn.set_visible(True)
            self.start_channel(Channel(path.stem, 'Grabaciones', path.resolve().as_uri()))

        def _syn_reattach_rec_button(self, data):
            """Recover the *UI*, never interrupt or launch the background DVR."""
            if not hasattr(self, 'rec_button'):
                return
            active = [j for j in data.get('jobs', [])
                      if isinstance(j, dict) and j.get('end') is None
                      and j.get('status') in ('scheduled', 'running')
                      and not j.get('stop_requested')]
            tracked = next((j for j in active
                            if self.current and j.get('url') == self.current.url
                            and j.get('id') == self._instant_recording_id), None)
            if tracked is None:
                # If multiple recordings are active, do not let the REC button
                # accidentally stop an arbitrary one. Show the library badge.
                tracked = next((j for j in active
                                if self.current and j.get('url') == self.current.url), None)
                self._instant_recording_id = tracked.get('id') if tracked else None
            if tracked:
                self.rec_button.set_label('■')
                self.rec_button.add_css_class('syn-dvr-recording')
                self.rec_button.set_tooltip_text(tr('Detener grabación'))
            else:
                self.rec_button.set_label('●')
                self.rec_button.remove_css_class('syn-dvr-recording')
                self.rec_button.set_tooltip_text(tr('Grabar ahora'))

        def dvr_refresh(self, force=False):
            if not hasattr(self, 'dvr_recording_list'):
                return True
            data = self.dvr_store.read()
            # The recorder lives outside this GTK window. Reattach the GUI's
            # REC button to a still-active, indefinite recording on reopen.
            self._syn_reattach_rec_button(data)
            jobs = sorted(data.get('jobs', []), key=lambda j: j.get('created', 0), reverse=True)[:120]
            files = syn_dvr.recorded_files()
            sig = json.dumps([(j.get('id'), j.get('status'), j.get('stop_requested'),
                                j.get('path'), j.get('programme')) for j in jobs])
            sig += '|' + str(data.get('folder')) + '|' + '|'.join(str(f) for f in files)
            if not force and sig == getattr(self, '_dvr_snapshot', None):
                return True
            self._dvr_snapshot = sig
            self.dvr_folder_label.set_text(tr('Carpeta: ') + str(data.get('folder') or syn_dvr.video_directory()))
            active_count = sum(1 for j in data.get('jobs', []) if j.get('status') == 'running')
            if hasattr(self, 'dvr_recording_indicator'):
                self.dvr_recording_indicator.set_visible(bool(active_count))
                self.dvr_recording_indicator.set_text(f'● REC {active_count}' if active_count > 1 else '● REC')
            box = self.dvr_recording_list
            while row := box.get_first_child():
                box.remove(row)
            statuses = {'scheduled':tr('Programada'), 'running':tr('Grabando'), 'completed':tr('Finalizada'),
                        'failed':'Error', 'cancelled':tr('Cancelada'), 'missed':tr('Perdida'),
                        'interrupted':tr('Interrumpida')}
            seen = set()
            for job in jobs:
                if job.get('path'):
                    seen.add(str(job['path']))
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                row.set_margin_start(8)
                row.set_margin_end(8)
                row.set_margin_top(8)
                row.set_margin_bottom(8)
                desc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                desc.set_hexpand(True)
                name = Gtk.Label(label=(job.get('programme') or display_channel_name(job.get('channel') or 'Canal')), xalign=0)
                name.set_ellipsize(Pango.EllipsizeMode.END)
                desc.append(name)
                start = dt.datetime.fromtimestamp(float(job.get('start', time.time())))
                when = format_day_time(start)
                detail = Gtk.Label(label=(statuses.get(job.get('status'), '?') + ' · ' + when + (' · ' + display_channel_name(job.get('channel') or 'Canal') if job.get('programme') else '')), xalign=0)
                detail.add_css_class('dim-label')
                desc.append(detail)
                if job.get('status') == 'failed' and job.get('error'):
                    info = Gtk.Label(label=str(job['error'])[:130], xalign=0, wrap=True)
                    info.add_css_class('error')
                    desc.append(info)
                row.append(desc)
                if job.get('status') in ('running', 'scheduled'):
                    action = Gtk.Button(label='■' if job['status'] == 'running' else '✕')
                    action.set_tooltip_text('Detener' if job['status'] == 'running' else 'Cancelar')
                    action.connect('clicked', lambda _b, ident=job['id']: self.dvr_stop_job(ident))
                    row.append(action)
                if job.get('path') and Path(job['path']).is_file():
                    action = Gtk.Button(label=tr('▶ Ver'))
                    action.connect('clicked', lambda _b, path=job['path']: self.dvr_play_file(path))
                    row.append(action)
                    open_location = Gtk.Button.new_from_icon_name('folder-open-symbolic')
                    open_location.set_tooltip_text(tr('Abrir ubicación del archivo original'))
                    open_location.connect('clicked', lambda _b, path=job['path']: self.dvr_open_folder(path))
                    row.append(open_location)
                box.append(row)
            for f in files[:120]:
                if str(f) in seen:
                    continue
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row.set_margin_start(8)
                row.set_margin_end(8)
                row.set_margin_top(8)
                row.set_margin_bottom(8)
                label = Gtk.Label(label=f.stem, xalign=0)
                label.set_ellipsize(Pango.EllipsizeMode.END)
                label.set_hexpand(True)
                row.append(label)
                action = Gtk.Button(label=tr('▶ Ver'))
                action.connect('clicked', lambda _b, path=str(f): self.dvr_play_file(path))
                row.append(action)
                open_location = Gtk.Button.new_from_icon_name('folder-open-symbolic')
                open_location.set_tooltip_text(tr('Abrir ubicación del archivo original'))
                open_location.connect('clicked', lambda _b, path=str(f): self.dvr_open_folder(path))
                row.append(open_location)
                box.append(row)
            if not jobs and not files:
                box.append(Gtk.Label(label=tr('Todavía no hay grabaciones.')))
            if self._instant_recording_id:
                tracked = next((j for j in jobs if j.get('id') == self._instant_recording_id), None)
                if tracked and tracked.get('status') in ('failed','cancelled','missed','interrupted','completed'):
                    self._instant_recording_id = None
                    self.rec_button.set_label('●')
                    self.rec_button.remove_css_class('syn-dvr-recording')
            return True
        def dvr_worker_check(self):
            # Visual, continuously checked confirmation, not a notification.
            db = self.dvr_store.read()
            active = syn_dvr.background_worker_confirmed(db)
            if active:
                msg = '● Servicio DVR independiente activo · puedes cerrar SYN'
            else:
                msg = ('⚠ El servicio DVR independiente no está activo. '
                       'Comprueba el servicio macOS con 04_DIAGNOSTICO_DVR.command')
            if hasattr(self, 'dvr_service_label'):
                self.dvr_service_label.set_text(msg)
            return True  # Keep the status current as service starts/stops.

        def show_welcome(self, *_):
            """Asistente de primer inicio, sin importar automáticamente alacarta.m3u."""
            if self._welcome_window:
                self._welcome_window.present()
                return False
            dialog = Gtk.Window(title=tr('Bienvenido a SYN'), transient_for=self,
                                modal=True, default_width=670, default_height=655)
            dialog.add_css_class('synplus-welcome')
            self._welcome_window = dialog
            dialog.connect('close-request', lambda *_: setattr(self, '_welcome_window', None))
            dialog.set_resizable(True)
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            root.add_css_class('syn-welcome-bg')
            dialog.set_child(root)

            # Toda la bienvenida es una sola portada con dos páginas animadas.
            stack = Gtk.Stack()
            stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
            stack.set_transition_duration(230)
            root.append(stack)
            hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11)
            hero.set_margin_start(32); hero.set_margin_end(32)
            hero.set_margin_top(26); hero.set_margin_bottom(27)
            hero.set_halign(Gtk.Align.FILL)
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
            header.append(brand_icon(35))
            name = Gtk.Label(label='SYN', xalign=0)
            name.add_css_class('syn-welcome-kicker')
            header.append(name)
            header.set_margin_bottom(10)
            hero.append(header)
            cover_logo = brand_icon(96)
            cover_logo.set_halign(Gtk.Align.CENTER)
            hero.append(cover_logo)
            tagline = Gtk.Label(label=tr('Tu televisión, a tu manera.'))
            tagline.add_css_class('syn-welcome-title')
            tagline.set_wrap(True)
            hero.append(tagline)
            subtitle = Gtk.Label(label=tr('Añade una fuente para empezar. Solo te pediremos los datos imprescindibles.'))
            subtitle.add_css_class('syn-welcome-subtitle')
            subtitle.set_wrap(True)
            subtitle.set_justify(Gtk.Justification.CENTER)
            subtitle.set_margin_bottom(10)
            hero.append(subtitle)

            def choice(label, desc, symbol, kind):
                button = Gtk.Button()
                button.add_css_class('syn-welcome-card')
                button.set_hexpand(True)
                content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
                icon = welcome_symbol(kind, 37)
                content.append(icon)
                labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                h = Gtk.Label(label=label, xalign=0)
                h.add_css_class('syn-welcome-card-title')
                labels.append(h)
                d = Gtk.Label(label=desc, xalign=0)
                d.add_css_class('syn-welcome-card-subtitle')
                d.set_wrap(True)
                labels.append(d)
                content.append(labels)
                content.append(welcome_symbol('next', 17))
                button.set_child(content)
                button.connect('clicked', lambda *_: choose_source(kind))
                hero.append(button)

            choice(tr('Archivo M3U'), tr('Abre una lista IPTV guardada en tu ordenador.'),
                   'folder-videos-symbolic', 'file')
            choice(tr('Enlace M3U'), tr('Pega la URL que te ha proporcionado tu servicio.'),
                   'network-server-symbolic', 'url')
            choice('Xtream Codes', tr('Conecta tu servidor con usuario y contraseña.'),
                   'network-wireless-symbolic', 'xtream')
            tip = Gtk.Label(label=tr('Sin cuentas obligatorias  ·  Sin datos de demostración  ·  Tu lista es privada'))
            tip.add_css_class('syn-welcome-muted')
            tip.set_wrap(True)
            tip.set_margin_top(8)
            hero.append(tip)
            stack.add_named(hero, 'intro')

            form_scroll = Gtk.ScrolledWindow()
            form_scroll.set_min_content_height(490)
            form_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            form_shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            form_shell.add_css_class('syn-welcome-body')
            form_shell.set_margin_top(22); form_shell.set_margin_bottom(23)
            form_shell.set_margin_start(28); form_shell.set_margin_end(28)
            form_scroll.set_child(form_shell)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            back = Gtk.Button()
            back.set_child(welcome_symbol('back', 19))
            back.set_tooltip_text(tr('Volver a elegir una fuente'))
            back.connect('clicked', lambda *_: stack.set_visible_child_name('intro'))
            row.append(back)
            form_title = Gtk.Label(label=tr('Configura tu fuente'), xalign=0)
            form_title.add_css_class('syn-welcome-card-title')
            form_title.set_hexpand(True)
            row.append(form_title)
            form_shell.append(row)

            def field(title, value='', secret=False):
                group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                text = Gtk.Label(label=title, xalign=0)
                group.append(text)
                entry = Gtk.PasswordEntry() if secret else Gtk.Entry()
                entry.set_text(value)
                entry.set_hexpand(True)
                group.append(entry)
                form_shell.append(group)
                return group, entry

            pname_group, pname = field(tr('Nombre del perfil'), tr('Mi televisión'))
            file_group, source = field(tr('Archivo M3U o URL M3U'))
            browse = Gtk.Button(label=tr('Explorar archivo…'))
            browse.set_halign(Gtk.Align.START)
            file_group.append(browse)
            server_group, server = field(tr('Servidor Xtream (http:// o https://)'))
            username_group, username = field(tr('Usuario Xtream'))
            password_group, password = field(tr('Contraseña Xtream'), secret=True)
            epg_group, epg = field(tr('EPG XMLTV: URL, archivo .xml o .xml.gz (opcional)'))
            epg_browse = Gtk.Button(label=tr('Seleccionar EPG…'))
            epg_browse.set_halign(Gtk.Align.START)
            epg_group.append(epg_browse)
            # The XMLTV override is useful, but should not interrupt basic setup.
            form_shell.remove(epg_group)
            extras = Gtk.Expander(label=tr('Opciones avanzadas · EPG opcional'))
            extras.set_child(epg_group)
            form_shell.append(extras)
            notice = Gtk.Label(label='', xalign=0)
            notice.add_css_class('syn-welcome-muted')
            notice.set_wrap(True)
            form_shell.append(notice)
            save = Gtk.Button(label=tr('Conectar y empezar'))
            save.add_css_class('syn-welcome-cta')
            form_shell.append(save)
            stack.add_named(form_scroll, 'form')
            selected = {'kind': 'file'}

            def choose_source(kind):
                selected['kind'] = kind
                labels = {'file':tr('Archivo M3U'), 'url':tr('Enlace M3U'), 'xtream':'Xtream Codes'}
                form_title.set_text('Conectar · ' + labels[kind])
                source.set_placeholder_text('https://servidor/lista.m3u' if kind == 'url' else '/home/usuario/Vídeos/lista.m3u')
                source.set_text('')
                source.set_input_purpose(Gtk.InputPurpose.URL if kind == 'url' else Gtk.InputPurpose.FREE_FORM)
                file_group.set_visible(kind != 'xtream')
                browse.set_visible(kind == 'file')
                for group in (server_group, username_group, password_group):
                    group.set_visible(kind == 'xtream')
                notice.set_text('')
                stack.set_visible_child_name('form')
                pname.grab_focus()

            def on_file_picked(picker, result):
                try:
                    selected_file = picker.open_finish(result)
                    if selected_file and selected_file.get_path():
                        source.set_text(selected_file.get_path())
                except GLib.Error:
                    pass

            def browse_file(*_):
                chooser = Gtk.FileDialog(title=tr('Selecciona tu lista M3U'))
                chooser.open(dialog, None, on_file_picked)
            browse.connect('clicked', browse_file)

            def on_epg_chosen(picker, result):
                try:
                    f = picker.open_finish(result)
                    if f and f.get_path(): epg.set_text(f.get_path())
                except GLib.Error:
                    pass
            epg_browse.connect('clicked', lambda *_: Gtk.FileDialog(
                title=tr('Selecciona XMLTV (.xml o .xml.gz)')).open(dialog, None, on_epg_chosen))

            def save_source(*_):
                kind = selected['kind']
                obj = {'id': sources.next_profile_id(), 'name': pname.get_text().strip(),
                       'type': kind, 'source': source.get_text().strip(),
                       'server': server.get_text().strip(), 'username': username.get_text().strip(),
                       'password': password.get_text(), 'format': 'm3u8', 'epg_url': epg.get_text().strip(),
                       'favorites': []}
                try:
                    sources.validate_profile(obj)
                except ValueError as exc:
                    notice.set_text(str(exc))
                    return
                # Solo escribimos al disco tras validar; así cancelar la bienvenida
                # nunca modifica los perfiles existentes.
                if self._needs_welcome:
                    self.cfg['profiles'] = [obj]
                else:
                    self.cfg['profiles'].append(obj)
                self.cfg['selected'] = obj['id']
                self.profile = obj
                self._needs_welcome = False
                self.favorites = set()
                sources.save_config(self.cfg)
                self.profile_picker.set_model(Gtk.StringList.new([p['name'] for p in self.cfg['profiles']]))
                self.profile_picker.set_selected(len(self.cfg['profiles']) - 1)
                self.load_channels()
                dialog.close()
                self._welcome_window = None

            save.connect('clicked', save_source)
            stack.set_visible_child_name('intro')
            dialog.present()
            return False

        def build_fullscreen_osd(self):
            """El OSD es un overlay; nunca recrea el GLArea ni libmpv."""
            self.fs_dim = Gtk.Box()
            self.fs_dim.set_hexpand(True)
            self.fs_dim.set_vexpand(True)
            self.fs_dim.set_halign(Gtk.Align.FILL)
            self.fs_dim.set_valign(Gtk.Align.FILL)
            self.fs_dim.set_can_target(False)
            self.fs_dim.add_css_class("syn-fs-dim")
            self.overlay.add_overlay(self.fs_dim)
            self.fs_dim.set_visible(False)

            # Gradientes decorativos transparentes a los clics. No reparentar
            # Gtk.GLArea ni recrear libmpv: mantenemos la ruta estable de 3.1.
            self.fs_scrim_top = Gtk.Box()
            self.fs_scrim_top.set_halign(Gtk.Align.FILL)
            self.fs_scrim_top.set_valign(Gtk.Align.START)
            self.fs_scrim_top.set_size_request(-1, 182)
            self.fs_scrim_top.set_can_target(False)
            self.fs_scrim_top.add_css_class("syn-fs-scrim-top")
            self.overlay.add_overlay(self.fs_scrim_top)
            self.fs_scrim_top.set_visible(False)

            self.fs_scrim_bottom = Gtk.Box()
            self.fs_scrim_bottom.set_halign(Gtk.Align.FILL)
            self.fs_scrim_bottom.set_valign(Gtk.Align.END)
            self.fs_scrim_bottom.set_size_request(-1, 250)
            self.fs_scrim_bottom.set_can_target(False)
            self.fs_scrim_bottom.add_css_class("syn-fs-scrim-bottom")
            self.overlay.add_overlay(self.fs_scrim_bottom)
            self.fs_scrim_bottom.set_visible(False)

            self.fs_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.fs_top.add_css_class("syn-fs-top")
            self.fs_top.set_halign(Gtk.Align.END)
            self.fs_top.set_valign(Gtk.Align.START)
            exit_btn = Gtk.Button()
            exit_btn.set_child(self._syn_exit_fullscreen_icon())
            exit_btn.set_tooltip_text(tr("Salir de pantalla completa (Esc)"))
            exit_btn.connect("clicked", self.toggle_fullscreen)
            self.fs_top.append(exit_btn)
            self.fs_remote = Gtk.ToggleButton()
            self.fs_remote.set_icon_name("view-list-symbolic")
            self.fs_remote.set_tooltip_text(tr("Mando de canales · buscar y hacer zapping"))
            self.fs_remote.connect("toggled", self.toggle_fs_remote)
            self.fs_top.append(self.fs_remote)
            self.fs_guide_btn = Gtk.Button(label=tr('Guía EPG'))
            self.fs_guide_btn.set_tooltip_text(tr('Ver la programación sin salir de pantalla completa'))
            self.fs_guide_btn.connect('clicked', self.show_guide)
            self.fs_top.append(self.fs_guide_btn)
            self.fs_cast_button = Gtk.ToggleButton()
            self.fs_cast_button.add_css_class('syn-cast-button')
            self.fs_cast_button.set_child(self._syn_cast_make_icon())
            self.fs_cast_button.set_tooltip_text('Retransmitir por Chromecast')
            self.fs_cast_button.connect('toggled', self._syn_cast_menu)
            self.fs_top.append(self.fs_cast_button)
            shot_full = Gtk.Button()
            shot_full.set_child(self._syn_capture_icon(on_black=True))
            shot_full.set_tooltip_text('Capturar fotograma PNG')
            shot_full.connect('clicked', self._syn_capture_take)
            self.fs_top.append(shot_full)
            previous = Gtk.Button.new_from_icon_name("go-previous-symbolic")
            previous.set_tooltip_text(tr("Canal anterior"))
            previous.connect("clicked", lambda *_: self.zap(-1))
            self.fs_top.append(previous)
            following = Gtk.Button.new_from_icon_name("go-next-symbolic")
            following.set_tooltip_text(tr("Canal siguiente"))
            following.connect("clicked", lambda *_: self.zap(1))
            self.fs_top.append(following)
            self.overlay.add_overlay(self.fs_top)
            self.fs_top.set_visible(False)

            # Panel verdaderamente integrado en Gtk.Overlay, no un Gtk.Popover
            # con aspecto genérico. Gtk.Revealer gestiona la transición sin
            # mover, reparentar o reconstruir el GLArea de libmpv.
            self.fs_remote_open = False
            self.fs_render_limit = 60
            self.fs_remote_revealer = Gtk.Revealer()
            self.fs_remote_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
            self.fs_remote_revealer.set_transition_duration(240)
            self.fs_remote_revealer.set_halign(Gtk.Align.END)
            self.fs_remote_revealer.set_valign(Gtk.Align.FILL)
            self.fs_remote_revealer.set_margin_top(0)
            self.fs_remote_revealer.set_margin_end(0)
            self.fs_remote_revealer.set_reveal_child(False)

            # La zona de degradado ocupa toda la altura y parte del vídeo.
            # El extremo izquierdo es transparente; controles solo a la derecha.
            remote_backdrop = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            remote_backdrop.add_css_class('syn-zap-backdrop')
            remote_backdrop.set_size_request(550, -1)
            remote_backdrop.set_valign(Gtk.Align.FILL)
            remote_backdrop.set_halign(Gtk.Align.END)

            remote_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11)
            remote_box.add_css_class('syn-zap-panel')
            remote_box.set_size_request(342, -1)
            remote_box.set_valign(Gtk.Align.START)
            remote_box.set_margin_start(167)
            remote_box.set_margin_end(25)
            remote_box.set_margin_top(78)
            remote_box.set_margin_bottom(20)
            remote_backdrop.append(remote_box)
            header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            eyebrow = Gtk.Label(label=tr("SYN  •  DIRECTO"), xalign=0)
            eyebrow.add_css_class("syn-zap-eyebrow")
            heading.append(eyebrow)
            title = Gtk.Label(label=tr("Elige un canal"), xalign=0)
            title.add_css_class("syn-zap-title")
            heading.append(title)
            header_row.append(heading)
            header_row.set_hexpand(True)
            close = Gtk.Button.new_from_icon_name("window-close-symbolic")
            close.add_css_class("flat")
            close.set_valign(Gtk.Align.START)
            close.set_tooltip_text(tr("Cerrar mando de canales (Esc)"))
            close.connect("clicked", lambda *_: self.set_fs_remote(False))
            header_row.append(close)
            remote_box.append(header_row)
            self.fs_search = Gtk.SearchEntry(placeholder_text=tr("Buscar por canal o categoría…"))
            self.fs_search.add_css_class("syn-zap-search")
            self.fs_search.connect("search-changed", self.fs_filter_changed)
            remote_box.append(self.fs_search)
            filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.fs_category = Gtk.DropDown.new_from_strings([tr('Todas las categorías')])
            self.fs_category.add_css_class("syn-zap-category")
            self.fs_category.set_hexpand(True)
            self.fs_category.connect("notify::selected", self.fs_filter_changed)
            filters.append(self.fs_category)
            self.fs_only_favorites = Gtk.ToggleButton()
            self.fs_only_favorites.set_label("♡")
            self.fs_only_favorites.add_css_class('syn-favorite-filter')
            self.fs_only_favorites.set_tooltip_text(tr("Mostrar solo favoritos"))
            self.fs_only_favorites.connect('toggled', lambda btn: (
                btn.set_label('♥' if btn.get_active() else '♡'), self.fs_filter_changed(btn)))
            filters.append(self.fs_only_favorites)
            remote_box.append(filters)

            remote_scroll = Gtk.ScrolledWindow()
            remote_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            remote_scroll.set_min_content_height(220)
            remote_scroll.set_max_content_height(300)
            remote_scroll.set_propagate_natural_height(True)
            self.fs_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE,
                                       activate_on_single_click=True)
            self.fs_list.add_css_class("navigation-sidebar")
            self.fs_list.connect("row-activated", self.fs_activate_channel)
            remote_scroll.set_child(self.fs_list)
            remote_box.append(remote_scroll)
            bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.fs_count = Gtk.Label(label="", xalign=0)
            self.fs_count.add_css_class("syn-zap-subtitle")
            self.fs_count.set_hexpand(True)
            bottom.append(self.fs_count)
            self.fs_more = Gtk.Button(label=tr("Ver más ↓"))
            self.fs_more.add_css_class("flat")
            self.fs_more.connect("clicked", self.fs_show_more)
            bottom.append(self.fs_more)
            remote_box.append(bottom)
            remote_guide = Gtk.Button(label=tr('▦  Abrir Guía EPG'))
            remote_guide.add_css_class('syn-guide-head-button')
            remote_guide.connect('clicked', self.show_guide)
            remote_box.append(remote_guide)
            self.fs_remote_revealer.set_child(remote_backdrop)
            self.overlay.add_overlay(self.fs_remote_revealer)
            self.fs_remote_revealer.set_visible(False)

            self.fs_bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
            self.fs_bottom.add_css_class("syn-fs-bottom")
            self.fs_bottom.set_halign(Gtk.Align.FILL)
            self.fs_bottom.set_valign(Gtk.Align.END)
            self.fs_bottom.set_hexpand(True)
            meta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            meta.set_hexpand(False)
            meta.set_size_request(240, -1)
            self.fs_channel_label = Gtk.Label(label=tr("Selecciona un canal"), xalign=0)
            self.fs_channel_label.add_css_class("syn-fs-channel")
            self.fs_channel_label.set_ellipsize(Pango.EllipsizeMode.END)
            meta.append(self.fs_channel_label)
            self.fs_epg_label = Gtk.Label(label=tr("Sin información EPG"), xalign=0)
            self.fs_epg_label.add_css_class("syn-fs-epg")
            self.fs_epg_label.set_ellipsize(Pango.EllipsizeMode.END)
            meta.append(self.fs_epg_label)
            self.fs_next_label = Gtk.Label(label="", xalign=0)
            self.fs_next_label.add_css_class("syn-fs-next")
            self.fs_next_label.set_ellipsize(Pango.EllipsizeMode.END)
            meta.append(self.fs_next_label)
            self.fs_bottom.append(meta)
            # Discreet horizontal timeshift control between channel metadata and volume.
            self.fs_ts_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            self.fs_ts_bar.add_css_class('syn-fs-volume')
            self.fs_ts_bar.set_valign(Gtk.Align.END)
            self.fs_ts_bar.set_hexpand(True)
            self.fs_ts_bar.set_halign(Gtk.Align.FILL)
            self.fs_ts_enable = Gtk.ToggleButton(label='⏱')
            self.fs_ts_enable.set_tooltip_text('Toggle timeshift' if LANGUAGE.startswith('en') else 'Activar o desactivar timeshift')
            self.fs_ts_enable.connect('toggled', self._syn_ts_toggle)
            self.fs_ts_bar.append(self.fs_ts_enable)
            self.fs_ts_shortcuts = []
            for label, seconds in (('−30s',30), ('−1m',60), ('−1m30',90)):
                btn = Gtk.Button(label=label)
                btn.add_css_class('flat')
                btn.set_tooltip_text(('Go back ' if LANGUAGE.startswith('en') else 'Retroceder ') + str(seconds) + (' seconds' if LANGUAGE.startswith('en') else ' segundos'))
                btn.connect('clicked', lambda _b, amount=seconds: self._syn_ts_seek_to(amount))
                self.fs_ts_bar.append(btn)
                self.fs_ts_shortcuts.append(btn)
            self.fs_ts_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,-120,0,1)
            self.fs_ts_slider.set_draw_value(False)
            self.fs_ts_slider.set_size_request(260,-1)
            self.fs_ts_slider.set_hexpand(True)
            self.fs_ts_slider.connect('value-changed', self._syn_ts_slider_changed)
            self.fs_ts_bar.append(self.fs_ts_slider)
            self.fs_ts_readout = Gtk.Label(label='DIRECTO')
            self.fs_ts_bar.append(self.fs_ts_readout)
            self.fs_ts_live = Gtk.Button(label='●')
            self.fs_ts_live.set_tooltip_text('Return to live' if LANGUAGE.startswith('en') else 'Volver al directo')
            self.fs_ts_live.connect('clicked', self._syn_ts_go_live)
            self.fs_ts_bar.append(self.fs_ts_live)
            self.fs_bottom.append(self.fs_ts_bar)
            self._syn_ts_render()
            volume_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
            volume_box.add_css_class("syn-fs-volume")
            volume_box.set_valign(Gtk.Align.END)
            volume_box.append(Gtk.Image.new_from_icon_name("audio-volume-high-symbolic"))
            self.fs_volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            self.fs_volume.set_draw_value(False)
            self.fs_volume.set_value(100)
            self.fs_volume.set_size_request(130, -1)
            self.fs_volume.connect("value-changed", self.fs_volume_changed)
            volume_box.append(self.fs_volume)
            self.fs_bottom.append(volume_box)
            self.overlay.add_overlay(self.fs_bottom)
            self.fs_bottom.set_visible(False)

        # SYN_DUAL_TIMESHIFT_BETA_132: optional 2-minute disk-backed live ring.
        def _syn_ts_stop(self, restore=False):
            session = getattr(self, '_syn_ts_session', None)
            self._syn_ts_session = None
            self._syn_ts_loading = False
            self._syn_ts_ready = False
            self._syn_ts_offset = 0.0
            self._syn_ts_snapshot_mode = False
            self._syn_ts_snapshot_length = 0.0
            self._syn_ts_snapshot_started = 0.0
            if getattr(self, '_syn_ts_poll_id', 0):
                GLib.source_remove(self._syn_ts_poll_id)
                self._syn_ts_poll_id = 0
            if getattr(self, '_syn_ts_seek_debounce', 0):
                GLib.source_remove(self._syn_ts_seek_debounce)
                self._syn_ts_seek_debounce = 0
            player = self.area.player if hasattr(self, 'area') else None
            if player and session and (
                    player.active_url == session.playlist.as_uri() or
                    player.active_url.startswith(session._base_url() or 'syn://invalid')):
                player.stop()
            if session:
                session.stop()
            if hasattr(self, 'fs_ts_enable'):
                self._syn_ts_ui_guard = True
                self.fs_ts_enable.set_active(False)
                self.fs_ts_slider.set_value(0)
                self._syn_ts_ui_guard = False
                self._syn_ts_render()
            if restore and self.current:
                self._syn_ts_auto_blocked_url = self.current.url
                self.start_channel(self.current)

        def _syn_ts_toggle(self, button):
            if getattr(self, '_syn_ts_ui_guard', False):
                return
            if button.get_active():
                self._syn_ts_start()
            else:
                self._syn_ts_stop(restore=True)

        def _syn_ts_auto_enabled(self, channel):
            if not syn_timeshift.stream_allowed(channel.url):
                return False
            if getattr(self, '_syn_ts_auto_blocked_url', None) == channel.url:
                return False
            return bool(self.cfg.get('player', {}).get('timeshift_auto', True))

        def _syn_ts_start(self):
            ch = self.current
            if not ch or not syn_timeshift.stream_allowed(ch.url):
                self.status.set_text('Timeshift: selecciona primero un canal IPTV.')
                self._syn_ts_stop()
                return
            if getattr(self, '_syn_ts_session', None):
                return
            db = self.dvr_store.read()
            # Don't make a second provider request to an already recorded channel.
            if any(j.get('url') == ch.url for j in syn_multistream.active_jobs(db, self.profile.get('id'))):
                self.status.set_text(tr('Timeshift: no disponible durante una grabación de este canal.'))
                self._syn_ts_stop()
                return
            if syn_multistream.should_release_playback(db, self.profile.get('id'),
                                                       syn_multistream.profile_limit(self.profile), ch.url):
                self.status.set_text(tr('Timeshift: todas las conexiones están ocupadas por el DVR.'))
                self._syn_ts_stop()
                return
            # Release the original provider connection before FFmpeg opens one.
            player = self.area.player
            if player:
                player.stop()
            try:
                self._syn_ts_session = syn_timeshift.TimeshiftSession()
                self._syn_ts_channel_url = ch.url
                self._syn_ts_ready = False
                self._syn_ts_loading = True
                self._syn_ts_started_at = time.monotonic()
                self._syn_ts_offset = 0.0
                ua = syn_dvr.VLC_UA
                if self.player_options.get('user_agent') == 'Personalizado':
                    ua = self.player_options.get('custom_ua') or ua
                self._syn_ts_session.start(ch.url, ua)
            except (OSError, ValueError) as exc:
                self.status.set_text('Timeshift: ' + str(exc)[:120])
                self._syn_ts_stop(restore=True)
                return
            self.status.set_text(tr('Timeshift: preparando búfer temporal…'))
            if self.fullscreen_mode: self.set_fs_osd(True)
            self._syn_ts_poll_id = GLib.timeout_add(450, self._syn_ts_poll)
            self._syn_ts_ui_guard = True
            try:
                self.fs_ts_enable.set_active(True)
            finally:
                self._syn_ts_ui_guard = False
            self._syn_ts_render()

        def _syn_ts_poll(self):
            session = getattr(self, '_syn_ts_session', None)
            if not session or not self.current or self.current.url != self._syn_ts_channel_url:
                self._syn_ts_poll_id = 0
                return False
            error = session.error()
            if error:
                self._syn_ts_poll_id = 0
                self.status.set_text('Timeshift: ' + error)
                self._syn_ts_stop(restore=True)
                return False
            if (not self._syn_ts_ready and
                    time.monotonic() - getattr(self, '_syn_ts_started_at', time.monotonic()) > 20):
                self.status.set_text(tr('Timeshift: sin señal inicial; regreso al directo.'))
                self._syn_ts_stop(restore=True)
                return False
            if not self._syn_ts_ready and session.ready():
                self._syn_ts_ready = True
                self._syn_ts_loading = False
                if self.area.player:
                    # SYN_TIMESHIFT_BETA2_HTTP_SNAPSHOT: serving a changing
                    # local HLS playlist over loopback is more reliable than file://.
                    self.area.player.play(Channel(self.current.name, self.current.group,
                                                  session.live_url(), self.current.logo))
                self.status.set_text('Timeshift activo · memoria circular de hasta 2 minutos')
                if self.fullscreen_mode: self.set_fs_osd(True)
            if self._syn_ts_ready:
                self._syn_ts_render()
                if session.disk_bytes() > syn_timeshift.MAX_DISK_BYTES:
                    self.status.set_text(tr('Timeshift: límite de almacenamiento; regresando al directo.'))
                    self._syn_ts_stop(restore=True)
                    return False
            return True

        def _syn_ts_render(self):
            if not hasattr(self, 'fs_ts_slider'):
                return
            session = getattr(self, '_syn_ts_session', None)
            ready = bool(session and getattr(self, '_syn_ts_ready', False))
            available = min(120.0, session.available_seconds()) if ready else 0.0
            self._syn_ts_ui_guard = True
            self.fs_ts_slider.set_range(-max(1,available), 0)
            if not ready:
                self.fs_ts_slider.set_value(0)
            self._syn_ts_ui_guard = False
            self.fs_ts_slider.set_sensitive(ready)
            for button, threshold in zip(self.fs_ts_shortcuts, (30, 60, 90)):
                button.set_sensitive(ready and available >= threshold - 2)
            self.fs_ts_live.set_sensitive(ready)
            # A VOD snapshot does not seek on a changing live HLS manifest.
            # Behind-live is approximate: live edge keeps moving as VOD plays.
            if ready and getattr(self, '_syn_ts_snapshot_mode', False):
                pos = self.area.player.playback_position() if self.area.player else None
                length = getattr(self, '_syn_ts_snapshot_length', 0.0)
                if pos is not None:
                    elapsed = max(0.0, time.monotonic() - self._syn_ts_snapshot_started)
                    self._syn_ts_offset = -max(0.0, length + elapsed - pos)
                if pos is not None and length > 1 and pos >= length - 1.2:
                    self._syn_ts_go_live()
                    return
            lag = int(round(-self._syn_ts_offset)) if ready else 0
            # Reflect playback, not just the user's last button press.
            self._syn_ts_ui_guard = True
            self.fs_ts_slider.set_value(-min(available, max(0.0, float(lag))))
            self._syn_ts_ui_guard = False
            self.fs_ts_readout.set_text('≈−%ds' % lag if lag else ('LIVE' if LANGUAGE.startswith('en') else 'DIRECTO'))

        def _syn_ts_seek_to(self, seconds_back):
            session = getattr(self, '_syn_ts_session', None)
            if not session or not self._syn_ts_ready or not self.area.player:
                return
            available = max(0, session.available_seconds() - 1)
            target = min(max(0.0, float(seconds_back)), available)
            if target < 1:
                self._syn_ts_go_live()
                return
            try:
                url, duration = session.snapshot_back(target)
            except (OSError, ValueError, RuntimeError) as exc:
                self.status.set_text('Timeshift: ' + str(exc)[:125])
                self.fs_ts_readout.set_text('ERROR')
                return
            self._syn_ts_snapshot_mode = True
            self._syn_ts_snapshot_length = duration
            self._syn_ts_snapshot_started = time.monotonic()
            self._syn_ts_offset = -duration
            self.area.player.play(Channel(self.current.name, self.current.group,
                                          url, self.current.logo))
            if self.fullscreen_mode: self.set_fs_osd(True)
            self._syn_ts_ui_guard = True
            self.fs_ts_slider.set_value(-min(available, duration))
            self._syn_ts_ui_guard = False
            self._syn_ts_render()

        def _syn_ts_slider_changed(self, slider):
            if not getattr(self, '_syn_ts_ui_guard', False):
                if self.fullscreen_mode: self.set_fs_osd(True)
                if getattr(self, '_syn_ts_seek_debounce', 0):
                    GLib.source_remove(self._syn_ts_seek_debounce)
                self._syn_ts_seek_debounce = GLib.timeout_add(170, self._syn_ts_slider_commit)

        def _syn_ts_slider_commit(self):
            self._syn_ts_seek_debounce = 0
            self._syn_ts_seek_to(-self.fs_ts_slider.get_value())
            return False

        def _syn_ts_go_live(self, *_):
            session = getattr(self, '_syn_ts_session', None)
            if not session or not self._syn_ts_ready:
                return
            self._syn_ts_offset = 0
            self._syn_ts_snapshot_mode = False
            self._syn_ts_snapshot_length = 0.0
            self._syn_ts_snapshot_started = 0.0
            # Reopen the *local HTTP* live playlist. No extra provider login.
            if self.area.player and self.current:
                self.area.player.play(Channel(self.current.name, self.current.group,
                                              session.live_url(), self.current.logo))
            self._syn_ts_ui_guard = True
            self.fs_ts_slider.set_value(0)
            self._syn_ts_ui_guard = False
            self._syn_ts_render()

        # SYN_RECONNECT_COLOR_BARS_BETA3: never interfere with DVR or timeshift.
        def _syn_reconnect_bars_draw(self, _area, cr, width, height):
            # Colours and geometry follow SYN's approved colour-bar icon.
            top = ((.42,.79,.99), (1.00,.87,.28), (.31,.88,.74),
                   (.19,.69,.96), (.63,.32,.94), (.96,.28,.65), (.99,.43,.33))
            bottom = ((.17,.30,.58), (.50,.20,.98), (.16,.25,.44),
                      (.10,.85,.90), (.98,.17,.58))
            split = int(height * .79)
            for i, (r,g,b) in enumerate(top):
                left = width * i / len(top)
                cr.set_source_rgb(r,g,b)
                cr.rectangle(left, 0, width / len(top) + 1, split)
                cr.fill()
            for i, (r,g,b) in enumerate(bottom):
                left = width * i / len(bottom)
                cr.set_source_rgb(r,g,b)
                cr.rectangle(left, split, width / len(bottom) + 1, height - split)
                cr.fill()

        def _syn_reconnect_build(self):
            self._syn_reconnect_watch = syn_reconnect.RecoveryWatch()
            self._syn_reconnect_last_url = None
            self._syn_reconnect_layer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self._syn_reconnect_layer.set_halign(Gtk.Align.CENTER)
            self._syn_reconnect_layer.set_valign(Gtk.Align.CENTER)
            self._syn_reconnect_layer.set_can_target(False)
            self._syn_reconnect_layer.set_visible(False)
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
            card.set_halign(Gtk.Align.CENTER)
            card.set_margin_top(15); card.set_margin_bottom(15)
            card.set_margin_start(15); card.set_margin_end(15)
            card.add_css_class('syn-reconnect-card')
            self._syn_reconnect_art = Gtk.DrawingArea()
            self._syn_reconnect_art.set_content_width(280)
            self._syn_reconnect_art.set_content_height(172)
            self._syn_reconnect_art.set_draw_func(self._syn_reconnect_bars_draw)
            card.append(self._syn_reconnect_art)
            label = Gtk.Label(label=('Reconnecting…' if LANGUAGE.startswith('en')
                                      else 'Reconectando…'))
            label.set_xalign(.5)
            label.add_css_class('title-3')
            card.append(label)
            self._syn_reconnect_label = label
            self._syn_reconnect_layer.append(card)
            self.overlay.add_overlay(self._syn_reconnect_layer)
            # App priority: consistent in Sistema, Claro, Oscuro and Teal.
            css = Gtk.CssProvider()
            css.load_from_data(b'.syn-reconnect-card { background-color: rgba(11,24,29,0.94); '
                               b'color: white; padding: 18px; border-radius: 18px; '
                               b'border: 1px solid rgba(255,255,255,0.18); } '
                               b'.syn-reconnect-card label { color: white; }')
            display = self.get_display() or Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display, css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 4)
            self._syn_reconnect_css = css
            GLib.timeout_add(800, self._syn_reconnect_tick)

        def _syn_reconnect_reset(self):
            if hasattr(self, '_syn_reconnect_watch'):
                self._syn_reconnect_watch.clear()
                self._syn_reconnect_last_url = None
                self._syn_reconnect_layer.set_visible(False)

        def _syn_reconnect_tick(self):
            player = self.area.player if getattr(self, 'area', None) else None
            channel = getattr(self, 'current', None)
            if not hasattr(self, '_syn_reconnect_watch'):
                return True
            if not player or not player.ctx.value or not channel or not player.active_url:
                self._syn_reconnect_reset()
                return True
            if self.is_fullscreen() and getattr(self, 'guide_open', False):
                # Never obscure the interactive guide with a recovery card.
                self._syn_reconnect_layer.set_visible(False)
            if getattr(self, '_syn_ts_snapshot_mode', False) or getattr(self, '_dvr_playing_file', False):
                self._syn_reconnect_reset()
                return True
            # UI never calls mpv_get_property: the control thread owns polling.
            snapshot = player.playback_position()
            cache = bool(getattr(player, '_syn_reconnect_buffering', False))
            seeking = bool(getattr(player, '_syn_reconnect_seeking', False))
            loading = bool(getattr(player, '_awaiting_load', False))
            decision = self._syn_reconnect_watch.sample(
                time.monotonic(), player.active_url, snapshot,
                paused=player.paused(), buffering=cache,
                seeking=seeking, loading=loading)
            show = bool(decision.visible and not getattr(self, 'guide_open', False)
                        and not self.dvr_view.get_visible())
            self._syn_reconnect_layer.set_visible(show)
            if show:
                if LANGUAGE.startswith('en'):
                    msg = 'Reconnecting…' if decision.retry else 'Waiting for signal…'
                else:
                    msg = 'Reconectando…' if decision.retry else 'Esperando señal…'
                if decision.attempt:
                    msg += '  ·  ' + str(decision.attempt)
                self._syn_reconnect_label.set_text(msg)
            if decision.retry:
                # Crucial: reload CURRENT PLAYER URL. It may be a local DVR
                # relay or a timeshift HTTP URL, NOT the upstream IPTV URL.
                # Do not stop any FFmpeg worker, timeshift session or DVR job.
                try:
                    target = player.active_url
                    if target == channel.url and syn_dvr.allowed_stream_url(target):
                        # Double-DVR admission wins over reconnecting playback:
                        # never accidentally open a third provider connection.
                        db = self.dvr_store.read()
                        if syn_multistream.should_release_playback(
                                db, self.profile.get('id'),
                                syn_multistream.profile_limit(self.profile), channel.url):
                            relay, _waiting = self._syn_dvr_playback_target(channel)
                            if relay:
                                target = relay
                            else:
                                player.stop()
                                self._syn_reconnect_reset()
                                return True
                    player.play(Channel(channel.name, channel.group,
                                        target, channel.logo))
                except (OSError, ValueError, RuntimeError) as exc:
                    self.status.set_text('SYN: ' + type(exc).__name__)
            return True

        # SYN_IDLE_COLORBARS_BETA4: strictly visual; no MPV or DVR modifications.
        def _syn_idle_build(self):
            # Add before OSD/EPG/reconnect layers, so their controls stay visible.
            asset = Path(__file__).resolve().with_name('syn_idle_screen.png')
            self._syn_idle_layer = Gtk.Overlay()
            self._syn_idle_layer.set_hexpand(True)
            self._syn_idle_layer.set_vexpand(True)
            self._syn_idle_layer.set_halign(Gtk.Align.FILL)
            self._syn_idle_layer.set_valign(Gtk.Align.FILL)
            self._syn_idle_layer.set_can_target(False)
            picture = Gtk.Picture.new_for_filename(str(asset))
            picture.set_content_fit(Gtk.ContentFit.COVER)
            picture.set_can_shrink(True)
            picture.set_hexpand(True)
            picture.set_vexpand(True)
            self._syn_idle_layer.set_child(picture)
            hint = Gtk.Label(label=('Double-click a channel to play' if
                                    LANGUAGE.startswith('en') else
                                    'Doble click en un canal para reproducir'))
            hint.set_justify(Gtk.Justification.CENTER)
            hint.set_wrap(True)
            hint.set_max_width_chars(42)
            hint.set_halign(Gtk.Align.CENTER)
            hint.set_valign(Gtk.Align.CENTER)
            hint.set_can_target(False)
            hint.add_css_class('syn-idle-hint')
            self._syn_idle_hint = hint
            self._syn_idle_layer.add_overlay(hint)
            self.overlay.add_overlay(self._syn_idle_layer)
            # Old white-text placeholder is superseded only while this artwork
            # is installed. Keep the object for existing code paths/set_text.
            self.blank_label.set_visible(False)
            css = Gtk.CssProvider()
            # SYN_IDLE_TEXT_SHADOW_BETA4_1: text directly on bars, no container.
            css.load_from_data(b'.syn-idle-hint { color: #f6fafb; '
                               b'font-size: 19px; font-weight: 700; '
                               b'background: transparent; border: none; '
                               b'padding: 0; border-radius: 0; box-shadow: none; '
                               b'text-shadow: 0 2px 7px rgba(0,0,0,0.95), '
                               b'0 0 18px rgba(0,0,0,0.75); }')
            display = self.get_display() or Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display, css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
            self._syn_idle_css = css
            self._syn_idle_sync()
            self._syn_idle_timer_id = GLib.timeout_add(350, self._syn_idle_tick)

        def _syn_idle_sync(self):
            if not hasattr(self, '_syn_idle_layer'):
                return
            no_channel = self.current is None or bool(getattr(self,'_syn_cast_only',False))
            guide = bool(getattr(self, 'guide_open', False))
            dvr = getattr(self, 'dvr_view', None)
            dvr_visible = bool(dvr and dvr.get_visible())
            visible = no_channel and not dvr_visible and (getattr(self, "_synplus_ui", False) or not guide)
            if self._syn_idle_layer.get_visible() != visible:
                self._syn_idle_layer.set_visible(visible)
            # Preserve the original placeholder object for callers, but never
            # allow it to appear above the artist's colour-bar background.
            if self.blank_label.get_visible():
                self.blank_label.set_visible(False)

        def _syn_idle_tick(self):
            self._syn_idle_sync()
            return True

        def _syn_exit_fullscreen_icon(self):
            """Always-visible restore-window glyph on the fullscreen dark chrome.

            Draw directly in Cairo instead of relying on the GTK icon theme:
            view-restore-symbolic can be absent in a standalone macOS bundle.
            """
            area = Gtk.DrawingArea()
            area.set_content_width(20)
            area.set_content_height(20)
            area.set_size_request(20, 20)
            area.set_can_target(False)
            def paint(_area, cr, width, height):
                if min(width, height) <= 0:
                    return
                scale = min(width, height) / 20.0
                cr.save()
                try:
                    cr.translate((width - 20*scale)/2, (height - 20*scale)/2)
                    cr.scale(scale, scale)
                    cr.set_source_rgb(.98, .98, .99)
                    cr.set_line_width(1.8)
                    cr.set_line_cap(1)
                    cr.set_line_join(1)
                    # Two overlapping windows: standard 'restore' metaphor.
                    cr.move_to(6.5, 5.2)
                    cr.line_to(6.5, 3.2)
                    cr.line_to(16.9, 3.2)
                    cr.line_to(16.9, 13.3)
                    cr.line_to(14.8, 13.3)
                    cr.stroke()
                    cr.rectangle(3.1, 6.6, 10.7, 10.0)
                    cr.stroke()
                finally:
                    cr.restore()
            area.set_draw_func(paint)
            return area

        def _syn_capture_icon(self, on_black=False):
            """Camera glyph rendered by Cairo; never depends on GTK icon packs."""
            area = Gtk.DrawingArea()
            area.set_content_width(20)
            area.set_content_height(20)
            area.set_size_request(20, 20)
            area.set_can_target(False)
            def paint(widget, cr, width, height):
                if min(width, height) <= 0:
                    return
                scale = min(width, height) / 20.0
                cr.save()
                try:
                    cr.translate((width - 20*scale)/2, (height - 20*scale)/2)
                    cr.scale(scale, scale)
                    manager = Adw.StyleManager.get_default()
                    dark = bool(manager.get_dark())
                    color = (.97, .97, .98) if on_black or dark else (.12, .12, .14)
                    cr.set_source_rgb(*color)
                    cr.set_line_width(1.65)
                    cr.set_line_join(1)
                    # Camera body with upper viewfinder ridge and circular lens.
                    cr.move_to(3.0, 6.2)
                    cr.line_to(6.3, 6.2)
                    cr.line_to(7.5, 4.1)
                    cr.line_to(12.5, 4.1)
                    cr.line_to(13.7, 6.2)
                    cr.line_to(17.0, 6.2)
                    cr.line_to(17.0, 16.2)
                    cr.line_to(3.0, 16.2)
                    cr.close_path()
                    cr.stroke()
                    cr.arc(10.0, 11.2, 3.15, 0, 6.283185307179586)
                    cr.stroke()
                    cr.arc(15.2, 8.2, 0.75, 0, 6.283185307179586)
                    cr.fill()
                finally:
                    cr.restore()
            area.set_draw_func(paint)
            return area

        # SYN_CAPTURE_TIMESHIFT_BETA5: direct MPV frame PNG, not a window screenshot.
        def _syn_capture_folder(self):
            folder = (self.cfg.get('player', {}) or {}).get('screenshot_dir', '')
            if folder:
                return Path(folder).expanduser()
            if sys.platform == 'darwin':
                # Finder localizes 'Pictures' as 'Imágenes' automatically.
                return Path.home() / 'Pictures' / 'SYN'
            pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
            return Path(pictures) / 'SYN' if pictures else Path.home() / 'Imágenes' / 'SYN'

        def _syn_capture_setup(self):
            # Overlay decorations never consume mouse events or affect Gtk.GLArea.
            css = Gtk.CssProvider()
            css.load_from_data(b'.syn-shot-flash { background-color: rgba(255,255,255,0.65); } '
                               b'.syn-shot-preview { background-color: rgba(9,23,27,0.8); '
                               b'border: 1px solid rgba(255,255,255,0.4); border-radius: 8px; '
                               b'padding: 5px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }')
            display = self.get_display() or Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
            self._syn_shot_css = css
            self._syn_shot_flash = Gtk.Box()
            self._syn_shot_flash.add_css_class('syn-shot-flash')
            self._syn_shot_flash.set_hexpand(True)
            self._syn_shot_flash.set_vexpand(True)
            self._syn_shot_flash.set_halign(Gtk.Align.FILL)
            self._syn_shot_flash.set_valign(Gtk.Align.FILL)
            self._syn_shot_flash.set_can_target(False)
            self._syn_shot_flash.set_visible(False)
            self.overlay.add_overlay(self._syn_shot_flash)
            # No Gtk.Picture/preview overlay: a full-resolution frame had a
            # natural size of 1920x1080, covering the video indefinitely.
            # Use a brief non-interactive flash and dismissible status instead.
            self._syn_shot_fade_id = 0
            self._syn_shot_hold_id = 0
            self._syn_shot_poll_id = 0
            self._syn_shot_pending = None
            # Small temporary overlay for capture errors: the status label
            # stays detached from the layout to save player/EPG space.
            self._syn_shot_notice = Gtk.Label(label='')
            self._syn_shot_notice.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            self._syn_shot_notice.set_max_width_chars(52)
            self._syn_shot_notice.add_css_class('syn-shot-preview')
            self._syn_shot_notice.set_halign(Gtk.Align.CENTER)
            self._syn_shot_notice.set_valign(Gtk.Align.END)
            self._syn_shot_notice.set_margin_bottom(22)
            self._syn_shot_notice.set_margin_start(14)
            self._syn_shot_notice.set_margin_end(14)
            self._syn_shot_notice.set_can_target(False)
            self._syn_shot_notice.set_visible(False)
            self.overlay.add_overlay(self._syn_shot_notice)
            self._syn_shot_notice_timer = 0

        def _syn_capture_message(self, message):
            self.status.set_text(message)
            if self._syn_shot_notice_timer:
                GLib.source_remove(self._syn_shot_notice_timer)
            self._syn_shot_notice.set_text(message)
            self._syn_shot_notice.set_visible(True)
            self._syn_shot_notice_timer = GLib.timeout_add(3200, self._syn_capture_clear_message)

        def _syn_capture_clear_message(self):
            self._syn_shot_notice_timer = 0
            self._syn_shot_notice.set_visible(False)
            return False

        def _syn_capture_command_finished(self, result, error_text):
            if result < 0 and self._syn_shot_pending is not None:
                self._syn_shot_pending = None
                if self._syn_shot_poll_id:
                    GLib.source_remove(self._syn_shot_poll_id)
                    self._syn_shot_poll_id = 0
                self._syn_capture_message('Captura fallida: ' + (error_text or 'error de MPV'))
            return False

        def _syn_capture_flash(self):
            if self._syn_shot_fade_id:
                GLib.source_remove(self._syn_shot_fade_id)
                self._syn_shot_fade_id = 0
            layer = self._syn_shot_flash
            layer.set_opacity(0.82)
            layer.set_visible(True)
            start = time.monotonic()
            def tick():
                elapsed = time.monotonic() - start
                if elapsed >= 0.28:
                    layer.set_opacity(0.0)
                    layer.set_visible(False)
                    self._syn_shot_fade_id = 0
                    return False
                layer.set_opacity(max(0.0, 0.82 * (1.0-elapsed/0.28)**2))
                return True
            self._syn_shot_fade_id = GLib.timeout_add(16, tick)

        def _syn_capture_poll(self):
            pending = self._syn_shot_pending
            if not pending:
                self._syn_shot_poll_id = 0
                return False
            target, start = pending
            if target.is_file() and target.stat().st_size > 100:
                # PNG screenshot-to-file is asynchronous: only open when decodable.
                try:
                    # Decode a small image to ensure the PNG is complete,
                    # but NEVER put the full frame inside the player overlay.
                    GdkPixbuf.Pixbuf.new_from_file_at_scale(str(target), 160, 90, True)
                except (GLib.Error, OSError):
                    pass
                else:
                    self._syn_shot_pending = None
                    self._syn_shot_poll_id = 0
                    self._syn_capture_flash()
                    self._syn_capture_message('Foto PNG guardada · ' + str(target.parent))
                    return False
            if time.monotonic() - start >= 6.0:
                self._syn_shot_pending = None
                self._syn_shot_poll_id = 0
                self._syn_capture_message('No se pudo guardar la foto PNG. Revisa permisos y señal.')
                return False
            return True

        def _syn_capture_take(self, *_):
            player = self.area.player
            if not self.current or not player or not player.ctx.value or not player.active_url:
                self._syn_capture_message('Selecciona un canal antes de hacer una foto.')
                return
            if getattr(self, '_syn_shot_pending', None):
                return  # Do not pile up asynchronous screenshot commands.
            try:
                folder = self._syn_capture_folder()
                folder.mkdir(mode=0o700, parents=True, exist_ok=True)
                if not folder.is_dir():
                    raise OSError('No es una carpeta.')
                safe = syn_capture_filename(self.current.name)
                stamp = dt.datetime.now().strftime('%Y-%m-%d %H-%M-%S-%f')
                dest = folder / f'SYN - {safe} - {stamp}.png'
                # This command runs on the existing MPV control worker,
                # never on the GTK/GL rendering thread.
                if not player.screenshot_to_file(dest, self._syn_capture_command_finished):
                    raise OSError('El reproductor no está disponible.')
                self._syn_shot_pending = (dest, time.monotonic())
                self._syn_shot_poll_id = GLib.timeout_add(120, self._syn_capture_poll)
            except (OSError, ValueError) as exc:
                self._syn_capture_message('SYN captura: ' + str(exc)[:150])

        def _syn_capture_close(self):
            for name in ('_syn_shot_fade_id', '_syn_shot_hold_id', '_syn_shot_poll_id'):
                source_id = getattr(self, name, 0)
                if source_id:
                    GLib.source_remove(source_id)
                    setattr(self, name, 0)
            self._syn_shot_pending = None
            if getattr(self, '_syn_shot_notice_timer', 0):
                GLib.source_remove(self._syn_shot_notice_timer)
                self._syn_shot_notice_timer = 0

        def fs_volume_changed(self, scale):
            if hasattr(self, "volume") and abs(self.volume.get_value() - scale.get_value()) >= 0.5:
                self.volume.set_value(scale.get_value())

        def fs_filter_changed(self, *_):
            self.fs_render_limit = 60
            if self.fs_remote_open:
                self.render_fs_channels()

        def _fs_matching_channels(self):
            query = norm(self.fs_search.get_text().strip())
            ix = self.fs_category.get_selected()
            category = self.category_names[ix] if ix < len(self.category_names) else "Todas las categorías"
            fav_only = self.fs_only_favorites.get_active()
            matches = [ch for ch in self.channels
                       if (not query or query in norm(ch.name + ' ' + ch.group))
                       and (category == "Todas las categorías" or ch.group == category)
                       and (not fav_only or ch.favorite_id in self.favorites)]
            return (syn_fav_sort.order_channels(matches, self.profile.get('favorites', []))
                    if fav_only else matches)

        def render_fs_channels(self):
            if not hasattr(self, "fs_list") or not self.fs_remote_open:
                return
            matches = self._fs_matching_channels()
            # Construimos solo una tanda: Xtream puede contener miles de canales.
            # El buscador no bloquea a GTK reconstruyendo toda la lista.
            while (row := self.fs_list.get_row_at_index(0)) is not None:
                self.fs_list.remove(row)
            limit = min(self.fs_render_limit, len(matches))
            for ch in matches[:limit]:
                row = Gtk.ListBoxRow()
                row.channel = ch
                row.add_css_class("syn-zap-row")
                if self.current and ch.favorite_id == self.current.favorite_id:
                    row.add_css_class("syn-zap-playing")
                line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=11)
                line.set_margin_start(10)
                line.set_margin_end(10)
                line.set_margin_top(7)
                line.set_margin_bottom(7)
                line.append(self.channel_pill(ch, 116, 45))
                labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                labels.set_hexpand(True)
                # Nombre limpio para distinguir HD/FHD/UHD sin prefijo [ES].
                zap_channel_name = Gtk.Label(label=display_channel_name(ch.name), xalign=0)
                zap_channel_name.add_css_class('syn-zap-name')
                zap_channel_name.set_ellipsize(Pango.EllipsizeMode.END)
                labels.append(zap_channel_name)
                # Zapping rápido: datos reales, sin fabricar programas.
                now_item, future_items = sources.now_next(ch, self.guide, self.epg_aliases)
                current_title = now_item[2] if now_item else tr('Sin información EPG')
                group = Gtk.Label(label=current_title, xalign=0)
                group.add_css_class("syn-zap-group")
                group.set_ellipsize(Pango.EllipsizeMode.END)
                labels.append(group)
                if future_items:
                    nxt = future_items[0]
                    next_line = Gtk.Label(label=tr('A continuación ') + format_time(nxt[0]) + ' · ' + nxt[2], xalign=0)
                    next_line.add_css_class('syn-zap-subtitle')
                    next_line.set_ellipsize(Pango.EllipsizeMode.END)
                    labels.append(next_line)
                line.append(labels)
                if self.current and ch.favorite_id == self.current.favorite_id:
                    live = Gtk.Label(label="ON AIR")
                    live.add_css_class("syn-zap-live")
                    line.append(live)
                elif ch.favorite_id in self.favorites:
                    heart = Gtk.Label(label="♥")
                    heart.add_css_class('syn-heart-active')
                    heart.set_tooltip_text('Favorito')
                    line.append(heart)
                row.set_child(line)
                self.fs_list.append(row)
            self.fs_count.set_text(f"{limit} de {len(matches)} canales")
            self.fs_more.set_visible(limit < len(matches))

        def fs_show_more(self, *_):
            self.fs_render_limit += 60
            self.render_fs_channels()

        def toggle_fs_remote(self, toggle):
            self.set_fs_remote(toggle.get_active())

        def set_fs_remote(self, visible):
            visible = bool(visible and self.fullscreen_mode)
            if self.fs_remote_open == visible:
                return
            self.fs_remote_open = visible
            self.fs_remote.set_active(visible)
            self.fs_remote_revealer.set_reveal_child(visible)
            if visible:
                self.set_fs_osd(True)
                self.render_fs_channels()
                self.fs_search.grab_focus()
            elif self.fullscreen_mode:
                # Devuelve foco al vídeo para recuperar F11 y el zapping por teclado.
                self.area.grab_focus()

        def fs_activate_channel(self, _listbox, row):
            if row is None:
                return
            self.set_fs_remote(False)
            self.start_channel(row.channel)
            self.set_fs_osd(True)

        def zap(self, direction):
            if not self.channels:
                return
            ids = [ch.favorite_id for ch in self.channels]
            index = ids.index(self.current.favorite_id) if self.current and self.current.favorite_id in ids else 0
            self.start_channel(self.channels[(index + direction) % len(self.channels)])
            self.set_fs_osd(True)

        def on_video_click(self, _gesture, _n_press, _x, _y):
            if getattr(self, '_synplus_ui', False) and not self.fullscreen_mode:
                synplus_layout.click_controls(self)
            if self.fullscreen_mode:
                if self.fs_remote_open:
                    self.set_fs_remote(False)
                else:
                    self.set_fs_osd(not self.fs_osd_visible)

        def _fs_osd_hide_timeout(self):
            self.fs_osd_timer = 0
            # No cerramos la paleta durante el zapping, para poder buscar.
            if not self.fs_remote_open:
                self.set_fs_osd(False)
            return False

        def _syn_fade_fullscreen_osd(self, show):
            """Symmetric 260 ms fade; never touch GLArea/libmpv."""
            names = ('fs_dim', 'fs_scrim_top', 'fs_scrim_bottom',
                     'fs_top', 'fs_bottom')
            layers = tuple(getattr(self, name + '_fade', getattr(self, name))
                           for name in names)
            existing = getattr(self, '_syn_osd_fade_timer', 0)
            if existing:
                GLib.source_remove(existing)
                self._syn_osd_fade_timer = 0
            immediate = not self.fullscreen_mode and not show
            starts = []
            for layer in layers:
                revealed = (layer.get_reveal_child() if
                            hasattr(layer, 'get_reveal_child') else layer.get_visible())
                alpha = (float(layer.get_opacity()) if layer.get_visible()
                         and revealed else 0.0)
                starts.append(max(0.0, min(1.0, alpha)))
                if hasattr(layer, 'set_transition_duration'):
                    layer.set_transition_duration(0)
                if immediate:
                    layer.set_opacity(0.0)
                    if hasattr(layer, 'set_reveal_child'):
                        layer.set_reveal_child(False)
                    layer.set_visible(False)
                else:
                    # Set alpha BEFORE mapping; no first-frame flash.
                    layer.set_opacity(starts[-1])
                    layer.set_visible(True)
                    if hasattr(layer, 'set_reveal_child'):
                        layer.set_reveal_child(True)
            if immediate:
                return
            target = 1.0 if show else 0.0
            beginning = time.monotonic()
            def tick():
                t = min(1.0, (time.monotonic() - beginning) / 0.260)
                eased = t * t * (3.0 - 2.0 * t)
                for layer, initial in zip(layers, starts):
                    layer.set_opacity(initial + (target - initial) * eased)
                if t >= 1:
                    self._syn_osd_fade_timer = 0
                    if not show:
                        for layer in layers:
                            if hasattr(layer, 'set_reveal_child'):
                                layer.set_reveal_child(False)
                            layer.set_visible(False)
                    return False
                return True
            self._syn_osd_fade_timer = GLib.timeout_add(16, tick)

        def set_fs_osd(self, visible):
            if self.fs_osd_timer:
                GLib.source_remove(self.fs_osd_timer)
                self.fs_osd_timer = 0
            visible = bool(visible and self.fullscreen_mode)
            if not visible and self.fs_remote_open:
                self.set_fs_remote(False)
            self.fs_osd_visible = visible
            self.fs_remote_revealer.set_visible(self.fullscreen_mode)
            self._syn_fade_fullscreen_osd(visible)
            if visible:
                self._syn_ts_render()
                self.fs_channel_label.set_text(display_channel_name(self.current.name) if self.current else "SYN")
                self.update_programme()
                if abs(self.fs_volume.get_value() - self.volume.get_value()) >= 0.5:
                    self.fs_volume.set_value(self.volume.get_value())
                self.fs_osd_timer = GLib.timeout_add_seconds(8, self._fs_osd_hide_timeout)
            else:
                self.fs_remote_revealer.set_reveal_child(False)

        def build_compact_channel_menu(self):
            popover = Gtk.Popover()
            popover.set_has_arrow(True)
            popover.set_autohide(True)
            self.channel_popover = popover
            popover.connect('notify::visible',
                lambda _w, _prop: self.render_quick_channels() if popover.get_visible() else None)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            content.set_margin_start(10)
            content.set_margin_end(10)
            content.set_margin_top(10)
            content.set_margin_bottom(10)
            self.quick_search = Gtk.SearchEntry(placeholder_text=tr("Buscar canal…"))
            self.quick_search.connect("search-changed", lambda *_: self.render_quick_channels())
            content.append(self.quick_search)
            self.quick_favs = Gtk.CheckButton(label=tr("Solo favoritos"))
            self.quick_favs.connect("toggled", lambda *_: self.render_quick_channels())
            content.append(self.quick_favs)
            self.quick_scroller = Gtk.ScrolledWindow()
            self.quick_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            self.quick_scroller.set_min_content_width(255)
            self.quick_scroller.set_min_content_height(300)
            self.quick_scroller.set_max_content_height(430)
            self.quick_listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
            self.quick_listbox.add_css_class("iptv-list")
            self.quick_listbox.connect("row-activated", self.quick_channel_activated)
            self.quick_scroller.set_child(self.quick_listbox)
            content.append(self.quick_scroller)
            self.quick_count = Gtk.Label(label="", xalign=0)
            self.quick_count.add_css_class("iptv-info")
            content.append(self.quick_count)
            popover.set_child(content)
            self.channel_menu.set_popover(popover)

        def render_quick_channels(self):
            if not hasattr(self, 'quick_listbox'):
                return
            self._syn_beta_quick_token = getattr(self, '_syn_beta_quick_token', 0) + 1
            token = self._syn_beta_quick_token
            while row := self.quick_listbox.get_first_child():
                self.quick_listbox.remove(row)
            if not self.channel_popover.get_visible():
                return
            query = norm(self.quick_search.get_text())
            channels = [ch for ch in self.channels
                        if (not query or query in norm(ch.name) or query in norm(ch.group))
                        and (not self.quick_favs.get_active() or ch.favorite_id in self.favorites)]
            if self.quick_favs.get_active():
                channels = syn_fav_sort.order_channels(
                    channels, self.profile.get('favorites', []))
            self.quick_count.set_text(f'{min(len(channels), 160)} de {len(channels)} canales')
            portion = channels[:160]
            position = 0
            def add_batch():
                nonlocal position
                if token != self._syn_beta_quick_token or not self.channel_popover.get_visible():
                    return False
                for ch in portion[position:position + 18]:
                    row = Gtk.ListBoxRow()
                    row.channel = ch
                    line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                    line.set_margin_start(9)
                    line.set_margin_end(9)
                    line.set_margin_top(7)
                    line.set_margin_bottom(7)
                    line.append(self.channel_pill(ch, 92, 37))
                    label = Gtk.Label(label=display_channel_name(ch.name), xalign=0)
                    label.set_hexpand(True)
                    label.set_ellipsize(Pango.EllipsizeMode.END)
                    line.append(label)
                    line.append(self._favorite_heart_button(ch))
                    row.set_child(line)
                    self.quick_listbox.append(row)
                position += 18
                return position < len(portion)
            GLib.timeout_add(18, add_batch)

        def quick_channel_activated(self, _listbox, row):
            self.channel_popover.popdown()
            self.start_channel(row.channel)
            # Selección también en el panel grande, si está filtrada.
            for i, ch in enumerate(self.filtered):
                if ch.favorite_id == row.channel.favorite_id:
                    self.listbox.select_row(self.listbox.get_row_at_index(i))
                    break

        # SYN_CAST_BETA6: cast runs via a separate authenticated user service.
        # The GTK process never handles discovery, video relay or ffmpeg itself.
        # SYN_CAST_ICON_HOTFIX: icono Chromecast dedicado y resaltado visual.
        # SYN_CAST_ORANGE_VISUAL_6_2: solo cambia el color de los botones Chromecast.
        # SYN_MAC_CAST_GLYPH_V1: dibujo vectorial del símbolo Google Cast.
        # No depende de "chromecast-symbolic", que no es un icono GTK estándar.
        def _syn_cast_make_icon(self):
            canvas = Gtk.DrawingArea()
            canvas.set_content_width(21)
            canvas.set_content_height(21)
            canvas.set_halign(Gtk.Align.CENTER)
            canvas.set_valign(Gtk.Align.CENTER)
            canvas.set_draw_func(self._syn_cast_draw_icon)
            return canvas

        def _syn_cast_draw_icon(self, _area, cr, width, height):
            # Pantalla y ondas de emisión abajo a la izquierda, blanco sobre
            # el fondo naranja existente. Escala nítidamente en pantallas Retina.
            if width <= 0 or height <= 0:
                return
            scale = min(width, height) / 24.0
            cr.save()
            cr.translate((width - 24.0*scale)/2, (height - 24.0*scale)/2)
            cr.scale(scale, scale)
            cr.set_source_rgb(1.0, 1.0, 1.0)
            cr.set_line_width(2.0)
            cr.set_line_cap(1)  # cairo.LINE_CAP_ROUND
            cr.set_line_join(1)  # cairo.LINE_JOIN_ROUND
            # Marco de televisor con esquina inferior izquierda abierta.
            cr.move_to(2.4, 8.0)
            cr.line_to(2.4, 5.5)
            cr.curve_to(2.4, 4.2, 3.4, 3.2, 4.7, 3.2)
            cr.line_to(19.3, 3.2)
            cr.curve_to(20.7, 3.2, 21.7, 4.2, 21.7, 5.5)
            cr.line_to(21.7, 18.4)
            cr.curve_to(21.7, 19.7, 20.7, 20.7, 19.3, 20.7)
            cr.line_to(14.0, 20.7)
            cr.stroke()
            # Ondas de Google Cast, cuadrante inferior izquierdo.
            cr.arc(2.6, 20.8, 4.2, -1.5707963267948966, 0.0)
            cr.stroke()
            cr.arc(2.6, 20.8, 8.3, -1.5707963267948966, 0.0)
            cr.stroke()
            cr.rectangle(1.8, 18.1, 3.0, 3.0)
            cr.fill()
            cr.restore()

        def _syn_cast_apply_orange_style(self):
            # SYN_CAST_CONTRASTE_CLARO_6_5: por encima de Claro, Oscuro, Teal y acento.
            if getattr(self, '_syn_cast_orange_css', None) is not None:
                return
            css = Gtk.CssProvider()
            css.load_from_data(b"""
            window.iptv-tv button.syn-cast-button {
                background-image: none;
                background-color: #FF6B00;
                border: 1px solid #C94B00;
                border-radius: 9px;
                color: #FFFFFF;
                min-width: 32px;
                min-height: 32px;
                padding: 4px 7px;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.33);
            }
            window.iptv-tv button.syn-cast-button image { color: #FFFFFF; }
            window.iptv-tv button.syn-cast-button:hover {
                background-image: none;
                background-color: #FF8C29;
                color: #FFFFFF;
                border-color: #D75B00;
            }
            window.iptv-tv button.syn-cast-button:active,
            window.iptv-tv button.syn-cast-button:checked {
                background-image: none;
                background-color: #DC5900;
                color: #FFFFFF;
                border-color: #B84700;
            }
            window.iptv-tv button.syn-cast-button:disabled {
                background-image: none;
                background-color: #986044;
                color: #FFFFFF;
            }
            """)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 8)
            self._syn_cast_orange_css = css

        def _syn_cast_call(self, data, on_result):
            def worker():
                try:
                    import urllib.request
                    token = (Path.home() / 'Library/Application Support/SYN Alpha/cast-token').read_text('utf-8').strip()
                    request = urllib.request.Request(
                        'http://127.0.0.1:18976',
                        data=json.dumps(data).encode('utf-8'),
                        headers={'Content-Type': 'application/json', 'X-Syn-Token': token},
                        method='POST')
                    with urllib.request.urlopen(request, timeout=105) as resp:
                        result = json.loads(resp.read(20000))
                    if result.get('error'):
                        raise RuntimeError(result['error'])
                    GLib.idle_add(on_result, result, None)
                except Exception as exc:
                    # Do not expose the user's IPTV URLs in error messages.
                    msg = type(exc).__name__ + ': ' + str(exc)
                    if data.get('url'):
                        msg = msg.replace(str(data['url']), '[URL]')
                    GLib.idle_add(on_result, None, msg[:220])
            threading.Thread(target=worker, daemon=True).start()

        def _syn_cast_limit(self):
            try:
                count = int(self.profile.get('cast_max_connections', 1))
            except (ValueError,TypeError): count = 1
            return min(8, max(1,count))

        def _syn_cast_dvr_count(self):
            # Conservative: every running job consumes a slot. Never stop a DVR.
            try:
                jobs=self.dvr_store.read().get('jobs',[])
                return sum(1 for j in jobs if j.get('status')=='running')
            except Exception:
                return None  # Unknown => refuse instead of risking the provider.

        def _syn_cast_show_card(self):
            if not hasattr(self, '_syn_idle_hint'): return
            if getattr(self,'_syn_cast_only',False):
                dest = getattr(self,'_syn_cast_device_name','') or 'Chromecast'
                self._syn_idle_hint.set_text('RETRANSMITIENDO A…\n' + dest)
            else:
                self._syn_idle_hint.set_text(
                    'Double-click a channel to play' if LANGUAGE.startswith('en')
                    else 'Doble click en un canal para reproducir')
            if hasattr(self,'_syn_idle_sync'): self._syn_idle_sync()

        # SYN_CAST_SLIDER_720_1080_BETA6_5: GUI controls NEXT Cast session only.
        # The host reads ~/.config/syn/cast-quality when a new HLS stream starts.
        def _syn_cast_quality_read(self):
            path = Path.home() / 'Library/Application Support/SYN Alpha/cast-quality'
            try:
                raw = path.read_text(encoding='utf-8').strip()
            except OSError:
                raw = 'compatible'
            return 'alta' if raw == 'alta' else 'compatible'

        def _syn_cast_quality_write(self, value):
            if value not in ('compatible', 'alta'):
                return False
            path = Path.home() / 'Library/Application Support/SYN Alpha/cast-quality'
            temp_path = None
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                        dir=str(path.parent), prefix='.cast-quality-',
                        delete=False) as temp:
                    temp_path = Path(temp.name)
                    temp.write(value + '\n')
                os.chmod(temp_path, 0o600)
                os.replace(temp_path, path)
                return True
            except OSError:
                if temp_path is not None:
                    try: temp_path.unlink(missing_ok=True)
                    except OSError: pass
                return False

        def _syn_cast_menu(self, button):
            # SYN_MAC_572_MENUS: autohide en desplegables/popovers; cierre limpio.
            # SYN_MAC_ALPHA53_TOGGLE_CAST: un segundo clic cierra el desplegable.
            # Gtk.ToggleButton conserva el estado al abrir y al cerrar por clic exterior.
            previous = getattr(button, '_syn_cast_owned_popover', None)
            if not button.get_active():
                if previous is not None and previous.get_visible():
                    previous.popdown()
                return
            # No permitir dos menus Cast abiertos (normal + pantalla completa).
            other = getattr(self, '_syn_cast_active_button', None)
            if other is not None and other is not button and other.get_active():
                other.set_active(False)
            # Volver a crear el contenido solo al reabrir: lista de dispositivos actualizada.
            if previous is not None and previous.get_parent() is button:
                previous.unparent()
            pop = Gtk.Popover()
            pop.add_css_class('syn-cast-popover')
            pop.set_autohide(True)
            pop.set_parent(button)
            button._syn_cast_owned_popover = pop
            self._syn_cast_active_button = button
            def _closed_cast(closed_pop):
                if getattr(button, '_syn_cast_owned_popover', None) is closed_pop:
                    if button.get_active():
                        button.set_active(False)
                if getattr(self, '_syn_cast_active_button', None) is button:
                    self._syn_cast_active_button = None
            pop.connect('closed', _closed_cast)
            # 2.0.1: Cast lives inside a hover-only player toolbar. Keep its
            # anchor mapped while the independent GTK popover is open.
            if getattr(self, '_synplus_ui', False) and not getattr(self, '_synplus_in_fullscreen', False):
                synplus_layout.hold_chrome_for_cast(self, pop, Gtk)
            col=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7)
            col.add_css_class('syn-cast-panel')
            col.set_margin_top(10);col.set_margin_bottom(10)
            col.set_margin_start(12);col.set_margin_end(12)
            title=Gtk.Label(label='Retransmitir a un televisor',xalign=0)
            title.add_css_class('heading');col.append(title)
            row=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=12)
            row.append(Gtk.Label(label=tr('Conexiones máximas del perfil')))
            spin=Gtk.SpinButton.new_with_range(1,8,1)
            spin.add_css_class('syn-cast-numeric')
            spin.set_value(self._syn_cast_limit())
            def limit_changed(s):
                self.profile['cast_max_connections']=s.get_value_as_int()
                sources.save_config(self.cfg)
            spin.connect('value-changed',limit_changed)
            row.append(spin);col.append(row)
            # Only 720p and 1080p are offered; 480p is deliberately excluded.
            resolution_title = Gtk.Label(label='Calidad Chromecast', xalign=0)
            col.append(resolution_title)
            resolution_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, 1, 1)
            resolution_slider.set_draw_value(False)
            resolution_slider.set_digits(0)
            resolution_slider.set_round_digits(0)
            resolution_slider.set_has_origin(False)
            resolution_slider.set_size_request(210, -1)
            resolution_slider.set_hexpand(True)
            resolution_slider.add_mark(0, Gtk.PositionType.BOTTOM, '720p')
            resolution_slider.add_mark(1, Gtk.PositionType.BOTTOM, '1080p')
            resolution_slider.set_value(1 if self._syn_cast_quality_read()=='alta' else 0)
            col.append(resolution_slider)
            resolution_info = Gtk.Label(xalign=0)
            resolution_info.set_wrap(True)
            def describe_quality(value):
                selected = '1080p · Full HD (más CPU)' if value=='alta' else '720p · Recomendado'
                return selected + '\nSe aplicará al iniciar la siguiente retransmisión.'
            resolution_info.set_text(describe_quality(self._syn_cast_quality_read()))
            col.append(resolution_info)
            def resolution_changed(widget):
                selected = 'alta' if widget.get_value() >= 0.5 else 'compatible'
                if self._syn_cast_quality_write(selected):
                    resolution_info.set_text(describe_quality(selected))
                else:
                    resolution_info.set_text('No se pudo guardar la calidad. Comprueba los permisos.')
                    previous = 1 if self._syn_cast_quality_read()=='alta' else 0
                    if widget.get_value() != previous:
                        widget.set_value(previous)
            resolution_slider.connect('value-changed', resolution_changed)
            info=Gtk.Label(label='Se respetarán las grabaciones activas.\n'
                                      'El límite debe coincidir con el de tu proveedor.',xalign=0)
            info.set_wrap(True);col.append(info)
            if getattr(self,'_syn_cast_target_uuid',None):
                stop=Gtk.Button(label='Dejar de retransmitir y volver a SYN')
                stop.add_css_class('syn-cast-action')
                stop.connect('clicked',lambda *_:(pop.popdown(),self._syn_cast_stop()))
                col.append(stop)
            col.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
            busy=Gtk.Label(label='Buscando Chromecast…',xalign=0)
            col.append(busy)
            pop.set_child(col);pop.popup()
            def done(result,error):
                if not pop.get_parent() or not pop.get_visible(): return False
                col.remove(busy)
                if error:
                    message=Gtk.Label(label='Sin conexión con el servicio Cast.\n'+error,xalign=0)
                    message.set_wrap(True);col.append(message)
                    return False
                devices=result.get('devices',[])
                if not devices:
                    text=Gtk.Label(label='No se detectan dispositivos. Comprueba\n'
                                         'que el Mac y Chromecast estén en la misma red.',xalign=0)
                    col.append(text)
                for dev in devices:
                    b=Gtk.Button(label=dev['name'])
                    b.add_css_class('syn-cast-action')
                    b.connect('clicked',lambda _,d=dev:(pop.popdown(),self._syn_cast_play(d)))
                    col.append(b)
                return False
            self._syn_cast_call({'action':'devices'},done)

        # SYN_CAST_SHARED_RELAY_BETA6_4: player and TV share one upstream HLS relay.
        # SYN_CAST_REJOIN_SHARED_BETA6_5: returning to Cast channel must NOT
        # open an extra provider session, even when local TS is enabled.
        def _syn_cast_rejoin_shared(self, channel):
            local_url=getattr(self,'_syn_cast_shared_url',None)
            if not isinstance(local_url,str) or not local_url.startswith('http://127.0.0.1:18977/'):
                self.status.set_text(tr('Cast: relay compartido no disponible; no se abrirá una conexión duplicada.'))
                return
            if getattr(self,'_syn_cast_busy',False):
                return
            self._syn_cast_busy=True
            previous=self.current
            # Release Antena 3 and its timeshift BEFORE switching the bridge
            # back to one shared upstream. Otherwise a transient third session
            # can cause an IPTV provider to disconnect the TV after a few seconds.
            self._syn_reconnect_reset()
            if getattr(self,'_syn_ts_session',None):
                try:self._syn_ts_stop(restore=False)
                except Exception as exc:
                    self._syn_cast_busy=False
                    self.status.set_text('Cast: no se pudo cerrar el timeshift: '+type(exc).__name__)
                    return
            if self.area.player:self.area.player.stop()
            self.status.set_text(tr('Cast: recuperando canal compartido sin otra conexión IPTV…'))
            def done(result,error):
                self._syn_cast_busy=False
                if error or not result or not result.get('ok'):
                    self.status.set_text('Cast: '+(error or 'no se pudo compartir el canal'))
                    # Restore Antena 3 if the Cast service refused rejoining.
                    if previous:self.start_channel(previous)
                    return False
                self._syn_cast_shared_local=True
                self.current=channel
                self._syn_idle_layer.set_visible(False)
                self.blank_label.set_visible(False)
                self.now_playing.set_text(display_channel_name(channel.name))
                self.fs_channel_label.set_text(display_channel_name(channel.name))
                self.pause_button.set_sensitive(True)
                if self.area.player and self.area.player.ctx.value:
                    self.area.player.play(Channel(channel.name,channel.group,
                                                  local_url,channel.logo))
                else:
                    self.status.set_text(tr('Cast: libmpv no está listo para abrir el relay local.'))
                    return False
                self.status.set_text(tr('Cast: mismo canal en SYN y Chromecast · una conexión IPTV'))
                self._update_pause_label()
                self.update_programme()
                return False
            self._syn_cast_call({'action':'local_usage','shared':True},done)

        def _syn_cast_prepare_local_zap(self, channel):
            if self._syn_cast_dvr_count() is None or (self._syn_cast_dvr_count() + 2 > self._syn_cast_limit()):
                self.status.set_text('Cast: no hay conexiones libres para otro canal por las grabaciones DVR.')
                return
            self._syn_cast_busy=True
            def done(result,error):
                self._syn_cast_busy=False
                if error:
                    self.status.set_text('Cast: '+error)
                    return False
                # Reserve the second provider connection before opening MPV.
                self._syn_cast_shared_local=False
                self.start_channel(channel)
                return False
            self._syn_cast_call({'action':'local_usage','shared':False}, done)

        def _syn_cast_watch(self):
            if not getattr(self,'_syn_cast_target_uuid',None) or getattr(self,'_syn_cast_busy',False):
                return True
            if getattr(self,'_syn_cast_watch_inflight',False):
                return True
            self._syn_cast_watch_inflight=True
            def done(result,error):
                self._syn_cast_watch_inflight=False
                if error or result is None:
                    return False
                if result.get('active'):
                    return False
                # The bridge may yield automatically to an incoming DVR job.
                restore=bool(getattr(self,'_syn_cast_only',False) or
                             getattr(self,'_syn_cast_shared_local',False))
                channel=self.current
                self._syn_cast_target_uuid=None
                self._syn_cast_only=False
                self._syn_cast_shared_local=False
                self._syn_cast_origin_url=None
                self._syn_cast_shared_url=None
                self._syn_cast_show_card()
                if restore and channel:
                    self.start_channel(channel)
                self.status.set_text(tr('Cast finalizado; DVR y reproducción local protegidos.'))
                return False
            self._syn_cast_call({'action':'status'},done)
            return True

        def _syn_cast_play(self, device, channel=None):
            if getattr(self, '_syn_cast_busy', False):
                self.status.set_text(tr('Cast: espera a que termine la operación anterior.'))
                return
            channel = channel or self.current
            if not channel:
                self.status.set_text('Cast: selecciona primero un canal.')
                return
            if not channel.url.startswith(('http://','https://')):
                self.status.set_text('Cast: este canal no tiene una URL HTTP(S) compatible.')
                return
            occupied=self._syn_cast_dvr_count()
            if occupied is None:
                self.status.set_text('Cast: no se puede verificar el estado del DVR.')
                return
            capacity=self._syn_cast_limit()
            if occupied>=capacity:
                self.status.set_text(tr('Cast: todas las conexiones están ocupadas por el DVR.'))
                return
            local_playing = bool(self.current is not None)
            old_cast_only=bool(getattr(self,'_syn_cast_only',False))
            exclusive=old_cast_only or (occupied + 1 >= capacity)
            previous=self.current
            self._syn_cast_device_name=device.get('name','Chromecast')
            # One provider connection for both local and TV: release local MPV
            # and optional timeshift upstream BEFORE starting FFmpeg. This also
            # avoids a short-lived third upstream connection on slow providers.
            if hasattr(self,'_syn_ts_stop') and getattr(self,'_syn_ts_session',None):
                try:self._syn_ts_stop(restore=False)
                except Exception as exc:
                    self.status.set_text('Cast: no se pudo liberar el timeshift. '+type(exc).__name__)
                    return
            if self.area.player:self.area.player.stop()
            self._syn_cast_shared_local=False
            self._syn_cast_only=exclusive
            self._syn_cast_show_card()
            self.status.set_text(tr('Cast: preparando retransmisión compartida…'))
            ua=getattr(syn_dvr,'VLC_UA','VLC/3.0.21 LibVLC/3.0.21')
            # A relay/remux is needed for .ts and provider-specific User-Agent.
            self._syn_cast_busy=True
            def done(result,error):
                self._syn_cast_busy=False
                if error:
                    self.status.set_text('Cast: '+error)
                    self._syn_cast_only=False
                    self._syn_cast_shared_local=False
                    self._syn_cast_show_card()
                    if previous:self.start_channel(previous)
                    return False
                local_url=result.get('local_url')
                if not exclusive and not (isinstance(local_url,str) and
                        local_url.startswith('http://127.0.0.1:18977/')):
                    self.status.set_text(tr('Cast: puente antiguo, falta el relay local. Detén Cast.'))
                    # Do not open an extra provider session; stop Cast safely.
                    self._syn_cast_target_uuid=device['id']
                    self._syn_cast_stop()
                    return False
                self._syn_cast_target_uuid=device['id']
                self.current=channel
                self._syn_cast_device_name=result.get('name',device['name'])
                self.now_playing.set_text(display_channel_name(channel.name))
                self.fs_channel_label.set_text(display_channel_name(channel.name))
                self._syn_cast_shared_local=not exclusive
                self._syn_cast_origin_url=channel.url
                self._syn_cast_shared_url=local_url if isinstance(local_url,str) else None
                if not exclusive:
                    # Same HLS segments as Chromecast, no second IPTV request.
                    self._syn_idle_layer.set_visible(False)
                    self.area.player.play(Channel(channel.name,channel.group,
                                                  local_url,channel.logo))
                self._syn_cast_show_card()
                self.status.set_text('Retransmitiendo a '+self._syn_cast_device_name)
                return False
            self._syn_cast_call({'action':'play','device':device['id'],
                                 'url':channel.url,'title':display_channel_name(channel.name),
                                 'ua':ua,'relay':True,
                                 'capacity':capacity,'exclusive':exclusive},done)

        def _syn_cast_restore(self):
            def done(result,error):
                if not error and result and result.get('active'):
                    self._syn_cast_target_uuid=result.get('device')
                    self._syn_cast_device_name=result.get('name') or 'Chromecast'
                    self._syn_cast_only=bool(result.get('exclusive'))
                    self._syn_cast_shared_local=bool(result.get('local_shared'))
                    self._syn_cast_shared_url=result.get('local_url')
                    # The origin channel is unknown after an app restart: no
                    # automatic guess from the title or another provider URL.
                    self._syn_cast_origin_url=None
                    self._syn_cast_show_card()
                    self.status.set_text('Cast activo: '+self._syn_cast_device_name)
                return False
            self._syn_cast_call({'action':'status'},done)
            return False

        def _syn_cast_stop(self):
            if getattr(self,'_syn_cast_busy',False):
                self.status.set_text(tr('Cast: operación en curso.'))
                return
            restore=bool(getattr(self,'_syn_cast_only',False))
            shared=bool(getattr(self,'_syn_cast_shared_local',False))
            channel=self.current
            self._syn_cast_busy=True
            def done(result,error):
                self._syn_cast_busy=False
                if error:
                    self.status.set_text('Cast: '+error)
                    return False
                self._syn_cast_target_uuid=None
                self._syn_cast_only=False
                self._syn_cast_shared_local=False
                self._syn_cast_origin_url=None
                self._syn_cast_shared_url=None
                self._syn_cast_show_card()
                if (restore or shared) and channel:
                    # The HLS relay has stopped; switch back to the provider.
                    self.start_channel(channel)
                else:
                    self.status.set_text('Cast detenido.')
                return False
            self._syn_cast_call({'action':'stop'},done)

        def _syn_cast_zap(self,channel):
            if getattr(self,'_syn_cast_busy',False):
                self.status.set_text('Cast: espera a que termine el cambio de canal.')
                return
            if not getattr(self,'_syn_cast_target_uuid',None):
                if getattr(self,'_syn_cast_busy',False):
                    self.status.set_text('Cast: esperando a que el televisor conecte.')
                    return
                self._syn_cast_only=False
                self.start_channel(channel)
                return
            self._syn_cast_play({'id':self._syn_cast_target_uuid,
                                 'name':self._syn_cast_device_name},channel)

        def _arrange_toolbar(self, compact):
            for child in self.toolbar_widgets:
                if child.get_parent() == self.strip:
                    self.strip.remove(child)
            play, pause, stop, rec, shot, speaker, slider, info, full = self.toolbar_widgets
            if compact:
                layout = ((play, 0, 0, 1), (pause, 1, 0, 1),
                          (stop, 2, 0, 1), (rec, 3, 0, 1),
                          (shot, 4, 0, 1),
                          (speaker, 0, 1, 1), (slider, 1, 1, 2),
                          (info, 3, 1, 1), (full, 4, 1, 1))
            else:
                layout = tuple((w, i, 0, 1) for i, w in enumerate(self.toolbar_widgets))
            if getattr(self, '_synplus_ui', False):
                # Alfa 2.2: Play is redundant: channel rows start playback,
                # and Pause/Continue already resumes the current transmission.
                # Remove it from both regular AND compact grid arrangements.
                layout = tuple((widget, column - (1 if row == 0 else 0), row, span)
                               for widget, column, row, span in layout
                               if widget is not play)
            for widget, column, row, span in layout:
                self.strip.attach(widget, column, row, span, 1)
            self.volume.set_hexpand(compact)
            self.play_button.set_label(
                '▶' if getattr(self, '_synplus_ui', False)
                else (tr("▶ Ver") if compact else tr("▶  Reproducir")))
            self._update_pause_label()
            if hasattr(self, 'cast_button'):
                if self.cast_button.get_parent() == self.strip:
                    self.strip.remove(self.cast_button)
                if compact:
                    self.strip.attach(self.cast_button, 5, 1, 1, 1)
                else:
                    self.strip.attach(self.cast_button,
                        len(self.toolbar_widgets) - (1 if getattr(self, '_synplus_ui', False) else 0),
                        0, 1, 1)
        def _update_pause_label(self):
            paused = bool(self.area.player and self.area.player.paused())
            if getattr(self, '_synplus_ui', False):
                self.pause_button.set_label('▶' if paused else '⏸')
                return
            if self.compact_controls:
                self.pause_button.set_label("▶" if paused else "⏸")
            else:
                self.pause_button.set_label("▶ Continuar" if paused else tr("⏸ Pausa"))

        def _enforce_sidebar_width(self, pane, _pspec):
            if (self.compact_sidebar or self.fullscreen_mode or
                    getattr(self, '_clamping_sidebar', False)):
                return
            position = pane.get_position()
            if position >= 280:
                self._saved_paned_position = position
                return
            # No alterar la geometría de MPV ni crear un nuevo GLArea.
            self._clamping_sidebar = True
            try:
                pane.set_position(280)
            finally:
                self._clamping_sidebar = False

        def _syn_apply_startup_video_ratio(self):
            """Ajusta el tamaño de ventana una vez; después no impone proporción."""
            if not self._syn_startup_ratio_pending:
                return
            if self.is_fullscreen() or self.is_maximized() or self.fullscreen_mode:
                self._syn_startup_ratio_pending = False
                return
            window_w, window_h = self.get_width(), self.get_height()
            video_w, video_h = self.overlay.get_width(), self.overlay.get_height()
            # La primera asignación GTK puede tardar uno o varios ciclos.
            if min(window_w, window_h, video_w, video_h) <= 0:
                return
            self._syn_startup_ratio_pending = False
            desired_video_h = round(video_w * 9 / 16)
            delta = desired_video_h - video_h
            if abs(delta) >= 3:
                # set_default_size NO fija tamaño mínimo ni fuerza 16:9 después.
                self.set_default_size(window_w, max(1, window_h + delta))

        def _check_responsive_layout(self):
            if self.is_fullscreen() or self.fullscreen_mode:
                return True
            width = self.get_width()
            if width <= 0:
                return True
            video_width = self.overlay.get_width()
            # Medir el vídeo real tras el primer layout, antes del early-return.
            if self._syn_startup_ratio_pending:
                self._syn_apply_startup_video_ratio()
            if (width == self._last_window_width and
                    video_width == self._last_video_width):
                return True
            # Dos umbrales diferentes: primero la lista se convierte en menú,
            # después los controles pasan a dos filas. Histéresis pequeña
            # para que no parpadeen al arrastrar junto al umbral.
            # La anchura real del video también importa si el usuario
            # arrastra el divisor dejando una zona de reproducción mínima.
            next_sidebar = (width < (
                (1120 if not self.compact_sidebar else 1140)
                if getattr(self, '_synplus_ui', False)
                else (990 if not self.compact_sidebar else 1010)))
            next_controls = (width < (740 if not self.compact_controls else 760)
                             or (not next_sidebar and 0 < video_width < 520))
            if next_sidebar != self.compact_sidebar:
                if not self.compact_sidebar and self.paned.get_position() >= 220:
                    self._saved_paned_position = self.paned.get_position()
                self.compact_sidebar = next_sidebar
                self.sidebar.set_visible(not next_sidebar and not getattr(self, '_synplus_maxi_mode', False))
                self.channel_menu.set_visible(next_sidebar and not getattr(self, '_synplus_maxi_mode', False))
                self.paned.set_wide_handle(not next_sidebar)
                if next_sidebar:
                    self.paned.add_css_class("iptv-fullscreen-paned")
                    self.paned.set_position(0)
                    self.render_quick_channels()
                else:
                    self.channel_popover.popdown()
                    self.paned.remove_css_class("iptv-fullscreen-paned")
                    usable = max(280, width - 485)
                    self.paned.set_position(max(280, min(usable, self._saved_paned_position)))
            if next_controls != self.compact_controls:
                self.compact_controls = next_controls
                self._arrange_toolbar(next_controls)
            tiny = width < 510
            if tiny != self._tiny_header:
                self._tiny_header = tiny
                self.header_title.set_markup("<b>SYN</b>")
                self.resolution.set_visible(not tiny)
            self._last_window_width = width
            self._last_video_width = video_width
            if getattr(self, '_synplus_ui', False):
                synplus_layout.adapt(self, width)
            return True

        def player_ready(self):
            self.status.set_text(tr("SYN preparado · MPV integrado · ajustes activos desde el inicio"))
            if self.pending_channel:
                channel = self.pending_channel
                self.pending_channel = None
                self.start_channel(channel)

        def player_failed(self, reason):
            self.status.set_text(tr("No se pudo integrar libmpv: ") + reason)
            self.blank_label.set_text(tr("No se pudo iniciar el vídeo\n\n") + reason)

        def player_status(self, text, failed):
            if failed and getattr(self, '_syn_ts_ready', False):
                self._syn_ts_stop(restore=True)
                self.status.set_text('Timeshift no compatible con este canal; recuperado el directo.')
                return
            if failed and hasattr(self, '_syn_reconnect_watch') and self.current:
                self._syn_reconnect_watch.error(time.monotonic())
            if text == 'Reproduciendo': text = tr('Reproduciendo')
            if failed:
                self.status.set_text(text)
                if self.area.player:
                    self.area.player.write_diag()
            elif self.current:
                self.status.set_text(text + " · " + self.current.name)

        def change_profile(self, dropdown, *_):
            if getattr(self,'_syn_cast_target_uuid',None):
                self.status.set_text(tr('Detén Cast antes de cambiar de perfil IPTV.'))
                ix=next((i for i,p in enumerate(self.cfg['profiles'])
                         if p.get('id')==self.profile.get('id')),None)
                if ix is not None and dropdown.get_selected()!=ix:
                    dropdown.set_selected(ix)
                return
            ix = dropdown.get_selected()
            if ix >= len(self.cfg['profiles']): return
            profile = self.cfg['profiles'][ix]
            if profile.get('id') == self.profile.get('id'): return
            self.stop()
            self.profile = profile
            self.cfg['selected'] = profile['id']
            self.favorites = set(profile.get('favorites', []))
            sources.save_config(self.cfg)
            self.guide, self.epg_aliases = {}, {}
            self.load_channels()

        def load_channels(self):
            self._source_generation += 1
            self._syn_movies = []
            self._syn_series = []
            self._syn_catalog_busy = self.profile.get('type') == 'xtream'
            self._syn_portal_update_counters()
            token = self._source_generation
            self.status.set_text(tr('Loading profile') + ' «' + self.profile['name'] + '»…')
            self.channels = []
            self._refresh_categories()
            self._syn_portal_update_counters()
            # Network and XMLTV must never block GTK, even for a file source.
            profile = dict(self.profile)
            def worker():
                try:
                    channels = sources.load_channels(profile, user_agent=sources.metadata_user_agent(self.player_options))
                    GLib.idle_add(self._channels_loaded, token, channels, None)
                except Exception as exc:
                    GLib.idle_add(self._channels_loaded, token, None, exc)
            threading.Thread(target=worker, name='syn-playlist', daemon=True).start()

        def _channels_loaded(self, token, channels, error):
            if token != self._source_generation: return False
            if error:
                # Never display URL/credentials from urllib exceptions.
                if isinstance(error, ValueError):
                    message = str(error) if 'http' not in str(error).lower() else tr('Comprueba los datos de la fuente.')
                else: message = type(error).__name__ + tr(' al cargar la fuente (revisa URL o credenciales).')
                self.status.set_text(tr('No se pudo cargar el perfil: ') + message)
                self._syn_catalog_busy = False
                self._syn_catalog_errors = ['movies', 'series']
                self._syn_portal_update_counters()
                return False
            if self.profile.get('type') == 'xtream':
                self.channels = channels
                self._syn_local_movies = []
                self._syn_local_series = []
            else:
                tv, movies, series = syn_catalog.partition_channels(channels)
                self.channels = tv
                self._syn_local_movies = syn_catalog.local_entries(movies, 'movies')
                self._syn_local_series = syn_catalog.local_series_catalog(series)
            if os.environ.get('SYN_LOGO_DEBUG') == '1':
                test_visible = self.channels[:250]
                has_logo = [ch.logo for ch in test_visible
                            if ch.logo.startswith(('http://', 'https://'))]
                in_cache = sum(sources.logo_path(url).is_file() for url in has_logo)
                print(f'SYN_BETA_LOGO_RESUMEN: total={len(self.channels)} '
                      f'primeros_250_con_url={len(has_logo)} cache={in_cache}',
                      file=sys.stderr, flush=True)
            self.dvr_update_channels()
            self._refresh_categories()
            self._syn_portal_catalog_refresh()
            self.status.set_text(f"SYN · {len(channels)} {tr('channels loaded')} · {tr('profile')}: {self.profile['name']}")
            self.load_guide()
            return False

        def _refresh_categories(self):
            item = self.category.get_selected_item()
            prev = self.category_names[self.category.get_selected()] if item and self.category.get_selected() < len(self.category_names) else 'Todas las categorías'
            self.category_names = ['Todas las categorías'] + sorted({c.group for c in self.channels})
            saved_category = self._restore_ui.pop('category', None) if self.channels else self._restore_ui.get('category')
            if saved_category in self.category_names:
                prev = saved_category
            self.category.set_model(Gtk.StringList.new([tr('Todas las categorías') if c == 'Todas las categorías' else c for c in self.category_names]))
            self.category.set_selected(self.category_names.index(prev) if prev in self.category_names else 0)
            if hasattr(self, 'fs_category'):
                selected_item = self.fs_category.get_selected_item()
                old_fs = self.category_names[self.fs_category.get_selected()] if selected_item and self.fs_category.get_selected() < len(self.category_names) else 'Todas las categorías'
                self.fs_category.set_model(Gtk.StringList.new([tr('Todas las categorías') if c == 'Todas las categorías' else c for c in self.category_names]))
                self.fs_category.set_selected(self.category_names.index(old_fs) if old_fs in self.category_names else 0)
            self.render_list()
            if self.guide_open:
                self.guide_render_categories()
                self.guide_render_rows()

        def load_guide(self, force=False):
            profile = dict(self.profile)
            token = self._source_generation
            if not sources.profile_epg_url(profile):
                self.guide, self.epg_aliases = {}, {}
                self.update_programme()
                return
            def worker():
                try:
                    data = sources.get_epg(profile, force=force, user_agent=sources.metadata_user_agent(self.player_options))
                    GLib.idle_add(self._guide_loaded, token, data, None)
                except Exception as exc:
                    GLib.idle_add(self._guide_loaded, token, None, type(exc).__name__)
            threading.Thread(target=worker, name='syn-epg', daemon=True).start()

        def _guide_loaded(self, token, data, error):
            if token != self._source_generation: return False
            if error:
                self.program_label.set_text(tr('EPG: no se pudo consultar (') + error + ')')
            else:
                self.guide, self.epg_aliases = data
                self.update_programme()
                if self.guide_open:
                    self.guide_render_rows()
            return False

        def update_programme(self):
            if not self.current:
                self.program_label.set_text(tr('EPG: selecciona un canal'))
                self.fs_epg_label.set_text(tr('Sin información EPG'))
                self.fs_next_label.set_text('')
                return
            now, next_items = sources.now_next(self.current, self.guide, self.epg_aliases)
            if now:
                label = tr('Ahora  ') + format_time(now[0]) + '–' + format_time(now[1]) + ' · ' + now[2]
            elif next_items:
                label = tr('Próximo  ') + format_time(next_items[0][0]) + ' · ' + next_items[0][2]
            else:
                label = tr('EPG no disponible para este canal')
            self.program_label.set_text(label)
            self.fs_epg_label.set_text(label)
            if next_items:
                nxt = next_items[0]
                self.fs_next_label.set_text(tr('A continuación   ') + format_time(nxt[0]) + '–' + format_time(nxt[1]) + '  ·  ' + nxt[2])
            else:
                self.fs_next_label.set_text('')

        def _logo_selected_channel(self):
            row = self.listbox.get_selected_row()
            return row.channel if row and hasattr(row, 'channel') else self.current

        def choose_custom_logo(self, _widget=None, channel=None):
            ch = channel or self._logo_selected_channel()
            if not ch:
                self.status.set_text(tr('Selecciona primero un canal para cambiar su logo.'))
                return
            dialog = Gtk.FileDialog(title='Logo personalizado de ' + ch.name)
            flt = Gtk.FileFilter()
            flt.set_name('Imágenes PNG, JPG y WebP')
            for ext in ('*.png','*.jpg','*.jpeg','*.webp'):
                flt.add_pattern(ext)
            model = Gio.ListStore.new(Gtk.FileFilter)
            model.append(flt)
            dialog.set_filters(model)
            def chosen(picker, result):
                try:
                    f = picker.open_finish(result)
                    path = f.get_path() if f else None
                    if not path:
                        self.status.set_text(tr('No se puede leer la imagen seleccionada.'))
                        return
                    # Validación en GTK antes de almacenarla en el perfil.
                    GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 150, 90, True)
                    sources.install_custom_logo(self.profile, ch, path)
                    sources.save_config(self.cfg)
                    self._redraw_logos()
                    self.status.set_text(tr('Logo personalizado guardado para ') + ch.name)
                except (GLib.Error, OSError, ValueError) as exc:
                    self.status.set_text(tr('No se pudo importar el logo: ') + str(exc)[:170])
            dialog.open(self, None, chosen)

        def choose_custom_logo_url(self, _widget=None, channel=None):
            ch = channel or self._logo_selected_channel()
            if not ch:
                self.status.set_text(tr('Selecciona un canal para cambiar su logo.'))
                return
            dialog = Gtk.Dialog(title='Logo desde URL · ' + ch.name, transient_for=self, modal=True)
            dialog.set_default_size(440, -1)
            dialog.add_button(tr('Cancelar'), Gtk.ResponseType.CANCEL)
            dialog.add_button('Descargar logo', Gtk.ResponseType.ACCEPT)
            area = dialog.get_content_area()
            area.set_spacing(12)
            area.set_margin_top(16)
            area.set_margin_bottom(16)
            area.set_margin_start(18)
            area.set_margin_end(18)
            explanation = Gtk.Label(label=tr('Pega la dirección HTTPS o HTTP de una imagen PNG, JPG o WebP.'))
            explanation.set_xalign(0)
            explanation.set_wrap(True)
            area.append(explanation)
            entry = Gtk.Entry()
            entry.set_placeholder_text('https://ejemplo.com/logos/canal.png')
            entry.set_activates_default(True)
            area.append(entry)
            note = Gtk.Label(label=tr('Máximo 8 MiB. SYN guarda una copia local; no almacena la URL.'))
            note.set_xalign(0)
            note.set_wrap(True)
            note.add_css_class('iptv-details')
            area.append(note)
            dialog.set_default_response(Gtk.ResponseType.ACCEPT)

            def on_response(win, response):
                url = entry.get_text().strip()
                win.destroy()
                if response != Gtk.ResponseType.ACCEPT:
                    return
                try:
                    sources.require_http(url)
                except ValueError:
                    self.status.set_text(tr('Logo: introduce una URL http:// o https:// válida.'))
                    return
                self.status.set_text(tr('Descargando logo para ') + ch.name + '…')
                profile = self.profile
                agent = sources.metadata_user_agent(self.player_options)
                def worker():
                    try:
                        # No descargar en el hilo GTK: el servidor puede tardar.
                        data = sources.download_custom_logo_url(url, user_agent=agent)
                        def complete():
                            try:
                                sources.install_custom_logo_bytes(profile, ch, data)
                                sources.save_config(self.cfg)
                                self._redraw_logos()
                                self.status.set_text(tr('Logo desde URL guardado para ') + ch.name)
                            except (OSError, ValueError) as exc:
                                self.status.set_text(tr('No se pudo guardar el logo: ') + str(exc)[:150])
                            return False
                        GLib.idle_add(complete)
                    except Exception as exc:
                        # No mostrar URL ni posibles credenciales en los errores.
                        msg = 'No se pudo descargar el logo (' + type(exc).__name__ + ').'
                        GLib.idle_add(lambda: (self.status.set_text(msg), False)[1])
                threading.Thread(target=worker, daemon=True, name='syn-custom-logo-url').start()
            dialog.connect('response', on_response)
            dialog.present()

        def open_logo_context_menu(self, pill, ch, x=0, y=0):
            """Menú contextual con clic secundario sobre cualquier pastilla."""
            menu = getattr(pill, '_syn_logo_context', None)
            if menu is None:
                menu = Gtk.Popover()
                menu.set_has_arrow(True)
                menu.set_autohide(True)
                menu.set_position(Gtk.PositionType.BOTTOM)
                menu.set_parent(pill)
                menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                for label, callback in (
                    (tr('Cambiar logo… (archivo)'), lambda: self.choose_custom_logo(channel=ch)),
                    (tr('Cambiar logo… (URL)'), lambda: self.choose_custom_logo_url(channel=ch)),
                    (tr('Restaurar logo original'), lambda: self.restore_channel_logo(ch)),
                ):
                    btn = Gtk.Button(label=label)
                    btn.add_css_class('flat')
                    btn.set_halign(Gtk.Align.FILL)
                    def action(_button, handler=callback):
                        menu.popdown()
                        handler()
                    btn.connect('clicked', action)
                    menu_box.append(btn)
                menu_box.set_margin_top(8)
                menu_box.set_margin_bottom(8)
                menu_box.set_margin_start(8)
                menu_box.set_margin_end(8)
                menu.set_child(menu_box)
                pill._syn_logo_context = menu
            rect = Gdk.Rectangle()
            rect.x = int(x); rect.y = int(y)
            rect.width = 1; rect.height = 1
            menu.set_pointing_to(rect)
            menu.popup()

        def restore_channel_logo(self, channel):
            sources.reset_custom_logo(self.profile, channel)
            sources.save_config(self.cfg)
            self._redraw_logos()
            self.status.set_text(tr('Logo de proveedor restaurado para ') + channel.name)

        def reset_selected_logo(self, *_):
            ch = self._logo_selected_channel()
            if not ch: return
            sources.reset_custom_logo(self.profile, ch)
            sources.save_config(self.cfg)
            self._redraw_logos()
            self.status.set_text(tr('Logo de proveedor restaurado para ') + ch.name)

        def _redraw_logos(self):
            preview = getattr(self, '_logo_settings_preview', None)
            if preview:
                ch, container = preview
                if container.get_root() is not None:
                    while (item := container.get_first_child()) is not None:
                        container.remove(item)
                    if ch: container.append(self.channel_pill(ch, 148, 58))
            self.render_list()
            if self.guide_open:
                self.guide_render_rows()
            if getattr(self, 'fs_remote_open', False):
                self.render_fs_channels()

        def _channel_logo_path(self, ch):
            return sources.custom_logo_path(self.profile, ch)

        def _logo_palette_index(self, pixbuf):
            n = pixbuf.get_n_channels()
            width, height = pixbuf.get_width(), pixbuf.get_height()
            if width <= 0 or height <= 0 or n < 3: return 6
            data = pixbuf.get_pixels()
            stride = pixbuf.get_rowstride()
            return logo_color_bucket(self._logo_samples(pixbuf))

        def _logo_samples(self, pixbuf):
            n = pixbuf.get_n_channels()
            data = pixbuf.get_pixels()
            width, height = pixbuf.get_width(), pixbuf.get_height()
            stride = pixbuf.get_rowstride()
            samples = []
            step = max(1, int(max(width, height) / 32))
            for y in range(0, height, step):
                for x in range(0, width, step):
                    j = y * stride + x * n
                    samples.append((data[j],data[j+1],data[j+2],data[j+3] if n == 4 else 255))
            return samples

        def _draw_channel_logo(self, area, cr, width, height):
            """Pinta un logo sin que la imagen pueda alterar el layout GTK.

            Gtk.Picture negocia su tamaño natural según la proporción del logo;
            Gtk.DrawingArea solo anuncia el lienzo fijo 108 x 38.
            """
            pix = getattr(area, '_syn_pixbuf', None)
            if pix is None:
                return
            x, y = logo_canvas_offset(width, height,
                                      pix.get_width(), pix.get_height())
            # GTK4 conserva esta API Cairo (deprecated desde GTK 4.20, pero
            # disponible en GTK 4.x, incluyendo Fedora 45). Solo dibujamos.
            Gdk.cairo_set_source_pixbuf(cr, pix, x, y)
            cr.paint()

        def _prepare_logo_pixbuf(self, path):
            # Off the GTK main loop. Keep the fitted content and alpha trimming.
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 160, 160, True)
            x, y, w, h = logo_visible_bounds(
                pix.get_pixels(), pix.get_width(), pix.get_height(),
                pix.get_rowstride(), pix.get_n_channels())
            if (0 < w < pix.get_width()) or (0 < h < pix.get_height()):
                pix = GdkPixbuf.Pixbuf.new_subpixbuf(pix, x, y, w, h)
            size = (pix.get_width(), pix.get_height())
            fitted = fitted_logo_size(*size)
            if fitted != size:
                pix = pix.scale_simple(*fitted, GdkPixbuf.InterpType.BILINEAR)
            return pix

        def _publish_logo_pixbuf(self, pix, image, pill):
            # Run ONLY on GTK main loop. Gtk.Picture stays inside the fixed pill.
            try:
                if pix is None or pill is None:
                    return False
                picture = getattr(pill, '_syn_async_logo_picture', None)
                if picture is None:
                    picture = Gtk.Picture()
                    picture.set_content_fit(Gtk.ContentFit.CONTAIN)
                    picture.set_can_shrink(True)
                    picture.set_size_request(108, 38)
                    picture.set_hexpand(False)
                    picture.set_vexpand(False)
                    picture.set_halign(Gtk.Align.CENTER)
                    picture.set_valign(Gtk.Align.CENTER)
                    picture.set_visible(False)
                    # Overlay, NEVER Gtk.Box.append: the previous beta placed
                    # the logo beside the artwork and could shift Favorites.
                    pill.add_overlay(picture)
                    pill.set_measure_overlay(picture, False)
                    pill.set_clip_overlay(picture, True)
                    pill._syn_async_logo_picture = picture
                picture.set_paintable(Gdk.Texture.new_for_pixbuf(pix))
                image._syn_pixbuf = pix
                pill.remove_css_class('syn-art-fullbleed')
                label = getattr(pill, 'fallback_label', None)
                if label:
                    label.set_visible(False)
                # Palette sampling is cheap on the final 108x38 thumbnail.
                try:
                    prior = getattr(pill, 'hue_class', 'syn-logo-pill-h6')
                    pill.remove_css_class(prior)
                    samples = self._logo_samples(pix)
                    new_class = ('syn-logo-pill-h' + str(logo_color_bucket(samples))
                                 + '-' + logo_contrast_variant(samples))
                    pill.add_css_class(new_class)
                    pill.hue_class = new_class
                except Exception:
                    pass  # visual palette is optional; never suppress the logo
                image.set_visible(False)
                picture.set_visible(True)
                if os.environ.get('SYN_LOGO_DEBUG') == '1':
                    count = getattr(self, '_syn_beta_logo_shown', 0) + 1
                    self._syn_beta_logo_shown = count
                    if count <= 5:
                        print('SYN_BETA_LOGO: imagen mostrada; '
                              f'{pix.get_width()}x{pix.get_height()}',
                              file=sys.stderr, flush=True)
            except Exception as exc:
                if os.environ.get('SYN_LOGO_DEBUG') == '1':
                    print('SYN_BETA_LOGO_ERROR: ' + type(exc).__name__,
                          file=sys.stderr, flush=True)
            return False

        def _fill_logo_image(self, path, image, pill=None):
            # Custom logos are few; provider logos use the worker queue below.
            try:
                pix = self._prepare_logo_pixbuf(path)
                return self._publish_logo_pixbuf(pix, image, pill)
            except Exception as exc:
                if os.environ.get('SYN_LOGO_DEBUG') == '1':
                    print('SYN_BETA_LOGO_PREP_ERROR: ' + type(exc).__name__,
                          file=sys.stderr, flush=True)
            return False

        def _draw_channel_logo_or_art(self, area, cr, width, height):
            # El logo real gana SIEMPRE; el fallback solo cubre su ausencia.
            if getattr(area, '_syn_pixbuf', None) is not None:
                return self._draw_channel_logo(area, cr, width, height)
            from syn_fallback_art import draw_art_pill
            name, group = getattr(area, '_syn_art_id', ('SYN', 'TV'))
            draw_art_pill(cr, width, height, name, group)

        def channel_pill(self, ch, width=120, height=46):
            # Unico tamano para TODOS los canales, con o sin filtro favorito.
            width, height = 120, 46
            pill = Gtk.Overlay()
            pill.add_css_class('syn-logo-pill')
            pill.add_css_class('syn-logo-pill-h6')
            pill.hue_class = 'syn-logo-pill-h6'
            pill.set_size_request(width, height)
            pill.set_hexpand(False)
            pill.set_vexpand(False)
            pill.set_halign(Gtk.Align.CENTER)
            pill.set_valign(Gtk.Align.CENTER)
            pill.set_overflow(Gtk.Overflow.HIDDEN)
            pill.set_tooltip_text(ch.name + ' · ' + ch.group + tr(' · clic derecho para cambiar logo'))
            right_click = Gtk.GestureClick.new()
            right_click.set_button(3)
            right_click.connect('pressed',
                lambda _gesture, _n, x, y, c=ch, widget=pill:
                    self.open_logo_context_menu(widget, c, x, y))
            pill.add_controller(right_click)
            # Gtk.DrawingArea no negocia un tamano intrinseco basado en
            # proporciones de la imagen. Su area fija es 108 x 38.
            pic = Gtk.DrawingArea()
            pic.add_css_class('syn-channel-logo-picture')
            pic.set_content_width(108)
            pic.set_content_height(38)
            pic.set_size_request(108, 38)
            pic.set_hexpand(False)
            pic.set_vexpand(False)
            pic.set_halign(Gtk.Align.CENTER)
            pic.set_valign(Gtk.Align.CENTER)
            pic.set_visible(False)
            pic.set_can_target(False)
            pic.set_draw_func(self._draw_channel_logo_or_art)
            # Cairo artwork is the base layer, including channels without a logo.
            # Gtk.Overlay paints it in the whole fixed-size 120×46 area.
            pill.set_child(pic)
            short = display_channel_name(ch.name)
            short = short if len(short) <= 22 else short[:19] + '…'
            fallback = Gtk.Label(label=short)
            fallback.add_css_class('syn-logo-fallback')
            fallback.set_ellipsize(Pango.EllipsizeMode.END)
            fallback.set_max_width_chars(16)
            # Preserve the old label as a hidden backup, without affecting
            # Gtk.Overlay's minimum size or any Favorites row width.
            pill.add_overlay(fallback)
            pill.set_measure_overlay(fallback, False)
            pill.set_clip_overlay(fallback, True)
            pill.fallback_label = fallback
            # BETA8_POP: imagen artística inicial, reemplazada por logo real al llegar.
            pic._syn_art_id = (display_channel_name(ch.name), ch.group)
            # Make only ART fill the entire outer 120x46 pill. Logos remain 108x38.
            pill.add_css_class('syn-art-fullbleed')
            pic.set_content_width(120)
            pic.set_content_height(46)
            pic.set_size_request(120, 46)
            fallback.set_visible(False)
            pic.set_visible(True)
            # Force the original SYN artistic substitute to render on map,
            # also for favorites and broken/nonexistent provider URLs.
            pic.connect('map', lambda area: area.queue_draw())
            custom = self._channel_logo_path(ch)
            if custom:
                self._fill_logo_image(custom, pic, pill)
            elif ch.logo and ch.logo.startswith(('http://', 'https://')):
                # Cached logos have highest priority and appear immediately,
                # without waiting behind other network requests in the pool.
                cached = sources.logo_path(ch.logo)
                if cached.is_file():
                    self._fill_logo_image(cached, pic, pill)
                else:
                    self._request_logo(ch.logo, pic, ch, pill)
            return pill

        # SYN_FAVORITOS_DRAG_BETA7: Gtk4 DnD, order scoped to the IPTV profile.
        def _syn_fav_drag_prepare(self, key):
            # Only inside the Favorites filter. Ordinary channel clicks are unchanged.
            if not self.favs.get_active() or key not in self.favorites:
                return None
            if not hasattr(self, '_syn_fav_drag_token'):
                self._syn_fav_drag_token = os.urandom(16).hex()
            return Gdk.ContentProvider.new_for_value(self._syn_fav_drag_token + '|' + key)

        # SYN_FAVORITOS_VISUAL_BETA7_1: mostrar LA FILA real bajo el puntero.
        def _syn_fav_drag_prepare_visual(self, source, row, key, x, y):
            payload = self._syn_fav_drag_prepare(key)
            if payload is not None:
                # La cadena interna sigue autenticando el DnD, pero no se ve.
                # GTK dibuja pastilla, nombre y corazon de la fila original.
                paintable = Gtk.WidgetPaintable.new(row)
                hot_x = max(0, min(int(x), max(0, row.get_width() - 1)))
                hot_y = max(0, min(int(y), max(0, row.get_height() - 1)))
                source.set_icon(paintable, hot_x, hot_y)
            return payload

        def _syn_fav_visual_style(self):
            if getattr(self, '_syn_fav_visual_css', None) is not None:
                return
            provider = Gtk.CssProvider()
            provider.load_from_data(b"""
                window.iptv-tv row.syn-fav-insert-before {
                    box-shadow: inset 0 4px 0 #FF6B00;
                }
                window.iptv-tv row.syn-fav-insert-after {
                    box-shadow: inset 0 -4px 0 #FF6B00;
                }
            """)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
            self._syn_fav_visual_css = provider

        def _syn_fav_clear_drop_marker(self):
            old = getattr(self, '_syn_fav_visual_target', None)
            if old is not None:
                old.remove_css_class('syn-fav-insert-before')
                old.remove_css_class('syn-fav-insert-after')
            self._syn_fav_visual_target = None
            self._syn_fav_visual_position = None
            self.listbox.drag_unhighlight_row()

        def _syn_fav_drag_end_visual(self, row):
            row.remove_css_class('syn-fav-dragging')
            self._syn_fav_clear_drop_marker()

        def _syn_fav_drag_leave_visual(self, row):
            if getattr(self, '_syn_fav_visual_target', None) is row:
                self._syn_fav_clear_drop_marker()

        def _syn_fav_attach_drag(self, row, channel):
            if not self.favs.get_active() or channel.favorite_id not in self.favorites:
                return
            row.set_tooltip_text('Arrastra para ordenar los favoritos')
            source = Gtk.DragSource.new()
            source.set_actions(Gdk.DragAction.MOVE)
            source.connect('prepare', lambda s, x, y, key=channel.favorite_id, r=row:
                           self._syn_fav_drag_prepare_visual(s, r, key, x, y))
            source.connect('drag-begin', lambda _s, _drag, r=row:
                           r.add_css_class('syn-fav-dragging'))
            source.connect('drag-end', lambda _s, _drag, _delete, r=row:
                           self._syn_fav_drag_end_visual(r))
            row.add_controller(source)

            target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
            target.connect('enter', lambda _t, _x, y, r=row:
                           self._syn_fav_drag_enter(r, y))
            target.connect('motion', lambda _t, _x, y, r=row:
                           self._syn_fav_drag_enter(r, y))
            target.connect('leave', lambda _t, r=row:
                           self._syn_fav_drag_leave_visual(r))
            target.connect('drop', lambda _t, value, _x, y, r=row:
                           self._syn_fav_drag_drop(value, r, y))
            row.add_controller(target)

        def _syn_fav_drag_enter(self, row, y):
            if not self.favs.get_active():
                return Gdk.DragAction(0)
            self._syn_fav_visual_style()
            direction = 'after' if y >= row.get_height() / 2 else 'before'
            old_row = getattr(self, '_syn_fav_visual_target', None)
            old_direction = getattr(self, '_syn_fav_visual_position', None)
            if old_row is row and old_direction == direction:
                return Gdk.DragAction.MOVE
            self._syn_fav_clear_drop_marker()
            self.listbox.drag_highlight_row(row)
            row.add_css_class('syn-fav-insert-' + direction)
            self._syn_fav_visual_target = row
            self._syn_fav_visual_position = direction
            return Gdk.DragAction.MOVE

        def _syn_fav_drag_drop(self, value, row, y):
            self._syn_fav_clear_drop_marker()
            if not self.favs.get_active() or not isinstance(value, str):
                return False
            token = getattr(self, '_syn_fav_drag_token', None)
            if not token or not value.startswith(token + '|'):
                return False
            original = value[len(token) + 1:]
            target_id = row.channel.favorite_id
            if original not in self.favorites or target_id not in self.favorites:
                return False
            previous = list(self.profile.get('favorites', []))
            updated = syn_fav_sort.move(
                syn_fav_sort.normalize(previous, self.favorites),
                original, target_id, after=(y > row.get_height() / 2))
            if updated == previous:
                return True
            self.profile['favorites'] = updated
            try:
                sources.save_config(self.cfg)
            except (OSError, ValueError):
                self.profile['favorites'] = previous
                self.status.set_text('No se pudo guardar el orden de favoritos.')
                return False
            # Never destroy the Gtk.ListBoxRow while GTK completes its DnD event.
            GLib.idle_add(self._syn_fav_refresh_after_drop)
            return True

        def _syn_fav_refresh_after_drop(self):
            self.render_list()
            self._syn_sync_favorite_guide()
            if hasattr(self, 'fs_list') and self.fs_remote_open:
                self.render_fs_channels()
            self.status.set_text('Orden de favoritos guardado.')
            return False

        def _channel_sidebar_row(self, ch):
            """UNA fila para todos los canales. El filtro Favoritos NO cambia el diseño.

            Recuperamos el diseño horizontal original de la lista general:
            pastilla, nombre limpio, corazón independiente. Ninguna tarjeta vertical
            especial para favoritos, Gtk.Overlay, ni botones con altura heredada.
            """
            row = Gtk.ListBoxRow()
            row.channel = ch
            row.add_css_class('iptv-row')
            row.add_css_class('syn-unified-channel-row')

            content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
            content.set_halign(Gtk.Align.FILL)
            content.set_hexpand(True)
            content.set_margin_start(10)
            # 20 px between the 40 px button and the overlay scrollbar.
            content.set_margin_end(20)
            content.set_margin_top(5)
            content.set_margin_bottom(5)

            content.append(self.channel_pill(ch, 120, 46))

            # Nombre a continuación de la pastilla, igual que en la antigua
            # lista general. Nunca mostramos grupo ni prefijos |ES|, [ES].
            name = Gtk.Label(label=display_channel_name(ch.name), xalign=0)
            name.add_css_class('syn-channel-display-name')
            name.set_hexpand(True)
            name.set_halign(Gtk.Align.FILL)
            name.set_ellipsize(Pango.EllipsizeMode.END)
            name.set_max_width_chars(18)
            name.set_tooltip_text(display_channel_name(ch.name))
            content.append(name)

            # The full 40px Gtk.Button captures the click and keyboard activation;
            # no overlapping GtkGestureClick near the ScrolledWindow scrollbar.
            heart = self._favorite_heart_button(ch)
            content.append(heart)
            row.set_child(content)
            self._syn_fav_attach_drag(row, ch)
            return row

        def render_list(self):
            self._syn_beta_list_token = getattr(self, '_syn_beta_list_token', 0) + 1
            token = self._syn_beta_list_token
            current = self.listbox.get_selected_row()
            selected_id = current.channel.favorite_id if current else None
            query = norm(self.search.get_text().strip())
            cat_idx = self.category.get_selected()
            cat = (self.category_names[cat_idx]
                   if cat_idx < len(self.category_names) else self.category_names[0])
            self.filtered = [ch for ch in self.channels if
                             (cat == 'Todas las categorías' or ch.group == cat) and
                             (not self.favs.get_active() or ch.favorite_id in self.favorites) and
                             (not query or query in norm(ch.name + ' ' + ch.group))]
            if self.favs.get_active():
                self.filtered = syn_fav_sort.order_channels(
                    self.filtered, self.profile.get('favorites', []))
            while (row := self.listbox.get_row_at_index(0)) is not None:
                self.listbox.remove(row)
            self.count.set_text(f"{tr('Showing')} {min(250, len(self.filtered))} "
                                f"{tr('of')} {len(self.channels)} · {tr('search to filter')}")
            self.render_quick_channels()
            portion = self.filtered[:250]
            position = 0
            selected = False
            def add_batch():
                nonlocal position, selected
                if token != self._syn_beta_list_token:
                    return False
                for ch in portion[position:position + 18]:
                    row = self._channel_sidebar_row(ch)
                    self.listbox.append(row)
                    if selected_id and ch.favorite_id == selected_id:
                        self.listbox.select_row(row)
                        selected = True
                position += 18
                if not selected and (not selected_id or position >= len(portion)):
                    first = self.listbox.get_row_at_index(0)
                    if first:
                        self.listbox.select_row(first)
                        selected = True
                if position >= len(portion):
                    if os.environ.get('SYN_LAYOUT_DEBUG') == '1':
                        GLib.timeout_add(900, self._debug_sidebar_geometry)
                    self._syn_sync_visible_guide_scope()
                    return False
                return True
            GLib.timeout_add(18, add_batch)

        def _debug_sidebar_geometry(self):
            self._layout_probe_pending = False
            try:
                row = self.listbox.get_row_at_index(0)
                if row is None:
                    print('SYN_LAYOUT: sin filas visibles', file=sys.stderr)
                    return False
                box = row.get_child()
                pill = box.get_first_child()
                name = pill.get_next_sibling()
                heart = name.get_next_sibling()
                widgets = [('row', row), ('box', box), ('pill', pill), ('name', name), ('heart', heart)]
                data = ' '.join(f'{n}={w.get_width()}x{w.get_height()}' for n,w in widgets)
                print(f'SYN_LAYOUT v{SYN_VERSION}: {data}; favoritos={self.favs.get_active()}', file=sys.stderr, flush=True)
            except Exception as e:
                print(f'SYN_LAYOUT: error: {e}', file=sys.stderr, flush=True)
            return False

        def _request_logo(self, url, widget, channel=None, pill=None):
            if channel:
                local = self._channel_logo_path(channel)
                if local:
                    self._fill_logo_image(local, widget, pill)
                    return
            if not url or not url.startswith(('http://', 'https://')):
                return
            key = (url, id(widget))
            if key in self._logo_requested:
                return
            self._logo_requested.add(key)
            def worker():
                try:
                    # HTTP and CPU thumbnail generation BOTH run off GTK.
                    path = sources.get_logo(
                        url, user_agent=sources.metadata_user_agent(self.player_options))
                    pix = self._prepare_logo_pixbuf(path)
                    GLib.idle_add(self._publish_logo_pixbuf, pix, widget, pill)
                except Exception as exc:
                    if os.environ.get('SYN_LOGO_DEBUG') == '1':
                        count = getattr(self, '_syn_beta_logo_errors', 0) + 1
                        self._syn_beta_logo_errors = count
                        if count <= 8:
                            print('SYN_BETA_LOGO_FETCH_ERROR: ' + type(exc).__name__,
                                  file=sys.stderr, flush=True)
                finally:
                    self._logo_requested.discard(key)
            try:
                self._logo_pool.submit(worker)
            except RuntimeError:
                self._logo_requested.discard(key)

        def _favorite_heart_button(self, channel):
            active = channel.favorite_id in self.favorites
            heart = Gtk.Button(label='♥' if active else '♡')
            heart.add_css_class('syn-favorite-heart')
            if active:
                heart.add_css_class('syn-heart-active')
            heart.set_size_request(40, 40)
            heart.set_halign(Gtk.Align.CENTER)
            heart.set_valign(Gtk.Align.CENTER)
            heart.set_hexpand(False)
            heart.set_tooltip_text(tr('Quitar de favoritos') if active
                                  else tr('Añadir a favoritos'))
            heart.connect('clicked', self._favorite_clicked, channel)
            return heart

        def _favorite_clicked(self, button, channel):
            # Defer rebuilding Gtk.ListBox until the 260ms animation finishes.
            # Removing the row immediately would destroy the animation.
            self.toggle_favorite(channel, animate_button=button)

        def toggle_favorite(self, channel, animate_button=None):
            key = channel.favorite_id
            active = key not in self.favorites
            if active:
                self.favorites.add(key)
            else:
                self.favorites.remove(key)
            self.profile['favorites'] = syn_fav_sort.normalize(
                self.profile.get('favorites', []), self.favorites)
            sources.save_config(self.cfg)
            if animate_button is None:
                self.render_list()
                self._syn_sync_favorite_guide()
                return
            animate_button.set_label('♥' if active else '♡')
            if active:
                animate_button.add_css_class('syn-heart-active')
            else:
                animate_button.remove_css_class('syn-heart-active')
            animate_button.set_tooltip_text(tr('Quitar de favoritos') if active
                                            else tr('Añadir a favoritos'))
            # Force the animation to restart if the user clicks repeatedly.
            animate_button.remove_css_class('syn-heart-animate')
            animate_button.add_css_class('syn-heart-animate')
            GLib.timeout_add(285, self._finish_favorite_animation)

        def _finish_favorite_animation(self):
            self.render_list()
            self._syn_sync_favorite_guide()
            return False

        def _syn_sync_visible_guide_scope(self):
            if not self.guide_open:
                return
            index = self.category.get_selected()
            selected_category = (self.category_names[index]
                                 if 0 <= index < len(self.category_names)
                                 else 'Todas las categorías')
            self.guide_category_name = (syn_favoritos.FAVORITES_CATEGORY
                                        if self.favs.get_active()
                                        else selected_category)
            self.guide_page = 0
            self._guide_reset_vertical = True
            self.guide_render_categories()
            self.guide_render_rows()

        def _syn_sync_favorite_guide(self):
            self._syn_sync_visible_guide_scope()

        def play_selected(self):
            if self.compact_sidebar and self.current:
                self.start_channel(self.current)
                return
            row = self.listbox.get_selected_row()
            if row:
                self.start_channel(row.channel)
            else:
                self.status.set_text(tr("Selecciona un canal en la lista."))

        def _syn_enforce_connection_limit(self):
            player = self.area.player
            if not player or not self.current or not syn_dvr.allowed_stream_url(self.current.url):
                return
            db = self.dvr_store.read()
            slots = syn_multistream.profile_limit(self.profile)
            if (syn_multistream.should_release_playback(db, self.profile.get('id'),
                                                        slots, self.current.url)
                    and player.active_url == self.current.url):
                player.stop()
                self.status.set_text(tr('DVR: conexiones ocupadas. Selecciona uno de los canales que se están grabando.'))

        # SYN_DVR_SHARED_124: no second IPTV session while viewing a recording.
        def _syn_dvr_playback_target(self, channel):
            """Return (local URL, waiting). Only trusted local DB drives routing."""
            if not syn_dvr.allowed_stream_url(channel.url):
                return None, False
            jobs = self.dvr_store.read().get('jobs', [])
            now = time.time()
            same = [j for j in jobs if isinstance(j, dict)
                    and j.get('url') == channel.url
                    and j.get('status') in ('running', 'scheduled')
                    and not j.get('stop_requested')]
            same.sort(key=lambda j: j.get('created', 0), reverse=True)
            # A running job wins even when other future jobs are scheduled.
            for job in same:
                if job.get('status') == 'running':
                    return (job.get('relay_url') or syn_dvr.syn_relay_url(job['id'])), True
            for job in same:
                if float(job.get('start', 0)) <= now + 3:
                    return None, True
            return None, False

        def _syn_follow_dvr(self):
            """Switch current channel to/from local relay without modifying DVR."""
            try:
                channel = self.current
                player = self.area.player
                if (not channel or not player or not player.ctx.value
                        or getattr(self, '_dvr_playing_file', False)
                        or not syn_dvr.allowed_stream_url(channel.url)):
                    return True
                url, waiting = self._syn_dvr_playback_target(channel)
                if getattr(self, '_syn_ts_session', None):
                    db = self.dvr_store.read()
                    if (url or syn_multistream.should_release_playback(
                            db, self.profile.get('id'),
                            syn_multistream.profile_limit(self.profile), channel.url)):
                        self._syn_ts_stop(restore=False)
                playing = player.active_url
                if url:
                    if playing != url:
                        player.play(Channel(channel.name, channel.group, url, channel.logo))
                        self.status.set_text(tr('DVR: viendo la señal compartida, sin segunda conexión IPTV'))
                elif waiting:
                    if playing == channel.url:
                        player.stop()  # Never displace the recording session.
                    if not playing or playing == channel.url:
                        self.status.set_text(tr('DVR: esperando al grabador o su reconexión…'))
                elif playing and playing.startswith('udp://127.0.0.1:'):
                    if not syn_multistream.should_release_playback(
                            self.dvr_store.read(), self.profile.get('id'),
                            syn_multistream.profile_limit(self.profile), channel.url):
                        player.play(channel)  # Return only with a free provider slot.
                elif playing == channel.url:
                    self._syn_enforce_connection_limit()
                if hasattr(self, '_syn_reattach_rec_button'):
                    self._syn_reattach_rec_button(self.dvr_store.read())
            except (ValueError, OSError, RuntimeError, AttributeError) as exc:
                self.status.set_text(tr('DVR compartido: ') + str(exc)[:130])
            return True

        def start_channel(self, channel):
            self._syn_portal_hide()
            if getattr(self,'_syn_cast_busy',False):
                self.status.set_text('Cast: espera a que se conecte el televisor.')
                return
            if getattr(self,'_syn_cast_only',False):
                return self._syn_cast_zap(channel)
            if getattr(self,'_syn_cast_target_uuid',None):
                # Returning to Cast's existing source MUST reuse its HLS URL.
                # Comparing source URLs supports duplicate entries in playlists.
                if getattr(self,'_syn_cast_origin_url',None)==channel.url:
                    if getattr(self,'_syn_cast_shared_local',False) and self.current and self.current.url==channel.url:
                        return
                    return self._syn_cast_rejoin_shared(channel)
                if getattr(self,'_syn_cast_shared_local',False):
                    return self._syn_cast_prepare_local_zap(channel)
            # SYN_TIMESHIFT_AUTO_BETA5: retry only after switching channels.
            if getattr(self, '_syn_ts_auto_blocked_url', None) != channel.url:
                self._syn_ts_auto_blocked_url = None
            self._syn_idle_layer.set_visible(False)
            self._syn_reconnect_reset()
            if getattr(self, '_syn_ts_session', None):
                self._syn_ts_stop(restore=False)
            if syn_dvr.allowed_stream_url(channel.url):
                self._dvr_playing_file = False
                self.dvr_back_btn.set_visible(False)
            self.current = channel
            self.blank_label.set_visible(False)
            self.now_playing.set_text(display_channel_name(channel.name))
            self.fs_channel_label.set_text(display_channel_name(channel.name))
            self.resolution.set_text(tr("Detectando resolución…"))
            self.status.set_text(tr("Conectando con ") + channel.name + "…")
            self.pause_button.set_sensitive(True)
            player = self.area.player
            if not player or not player.ctx.value:
                self.pending_channel = channel
                if self.area.problem:
                    self.player_failed(self.area.problem)
                return
            player.on_status = self.player_status
            try:
                relay_url, wait_for_relay = self._syn_dvr_playback_target(channel)
                if relay_url:
                    player.play(Channel(channel.name, channel.group, relay_url, channel.logo))
                    self.status.set_text(tr('DVR: viendo la señal compartida'))
                elif wait_for_relay:
                    player.stop()  # Never open a second IPTV session while DVR is active.
                    self.status.set_text(tr('DVR: esperando la señal compartida…'))
                else:
                    if syn_multistream.should_release_playback(
                            self.dvr_store.read(), self.profile.get('id'),
                            syn_multistream.profile_limit(self.profile), channel.url):
                        player.stop()
                        self.status.set_text(tr('DVR: límite de conexiones alcanzado.'))
                    else:
                        if self._syn_ts_auto_enabled(channel):
                            # FFmpeg takes over this provider slot; do NOT open
                            # a transient second mpv connection first.
                            self._syn_ts_start()
                        else:
                            player.play(channel)
            except Exception as exc:
                self.status.set_text(tr("No se pudo abrir el canal: ") + str(exc))
            if hasattr(self, '_syn_reattach_rec_button'):
                self._syn_reattach_rec_button(self.dvr_store.read())
            self._update_pause_label()
            self.update_programme()

        def pause(self, *_):
            player = self.area.player
            if player:
                player.toggle_pause()
                self._update_pause_label()

        def stop(self, *_):
            if getattr(self,'_syn_cast_shared_local',False):
                return self._syn_cast_stop()
            if getattr(self,'_syn_cast_only',False):
                return self._syn_cast_stop()
            self._syn_reconnect_reset()
            if getattr(self, '_syn_ts_session', None):
                self._syn_ts_stop(restore=False)
            if self.area.player:
                self.area.player.stop()
            self.current = None
            self._syn_idle_sync()
            self.blank_label.set_text(tr("▣\n\nSelecciona un canal para empezar"))
            self.blank_label.set_visible(True)
            self.now_playing.set_text(tr("Sin reproducción"))
            self.resolution.set_text("")
            self.status.set_text(tr("Reproducción detenida"))
            self.pause_button.set_sensitive(False)
            self.update_programme()

        def poll_resolution(self):
            if self.area.player and self.current:
                self.update_programme()
                dimensions = self.area.player.video_dimensions()
                if dimensions:
                    w, h = dimensions
                    quality = "4K UHD" if w >= 3840 and h >= 2160 else "Full HD" if w >= 1920 and h >= 1080 else "HD" if h >= 720 else "SD"
                    self.resolution.set_text(f"{w} × {h} · {quality}")
            return True

        def show_info(self, *_):
            if self.area.player:
                dims = self.area.player.video_dimensions()
                msg = f"Resolución real: {dims[0]} × {dims[1]}" if dims else tr("La resolución aún no está disponible.")
                ua = self.player_options.get('user_agent', 'Predeterminado')
                dialog = Adw.MessageDialog(transient_for=self, heading='Datos de reproducción', body=msg + '\n\nReproductor: libmpv integrado\nUser-Agent: ' + ua + '\nFuente: ' + self.profile['name'])
                dialog.add_response("cerrar", "Cerrar")
                dialog.present()

        def _queue_video_frame(self):
            if self.area.get_realized():
                self.area.queue_render()
            return False

        def _set_fullscreen_layout(self, enabled):
            # No tocar parent, GLArea, contexto OpenGL ni libmpv: SOLO
            # visibilidad de widgets hermanos. Evita destruir el renderizador
            # al cambiar de modo o durante el redimensionamiento Wayland.
            if self.fullscreen_mode == enabled:
                return
            self.fullscreen_mode = enabled
            if self.guide_open:
                self.set_guide_open(False)
            self.set_fs_osd(False)
            if enabled:
                if not self.compact_sidebar and self.paned.get_position() >= 220:
                    self._saved_paned_position = self.paned.get_position()
                self.paned.set_wide_handle(False)
                self.paned.add_css_class("iptv-fullscreen-paned")
            else:
                self.paned.set_wide_handle(not self.compact_sidebar)
                if not self.compact_sidebar:
                    self.paned.remove_css_class("iptv-fullscreen-paned")

            # La v1.2 dejaba visibles details, toolbar y status: esa era
            # la franja inferior que seguía apareciendo en pantalla completa.
            for widget in (self.header, self.details, self.program_label, self.toolbar,
                           self.footer, self.status):
                widget.set_visible(not enabled)
            self.sidebar.set_visible(not enabled and not self.compact_sidebar)
            if enabled:
                self.channel_popover.popdown()
                self.paned.set_position(0)
                self.area.grab_focus()  # F y Escape no dependen del buscador
            else:
                self.paned.set_position(0 if self.compact_sidebar else self._saved_paned_position)
                GLib.idle_add(lambda: (self._check_responsive_layout(), False)[1])
            if getattr(self, '_synplus_ui', False):
                synplus_layout.fullscreen_changed(self, enabled, GLib)
            # El nuevo tamano del framebuffer puede llegar en varios pasos.
            # queue_render() no crea ni destruye ningun contexto libmpv.
            GLib.idle_add(self._queue_video_frame)

        def fullscreen_changed(self, _window, _param):
            # Única fuente de verdad: estado informado por GNOME/Wayland.
            self._fullscreen_target = None
            if self._fullscreen_timeout_id:
                GLib.source_remove(self._fullscreen_timeout_id)
                self._fullscreen_timeout_id = 0
            self._set_fullscreen_layout(bool(self.is_fullscreen()))

        def _finish_fullscreen_request(self):
            # Evita un bloqueo logico si el WM ignora la solicitud. No
            # alteramos el estado arbitrariamente: leemos lo que confirma GTK.
            self._fullscreen_target = None
            self._fullscreen_timeout_id = 0
            self._set_fullscreen_layout(bool(self.is_fullscreen()))
            return False

        def toggle_fullscreen(self, *_):
            # Evitar solicitudes solapadas mientras el compositor confirma
            # la anterior. Sobre Parallels/VirGL el cambio repetido de
            # resolucion puede saturar la cola grafica.
            if self._fullscreen_target is not None:
                return
            self._fullscreen_target = not bool(self.is_fullscreen())
            # Registramos el watchdog antes de solicitar fullscreen: algunos
            # backends de GTK notifican el cambio casi inmediatamente.
            self._fullscreen_timeout_id = GLib.timeout_add(1000, self._finish_fullscreen_request)
            if self._fullscreen_target:
                self.fullscreen()
            else:
                self.unfullscreen()

        def key_press(self, _controller, key, _code, mods):
            ctrl = bool(mods & Gdk.ModifierType.CONTROL_MASK)
            if self._syn_portal.get_visible():
                if key == Gdk.KEY_Escape:
                    self._syn_portal_go_back()
                    return True
                if ctrl and key in (Gdk.KEY_p, Gdk.KEY_P):
                    self._syn_portal_hide()
                    return True
                # Prevent TV shortcuts when the catalogue has keyboard focus.
                return False
            if ctrl and key in (Gdk.KEY_p, Gdk.KEY_P):
                self._syn_portal_show('home')
                return True
            focused = self.get_focus()
            typing = isinstance(focused, (Gtk.Entry, Gtk.SearchEntry))
            if key == Gdk.KEY_Escape and self.guide_open:
                self._synplus_close_guide_or_restore()
                return True
            if self.guide_open and not typing and key in (Gdk.KEY_Home, Gdk.KEY_KP_Home):
                self.guide_go_now()
                return True
            if self.guide_open and not typing and key in (Gdk.KEY_Page_Up, Gdk.KEY_Page_Down):
                self.guide_shift(-60 if key == Gdk.KEY_Page_Up else 60)
                return True
            if key in (Gdk.KEY_g, Gdk.KEY_G) and not typing:
                self.show_guide()
                return True
            if ctrl and key in (Gdk.KEY_f, Gdk.KEY_F) and self.guide_open:
                self.guide_search.grab_focus()
                return True
            if ctrl and key in (Gdk.KEY_f, Gdk.KEY_F):
                self.search.grab_focus()
                return True
            if ctrl and key in (Gdk.KEY_r, Gdk.KEY_R):
                self.load_channels()
                return True
            if key == Gdk.KEY_F11 or (key in (Gdk.KEY_f, Gdk.KEY_F) and not typing):
                self.toggle_fullscreen()
                return True
            if self.fullscreen_mode and key in (Gdk.KEY_Up, Gdk.KEY_Down) and not typing:
                self.zap(-1 if key == Gdk.KEY_Up else 1)
                return True
            if key == Gdk.KEY_Escape and self.fs_remote_open:
                self.set_fs_remote(False)
                return True
            if key == Gdk.KEY_Escape and (self.fullscreen_mode or self._fullscreen_target is True):
                if self._fullscreen_target is None:
                    self.toggle_fullscreen()
                return True
            if key == Gdk.KEY_space and not typing:
                self.pause()
                return True
            return False

        def build_epg_guide(self):
            """Parrilla sobre Gtk.Overlay: MPV mantiene su GLArea sin reparentar."""
            self.guide_surface = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.guide_surface.set_hexpand(True)
            self.guide_surface.set_vexpand(True)
            self.guide_surface.set_halign(Gtk.Align.FILL)
            self.guide_surface.set_valign(Gtk.Align.FILL)
            self.guide_surface.add_css_class('syn-guide-backdrop')
            self.overlay.add_overlay(self.guide_surface)
            self.overlay.set_clip_overlay(self.guide_surface, True)
            self.guide_surface.set_overflow(Gtk.Overflow.HIDDEN)
            self.guide_surface.set_visible(False)
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            head.add_css_class('syn-guide-header')
            heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            title = Gtk.Label(label=tr('Guía de televisión'), xalign=0)
            title.add_css_class('syn-guide-title')
            heading.append(title)
            subtitle = Gtk.Label(label=tr('Explora la programación sin abandonar el directo'), xalign=0)
            subtitle.add_css_class('syn-guide-muted')
            heading.append(subtitle)
            self._guide_header_subtitle = subtitle
            heading.set_hexpand(True)
            head.append(heading)
            self.guide_search = Gtk.SearchEntry(placeholder_text=tr('Buscar canal…'))
            self.guide_search.set_size_request(180, -1)
            self.guide_search.set_hexpand(False)
            self.guide_search.add_css_class('syn-guide-search')
            self.guide_search.connect('search-changed', self.guide_search_changed)
            head.append(self.guide_search)
            for label, cb in [('‹', lambda *_: self.guide_shift(-60)),
                              ('Ahora', lambda *_: self.guide_go_now()),
                              ('›', lambda *_: self.guide_shift(60))]:
                btn = Gtk.Button(label=label)
                btn.add_css_class('syn-guide-head-button')
                btn.connect('clicked', cb)
                head.append(btn)
            close = Gtk.Button.new_from_icon_name('window-close-symbolic')
            close.add_css_class('syn-guide-head-button')
            close.set_tooltip_text(tr('Cerrar guía (Esc)'))
            close.connect('clicked', lambda *_: self._synplus_close_guide_or_restore())
            head.append(close)
            self.guide_surface.append(head)

            body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            body.set_vexpand(True)
            self.guide_surface.append(body)
            self.guide_categories_scroll = Gtk.ScrolledWindow()
            # Gtk.ScrolledWindow.set_size_request fija un MÍNIMO, no un máximo.
            # Con NEVER, GTK propaga el ancho mínimo de botones largos y desplaza
            # el resto de la parrilla. AUTOMATIC + min/max limita el ancho real.
            self.guide_categories_scroll.set_size_request(GUIDE_CATEGORIES_WIDTH, -1)
            self.guide_categories_scroll.set_min_content_width(GUIDE_CATEGORIES_WIDTH)
            self.guide_categories_scroll.set_max_content_width(GUIDE_CATEGORIES_WIDTH)
            self.guide_categories_scroll.set_propagate_natural_width(False)
            self.guide_categories_scroll.set_propagate_natural_height(False)
            self.guide_categories_scroll.set_hexpand(False)
            self.guide_categories_scroll.set_halign(Gtk.Align.START)
            self.guide_categories_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            self.guide_categories_scroll.add_css_class('syn-guide-categories')
            self.guide_categories_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            self.guide_categories_box.set_margin_top(13)
            self.guide_categories_scroll.set_child(self.guide_categories_box)
            body.append(self.guide_categories_scroll)

            programmes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            programmes.set_hexpand(True)
            programmes.set_vexpand(True)
            programmes.set_overflow(Gtk.Overflow.HIDDEN)
            body.append(programmes)
            time_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            time_row.add_css_class('syn-guide-axis')
            programmes.append(time_row)
            corner = Gtk.Label(label=tr('CANAL'), xalign=0)
            corner.set_size_request(GUIDE_CHANNEL_WIDTH - 10, 42)
            corner.set_margin_start(10)
            corner.add_css_class('syn-guide-muted')
            time_row.append(corner)
            # Eje dibujado a las mismas X absolutas de cada programa.
            # No es otro ScrolledWindow: el scroll independiente de la regla
            # causaba el desfase de varias horas visible en la captura.
            self.guide_axis = Gtk.DrawingArea()
            self.guide_axis.set_content_height(42)
            self.guide_axis.set_size_request(-1, 42)
            self.guide_axis.set_hexpand(True)
            self.guide_axis.set_draw_func(self._guide_draw_axis)
            time_row.append(self.guide_axis)
            self._guide_axis_start = self.guide_start
            self._guide_axis_scale = 1.0

            row_area = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            row_area.set_vexpand(True)
            row_area.set_overflow(Gtk.Overflow.HIDDEN)
            programmes.append(row_area)
            self.guide_names_scroll = Gtk.ScrolledWindow()
            # La columna de canales NO puede crecer al ancho natural de las estrellas.
            # NEVER sumaba el mínimo del contenido y hacía que la EPG empezase
            # 600+ píxeles más a la derecha, aunque la regla siguiera en su sitio.
            self.guide_names_scroll.set_size_request(GUIDE_CHANNEL_WIDTH, -1)
            self.guide_names_scroll.set_min_content_width(GUIDE_CHANNEL_WIDTH)
            self.guide_names_scroll.set_max_content_width(GUIDE_CHANNEL_WIDTH)
            self.guide_names_scroll.set_min_content_height(0)
            self.guide_names_scroll.set_propagate_natural_width(False)
            self.guide_names_scroll.set_propagate_natural_height(False)
            self.guide_names_scroll.set_hexpand(False)
            self.guide_names_scroll.set_halign(Gtk.Align.START)
            # SYN_REV6_EXTERNAL_SCROLL: NEVER pide altura natural completa y
            # puede hacer que GTK considere la EPG no desplazable.
            # EXTERNAL conserva viewport limitado sin una segunda barra.
            self.guide_names_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)
            self.guide_names_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.guide_names_scroll.set_child(self.guide_names_box)
            row_area.append(self.guide_names_scroll)
            self.guide_tracks_scroll = Gtk.ScrolledWindow()
            self.guide_tracks_scroll.set_hexpand(True)
            self.guide_tracks_scroll.set_vexpand(True)
            self.guide_tracks_scroll.set_propagate_natural_width(False)
            self.guide_tracks_scroll.set_propagate_natural_height(False)
            self.guide_tracks_scroll.set_min_content_height(0)
            # EPG usa su propia interpolación: evitar doble inercia de GTK.
            self.guide_tracks_scroll.set_kinetic_scrolling(False)
            # Mostrar siempre la barra vertical: con miles de canales, el usuario
            # debe saber que puede seguir bajando. La barra horizontal sigue auto.
            self.guide_tracks_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
            self.guide_tracks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.guide_tracks_scroll.set_child(self.guide_tracks_box)
            row_area.append(self.guide_tracks_scroll)
            self._guide_viewport_width = 0
            self._guide_resize_timer = 0
            self._guide_scroll_timer = 0
            self._guide_scroll_target = None
            # GTK4 no expone notify::width para GtkWidget. Un DrawingArea de
            # 1 px avisa con su señal resize sin interceptar interacción.
            self.guide_width_probe = Gtk.DrawingArea()
            self.guide_width_probe.set_content_height(1)
            self.guide_width_probe.set_hexpand(True)
            self.guide_width_probe.connect('resize', self._guide_size_changed)
            programmes.append(self.guide_width_probe)
            # Un ajuste horizontal y vertical para mantener la parrilla alineada.
            self.guide_tracks_scroll.get_hadjustment().connect(
                'value-changed', lambda *_: self.guide_axis.queue_draw())
            self.guide_names_scroll.set_vadjustment(self.guide_tracks_scroll.get_vadjustment())
            self.guide_tracks_scroll.get_vadjustment().connect(
                'value-changed', self._guide_virtual_scroll_changed)
            self.guide_tracks_scroll.get_hadjustment().connect(
                'value-changed', self._guide_time_scroll_changed)
            # Arrastre con ratón de la parrilla y de la regla, sin sacrificar clic derecho DVR.
            for drag_surface in (self.guide_tracks_scroll, self.guide_axis):
                drag = Gtk.GestureDrag.new()
                drag.set_button(1)
                drag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                drag.connect('drag-begin', self._guide_touch_begin)
                drag.connect('drag-update', self._guide_touch_update)
                drag.connect('drag-end', self._guide_touch_end)
                drag_surface.add_controller(drag)
            # GTK no siempre entrega el giro de rueda de una columna cuya
            # política vertical es NEVER al ScrolledWindow vecino. Capturamos
            # el scroll en AMBAS columnas y avanzamos automáticamente de tanda
            # al llegar al final. Las categorías conservan su scroll propio.
            for scrolling_column in (self.guide_names_scroll, self.guide_tracks_scroll):
                wheel = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
                wheel.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                wheel.connect('scroll', self._guide_wheel_scroll)
                scrolling_column.add_controller(wheel)
            footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            footer.add_css_class('syn-guide-footer')
            self.guide_count = Gtk.Label(label='', xalign=0)
            self.guide_count.set_hexpand(True)
            self.guide_count.set_ellipsize(Pango.EllipsizeMode.END)
            footer.append(self.guide_count)
            self.guide_back = Gtk.Button(label=tr('‹ Anteriores'))
            self.guide_back.add_css_class('syn-guide-head-button')
            self.guide_back.connect('clicked', lambda *_: self.guide_page_step(-1))
            footer.append(self.guide_back)
            self.guide_more = Gtk.Button(label=tr('Mostrar otros 24 canales'))
            self.guide_more.add_css_class('syn-guide-head-button')
            self.guide_more.connect('clicked', self.guide_more_clicked)
            footer.append(self.guide_more)
            reload_btn = Gtk.Button.new_from_icon_name('view-refresh-symbolic')
            reload_btn.add_css_class('syn-guide-head-button')
            reload_btn.set_tooltip_text(tr('Actualizar EPG'))
            reload_btn.connect('clicked', lambda *_: self.load_guide(force=True))
            footer.append(reload_btn)
            self.guide_surface.append(footer)

        def _guide_draw_axis(self, _area, ctx, width, height):
            """Regla EPG sin desplazamiento independiente: usa el scroll de los bloques."""
            if not self.guide_open:
                return
            start = self._guide_axis_start
            scale = self._guide_axis_scale
            scroll_x = self.guide_tracks_scroll.get_hadjustment().get_value()
            # Cairo bypasses GTK CSS; choose ink explicitly for each palette.
            theme = getattr(self.get_application(), '_current_theme', 'system')
            grid_ink, hour_ink = epg_axis_ink(theme)
            ctx.set_line_width(1.0)
            ctx.set_font_size(12)
            for instant, minutes in epg_axis_sections(start, duration_minutes=720):
                if instant is None:
                    continue
                x = epg_x_at(instant, start, scale) - scroll_x
                if x < -80 or x > width + 20:
                    continue
                ctx.set_source_rgba(*grid_ink)
                ctx.move_to(x + .5, 0)
                ctx.line_to(x + .5, height)
                ctx.stroke()
                ctx.set_source_rgba(*hour_ink)
                ctx.move_to(x + 9, 25)
                ctx.show_text(format_time(instant))

        def _guide_restore_position(self, horizontal, vertical):
            """Restore the viewport, centering NOW on the first measured open."""
            if self.guide_open:
                if self._guide_center_after_render:
                    measured = self.guide_tracks_scroll.get_hadjustment().get_page_size()
                    if measured >= 180:
                        horizontal = max(0.0, epg_x_at(
                            dt.datetime.now().astimezone(),
                            self._guide_axis_start, self._guide_axis_scale) - measured / 2.0)
                    self._guide_center_after_render = False
                for adj, target in ((self.guide_tracks_scroll.get_hadjustment(), horizontal),
                                    (self.guide_tracks_scroll.get_vadjustment(), vertical)):
                    upper = max(adj.get_lower(), adj.get_upper() - adj.get_page_size())
                    adj.set_value(max(adj.get_lower(), min(upper, target)))
                self.guide_axis.queue_draw()
                if os.environ.get('SYN_EPG_DEBUG') == '1':
                    a = self.guide_tracks_scroll.get_vadjustment()
                    print(f'SYN EPG medido: upper={a.get_upper():.0f} '
                          f'page={a.get_page_size():.0f} pos={a.get_value():.1f}',
                          file=sys.stderr, flush=True)
            return False

        def _guide_virtual_scroll_changed(self, *_):
            if not self.guide_open or self._guide_render_busy or self._guide_virtual_timer:
                return
            y = self.guide_tracks_scroll.get_vadjustment().get_value()
            first = max(0, ((int(y) // 70) // 12) * 12 - 12)
            if first != self._guide_virtual_first:
                self._guide_virtual_timer = GLib.timeout_add(135, self._guide_virtual_refresh)

        def _guide_virtual_refresh(self):
            self._guide_virtual_timer = 0
            if self.guide_open and not self._guide_render_busy:
                self._guide_soft_arrival = True
                self.guide_render_rows()
            return False

        def _guide_time_scroll_changed(self, *_):
            if not self.guide_open or self._guide_render_busy:
                return
            self.guide_axis.queue_draw()
            # Debounce instead of rebuilding 36+ GTK rows while live video
            # and continuous touch/trackpad movement compete on the main loop.
            if self._guide_rebase_timer:
                GLib.source_remove(self._guide_rebase_timer)
                self._guide_rebase_timer = 0
            if not self._guide_dragging:
                self._guide_rebase_timer = GLib.timeout_add(260, self._guide_rebase_if_needed)

        def _guide_rebase_if_needed(self):
            self._guide_rebase_timer = 0
            if not self.guide_open or self._guide_render_busy or self._guide_dragging:
                return False
            if time.monotonic() < getattr(self, '_guide_rebase_cooldown_until', 0.0):
                return False
            adj = self.guide_tracks_scroll.get_hadjustment()
            scale = max(0.1, self._guide_axis_scale)
            right = max(0, adj.get_upper() - adj.get_page_size())
            if right < 240 * scale:
                return False
            value = adj.get_value()
            threshold = 85 * scale
            if value < threshold:
                self._guide_rebase_cooldown_until = time.monotonic() + 0.5
                self._guide_rebase_time(-180)
            elif value > right - threshold:
                self._guide_rebase_cooldown_until = time.monotonic() + 0.5
                self._guide_rebase_time(180)
            return False

        def _guide_rebase_time(self, minutes):
            """Slide the 12-hour time window without changing visible wall-clock time."""
            h = self.guide_tracks_scroll.get_hadjustment().get_value()
            v = self.guide_tracks_scroll.get_vadjustment().get_value()
            old_scale = self._guide_axis_scale
            self.guide_start += dt.timedelta(minutes=minutes)
            self._guide_saved_adjustments = (h - minutes * old_scale, v)
            self.guide_render_rows()

        def _guide_horizontal_move(self, pixels):
            if not self.guide_open:
                return
            adj = self.guide_tracks_scroll.get_hadjustment()
            right = max(adj.get_lower(), adj.get_upper() - adj.get_page_size())
            adj.set_value(max(adj.get_lower(), min(right, adj.get_value() + pixels)))

        def _guide_touch_begin(self, _gesture, _x, _y):
            self._guide_drag_last = 0.0
            self._guide_dragging = False

        def _guide_touch_update(self, gesture, offset_x, offset_y):
            # Do NOT hijack natural vertical scrolling or clicks. A drag must
            # be clearly horizontal before it becomes a timetable pan.
            if abs(offset_y) >= 7 and abs(offset_y) > abs(offset_x) * 1.15:
                gesture.set_state(Gtk.EventSequenceState.DENIED)
                return
            if abs(offset_x) < 7 or abs(offset_x) <= abs(offset_y) * 1.15:
                return
            if not self._guide_dragging:
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            self._guide_dragging = True
            self._guide_horizontal_move(self._guide_drag_last - offset_x)
            self._guide_drag_last = offset_x

        def _guide_touch_end(self, _gesture, _x, _y):
            was_horizontal = self._guide_dragging
            if was_horizontal:
                self._guide_drag_until = time.monotonic() + 0.28
            self._guide_dragging = False
            # Continue past the edge after release, never from drag-update.
            if was_horizontal and self.guide_open:
                if self._guide_rebase_timer:
                    GLib.source_remove(self._guide_rebase_timer)
                self._guide_rebase_timer = GLib.timeout_add(260, self._guide_rebase_if_needed)

        def _guide_adapt_width(self):
            if not hasattr(self, '_guide_header_subtitle'):
                return
            available = max(0, self.get_width())
            self._guide_header_subtitle.set_visible(available >= 1050)
            self.guide_search.set_visible(available >= 865 and (
                not getattr(self, '_synplus_ui', False) or
                getattr(self, '_synplus_full_guide', False) or
                getattr(self, '_synplus_fullscreen_guide', False)))

        def _guide_size_changed(self, _area, width, _height):
            self._guide_adapt_width()
            if not self.guide_open:
                return
            width = max(0, width - GUIDE_CHANNEL_WIDTH)
            # Evitar rerenderizados durante cada píxel de un resize y no
            # reinicializar libmpv. Cambios insignificantes no afectan zoom.
            if width < 240 or abs(width - self._guide_viewport_width) < 36:
                return
            if self._guide_resize_timer:
                GLib.source_remove(self._guide_resize_timer)
            self._guide_resize_timer = GLib.timeout_add(180, self._guide_finish_resize)

        def _guide_finish_resize(self):
            self._guide_resize_timer = 0
            if self.guide_open:
                self.guide_render_rows()
            return False

        def guide_search_changed(self, *_):
            if self.guide_search_timer:
                GLib.source_remove(self.guide_search_timer)
            self.guide_search_timer = GLib.timeout_add(180, self._guide_apply_search)

        def _guide_apply_search(self):
            self.guide_search_timer = 0
            self.guide_page = 0
            self._guide_reset_vertical = True
            if self.guide_open:
                self.guide_render_rows()
            return False

        def guide_choose_category(self, category):
            self.guide_category_name = category
            self.guide_page = 0
            self._guide_reset_vertical = True
            self.guide_render_categories()
            self.guide_render_rows()

        def guide_render_categories(self):
            while (child := self.guide_categories_box.get_first_child()) is not None:
                self.guide_categories_box.remove(child)
            groups = [syn_favoritos.ALL_CATEGORY, syn_favoritos.FAVORITES_CATEGORY] + sorted(
                {c.group for c in self.channels if c.group not in
                 (syn_favoritos.ALL_CATEGORY, syn_favoritos.FAVORITES_CATEGORY)}, key=norm)
            for name in groups:
                # Los nombres de categorías largos (Xtream) no pueden forzar
                # a la columna izquierda a crecer: elipsis + tooltip.
                btn = Gtk.Button()
                if name == syn_favoritos.FAVORITES_CATEGORY:
                    is_selected = self.guide_category_name == name
                    shown = ('♥ ' if is_selected else '♡ ') + tr('Favoritos')
                elif name == syn_favoritos.ALL_CATEGORY:
                    shown = tr('Todas las categorías')
                else:
                    shown = name
                cat_label = Gtk.Label(label=shown, xalign=0)
                if name == syn_favoritos.FAVORITES_CATEGORY:
                    cat_label.add_css_class('syn-guide-favorites-heart')
                    if self.guide_category_name == name:
                        cat_label.add_css_class('syn-heart-active')
                cat_label.set_ellipsize(Pango.EllipsizeMode.END)
                cat_label.set_width_chars(11)
                cat_label.set_max_width_chars(15)
                cat_label.set_single_line_mode(True)
                btn.set_child(cat_label)
                btn.set_tooltip_text(tr('Solo favoritos') if name == syn_favoritos.FAVORITES_CATEGORY else shown)
                btn.set_halign(Gtk.Align.FILL)
                btn.add_css_class('syn-guide-cat')
                if name == self.guide_category_name:
                    btn.add_css_class('active')
                btn.connect('clicked', lambda _btn, cat=name: self.guide_choose_category(cat))
                self.guide_categories_box.append(btn)

        def guide_filtered_channels(self):
            # Keep the exact original Channel instance and its XMLTV ID.
            matches = syn_favoritos.filter_channels(
                self.channels, self.favorites, self.guide_category_name,
                self.guide_search.get_text(), norm)
            if self.guide_category_name == syn_favoritos.FAVORITES_CATEGORY:
                return syn_fav_sort.order_channels(matches, self.profile.get('favorites', []))
            return matches

        def _guide_programmes_for(self, channel):
            return syn_favoritos.programmes_for(
                channel, self.channels, self.guide, self.epg_aliases,
                sources.epg_for_channel, norm)

        def guide_go_now(self):
            # SYN_579_EPG_CENTER: preserve earlier and later programmes.
            # Position the live time marker in the middle of the visible guide.
            self.guide_start = epg_initial_start(dt.datetime.now().astimezone(), lookback_minutes=120)
            self._guide_open_initial = True
            self.guide_render_rows()

        def guide_shift(self, minutes):
            # Header arrows move the same scroll position as mouse/trackpad.
            self._guide_horizontal_move(minutes * self._guide_axis_scale)

        def _guide_set_vertical_position(self, at_end=False):
            """Aplicar el scroll tras la nueva medición GTK de la tanda."""
            adj = self.guide_tracks_scroll.get_vadjustment()
            limit = max(adj.get_lower(), adj.get_upper() - adj.get_page_size())
            adj.set_value(limit if at_end else adj.get_lower())
            return False

        # SYN_EPG_ALIGN_SMOOTH_126: animación vertical sobre el ajuste COMPARTIDO
        # entre nombres y programación. No hay un segundo scroll desincronizado.
        def _guide_smooth_scroll_tick(self):
            if not self.guide_open:
                self._guide_scroll_timer = 0
                self._guide_scroll_target = None
                return False
            adj = self.guide_tracks_scroll.get_vadjustment()
            end = max(adj.get_lower(), adj.get_upper() - adj.get_page_size())
            target = self._guide_scroll_target
            if target is None:
                self._guide_scroll_timer = 0
                return False
            target = max(adj.get_lower(), min(end, target))
            current = adj.get_value()
            remaining = target - current
            if abs(remaining) <= 0.65:
                adj.set_value(target)
                self._guide_scroll_timer = 0
                self._guide_scroll_target = None
                return False
            adj.set_value(current + remaining * 0.19)
            return True

        def _guide_wheel_scroll(self, controller, dx, dy):
            """Wheel on names OR tracks moves ONE vertical document.

            Captured deliberately on both GtkScrolledWindows, avoiding
            nested GTK wheel handlers and never snapping to full 70px rows.
            Shift/Ctrl or real horizontal wheel continues to pan time.
            """
            if not self.guide_open:
                return False
            mods = controller.get_current_event_state()
            if mods & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK):
                delta = dx if abs(dx) > 0.08 else dy
                if abs(delta) > 0.0001:
                    self._guide_horizontal_move(delta * 56)
                    return True
            if abs(dx) > max(0.08, abs(dy) * 0.75):
                self._guide_horizontal_move(dx * 56)
                return True
            if abs(dy) <= 0.0001:
                return False
            # Gtk.PolicyType.EXTERNAL on names gives the same constrained
            # vertical geometry as tracks, rather than forcing natural height.
            adj = self.guide_tracks_scroll.get_vadjustment()
            lo = adj.get_lower()
            hi = max(lo, adj.get_upper() - adj.get_page_size())
            # Mac trackpads emit fractional deltas; mouse wheels arrive in steps.
            # Move one shared GTK adjustment with critically damped easing.
            # Una rueda/trackpad puede emitir ráfagas antes de que la
            # animación alcance el objetivo. No acumular filas fuera de vista.
            # El destino nunca adelanta más de 2 filas (140 px) al viewport
            # actual, ni siquiera con un evento de dy excepcionalmente grande.
            step = max(-48.0, min(48.0, dy * 22.0))
            current = adj.get_value()
            lead = min(140.0, max(70.0, adj.get_page_size() * 0.65))
            origin = (self._guide_scroll_target if self._guide_scroll_target is not None
                      else current)
            proposed = origin + step
            self._guide_scroll_target = max(lo, min(hi,
                max(current - lead, min(current + lead, proposed))))
            if not self._guide_scroll_timer:
                self._guide_scroll_timer = GLib.timeout_add(16, self._guide_smooth_scroll_tick)
            if os.environ.get('SYN_EPG_DEBUG') == '1':
                print(f'SYN EPG rueda: dy={dy:.3f} range={lo:.0f}..{hi:.0f} '
                      f'pos={adj.get_value():.1f} upper={adj.get_upper():.0f} '
                      f'page={adj.get_page_size():.0f}', file=sys.stderr, flush=True)
            return True

        def guide_page_step(self, direction, wheel=False):
            matches = self.guide_filtered_channels()
            total_pages = max(1, (len(matches) + 23) // 24)
            target = max(0, min(total_pages - 1, self.guide_page + direction))
            if target == self.guide_page:
                return
            self.guide_page = target
            if self._guide_scroll_timer:
                GLib.source_remove(self._guide_scroll_timer)
                self._guide_scroll_timer = 0
            self._guide_scroll_target = None
            self.guide_render_rows()
            # Desde el final de una tanda siguiente comienza arriba; al subir
            # a la tanda anterior se muestra su extremo inferior.
            GLib.idle_add(self._guide_set_vertical_position, wheel and direction < 0)

        def guide_more_clicked(self, *_):
            self.guide_page_step(1)

        def _guide_switch(self, channel):
            if self._guide_dragging or time.monotonic() < self._guide_drag_until:
                return
            self.set_guide_open(False)
            self.start_channel(channel)
            if getattr(self, '_synplus_embedded_guide', False) and not self.fullscreen_mode:
                GLib.idle_add(lambda: (self.set_guide_open(True), False)[1])
            if self.fullscreen_mode:
                self.set_fs_osd(True)

        def guide_render_rows(self):
            """One continuous y document, windowed in 60-row buffers."""
            if not self.guide_open or self._guide_render_busy:
                return
            self._guide_render_busy = True
            hadj = self.guide_tracks_scroll.get_hadjustment()
            vadj = self.guide_tracks_scroll.get_vadjustment()
            hsave, vsave = (getattr(self, '_guide_saved_adjustments', None)
                            or (hadj.get_value(), vadj.get_value()))
            self._guide_saved_adjustments = None
            if self._guide_reset_vertical:
                vsave = 0
                self._guide_reset_vertical = False
            for box in (self.guide_names_box, self.guide_tracks_box):
                while (child := box.get_first_child()) is not None:
                    box.remove(child)
            start = self.guide_start
            end = start + dt.timedelta(hours=12)
            now = dt.datetime.now().astimezone()
            # Gtk puede no haber asignado aún tamaño al mostrar el overlay;
            # usar el ancho de la ventana como respaldo sin tocar GLArea.
            viewport = self.guide_tracks_scroll.get_width()
            probe_width = self.guide_width_probe.get_width() - GUIDE_CHANNEL_WIDTH
            if viewport < 240 and probe_width >= 240:
                viewport = probe_width
            if viewport < 240:
                viewport = max(360, self.get_width() - GUIDE_CATEGORIES_WIDTH - GUIDE_CHANNEL_WIDTH - 36)
            self._guide_viewport_width = viewport
            px_min = epg_minutes_scale(viewport)
            total = epg_x_at(end, start, px_min)
            if self._guide_open_initial:
                # SYN_579_EPG_CENTER: show past and future, with the red
                # NOW marker exactly halfway across the visible timeline.
                hsave = max(0.0, epg_x_at(now, start, px_min) - viewport / 2.0)
                # GTK measures the real visible timetable after building rows.
                # Recenter once using that exact width in _guide_restore_position.
                self._guide_center_after_render = True
                self._guide_open_initial = False
            self._guide_axis_start = start
            self._guide_axis_scale = px_min
            self.guide_axis.queue_draw()
            matches = self.guide_filtered_channels()
            # 70px fixed row height and matching invisible spacers in both columns.
            # The scrollbar sees the entire list, never a 24-channel 'page'.
            first = max(0, ((int(vsave) // 70) // 12) * 12 - 12)
            first = min(first, max(0, len(matches) - 1))
            subset = matches[first:first + 60]
            self._guide_virtual_first = first
            self._guide_virtual_total = len(matches)
            if first:
                for column in (self.guide_names_box, self.guide_tracks_box):
                    spacer = Gtk.Box()
                    spacer.set_size_request(-1, first * 70)
                    column.append(spacer)
            if not matches:
                empty_text = (tr('No hay favoritos todavía. Marca ♡ en algún canal.')
                              if self.guide_category_name == syn_favoritos.FAVORITES_CATEGORY and not self.favorites
                              else tr('No hay canales que coincidan con este filtro.'))
                msg = Gtk.Label(label=empty_text, xalign=0)
                msg.add_css_class('syn-guide-muted')
                msg.set_margin_start(12)
                msg.set_margin_top(15)
                msg.set_wrap(True)
                self.guide_tracks_box.append(msg)
            for channel in subset:
                channel_widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
                channel_widget.set_size_request(GUIDE_CHANNEL_WIDTH, 70)
                channel_widget.set_valign(Gtk.Align.START)
                channel_widget.set_overflow(Gtk.Overflow.HIDDEN)
                channel_widget.add_css_class('syn-guide-channel')
                if self.current and self.current.favorite_id == channel.favorite_id:
                    channel_widget.add_css_class('syn-guide-channel-playing')
                guide_logo_name = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
                guide_logo_name.set_size_request(120, -1)
                guide_logo_name.append(self.channel_pill(channel, 120, 46))
                guide_title = Gtk.Label(label=display_channel_name(channel.name), xalign=.5)
                guide_title.add_css_class('syn-favorite-display-name')
                guide_title.set_ellipsize(Pango.EllipsizeMode.END)
                guide_title.set_max_width_chars(16)
                guide_title.set_tooltip_text(display_channel_name(channel.name))
                guide_logo_name.append(guide_title)
                channel_widget.append(guide_logo_name)
                # Favorito pequeño junto al logo, no una fila expansible.
                if channel.favorite_id in self.favorites:
                    fav_icon = Gtk.Label(label='♥')
                    fav_icon.add_css_class('syn-heart-active')
                    fav_icon.set_size_request(14, 14)
                    fav_icon.set_size_request(14, 14)
                    fav_icon.set_hexpand(False)
                    fav_icon.set_halign(Gtk.Align.END)
                    channel_widget.append(fav_icon)
                click = Gtk.GestureClick()
                click.connect('released', lambda _g, _n, _x, _y, ch=channel: self._guide_switch(ch))
                channel_widget.add_controller(click)
                self.guide_names_box.append(channel_widget)

                track = Gtk.Fixed()
                track.set_size_request(total, 70)
                track.set_valign(Gtk.Align.START)
                track.set_overflow(Gtk.Overflow.HIDDEN)
                track.add_css_class('syn-guide-track')
                for x, width, a, b, title, description, available in epg_geometry(
                        self._guide_programmes_for(channel),
                        start, px_min, duration_minutes=720):
                    # Gtk.Box interactivo: Gtk.Button tiene ancho mínimo del
                    # tema (Adwaita/Colloid) y desalineaba los programas.
                    block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                    block.set_size_request(width, 68)
                    block.set_overflow(Gtk.Overflow.HIDDEN)
                    if available:
                        block.add_css_class('syn-guide-program')
                        if self._guide_soft_arrival:
                            block.add_css_class('syn-guide-soft-arrival')
                        block.add_css_class('syn-guide-program-' + str(sum(map(ord,channel.name)) % 6))
                        if a <= now < b:
                            block.add_css_class('syn-guide-current')
                        block.set_tooltip_text(f'{epg_time_label(a,b)} · {title}' + (f'\n{description[:300]}' if description else ''))
                        if width >= 45:
                            timestamp = Gtk.Label(label=format_time(a), xalign=0)
                            timestamp.add_css_class('syn-guide-time')
                            timestamp.set_margin_start(5)
                            block.append(timestamp)
                        if width >= 85:
                            ttl = Gtk.Label(label=title, xalign=0)
                            ttl.add_css_class('syn-guide-program-name')
                            ttl.set_margin_start(5)
                            ttl.set_ellipsize(Pango.EllipsizeMode.END)
                            ttl.set_max_width_chars(max(4, int((width - 16) / 9)))
                            block.append(ttl)
                        click = Gtk.GestureClick()
                        click.set_button(1)
                        click.connect('released', lambda _g, _n, _x, _y, ch=channel: self._guide_switch(ch))
                        block.add_controller(click)
                        # Right-click the programme pill to schedule its
                        # original (unclipped) XMLTV programme time.
                        context = Gtk.GestureClick()
                        context.set_button(3)
                        context.connect('pressed', lambda _g, _n, _x, _y,
                                        target=block, ch=channel, a0=a, b0=b, name=title:
                                        self.dvr_epg_context_menu(target, ch, a0, b0, name))
                        block.add_controller(context)
                    else:
                        block.add_css_class('syn-guide-gap')
                        if width >= 160:
                            missing = Gtk.Label(label=tr('Datos no disponibles'), xalign=0)
                            missing.set_margin_start(9)
                            missing.set_valign(Gtk.Align.CENTER)
                            block.append(missing)
                    track.put(block, x, 0)
                if start <= now < end:
                    now_pos = epg_x_at(now, start, px_min)
                    line = Gtk.Box()
                    line.add_css_class('syn-guide-now-line')
                    line.set_size_request(2, 68)
                    line.set_can_target(False)
                    track.put(line, now_pos, 0)
                self.guide_tracks_box.append(track)
            # Invisible y spacers keep one shared continuous scrollbar for all channels.
            remain = max(0, len(matches) - first - len(subset))
            if remain:
                for column in (self.guide_names_box, self.guide_tracks_box):
                    spacer = Gtk.Box()
                    spacer.set_size_request(-1, remain * 70)
                    column.append(spacer)
            self.guide_back.set_visible(False)
            self.guide_more.set_visible(False)
            hint = ('Rueda: canales · Shift+rueda / arrastrar: horas' if LANGUAGE == 'es'
                    else 'Wheel: channels · Shift+wheel / drag: hours')
            self.guide_count.set_text(f"{len(matches)} {tr('channels')} · " +
                                      f"{format_day_time(start)} {tr('to')} {format_day_time(end)} · " + hint)
            self._guide_soft_arrival = False
            self._guide_render_busy = False
            # Apply AFTER Gtk has recomputed both scroll adjustments.
            GLib.timeout_add(36, self._guide_restore_position, hsave, vsave)


        def set_guide_open(self, visible):
            # The fullscreen EPG lives over the actual video, not in the
            # windowed 3–5-row guide underneath the player.
            if (visible and getattr(self, '_synplus_ui', False)
                    and getattr(self, '_synplus_in_fullscreen', False)):
                synplus_layout.mount_fullscreen_guide(self)
            if self.guide_open == bool(visible): return
            self.guide_open = bool(visible)
            if visible:
                if self.fs_remote_open:
                    self.set_fs_remote(False)
                if self.fullscreen_mode:
                    self.set_fs_osd(False)
                # Open the EPG in the same scope as the visible channel list.
                # Favourites win over the category dropdown if that filter is active.
                index = self.category.get_selected()
                selected_category = (self.category_names[index] if
                                     0 <= index < len(self.category_names) else
                                     'Todas las categorías')
                self.guide_category_name = (syn_favoritos.FAVORITES_CATEGORY if self.favs.get_active()
                                            else selected_category)
                self.guide_page = 0
                # SYN_579_EPG_CENTER: include two hours before the live time.
                # Opening scroll will center NOW without moving the panel.
                self.guide_start = epg_initial_start(dt.datetime.now().astimezone(), lookback_minutes=120)
                self._guide_open_initial = True
                self._guide_reset_vertical = True
                self._guide_virtual_first = -1
                self.guide_render_categories()
                self.guide_surface.set_visible(True)
                self._guide_adapt_width()
                self.guide_render_rows()
                self.guide_search.grab_focus()
            else:
                if getattr(self, '_guide_scroll_timer', 0):
                    GLib.source_remove(self._guide_scroll_timer)
                    self._guide_scroll_timer = 0
                self._guide_scroll_target = None
                if self._guide_resize_timer:
                    GLib.source_remove(self._guide_resize_timer)
                    self._guide_resize_timer = 0
                self.guide_surface.set_visible(False)
                # This also runs when the EPG is closed via Escape, its close
                # button, or leaving fullscreen. The original view is restored.
                if getattr(self, '_synplus_fullscreen_guide', False):
                    synplus_layout.unmount_fullscreen_guide(self)
                self.area.grab_focus()
                if self.fullscreen_mode:
                    self.set_fs_osd(True)

        def _synplus_close_guide_or_restore(self):
            # Close the navigation Guide as Back. The fullscreen-on-video
            # overlay uses the existing close behaviour: remain fullscreen.
            restore = getattr(self, '_synplus_restore_guide', None)
            if (callable(restore)
                    and getattr(self, '_synplus_full_guide', False)
                    and not (self.fullscreen_mode or self.is_fullscreen()
                             or getattr(self, '_synplus_in_fullscreen', False))):
                restore()
                return
            self.set_guide_open(False)

        def show_guide(self, *_):
            if getattr(self, '_synplus_ui', False):
                # The fullscreen OSD Guide button must use the fullscreen
                # EPG handler, NOT the windowed navigation handler.
                if (self.fullscreen_mode or self.is_fullscreen()
                        or getattr(self, '_synplus_in_fullscreen', False)):
                    synplus_layout.show_guide_page(self, GLib)
                elif getattr(self, '_synplus_full_guide', False):
                    self._synplus_close_guide_or_restore()
                else:
                    synplus_layout.show_guide_page(self, GLib)
                return
            self.set_guide_open(not self.guide_open)

        def open_settings(self, *_):
            # 1.3b Rev3: Profile / Playback / Appearance in independent pages.
            from syn_settings_rev3 import open_settings
            return open_settings(self, Gtk, GLib, Pango, normalize_accent_hex)

        def open_playlist(self, *_):
            dlg = Gtk.FileDialog(title=tr("Selecciona una lista M3U"))
            f = Gtk.FileFilter()
            f.set_name(tr("Listas IPTV M3U"))
            f.add_pattern("*.m3u")
            f.add_pattern("*.m3u8")
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(f)
            dlg.set_filters(filters)
            dlg.open(self, None, self.opened_playlist)

        def opened_playlist(self, dlg, result):
            try:
                file = dlg.open_finish(result)
                if file and file.get_path():
                    self.profile['type'] = 'file'
                    self.profile['source'] = file.get_path()
                    sources.save_config(self.cfg)
                    self.load_channels()
            except GLib.Error:
                pass

        def closing(self, *_):
            # The Cocoa menu may already be empty while GTK tears down.
            if sys.platform == 'darwin':
                app = self.get_application()
                if app is not None:
                    app._syn_mac_cancel_menu_timer()
            if getattr(self, '_syn_mac_closing', False):
                return False
            self._syn_mac_closing = True
            # Stop accepting new poster/logo work; cancel tasks still queued.
            for worker_name in ('_logo_pool', '_syn_poster_pool'):
                pool = getattr(self, worker_name, None)
                if pool is not None:
                    try:
                        pool.shutdown(wait=False, cancel_futures=True)
                    except Exception:
                        pass
            self._syn_capture_close()
            if getattr(self, '_syn_idle_timer_id', 0):
                GLib.source_remove(self._syn_idle_timer_id)
                self._syn_idle_timer_id = 0
            self._syn_reconnect_reset()
            if getattr(self, '_syn_ts_session', None):
                self._syn_ts_stop(restore=False)
            # Save the current view at normal close; playlist/profile data is preserved.
            try:
                idx = self.category.get_selected()
                category = self.category_names[idx] if 0 <= idx < len(self.category_names) else 'Todas las categorías'
                self.cfg['last_ui'] = {
                    'favorites': bool(self.favs.get_active()),
                    'category': category,
                    'guide': bool(self.guide_open),
                }
                sources.save_config(self.cfg)
            except (OSError, ValueError, TypeError) as exc:
                print(f'SYN: no se pudo guardar última vista: {exc}', file=sys.stderr)
            try:
                self.dvr_notify_on_exit()
            except (GLib.Error, OSError, ValueError) as exc:
                print('SYN DVR: aviso de salida no disponible: ' + type(exc).__name__, file=sys.stderr)
            if self.area.player:
                self.area.player.stop()
            return False  # GTK realizará unrealize y liberará libmpv/GL correctamente.

    class IPTVApp(Adw.Application):
        def __init__(self):
            flags = (Gio.ApplicationFlags.NON_UNIQUE if os.environ.get('SYN_FIRST_RUN_PREVIEW')
                     else Gio.ApplicationFlags.FLAGS_NONE)
            super().__init__(application_id=APP_ID, flags=flags)
            self.win = None

        def _syn_mac_cancel_menu_timer(self):
            source_id = getattr(self, '_syn_mac_menu_timer_id', 0)
            if source_id:
                GLib.source_remove(source_id)
                self._syn_mac_menu_timer_id = 0
            self._syn_mac_menu_name_timer = False

        def _syn_mac_quit(self, *_):
            # No poll may run while AppKit dismantles the application menu.
            self._syn_mac_cancel_menu_timer()
            # Cerrar las ventanas secundarias antes que la principal para que
            # el cierre normal de SYN guarde configuración y detenga el vídeo.
            # El servicio DVR independiente no se modifica.
            for window in tuple(self.get_windows()):
                if window is not self.win:
                    window.close()
            if self.win is not None:
                self.win.close()
            else:
                self.quit()

        def _syn_mac_preferences(self, *_):
            # Reutiliza la ventana real de Ajustes; no crea otro diálogo.
            window = self.win or self.get_active_window()
            if window is not None:
                window.open_settings()

        def do_activate(self):
            # GTK/macOS: Command es Meta, NO Primary. Registrar la acción
            # después del startup estándar, sin sobreescribir do_startup().
            if sys.platform == 'darwin' and self.lookup_action('quit') is None:
                action = Gio.SimpleAction.new('quit', None)
                action.connect('activate', self._syn_mac_quit)
                self.add_action(action)
                self.set_accels_for_action('app.quit', ['<Meta>q'])
            if sys.platform == 'darwin' and self.lookup_action('preferences') is None:
                # GTK4 integra app.preferences en el menú de aplicación macOS.
                preferences = Gio.SimpleAction.new('preferences', None)
                preferences.connect('activate', self._syn_mac_preferences)
                self.add_action(preferences)
                self.set_accels_for_action('app.preferences', ['<Meta>comma'])

                # Sustituir Editar por un modelo GMenu propio es la vía GTK4
                # documentada: evita manipular NSMenu con ctypes/Objective-C.
                # Mantener el menú Ventana nativo para minimizar/restaurar.
                menubar = Gio.Menu()
                native_window = Gio.MenuItem.new_submenu('Ventana', Gio.Menu())
                native_window.set_attribute_value(
                    'gtk-macos-special', GLib.Variant('s', 'window-submenu'))
                menubar.append_item(native_window)
                self.set_menubar(menubar)
            if not self.win:
                self.theme_provider = Gtk.CssProvider()
                self.host_theme_provider = Gtk.CssProvider()
                self.teal_theme_provider = Gtk.CssProvider()
                self.favorite_geometry_provider = Gtk.CssProvider()
                self.accent_provider = Gtk.CssProvider()
                self._teal_provider_active = False
                self._host_provider_active = False
                self._host_theme_css_path = None
                self._display = Gdk.Display.get_default()
                if self._display:
                    Gtk.StyleContext.add_provider_for_display(
                        self._display, self.theme_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                    self.favorite_geometry_provider.load_from_data(FAVORITE_GEOMETRY_CSS.encode('utf-8'))
                    Gtk.StyleContext.add_provider_for_display(
                        self._display, self.favorite_geometry_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
                    Gtk.StyleContext.add_provider_for_display(
                        self._display, self.accent_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_USER + 3)
                self._current_theme = None
                if sys.platform == 'darwin':
                    from syn_macos_theme import signature
                    self._syn_mac_signature = signature()
                self._gtk_theme_settings = Gtk.Settings.get_default()
                if self._gtk_theme_settings:
                    self._gtk_theme_settings.connect('notify::gtk-theme-name', self._gtk_theme_changed)
                    self._gtk_theme_settings.connect('notify::gtk-application-prefer-dark-theme', self._gtk_theme_changed)
                self._adw_manager = Adw.StyleManager.get_default()
                self._adw_manager.connect('notify::dark', self._gtk_theme_changed)
                config = sources.load_config()
                self._accent_hex = config.get('accent_hex','')
                self._host_signature = self._host_theme_signature()
                self.apply_theme(config.get('theme', 'system'), self._accent_hex)
                self.win = IPTVWindow(self)
                # Clear the old persistent "unconfirmed" GNOME notification.
                self.withdraw_notification('syn-dvr-closing')
                # GTK/Plasma/Xfce pueden cambiar settings.ini sin emitir
                # notify::gtk-theme-name dentro del sandbox Flatpak.
                GLib.timeout_add_seconds(5, self._poll_host_theme)
            self.win.present()
            if sys.platform == 'darwin':
                # SYN_MAC_575_TITLE: GTK constructs NSApplication's menu after
                # process setup. Correct its displayed title on the GUI thread.
                from syn_mac_identity import fix_menu_bar_name
                GLib.set_prgname('SYN')
                GLib.set_application_name('SYN')
                if not getattr(self, '_syn_mac_menu_name_timer', False):
                    self._syn_mac_menu_name_timer = True
                    self._syn_mac_menu_name_attempts = 0
                    def rename_menu():
                        # No Objective-C menu calls after close has started.
                        if (self.win is None or
                                getattr(self.win, '_syn_mac_closing', False)):
                            self._syn_mac_menu_name_timer = False
                            self._syn_mac_menu_timer_id = 0
                            return False
                        self._syn_mac_menu_name_attempts += 1
                        try:
                            ok = fix_menu_bar_name('SYN')
                        except Exception:
                            ok = False
                        if ok or self._syn_mac_menu_name_attempts >= 24:
                            self._syn_mac_menu_name_timer = False
                            self._syn_mac_menu_timer_id = 0
                            return False
                        return True
                    self._syn_mac_menu_timer_id = GLib.timeout_add(400, rename_menu)

        def _gtk_theme_changed(self, *_):
            if self._current_theme == 'system' and not getattr(self, '_theme_guard', False):
                self.apply_theme('system', self._accent_hex)

        def _poll_host_theme(self):
            if sys.platform == 'darwin':
                from syn_macos_theme import signature
                current = signature()
                if current != getattr(self, '_syn_mac_signature', None):
                    self._syn_mac_signature = current
                    self.apply_theme(self._current_theme or 'system', '')
                return True
            if self._current_theme == 'system':
                signature = self._host_theme_signature()
                if signature != getattr(self, '_host_signature', None):
                    self._host_signature = signature
                    self.apply_theme('system', self._accent_hex)
            return True

        def _gtk_name(self):
            gtk_settings = getattr(self, '_gtk_theme_settings', None)
            if gtk_settings:
                try: return gtk_settings.get_property('gtk-theme-name') or ''
                except (TypeError, ValueError): pass
            return ''

        def _host_theme_signature(self):
            name, dark_setting = self._host_theme()
            dark = gtk_theme_prefers_dark(name, dark_setting)
            path = find_host_gtk4_css(Path.home(), name, dark)
            if path:
                try:
                    stat = path.stat()
                    return name, dark_setting, str(path), stat.st_mtime_ns, stat.st_size
                except OSError:
                    pass
            return name, dark_setting, None, 0, 0

        def _host_theme(self):
            saved_name, saved_dark = host_gtk_settings(Path.home())
            gtk_name = os.environ.get('GTK_THEME', '') or self._gtk_name()
            # Preferencia real anfitrión cuando Flatpak anuncia Adwaita.
            if saved_name and (not gtk_name or gtk_name in ('Default', 'Adwaita')):
                gtk_name = saved_name
            return gtk_name, saved_dark

        def theme_description(self):
            name = self._host_theme()[0] or 'Adwaita'
            if self._current_theme != 'system':
                return tr('Sistema, Claro, Oscuro, Teal SYN, Nord claro/oscuro y Gruvbox claro/oscuro. Acentos Frost, Aurora y Gruvbox en Apariencia.')
            css = getattr(self, '_host_theme_css_path', None)
            accent = getattr(self, '_accent_hex','') or tr('del portal/libadwaita')
            if css:
                return f"{tr('Tema detectado: ')}{name}{tr(' · CSS GTK4: ')}{css}{tr(' · Realce: ')}{accent}."
            if os.path.exists('/.flatpak-info'):
                return ('GTK: ' + name + tr(' · No hay CSS GTK4 accesible del anfitrión. En Flatpak hay que compartir ~/.config/gtk-4.0 y sus recursos; para Colloid es necesario instalar su variante libadwaita (-l). Realce actual: ') + accent + '.')
            return ('GTK: ' + name + tr(' · Sin hoja GTK4 personalizada detectada. Los temas GTK3/Qt no pueden copiarse automáticamente a libadwaita. Realce actual: ') + accent + '.')

        def _update_host_css(self, enabled, dark):
            display = getattr(self, '_display', None)
            if not display:
                return
            if getattr(self, '_host_provider_active', False):
                Gtk.StyleContext.remove_provider_for_display(display, self.host_theme_provider)
                self._host_provider_active = False
            self._host_theme_css_path = None
            if not enabled:
                return
            # En instalaciones nativas GTK ya carga ~/.config/gtk-4.0/gtk.css.
            # Flatpak usa otro XDG_CONFIG_HOME: hay que cargar el CSS host explícitamente.
            name = self._host_theme()[0]
            path = find_host_gtk4_css(Path.home(), name, dark)
            if path is None:
                return
            if not os.path.exists('/.flatpak-info'):
                self._host_theme_css_path = str(path)
                return
            try:
                self.host_theme_provider.load_from_path(str(path))
                Gtk.StyleContext.add_provider_for_display(
                    display, self.host_theme_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_USER)
                self._host_provider_active = True
                self._host_theme_css_path = str(path)
            except (GLib.Error, OSError, ValueError) as exc:
                print(f'SYN: CSS GTK4 no aplicable ({path}): {exc}', file=sys.stderr)

        def apply_theme(self, theme, accent_hex=None):
            if sys.platform == 'darwin':
                # macOS has only system/light/dark appearances. GTK accent
                # overrides are ignored: the user's macOS accent always wins.
                theme = theme if theme in ('system', 'light', 'dark') else 'system'
                accent_hex = ''
            elif theme not in ('system','light','dark','teal','nord-light','nord-dark','gruvbox-light','gruvbox-dark'):
                theme = 'system'
            if accent_hex is not None:
                try: self._accent_hex = normalize_accent_hex(accent_hex)
                except ValueError: self._accent_hex = ''
            self._current_theme = theme
            manager = self._adw_manager
            self._theme_guard = True
            try:
                if theme == 'system' and sys.platform == 'darwin':
                    from syn_macos_theme import is_dark
                    mode = (Adw.ColorScheme.FORCE_DARK if is_dark()
                            else Adw.ColorScheme.FORCE_LIGHT)
                elif theme == 'system':
                    name, host_dark = self._host_theme()
                    gtk_settings = getattr(self, '_gtk_theme_settings', None)
                    prefer_dark = False
                    if gtk_settings:
                        try:
                            prefer_dark = bool(gtk_settings.get_property(
                                'gtk-application-prefer-dark-theme'))
                        except (TypeError, ValueError): pass
                    # GNOME's actual light/dark preference takes precedence
                    # over the GTK theme *name*. Flatpak also follows the
                    # portal; native installations can read GSettings directly.
                    # If GNOME does not specify a preference, honour dark/light
                    # GTK theme variants as a backward-compatible fallback.
                    desktop_pref = ''
                    if not os.path.exists('/.flatpak-info'):
                        try:
                            schema_source = Gio.SettingsSchemaSource.get_default()
                            if schema_source and schema_source.lookup('org.gnome.desktop.interface', True):
                                desktop_pref = Gio.Settings.new('org.gnome.desktop.interface').get_string('color-scheme')
                        except (GLib.Error, AttributeError, ValueError):
                            desktop_pref = ''
                    choice = synplus_layout.choose_system_scheme(
                        name, prefer_dark or host_dark, desktop_pref)
                    mode = {
                        'follow-system': Adw.ColorScheme.PREFER_LIGHT,
                        'dark': Adw.ColorScheme.FORCE_DARK,
                        'light': Adw.ColorScheme.FORCE_LIGHT,
                    }[choice]
                elif theme in ('light', 'nord-light', 'gruvbox-light'):
                    mode = Adw.ColorScheme.FORCE_LIGHT
                else:
                    mode = Adw.ColorScheme.FORCE_DARK
                manager.set_color_scheme(mode)
                self._update_host_css(theme == 'system', manager.get_dark())
                # BASE a prioridad APP: respeta el tema GTK4 del usuario.
                # Teal a prioridad superior al CSS USER del anfitrión:
                # sin ello Colloid/Terafox pueden tapar nuestra paleta.
                display = getattr(self, '_display', None)
                if display and getattr(self, '_teal_provider_active', False):
                    Gtk.StyleContext.remove_provider_for_display(display, self.teal_theme_provider)
                    self._teal_provider_active = False
                css = BASE_CSS + dvr_palette_css('system') + logo_pill_css(dark=manager.get_dark(), pastel=(theme in ('light','nord-light','gruvbox-light')), teal=(theme == 'teal')) + epg_gradient_css() + synplus_layout.css(theme, getattr(self, "_accent_hex", ""), manager.get_dark())
                self.theme_provider.load_from_data(css.encode('utf-8'))
                # The accent CSS is loaded separately at higher priority so
                # Adwaita and all bundled color schemes cannot override it.
                self.accent_provider.load_from_data(
                    accent_css(getattr(self, '_accent_hex', '')).encode('utf-8'))
                if display:
                    cast_provider = getattr(self, '_syn_cast_popover_provider', None)
                    if cast_provider is None:
                        cast_provider = Gtk.CssProvider()
                        Gtk.StyleContext.add_provider_for_display(
                            display, cast_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 14)
                        self._syn_cast_popover_provider = cast_provider
                    cast_provider.load_from_data(
                        synplus_layout.cast_popover_css(theme, manager.get_dark()).encode('utf-8'))
                    if sys.platform == 'darwin':
                        mac_provider = getattr(self, '_syn_mac_native_provider', None)
                        if mac_provider is None:
                            mac_provider = Gtk.CssProvider()
                            Gtk.StyleContext.add_provider_for_display(
                                display, mac_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 16)
                            self._syn_mac_native_provider = mac_provider
                        mac_provider.load_from_data(
                            synplus_layout.mac_native_css('', manager.get_dark()).encode('utf-8'))
                        # Detached GTK popups ignore the window's CSS scope.
                        # Only these surfaces receive a final high-priority neutral override.
                        menu_provider = getattr(self, '_syn_mac_menu_provider', None)
                        if menu_provider is None:
                            menu_provider = Gtk.CssProvider()
                            Gtk.StyleContext.add_provider_for_display(
                                display, menu_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 19)
                            self._syn_mac_menu_provider = menu_provider
                        menu_provider.load_from_data(
                            synplus_layout.mac_popover_css(manager.get_dark()).encode('utf-8'))
                        # SYN_MAC_575_SETTINGS: separate Preferences window
                        # has high-priority Linux rules; override them on macOS.
                        pref_provider = getattr(self, '_syn_mac_settings_provider', None)
                        if pref_provider is None:
                            pref_provider = Gtk.CssProvider()
                            Gtk.StyleContext.add_provider_for_display(
                                display, pref_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 21)
                            self._syn_mac_settings_provider = pref_provider
                        pref_provider.load_from_data(
                            synplus_layout.mac_settings_css(manager.get_dark()).encode('utf-8'))
                    # SYN 2.0.4: the welcome is a separate window and needs
                    # LIGHT-theme ink at a priority above host GTK/Yaru CSS.
                    # Keep the provider even when the desktop changes to dark:
                    # an empty stylesheet clears only the welcome overrides.
                    welcome_provider = getattr(self, '_syn_welcome_theme_provider', None)
                    if welcome_provider is None:
                        welcome_provider = Gtk.CssProvider()
                        Gtk.StyleContext.add_provider_for_display(
                            display, welcome_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
                        self._syn_welcome_theme_provider = welcome_provider
                    welcome_provider.load_from_data(
                        synplus_layout.welcome_light_css(theme, manager.get_dark()).encode('utf-8'))
                # SYN_207_LIGHT_POPOVER: Fedora Flatpak approved light dialog and popup fix.
                # Deliberately empty for all dark themes and System dark.
                if display:
                    popup_fix = getattr(self, '_syn_207_light_popup_fix', None)
                    if popup_fix is None:
                        popup_fix = Gtk.CssProvider()
                        Gtk.StyleContext.add_provider_for_display(
                            display, popup_fix, Gtk.STYLE_PROVIDER_PRIORITY_USER + 6)
                        self._syn_207_light_popup_fix = popup_fix
                    popup_fix.load_from_data(
                        light_surface_css(theme, manager.get_dark()).encode('utf-8'))
                # Native GTK loads ~/.config/gtk-4.0/gtk.css at USER,
                # above the APPLICATION-level SYN workbench. Protect only
                # SYN's layout in native System mode at USER+1 while keeping
                # generic host widget styling and the chosen accent intact.
                native_system = (theme == 'system' and
                                 not os.path.exists('/.flatpak-info'))
                if display and (native_system or theme in ('teal','light','dark','nord-light','nord-dark','gruvbox-light','gruvbox-dark')):
                    if native_system:
                        palette_css = (synplus_layout.css(
                            'system', getattr(self, '_accent_hex', ''), manager.get_dark()) +
                            synplus_layout.native_system_css())
                    elif theme in ('nord-light', 'nord-dark'):
                        from syn_nord_palette import nord_css
                        base = 'light' if theme == 'nord-light' else 'dark'
                        # Nord CSS last: Nord takes priority over DVR fallbacks.
                        palette_css = dvr_palette_css(base) + nord_css(theme, getattr(self, '_accent_hex', ''))
                    elif theme in ('gruvbox-light', 'gruvbox-dark'):
                        from syn_gruvbox_palette import gruvbox_css
                        base = 'light' if theme == 'gruvbox-light' else 'dark'
                        palette_css = dvr_palette_css(base) + gruvbox_css(theme, getattr(self, '_accent_hex', ''))
                    else:
                        palette_css = {'teal': TEAL_CSS, 'light': LIGHT_CSS, 'dark': DARK_CSS}[theme] + dvr_palette_css(theme)
                    effective_css = (palette_css if native_system else
                        palette_css + epg_gradient_css() +
                        syn_popup_theme_css(theme) +
                        synplus_layout.css(theme, getattr(self, '_accent_hex', ''), manager.get_dark()))
                    self.teal_theme_provider.load_from_data(effective_css.encode('utf-8'))
                    Gtk.StyleContext.add_provider_for_display(
                        display, self.teal_theme_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
                    self._teal_provider_active = True
                # Repaint the Cairo hour ruler immediately after changing themes.
                for window in self.get_windows():
                    axis = getattr(window, 'guide_axis', None)
                    if axis is not None:
                        axis.queue_draw()
                    # Cairo-drawn glyphs do not respond automatically to
                    # libadwaita palette changes; repaint at each theme change.
                    if sys.platform == 'darwin':
                        for glyph in (getattr(window, '_synplus_cine_reel', None),
                                      getattr(window, '_synplus_tv_icon', None),
                                      (window.shot_button.get_child()
                                       if hasattr(window, 'shot_button') else None)):
                            if glyph is not None:
                                glyph.queue_draw()
            finally:
                self._theme_guard = False

    return IPTVApp().run([])


def main():
    parser = argparse.ArgumentParser(description=tr('SYN — IPTV M3U, Xtream y EPG en GNOME'))
    parser.add_argument('--version', action='version', version=f'SYN {SYN_VERSION}')
    parser.add_argument('--playlist', help=tr('Archivo M3U para importar como primer perfil'))
    parser.add_argument('--list', action='store_true', help=tr('Listar los canales del perfil seleccionado'))
    parser.add_argument('--preview-first-run', action='store_true',
                        help=tr('Probar el primer arranque sin cambiar perfiles ni ajustes'))
    parser.add_argument('--locale-info', action='store_true', help='Display resolved interface locale')
    args = parser.parse_args()
    if args.locale_info:
        print('SYN ' + SYN_VERSION + ' · ' + locale_description())
        return 0
    if args.preview_first_run:
        # Sin alterar la configuración compartida con la instalación nativa.
        # NON_UNIQUE permite otra ventana aunque SYN esté abierto.
        os.environ['SYN_FIRST_RUN_PREVIEW'] = '1'
        with tempfile.TemporaryDirectory(prefix='syn-primer-inicio-') as tmp:
            sources.APP_CONFIG = Path(tmp) / 'config'
            sources.APP_CACHE = Path(tmp) / 'cache'
            sources.CONFIG_FILE = sources.APP_CONFIG / 'profiles.json'
            return run_gui(None)
    playlist = find_m3u(args.playlist)
    if args.list:
        cfg = sources.load_config()
        profile = next((p for p in cfg['profiles'] if p.get('id') == cfg.get('selected')), None)
        if profile is None: profile = sources.default_profile(playlist)
        for ch in sources.load_channels(profile):
            print(f'{ch.group:30} {ch.name}')
        return 0
    return run_gui(playlist)


if __name__ == '__main__':
    sys.exit(main())
