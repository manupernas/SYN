"""SYN 2.0.2: Chromecast popup contrast/anchoring in every theme."""
from pathlib import Path
import re
from synplus_layout import css

ROOT = Path(__file__).resolve().parents[1]


def test_cast_popup_fg_bg_for_light_and_dark_schemes():
    schemes = [
        ('light', '#ffffff', '#18242e', False),
        ('nord-light', '#ffffff', '#293b4c', False),
        ('gruvbox-light', '#fffae6', '#3c3836', False),
        ('dark', '#1b2631', '#f2f5f8', True),
        ('teal', '#10272c', '#e9f7f4', True),
        ('nord-dark', '#303f50', '#e9f0f6', True),
        ('gruvbox-dark', '#37332c', '#f6ead6', True),
        ('system', '@window_bg_color', '@window_fg_color', False),
        ('system', '@window_bg_color', '@window_fg_color', True),
    ]
    for name, bg, fg, dark in schemes:
        theme = css(name, '', dark)
        assert 'popover.syn-cast-popover > contents' in theme
        assert f'background-color:{bg}; color:{fg};' in theme
        assert f'box.syn-cast-panel label' in theme
        assert f'color:{fg}; background-color:transparent;' in theme
        assert 'spinbutton.syn-cast-numeric button' in theme
        assert 'button.syn-cast-action label' in theme


def test_cast_popover_scoped_and_does_not_change_broadcast():
    source = (ROOT/'syn.py').read_text('utf-8')
    popup = source.split('def _syn_cast_menu(self, button):', 1)[1].split('def _syn_cast_rejoin_shared', 1)[0]
    assert "pop.add_css_class('syn-cast-popover')" in popup
    assert "col.add_css_class('syn-cast-panel')" in popup
    assert "spin.add_css_class('syn-cast-numeric')" in popup
    assert "stop.add_css_class('syn-cast-action')" in popup
    assert "b.add_css_class('syn-cast-action')" in popup
    assert 'hold_chrome_for_cast(self, pop, Gtk)' in popup
    assert "self._syn_cast_call({'action':'devices'},done)" in popup
    assert 'self._syn_cast_play(d)' in popup
    assert 'self._syn_cast_stop()' in popup
    assert 'SYN_VERSION = "2.0.3"' in source
    assert 'STYLE_PROVIDER_PRIORITY_USER + 4' in source
    assert 'syn-dvr-worker' in (ROOT/'packaging/stage-native.sh').read_text('utf-8')
