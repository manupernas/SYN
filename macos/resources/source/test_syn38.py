import unittest, tempfile
from pathlib import Path
from unittest.mock import patch
import syn_sources as src
from syn import logo_color_bucket, logo_pill_css, logo_visible_bounds

class ThemeLogoTests(unittest.TestCase):
    def test_logo_color_ignores_transparency(self):
        self.assertEqual(logo_color_bucket([(255,0,0,0)]*20),6)
        self.assertEqual(logo_color_bucket([(255,0,0,255)]*20),0) # rojo -> rojo
        self.assertEqual(logo_color_bucket([(0,0,255,255)]*20),8) # azul -> azul
    def test_pastel_and_dark_palettes(self):
        a=logo_pill_css(pastel=True); b=logo_pill_css(dark=True)
        self.assertIn('.syn-logo-pill-h11', a)
        self.assertNotEqual(a,b)
    def test_visible_bounds_trims_transparent_margin(self):
        # PNG 100x60; logo visible entre x=40..59, y=18..42.
        width, height = 100, 60
        data = bytearray(width*height*4)
        for y in range(18,43):
            for x in range(40,60):
                pos = (y*width+x)*4
                data[pos:pos+4] = bytes((19,112,245,255))
        x,y,w,h = logo_visible_bounds(data,width,height,width*4,4)
        self.assertLess(w,32)
        self.assertLess(h,37)
        self.assertGreaterEqual(x,0)
        self.assertLessEqual(x+w,width)
    def test_opaque_logo_not_cropped(self):
        self.assertEqual(logo_visible_bounds(b'\x00'*600,20,10,60,3),(0,0,20,10))
    def test_chromatic_buckets_match_brands(self):
        self.assertEqual(logo_color_bucket([(20,150,255,255)]*50),7)  # LA 1 azul
        self.assertEqual(logo_color_bucket([(255,110,0,255)]*50),1)   # 24 h naranja
        self.assertIn('#', logo_pill_css(dark=True))
    def test_fixed_canvas_not_theme_icon_size(self):
        src = Path(__file__).with_name('syn.py').read_text()
        self.assertIn('pic = Gtk.DrawingArea()',src)
        self.assertIn('pic.set_content_width(108)',src)
        self.assertIn('pic.set_content_height(38)',src)
        self.assertNotIn('pic = Gtk.Picture()',src)
        self.assertIn('GdkPixbuf.Pixbuf.new_subpixbuf',src)
        self.assertNotIn('.syn-logo-pill image { -gtk-icon-size: 20px; }',src)

    def test_custom_logo_saved_by_profile_no_original_path(self):
        with tempfile.TemporaryDirectory() as directory:
            logo = Path(directory)/'demo.png'
            logo.write_bytes(b'\x89PNG\r\n\x1a\n'+b'sample')
            profile={'id':'profile123'}
            ch=src.Channel('Demo','TDT','https://example.org/stream')
            with patch.object(src,'APP_CONFIG',Path(directory)/'config'):
                stored=src.install_custom_logo(profile,ch,logo)
                self.assertEqual(src.custom_logo_path(profile,ch),stored)
                self.assertEqual(stored.read_bytes(),logo.read_bytes())
                self.assertNotIn(directory,repr(profile))
                src.reset_custom_logo(profile,ch)
                self.assertIsNone(src.custom_logo_path(profile,ch))
    def test_reject_untrusted_formats(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.jpg'; p.write_bytes(b'not a jpg')
            with self.assertRaises(ValueError):
                src.install_custom_logo({'id':'abc'},src.Channel('demo','TDT','https://x'),p)
    def test_old_profile_without_logos(self):
        self.assertIsNone(src.custom_logo_path({'id':'profile'},src.Channel('demo','TDT','https://x')))
    def test_flatpak_keeps_imported_icon_file(self):
        source=Path(__file__).with_name('syn.py').read_text()
        self.assertIn('sources.install_custom_logo(self.profile, ch, path)',source)
        self.assertIn('sources.save_config(self.cfg)',source)
        self.assertIn('self.channel_pill(channel, 120, 46)',source)
        self.assertIn('self.channel_pill(ch, 120, 46)',source)
    def test_theme_selector(self):
        source=Path(__file__).with_name('syn.py').read_text()
        for name in ('LIGHT_CSS', 'DARK_CSS', 'TEAL_CSS', 'Sistema (GTK3/GTK4 disponible)'):
            self.assertIn(name,source)

if __name__ == '__main__': unittest.main()
