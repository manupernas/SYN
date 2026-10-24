"""Regresiones de SYN 3.8.2: logos URL, persistencia y geometría uniforme."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import syn_sources as src

# PNG minimal para verificar la firma; el codec GTK valida las imágenes
# reales cuando se cargan en la interfaz.
PNG = b'\x89PNG\r\n\x1a\n' + b'payload-example'
JPG = b'\xff\xd8\xff' + b'payload-example'
WEBP = b'RIFF\x12\x00\x00\x00WEBP' + b'payload-example'

class LogoUrlTests(unittest.TestCase):
    def setUp(self):
        self.profile = {'id': 'perfil123'}
        self.ch = src.Channel('LA 1','ES - TDT','https://tv.example/stream')

    def test_png_jpg_webp_magic(self):
        for raw, expected in [(PNG, '.png'), (JPG, '.jpg'), (WEBP, '.webp')]:
            self.assertEqual(src.custom_logo_type(raw), expected)

    def test_url_download_is_http_only_and_limited(self):
        with patch.object(src, 'limited_http', return_value=PNG) as get:
            data = src.download_custom_logo_url('https://example.org/logo?id=43')
            self.assertEqual(data, PNG)
            self.assertEqual(get.call_args.args[1], 8 * 1024 * 1024)
        for url in ['file:///etc/passwd','data:image/png;base64,xxx','javascript:alert(1)', '']:
            with self.assertRaises(ValueError):
                src.download_custom_logo_url(url)

    def test_invalid_content_rejected(self):
        with patch.object(src, 'limited_http', return_value=b'<html>error</html>'):
            with self.assertRaises(ValueError):
                src.download_custom_logo_url('https://example.org/bad.png')

    def test_url_download_stored_locally_without_url_in_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(src, 'APP_CONFIG', Path(directory)):
                with patch.object(src, 'limited_http', return_value=PNG):
                    output = src.install_custom_logo_url(self.profile, self.ch, 'https://logo.example.com/hello.png')
                self.assertEqual(output.read_bytes(), PNG)
                self.assertEqual(output, src.custom_logo_path(self.profile, self.ch))
                self.assertNotIn('logo.example.com', str(self.profile))
                src.reset_custom_logo(self.profile, self.ch)
                self.assertIsNone(src.custom_logo_path(self.profile, self.ch))

    def test_overrides_independent_across_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            p2 = {'id': 'perfil987'}
            with patch.object(src, 'APP_CONFIG', Path(directory)):
                one = src.install_custom_logo_bytes(self.profile, self.ch, PNG)
                two = src.install_custom_logo_bytes(p2, self.ch, JPG)
                self.assertNotEqual(one, two)
                self.assertEqual(one.suffix, '.png')
                self.assertEqual(two.suffix, '.jpg')

    def test_pills_are_uniform_all_views_with_context_menu(self):
        code = Path(__file__).with_name('syn.py').read_text()
        self.assertIn('width, height = 120, 46', code)
        self.assertIn("right_click.set_button(3)", code)
        self.assertIn('open_logo_context_menu(widget, c, x, y)', code)
        self.assertIn("Cambiar logo… (URL)", code)
        self.assertIn("sources.download_custom_logo_url(url, user_agent=agent)", code)
        self.assertIn('GdkPixbuf.InterpType.BILINEAR', code)

if __name__ == '__main__':
    unittest.main()
