"""Static/package regressions; headless machine does not have Gtk/Flatpak."""
from pathlib import Path
import ast
import unittest
import yaml
import syn_sources as ss
R=Path(__file__).parent
class Syn3Tests(unittest.TestCase):
 def test_python_parse(self):
  ast.parse((R/'syn.py').read_text())
  ast.parse((R/'syn_sources.py').read_text())
 def test_source_theme(self):
  self.assertEqual(ss.blank_config()['theme'],'system')
 def test_fullscreen_components(self):
  src=(R/'syn.py').read_text()
  for t in ('build_fullscreen_osd','fs_remote','fs_channel_label','fs_epg_label','fs_volume','fs_remote_revealer','self.zap(', 'on_video_click','set_fs_osd', 'Adw.ColorScheme.FORCE_LIGHT', 'Adw.ColorScheme.FORCE_DARK'):
   self.assertIn(t,src)
 def test_flatpak_manifest_arch_independent(self):
  d=yaml.safe_load((R/'com.mrseivane.Syn.yml').read_text())
  self.assertEqual(d['id'],'com.mrseivane.Syn')
  self.assertTrue(any(m['name']=='syn-libmpv' for m in d['modules']))
  self.assertFalse(any('only-arches' in m for m in d['modules']))
 def test_no_secrets_packaged(self):
  for f in R.glob('*.m3u'): self.fail(f'Contains private playlist: {f}')
if __name__=='__main__':unittest.main(verbosity=2)
