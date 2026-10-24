"""Checks for source parity and 8-package release. No IPTV access or GTK display."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent


class Release132Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.syn = (ROOT / 'syn.py').read_text(encoding='utf-8')

    def test_version_and_proven_rev6_scroll(self):
        self.assertIn('SYN_VERSION = "2.0.6"', self.syn)
        for feature in (
            'SYN_REV6_EXTERNAL_SCROLL',
            'Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL',
            'def _guide_wheel_scroll(',
            'self.guide_tracks_scroll.get_vadjustment()',
            'def _guide_touch_begin(',
            'def _guide_horizontal_move(',
        ):
            with self.subTest(feature=feature):
                self.assertIn(feature, self.syn)

    def test_favourites_and_settings(self):
        for token in ('syn_favoritos', 'syn_settings_rev3', '_guide_programmes_for(',
                      'def _favorite_heart_button(', '♡', '♥'):
            with self.subTest(token=token):
                self.assertIn(token, self.syn)
        for file in ('syn_favoritos.py','syn_settings_rev3.py','syn_locale_rev3.py'):
            self.assertTrue((ROOT / file).is_file(), file)

    def test_every_distribution_ships_helpers(self):
        for f in ('packaging/stage-native.sh', 'com.mrseivane.Syn.yml'):
            text = (ROOT / f).read_text(encoding='utf-8')
            for name in ('syn_favoritos.py','syn_settings_rev3.py','syn_locale_rev3.py'):
                with self.subTest(distribution=f, module=name):
                    self.assertIn(name, text)

    def test_tag_runs_8_package_release(self):
        ci = (ROOT / '.github/workflows/release-10-packages.yml').read_text(encoding='utf-8')
        for token in ("'v[0-9]*.[0-9]*.[0-9]*'", 'format: [rpm, deb, pacman]',
                      'arch: [x86_64, aarch64]', 'Publish exactly 8 packages and SHA256'):
            self.assertIn(token, ci)
        self.assertIn('test_syn_release_132.py', ci)
        self.assertTrue((ROOT / 'docs/RELEASE_1.3.2.md').is_file())
        self.assertIn('**SYN 1.3.7**', (ROOT / 'README.md').read_text(encoding='utf-8'))
        self.assertIn('<release version="1.3.2"', (ROOT / 'com.mrseivane.Syn.metainfo.xml').read_text(encoding='utf-8'))

    def test_no_included_user_data(self):
        self.assertFalse((ROOT/'profiles.json').exists())
        self.assertFalse((ROOT/'dvr.json').exists())


if __name__ == '__main__':
    unittest.main()
