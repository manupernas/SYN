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
            16: 'fce3e06b2d2d02905f18664cef4f3d79f431bedd472656f18ed2fee168e8a333',
            24: '2b26324c6e01900b92194a49a99e8fbd5540f75f0eadde490bde56b2156f083e',
            32: '19f807e45145937063dad5a987275df38ffa716bd1c0ca58053e082bdf6d33e5',
            48: '08cc430778c4df6ecb0ea8f3e326525e1ef4bf21799fb03648ff6a6f0fc70f48',
            64: 'fba78683e7f5517d77d26e11771be413857a70c10e3b773815c62301553aa3b3',
            96: 'bdfd89dae5b23b19aceb20275f14bfd87349142ddb9e13aef45c2c2260267445',
            128: '7dffbfc87f9c2216396100463b2599731d6336ce99f2e6d5a718ff4dde871757',
            256: '44d5b7e0a4e1d1afadf2ac843fafc475a02332fb4b809958fe785c9c32b15ad0',
            512: '981c9eed8e0e2acf65da0c3f247a327962c4bfc21c113d9004d58eee2aed2113',
        }
        for size, expected in reference.items():
            target = ROOT / 'icons' / f'{size}x{size}' / 'apps' / 'com.mrseivane.Syn.png'
            self.assertTrue(target.is_file(), str(target))
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), expected)

    def test_host_setup_only_for_our_app(self):
        content = setup._HOST_SETUP
        self.assertIn('app=com.mrseivane.Syn', content)
        self.assertIn('systemctl --user enable --now "$worker"', content)
        self.assertIn('flatpak run --command=', content.replace('$flatpak_bin', 'flatpak'))
        self.assertIn('is-active --quiet "$worker"', content)
        self.assertIn('existing custom worker service', content)
        self.assertNotIn('systemctl --user restart', content)

    @patch.object(setup, '_native_user_override_exists', return_value=False)
    @patch.object(setup.shutil, 'which', return_value='/usr/bin/systemctl')
    @patch.object(setup.subprocess, 'run', return_value=Mock(returncode=0, stderr='', stdout=''))
    def test_native_enables_worker_without_restarting(self, run, which, override):
        setup._run_native()
        cmds = [tuple(call.args[0]) for call in run.call_args_list if 'enable' in call.args[0]]
        self.assertEqual(cmds, [
            ('systemctl', '--user', 'enable', '--now', 'syn-dvr-worker.service')])

    @patch.object(setup, '_native_user_override_exists', return_value=True)
    @patch.object(setup.shutil, 'which', return_value='/usr/bin/systemctl')
    @patch.object(setup.subprocess, 'run')
    def test_native_preserves_foreign_services(self, run, which, override):
        setup._run_native()
        self.assertFalse(any('enable' in call.args[0] for call in run.call_args_list))

    @patch.object(setup.shutil, 'which', return_value='/usr/bin/flatpak-spawn')
    @patch.object(setup.subprocess, 'run', return_value=Mock(returncode=0, stderr='', stdout=''))
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
