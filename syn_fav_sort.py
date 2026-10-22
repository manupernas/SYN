"""SYN favorites order: pure helpers, no GTK, IPTV credentials or network access.

The profile's existing favorites list is the canonical storage. Duplicates are
removed only from the list of identifiers, never from the user's channel feed.
"""
from __future__ import annotations


def normalize(stored, active):
    """Preserve stored relative order, append newly-favorited ids to the end."""
    allowed = set(active)
    result = []
    seen = set()
    for item in stored if isinstance(stored, (list, tuple)) else ():
        if isinstance(item, str) and item in allowed and item not in seen:
            seen.add(item)
            result.append(item)
    for item in sorted(allowed):
        if isinstance(item, str) and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def move(stored, source, target, after=False):
    """Return a new stable profile list with source placed before/after target."""
    values = list(dict.fromkeys(stored))
    if source not in values or target not in values or source == target:
        return values
    values.remove(source)
    at = values.index(target) + (1 if after else 0)
    values.insert(at, source)
    return values


def order_channels(channels, stored):
    """Stable sorting; preserve duplicate channel rows and their EPG identity."""
    ids = stored if isinstance(stored, (list, tuple)) else ()
    positions = {key: pos for pos, key in enumerate(ids) if isinstance(key, str)}
    return sorted(channels, key=lambda ch: positions.get(ch.favorite_id, len(positions)))
