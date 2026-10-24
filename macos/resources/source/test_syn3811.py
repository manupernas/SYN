"""SYN 3.8.11: pruebas del scroll de EPG y de la paleta clara.

No simulan GTK; verifican las ramas de control y las reglas críticas que
provocaban que la lista no pudiera navegarse o el modo Claro quedase oscuro.
"""
import ast
from pathlib import Path
import textwrap
import unittest
import syn

SRC = Path(__file__).with_name('syn.py').read_text(encoding='utf-8')


def method_as_callable(name):
    tree = ast.parse(SRC)
    node = next(x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name == name)
    code = ast.get_source_segment(SRC, node)
    ns = {}
    exec(textwrap.dedent(code), ns)
    return ns[name]


class Adjustment:
    def __init__(self, upper=1680, page=490, value=0):
        self.upper, self.page, self.value = upper, page, value
    def get_lower(self): return 0
    def get_upper(self): return self.upper
    def get_page_size(self): return self.page
    def get_value(self): return self.value
    def set_value(self, value): self.value = value

class FakeWindow:
    guide_open = True
    def __init__(self, adjustment):
        self.guide_tracks_scroll = type('Scroll', (), {'get_vadjustment': lambda self_: adjustment})()
        self.pages = []
    def guide_page_step(self, direction, wheel=False):
        self.pages.append((direction, wheel))

class GuideScrollTests(unittest.TestCase):
    def setUp(self):
        self.scroll = method_as_callable('_guide_wheel_scroll')
    def test_scrolling_over_guide_moves_shared_adjustment(self):
        adj = Adjustment(value=30)
        fake = FakeWindow(adj)
        self.assertTrue(self.scroll(fake, None, 0, 1))
        self.assertEqual(adj.value, 95)
        self.assertEqual(fake.pages, [])
    def test_next_24_channels_at_bottom(self):
        adj = Adjustment(value=1190)
        fake = FakeWindow(adj)
        self.scroll(fake, None, 0, 1)
        self.assertEqual(fake.pages, [(1, True)])
    def test_previous_24_channels_at_top(self):
        adj = Adjustment(value=0)
        fake = FakeWindow(adj)
        self.scroll(fake, None, 0, -1)
        self.assertEqual(fake.pages, [(-1, True)])
    def test_both_columns_have_explicit_wheel_and_share_adjustment(self):
        build = SRC.split('        def build_epg_guide(self):', 1)[1].split('        def _guide_draw_axis(', 1)[0]
        self.assertIn('self.guide_names_scroll.set_vadjustment(self.guide_tracks_scroll.get_vadjustment())',build)
        self.assertIn('for scrolling_column in (self.guide_names_scroll, self.guide_tracks_scroll):',build)
        self.assertIn('wheel.connect(\'scroll\', self._guide_wheel_scroll)', build)
        self.assertIn('Gtk.PolicyType.ALWAYS', build)
        self.assertIn('self.guide_categories_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)', build)
    def test_light_palette_covers_guide_zap_and_welcome(self):
        css = SRC.split('    LIGHT_CSS = """', 1)[1].split('    """\n    DARK_CSS', 1)[0]
        for marker in ('.syn-guide-search', '.syn-guide-head-button', '.syn-guide-program-name',
                       '.syn-zap-search', '.syn-zap-panel', '.syn-zap-row',
                       '.syn-fs-top button', '.syn-welcome-bg', '.syn-welcome-card',
                       '.syn-fs-volume', '.syn-guide-backdrop'):
            self.assertIn(marker, css, marker)
    def test_version(self):
        self.assertEqual(syn.SYN_VERSION, '1.0.2b')

if __name__ == '__main__': unittest.main()
