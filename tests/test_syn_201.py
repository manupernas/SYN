"""Regression checks for SYN 2.0.1, including Cast popup hover lifetime."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from synplus_layout import css, poll_chrome, hold_chrome_for_cast, reveal_controls

class Revealer:
    def __init__(self): self.state = False
    def set_reveal_child(self, state): self.state = bool(state)

class Window:
    _synplus_ui = True
    _synplus_in_fullscreen = False
    _synplus_mouse_over_video = False
    _synplus_reveal_until = 0.0
    _synplus_cast_popover_open = False
    _synplus_cast_popover = None
    def __init__(self):
        self._synplus_chrome_reveal = Revealer()
        self._synplus_gradient_reveal = Revealer()

class GtkStub:
    class PositionType:
        TOP = 'top'

class Pop:
    def __init__(self): self.callbacks = {}; self.position = None; self.dismissed = False
    def set_position(self, pos): self.position = pos
    def connect(self, signal, cb): self.callbacks[signal] = cb
    def popdown(self):
        self.dismissed = True
        self.callbacks['closed'](self)

class Tests(unittest.TestCase):
    def test_light_rail_follows_accent_and_theme(self):
        self.assertIn('alpha(#D65D0E,.08)', css('gruvbox-light','#D65D0E',False))
        self.assertIn('alpha(#5e81ac,.08)', css('nord-light','',False))
        self.assertIn('alpha(@accent_color,.08)', css('system','',False))
    def test_dark_rail_is_subtle_and_still_tinted(self):
        dark = css('dark','',True)
        self.assertIn('alpha(#76c2c2,.035)',dark)
        self.assertIn('alpha(#d79921,.035)', css('gruvbox-dark','',True))
        self.assertIn('alpha(#FF6600,.035)', css('system','#FF6600',True))
        self.assertNotIn('alpha(@accent_color,.08)', css('system','',True))
        # Only nav gets the softened RGB surface; channel sidebar remains original.
        self.assertIn('background-color:#141b24;',dark)
        self.assertIn('.synplus-sidebar { background-color:#18212b;',dark)
    def test_cast_menu_remains_visible_outside_player(self):
        w=Window(); p=Pop()
        hold_chrome_for_cast(w,p,GtkStub)
        self.assertEqual(p.position,'top')
        self.assertTrue(w._synplus_chrome_reveal.state)
        self.assertTrue(w._synplus_gradient_reveal.state)
        reveal_controls(w,False)
        self.assertTrue(w._synplus_chrome_reveal.state)
        p.popdown()
        self.assertFalse(w._synplus_chrome_reveal.state)
        self.assertFalse(w._synplus_gradient_reveal.state)
    def test_cast_fullscreen_and_next_popover(self):
        w=Window(); a=Pop(); b=Pop()
        hold_chrome_for_cast(w,a,GtkStub)
        hold_chrome_for_cast(w,b,GtkStub)
        self.assertTrue(a.dismissed)
        self.assertTrue(w._synplus_chrome_reveal.state)
        w._synplus_in_fullscreen=True
        poll_chrome(w)
        self.assertFalse(w._synplus_chrome_reveal.state)
        b.popdown()
        self.assertFalse(w._synplus_cast_popover_open)
    def test_version_and_cast_anchor(self):
        s=(ROOT/'syn.py').read_text(encoding='utf-8')
        self.assertIn('SYN_VERSION = "2.0.5"',s)
        self.assertIn('synplus_layout.hold_chrome_for_cast(self, pop, Gtk)',s)
        self.assertIn('self._syn_cast_call({\'action\':\'devices\'},done)',s)
        self.assertIn('self._syn_cast_play(d)',s)
        x=(ROOT/'com.mrseivane.Syn.metainfo.xml').read_text(encoding='utf-8')
        self.assertIn('release version="2.0.1"',x)

if __name__=='__main__': unittest.main()
