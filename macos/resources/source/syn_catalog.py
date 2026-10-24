"""SYN 1.3.5b: IPTV catalogs for M3U and Xtream. No GTK; never log IPTV URLs."""
from __future__ import annotations
import json
import re
from urllib.parse import quote, urlsplit, urljoin
import syn_sources as sources

_MOVIE = re.compile(r'(?i)(?:\b(?:vod|pel[ií]culas?|movies?|filmes?|cine|cinema)\b)')
_SERIES = re.compile(r'(?i)(?:\b(?:series?|s[eé]ries?|episodios?|shows?|temporadas?|seasons?)\b)')


def is_media(channel):
    """Classify M3U entries, leaving regular TV untouched."""
    group = str(channel.group or '')
    u = urlsplit(channel.url or '')
    path = u.path.casefold()
    if '/series/' in path or _SERIES.search(group):
        return 'series'
    if '/movie/' in path or '/vod/' in path or _MOVIE.search(group):
        return 'movies'
    return 'tv'


def partition_channels(channels):
    tv, movies, series = [], [], []
    for ch in channels:
        kind = is_media(ch)
        if kind == 'movies':
            movies.append(ch)
        elif kind == 'series':
            series.append(ch)
        else:
            tv.append(ch)
    return tv, movies, series


def _fetch(profile, action, user_agent):
    url = sources.xtream_url(profile, 'player_api.php', action)
    data = json.loads(sources.limited_http(url, sources.MAX_PLAYLIST, user_agent=user_agent))
    return data


def _groups(data):
    if not isinstance(data, list):
        return {}
    return {str(x.get('category_id')): str(x.get('category_name') or 'Sin categoría')
            for x in data if isinstance(x, dict)}


def _title(value, fallback):
    return str(value or fallback).strip()[:240]


def _poster(value, base=''):
    value = str(value or '').strip()
    if value.startswith(('https://', 'http://')):
        return value
    # Xtream can return an absolute image path on the same server.
    if value.startswith('/') and base:
        return urljoin(base + '/', value)
    return ''


def _poster_options(values, base=''):
    result = []
    for value in values:
        image = _poster(value, base)
        if image and image not in result:
            result.append(image)
    return result[:4]


def load_xtream_catalog(profile, user_agent=None):
    """Returns movies, series, and per-family error flags; no exceptions with URL leaks."""
    if profile.get('type') != 'xtream':
        return [], [], []
    movies, series, errors = [], [], []
    base = sources.require_http(profile['server']).rstrip('/')
    user = quote(profile['username'], safe='')
    password = quote(profile['password'], safe='')
    try:
        mgroups = _groups(_fetch(profile, 'get_vod_categories', user_agent))
        rows = _fetch(profile, 'get_vod_streams', user_agent)
        for x in rows if isinstance(rows, list) else []:
            if not isinstance(x, dict):
                continue
            sid = str(x.get('stream_id', ''))
            if not sid.isdecimal():
                continue
            ext = str(x.get('container_extension') or 'mp4').lower()
            if ext not in ('mp4', 'mkv', 'avi', 'ts', 'mov'):
                ext = 'mp4'
            covers = _poster_options((x.get('cover_big'), x.get('cover'),
                                      x.get('stream_icon'), x.get('movie_image'),
                                      x.get('poster')), base)
            movies.append({'name': _title(x.get('name'), 'Película'),
                           'group': mgroups.get(str(x.get('category_id')), 'Cine'),
                           'poster': covers[0] if covers else '',
                           'poster_options': covers,
                           'year': str(x.get('year') or '')[:4],
                           'url': f'{base}/movie/{user}/{password}/{sid}.{ext}',
                           'kind': 'movies'})
    except (OSError, ValueError, KeyError, TypeError):
        errors.append('movies')
    try:
        sgroups = _groups(_fetch(profile, 'get_series_categories', user_agent))
        rows = _fetch(profile, 'get_series', user_agent)
        for x in rows if isinstance(rows, list) else []:
            if not isinstance(x, dict):
                continue
            sid = str(x.get('series_id', ''))
            if not sid.isdecimal():
                continue
            covers = _poster_options((x.get('cover_big'), x.get('cover'),
                                      x.get('stream_icon'), x.get('poster')), base)
            series.append({'name': _title(x.get('name'), 'Serie'),
                           'group': sgroups.get(str(x.get('category_id')), 'Series'),
                           'poster': covers[0] if covers else '',
                           'poster_options': covers,
                           'year': str(x.get('releaseDate') or x.get('year') or '')[:4],
                           'id': sid, 'kind': 'series'})
    except (OSError, ValueError, KeyError, TypeError):
        errors.append('series')
    return movies, series, errors


def episodes_for_xtream(profile, series_id, user_agent=None):
    """Loads per-series episodes only on click, preserving server-side pagination load."""
    if profile.get('type') != 'xtream' or not str(series_id).isdecimal():
        return []
    url = sources.xtream_url(profile, 'player_api.php', 'get_series_info')
    url += '&series_id=' + str(series_id)
    data = json.loads(sources.limited_http(url, sources.MAX_PLAYLIST, user_agent=user_agent))
    groups = data.get('episodes', {}) if isinstance(data, dict) else {}
    if not isinstance(groups, dict):
        return []
    base = sources.require_http(profile['server']).rstrip('/')
    user, password = quote(profile['username'], safe=''), quote(profile['password'], safe='')
    episodes = []
    for season, entries in sorted(groups.items(), key=lambda pair: int(pair[0]) if str(pair[0]).isdecimal() else 999):
        if not isinstance(entries, list):
            continue
        for n, x in enumerate(entries, 1):
            if not isinstance(x, dict):
                continue
            ep = str(x.get('id', ''))
            if not ep.isdecimal():
                continue
            ext = str(x.get('container_extension') or 'mp4').lower()
            if ext not in ('mp4', 'mkv', 'ts', 'avi', 'mov'):
                ext = 'mp4'
            info = x.get('info') if isinstance(x.get('info'), dict) else {}
            episode_num = str(x.get('episode_num') or n)
            episodes.append({'name': _title(x.get('title'), 'Episodio ' + episode_num),
                             'group': 'Temporada ' + str(season),
                             'poster': _poster(info.get('movie_image') or info.get('cover_big')),
                             'url': f'{base}/series/{user}/{password}/{ep}.{ext}',
                             'kind': 'episode'})
    return episodes


def local_entries(channels, kind):
    return [{'name': ch.name, 'group': ch.group, 'poster': _poster(ch.logo),
             'poster_options': [_poster(ch.logo)] if _poster(ch.logo) else [],
             'url': ch.url, 'kind': kind} for ch in channels]

_EPISODE_MARK = re.compile(r'(?i)\b(?:s\d{1,2}\s*e\d{1,3}|\d{1,2}x\d{1,3}|temporada\s*\d+\s*episodio\s*\d+)\b')


def local_series_catalog(channels):
    """Group M3U episodes when conventional S01E01-style metadata is present."""
    by_name = {}
    for ch in channels:
        name = str(ch.name)
        match = _EPISODE_MARK.search(name)
        if match:
            show = name[:match.start()].strip(' |-:._') or name
        else:
            # Without a recognizable episode number, don't merge unrelated content.
            show = name
        key = show.casefold()
        entry = by_name.get(key)
        if entry is None:
            entry = {'name': show, 'group': ch.group, 'poster': _poster(ch.logo),
                     'poster_options': [_poster(ch.logo)] if _poster(ch.logo) else [],
                     'kind': 'series', 'children': []}
            by_name[key] = entry
        entry['children'].append({'name': ch.name, 'group': ch.group,
                                  'poster': _poster(ch.logo), 'url': ch.url,
                                  'kind': 'episode'})
        if not entry['poster']:
            entry['poster'] = _poster(ch.logo)
            entry['poster_options'] = [_poster(ch.logo)] if _poster(ch.logo) else []
    return list(by_name.values())
