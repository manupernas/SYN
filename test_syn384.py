"""Regresiones de diseño de Favoritos: compactación y etiquetas limpias."""
import unittest
from pathlib import Path
from syn import display_channel_name


class FavoriteCardTests(unittest.TestCase):
    def test_prefixes_from_real_lists(self):
        expected = {
            '|ES| LA 2 FHD': 'LA 2 FHD',
            '|ES| LA 1 UHD (4K)': 'LA 1 UHD (4K)',
            '[ES] 24 HORAS': '24 HORAS',
            'ES - ANTENA 3 HD': 'ANTENA 3 HD',
            'ESPN UHD': 'ESPN UHD',
            '[UK] BBC HD': '[UK] BBC HD',
        }
        for source, clean in expected.items():
            with self.subTest(source=source):
                self.assertEqual(display_channel_name(source), clean)

    def test_identical_logo_pill_in_general_and_favorites(self):
        source = Path(__file__).with_name('syn.py').read_text()
        self.assertIn('content.append(self.channel_pill(ch, 120, 46))', source)
        self.assertIn('row = self._channel_sidebar_row(ch)', source)
        self.assertIn("name.add_css_class('syn-channel-display-name')", source)
        self.assertIn("star = Gtk.Image.new_from_icon_name(", source)
        self.assertNotIn('button.syn-favorite-star', source)

    def test_internal_channel_ids_untouched(self):
        from syn_sources import Channel
        channel = Channel('|ES| LA 2 FHD', 'ES - TDT', 'https://example.invalid/some.m3u8')
        self.assertEqual(channel.favorite_id, 'ES - TDT||ES| LA 2 FHD')
        self.assertEqual(display_channel_name(channel.name), 'LA 2 FHD')


if __name__ == '__main__':
    unittest.main()
