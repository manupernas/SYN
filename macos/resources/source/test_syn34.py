"""SYN 3.4: regresión sin servidor ni interfaz gráfica."""
import ast
import datetime as dt
import gzip
import tempfile
import unittest
from pathlib import Path
import syn
import syn_sources as S

R=Path(__file__).resolve().parent
XML=b'''<?xml version="1.0"?><tv><channel id="uno"><display-name>La uno</display-name></channel><programme channel="uno" start="20261019130000 +0200" stop="20261019150000 +0200"><title>El programa</title></programme></tv>'''

class Syn34Tests(unittest.TestCase):
    def test_local_xml_and_gzip_epg(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml=Path(tmp)/'guia.xml'
            gz=Path(tmp)/'guia.xml.gz'
            xml.write_bytes(XML)
            with gzip.open(gz, 'wb') as f: f.write(XML)
            for file in (xml,gz):
                p=S.default_profile(Path(tmp)/'channels.m3u')
                p['epg_url']=str(file)
                (Path(tmp)/'channels.m3u').write_text('#EXTM3U')
                S.validate_profile(p)
                self.assertEqual(S.profile_epg_url(p),str(file))
                channels, aliases=S.get_epg(p)
                self.assertEqual(channels['uno'][0][2],'El programa')
                self.assertEqual(aliases['la uno'],'uno')
    def test_local_epg_missing_or_bad_ext(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('nada.xml.gz','archive.zip'):
                with self.assertRaises(ValueError): S.validate_epg_source(str(Path(tmp)/name))
    def test_gzip_max_decompressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'guide.xml.gz'
            with gzip.open(dest,'wb') as f: f.write(b'A'*1000)
            with self.assertRaisesRegex(ValueError,'descomprimido'):
                S.read_local_xmltv(dest, max_size=500)
    def test_host_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'.config/gtk-4.0/settings.ini'
            config.parent.mkdir(parents=True)
            config.write_text('[Settings]\ngtk-theme-name=Colloid-Dark-Teal\ngtk-application-prefer-dark-theme=true\n')
            self.assertEqual(syn.host_gtk_settings(Path(tmp)),('Colloid-Dark-Teal',True))
            self.assertTrue(syn.gtk_theme_prefers_dark(syn.host_gtk_settings(tmp)[0]))
    def test_responsive_and_theme_scoping(self):
        text=(R/'syn.py').read_text()
        self.assertIn('set_shrink_start_child(False)',text)
        self.assertIn('def _enforce_sidebar_width',text)
        self.assertIn('Gtk.STYLE_PROVIDER_PRIORITY_USER + 1',text)
        self.assertIn('default_width=1280, default_height=720',text)
        self.assertIn('Seleccionar EPG…',text)
        self.assertIn('Buscar archivo EPG…',text)
    def test_player_unchanged(self):
        tree=ast.parse((R/'syn.py').read_text())
        import hashlib
        node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeMpv')
        self.assertEqual(hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
                         'fccf6acdefea0a48051946aa54d796c0877590d3b9e47940753bfe8e598ed19e')

if __name__=='__main__': unittest.main(verbosity=2)
