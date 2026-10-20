"""Regresiones 3.8.5: estrella sin botones, marca de versión instalada."""
import unittest
from pathlib import Path
import syn

class InstalledFavoriteLayoutTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(syn.SYN_VERSION, '1.0.2b')

    def test_small_glyph_not_button(self):
        txt = Path(__file__).with_name('syn.py').read_text()
        start = txt.index('        def _channel_sidebar_row(self, ch):')
        end = txt.index('        def render_list(self):', start)
        card = txt[start:end]
        self.assertNotIn('Gtk.Button.new_', card)
        self.assertIn('Gtk.Image.new_from_icon_name', card)
        self.assertIn('star.set_pixel_size(17)', card)
        self.assertIn('star.set_valign(Gtk.Align.CENTER)', card)
        self.assertIn('GLib.idle_add(self.toggle_favorite, ch)', card)

    def test_no_separate_favorite_columns(self):
        txt = Path(__file__).with_name('syn.py').read_text()
        start = txt.index('        def render_list(self):')
        end = txt.index('        def _request_logo(', start)
        render = txt[start:end]
        self.assertIn('row = self._channel_sidebar_row(ch)', render)
        self.assertNotIn('overlay.add_overlay(star)', render)
        self.assertNotIn('star = Gtk.Button.new_from_icon_name', render)

    def test_original_ids(self):
        self.assertEqual(syn.display_channel_name('|ES| LA 1 UHD (4K)'), 'LA 1 UHD (4K)')

if __name__ == '__main__':
    unittest.main()
