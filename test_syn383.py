"""SYN 3.8.3: regresiones de etiquetas visibles, favoritos y contraste."""
import re
import unittest
from pathlib import Path
import syn_sources as sources
from syn import display_channel_name, logo_contrast_variant, logo_pill_css


class RefinedFavoritesTests(unittest.TestCase):
    def test_remove_only_country_prefixes(self):
        examples = {
            '[ES] LA 1 UHD (4K)': 'LA 1 UHD (4K)',
            '[ES] LA 1 FHD': 'LA 1 FHD',
            'ES - 24 HORAS': '24 HORAS',
            '(es) Antena 3 HD': 'Antena 3 HD',
            'ES: La 2': 'La 2',
            'ES| Telecinco FHD': 'Telecinco FHD',
            'ESPN HD': 'ESPN HD',
            'ESTRENOS': 'ESTRENOS',
            '[UK] SKY SPORTS': '[UK] SKY SPORTS',
        }
        for original, expected in examples.items():
            with self.subTest(original=original):
                self.assertEqual(display_channel_name(original), expected)

    def test_preserves_unique_channel_keys_and_epg(self):
        ch = sources.Channel('[ES] LA 1 UHD', 'ES - TDT', 'https://example.net/live', 'https://example.net/logo.png', 'la1.es')
        self.assertEqual(display_channel_name(ch.name), 'LA 1 UHD')
        self.assertEqual(ch.name, '[ES] LA 1 UHD')
        self.assertEqual(ch.favorite_id, 'ES - TDT|[ES] LA 1 UHD')
        self.assertEqual(ch.epg_id, 'la1.es')

    def test_logo_palette_contrasts_dark_and_bright_artwork(self):
        self.assertEqual(logo_contrast_variant([(15, 60, 140, 255)]*100), 'light')
        self.assertEqual(logo_contrast_variant([(240, 246, 248, 255)]*100), 'dark')
        self.assertEqual(logo_contrast_variant([(10,20,30,0)]*100), 'dark')
        css = logo_pill_css(dark=True)
        self.assertIn('.syn-logo-pill-h7-light', css)
        self.assertIn('.syn-logo-pill-h7-dark', css)

    def test_favorites_stack_and_nonexpanding_guide(self):
        source = Path(__file__).with_name('syn.py').read_text()
        self.assertIn('row = self._channel_sidebar_row(ch)', source)
        self.assertIn("name.add_css_class('syn-channel-display-name')", source)
        self.assertIn('display_channel_name(ch.name)', source)
        self.assertIn('display_channel_name(channel.name)', source)
        self.assertIn('guide_logo_name.set_size_request(120, -1)', source)
        self.assertIn('channel_widget.set_size_request(GUIDE_CHANNEL_WIDTH, 70)', source)
        self.assertNotIn('group = Gtk.Label(label=ch.group, xalign=0)', source)
        self.assertIn('self.channel_pill(ch, 120, 46)', source)
        self.assertIn('right_click.set_button(3)', source)
        self.assertIn('choose_custom_logo_url', source)

if __name__ == '__main__':
    unittest.main()
