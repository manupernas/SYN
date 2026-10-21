"""Pure EPG favourite helpers for SYN 1.3b private revision 2.

No GTK dependency. Existing channel objects and provider EPG tuples are preserved.
"""
from __future__ import annotations

FAVORITES_CATEGORY = '__syn_favorite_channels__'
ALL_CATEGORY = 'Todas las categorías'


def filter_channels(channels, favorite_ids, category, search, normalize):
    """Use the ORIGINAL channel objects; filtering must never remap EPG ids."""
    query = normalize(search.strip())
    return [ch for ch in channels
            if (category == ALL_CATEGORY or
                (category == FAVORITES_CATEGORY and ch.favorite_id in favorite_ids) or
                ch.group == category)
            and (not query or query in normalize(ch.name + ' ' + ch.group))]


def programmes_for(channel, channels, guide, aliases, lookup, normalize):
    """Same EPG lookup as category view; safe duplicate-channel fallback.

    Some providers duplicate a channel across groups but only one entry has a
    usable XMLTV ID. Do not change the selected channel or favourite identity.
    """
    found = lookup(channel, guide, aliases)
    if found:
        return found
    # Prefer matching live source; compare names only if no URL/EPG match.
    comparable = []
    for other in channels:
        if other is channel:
            continue
        if (getattr(other, 'url', None) and other.url == channel.url) or (
                getattr(other, 'epg_id', None) and other.epg_id == channel.epg_id):
            comparable.append(other)
    for other in comparable:
        result = lookup(other, guide, aliases)
        if result:
            return result
    # Only use a unique normalised name, avoiding EPG borrowed from homonyms.
    needle = normalize(channel.name)
    same_name = [other for other in channels if other is not channel and normalize(other.name) == needle]
    if len(same_name) == 1:
        return lookup(same_name[0], guide, aliases)
    return found
