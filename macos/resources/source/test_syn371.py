"""Regresiones de parrilla SYN 3.7.3 (sin depender de GTK)."""
import datetime as dt
from pathlib import Path
import unittest
import syn

SRC = Path(__file__).with_name('syn.py').read_text(encoding='utf-8')
BASE = dt.datetime(2026, 10, 19, 21, 32, tzinfo=dt.timezone(dt.timedelta(hours=2)))

class EquilibrioTests(unittest.TestCase):
    def test_past_programming_visible_at_left(self):
        start = syn.epg_initial_start(BASE)
        self.assertEqual(start, dt.datetime(2026, 10, 19, 20, 2, tzinfo=BASE.tzinfo))
        self.assertEqual((BASE-start).total_seconds(), 90*60)

    def test_now_with_past_programming_at_45_percent(self):
        for width in (450, 760, 980, 1400, 2200):
            zoom = syn.epg_minutes_scale(width)
            position = 90*zoom
            self.assertAlmostEqual(position / width, 0.45, delta=.015)
            self.assertGreater(position / width, 0.40)

    def test_axis_half_hour_ticks_and_total_duration(self):
        start = syn.epg_initial_start(BASE)
        ticks = syn.epg_axis_sections(start)
        self.assertEqual(sum(length for _, length in ticks), 300)
        labelled = [when for when, _ in ticks if when is not None]
        self.assertGreaterEqual(len(labelled), 8)
        self.assertTrue(all(t.minute in (0, 30) and t.second == 0 for t in labelled))
        self.assertEqual(labelled[0].strftime('%H:%M'), '20:30')

    def test_epg_blocks_still_preserve_actual_durations(self):
        start = syn.epg_initial_start(BASE)
        t1 = start + dt.timedelta(minutes=12)
        t2 = t1 + dt.timedelta(minutes=80)
        seg = syn.epg_window_segments([(t1, t2, 'Película', 'Estreno')], start)
        self.assertEqual(sum((b-a).total_seconds() for a,b,*_ in seg), 300*60)
        self.assertEqual([x[4] for x in seg], [False, True, False])

    def test_previous_and_current_programmes_fill_left_half(self):
        start = syn.epg_initial_start(BASE)
        programmes = [
            (BASE - dt.timedelta(minutes=85), BASE - dt.timedelta(minutes=30), 'Anterior', ''),
            (BASE - dt.timedelta(minutes=30), BASE + dt.timedelta(minutes=35), 'Actual', ''),
            (BASE + dt.timedelta(minutes=35), BASE + dt.timedelta(minutes=90), 'Siguiente', ''),
        ]
        seg = syn.epg_window_segments(programmes, start)
        previous = [x for x in seg if x[4] and x[2] == 'Anterior'][0]
        current = [x for x in seg if x[4] and x[2] == 'Actual'][0]
        self.assertLess((previous[0] - start).total_seconds(), (BASE - start).total_seconds())
        self.assertLess((current[0] - start).total_seconds(), (BASE - start).total_seconds())
        self.assertEqual((BASE - start).total_seconds() / 60, 90)


    def test_compact_columns_and_gtk4_resize_signal(self):
        self.assertIn('set_size_request(GUIDE_CATEGORIES_WIDTH, -1)', SRC)
        self.assertIn('set_size_request(GUIDE_CHANNEL_WIDTH, -1)', SRC)
        self.assertIn("self.guide_width_probe.connect('resize'", SRC)
        self.assertNotIn("connect('notify::width'", SRC)

    def test_mpv_backend_not_touched(self):
        from hashlib import sha256
        backend = SRC[SRC.index('class NativeMpv:'):SRC.index('def epg_window_segments(')].strip()
        self.assertEqual(sha256(backend.encode()).hexdigest(),
                         '8cbdb7c3656ea37012bce18ca7a5852219ed00fd14a5ab021de41acf8b56cf1d')

if __name__ == '__main__':
    unittest.main()
