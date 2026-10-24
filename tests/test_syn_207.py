"""SYN 2.0.7: Fedora Flatpak user-approved popup/theme CSS regression."""
from pathlib import Path
import ast
import synplus_layout

ROOT=Path(__file__).resolve().parents[1]


def popup_css():
    src=(ROOT/'syn.py').read_text('utf-8')
    tree=ast.parse(src)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='light_surface_css')
    namespace={'synplus_layout':synplus_layout}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'syn_light_popups_207','exec'),namespace)
    return namespace['light_surface_css']


def test_version_and_approved_provider_is_dynamic_and_theme_safe():
    source=(ROOT/'syn.py').read_text('utf-8')
    assert 'SYN_VERSION = "2.0.7"' in source
    assert 'SYN_207_LIGHT_POPOVER' in source
    assert 'Gtk.STYLE_PROVIDER_PRIORITY_USER + 6' in source
    assert "light_surface_css(theme, manager.get_dark()).encode('utf-8')" in source
    assert 'syn_popup_theme_css(theme)' in source


def test_all_light_popups_have_settings_titlebar_and_cast():
    css=popup_css()
    for theme in ('light','nord-light','gruvbox-light','system'):
        sheet=css(theme,False)
        for required in ('window.syn-settings-window headerbar',
                         'window.syn-settings-window windowcontrols button',
                         'popover.background > contents',
                         'popover listview row:selected',
                         'popover.syn-cast-popover > contents'):
            assert required in sheet,(theme,required)
    for theme in ('dark','nord-dark','gruvbox-dark','teal'):
        assert css(theme,True)==''
    assert css('system',True)==''


def test_release_workflow_uses_this_test_and_prior_fixes_intact():
    wf=(ROOT/'.github/workflows/release-10-packages.yml').read_text('utf-8')
    assert 'tests/test_syn_207.py' in wf
    meta=(ROOT/'com.mrseivane.Syn.metainfo.xml').read_text('utf-8')
    assert '<release version="2.0.7"' in meta
    source=(ROOT/'syn.py').read_text('utf-8')
    assert 'GLib.timeout_add(18, add_batch)' in source
    assert 'Gdk.Texture.new_for_pixbuf(pix)' in source
    assert 'SYN_207_LIGHT_POPOVER' in source
