"""Pruebas de geometría exacta y visibilidad de Guía EPG, sin GTK."""
from pathlib import Path
import datetime as dt
import unittest
import syn

SOURCE=Path(__file__).with_name('syn.py').read_text(encoding='utf-8')
TZ=dt.timezone(dt.timedelta(hours=2))
BASE=dt.datetime(2026,10,19,20,31,tzinfo=TZ)

class AlignedEPGTests(unittest.TestCase):
    def test_program_2031_before_tick_2100_regression_from_screenshot(self):
        start=dt.datetime(2026,10,19,19,10,tzinfo=TZ)
        px=6.0
        program=syn.epg_x_at(BASE,start,px)
        tick=syn.epg_x_at(BASE.replace(hour=21,minute=0),start,px)
        self.assertEqual(program,486)
        self.assertEqual(tick,660)
        self.assertLess(program,tick)
        self.assertEqual(tick-program,29*6)

    def test_axis_and_block_x_match_for_multiple_timezones(self):
        for tz in [dt.timezone.utc, TZ, dt.timezone(dt.timedelta(hours=-4))]:
            start=dt.datetime(2026,10,19,19,10,tzinfo=tz)
            a=start+dt.timedelta(minutes=81)
            b=a+dt.timedelta(minutes=24)
            segment=syn.epg_geometry([(a,b,'Programa','')],start,5.3)[1]
            self.assertEqual(segment[0],syn.epg_x_at(a,start,5.3))
            self.assertEqual(segment[1],syn.epg_x_at(b,start,5.3)-segment[0])
            self.assertEqual(sum(item[1] for item in syn.epg_geometry([(a,b,'P','')],start,5.3)),round(300*5.3))

    def test_no_intrinsic_width_drift_or_separate_axis_scroll(self):
        self.assertIn('track = Gtk.Fixed()', SOURCE)
        self.assertIn('track.put(block, x, 0)', SOURCE)
        self.assertIn('self.guide_axis.set_draw_func(self._guide_draw_axis)', SOURCE)
        self.assertIn('scroll_x = self.guide_tracks_scroll.get_hadjustment().get_value()', SOURCE)
        self.assertNotIn('self.guide_clock_scroll',SOURCE)
        self.assertNotIn('cells.append(block)',SOURCE)

    def test_explicit_buttons_in_main_fullscreen_and_remote(self):
        self.assertIn("Gtk.Button(label=tr('▦ Guía EPG'))",SOURCE)
        self.assertIn("self.fs_guide_btn = Gtk.Button(label=tr('Guía EPG'))",SOURCE)
        self.assertIn("Gtk.Button(label=tr('▦  Abrir Guía EPG'))",SOURCE)

    def test_mpv_backend_unchanged(self):
        import hashlib
        backend=SOURCE[SOURCE.index('class NativeMpv:'):SOURCE.index('def epg_window_segments(')].strip()
        self.assertEqual(hashlib.sha256(backend.encode()).hexdigest(),'8cbdb7c3656ea37012bce18ca7a5852219ed00fd14a5ab021de41acf8b56cf1d')

if __name__=='__main__': unittest.main()
