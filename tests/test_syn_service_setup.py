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
        import struct
        for size in (16, 24, 32, 48, 64, 96, 128, 256, 512):
            target = ROOT / 'icons' / f'{size}x{size}' / 'apps' / 'com.mrseivane.Syn.png'
            self.assertTrue(target.is_file(), str(target))
            data = target.read_bytes()
            self.assertTrue(data.startswith(b'\\x89PNG\\r\\n\\x1a\\n'))
            self.assertGreater(len(data), 100)
            self.assertEqual(struct.unpack('>II', data[16:24]), (size, size))

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
