"""SYN 2.0.9: ten accessible, colourful EPG programme gradients.

Colour selection advances per programme within each channel (rather than one
colour per channel). A stable per-channel offset makes the overall guide
colourful without random flashes when it refreshes or scrolls.
"""

from hashlib import blake2s

# Rich, muted pastel / pop-art shades. Both endpoints of every gradient have
# at least 4.5:1 WCAG contrast against white text (normal-size labels).
COLORS = (
    ('#BC4E74', '#762C50'),  # berry pink
    ('#B75351', '#73353A'),  # warm coral
    ('#A85B46', '#704139'),  # terracotta peach
    ('#A36431', '#694C2D'),  # honey amber
    ('#588128', '#385927'),  # leafy apple
    ('#40825D', '#275741'),  # pastel jade
    ('#217F83', '#20525A'),  # teal aqua
    ('#4175AC', '#2C4E7C'),  # vintage sky blue
    ('#5C6DB3', '#414A79'),  # periwinkle blue
    ('#8256AC', '#523D75'),  # soft orchid violet
)


def contrast_against_white(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    luminance = sum(w * v for w, v in zip((.2126, .7152, .0722), linear))
    return 1.05 / (luminance + .05)


def epg_programme_color_index(channel_id, programme_position):
    """Return a repeatable palette index for programme N of a channel.

    Avoid Python's salted hash(), so colours do not jump between sessions.
    """
    digest = blake2s(str(channel_id).encode('utf-8'), digest_size=2).digest()
    offset = int.from_bytes(digest, 'big') % len(COLORS)
    return (offset + programme_position) % len(COLORS)


def epg_programme_color_indices(channel_id, programmes, geometry):
    """Colour clipped visible EPG blocks by ORIGINAL programme position.

    *programmes* are the full tuples used by epg_geometry(). *geometry* is the
    resulting list (x, width, clipped_start, clipped_end, title, desc, valid).
    The original ordinal (not the visible index) keeps one programme's colour
    consistent when scrolling the timeline or showing a clipped first block.
    Missing-EPG gaps are kept neutral (None), not painted as programmes.
    """
    ordered = sorted(
        (p for p in programmes if len(p) >= 3 and p[1] > p[0]),
        key=lambda p: p[0],
    )
    indices = []
    fallback_position = 0
    for _x, _width, start, _end, title, _description, available in geometry:
        if not available:
            indices.append(None)
            continue
        # Geometry clips to the viewing window. Recover the programme in the
        # source schedule, so horizontal panning won't recolour the same show.
        original_position = next(
            (i for i, p in enumerate(ordered)
             if p[0] <= start < p[1] and str(p[2]) == str(title)),
            None,
        )
        if original_position is None:
            original_position = fallback_position
        indices.append(epg_programme_color_index(channel_id, original_position))
        fallback_position += 1
    return indices


def epg_gradient_css():
    # Programme tiles only: no channel names, axis, tabs, DVR or video overlays.
    # Retains the existing horizontal gradient direction and GTK geometry.
    rules = [
        '/* SYN 2.0.9: 10 saturated-pastel, accessible EPG programme gradients. */',
        'window.iptv-tv .syn-guide-program { '
        'color: #FFFFFF; border-color: rgba(10,20,37,.42); '
        'background-clip: padding-box; }',
        'window.iptv-tv .syn-guide-program .syn-guide-program-name, '
        'window.iptv-tv .syn-guide-program .syn-guide-time, '
        'window.iptv-tv .syn-guide-program label { '
        'color: #FFFFFF; text-shadow: 0 1px 2px rgba(0,0,0,.40); }',
        'window.iptv-tv .syn-guide-program:hover { '
        'border-color: rgba(240,248,255,.78); }',
    ]
    for i, (left, right) in enumerate(COLORS):
        rules.append(
            'window.iptv-tv .syn-guide-program-%d { '
            'background-color: %s; '
            'background-image: linear-gradient(to right, %s 0%%, %s 100%%); }'
            % (i, right, left, right)
        )
    return '\n'.join(rules)
