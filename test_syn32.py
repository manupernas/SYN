"""Headless regression tests for SYN 3.2 UX and render backend preservation."""
import ast
import hashlib
from pathlib import Path
import sys
import unittest
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R))
import syn
import syn_sources as sources

class Syn32Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code=(R/'syn.py').read_text('utf-8')
        cls.tree=ast.parse(cls.code)
    def test_theme_fallback(self):
        self.assertTrue(syn.gtk_theme_prefers_dark('Colloid-Dark-Teal'))
        self.assertTrue(syn.gtk_theme_prefers_dark('Adwaita:dark'))
        self.assertTrue(syn.gtk_theme_prefers_dark('Adwaita', True))
        self.assertFalse(syn.gtk_theme_prefers_dark('Colloid-Light-Teal'))
        self.assertFalse(syn.gtk_theme_prefers_dark('Adwaita'))
    def test_modes(self):
        self.assertIn('Adw.ColorScheme.DEFAULT',self.code)
        self.assertIn('Adw.ColorScheme.FORCE_LIGHT',self.code)
        self.assertIn('Adw.ColorScheme.FORCE_DARK',self.code)
        self.assertIn('notify::gtk-theme-name',self.code)
        self.assertEqual(sources.blank_config()['theme'],'system')
    def test_fullscreen_scrim_and_osd(self):
        for x in ('syn-fs-scrim-top', 'syn-fs-scrim-bottom',
                  'Gtk.Align.END', 'self.fs_top', 'self.fs_remote',
                  'self.fs_volume', 'self.fs_remote_revealer', 'set_can_target(False)',
                  'self.fs_osd_timer', 'self.fs_scrim_bottom'):
            self.assertIn(x,self.code)
        self.assertNotIn('.syn-fs-top { background-color: rgba(5, 18, 20, 0.88)',self.code)
        self.assertNotIn('.syn-fs-bottom { background-color: rgba(5, 18, 20, 0.88)',self.code)
    def test_player_backend_preserved(self):
        original = {'NativeMpv': 'fccf6acdefea0a48051946aa54d796c0877590d3b9e47940753bfe8e598ed19e', 'RenderParam': '9fd3eaa29692cba05b62e377ba73e6fd97a725418b4b98435c48faaf64ba65c6', 'GLInit': '4ec966e4eb40012977aff4334ffa02955f33dbd7c722664d1e99693faf723a68', 'GLFbo': 'b8ce1d05776801867b34d818e08e7f27e9fc3c6c2a5b037aaa8babb918659d4f'}
        for name, expected in original.items():
            node=next(n for n in self.tree.body if isinstance(n,ast.ClassDef) and n.name==name)
            digest=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
            self.assertEqual(digest,expected)
        outer=next(n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_gui')
        mpvarea=next(n for n in outer.body if isinstance(n,ast.ClassDef) and n.name=='MpvArea')
        self.assertEqual(hashlib.sha256(ast.dump(mpvarea,include_attributes=False).encode()).hexdigest(), 'ded6a5dafbb1f348bad81e90c3240a26c1c9366f983fafa8d00f55f4bd08f6e6')
    def test_first_run(self):
        self.assertIn('--preview-first-run',self.code)
        self.assertIn('syn-welcome-bg', self.code)
    def test_app_assets_and_secrets(self):
        for px in (16,24,32,48,64,96,128,256,512):
            self.assertTrue((R/f'icons/{px}x{px}/apps/com.mrseivane.Syn.png').exists())
        self.assertFalse(list(R.glob('*.m3u')))

if __name__=='__main__': unittest.main(verbosity=2)
