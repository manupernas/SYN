"""Offline release smoke tests. No IPTV credentials, channels or streams are accessed."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class ReleaseSmokeTests(unittest.TestCase):
    def test_user_agents_separate(self):
        import syn_sources
        opts = {'user_agent': 'VLC'}
        self.assertEqual(syn_sources.metadata_user_agent(opts), 'SYN/2.0')
        self.assertTrue(syn_sources.network_user_agent(opts).startswith('VLC/'))

    def test_dvr_single_input_dual_output_without_reencode(self):
        import syn_dvr
        job = {'id':'123456789abcdef', 'url':'https://example.invalid/stream',
               'user_agent':syn_dvr.VLC_UA, 'end':None}
        cmd = syn_dvr.ffmpeg_command(job, ROOT/'sample.mkv')
        self.assertEqual(cmd.count('-i'),1)
        self.assertEqual(cmd[cmd.index('-user_agent')+1],syn_dvr.VLC_UA)
        self.assertIn('matroska',cmd)
        self.assertIn('mpegts',cmd)
        self.assertTrue(cmd.count('copy') >= 2)
        self.assertEqual(cmd.count('-c'),2)

    def test_tray_status_menu(self):
        import syn_dvr_tray
        rows = syn_dvr_tray.menu_rows(['Test Channel'], True)
        self.assertTrue(any(row[0] == 40 and row[2] for row in rows))
        self.assertTrue(any(row[0] == 41 and row[2] for row in rows))
        self.assertTrue(any('Test Channel' in row[1] for row in rows))
        self.assertEqual(syn_dvr_tray.read_state('/does/not/exist/dvr.json'), (False, [], None))

    def test_app_version_and_flatpak_manifest(self):
        s = (ROOT/'syn.py').read_text(encoding='utf-8')
        m = re.search(r'^SYN_VERSION\s*=\s*[\'\"]([^\'\"]+)',s,re.M)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1),r'^\d+\.\d+(?:\.\d+)?$')
        manifest = (ROOT/'com.mrseivane.Syn.yml').read_text(encoding='utf-8')
        for required in ('id: com.mrseivane.Syn','syn-dvr-worker',
                         'syn_dvr_tray.py','syn-dvr-tray',
                         '--own-name=com.mrseivane.Syn.Tray'):
            self.assertIn(required,manifest)

    def test_native_package_contains_two_user_services(self):
        path = (ROOT/'packaging/stage-native.sh').read_text(encoding='utf-8')
        for name in ('syn-dvr-worker.service','syn-dvr-tray.service',
                     'syn_dvr_tray.py','syn-dvr-tray'):
            self.assertIn(name,path)


if __name__ == '__main__':
    unittest.main()


class ServiceSetupReleaseTests(unittest.TestCase):
    def test_auto_service_installed_all_formats(self):
        assert "syn_service_setup.py" in (ROOT/"packaging/stage-native.sh").read_text()
        assert "syn_service_setup.py" in (ROOT/"com.mrseivane.Syn.yml").read_text()
        src = (ROOT/"syn.py").read_text()
        assert "syn_service_setup.ensure_services_async()" in src
        assert src.index("if not syn_dvr.background_worker_confirmed():") < src.index("paused = bool(player")
