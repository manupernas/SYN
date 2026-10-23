"""Regression: compact wordmarks, true Flatpak desktop icon and lossless configuration."""
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parent.parent

def test_brand_logo_is_physically_bounded():
    src=(ROOT/'syn.py').read_text('utf-8')
    assert 'self.syn_wordmark.set_can_shrink(True)' in src
    assert 'self.syn_wordmark.set_size_request(206, 108)' in src
    assert 'self._syn_brand_band_spacer.set_size_request(-1, 122)' in src
    for name in ('logo_dark_ui.png','logo_light_ui.png'):
        data=(ROOT/'branding'/name).read_bytes()
        assert data[:8]==bytes.fromhex('89504e470d0a1a0a')
        assert struct.unpack('>II',data[16:24]) == (206,108)

def test_app_id_icon_and_launch():
    d=(ROOT/'com.mrseivane.Syn.desktop').read_text('utf-8')
    assert 'Icon=com.mrseivane.Syn' in d
    assert 'Exec=syn-flatpak' in d
    assert 'StartupWMClass=com.mrseivane.Syn' in d
    for sz in (16,24,32,48,64,96,128,256,512):
        p=ROOT/'icons'/f'{sz}x{sz}'/'apps/com.mrseivane.Syn.png'
        data=p.read_bytes()
        assert struct.unpack('>II',data[16:24])==(sz,sz)
