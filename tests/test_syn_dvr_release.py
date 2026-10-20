"""Offline smoke tests of the source release; never load personal IPTV files."""
import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

class ReleaseSmokeTests(unittest.TestCase):
    def test_source_and_player_agents_independent(self):
        import syn_sources
        opts = {'user_agent': 'VLC'}
        self.assertEqual(syn_sources.metadata_user_agent(opts), 'SYN/2.0')
        self.assertTrue(syn_sources.network_user_agent(opts).startswith('VLC/'))

    def test_recorder_user_agent_vlc(self):
        import syn_dvr
        job = {'url': 'https://example.invalid/live.ts', 'user_agent': syn_dvr.VLC_UA,
               'end': None}
        cmd = syn_dvr.ffmpeg_command(job, ROOT / 'sample.mkv')
        self.assertEqual(cmd[cmd.index('-user_agent') + 1], syn_dvr.VLC_UA)
        self.assertIn('copy', cmd)

    def test_appid_and_version(self):
        code = (ROOT / 'syn.py').read_text(encoding='utf-8')
        manifest = (ROOT / 'com.mrseivane.Syn.yml').read_text(encoding='utf-8')
        self.assertIn('SYN_VERSION = "1.2.2-dvr"', code)
        self.assertIn('id: com.mrseivane.Syn\n', manifest)
        self.assertIn('syn-dvr-worker', manifest)

if __name__ == '__main__':
    unittest.main()
