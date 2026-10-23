#!/usr/bin/env python3
"""SYN beta8 · Artistic channel logo fallback (no third-party modules).

Deterministic GTK4/Cairo drawing; only used while no real channel logo is
available. Fixed 108x38 canvas and no disk cache to keep scrolling lightweight.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata

# Deep, high-contrast POP/SYN palettes: background, graphic, bright detail.
# Nord themes keep their own UI palette; channel art remains editorial.
PALETTES = (
    ((0.09, .18, .39), (.96, .33, .47), (1.0, .79, .33)),
    ((.08, .28, .31), (1.0, .43, .26), (.99, .80, .39)),
    ((.31, .15, .45), (.23, .81, .77), (.99, .48, .64)),
    ((.06, .28, .49), (.91, .39, .68), (.99, .78, .36)),
    ((.36, .16, .29), (.98, .56, .34), (.98, .78, .67)),
    ((.13, .30, .23), (.91, .44, .31), (.88, .83, .37)),
    ((.17, .19, .43), (.66, .46, .96), (.39, .84, .99)),
    ((.12, .33, .36), (.98, .40, .57), (.98, .80, .35)),
)


def _ascii_label(value):
    """Normalize names without mutating the actual channel name or ID."""
    val = unicodedata.normalize('NFKD', str(value or 'SYN'))
    val = ''.join(c for c in val if not unicodedata.combining(c))
    val = re.sub(r'[^A-Za-z0-9 +&]', ' ', val).upper()
    return re.sub(r'\s+', ' ', val).strip() or 'SYN'


def artwork_identity(name, group=''):
    """A stable design regardless of Python's randomized hash seed."""
    name = _ascii_label(name)
    group = _ascii_label(group)
    digest = hashlib.sha256((group + '\x1f' + name).encode('utf-8')).digest()
    return digest[0] % len(PALETTES), digest[1] % 4


def artwork_lines(name):
    """Two controlled lines, deliberately designed for 108x38 pixels."""
    words = _ascii_label(name).split()
    if not words:
        return ('SYN', 'TV')
    first = words[0]
    if len(first) <= 4 and len(words) > 1 and len(first + ' ' + words[1]) <= 10:
        first = first + ' ' + words[1]
        words = words[2:]
    else:
        words = words[1:]
    title = first[:12]
    subtitle = (' '.join(words[:3]) or '◦ CHANNEL')[:15]
    # Keep Cairo's toy text API to ASCII only; no glyph fallback dependency.
    subtitle = subtitle.replace('◦', '·')
    return title, subtitle


def draw_art_pill(cr, width, height, name, group=''):
    """Draw one mini-cover on the supplied Gtk.DrawingArea Cairo context.

    Do not assume a fixed allocated dimension: scale artwork to the widget.
    Real logo drawing is handled by SYN's original renderer instead.
    """
    if width <= 0 or height <= 0:
        return
    palette_idx, motif = artwork_identity(name, group)
    bg, shape, sparkle = PALETTES[palette_idx]
    title, subtitle = artwork_lines(name)
    cr.save()
    try:
        cr.scale(width / 108.0, height / 38.0)
        cr.set_source_rgb(*bg)
        cr.rectangle(0, 0, 108, 38)
        cr.fill()

        # Asymmetric POP collage in the right third, never behind the text.
        cr.set_source_rgb(*shape)
        if motif == 0:
            cr.arc(100, 6, 29, 0, math.tau)
            cr.fill()
            cr.set_source_rgb(*sparkle)
            cr.rectangle(87, 23, 24, 7)
            cr.fill()
        elif motif == 1:
            cr.move_to(78, 38)
            cr.line_to(94, 0)
            cr.line_to(108, 0)
            cr.line_to(108, 38)
            cr.close_path()
            cr.fill()
            cr.set_source_rgb(*sparkle)
            cr.arc(104, 31, 9, 0, math.tau)
            cr.fill()
        elif motif == 2:
            cr.rectangle(89, 0, 8, 38)
            cr.fill()
            cr.set_source_rgb(*sparkle)
            cr.rectangle(99, 0, 9, 38)
            cr.fill()
        else:
            cr.arc(98, 20, 22, 0, math.tau)
            cr.fill()
            cr.set_source_rgb(*sparkle)
            cr.arc(98, 20, 10, 0, math.tau)
            cr.fill()

        cr.set_source_rgba(1, 1, 1, .29)
        cr.rectangle(6, 5, 2, 28)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.select_font_face('Sans', 0, 1)
        cr.set_font_size(9.6 if len(title) <= 9 else 7.8)
        cr.move_to(13, 17)
        cr.show_text(title)
        cr.set_source_rgba(1, 1, 1, .83)
        cr.select_font_face('Sans', 0, 0)
        cr.set_font_size(6.8 if len(subtitle) <= 13 else 5.9)
        cr.move_to(13, 29)
        cr.show_text(subtitle)
    finally:
        cr.restore()
