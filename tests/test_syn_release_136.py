"""Offline regressions for the public SYN 1.3.6 release."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent.parent

def test_public_release_136():
    syn = (ROOT / 'syn.py').read_text('utf-8')
    assert 'SYN_VERSION = "2.0.5"' in syn
    for marker in ('_draw_channel_logo_or_art', 'epg_gradient_css()',
                   '_guide_touch_update', 'gruvbox_css(theme', 'nord_css(theme'):
        assert marker in syn
    settings = (ROOT / 'syn_settings_rev3.py').read_text('utf-8')
    assert 'Ajustes guardados. La reproducción continúa sin interrupción.' in settings
    tree = ast.parse(settings)
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'save_click']
    assert len(handlers) == 1
    loads = [n for n in ast.walk(handlers[0]) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == 'load_channels']
    guarded = [n for n in ast.walk(handlers[0]) if isinstance(n, ast.If)
               and isinstance(n.test, ast.Name) and n.test.id == 'profile_changed'
               and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                       and c.func.attr == 'load_channels'
                       for child in n.body for c in ast.walk(child))]
    assert len(loads) == len(guarded) == 1
    for module in ('syn_nord_palette.py', 'syn_gruvbox_palette.py',
                   'syn_fallback_art.py', 'syn_epg_pop.py'):
        src = (ROOT / module).read_text('utf-8')
        ast.parse(src, filename=module)
        assert module in (ROOT / 'com.mrseivane.Syn.yml').read_text('utf-8')
        assert module in (ROOT / 'packaging/stage-native.sh').read_text('utf-8')
    assert (ROOT / 'docs/RELEASE_1.3.6.md').is_file()
    assert 'release version="1.3.6"' in (ROOT / 'com.mrseivane.Syn.metainfo.xml').read_text('utf-8')
    assert (ROOT / 'branding/logo_dark_ui.png').is_file()
    assert (ROOT / 'branding/icono_header_ui.png').is_file()
    assert '/usr/share/locale' in (ROOT / 'syn_i18n.py').read_text('utf-8')
    workflow = (ROOT / '.github/workflows/release-10-packages.yml').read_text('utf-8')
    assert 'format: [rpm, deb, pacman]' in workflow
    assert 'ghcr.io/flathub-infra/flatpak-github-actions:gnome-49' in workflow
    assert 'flatpak/flatpak-github-actions/flatpak-builder@v6' in workflow
    assert 'needs: [verify, build_native, build_flatpak_flathub]' in workflow
    assert 'format: [rpm, deb, pacman, flatpak]' not in workflow
