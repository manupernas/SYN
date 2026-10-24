"""SYN 2.0.5: regression for tested native guide and independent Appearance Save.

Pure Python: runs without a GTK display, IPTV playlist or connected account.
"""
from pathlib import Path
import ast
from synplus_layout import css

ROOT = Path(__file__).resolve().parents[1]


def test_appearance_save_does_not_validate_iptv():
    source = (ROOT / 'syn_settings_rev3.py').read_text('utf-8')
    ast.parse(source)
    before = source.split('    def save_click(*_):', 1)[1]
    independent = before.split("        is_new = state['id'] is None", 1)[0]
    assert "if stack.get_visible_child_name() == 'appearance':" in independent
    assert 'sources.validate_profile' not in independent
    assert "app.cfg['theme'] = chosen_theme" in independent
    assert "app.cfg['accent_hex'] = chosen_accent" in independent
    assert 'sources.save_config(app.cfg)' in independent
    assert 'app.get_application().apply_theme(chosen_theme, chosen_accent)' in independent
    assert 'win.close()' in independent
    assert 'return' in independent
    assert 'sources.validate_profile(obj)' in before  # still validates source edits


def test_guide_edges_use_own_palette_in_all_eight_themes():
    ui = (ROOT / 'synplus_layout.py').read_text('utf-8')
    assert "video_column.add_css_class('synplus-video-column')" in ui
    for name in ('system', 'light', 'dark', 'teal', 'nord-light', 'nord-dark',
                 'gruvbox-light', 'gruvbox-dark'):
        style = css(name, '', name.endswith('dark'))
        assert 'window.iptv-tv.synplus-window .synplus-video-column' in style, name
        assert 'window.iptv-tv.synplus-window .synplus-guide .syn-guide-header' in style, name
        assert 'window.iptv-tv.synplus-window .synplus-guide .syn-guide-axis' in style, name
        assert 'window.iptv-tv.synplus-window .synplus-guide .syn-guide-footer' in style, name
    # These selectors are inside SYN only; no global GTK host CSS change.
    assert 'window.syn-settings-window .synplus-video-column' not in ui
    assert 'window.synplus-welcome .synplus-video-column' not in ui


def test_native_and_flatpak_packages_get_the_exact_same_fix():
    syn = (ROOT/'syn.py').read_text('utf-8')
    assert 'SYN_VERSION = "2.0.6"' in syn
    assert 'synplus_layout.css(theme,' in syn
    native = (ROOT/'packaging/stage-native.sh').read_text('utf-8')
    flatpak = (ROOT/'com.mrseivane.Syn.yml').read_text('utf-8')
    assert 'syn_settings_rev3.py' in native and 'synplus_layout.py' in native
    assert 'syn_settings_rev3.py' in flatpak and 'synplus_layout.py' in flatpak
    assert 'syn-dvr-worker' in native
