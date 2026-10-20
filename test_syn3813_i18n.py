"""Locale tests for SYN 3.8.13; provider names/config keys remain unchanged."""
from syn_test_backend import baseline_digest

import os
import gettext
import unittest
from pathlib import Path
import syn_i18n
import syn
import syn_sources
import datetime as dt
ROOT = Path(__file__).parent

class LocaleTests(unittest.TestCase):
    def test_detection(self):
        detect = syn_i18n.detect_language
        self.assertEqual(detect({'LANG':'en_US.UTF-8'}),'en_US')
        self.assertEqual(detect({'LANG':'en_GB.UTF-8'}),'en_GB')
        self.assertEqual(detect({'LANG':'es_ES.UTF-8'}),'es')
        self.assertEqual(detect({'LANG':'fr_FR.UTF-8'}),'es')
        self.assertEqual(detect({'LANG':'en_US','LC_MESSAGES':'en_GB.UTF-8'}),'en_GB')
        self.assertEqual(detect({'LANG':'es_ES','LANGUAGE':'en_US:en_GB'}),'en_US')

    def test_regional_clock(self):
        import unittest.mock as mock
        for lang,expected in [('en_US','6:45 PM'),('en_GB','18:45'),('es','18:45')]:
            with mock.patch.object(syn_i18n, 'LANGUAGE', lang):
                self.assertEqual(syn_i18n.format_time(dt.datetime(2026,10,20,18,45)), expected)

    def test_catalogues_translate_same_ui(self):
        for lang,expected in [('en_US','Favorites only'),('en_GB','Favourites only')]:
            trans=gettext.translation('syn',localedir=str(ROOT/'locale'),languages=[lang])
            self.assertEqual(trans.gettext('Solo favoritos'), expected)
        self.assertEqual(gettext.translation('syn',localedir=str(ROOT/'locale'),languages=['en_GB']).gettext('Guía de televisión'), 'TV Guide')

    def test_no_profile_protocol_changes(self):
        self.assertIn("'user_agent': ['Predeterminado','VLC','Firefox','Safari','Personalizado'][ua.get_selected()]", (ROOT/'syn.py').read_text())
        self.assertEqual(syn.display_channel_name('|ES| LA 1 UHD (4K)'), 'LA 1 UHD (4K)')
        self.assertEqual(syn_sources.blank_config()['theme'],'system')

    def test_unmodified_video_core(self):
        import ast,hashlib
        node=ast.parse((ROOT/'syn.py').read_text())
        mpv=next(n for n in node.body if isinstance(n,ast.ClassDef) and n.name=='NativeMpv')
        self.assertEqual(hashlib.sha256(ast.dump(mpv,include_attributes=False).encode()).hexdigest(),
                         baseline_digest('NativeMpv'))

if __name__=='__main__':unittest.main()
