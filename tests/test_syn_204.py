"""SYN 2.0.4: independent light-mode welcome dialog contrast.

Offline/no-display tests: palette is non-empty for light variants; completely
absent in dark variants. Scoped CSS cannot recolor the player/EPG/sidebars.
"""
from pathlib import Path
import re
from synplus_layout import welcome_light_css, css

ROOT = Path(__file__).resolve().parents[1]


def _lum(color):
    channels = [int(color[i:i+2], 16) / 255 for i in (1,3,5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4 for c in channels]
    return 0.2126*linear[0] + 0.7152*linear[1] + 0.0722*linear[2]


def _ratio(a, b):
    l1, l2 = sorted((_lum(a), _lum(b)), reverse=True)
    return (l1+0.05)/(l2+0.05)


def test_welcome_light_palette_contrast_and_scoping():
    for name in ('system', 'light', 'nord-light', 'gruvbox-light'):
        style = welcome_light_css(name, False)
        assert 'window.synplus-welcome' in style
        assert 'window.iptv-tv' not in style
        assert 'background-image:none;' in style
        assert 'window.synplus-welcome .syn-welcome-card-subtitle' in style
        assert 'window.synplus-welcome .syn-welcome-body entry' in style
        assert 'window.synplus-welcome .syn-welcome-body passwordentry' in style
        assert 'window.synplus-welcome button.syn-welcome-cta label' in style
        assert 'window.synplus-welcome button.syn-welcome-card image.syn-welcome-symbol' in style
        # Extract the complete eight-colour palette from the source, not the stylesheet.
        source = (ROOT/'synplus_layout.py').read_text('utf-8')
        source = source.split('def welcome_light_css', 1)[1].split('def css', 1)[0]
        match = re.search(r"^\s*'"+re.escape(name)+r"':\s*\(([^\n]+)\)", source, re.M)
        assert match, name
        colours = re.findall(r"#[0-9a-fA-F]{6}", match.group(1))
        assert len(colours) == 8, (name, colours)
        bg, fg, muted, card, _stroke, _hover, accent, accent_fg = colours
        assert _ratio(bg, fg) >= 7.0, (name, 'foreground')
        assert _ratio(card, fg) >= 7.0, (name, 'card')
        assert _ratio(bg, muted) >= 4.5, (name, 'muted')
        assert _ratio(accent, accent_fg) >= 4.5, (name, 'button')


def test_welcome_dark_unchanged_and_host_gtk_can_not_override_light():
    for name in ('system', 'teal', 'dark', 'nord-dark', 'gruvbox-dark'):
        assert welcome_light_css(name, True) == ''
    source = (ROOT/'syn.py').read_text('utf-8')
    assert 'Gtk.STYLE_PROVIDER_PRIORITY_USER + 5' in source
    assert 'welcome_light_css(theme, manager.get_dark())' in source
    assert 'SYN_VERSION = "2.0.4"' in source
    assert 'window.synplus-welcome' in css('light')  # base CSS stays supported
    assert 'syn-dvr-worker' in (ROOT/'packaging/stage-native.sh').read_text('utf-8')
