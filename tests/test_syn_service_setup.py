"""Offline auto-enable tests: never call actual systemd or host services."""
import os
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import syn_service_setup as setup


class AutomaticServiceTests(unittest.TestCase):
    def test_new_approved_icon_in_all_nine_sizes(self):
        reference = {
            16: 'f0539e9cca0444649512526a53c5709da2c21cdd6889dc6988efa40a7c66e108',
            24: '105dbf30b9df061ede8a7327379c795a84d61869ba43b43117eb25d0f6dffe25',
            32: '1083686036314c2807bed0e9bf1ef16a0f7027c271615a6493711f0211d7981b',
            48: '6e9b9a24c664831af7458211c1825377deda339c309404e2d54b47c389861e57',
            64: 'c98939c69d9e49b39229f85627f254d9edb9b1fdc60fd0662a69fe88776c725c',
            96: '9a1493d974c3e266d671d13f0f29dc97bd545e3aa129c772dd8948e61b576f0f',
            128: 'e9a20030f70a4f1009628fdd5f87f4812be95a246ae202f8c043e43e28b19583',
            256: '0ad07e4c23c868502a8f73f7490c351acc59d8e2c3212fa1a690e9c4ae3e7dcd',
            512: '9d4d832d50f70c66be4d0f2884348c4b1978257ee833f24a214e741856f0d91f',
        }
        for size, expected in reference.items():
            target = ROOT / 'icons' / f'{size}x{size}' / 'apps' / 'com.mrseivane.Syn.png'
            self.assertTrue(target.is_file(), str(target))
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), expected)

    def test_host_setup_only_for_our_app(self):
        content = setup._HOST_SETUP
        self.assertIn('app=com.mrseivane.Syn', content)
        self.assertIn('systemctl --user enable --now "$worker" "$tray"', content)
        self.assertIn('flatpak run --command=', content.replace('$flatpak_bin', 'flatpak'))
        self.assertIn('is-active --quiet "$worker"', content)
        self.assertIn('existing custom service', content)
        self.assertNotIn('systemctl --user restart', content)

    @patch.object(setup, '_native_user_override_exists', return_value=False)
    @patch.object(setup.shutil, 'which', return_value='/usr/bin/systemctl')
    @patch.object(setup.subprocess, 'run', return_value=Mock(returncode=0, stderr=''))
    def test_native_enables_both_without_restarting(self, run, which, override):
        setup._run_native()
        cmds = [tuple(call.args[0]) for call in run.call_args_list]
        self.assertEqual(cmds, [
            ('systemctl', '--user', 'enable', '--now', 'syn-dvr-worker.service'),
            ('systemctl', '--user', 'enable', '--now', 'syn-dvr-tray.service')])

    @patch.object(setup, '_native_user_override_exists', return_value=True)
    @patch.object(setup.shutil, 'which', return_value='/usr/bin/systemctl')
    @patch.object(setup.subprocess, 'run')
    def test_native_preserves_foreign_services(self, run, which, override):
        setup._run_native()
        run.assert_not_called()

    @patch.object(setup.shutil, 'which', return_value='/usr/bin/flatpak-spawn')
    @patch.object(setup.subprocess, 'run', return_value=Mock(returncode=0, stderr=''))
    def test_flatpak_installs_only_from_host_spawn(self, run, which):
        setup._run_flatpak()
        args = run.call_args.args[0]
        self.assertEqual(args[:4], ['flatpak-spawn', '--host', 'sh', '-c'])
        self.assertIn('syn-dvr-worker', args[4])

    @patch.object(setup.threading, 'Thread')
    def test_async_throttled_and_no_bootstrap_for_preview(self, thread):
        setup._LAST_START = 0.0
        with patch.dict(os.environ, {'SYN_FIRST_RUN_PREVIEW': '1'}):
            setup.ensure_services_async()
        thread.assert_not_called()
        with patch.dict(os.environ, {'SYN_FIRST_RUN_PREVIEW': ''}, clear=False):
            setup.ensure_services_async()
            setup.ensure_services_async()
        self.assertEqual(thread.call_count, 1)
        setup._LAST_START = 0.0


if __name__ == '__main__':
    unittest.main()
