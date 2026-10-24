"""SYN 2.0.3: native theme detection and CSS priority regressions."""
from pathlib import Path
from synplus_layout import css, choose_system_scheme
ROOT = Path(__file__).resolve().parents[1]


def test_desktop_preference_beats_misleading_gtk_theme_name():
    assert choose_system_scheme('Colloid-Teal-Light', False, 'prefer-dark') == 'follow-system'
    assert choose_system_scheme('Colloid-Teal-Dark', True, 'prefer-light') == 'follow-system'
    assert choose_system_scheme('Colloid-Teal-Dark', False, 'default') == 'dark'
    assert choose_system_scheme('Colloid-Teal-Light', False, '') == 'light'
    assert choose_system_scheme('Adwaita', False, 'default') == 'follow-system'
    assert choose_system_scheme('Adwaita', True, '') == 'dark'


def test_native_system_workbench_has_matching_foreground_and_background():
    from synplus_layout import native_system_css
    txt=native_system_css()
    assert '.synplus-workbench' in txt
    assert 'background-color:@window_bg_color; color:@window_fg_color;' in txt
    assert '.synplus-nav' in txt
    # Scope this check to the native-only workbench rule. The Welcome
    # window legitimately uses the very same symbolic GTK colors in every
    # build; searching that declaration across the *whole* stylesheet
    # incorrectly flags the existing Welcome CSS as a native override.
    native_workbench_rule = (
        'window.iptv-tv.synplus-window .synplus-workbench {\n'
        '        background-color:@window_bg_color; color:@window_fg_color;'
    )
    assert native_workbench_rule in txt
    for dark in (False, True):
        themed=css('system', '', dark)
        assert ('alpha(@accent_color,.035)' if dark else 'alpha(@accent_color,.08)') in themed
        assert native_workbench_rule not in themed


def test_native_custom_css_is_scoped_and_existing_flatpak_kept():
    source=(ROOT/'syn.py').read_text('utf-8')
    assert 'SYN_VERSION = "2.0.3"' in source
    assert "if native_system:" in source
    assert "not os.path.exists('/.flatpak-info')" in source
    assert "synplus_layout.choose_system_scheme(" in source
    assert "Adw.ColorScheme.PREFER_LIGHT" in source
    assert "Gtk.STYLE_PROVIDER_PRIORITY_USER + 1" in source
    assert "native_system = (theme == 'system'" in source
    assert 'synplus_layout.native_system_css()' in source
    for p in ('packaging/stage-native.sh', 'com.mrseivane.Syn.yml'):
        txt=(ROOT/p).read_text('utf-8')
        for module in ('synplus_layout.py', 'syn_dvr.py','syn_cast_host.py'):
            assert module in txt
