"""Regresiones de columnas GTK: el favoritos NO ensancha la parrilla EPG."""
from pathlib import Path
import re
import unittest
import syn

S = Path(__file__).with_name('syn.py').read_text(encoding='utf-8')

class GuideColumnsTests(unittest.TestCase):
    def test_width_contract(self):
        self.assertEqual(syn.GUIDE_CATEGORIES_WIDTH, 158)
        self.assertEqual(syn.GUIDE_CHANNEL_WIDTH, 174)
        self.assertIn('self.guide_categories_scroll.set_max_content_width(GUIDE_CATEGORIES_WIDTH)',S)
        self.assertIn('self.guide_names_scroll.set_max_content_width(GUIDE_CHANNEL_WIDTH)',S)
        self.assertIn('self.guide_names_scroll.set_hexpand(False)',S)
        self.assertIn('self.guide_names_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)',S)
        self.assertIn('self.guide_categories_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)',S)

    def test_small_star_and_ellipsis(self):
        self.assertIn("fav_icon.set_pixel_size(13)", S)
        self.assertIn("fav_icon.set_size_request(14, 14)", S)
        self.assertIn("fav_icon.set_hexpand(False)", S)
        self.assertIn('fallback.set_ellipsize(Pango.EllipsizeMode.END)', S)
        self.assertIn('cat_label.set_ellipsize(Pango.EllipsizeMode.END)',S)
        self.assertIn('btn.set_tooltip_text(name)',S)

    def test_axis_and_track_unchanged(self):
        self.assertIn('self.guide_axis.set_draw_func(self._guide_draw_axis)',S)
        self.assertIn('track.put(block, x, 0)',S)
        self.assertIn("Gtk.Button(label=tr('▦ Guía EPG'))",S)

    def test_mpv_unchanged(self):
        import hashlib
        backend = S[S.index('class NativeMpv:'):S.index('def epg_window_segments(')].strip()
        self.assertEqual(hashlib.sha256(backend.encode()).hexdigest(),
                         '8cbdb7c3656ea37012bce18ca7a5852219ed00fd14a5ab021de41acf8b56cf1d')

if __name__ == '__main__': unittest.main()
