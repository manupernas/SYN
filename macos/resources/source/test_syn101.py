import unittest
import syn
import syn_sources

class Syn101Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(syn.SYN_VERSION, '1.0.2b')
    def test_accent_selectors(self):
        css = syn.accent_css('#279b91')
        self.assertIn('window.iptv-tv togglebutton:checked', css)
        self.assertIn('background-color: #279B91', css)
        self.assertIn('window.syn-settings-window selection', css)
        self.assertEqual(syn.accent_css(''), '')
    def test_persist_last_ui_config(self):
        cfg = syn_sources.blank_config()
        cfg['last_ui'] = {'favorites': True, 'category':'Cine', 'guide': False}
        self.assertTrue(cfg['last_ui']['favorites'])
        self.assertIn('last_ui', cfg)

if __name__ == '__main__': unittest.main()
