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
import syn_sources as sources
import syn_dvr
import syn_service_setup
from syn_i18n import translate as tr, format_time, format_day_time, LANGUAGE, locale_description
from pathlib import Path
from urllib.parse import urlsplit

APP_ID = "com.mrseivane.Syn"
APP_TITLE = "SYN"
SYN_VERSION = "1.3.1"
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
        library = ctypes.util.find_library("mpv")
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
                next_poll = time.monotonic() + 0.8
            elif not self.active_url:
                self._dimensions = None
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
        self._libGL = C.CDLL(ctypes.util.find_library("GL") or "libGL.so.1")
        self._libGL.glGetIntegerv.argtypes = [C.c_uint, C.POINTER(C.c_int)]
        self._libGL.glGetIntegerv.restype = None
        self._libGL.glClearColor.argtypes = [C.c_float] * 4
        self._libGL.glClear.argtypes = [C.c_uint]
        self._libEGL = C.CDLL(ctypes.util.find_library("EGL") or "libEGL.so.1")
        self._libEGL.eglGetProcAddress.argtypes = [C.c_char_p]
        self._libEGL.eglGetProcAddress.restype = C.c_void_p

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
            address = self._libEGL.eglGetProcAddress(name)
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

    def video_dimensions(self):
        # Snapshot actualizado por el hilo de control: no bloquea GTK.
        return (self._dimensions if not self.closed and self.active_url
                and not self._awaiting_load else None)

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

    TEAL_CSS = """
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
    """

    # Por defecto usamos CSS nativo de GTK/libadwaita. Solo el tema teal
    # aplica los colores de marca. Esta base es necesaria para que el OSD
    # del televisor sea legible independientemente del tema de GNOME/KDE.
    BASE_CSS = """
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
    .syn-logo-fallback { font-size: 10px; font-weight: 850; }
    .syn-channel-display-name { font-size: 12px; font-weight: 600; opacity: .84; }
    .syn-favorite-display-name { font-size: 11px; font-weight: 650; opacity: .82; }
    .syn-unified-channel-row { min-height: 0; }
    .syn-channel-logo-picture { margin: 0; padding: 0; background: transparent; border: none; box-shadow: none; }
    .syn-unified-favorite-star { opacity: .83; padding: 0; margin: 0;
      min-width: 0; min-height: 0; background: transparent; }
    .syn-unified-favorite-star:hover { opacity: 1; }
    .syn-favorite-display-name { font-size: 11px; font-weight: 600; opacity: .78; }
    .syn-row-star { padding: 2px; min-width: 28px; min-height: 28px; }

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
    window.iptv-tv row.syn-unified-channel-row { min-height: 0; padding: 0; }
    window.iptv-tv image.syn-unified-favorite-star,
    window.iptv-tv picture.syn-channel-logo-picture {
      min-width: 0; min-height: 0; margin: 0; padding: 0;
      background: transparent; border: none; box-shadow: none;
    }
    """

    LIGHT_CSS = """
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

    """
    DARK_CSS = """
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
        """Icono local: funciona en Flatpak y en la instalación nativa."""
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
            super().__init__(application=app, title=APP_TITLE, default_width=1280, default_height=720)
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
            self._logo_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='syn-logo')
            self._logo_requested = set()
            self.channels = []
            self.filtered = []
            self.category_names = ["Todas las categorías"]
            self.current = None
            self._instant_recording_id = None
            self._dvr_playing_file = False
            self._dvr_return_channel = None
            self.dvr_store = syn_dvr.DVRStore()
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
            self._tiny_header = False
            self.fs_osd_visible = False
            self.fs_osd_timer = 0
            self.guide_open = False
            self._restore_ui = self.cfg.get('last_ui', {})
            if not isinstance(self._restore_ui, dict):
                self._restore_ui = {}
            self.guide_start = epg_initial_start(dt.datetime.now().astimezone())
            self.guide_category_name = 'Todas las categorías'
            self.guide_page = 0
            self.guide_search_timer = 0

            base = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            base.add_css_class("iptv-surface")
            self.set_content(base)

            self.header = Adw.HeaderBar()
            self.header.add_css_class("iptv-header")
            brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
            brand.append(brand_icon(35))
            heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            title = Gtk.Label(label="SYN", xalign=0)
            title.add_css_class("iptv-heading")
            self.header_title = title
            heading.append(title)
            self.subtitle = Gtk.Label(label=tr("Televisión · GTK4 · libmpv"), xalign=0)
            self.subtitle.add_css_class("iptv-subtitle")
            heading.append(self.subtitle)
            brand.append(heading)
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
            self.dvr_nav_button.set_tooltip_text('Calendario, programación y grabaciones')
            self.dvr_nav_button.connect('clicked', self.toggle_dvr_view)
            self.header.pack_end(self.dvr_nav_button)
            self.dvr_recording_indicator = Gtk.Label(label='● REC')
            self.dvr_recording_indicator.add_css_class('syn-dvr-indicator')
            self.dvr_recording_indicator.set_tooltip_text('SYN DVR está grabando en segundo plano')
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

            self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            self.sidebar.add_css_class("iptv-sidebar")
            self.sidebar.set_size_request(280, -1)
            self.sidebar.set_margin_start(0)
            self.sidebar.set_margin_bottom(0)
            self.paned.set_start_child(self.sidebar)

            self.search = Gtk.SearchEntry(placeholder_text=tr("Buscar canales…"))
            self.search.set_margin_start(12)
            self.search.set_margin_end(12)
            self.search.set_margin_top(15)
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
            self.category.connect("notify::selected", lambda *_: self.render_list())
            filter_row.append(self.category)
            self.favs = Gtk.ToggleButton(label="★")
            self.favs.set_tooltip_text(tr("Solo favoritos"))
            self.favs.connect("toggled", lambda *_: self.render_list())
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
            self.build_fullscreen_osd()
            self.build_epg_guide()
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
            self.dvr_back_btn.set_tooltip_text('Regresar al último canal en directo')
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
            self.rec_button.set_tooltip_text('Grabar canal actual')
            self.rec_button.connect('clicked', self.toggle_instant_record)
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
                                    self.rec_button, volume_icon, self.volume, info, full)
            self._arrange_toolbar(compact=False)

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
            if self._needs_welcome:
                self.status.set_text(tr('SYN · Elige una fuente para empezar'))
                self.blank_label.set_text(tr('Bienvenido a SYN\n\nConfigura tu primera lista para empezar'))
                GLib.idle_add(self.show_welcome)
            else:
                self.load_channels()

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
            title = Gtk.Label(label='DVR · Grabaciones', xalign=0)
            title.add_css_class('title-1')
            title.set_hexpand(True)
            head.append(title)
            self.dvr_view.append(head)
            # Open the recording's real folder in the host file manager through
            # the desktop's default handler (Flatpak portal when available).
            open_folder = Gtk.Button.new_from_icon_name('folder-open-symbolic')
            open_folder.set_tooltip_text('Abrir carpeta de grabaciones')
            open_folder.connect('clicked', lambda *_: self.dvr_open_folder())
            head.append(open_folder)
            choose_folder = Gtk.Button(label='Elegir carpeta…')
            choose_folder.set_tooltip_text('Cambiar la carpeta donde se guardan las grabaciones')
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

            section = Gtk.Label(label='Programar una grabación', xalign=0)
            section.add_css_class('title-3')
            planner.append(section)
            planner.append(Gtk.Label(label='Fecha', xalign=0))
            self.dvr_calendar = Gtk.Calendar()
            planner.append(self.dvr_calendar)
            planner.append(Gtk.Label(label='Canal', xalign=0))
            self.dvr_channel_dropdown = Gtk.DropDown.new_from_strings(['Cargando canales…'])
            self.dvr_channel_dropdown.add_css_class('syn-dvr-channel-picker')
            self.dvr_channel_dropdown.set_enable_search(True)
            planner.append(self.dvr_channel_dropdown)
            planner.append(Gtk.Label(label='Horario (24 h)', xalign=0))
            times = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            now = dt.datetime.now() + dt.timedelta(minutes=5)
            self.dvr_start_entry = Gtk.Entry()
            self.dvr_start_entry.set_text(now.strftime('%H:%M'))
            self.dvr_start_entry.set_max_length(5)
            self.dvr_start_entry.set_width_chars(6)
            self.dvr_start_entry.set_tooltip_text('Inicio: HH:MM')
            self.dvr_end_entry = Gtk.Entry()
            self.dvr_end_entry.set_text((now + dt.timedelta(hours=1)).strftime('%H:%M'))
            self.dvr_end_entry.set_max_length(5)
            self.dvr_end_entry.set_width_chars(6)
            self.dvr_end_entry.set_tooltip_text('Fin: HH:MM')
            times.append(Gtk.Label(label='De'))
            times.append(self.dvr_start_entry)
            times.append(Gtk.Label(label='a'))
            times.append(self.dvr_end_entry)
            planner.append(times)
            planned = Gtk.Button(label='Programar grabación')
            planned.add_css_class('suggested-action')
            planned.add_css_class('syn-dvr-schedule-action')
            planned.connect('clicked', self.dvr_schedule)
            planner.append(planned)
            instant = Gtk.Button(label='● Grabar canal seleccionado ahora')
            instant.add_css_class('syn-dvr-action-record')
            instant.connect('clicked', self.dvr_record_selected)
            planner.append(instant)
            planner.append(Gtk.Label(label='Se utiliza FFmpeg sin recodificar y User-Agent VLC.',
                                     xalign=0, wrap=True))

            library = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            library.set_margin_start(16)
            library.set_margin_end(8)
            library.set_margin_top(10)
            split.set_end_child(library)
            library_title = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            title2 = Gtk.Label(label='Programadas y grabadas', xalign=0)
            title2.add_css_class('title-3')
            title2.set_hexpand(True)
            library_title.append(title2)
            refresh = Gtk.Button.new_from_icon_name('view-refresh-symbolic')
            refresh.set_tooltip_text('Actualizar grabaciones')
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
            self.dvr_service_label = Gtk.Label(label='Servicio DVR: comprobando…', xalign=0, wrap=True)
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
            programmes = sources.epg_for_channel(channel, self.guide, self.epg_aliases)
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
            button = Gtk.Button(label='● Programar grabación')
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
                                         end, syn_dvr.VLC_UA, programme=programme)
            except Exception:
                if paused:
                    player.play(channel)
                raise
            syn_dvr.ensure_worker()
            self.dvr_refresh(force=True)
            return job

        def dvr_record_selected(self, *_):
            try:
                ch = self.dvr_chosen_channel()
                self.dvr_enqueue(ch)
                self.dvr_feedback.set_text('Grabación inmediata solicitada: ' + display_channel_name(ch.name))
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
                self.dvr_feedback.set_text('Grabación programada: ' +
                                           start.strftime('%d/%m/%Y %H:%M') + ' – ' + end.strftime('%H:%M'))
            except (OSError, ValueError) as exc:
                self.dvr_feedback.set_text('No se pudo programar: ' + str(exc))

        def toggle_instant_record(self, *_):
            if self._instant_recording_id:
                self.dvr_store.stop(self._instant_recording_id)
                self._instant_recording_id = None
                self.rec_button.set_label('●')
                self.rec_button.remove_css_class('syn-dvr-recording')
                self.rec_button.set_tooltip_text('Grabar ahora')
                self.status.set_text('DVR: deteniendo grabación…')
                return
            if not self.current:
                self.status.set_text('DVR: reproduce un canal antes de grabar.')
                return
            try:
                job = self.dvr_enqueue(self.current)
                self._instant_recording_id = job['id']
                self.rec_button.set_label('■')
                self.rec_button.add_css_class('syn-dvr-recording')
                self.rec_button.set_tooltip_text('Detener grabación')
                self.status.set_text('DVR: grabación solicitada de ' + display_channel_name(self.current.name))
            except (ValueError, OSError) as exc:
                self.status.set_text('DVR: ' + str(exc))

        def dvr_stop_job(self, job_id):
            self.dvr_store.stop(job_id)
            self.dvr_refresh(force=True)

        def dvr_play_file(self, filepath):
            path = Path(filepath)
            if not path.is_file():
                self.dvr_feedback.set_text('El archivo ya no está disponible: ' + path.name)
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
                self.rec_button.set_tooltip_text('Detener grabación')
            else:
                self.rec_button.set_label('●')
                self.rec_button.remove_css_class('syn-dvr-recording')
                self.rec_button.set_tooltip_text('Grabar ahora')

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
            self.dvr_folder_label.set_text('Carpeta: ' + str(data.get('folder') or syn_dvr.video_directory()))
            active_count = sum(1 for j in data.get('jobs', []) if j.get('status') == 'running')
            if hasattr(self, 'dvr_recording_indicator'):
                self.dvr_recording_indicator.set_visible(bool(active_count))
                self.dvr_recording_indicator.set_text(f'● REC {active_count}' if active_count > 1 else '● REC')
            box = self.dvr_recording_list
            while row := box.get_first_child():
                box.remove(row)
            statuses = {'scheduled':'Programada', 'running':'Grabando', 'completed':'Finalizada',
                        'failed':'Error', 'cancelled':'Cancelada', 'missed':'Perdida',
                        'interrupted':'Interrumpida'}
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
                when = start.strftime('%d/%m %H:%M')
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
                    action = Gtk.Button(label='▶ Ver')
                    action.connect('clicked', lambda _b, path=job['path']: self.dvr_play_file(path))
                    row.append(action)
                    open_location = Gtk.Button.new_from_icon_name('folder-open-symbolic')
                    open_location.set_tooltip_text('Abrir ubicación del archivo original')
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
                action = Gtk.Button(label='▶ Ver')
                action.connect('clicked', lambda _b, path=str(f): self.dvr_play_file(path))
                row.append(action)
                open_location = Gtk.Button.new_from_icon_name('folder-open-symbolic')
                open_location.set_tooltip_text('Abrir ubicación del archivo original')
                open_location.connect('clicked', lambda _b, path=str(f): self.dvr_open_folder(path))
                row.append(open_location)
                box.append(row)
            if not jobs and not files:
                box.append(Gtk.Label(label='Todavía no hay grabaciones.'))
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
                       'Consulta: systemctl --user status syn-dvr-worker.service')
            if hasattr(self, 'dvr_service_label'):
                self.dvr_service_label.set_text(msg)
            return True  # Keep the status current as service starts/stops.

        def show_welcome(self, *_):
            """Asistente de primer inicio, sin importar automáticamente alacarta.m3u."""
            if self._welcome_window:
                self._welcome_window.present()
                return False
            dialog = Gtk.Window(title=tr('Bienvenido a SYN'), transient_for=self,
                                modal=True, default_width=650, default_height=690)
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
            cover_logo = brand_icon(138)
            cover_logo.set_halign(Gtk.Align.CENTER)
            hero.append(cover_logo)
            tagline = Gtk.Label(label=tr('Tu televisión. A tu manera.'))
            tagline.add_css_class('syn-welcome-title')
            tagline.set_wrap(True)
            hero.append(tagline)
            subtitle = Gtk.Label(label=tr('Empecemos por lo esencial: conecta tu primera fuente de canales.'))
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
                icon = Gtk.Image.new_from_icon_name(symbol)
                icon.set_pixel_size(37)
                icon.add_css_class('syn-welcome-symbol')
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
                content.append(Gtk.Image.new_from_icon_name('go-next-symbolic'))
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
            back = Gtk.Button.new_from_icon_name('go-previous-symbolic')
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
            exit_btn = Gtk.Button.new_from_icon_name("view-restore-symbolic")
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
            self.fs_only_favorites.set_icon_name("starred-symbolic")
            self.fs_only_favorites.set_tooltip_text(tr("Mostrar solo favoritos"))
            self.fs_only_favorites.connect("toggled", self.fs_filter_changed)
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
            meta.set_hexpand(True)
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
            return [ch for ch in self.channels
                    if (not query or query in norm(ch.name + ' ' + ch.group))
                    and (category == "Todas las categorías" or ch.group == category)
                    and (not fav_only or ch.favorite_id in self.favorites)]

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
                    star = Gtk.Image.new_from_icon_name("starred-symbolic")
                    star.set_tooltip_text("Favorito")
                    line.append(star)
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
            self.channel_popover = popover
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
            if not hasattr(self, "quick_listbox"):
                return
            while row := self.quick_listbox.get_first_child():
                self.quick_listbox.remove(row)
            query = norm(self.quick_search.get_text())
            channels = [ch for ch in self.channels
                        if (not query or query in norm(ch.name) or query in norm(ch.group))
                        and (not self.quick_favs.get_active() or ch.favorite_id in self.favorites)]
            for ch in channels[:160]:
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
                fav = Gtk.Button.new_from_icon_name(
                    "starred-symbolic" if ch.favorite_id in self.favorites
                    else "non-starred-symbolic")
                fav.add_css_class("flat")
                fav.set_tooltip_text(tr("Marcar o quitar favorito"))
                fav.connect("clicked", lambda _button, c=ch: self.toggle_favorite(c))
                line.append(fav)
                row.set_child(line)
                self.quick_listbox.append(row)
            self.quick_count.set_text(f"{min(len(channels), 160)} de {len(channels)} canales")

        def quick_channel_activated(self, _listbox, row):
            self.channel_popover.popdown()
            self.start_channel(row.channel)
            # Selección también en el panel grande, si está filtrada.
            for i, ch in enumerate(self.filtered):
                if ch.favorite_id == row.channel.favorite_id:
                    self.listbox.select_row(self.listbox.get_row_at_index(i))
                    break

        def _arrange_toolbar(self, compact):
            for child in self.toolbar_widgets:
                if child.get_parent() == self.strip:
                    self.strip.remove(child)
            play, pause, stop, rec, speaker, slider, info, full = self.toolbar_widgets
            if compact:
                layout = ((play, 0, 0, 1), (pause, 1, 0, 1),
                          (stop, 2, 0, 1), (rec, 3, 0, 1),
                          (speaker, 0, 1, 1), (slider, 1, 1, 2),
                          (info, 3, 1, 1), (full, 4, 1, 1))
            else:
                layout = tuple((w, i, 0, 1) for i, w in enumerate(self.toolbar_widgets))
            for widget, column, row, span in layout:
                self.strip.attach(widget, column, row, span, 1)
            self.volume.set_hexpand(compact)
            self.play_button.set_label(tr("▶ Ver") if compact else tr("▶  Reproducir"))
            self._update_pause_label()

        def _update_pause_label(self):
            paused = bool(self.area.player and self.area.player.paused())
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

        def _check_responsive_layout(self):
            if self.is_fullscreen() or self.fullscreen_mode:
                return True
            width = self.get_width()
            if width <= 0:
                return True
            video_width = self.overlay.get_width()
            if (width == self._last_window_width and
                    video_width == self._last_video_width):
                return True
            # Dos umbrales diferentes: primero la lista se convierte en menú,
            # después los controles pasan a dos filas. Histéresis pequeña
            # para que no parpadeen al arrastrar junto al umbral.
            # La anchura real del video también importa si el usuario
            # arrastra el divisor dejando una zona de reproducción mínima.
            next_sidebar = (width < (990 if not self.compact_sidebar else 1010))
            next_controls = (width < (740 if not self.compact_controls else 760)
                             or (not next_sidebar and 0 < video_width < 520))
            if next_sidebar != self.compact_sidebar:
                if not self.compact_sidebar and self.paned.get_position() >= 220:
                    self._saved_paned_position = self.paned.get_position()
                self.compact_sidebar = next_sidebar
                self.sidebar.set_visible(not next_sidebar)
                self.channel_menu.set_visible(next_sidebar)
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
                self.header_title.set_text("SYN")
                self.subtitle.set_visible(not tiny)
                self.resolution.set_visible(not tiny)
            self._last_window_width = width
            self._last_video_width = video_width
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
            if text == 'Reproduciendo': text = tr('Reproduciendo')
            if failed:
                self.status.set_text(text)
                if self.area.player:
                    self.area.player.write_diag()
            elif self.current:
                self.status.set_text(text + " · " + self.current.name)

        def change_profile(self, dropdown, *_):
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
            token = self._source_generation
            self.status.set_text(tr('Loading profile') + ' «' + self.profile['name'] + '»…')
            self.channels = []
            self._refresh_categories()
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
                return False
            self.channels = channels
            self.dvr_update_channels()
            self._refresh_categories()
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
            self.subtitle.set_text(f"{len(self.channels)} {tr('channels')} · {len(self.category_names)-1} {tr('categories')} · {self.profile['name']} · v{SYN_VERSION}")
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

        def _fill_logo_image(self, path, image, pill=None):
            try:
                # Procesamos la imagen a resolucion suficiente, recortamos
                # los bordes transparentes y ajustamos el contenido a 108x38.
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 256, 256, True)
                x, y, w, h = logo_visible_bounds(
                    pix.get_pixels(), pix.get_width(), pix.get_height(),
                    pix.get_rowstride(), pix.get_n_channels())
                if 0 < w < pix.get_width() or 0 < h < pix.get_height():
                    pix = GdkPixbuf.Pixbuf.new_subpixbuf(pix, x, y, w, h)
                source_size = (pix.get_width(), pix.get_height())
                fitted = fitted_logo_size(*source_size)
                if fitted != source_size:
                    pix = pix.scale_simple(*fitted, GdkPixbuf.InterpType.BILINEAR)
                # La pixbuf NO se entrega a Gtk.Picture/Gtk.Image: ambos
                # podrian influir en la negociacion de tamano de la fila.
                image._syn_pixbuf = pix
                if os.environ.get('SYN_LOGO_DEBUG') == '1':
                    if not hasattr(self, '_logo_debug_count'):
                        self._logo_debug_count = 0
                    if self._logo_debug_count < 8:
                        print(f'SYN_LOGO: recortado={source_size[0]}x{source_size[1]} '
                              f'final={fitted[0]}x{fitted[1]} '
                              'lienzo=108x38 pastilla=120x46',
                              file=sys.stderr, flush=True)
                        def _after_layout():
                            dims = f'lienzo={image.get_width()}x{image.get_height()}'
                            if pill:
                                dims += f' pastilla={pill.get_width()}x{pill.get_height()}'
                            print('SYN_LOGO_WIDGET: ' + dims, file=sys.stderr, flush=True)
                            return False
                        GLib.timeout_add(650, _after_layout)
                        self._logo_debug_count += 1
                if pill:
                    label = getattr(pill, 'fallback_label', None)
                    if label: label.set_visible(False)
                    prior = getattr(pill, 'hue_class', 'syn-logo-pill-h6')
                    pill.remove_css_class(prior)
                    new_class = ('syn-logo-pill-h' + str(self._logo_palette_index(pix))
                                 + '-' + logo_contrast_variant(self._logo_samples(pix)))
                    pill.add_css_class(new_class)
                    pill.hue_class = new_class
                # Publicar el widget solo después de ocultar el fallback;
                # evita una negociación de tamaños con ambos simultáneos.
                image.set_visible(True)
                image.queue_draw()
            except (GLib.Error, OSError, ValueError):
                pass
            return False

        def channel_pill(self, ch, width=120, height=46):
            # Unico tamano para TODOS los canales, con o sin filtro favorito.
            width, height = 120, 46
            pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
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
            pic.set_draw_func(self._draw_channel_logo)
            pill.append(pic)
            short = display_channel_name(ch.name)
            short = short if len(short) <= 22 else short[:19] + '…'
            fallback = Gtk.Label(label=short)
            fallback.add_css_class('syn-logo-fallback')
            fallback.set_ellipsize(Pango.EllipsizeMode.END)
            fallback.set_max_width_chars(16)
            pill.append(fallback)
            pill.fallback_label = fallback
            custom = self._channel_logo_path(ch)
            if custom:
                self._fill_logo_image(custom, pic, pill)
            else:
                self._request_logo(ch.logo, pic, ch, pill)
            return pill

        def _channel_sidebar_row(self, ch):
            """UNA fila para todos los canales. El filtro Favoritos NO cambia el diseño.

            Recuperamos el diseño horizontal original de la lista general:
            pastilla, nombre limpio, estrella pequeña. Ninguna tarjeta vertical
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
            content.set_margin_end(10)
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

            # La estrella es una imagen de 17px; no un botón de 90px de alto.
            star = Gtk.Image.new_from_icon_name(
                'starred-symbolic' if ch.favorite_id in self.favorites else 'non-starred-symbolic')
            star.add_css_class('syn-unified-favorite-star')
            star.set_pixel_size(17)
            star.set_size_request(19, 19)
            star.set_halign(Gtk.Align.END)
            star.set_valign(Gtk.Align.CENTER)
            star.set_hexpand(False)
            star.set_vexpand(False)
            star.set_can_target(True)
            star.set_tooltip_text(tr('Quitar de favoritos') if ch.favorite_id in self.favorites
                                  else tr('Añadir a favoritos'))
            click = Gtk.GestureClick.new()
            click.set_button(1)
            def on_star_press(gesture, _count, _x, _y):
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
                GLib.idle_add(self.toggle_favorite, ch)
            click.connect('pressed', on_star_press)
            star.add_controller(click)
            content.append(star)
            row.set_child(content)
            return row

        def render_list(self):
            current = self.listbox.get_selected_row()
            selected_id = current.channel.favorite_id if current else None
            query = norm(self.search.get_text().strip())
            cat_idx = self.category.get_selected()
            cat = self.category_names[cat_idx] if cat_idx < len(self.category_names) else self.category_names[0]
            self.filtered = [ch for ch in self.channels if
                             (cat == 'Todas las categorías' or ch.group == cat) and
                             (not self.favs.get_active() or ch.favorite_id in self.favorites) and
                             (not query or query in norm(ch.name + ' ' + ch.group))]
            while (row := self.listbox.get_row_at_index(0)) is not None:
                self.listbox.remove(row)
            restore = None
            for ch in self.filtered[:250]:
                # SAME builder for all channels, in or out of favorites filter.
                row = self._channel_sidebar_row(ch)
                self.listbox.append(row)
                if selected_id and ch.favorite_id == selected_id:
                    restore = row
            if restore:
                self.listbox.select_row(restore)
            elif self.filtered:
                self.listbox.select_row(self.listbox.get_row_at_index(0))
            self.count.set_text(f"{tr('Showing')} {min(250, len(self.filtered))} {tr('of')} {len(self.channels)} · {tr('search to filter')}")
            self.render_quick_channels()
            if os.environ.get('SYN_LAYOUT_DEBUG') == '1' and not getattr(self, '_layout_probe_pending', False):
                self._layout_probe_pending = True
                GLib.timeout_add(900, self._debug_sidebar_geometry)

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
                star = name.get_next_sibling()
                widgets = [('row', row), ('box', box), ('pill', pill), ('name', name), ('star', star)]
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
            if not url or not url.startswith(('http://', 'https://')): return
            try:
                cached = sources.logo_path(url)
                if cached.is_file():
                    self._fill_logo_image(cached, widget, pill)
                    return
                key = (url, id(widget))
                if key in self._logo_requested: return
                self._logo_requested.add(key)
                def worker():
                    try:
                        path = sources.get_logo(url, user_agent=sources.metadata_user_agent(self.player_options))
                        GLib.idle_add(self._fill_logo_image, path, widget, pill)
                    except Exception: pass
                    finally: self._logo_requested.discard(key)
                self._logo_pool.submit(worker)
            except Exception: pass

        def toggle_favorite(self, channel):
            key = channel.favorite_id
            if key in self.favorites:
                self.favorites.remove(key)
            else:
                self.favorites.add(key)
            self.profile['favorites'] = sorted(self.favorites)
            sources.save_config(self.cfg)
            self.render_list()

        def play_selected(self):
            if self.compact_sidebar and self.current:
                self.start_channel(self.current)
                return
            row = self.listbox.get_selected_row()
            if row:
                self.start_channel(row.channel)
            else:
                self.status.set_text(tr("Selecciona un canal en la lista."))

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
                playing = player.active_url
                if url:
                    if playing != url:
                        player.play(Channel(channel.name, channel.group, url, channel.logo))
                        self.status.set_text('DVR: viendo la señal compartida, sin segunda conexión IPTV')
                elif waiting:
                    if playing == channel.url:
                        player.stop()  # Never displace the recording session.
                    if not playing or playing == channel.url:
                        self.status.set_text('DVR: esperando al grabador o su reconexión…')
                elif playing and playing.startswith('udp://127.0.0.1:'):
                    player.play(channel)  # The DVR has stopped: return to live IPTV.
                if hasattr(self, '_syn_reattach_rec_button'):
                    self._syn_reattach_rec_button(self.dvr_store.read())
            except (ValueError, OSError, RuntimeError, AttributeError) as exc:
                self.status.set_text('DVR compartido: ' + str(exc)[:130])
            return True

        def start_channel(self, channel):
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
                    self.status.set_text('DVR: viendo la señal compartida')
                elif wait_for_relay:
                    player.stop()  # Never open a second IPTV session while DVR is active.
                    self.status.set_text('DVR: esperando la señal compartida…')
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
            if self.area.player:
                self.area.player.stop()
            self.current = None
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
            focused = self.get_focus()
            typing = isinstance(focused, (Gtk.Entry, Gtk.SearchEntry))
            if key == Gdk.KEY_Escape and self.guide_open:
                self.set_guide_open(False)
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
            heading.set_hexpand(True)
            head.append(heading)
            self.guide_search = Gtk.SearchEntry(placeholder_text=tr('Buscar canal…'))
            self.guide_search.set_size_request(180, -1)
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
            close.connect('clicked', lambda *_: self.set_guide_open(False))
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
            programmes.append(row_area)
            self.guide_names_scroll = Gtk.ScrolledWindow()
            # La columna de canales NO puede crecer al ancho natural de las estrellas.
            # NEVER sumaba el mínimo del contenido y hacía que la EPG empezase
            # 600+ píxeles más a la derecha, aunque la regla siguiera en su sitio.
            self.guide_names_scroll.set_size_request(GUIDE_CHANNEL_WIDTH, -1)
            self.guide_names_scroll.set_min_content_width(GUIDE_CHANNEL_WIDTH)
            self.guide_names_scroll.set_max_content_width(GUIDE_CHANNEL_WIDTH)
            self.guide_names_scroll.set_propagate_natural_width(False)
            self.guide_names_scroll.set_hexpand(False)
            self.guide_names_scroll.set_halign(Gtk.Align.START)
            self.guide_names_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            self.guide_names_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.guide_names_scroll.set_child(self.guide_names_box)
            row_area.append(self.guide_names_scroll)
            self.guide_tracks_scroll = Gtk.ScrolledWindow()
            self.guide_tracks_scroll.set_hexpand(True)
            self.guide_tracks_scroll.set_vexpand(True)
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
            # GTK no siempre entrega el giro de rueda de una columna cuya
            # política vertical es NEVER al ScrolledWindow vecino. Capturamos
            # el scroll en AMBAS columnas y avanzamos automáticamente de tanda
            # al llegar al final. Las categorías conservan su scroll propio.
            for scrolling_column in (self.guide_names_scroll, self.guide_tracks_scroll):
                wheel = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
                wheel.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                wheel.connect('scroll', self._guide_wheel_scroll)
                scrolling_column.add_controller(wheel)
            footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            footer.add_css_class('syn-guide-footer')
            self.guide_count = Gtk.Label(label='', xalign=0)
            self.guide_count.set_hexpand(True)
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
            ctx.set_line_width(1.0)
            ctx.set_font_size(12)
            for instant, minutes in epg_axis_sections(start):
                if instant is None:
                    continue
                x = epg_x_at(instant, start, scale) - scroll_x
                if x < -80 or x > width + 20:
                    continue
                ctx.set_source_rgba(.58, .80, .75, .35)
                ctx.move_to(x + .5, 0)
                ctx.line_to(x + .5, height)
                ctx.stroke()
                ctx.set_source_rgba(.82, .94, .91, .98)
                ctx.move_to(x + 9, 25)
                ctx.show_text(format_time(instant))

        def _guide_reset_horizontal(self):
            """Resetea el scroll tras medir el contenido de la nueva parrilla."""
            if self.guide_open:
                adj = self.guide_tracks_scroll.get_hadjustment()
                adj.set_value(adj.get_lower())
                self.guide_axis.queue_draw()
            return False

        def _guide_size_changed(self, _area, width, _height):
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
            if self.guide_open:
                self.guide_render_rows()
            return False

        def guide_choose_category(self, category):
            self.guide_category_name = category
            self.guide_page = 0
            self.guide_render_categories()
            self.guide_render_rows()

        def guide_render_categories(self):
            while (child := self.guide_categories_box.get_first_child()) is not None:
                self.guide_categories_box.remove(child)
            groups = ['Todas las categorías', '★ Favoritos'] + sorted({c.group for c in self.channels}, key=norm)
            for name in groups:
                # Los nombres de categorías largos (Xtream) no pueden forzar
                # a la columna izquierda a crecer: elipsis + tooltip.
                btn = Gtk.Button()
                cat_label = Gtk.Label(label=(tr('Todas las categorías') if name == 'Todas las categorías' else tr('★ Favoritos') if name == '★ Favoritos' else name), xalign=0)
                cat_label.set_ellipsize(Pango.EllipsizeMode.END)
                cat_label.set_width_chars(11)
                cat_label.set_max_width_chars(15)
                cat_label.set_single_line_mode(True)
                btn.set_child(cat_label)
                btn.set_tooltip_text(name)
                btn.set_halign(Gtk.Align.FILL)
                btn.add_css_class('syn-guide-cat')
                if name == self.guide_category_name:
                    btn.add_css_class('active')
                btn.connect('clicked', lambda _btn, cat=name: self.guide_choose_category(cat))
                self.guide_categories_box.append(btn)

        def guide_filtered_channels(self):
            query = norm(self.guide_search.get_text().strip())
            cat = self.guide_category_name
            return [ch for ch in self.channels
                    if (cat == 'Todas las categorías' or
                        (cat == '★ Favoritos' and ch.favorite_id in self.favorites) or
                        ch.group == cat)
                    and (not query or query in norm(ch.name + ' ' + ch.group))]

        def guide_go_now(self):
            self.guide_start = epg_initial_start(dt.datetime.now().astimezone())
            self.guide_render_rows()

        def guide_shift(self, minutes):
            self.guide_start += dt.timedelta(minutes=minutes)
            self.guide_render_rows()

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
            adj.set_value(current + remaining * 0.27)
            return True

        def _guide_wheel_scroll(self, _controller, _dx, dy):
            """Desplazamiento suave, misma posición exacta en ambas columnas."""
            if not self.guide_open or abs(dy) < 0.0001:
                return False
            adj = self.guide_tracks_scroll.get_vadjustment()
            current = adj.get_value()
            lower = adj.get_lower()
            end = max(lower, adj.get_upper() - adj.get_page_size())
            if dy > 0 and current >= end - 1:
                self.guide_page_step(1, wheel=True)
                return True
            if dy < 0 and current <= lower + 1:
                self.guide_page_step(-1, wheel=True)
                return True
            # Acumulamos giros de rueda sin perder precisión del trackpad.
            basis = self._guide_scroll_target
            if basis is None:
                basis = current
            amount = max(-2.5, min(2.5, dy)) * 57
            self._guide_scroll_target = max(lower, min(end, basis + amount))
            if not self._guide_scroll_timer:
                self._guide_scroll_timer = GLib.timeout_add(16, self._guide_smooth_scroll_tick)
            return True

        def guide_page_step(self, direction, wheel=False):
            matches = self.guide_filtered_channels()
            total_pages = max(1, (len(matches) + 23) // 24)
            target = max(0, min(total_pages - 1, self.guide_page + direction))
            if target == self.guide_page:
                return
            self.guide_page = target
            self.guide_render_rows()
            # Desde el final de una tanda siguiente comienza arriba; al subir
            # a la tanda anterior se muestra su extremo inferior.
            GLib.idle_add(self._guide_set_vertical_position, wheel and direction < 0)

        def guide_more_clicked(self, *_):
            self.guide_page_step(1)

        def _guide_switch(self, channel):
            self.set_guide_open(False)
            self.start_channel(channel)
            if self.fullscreen_mode:
                self.set_fs_osd(True)

        def guide_render_rows(self):
            """Máximo 24 filas por página para no congelar listas Xtream enormes."""
            if not self.guide_open: return
            if getattr(self, '_guide_scroll_timer', 0):
                GLib.source_remove(self._guide_scroll_timer)
                self._guide_scroll_timer = 0
            self._guide_scroll_target = None
            for box in (self.guide_names_box, self.guide_tracks_box):
                while (child := box.get_first_child()) is not None:
                    box.remove(child)
            start = self.guide_start
            end = start + dt.timedelta(hours=5)
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
            self._guide_axis_start = start
            self._guide_axis_scale = px_min
            self.guide_axis.queue_draw()
            matches = self.guide_filtered_channels()
            page_size = 24
            page_count = max(1, (len(matches) + page_size - 1) // page_size)
            self.guide_page = min(self.guide_page, page_count - 1)
            subset = matches[self.guide_page * page_size: (self.guide_page + 1) * page_size]
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
                    fav_icon = Gtk.Image.new_from_icon_name('starred-symbolic')
                    fav_icon.set_pixel_size(13)
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
                        sources.epg_for_channel(channel, self.guide, self.epg_aliases),
                        start, px_min):
                    # Gtk.Box interactivo: Gtk.Button tiene ancho mínimo del
                    # tema (Adwaita/Colloid) y desalineaba los programas.
                    block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                    block.set_size_request(width, 68)
                    block.set_overflow(Gtk.Overflow.HIDDEN)
                    if available:
                        block.add_css_class('syn-guide-program')
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
            self.guide_back.set_visible(self.guide_page > 0)
            self.guide_more.set_visible(self.guide_page < page_count - 1)
            self.guide_more.set_label(f"{tr('Page')} {self.guide_page + 1}/{page_count} · {tr('Next 24')} ›")
            self.guide_count.set_text(f"{len(matches)} {tr('channels')} · {format_day_time(start)} {tr('to')} {format_time(end)} · {tr('page')} {self.guide_page + 1}/{page_count} · {tr('scroll for more')}")
            GLib.idle_add(self._guide_reset_horizontal)

        def set_guide_open(self, visible):
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
                self.guide_category_name = ('★ Favoritos' if self.favs.get_active()
                                            else selected_category)
                self.guide_page = 0
                # Mantener una franja de pasado; el eje y los programas usan idénticas X.
                self.guide_start = epg_initial_start(dt.datetime.now().astimezone())
                self.guide_render_categories()
                self.guide_surface.set_visible(True)
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
                self.area.grab_focus()
                if self.fullscreen_mode:
                    self.set_fs_osd(True)

        def show_guide(self, *_):
            self.set_guide_open(not self.guide_open)

        def open_settings(self, *_):
            # Si Gtk falla, mostrar la excepción en stderr en vez de dejar el botón mudo.
            win = Gtk.Window(title=tr('SYN · Ajustes'), transient_for=self, modal=True,
                             default_width=620, default_height=690)
            win.add_css_class('syn-settings-window')
            scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            outer.set_margin_top(16); outer.set_margin_bottom(16)
            outer.set_margin_start(22); outer.set_margin_end(22)
            scroll.set_child(outer)
            heading = Gtk.Label(label=tr('SYN · Fuentes y perfiles'), xalign=0)
            heading.add_css_class('iptv-heading'); outer.append(heading)
            def labeled(title, widget):
                label = Gtk.Label(label=title, xalign=0)
                label.add_css_class('iptv-details'); outer.append(label)
                if hasattr(widget, 'set_hexpand'): widget.set_hexpand(True)
                outer.append(widget)
                return widget
            def combo(strings, choice, localized=False):
                w = Gtk.DropDown.new_from_strings([tr(s) for s in strings] if localized else strings)
                w.set_selected(strings.index(choice) if choice in strings else 0)
                return w
            def selected(w):
                item = w.get_selected_item()
                return item.get_string() if item else ''
            def text_entry(value='', hidden=False):
                w = Gtk.PasswordEntry() if hidden else Gtk.Entry()
                w.set_text(str(value or ''))
                return w
            profile_names = [p['name'] for p in self.cfg['profiles']] + [tr('＋ Nuevo perfil')]
            theme_labels = [tr('Sistema (GTK3/GTK4 disponible)'), tr('Claro · Teal pastel'), tr('Oscuro · Gris/negro'), 'Teal SYN']
            theme_codes = ['system', 'light', 'dark', 'teal']
            active_theme = self.cfg.get('theme', 'teal')
            theme_picker = labeled(tr('Aspecto de SYN'), combo(theme_labels, theme_labels[theme_codes.index(active_theme)] if active_theme in theme_codes else theme_labels[3]))
            accent_picker = labeled(tr('Realce personalizado (opcional, #RRGGBB)'),
                                    text_entry(self.cfg.get('accent_hex', '')))
            theme_info = Gtk.Label(label=self.get_application().theme_description(), xalign=0)
            theme_info.set_wrap(True); theme_info.add_css_class('iptv-details'); outer.append(theme_info)
            theme_info.set_selectable(True)

            picker = labeled(tr('Editar perfil'), combo(profile_names, self.profile['name']))
            p = dict(self.profile)
            pname = labeled(tr('Nombre del perfil'), text_entry(p.get('name')))
            types = [tr('Archivo M3U'), tr('URL M3U'), 'Xtream Codes']
            kinds = {types[0]:'file', types[1]:'url', types[2]:'xtream'}
            source_type = labeled(tr('Tipo de fuente'), combo(types, next((v for v,k in kinds.items() if k == p['type']), types[0])))
            source = labeled(tr('Ruta del archivo o URL M3U'), text_entry(p.get('source')))
            server = labeled(tr('Servidor Xtream, con http:// o https://'), text_entry(p.get('server')))
            username = labeled(tr('Usuario Xtream'), text_entry(p.get('username')))
            password = labeled(tr('Contraseña Xtream'), text_entry(p.get('password'), hidden=True))
            fmt = labeled(tr('Formato Xtream'), combo(['m3u8','ts'], p.get('format','m3u8')))
            epg = labeled(tr('EPG XMLTV: URL, archivo .xml o .xml.gz'), text_entry(p.get('epg_url')))
            epg_file_button = Gtk.Button(label=tr('Buscar archivo EPG…'))
            epg_file_button.set_halign(Gtk.Align.START)
            outer.append(epg_file_button)
            def epg_selected(dlg, result):
                try:
                    f = dlg.open_finish(result)
                    if f and f.get_path(): epg.set_text(f.get_path())
                except GLib.Error: pass
            epg_file_button.connect('clicked', lambda *_: Gtk.FileDialog(
                title=tr('Seleccionar EPG XMLTV (.xml o .xml.gz)')).open(win, None, epg_selected))
            divider = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL); outer.append(divider)
            lh = Gtk.Label(label=tr('Logos y pastillas de canales'), xalign=0)
            lh.add_css_class('iptv-heading'); outer.append(lh)
            ch = self._logo_selected_channel()
            help_logos = Gtk.Label(label=(tr('Canal seleccionado: ') + ch.name if ch else tr('Selecciona un canal en la lista principal.')))
            help_logos.set_xalign(0); help_logos.set_wrap(True); outer.append(help_logos)
            preview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            preview_box.set_halign(Gtk.Align.START)
            if ch:
                preview_box.append(self.channel_pill(ch, 148, 58))
            self._logo_settings_preview = (ch, preview_box)
            outer.append(preview_box)
            logo_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            choose_logo_btn = Gtk.Button(label=tr('Cargar PNG/JPG/WebP…'))
            choose_logo_btn.connect('clicked', lambda *_: self.choose_custom_logo(channel=ch))
            choose_logo_btn.set_sensitive(bool(ch))
            logo_actions.append(choose_logo_btn)
            url_logo_btn = Gtk.Button(label=tr('Logo desde URL…'))
            url_logo_btn.connect('clicked', lambda *_: self.choose_custom_logo_url(channel=ch))
            url_logo_btn.set_sensitive(bool(ch))
            logo_actions.append(url_logo_btn)
            reset_logo_btn = Gtk.Button(label=tr('Restaurar logo'))
            reset_logo_btn.connect('clicked', lambda *_: self.reset_selected_logo())
            reset_logo_btn.set_sensitive(bool(ch))
            logo_actions.append(reset_logo_btn)
            outer.append(logo_actions)
            logo_expl = Gtk.Label(label=tr('SYN guarda una copia del archivo por perfil, usa el color del logo y muestra el nombre si falta imagen. Clic derecho en la pastilla para cambiarla.'), xalign=0)
            logo_expl.set_wrap(True); logo_expl.add_css_class('iptv-details'); outer.append(logo_expl)
            divider = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL); outer.append(divider)
            mpvh = Gtk.Label(label=tr('Opciones de MPV'), xalign=0); mpvh.add_css_class('iptv-heading')
            outer.append(mpvh)
            opts = self.cfg.get('player', {})
            ua = labeled(tr('User-Agent de reproducción (MPV)'), combo(['Predeterminado','VLC','Firefox','Safari','Personalizado'], opts.get('user_agent','Predeterminado'), localized=True))
            custom_ua = labeled(tr('User-Agent personalizado de reproducción'), text_entry(opts.get('custom_ua','')))
            source_ua = labeled('User-Agent para M3U, Xtream, EPG y logos',
                                combo(['Predeterminado','VLC','Firefox','Safari','Personalizado'],
                                      opts.get('source_user_agent','Predeterminado'), localized=True))
            source_custom_ua = labeled('User-Agent personalizado de las fuentes',
                                       text_entry(opts.get('source_custom_ua','')))
            hwdec = labeled(tr('Decodificación de hardware'), combo(['Predeterminado','no','auto-safe','auto'], opts.get('hwdec','Predeterminado'), localized=True))
            cache = labeled(tr('Caché de MPV'), combo(['Predeterminado','auto','yes','no'], opts.get('cache','Predeterminado'), localized=True))
            sync = labeled(tr('Sincronización de vídeo'), combo(['Predeterminado','audio','display-resample'], opts.get('video_sync','Predeterminado'), localized=True))
            mb = labeled(tr('Búfer demuxer, MiB (0 = predeterminado)'), Gtk.SpinButton.new_with_range(0, 1024, 16))
            mb.set_value(int(opts.get('demuxer_mb',0) or 0))
            tip = Gtk.Label(label=tr('Las opciones de MPV se aplican al reiniciar SYN. No se modifica OpenGL integrado ni el sistema.'), xalign=0)
            tip.set_wrap(True); tip.add_css_class('iptv-details'); outer.append(tip)
            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            actions.set_margin_top(10); outer.append(actions)
            delete = Gtk.Button(label=tr('Eliminar perfil')); actions.append(delete)
            cancel = Gtk.Button(label=tr('Cancelar')); actions.append(cancel)
            save = Gtk.Button(label=tr('Guardar ajustes')); save.add_css_class('suggested-action'); actions.append(save)
            notice = Gtk.Label(label='', xalign=0); notice.set_wrap(True)
            outer.append(notice)
            state = {'id': self.profile['id']}
            def update_fields():
                is_xtream = selected(source_type) == 'Xtream Codes'
                source.set_sensitive(not is_xtream)
                for w in (server, username, password, fmt): w.set_sensitive(is_xtream)
            def picked(_w, *_):
                index = picker.get_selected()
                if index == len(self.cfg['profiles']):
                    state['id'] = None
                    pname.set_text(tr('Nuevo perfil')); source.set_text(''); server.set_text('');
                    username.set_text(''); password.set_text(''); epg.set_text('')
                    source_type.set_selected(0)
                else:
                    q = self.cfg['profiles'][index]; state['id'] = q['id']
                    pname.set_text(q.get('name', '')); source.set_text(q.get('source',''))
                    server.set_text(q.get('server','')); username.set_text(q.get('username',''))
                    password.set_text(q.get('password','')); epg.set_text(q.get('epg_url',''))
                    source_type.set_selected(types.index(next(k for k,v in kinds.items() if v == q['type'])))
                    fmt.set_selected(1 if q.get('format') == 'ts' else 0)
                update_fields()
            picker.connect('notify::selected', picked)
            source_type.connect('notify::selected', lambda *_: update_fields())
            update_fields()
            def save_click(*_):
                obj = {
                    'id': state['id'] or sources.next_profile_id(),
                    'name': pname.get_text().strip(),
                    'type': kinds[selected(source_type)],
                    'source': source.get_text().strip(),
                    'server': server.get_text().strip(),
                    'username': username.get_text().strip(),
                    'password': password.get_text(),
                    'format': selected(fmt), 'epg_url': epg.get_text().strip(),
                }
                old = next((q for q in self.cfg['profiles'] if q.get('id') == obj['id']), None)
                if old:
                    obj['favorites'] = old.get('favorites', [])
                    obj['logo_overrides'] = old.get('logo_overrides', {})
                try: sources.validate_profile(obj)
                except ValueError as exc:
                    notice.set_text(str(exc)); return
                if old:
                    self.cfg['profiles'][self.cfg['profiles'].index(old)] = obj
                else: self.cfg['profiles'].append(obj)
                self.cfg['selected'] = obj['id']
                try:
                    self.cfg['accent_hex'] = normalize_accent_hex(accent_picker.get_text())
                except ValueError as exc:
                    notice.set_text(str(exc)); return
                self.cfg['theme'] = theme_codes[theme_picker.get_selected()]
                self.get_application().apply_theme(self.cfg['theme'], self.cfg['accent_hex'])
                self.cfg['player'] = {
                    'user_agent': ['Predeterminado','VLC','Firefox','Safari','Personalizado'][ua.get_selected()], 'custom_ua': custom_ua.get_text().strip(),
                    'source_user_agent': ['Predeterminado','VLC','Firefox','Safari','Personalizado'][source_ua.get_selected()],
                    'source_custom_ua': source_custom_ua.get_text().strip(),
                    'hwdec': ['Predeterminado','no','auto-safe','auto'][hwdec.get_selected()], 'cache': ['Predeterminado','auto','yes','no'][cache.get_selected()],
                    'video_sync': ['Predeterminado','audio','display-resample'][sync.get_selected()], 'demuxer_mb': mb.get_value_as_int()
                }
                sources.save_config(self.cfg)
                # Source downloads use new settings without waiting for MPV restart.
                # The current libmpv instance retains its own agent until restart.
                self.player_options = dict(self.cfg['player'])
                self.profile = obj
                self.favorites = set(obj.get('favorites', []))
                self.profile_picker.set_model(Gtk.StringList.new([q['name'] for q in self.cfg['profiles']]))
                self.profile_picker.set_selected(self.cfg['profiles'].index(obj))
                self.load_channels()
                self.status.set_text(tr('Ajustes guardados. Reinicia SYN para aplicar las opciones de MPV.'))
                win.close()
            def delete_click(*_):
                if len(self.cfg['profiles']) <= 1:
                    notice.set_text(tr('Debe quedar al menos un perfil.')); return
                old = next((q for q in self.cfg['profiles'] if q['id'] == state['id']), None)
                if not old:
                    notice.set_text(tr('Selecciona un perfil existente.')); return
                self.cfg['profiles'].remove(old)
                self.profile = self.cfg['profiles'][0]
                self.cfg['selected'] = self.profile['id']
                self.favorites = set(self.profile.get('favorites', []))
                sources.save_config(self.cfg)
                self.profile_picker.set_model(Gtk.StringList.new([q['name'] for q in self.cfg['profiles']]))
                self.profile_picker.set_selected(0)
                self.load_channels(); win.close()
            save.connect('clicked', save_click)
            delete.connect('clicked', delete_click)
            cancel.connect('clicked', lambda *_: win.close())
            win.set_child(scroll); win.present()

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

        def do_activate(self):
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

        def _gtk_theme_changed(self, *_):
            if self._current_theme == 'system' and not getattr(self, '_theme_guard', False):
                self.apply_theme('system', self._accent_hex)

        def _poll_host_theme(self):
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
                return tr('Claro = Teal pastel, Oscuro = gris/negro, Teal SYN = petróleo original. El CSS GTK4 del anfitrión solo se incorpora en Sistema.')
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
            if theme not in ('system','light','dark','teal'):
                theme = 'system'
            if accent_hex is not None:
                try: self._accent_hex = normalize_accent_hex(accent_hex)
                except ValueError: self._accent_hex = ''
            self._current_theme = theme
            manager = self._adw_manager
            self._theme_guard = True
            try:
                if theme == 'system':
                    name, host_dark = self._host_theme()
                    gtk_settings = getattr(self, '_gtk_theme_settings', None)
                    prefer_dark = False
                    if gtk_settings:
                        try:
                            prefer_dark = bool(gtk_settings.get_property(
                                'gtk-application-prefer-dark-theme'))
                        except (TypeError, ValueError): pass
                    dark_gtk = gtk_theme_prefers_dark(name, prefer_dark or host_dark)
                    if dark_gtk:
                        mode = Adw.ColorScheme.FORCE_DARK
                    elif re.search(r'(?:^|[-_:])light(?:$|[-_:])', str(name or '').lower()):
                        mode = Adw.ColorScheme.FORCE_LIGHT
                    else:
                        # Si GTK no expresa claramente claro/oscuro, dejar que
                        # el portal XDG/GNOME/KDE determine el esquema real.
                        mode = Adw.ColorScheme.DEFAULT
                elif theme == 'light':
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
                css = BASE_CSS + dvr_palette_css('system') + logo_pill_css(dark=manager.get_dark(), pastel=(theme == 'light'), teal=(theme == 'teal'))
                self.theme_provider.load_from_data(css.encode('utf-8'))
                # The accent CSS is loaded separately at higher priority so
                # Adwaita and all bundled color schemes cannot override it.
                self.accent_provider.load_from_data(
                    accent_css(getattr(self, '_accent_hex', '')).encode('utf-8'))
                if theme in ('teal','light','dark') and display:
                    palette_css = {'teal': TEAL_CSS, 'light': LIGHT_CSS, 'dark': DARK_CSS}[theme] + dvr_palette_css(theme)
                    self.teal_theme_provider.load_from_data(palette_css.encode('utf-8'))
                    Gtk.StyleContext.add_provider_for_display(
                        display, self.teal_theme_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
                    self._teal_provider_active = True
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
