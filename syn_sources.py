"""SYN: sources (M3U file/URL/Xtream), cached channel logos, and XMLTV EPG.

Pure Python; no GTK dependency. Network I/O must run in worker threads.
URLs and credentials are never written to logs; storage uses 0700/0600 modes.
"""
from __future__ import annotations
from syn_i18n import translate as _

import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
import time
import urllib.parse as U
import urllib.request as R
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

APP_CONFIG = Path.home() / '.config' / 'syn'
APP_CACHE = Path.home() / '.cache' / 'syn'
CONFIG_FILE = APP_CONFIG / 'profiles.json'
MAX_PLAYLIST = 28 * 1024 * 1024
MAX_EPG = 85 * 1024 * 1024
MAX_LOGO = 1024 * 1024
ATTR_RE = re.compile(r'([\w-]+)\s*=\s*"([^"]*)"')
XMLTV_DATE_RE = re.compile(r'^(\d{14})(?:\s*([+-]\d{4}|Z))?')


@dataclass(frozen=True)
class Channel:
    name: str
    group: str
    url: str
    logo: str = ''
    epg_id: str = ''

    @property
    def favorite_id(self):
        return f'{self.group}|{self.name}'


def secure_dir(folder):
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    try: folder.chmod(0o700)
    except OSError: pass


def secure_write(path, content: bytes):
    secure_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix='.syn-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as fp:
            fp.write(content)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def blank_config():
    return {'profiles': [], 'selected': '', 'theme':'system', 'accent_hex':'', 'last_ui': {}, 'player': {'user_agent': 'Predeterminado', 'custom_ua': '', 'hwdec': 'Predeterminado', 'cache': 'Predeterminado', 'demuxer_mb': 0, 'video_sync': 'Predeterminado'}}


def load_config():
    out = blank_config()
    try:
        raw = json.loads(CONFIG_FILE.read_text('utf-8'))
        if isinstance(raw, dict):
            out.update({k: raw[k] for k in ('profiles', 'selected', 'player', 'theme', 'accent_hex', 'last_ui') if k in raw})
        if 'theme' not in raw: out['theme'] = 'teal'  # Preservar el aspecto de SYN 2.1 en actualizaciones
        if not isinstance(out.get('accent_hex'), str): out['accent_hex'] = ''
        if not isinstance(out['profiles'], list): out['profiles'] = []
        if not isinstance(out['player'], dict): out['player'] = blank_config()['player']
    except (OSError, ValueError): pass
    return out


def save_config(cfg):
    secure_write(CONFIG_FILE, json.dumps(cfg, ensure_ascii=False, indent=2).encode('utf-8'))


def next_profile_id():
    import uuid
    return uuid.uuid4().hex[:12]


def default_profile(legacy_playlist=None):
    return {'id': next_profile_id(), 'name': 'Mi televisión', 'type': 'file', 'source': str(legacy_playlist or (Path.home() / 'Vídeos' / 'alacarta.m3u')), 'server': '', 'username': '', 'password': '', 'format': 'm3u8', 'epg_url': ''}


def validate_profile(p):
    kind = p.get('type')
    if kind not in ('file', 'url', 'xtream'): raise ValueError(_('Elige archivo M3U, URL M3U o Xtream.'))
    if not p.get('name', '').strip(): raise ValueError(_('Escribe un nombre para el perfil.'))
    if kind == 'file':
        if not Path(p.get('source', '')).expanduser().is_file(): raise ValueError(_('No existe el archivo M3U.'))
    elif kind == 'url':
        require_http(p.get('source', ''))
    else:
        require_http(p.get('server', ''))
        if not p.get('username') or not p.get('password'): raise ValueError(_('Falta usuario o contraseña Xtream.'))
    if p.get('epg_url'): validate_epg_source(p['epg_url'])


def require_http(url):
    parsed = U.urlsplit((url or '').strip())
    if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname:
        raise ValueError(_('Introduce una URL http:// o https:// válida.'))
    return url.strip()


def validate_epg_source(value):
    """XMLTV admite URL o archivo local .xml/.xml.gz, sin redireccionar claves."""
    value = str(value or '').strip()
    if not value: return ''
    if value.startswith(('http://', 'https://')):
        return require_http(value)
    path = Path(value).expanduser()
    if not (path.name.lower().endswith('.xml') or path.name.lower().endswith('.xml.gz')):
        raise ValueError(_('El EPG debe ser un XMLTV .xml o .xml.gz, local o por URL.'))
    if not path.is_file():
        raise ValueError(_('No existe el archivo XMLTV indicado.'))
    return str(path)


def read_local_xmltv(value, max_size=MAX_EPG):
    path = Path(validate_epg_source(value))
    if path.stat().st_size > max_size:
        raise ValueError(_('El archivo EPG supera el tamaño máximo permitido.'))
    opener = gzip.open if path.name.lower().endswith('.gz') else open
    with opener(path, 'rb') as src:
        data = src.read(max_size + 1)
    if len(data) > max_size:
        raise ValueError(_('El EPG descomprimido supera el tamaño máximo.'))
    return data


def limited_http(url, max_size, accept='*/*', user_agent=None):
    url = require_http(url)
    request = R.Request(url, headers={'Accept': accept, 'User-Agent': user_agent or 'SYN/2.0', 'Accept-Encoding': 'gzip'})
    with R.urlopen(request, timeout=22) as response:
        data = response.read(max_size + 1)
        if len(data) > max_size: raise ValueError(_('El archivo remoto supera el tamaño permitido.'))
        zipped = response.headers.get('Content-Encoding', '') == 'gzip' or url.split('?')[0].lower().endswith('.gz')
    if zipped:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            data = stream.read(max_size + 1)
        if len(data) > max_size: raise ValueError(_('El contenido descomprimido es demasiado grande.'))
    return data


def parse_m3u(blob):
    if isinstance(blob, bytes): blob = blob.decode('utf-8-sig', 'replace')
    result, meta, group = [], None, 'Otros'
    for line in blob.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF'):
            attrs = dict(ATTR_RE.findall(line))
            name = line.split(',', 1)[1].strip() if ',' in line else attrs.get('tvg-name', '')
            group = attrs.get('group-title') or 'Otros'
            meta = (name or 'Sin nombre', group, attrs.get('tvg-logo', ''), attrs.get('tvg-id', ''))
        elif line.startswith('#EXTGRP:') and meta:
            group = line.partition(':')[2].strip() or 'Otros'
            meta = (meta[0], group, meta[2], meta[3])
        elif line and not line.startswith('#'):
            if meta and U.urlsplit(line).scheme.lower() in ('http','https','rtsp','rtmp','udp','mms'):
                result.append(Channel(meta[0], meta[1], line, meta[2], meta[3]))
            meta = None
    return result


def xtream_url(p, endpoint, action=None):
    base = require_http(p.get('server', '')).rstrip('/')
    params = {'username': p['username'], 'password': p['password']}
    if action: params['action'] = action
    return base + '/' + endpoint + '?' + U.urlencode(params)


def profile_epg_url(p):
    if p.get('epg_url'): return p['epg_url'].strip()
    if p.get('type') == 'xtream': return xtream_url(p, 'xmltv.php')
    return ''


def load_channels(p, user_agent=None):
    validate_profile(p)
    if p['type'] == 'file':
        path = Path(p['source']).expanduser()
        if path.stat().st_size > MAX_PLAYLIST: raise ValueError(_('La lista M3U es demasiado grande.'))
        return parse_m3u(path.read_bytes())
    if p['type'] == 'url': return parse_m3u(limited_http(p['source'], MAX_PLAYLIST, user_agent=user_agent))
    categories = json.loads(limited_http(xtream_url(p, 'player_api.php', 'get_live_categories'), MAX_PLAYLIST, user_agent=user_agent))
    streams = json.loads(limited_http(xtream_url(p, 'player_api.php', 'get_live_streams'), MAX_PLAYLIST, user_agent=user_agent))
    if not isinstance(streams, list): raise ValueError(_('Xtream no devolvió una lista de canales.'))
    groups = {str(c.get('category_id')): str(c.get('category_name') or 'Otros') for c in categories if isinstance(c, dict)} if isinstance(categories, list) else {}
    result = []
    fmt = p.get('format', 'm3u8') if p.get('format') in ('ts', 'm3u8') else 'm3u8'
    for item in streams:
        if not isinstance(item, dict): continue
        sid = str(item.get('stream_id', ''))
        if not sid.isdecimal(): continue
        base = require_http(p['server']).rstrip('/')
        url = f'{base}/live/{U.quote(p["username"], safe="")}/{U.quote(p["password"], safe="")}/{sid}.{fmt}'
        result.append(Channel(str(item.get('name') or 'Sin nombre'), groups.get(str(item.get('category_id')), 'Otros'), url, str(item.get('stream_icon') or ''), str(item.get('epg_channel_id') or '')))
    return result


def xmltv_time(raw):
    match = XMLTV_DATE_RE.match(raw or '')
    if not match: return None
    main, zone = match.groups()
    tz = dt.timezone.utc
    if zone and zone != 'Z':
        n = int(zone[1:3]) * 60 + int(zone[3:5]); n *= -1 if zone.startswith('-') else 1
        tz = dt.timezone(dt.timedelta(minutes=n))
    try: return dt.datetime.strptime(main, '%Y%m%d%H%M%S').replace(tzinfo=tz).astimezone()
    except ValueError: return None


def parse_xmltv(blob):
    """Returns (programmes by channel id, channel display-name aliases)."""
    guide, aliases = {}, {}
    for evt, elem in ET.iterparse(io.BytesIO(blob), events=('end',)):
        if elem.tag == 'channel':
            key = elem.attrib.get('id', '')
            for tag in elem.findall('display-name'):
                if tag.text and key:
                    aliases.setdefault(tag.text.casefold().strip(), key)
            elem.clear()
        elif elem.tag == 'programme':
            ch = elem.attrib.get('channel', '')
            start, stop = xmltv_time(elem.attrib.get('start')), xmltv_time(elem.attrib.get('stop'))
            title = elem.findtext('title') or 'Sin título'
            if ch and start and stop and stop > start:
                guide.setdefault(ch, []).append((start, stop, title.strip(), (elem.findtext('desc') or '').strip()))
            elem.clear()
    for programmes in guide.values(): programmes.sort(key=lambda event: event[0])
    return guide, aliases


def guide_cache_path(p):
    return APP_CACHE / ('epg-' + hashlib.sha256(p['id'].encode('utf-8')).hexdigest()[:16] + '.xml')


def get_epg(p, force=False, user_agent=None):
    url = profile_epg_url(p)
    if not url: return {}, {}
    if not url.startswith(('http://', 'https://')):
        # Fuente local: recargar directamente. Así las ediciones al XMLTV
        # son visibles sin esperar las seis horas de caché remota.
        return parse_xmltv(read_local_xmltv(url))
    path = guide_cache_path(p)
    if force or not path.is_file() or time.time() - path.stat().st_mtime > 6 * 3600:
        contents = limited_http(url, MAX_EPG, 'application/xml,text/xml,*/*', user_agent=user_agent)
        # Parse before caching invalid sources.
        parsed = parse_xmltv(contents)
        secure_write(path, contents)
        return parsed
    return parse_xmltv(path.read_bytes())


def epg_for_channel(channel, guide, aliases):
    key = channel.epg_id
    if key not in guide:
        key = aliases.get(channel.name.casefold().strip(), key)
    return guide.get(key, [])


def now_next(channel, guide, aliases, when=None):
    when = when or dt.datetime.now().astimezone()
    programmes = epg_for_channel(channel, guide, aliases)
    current = next((x for x in programmes if x[0] <= when < x[1]), None)
    future = [x for x in programmes if x[0] > when][:4]
    return current, future


def logo_path(url):
    extension = '.png'
    path = U.urlsplit(url).path.lower()
    if path.endswith('.jpg') or path.endswith('.jpeg'): extension = '.jpg'
    if path.endswith('.webp'): extension = '.webp'
    return APP_CACHE / 'logos' / (hashlib.sha256(url.encode('utf-8')).hexdigest() + extension)


def get_logo(url, user_agent=None):
    require_http(url)
    target = logo_path(url)
    if target.is_file(): return target
    image = limited_http(url, MAX_LOGO, 'image/png,image/jpeg,image/webp,image/*', user_agent=user_agent)
    if not (image.startswith(b'\x89PNG') or image.startswith(b'\xff\xd8\xff') or image.startswith(b'RIFF')):
        raise ValueError(_('Formato de logo no admitido.'))
    secure_write(target, image)
    return target




# Los logos del usuario son independientes de los logos del proveedor.
# Solo se guarda el nombre generado, no rutas arbitrarias ni credenciales.
LOGO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
MAX_CUSTOM_LOGO = 8 * 1024 * 1024


def custom_logo_path(profile, channel):
    stored = profile.get('logo_overrides', {})
    value = stored.get(channel.favorite_id) if isinstance(stored, dict) else None
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}\.(?:png|jpg|jpeg|webp)', value):
        return None
    profile_id = str(profile.get('id', ''))
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', profile_id):
        return None
    path = APP_CONFIG / 'logos' / profile_id / value
    return path if path.is_file() else None


def custom_logo_type(raw):
    """Comprueba firmas reales, no extensiones ni Content-Type enviados."""
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if raw.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if raw.startswith(b'RIFF') and raw[8:12] == b'WEBP':
        return '.webp'
    raise ValueError(_('El logo debe ser PNG, JPG o WebP.'))


def install_custom_logo_bytes(profile, channel, data):
    """Guarda una copia local por perfil y canal, independientemente del origen."""
    if not data or len(data) > MAX_CUSTOM_LOGO:
        raise ValueError(_('El logo está vacío o supera los 8 MiB.'))
    ext = custom_logo_type(data)
    profile_id = str(profile.get('id', ''))
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', profile_id):
        raise ValueError(_('Identificador del perfil incorrecto.'))
    basename = hashlib.sha256(channel.favorite_id.encode('utf-8')).hexdigest() + ext
    output = APP_CONFIG / 'logos' / profile_id / basename
    secure_write(output, data)
    profile.setdefault('logo_overrides', {})[channel.favorite_id] = basename
    return output


def install_custom_logo(profile, channel, incoming):
    path = Path(incoming)
    if path.suffix.lower() not in LOGO_EXTENSIONS:
        raise ValueError(_('Selecciona PNG, JPG, JPEG o WebP.'))
    if not path.is_file() or path.stat().st_size > MAX_CUSTOM_LOGO:
        raise ValueError(_('La imagen no existe o supera los 8 MiB.'))
    with path.open('rb') as stream:
        raw = stream.read(MAX_CUSTOM_LOGO + 1)
    return install_custom_logo_bytes(profile, channel, raw)


def download_custom_logo_url(url, user_agent=None):
    """Descarga limitada (8 MiB) en hilo auxiliar; no guarda la URL privada."""
    require_http(url)
    data = limited_http(url, MAX_CUSTOM_LOGO,
                        'image/png,image/jpeg,image/webp,image/*',
                        user_agent=user_agent)
    custom_logo_type(data)
    return data


def install_custom_logo_url(profile, channel, url, user_agent=None):
    """Útil para scripts: descarga el logo y guarda solamente los bytes."""
    return install_custom_logo_bytes(profile, channel,
                                     download_custom_logo_url(url, user_agent))


def reset_custom_logo(profile, channel):
    overrides = profile.get('logo_overrides', {})
    if isinstance(overrides, dict):
        overrides.pop(channel.favorite_id, None)


def network_user_agent(player_options):
    """HTTP fetching follows the chosen profile for remote sources.

    Predeterminado leaves mpv untouched for video; the playlist downloader
    identifies itself as SYN.
    """
    options = player_options or {}
    profiles = {
        'VLC': 'VLC/3.0.21 LibVLC/3.0.21',
        'Firefox': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
        'Safari': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Personalizado': str(options.get('custom_ua', '')).strip(),
    }
    return profiles.get(options.get('user_agent', 'Predeterminado')) or 'SYN/2.0'
