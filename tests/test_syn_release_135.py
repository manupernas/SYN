"""SYN 1.3.5 source/packaging tests: never access real IPTV accounts."""
from pathlib import Path
import ast
import re
import unittest
from types import SimpleNamespace
import syn_catalog

ROOT=Path(__file__).resolve().parent.parent

class Release135Tests(unittest.TestCase):
    def test_version_and_unversioned_library_label(self):
        source=(ROOT/'syn.py').read_text('utf-8')
        self.assertIn('SYN_VERSION = "1.3.7"',source)
        self.assertIn('SYN  /  TU BIBLIOTECA',source)
        self.assertNotIn('CARTELERA  ·  1.3.5',source)
        for method in ('_syn_portal_build','_syn_portal_open','_syn_135d_refresh_wordmark'):
            self.assertIn(method,source)
        ast.parse(source)

    def test_m3u_films_series_and_live_tv(self):
        rows=[SimpleNamespace(group='ES TV',name='Canal 1',url='https://example.test/live/x',logo=''),
              SimpleNamespace(group='Cine',name='Film 1',url='https://example.test/movie/x',logo=''),
              SimpleNamespace(group='Series',name='Show S01E01',url='https://example.test/series/1',logo=''),
              SimpleNamespace(group='Series',name='Show S01E02',url='https://example.test/series/2',logo='')]
        tv,movies,series=syn_catalog.partition_channels(rows)
        self.assertEqual((len(tv),len(movies),len(series)),(1,1,2))
        shows=syn_catalog.local_series_catalog(series)
        self.assertEqual(len(shows),1)
        self.assertEqual(len(shows[0]['children']),2)

    def test_native_and_flatpak_share_media_modules(self):
        for file in ('com.mrseivane.Syn.yml','packaging/stage-native.sh'):
            content=(ROOT/file).read_text('utf-8')
            for token in ('syn_catalog.py','syn_poster.py','branding'):
                self.assertIn(token,content)
            self.assertNotIn('syn-dvr-tray',content)
        self.assertFalse((ROOT/'syn_dvr_tray.py').exists())

    def test_brand_assets_and_docs(self):
        for name in ('logo_dark.png','logo_light.png','icono_3.png'):
            self.assertTrue((ROOT/'branding'/name).is_file())
        self.assertTrue((ROOT/'docs/brand/syn-readme-banner.png').is_file())
        readme=(ROOT/'README.md').read_text('utf-8')
        for token in ('CINE','SERIES','Flatpak','RPM','DEB','Pacman','plug'):
            self.assertIn(token.lower(),readme.lower())

if __name__=='__main__': unittest.main()
