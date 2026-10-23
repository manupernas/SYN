"""Pure regression tests, no Gtk display or IPTV subscription required."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / 'syn.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)

def _helper(name):
    body = [node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(body) == 1, (name, len(body))
    sandbox = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), '<helper-test>', 'exec'), sandbox)
    return sandbox[name]

def test_popup_theme_surfaces_and_palette_contrast():
    css_for = _helper('syn_popup_theme_css')
    assert css_for('system') == ''
    themes = ('light', 'dark', 'teal', 'nord-light', 'nord-dark', 'gruvbox-light', 'gruvbox-dark')
    for theme in themes:
        css = css_for(theme)
        assert 'popover > contents' in css, theme
        assert 'popover listview row:selected' in css, theme
        assert 'popover listbox row:hover' in css, theme
        assert 'popover modelbutton' in css, theme
        assert 'popover scrollbar slider' in css, theme
    assert '#ECEFF4' in css_for('nord-light')
    assert '#fbf1c7' in css_for('gruvbox-light')
    assert '#10332f' in css_for('teal')

def test_axis_hour_text_ink_changes_only_for_light_themes():
    palette = _helper('epg_axis_ink')
    for name in ('light', 'nord-light', 'gruvbox-light'):
        grid, ink = palette(name)
        assert len(grid) == len(ink) == 4
        assert max(ink[:3]) < .31, (name, ink)
    for name in ('system', 'dark', 'teal', 'nord-dark', 'gruvbox-dark'):
        _, ink = palette(name)
        assert min(ink[:3]) > .80, (name, ink)

def test_popup_css_used_by_high_priority_theme_provider():
    assert 'palette_css + epg_gradient_css() + syn_popup_theme_css(theme)' in SOURCE

def test_epg_cairo_calls_theme_palette_and_repaints():
    assert 'grid_ink, hour_ink = epg_axis_ink(theme)' in SOURCE
    assert 'ctx.set_source_rgba(*hour_ink)' in SOURCE
    assert 'ctx.set_source_rgba(*grid_ink)' in SOURCE
    assert 'axis.queue_draw()' in SOURCE
