"""SYN i18n: automatically follow the desktop locale, independent of MPV LC_NUMERIC.

Never translate provider channel names or XMLTV programme titles.
"""
from __future__ import annotations
import datetime as _dt
import gettext as _gettext
import os as _os
from pathlib import Path as _Path


def detect_language(environ=None):
    env = _os.environ if environ is None else environ
    # GNU precedence: LC_ALL > LC_MESSAGES > LANGUAGE > LANG. The
    # LANGUAGE list may contain multiple fallbacks separated by colons.
    for key in ('LC_ALL', 'LC_MESSAGES', 'LANGUAGE', 'LANG'):
        raw = str(env.get(key, '') or '').strip()
        if not raw:
            continue
        if key == 'LANGUAGE':
            candidate = next((item for item in raw.split(':') if item), '')
        else:
            candidate = raw
        candidate = candidate.split('.', 1)[0].split('@', 1)[0].replace('-', '_').lower()
        if candidate in ('en_us', 'en_gb'):
            return 'en_US' if candidate == 'en_us' else 'en_GB'
        if candidate.startswith('es') or candidate in ('c','posix'):
            return 'es'
        if candidate.startswith('en'):
            # Other English locales have no dedicated catalogue yet.
            return 'en_GB'
        # Untranslated languages use Spanish for now.
        return 'es'
    return 'es'

# SYN macOS Alpha 5.4: idioma de interfaz español, independientemente de
# LANG/LC_MESSAGES que aporte el lanzador de macOS. Sólo afecta a esta copia
# de SYN Alpha 5; no cambia el idioma del sistema ni el perfil IPTV.
LANGUAGE = 'es' 
_LOCALE_PATH = _Path(__file__).parent / 'locale'
if not (_LOCALE_PATH / LANGUAGE / 'LC_MESSAGES' / 'syn.mo').is_file():
    for candidate in (_Path('/app/share/locale'), _Path('/usr/share/locale')):
        if (candidate / LANGUAGE / 'LC_MESSAGES' / 'syn.mo').is_file():
            _LOCALE_PATH = candidate
            break
_TRANSLATOR = _gettext.translation('syn', localedir=str(_LOCALE_PATH),
                                   languages=[LANGUAGE], fallback=True)

def translate(message):
    from syn_locale_rev3 import localize
    return localize(message, _TRANSLATOR.gettext(message), LANGUAGE)

def format_time(value):
    if LANGUAGE == 'en_US':
        return value.strftime('%I:%M %p').lstrip('0')
    return value.strftime('%H:%M')

def format_day_time(value):
    if LANGUAGE == 'en_US':
        return value.strftime('%m/%d ') + format_time(value)
    return value.strftime('%d/%m ') + format_time(value)

def locale_description():
    return LANGUAGE + (' (12-hour clock)' if LANGUAGE == 'en_US' else ' (24-hour clock)')
