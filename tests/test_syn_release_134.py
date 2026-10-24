"""Release 1.3.4 contract: Cast recovery, FullHD quality and automatic startup."""
import ast
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

class Release134Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui=(ROOT/'syn.py').read_text('utf-8')
        cls.cast=(ROOT/'syn_cast_host.py').read_text('utf-8')

    def test_version_and_sources(self):
        self.assertIn('SYN_VERSION = "2.0.6"',self.gui)
        self.assertIn('<release version="1.3.4"', (ROOT/'com.mrseivane.Syn.metainfo.xml').read_text())
        self.assertTrue((ROOT/'docs/RELEASE_1.3.4.md').is_file())

    def test_working_mibox_recovery(self):
        for s in ('SYN_CAST_MIBOX_RECOVERY_1','register_status_listener(cast_probe)',
                  "stream_type='BUFFERED'", "CURRENT['media_hits']['m3u8']>0"):
            self.assertIn(s,self.cast)

    def test_balanced_quality_preserves_720p(self):
        self.assertIn('SYN_CAST_1080_BALANCE_V1',self.cast)
        self.assertIn("'alta': {'height': 1080, 'bitrate': '6300k', 'maxrate': '7500k', 'bufsize': '14000k'}",self.cast)
        self.assertIn("'compatible': {'height': 720, 'bitrate': '2500k', 'maxrate': '3000k', 'bufsize': '4000k'}",self.cast)
        self.assertIn("'main' if quality=='alta' else 'baseline'",self.cast)
        self.assertIn("'-hls_init_time','1'",self.cast)

    def test_plug_play_and_no_meson_duplicate(self):
        s=(ROOT/'syn_cast_autostart.py').read_text('utf-8')
        self.assertIn('syn-cast-mibox-recovery/current/syn_cast_host.py',s)
        self.assertIn('_retire_known_local_cast_patch()',s)
        y=(ROOT/'com.mrseivane.Syn.yml').read_text('utf-8')
        self.assertNotIn('-Dlibdir=lib',y)
        self.assertIn('syn_cast_host.py',y)
        self.assertIn('pychromecast==14.0.10',y)
        self.assertIn('syn_cast_host.py',(ROOT/'packaging/stage-native.sh').read_text())

    def test_syntax(self):
        for name in ('syn.py','syn_cast_host.py','syn_cast_autostart.py'):
            ast.parse((ROOT/name).read_text('utf-8'),filename=name)

if __name__=='__main__':unittest.main()
