"""SYN 3.6: GTK-only right-edge cinema zapping tests."""
import ast
from pathlib import Path
import unittest
import yaml
R = Path(__file__).resolve().parent
S = (R / 'syn.py').read_text(encoding='utf-8')

class CinemaZapTests(unittest.TestCase):
    def test_right_hand_gradient_not_card(self):
        self.assertIn('linear-gradient(to left', S)
        self.assertIn('.syn-zap-backdrop', S)
        self.assertIn('rgba(5, 34, 36, 0.00) 100%', S)
        css = S.split('.syn-zap-panel {', 1)[1].split('}', 1)[0]
        self.assertIn('background: transparent', css)
        self.assertIn('box-shadow: none', css)
    def test_panel_keeps_glarea_and_no_popover_in_fullscreen(self):
        self.assertIn('self.overlay.add_overlay(self.fs_remote_revealer)', S)
        self.assertIn('Gtk.RevealerTransitionType.SLIDE_LEFT', S)
        self.assertIn('Gtk.Align.END', S)
        self.assertIn('self.fs_search.grab_focus()', S)
        self.assertIn('self.fs_remote_revealer.set_child(remote_backdrop)', S)
        self.assertIn('def fs_activate_channel', S)
        self.assertIn('def set_fs_remote', S)
        ast.parse(S)
    def test_next_epg(self):
        self.assertIn('A continuación', S)
        self.assertIn('sources.now_next', S)
    def test_gtk_only_package(self):
        manifest = yaml.safe_load((R / 'com.mrseivane.Syn.yml').read_text())
        names = [m['name'] for m in manifest['modules']]
        self.assertEqual(names[-1], 'syn')
        self.assertFalse(any('qt' in name.lower() for name in names))
        self.assertNotIn('syn_qt.py', str(manifest))
        self.assertNotIn('--ui=qt', (R / 'syn-flatpak').read_text())

if __name__ == '__main__': unittest.main()
