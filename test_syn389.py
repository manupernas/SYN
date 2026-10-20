"""SYN 3.8.10: el logo usa un lienzo invariable."""
import unittest
from pathlib import Path
import syn

SRC = Path(syn.__file__).read_text(encoding='utf-8')

class WidgetRenderingContract(unittest.TestCase):
    def test_actual_widget_is_picture_not_icon(self):
        block = SRC.split('        def channel_pill(self, ch',1)[1].split('        def _channel_sidebar_row',1)[0]
        self.assertIn('pic = Gtk.DrawingArea()', block)
        self.assertNotIn('pic = Gtk.Picture()', block)
        self.assertIn('pic.set_size_request(108, 38)', block)
        self.assertIn('pic.set_content_width(108)', block)
        self.assertIn('pic.set_content_height(38)', block)
        self.assertIn('pic.set_draw_func(self._draw_channel_logo)', block)
        self.assertIn('width, height = 120, 46',block)
        self.assertIn('pill.set_overflow(Gtk.Overflow.HIDDEN)',block)
        self.assertNotIn('set_pixel_size',block)

    def test_real_paintable_method_is_used(self):
        load = SRC.split('        def _fill_logo_image(',1)[1].split('        def channel_pill(',1)[0]
        self.assertIn('image._syn_pixbuf = pix',load)
        self.assertIn('image.queue_draw()',load)
        self.assertNotIn('image.set_from_paintable(',load)
        self.assertIn('GdkPixbuf.Pixbuf.new_subpixbuf',load)
        self.assertIn('fitted = fitted_logo_size(*source_size)',load)

    def test_no_favorites_special_layout(self):
        rows=SRC.split('        def _channel_sidebar_row',1)[1].split('        def _debug_sidebar_geometry(',1)[0]
        self.assertIn('content.append(self.channel_pill(ch, 120, 46))',rows)
        self.assertIn('row = self._channel_sidebar_row(ch)',rows)
        self.assertNotIn('Gtk.Overlay(',rows)

    def test_real_logo_fit_is_large_and_stays_inside(self):
        self.assertEqual(syn.fitted_logo_size(18,6),(108,36))
        self.assertEqual(syn.fitted_logo_size(40,40),(38,38))
        self.assertEqual(syn.fitted_logo_size(4,100),(2,38))
        self.assertEqual(syn.fitted_logo_size(2000,700),(108,38))

if __name__ == '__main__': unittest.main()
