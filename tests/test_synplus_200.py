"""SYN Plus 2.0 public release guard: all packages and locale alternatives."""
from pathlib import Path
from syn_locale_rev3 import localize

ROOT=Path(__file__).resolve().parents[1]

def test_locale_labels_in_spanish_and_english():
    for key in ('Guía','Cine','Perfiles','Más acciones de SYN','+  Añadir perfil','Bienvenido a SYN'):
        assert localize(key,key,'es') == key
        assert localize(key,key,'en_US') != key
        assert localize(key,key,'en_GB') != key
    assert localize('Favoritos','Favoritos','en_US') == 'Favorites'
    assert localize('Favoritos','Favoritos','en_GB') == 'Favourites'

def test_public_build_has_every_module_and_new_branding():
    ui=(ROOT/'synplus_layout.py').read_text('utf-8')
    source=(ROOT/'syn.py').read_text('utf-8')
    assert 'ALFA 2.7' not in ui
    from synplus_layout import css
    assert 'alpha(#D65D0E,.08)' in css('gruvbox-light', '#D65D0E')
    assert 'alpha(#5e81ac,.08)' in css('nord-light')
    assert 'alpha(@accent_color,.08)' in css('system','',False)
    assert 'alpha(@accent_color,.035)' in css('system','',True)
    assert 'alpha(#76c2c2,.035)' in css('dark')
    assert 'window.set_title("SYN")' in ui
    assert 'SYN_VERSION = "2.0.5"' in source
    assert 'SYNPLUS_ALPHA27' not in source
    for p in ('packaging/stage-native.sh','com.mrseivane.Syn.yml'):
        txt=(ROOT/p).read_text('utf-8')
        assert 'synplus_layout.py' in txt
        for component in ('syn_dvr.py','syn_service_setup.py','syn_cast_host.py'):
            assert component in txt
    assert 'Name=SYN' in (ROOT/'com.mrseivane.Syn.desktop').read_text('utf-8')
