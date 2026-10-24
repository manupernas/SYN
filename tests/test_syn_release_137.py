"""SYN 1.3.7 packaging/brand checks, no GTK display required."""
import hashlib
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent.parent
APP_ID='com.mrseivane.Syn'

def test_source_version_and_theme_fixes():
    source=(ROOT/'syn.py').read_text('utf-8')
    assert 'SYN_VERSION = "2.0.5"' in source
    assert 'def syn_popup_theme_css' in source
    assert 'def epg_axis_ink' in source
    assert 'self.syn_wordmark.set_size_request(206, 108)' in source
    assert 'self._syn_brand_band_spacer.set_size_request(-1, 122)' in source

def test_all_nine_hicolor_icons_match_approved_icono_3_art():
    for size in (16,24,32,48,64,96,128,256,512):
        p=ROOT/'icons'/f'{size}x{size}'/'apps'/f'{APP_ID}.png'
        data=p.read_bytes()
        assert data[:8] == bytes.fromhex('89504e470d0a1a0a')
        assert data[12:16] == b'IHDR'
        assert struct.unpack('>II',data[16:24]) == (size,size)
    p=ROOT/'icons/512x512/apps'/f'{APP_ID}.png'
    assert hashlib.sha256(p.read_bytes()).hexdigest() == '59b880479a8d2a31e8528b153d6e497e904ba3171394309cde200a3934161150'

def test_branding_and_software_center_metadata():
    for name in ('logo_light_ui.png','logo_dark_ui.png','icono_3.png','icono_header_ui.png'):
        assert (ROOT/'branding'/name).stat().st_size > 100
    doc=ET.parse(ROOT/f'{APP_ID}.metainfo.xml').getroot()
    assert doc.findtext('id') == APP_ID
    assert doc.find('icon').attrib['type'] == 'stock'
    assert doc.findtext('icon') == APP_ID
    assert doc.findtext('launchable') == f'{APP_ID}.desktop'
    assert any(x.attrib.get('version')=='1.3.7' for x in doc.findall('./releases/release'))
    desktop=(ROOT/f'{APP_ID}.desktop').read_text('utf-8')
    assert f'Icon={APP_ID}' in desktop
    assert 'Exec=syn-flatpak' in desktop
    for pack in ('packaging/stage-native.sh','com.mrseivane.Syn.yml'):
        text=(ROOT/pack).read_text('utf-8')
        assert 'icons' in text and 'metainfo' in text

def test_readme_showcases_new_brand():
    text=(ROOT/'README.md').read_text('utf-8')
    # Check the headline against the actual current version, not a stale
    # literal from a previous release. This must remain valid in 2.0.2+.
    import re
    source = (ROOT/'syn.py').read_text('utf-8')
    version = re.search(r'^SYN_VERSION\s*=\s*"([^"]+)"', source, re.M)
    assert version is not None
    assert f'**SYN {version.group(1)}**' in text
    for f in ('syn-readme-banner.png','syn-readme-banner-dark.png','syn-readme-banner-light.png'):
        assert (ROOT/'docs/brand'/f).stat().st_size > 100
        assert f in text or f == 'syn-readme-banner.png' and f in text
    assert (ROOT/'docs/RELEASE_1.3.7.md').stat().st_size > 100
