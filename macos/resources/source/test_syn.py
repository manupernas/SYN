"""Pruebas locales sin acceso a red de SYN (python3 test_syn.py)."""
import datetime as dt
import gzip
import json
import pathlib
import unittest
from unittest.mock import patch
import syn_sources as S


class TestSources(unittest.TestCase):
    def test_m3u_extended(self):
        text = b'#EXTM3U\n#EXTINF:-1 tvg-id="a.es" tvg-logo="https://example.test/a.png" group-title="ES - TDT",Canal A\nhttps://example.test/live/a.m3u8\n#EXTINF:-1,Canal B\nhttp://example.test/live/b.ts\n'
        result = S.parse_m3u(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, 'Canal A')
        self.assertEqual(result[0].group, 'ES - TDT')
        self.assertEqual(result[0].epg_id, 'a.es')
        self.assertEqual(result[0].logo, 'https://example.test/a.png')
        self.assertEqual(result[1].name, 'Canal B')

    def test_xmltv_now_next(self):
        xml = b'''<?xml version="1.0"?><tv><channel id="a.es"><display-name>Canal A</display-name></channel><programme channel="a.es" start="20261019133000 +0200" stop="20261019143000 +0200"><title>Programa 1</title><desc>Prueba</desc></programme><programme channel="a.es" start="20261019143000 +0200" stop="20261019153000 +0200"><title>Programa 2</title></programme></tv>'''
        guide, aliases = S.parse_xmltv(xml)
        self.assertEqual(aliases['canal a'], 'a.es')
        ch = S.Channel('Canal A', 'Grupo', 'http://example.test/a', '', 'a.es')
        now = dt.datetime(2026, 10, 19, 14, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        current, later = S.now_next(ch, guide, aliases, now)
        self.assertEqual(current[2], 'Programa 1')
        self.assertEqual(later[0][2], 'Programa 2')

    def test_xtream_calls_and_urls(self):
        p = {'id':'test','name':'TDT','type':'xtream','server':'https://tv.example.test:443', 'username':'user+a','password':'pass/b','format':'m3u8','epg_url':''}
        def fake_http(url, *_args, **_kwargs):
            if 'get_live_categories' in url: return json.dumps([{'category_id':'7','category_name':'Noticias'}]).encode()
            if 'get_live_streams' in url: return json.dumps([{'stream_id':42, 'name':'24 Horas','stream_icon':'https://img.example.test/logo.png','epg_channel_id':'24.es','category_id':'7'}]).encode()
            raise AssertionError('unexpected URL')
        with patch.object(S, 'limited_http', side_effect=fake_http):
            out = S.load_channels(p)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].group, 'Noticias')
        self.assertTrue(out[0].url.endswith('/live/user%2Ba/pass%2Fb/42.m3u8'))
        self.assertIn('xmltv.php', S.profile_epg_url(p))

    def test_credentials_not_in_pseudo_id(self):
        channel=S.Channel('La 1', 'TDT', 'https://tv.example/live/username/secret/100.ts')
        self.assertEqual(channel.favorite_id, 'TDT|La 1')

    def test_http_user_agent_presets(self):
        self.assertEqual(S.network_user_agent({'user_agent':'Predeterminado'}), 'SYN/2.0')
        self.assertEqual(S.network_user_agent({'user_agent':'Personalizado','custom_ua':'Prueba/1'}), 'Prueba/1')

    def test_profile_validation(self):
        p = S.default_profile('/does/not/exist.m3u')
        with self.assertRaisesRegex(ValueError, 'No existe'): S.validate_profile(p)
        p.update(type='url', source='https://example.test/iptv.m3u')
        S.validate_profile(p)

    def test_local_file(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            fn = pathlib.Path(folder) / 'channels.m3u'
            fn.write_text('#EXTM3U\n#EXTINF:-1,Demo\nhttps://example.test/live.m3u8\n', encoding='utf-8')
            got=S.load_channels(S.default_profile(fn))
            self.assertEqual(got[0].name,'Demo')


if __name__=='__main__':
    unittest.main(verbosity=2)
