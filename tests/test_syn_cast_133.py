"""Offline release-gate checks for tested CAST 6.5 integration."""
from pathlib import Path
import ast
import unittest
ROOT = Path(__file__).resolve().parent.parent

class CastStable133Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'syn.py').read_text('utf-8')
        cls.bridge = (ROOT / 'syn_cast_host.py').read_text('utf-8')

    def test_python_syntax_and_version(self):
        ast.parse(self.app)
        ast.parse(self.bridge)
        self.assertIn('SYN_VERSION = "1.3.5"', self.app)

    def test_original_approved_features_preserved(self):
        for marker in ('SYN_CAST_BETA6', 'SYN_CAST_ORANGE_VISUAL_6_2',
                       'SYN_FAVORITOS_DRAG_BETA7', 'SYN_FAVORITOS_VISUAL_BETA7_1',
                       'SYN_TIMESHIFT_BETA2_HTTP_SNAPSHOT'):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)

    def test_shared_hls_rejoin_and_dvr_guard(self):
        for marker in ('SYN_CAST_SHARED_RELAY_BETA6_4',
                       'SYN_CAST_REJOIN_SHARED_BETA6_5',
                       'def _syn_cast_rejoin_shared(self, channel):',
                       "{'action':'local_usage','shared':True}",
                       "{'action':'local_usage','shared':False}"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.app)
        self.assertIn("elif action=='local_usage':", self.bridge)
        self.assertIn("'local_url':CURRENT['local_url']", self.bridge)

    def test_light_theme_icon(self):
        self.assertIn('SYN_CAST_CONTRASTE_CLARO_6_5', self.app)
        self.assertIn('window.iptv-tv button.syn-cast-button', self.app)
        self.assertIn('Gtk.STYLE_PROVIDER_PRIORITY_USER + 8', self.app)
        self.assertIn('background-color: #FF6B00;', self.app)

    def test_only_two_slider_positions(self):
        self.assertIn('SYN_CAST_SLIDER_720_1080_BETA6_5', self.app)
        self.assertIn("resolution_slider.add_mark(0, Gtk.PositionType.BOTTOM, '720p')", self.app)
        self.assertIn("resolution_slider.add_mark(1, Gtk.PositionType.BOTTOM, '1080p')", self.app)
        self.assertNotIn("resolution_slider.add_mark(2", self.app)
        self.assertIn("'.config/syn/cast-quality'", self.app)

    def test_fullhd_optional_but_720_default(self):
        self.assertIn('SYN_CAST_FHD1080_OPTIONAL_BETA6_5', self.bridge)
        self.assertIn("'alta': {'height': 1080", self.bridge)
        self.assertIn("'compatible': {'height': 720", self.bridge)
        self.assertIn("'-c:v','libx264'", self.bridge)
        self.assertIn("'-c:a','aac'", self.bridge)
        self.assertIn("'shared_local':", self.bridge)

    def test_packaging_and_ci_gate(self):
        for name in ('packaging/stage-native.sh', 'com.mrseivane.Syn.yml'):
            content=(ROOT/name).read_text('utf-8')
            self.assertIn('syn_cast_host.py', content)
            self.assertIn('syn_timeshift.py', content)
            self.assertIn('syn_fav_sort.py', content)
        self.assertIn('tests/test_syn_cast_133.py',
                      (ROOT/'.github/workflows/release-10-packages.yml').read_text('utf-8'))

if __name__ == '__main__':
    unittest.main()
