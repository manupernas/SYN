"""SYN 1.3.3 offline packaging/content checks; no credentials or LAN needed."""
from pathlib import Path
import ast
import unittest
ROOT=Path(__file__).resolve().parent.parent

class Release133Tests(unittest.TestCase):
    def test_features(self):
        s=(ROOT/'syn.py').read_text('utf-8')
        self.assertIn('SYN_VERSION = "1.3.7"',s)
        for marker in ('SYN_CAST_BETA6','SYN_CAST_ORANGE_VISUAL_6_2',
                       'SYN_FAVORITOS_DRAG_BETA7','SYN_FAVORITOS_VISUAL_BETA7_1',
                       'Gtk.WidgetPaintable.new(row)','SYN_TIMESHIFT_BETA2_HTTP_SNAPSHOT'):
            with self.subTest(marker=marker):self.assertIn(marker,s)
    def test_host_fidelity(self):
        s=(ROOT/'syn_cast_host.py').read_text('utf-8')
        self.assertIn('libx264',s);self.assertIn("'-c:a','aac'",s)
        self.assertIn("'-profile:v',('main' if quality=='alta' else 'baseline')",s)
    def test_all_packages_ship_code(self):
        a=(ROOT/'packaging/stage-native.sh').read_text()
        b=(ROOT/'com.mrseivane.Syn.yml').read_text()
        for file in ('syn_fav_sort.py','syn_reconnect.py','syn_multistream.py',
                     'syn_timeshift.py','syn_cast_host.py','syn_idle_screen.png'):
            with self.subTest(file=file):
                self.assertIn(file,a);self.assertIn(file,b)
                self.assertTrue((ROOT/file).is_file())
        self.assertTrue((ROOT/'icons/symbolic/apps/chromecast-symbolic.svg').is_file())
        self.assertIn('instalar-servicio-cast.sh',a+b)
    def test_syntax(self):
        for name in ('syn.py','syn_fav_sort.py','syn_cast_host.py'):
            ast.parse((ROOT/name).read_text('utf-8'), filename=name)
    def test_release_docs(self):
        self.assertTrue((ROOT/'docs/RELEASE_1.3.3.md').exists())
        self.assertIn('release version="1.3.3"', (ROOT/'com.mrseivane.Syn.metainfo.xml').read_text())
