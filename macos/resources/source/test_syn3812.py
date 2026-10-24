"""Regresiones del tema Claro: menús desplegables GTK4 (código/estilos)."""
import unittest
from pathlib import Path
import syn

SRC = Path(__file__).with_name('syn.py').read_text(encoding='utf-8')

def palette(label, next_label):
    return SRC.split(f'    {label} = """',1)[1].split(f'    """\n    {next_label} = """',1)[0]

class LightDropdownTests(unittest.TestCase):
    def test_correct_version(self):
        self.assertEqual(syn.SYN_VERSION, '1.0.2b')

    def test_popup_contents_are_opaque_light(self):
        css = palette('LIGHT_CSS', 'DARK_CSS')
        self.assertIn('popover.background > contents', css)
        self.assertIn('background: #f8fffc;', css)
        self.assertIn('color: #154a40;', css)
        self.assertIn('background: #a9dfd0;', css)
        self.assertIn('popover.background listview row:selected label', css)

    def test_separate_hover_and_selection_states(self):
        css = palette('LIGHT_CSS', 'DARK_CSS')
        for selector in ('dropdown > button', 'popover.background listview row:hover',
                         'popover.background listview row:selected',
                         'popover.background listview row:selected:hover label',
                         'popover.background searchentry'):
            self.assertIn(selector, css)

    def test_only_light_overrides_popup_colors(self):
        # No se debe meter el parche en CSS base/global de todos los temas.
        base = palette('BASE_CSS','FAVORITE_GEOMETRY_CSS') if '    """\n    FAVORITE_GEOMETRY_CSS = """' in SRC else SRC.split('    BASE_CSS = """')[1].split('    """\n',1)[0]
        self.assertNotIn('popover.background > contents', base)
        dark = SRC.split('    DARK_CSS = """', 1)[1].split('    """\n',1)[0]
        self.assertIn('popover.background > contents', dark)

    def test_colors_have_high_contrast(self):
        def lum(hexstr):
            v=[int(hexstr[x:x+2],16)/255 for x in (1,3,5)]
            v=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in v]
            return sum(a*b for a,b in zip(v,(.2126,.7152,.0722)))
        for fg,bg in [('#154a40','#f8fffc'),('#103f36','#a9dfd0'),('#123f36','#d4efe6')]:
            light,dark=sorted([lum(fg),lum(bg)],reverse=True)
            self.assertGreater((light+.05)/(dark+.05),4.5)

if __name__=='__main__': unittest.main()
