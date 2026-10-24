"""SYN 2.0.6: Ubuntu 6,720-channel Beta2 regression markers."""
from pathlib import Path
import ast
ROOT = Path(__file__).resolve().parents[1]


def test_incremental_channel_rows_and_lazy_popup():
    s=(ROOT/'syn.py').read_text('utf-8')
    ast.parse(s)
    assert 'SYN_VERSION = "2.0.7"' in s
    assert 'GLib.timeout_add(18, add_batch)' in s
    assert 'self._syn_beta_list_token' in s
    assert 'self._syn_beta_quick_token' in s
    assert "popover.connect('notify::visible'" in s


def test_provider_logo_cpu_decode_is_background_and_texture_is_gtk():
    s=(ROOT/'syn.py').read_text('utf-8')
    assert 'def _prepare_logo_pixbuf(self, path):' in s
    assert 'self._prepare_logo_pixbuf(path)' in s
    assert 'GLib.idle_add(self._publish_logo_pixbuf, pix, widget, pill)' in s
    assert 'Gdk.Texture.new_for_pixbuf(pix)' in s


def test_illustrations_and_real_logos_share_one_overlay():
    s=(ROOT/'syn.py').read_text('utf-8')
    assert 'pill = Gtk.Overlay()' in s
    assert 'pill.set_child(pic)' in s
    assert 'pill.add_overlay(picture)' in s
    assert 'pill.set_measure_overlay(picture, False)' in s
    assert 'pill.set_clip_overlay(picture, True)' in s
    assert 'pic.set_draw_func(self._draw_channel_logo_or_art)' in s
    assert "pill.add_css_class('syn-art-fullbleed')" in s


def test_deb_depends_on_cairo_and_release_preserves_prior_theming():
    native=(ROOT/'packaging/build-native.sh').read_text('utf-8')
    assert 'python3-gi-cairo' in native
    assert 'libmpv2' in native
    src=(ROOT/'synplus_layout.py').read_text('utf-8')
    assert 'synplus-video-column' in src
    meta=(ROOT/'com.mrseivane.Syn.metainfo.xml').read_text('utf-8')
    assert '<release version="2.0.6"' in meta
