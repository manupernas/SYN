"""Regresiones 3.8.8: ampliar logotipos pequeños manteniendo la pastilla."""
import unittest
from pathlib import Path
import syn

class LogoSizingTests(unittest.TestCase):
    def test_small_wide_logo_grows(self):
        self.assertEqual(syn.fitted_logo_size(18, 6), (108, 36))
        self.assertEqual(syn.fitted_logo_size(27, 9), (108, 36))

    def test_small_square_logo_grows_but_fits(self):
        self.assertEqual(syn.fitted_logo_size(15, 15), (38, 38))

    def test_large_logo_shrinks(self):
        self.assertEqual(syn.fitted_logo_size(1080, 380), (108, 38))

    def test_respects_aspect_and_bounds(self):
        for w, h in [(5, 20), (400, 85), (999, 1200), (1, 1), (1920, 1080)]:
            nw, nh = syn.fitted_logo_size(w, h)
            self.assertTrue(0 < nw <= 108)
            self.assertTrue(0 < nh <= 38)
            self.assertLessEqual(abs(nw / nh - w / h), max(1/nw, 1/nh) * 4)

    def test_transparency_crop_before_upscale(self):
        width, height = 80, 40
        rgba = bytearray(width*height*4)
        for y in range(14, 26):
            for x in range(20, 60):
                i=(y*width+x)*4
                rgba[i:i+4] = bytes((35, 135, 230, 255))
        x,y,w,h = syn.logo_visible_bounds(rgba, width, height, width*4, 4)
        self.assertLess(w, width)
        self.assertLess(h, height)
        nw, nh = syn.fitted_logo_size(w,h)
        self.assertEqual(nw,108)
        self.assertGreater(nh,20)

    def test_layout_and_mpv_stay_unchanged(self):
        code=Path(syn.__file__).read_text()
        self.assertIn('width, height = 120, 46', code)
        self.assertIn('pic = Gtk.DrawingArea()', code)
        self.assertIn('row = self._channel_sidebar_row(ch)', code)
        self.assertIn('fitted = fitted_logo_size(*source_size)', code)
        self.assertNotIn('max_height / max(1, pix.get_height()), 1.0', code)

if __name__ == '__main__':
    unittest.main()
