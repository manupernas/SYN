from syn_test_backend import baseline_digest
import ast, hashlib, unittest, tempfile
from pathlib import Path
import syn
import syn_sources

R=Path(__file__).resolve().parent

class Tests(unittest.TestCase):
    def test_colors(self):
        self.assertEqual(syn.normalize_accent_hex(' #27aA99 '),'#27AA99')
        self.assertEqual(syn.normalize_accent_hex(''), '')
        for malformed in ('red','#abcd','#12345678','#123456;foo'):
            with self.assertRaises(ValueError): syn.normalize_accent_hex(malformed)
        self.assertIn('--accent-bg-color: #27AA99',syn.accent_css('#27aa99'))
    def test_new_config_defaults(self):
        self.assertEqual(syn_sources.blank_config()['accent_hex'], '')
    def test_config_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            current = syn_sources.CONFIG_FILE
            try:
                syn_sources.CONFIG_FILE = Path(d)/'profiles.json'
                cfg = syn_sources.blank_config()
                cfg['accent_hex']='#279B91'
                syn_sources.save_config(cfg)
                self.assertEqual(syn_sources.load_config()['accent_hex'],'#279B91')
            finally:
                syn_sources.CONFIG_FILE = current
    def test_gtk4_css_finder(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            self.assertIsNone(syn.find_host_gtk4_css(home,'Colloid-Dark-Teal',True))
            folder=home/'.config/gtk-4.0';folder.mkdir(parents=True)
            (folder/'gtk.css').write_text('window {}')
            self.assertEqual(syn.find_host_gtk4_css(home,'',False),folder/'gtk.css')
            (folder/'gtk-dark.css').write_text('window {}')
            self.assertEqual(syn.find_host_gtk4_css(home,'',True),folder/'gtk-dark.css')
            (folder/'gtk.css').unlink();(folder/'gtk-dark.css').unlink()
            themed=home/'.themes/Colloid-Dark-Teal/gtk-4.0';themed.mkdir(parents=True)
            (themed/'gtk.css').write_text('window {}')
            self.assertEqual(syn.find_host_gtk4_css(home,'Colloid-Dark-Teal',True),themed/'gtk.css')
    def test_manifest(self):
        y=(R/'com.mrseivane.Syn.yml').read_text()
        self.assertIn('xdg-config/gtk-4.0:ro',y)
        self.assertIn('~/.themes:ro',y)
        self.assertIn('xdg-data/themes:ro',y)
        self.assertIn('com.mrseivane.Syn.yml', (R/'actualizar-flatpak-existente.sh').read_text())
    def test_backend_unchanged(self):
        tree=ast.parse((R/'syn.py').read_text())
        orig={'NativeMpv': baseline_digest('NativeMpv'), 'RenderParam': baseline_digest('RenderParam'), 'GLInit': baseline_digest('GLInit'), 'GLFbo': baseline_digest('GLFbo')}
        for name, expected in orig.items():
            node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
            self.assertEqual(hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest(),expected)
        outer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_gui')
        area=next(n for n in outer.body if isinstance(n,ast.ClassDef) and n.name=='MpvArea')
        self.assertEqual(hashlib.sha256(ast.dump(area,include_attributes=False).encode()).hexdigest(), baseline_digest('MpvArea'))

if __name__=='__main__':unittest.main()
