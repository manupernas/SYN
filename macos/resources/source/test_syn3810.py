"""Pruebas de la medida fija y del renderizado de logos en SYN 3.8.10.

Estas pruebas prueban la logica, pero no sustituyen la comprobacion visual
real con GTK4/Wayland de Fedora.
"""
import unittest
import ast
import textwrap
import types
from pathlib import Path
import syn

SRC = Path(syn.__file__).read_text(encoding='utf-8')


class FixedLogoTest(unittest.TestCase):
    def test_centering_without_expansion(self):
        self.assertEqual(syn.logo_canvas_offset(108, 38, 108, 36), (0, 1))
        self.assertEqual(syn.logo_canvas_offset(108, 38, 38, 38), (35, 0))
        self.assertEqual(syn.logo_canvas_offset(108, 38, 20, 10), (44, 14))

    def test_canvas_has_no_intrinsic_image_size(self):
        block = SRC.split('        def channel_pill(self, ch', 1)[1].split('        def _channel_sidebar_row(', 1)[0]
        for required in (
            'Gtk.DrawingArea()', 'set_content_width(108)',
            'set_content_height(38)', 'set_size_request(108, 38)',
            'pic.set_hexpand(False)', 'pic.set_vexpand(False)',
            'pic.set_draw_func(self._draw_channel_logo)',
        ):
            self.assertIn(required, block)
        self.assertNotIn('Gtk.Picture()', block)
        self.assertNotIn('Gtk.Image()', block)

    def test_same_row_for_all_filter_states(self):
        block = SRC.split('        def render_list(', 1)[1].split('        def _debug_sidebar_geometry(', 1)[0]
        self.assertIn('row = self._channel_sidebar_row(ch)', block)
        self.assertEqual(block.count('self._channel_sidebar_row(ch)'), 1)
        self.assertNotIn('Gtk.Overlay(', block)

    def test_drawing_callback_centers_and_renders_without_resizing(self):
        tree = ast.parse(SRC)
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_draw_channel_logo')
        code = textwrap.dedent(ast.get_source_segment(SRC, method))
        calls = []
        class FakeGdk:
            @staticmethod
            def cairo_set_source_pixbuf(cr, pix, x, y):
                calls.append(('source', x, y))
        namespace = {'Gdk': FakeGdk, 'logo_canvas_offset': syn.logo_canvas_offset}
        exec(compile(code, syn.__file__, 'exec'), namespace)
        pix = types.SimpleNamespace(get_width=lambda: 40, get_height=lambda: 20)
        area = types.SimpleNamespace(_syn_pixbuf=pix)
        cr = types.SimpleNamespace(paint=lambda: calls.append(('paint',)))
        namespace['_draw_channel_logo'](None, area, cr, 108, 38)
        self.assertEqual(calls, [('source', 34.0, 9.0), ('paint',)])


if __name__ == '__main__':
    unittest.main()
