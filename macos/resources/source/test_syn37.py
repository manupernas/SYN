"""SYN 3.7: EPG layout must represent real times and missing intervals."""
import ast
import datetime as dt
from pathlib import Path
import unittest
import syn

SOURCE = (Path(__file__).resolve().parent / 'syn.py').read_text(encoding='utf-8')
TZ = dt.timezone(dt.timedelta(hours=2))
BASE = dt.datetime(2026, 10, 19, 20, 0, tzinfo=TZ)

def at(minutes):
    return BASE + dt.timedelta(minutes=minutes)

class EPGLayoutTests(unittest.TestCase):
    def test_early_late_and_gaps(self):
        result = syn.epg_window_segments([
            (at(-30), at(20), 'Anterior', 'd1'),
            (at(50), at(120), 'Siguiente', 'd2'),
            (at(250), at(350), 'Final', 'd3')], BASE)
        self.assertEqual([(int((a-BASE).total_seconds()/60), int((b-BASE).total_seconds()/60), ok)
                          for a,b,_,_,ok in result],
                         [(0,20,True),(20,50,False),(50,120,True),
                          (120,250,False),(250,300,True)])
    def test_no_programmes_returns_placeholder(self):
        self.assertEqual(syn.epg_window_segments([], BASE),
                         [(BASE, at(300),'Programación no disponible','',False)])
    def test_clamp_overlaps_and_discard_nonpositive(self):
        result = syn.epg_window_segments([
            (at(10), at(70), 'Uno',''),
            (at(60), at(80), 'Dos',''),
            (at(70), at(70), 'Malo','')], BASE)
        self.assertEqual([r[2] for r in result],
                         ['Programación no disponible','Uno','Dos','Programación no disponible'])
        self.assertEqual(result[2][0],at(70))
    def test_floor_local_hour(self):
        self.assertEqual(syn.epg_floor_hour(at(73)), at(60))
        self.assertEqual(syn.epg_time_label(at(0),at(30)), '20:00–20:30')
    def test_fullscreen_overlay_no_mpv_recreation(self):
        ast.parse(SOURCE)
        self.assertIn('self.overlay.add_overlay(self.guide_surface)', SOURCE)
        self.assertIn('self.guide_tracks_scroll.set_policy', SOURCE)
        self.assertIn('self.guide_names_scroll.set_vadjustment', SOURCE)
        self.assertIn('page_size = 24', SOURCE)
        self.assertIn('def set_guide_open', SOURCE)
        self.assertIn('if key == Gdk.KEY_Escape and self.guide_open:',SOURCE)
    def test_mpv_code_exactly_unchanged(self):
        from hashlib import sha256
        backend = SOURCE[SOURCE.index('class NativeMpv:'):SOURCE.index('def epg_window_segments(')].strip()
        self.assertEqual(sha256(backend.encode()).hexdigest(),
                         '8cbdb7c3656ea37012bce18ca7a5852219ed00fd14a5ab021de41acf8b56cf1d')

if __name__=='__main__': unittest.main()
