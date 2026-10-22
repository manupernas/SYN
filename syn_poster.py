"""SYN 1.3.5b poster cache: separate from the 1 MiB live-channel logo limit.

Downloads run only in the existing background pool. Original VOD URLs, credentials
and poster URLs never appear in logs. Missing covers are handled by GTK artwork.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlsplit
import syn_sources as sources

MAX_POSTER = 6 * 1024 * 1024


def _extension(data):
    if data.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    return None


def get_poster(options, user_agent=None):
    """Try up to three provider cover addresses and return an image file or None.

    No outside metadata lookup is performed and no failures expose private URLs.
    """
    if isinstance(options, str):
        options = [options]
    seen = set()
    for candidate in (options or [])[:4]:
        url = str(candidate or '').strip()
        if not url or url in seen:
            continue
        seen.add(url)
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            continue
        key = hashlib.sha256(url.encode('utf-8')).hexdigest()
        directory = sources.APP_CACHE / 'posters'
        for ext in ('.jpg', '.png', '.webp'):
            path = directory / (key + ext)
            if path.is_file() and 0 < path.stat().st_size <= MAX_POSTER:
                return path
        try:
            raw = sources.limited_http(
                url, MAX_POSTER, 'image/jpeg,image/png,image/webp,image/*',
                user_agent=user_agent)
            ext = _extension(raw)
            if not ext:
                continue
            path = directory / (key + ext)
            sources.secure_write(path, raw)
            return path
        except (OSError, ValueError, RuntimeError):
            continue
    return None
