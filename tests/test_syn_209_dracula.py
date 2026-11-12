"""Pure SYN 2.0.9 Dracula/Alucard Classic tests, no GTK display needed."""
from pathlib import Path
import importlib
import unittest

from syn_dracula_palette import COLORS, ACCENT_NAMES, contrast, readable_ink, dracula_css

ROOT = Path(__file__).resolve().parents[1]

class Dracula209Tests(unittest.TestCase):
    def test_two_official_classic_palettes(self):
        self.assertEqual(COLORS['dracula']['background'], '#282A36')
        self.assertEqual(COLORS['dracula']['foreground'], '#F8F8F2')
        self.assertEqual(COLORS['alucard']['background'], '#FFFBEB')
        self.assertEqual(COLORS['alucard']['foreground'], '#1F1F1F')
        self.assertEqual(COLORS['dracula']['red'], '#FF5555')
        self.assertEqual(COLORS['alucard']['red'], '#CB3A2A')
        self.assertEqual(len(ACCENT_NAMES), 7)
        for scheme in COLORS.values():
            self.assertTrue(all(k in scheme for k in ACCENT_NAMES))

    def test_all_accent_buttons_have_legible_foreground(self):
        for variant, scheme in COLORS.items():
            for name in ACCENT_NAMES:
                bg = scheme[name]
                self.assertGreaterEqual(contrast(bg, readable_ink(bg,variant)), 4.5,
                                        (variant, name, bg))

    def test_css_stays_inside_syn_and_leaves_epg_colours_alone(self):
        for variant in ('dracula','alucard'):
            css = dracula_css(variant)
            self.assertNotIn('%%', css)
            self.assertIn('window.iptv-tv .syn-guide-header', css)
            self.assertIn('window.syn-settings-window', css)
            self.assertIn('window.iptv-tv .syn-dvr-page', css)
            self.assertNotIn('.syn-guide-program-0 {', css)
            self.assertNotIn('window.iptv-tv .iptv-video { background-color:', css.replace(' ','') )
            self.assertIn(COLORS[variant]['background'], css)
            self.assertIn(COLORS[variant]['red'], css)

    def test_choose_custom_accent(self):
        for theme, bg in [('dracula','#8BE9FD'), ('alucard','#644AC9')]:
            css = dracula_css(theme, bg)
            self.assertIn(f'background-color:{bg}',css)
            self.assertIn(readable_ink(bg,theme),css)

    def test_native_rpm_deb_pacman_stage_includes_dracula(self):
        stage = (ROOT/'packaging/stage-native.sh').read_text(encoding='utf-8')
        self.assertIn('syn_dracula_palette.py', stage)
        self.assertIn('syn_epg_pop.py', stage)

    def test_integration_in_settings_flatpak_and_theme_engine(self):
        syn = (ROOT/'syn.py').read_text('utf8')
        settings = (ROOT/'syn_settings_rev3.py').read_text('utf8')
        layout = (ROOT/'synplus_layout.py').read_text('utf8')
        manifest = (ROOT/'com.mrseivane.Syn.yml').read_text('utf8')
        self.assertIn("elif theme in ('dracula', 'alucard'):",syn)
        self.assertIn("'gruvbox-dark','dracula','alucard'",syn)
        self.assertIn("'alucard'):\n                    mode = Adw.ColorScheme.FORCE_LIGHT",syn)
        self.assertIn("'Dracula Classic'",settings)
        self.assertIn("'Alucard Classic'",settings)
        self.assertIn("('red', 'Rojo', '#FF5555')",settings)
        self.assertIn("('red', 'Rojo', '#CB3A2A')",settings)
        self.assertIn("'dracula': ('#282A36'",layout)
        self.assertIn("'alucard': ('#FFFBEB'",layout)
        self.assertIn('install -Dm644 syn_dracula_palette.py',manifest)
        # The ten EPG gradients must still be installed and used.
        self.assertIn('epg_programme_color_indices(',syn)
        self.assertIn('epg_gradient_css()',syn)

if __name__ == '__main__':
    unittest.main()
