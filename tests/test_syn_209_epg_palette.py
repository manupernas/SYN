"""SYN 2.0.9: EPG palette and stable per-programme colour regression tests."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from syn_epg_pop import (
    COLORS, contrast_against_white, epg_gradient_css,
    epg_programme_color_index, epg_programme_color_indices,
)

ROOT = Path(__file__).resolve().parents[1]


class EPGPalette209Tests(unittest.TestCase):
    def test_ten_contrasting_pastels(self):
        self.assertEqual(len(COLORS), 10)
        for left, right in COLORS:
            self.assertGreaterEqual(contrast_against_white(left), 4.5, left)
            self.assertGreaterEqual(contrast_against_white(right), 4.5, right)

    def test_programme_colours_advance_within_same_channel(self):
        palette = [epg_programme_color_index('News|Channel A', n) for n in range(24)]
        self.assertEqual(len(set(palette[:10])), 10)
        self.assertEqual(palette[0], palette[10])
        self.assertTrue(all(a != b for a, b in zip(palette, palette[1:])))
        self.assertEqual(palette, [epg_programme_color_index('News|Channel A', n) for n in range(24)])

    def test_clipped_programme_does_not_change_colour_on_scroll(self):
        t0 = datetime(2026, 11, 12, 10, tzinfo=timezone.utc)
        programmes = [
            (t0, t0 + timedelta(minutes=30), 'Morning', ''),
            (t0 + timedelta(minutes=30), t0 + timedelta(minutes=60), 'Midday', ''),
            (t0 + timedelta(minutes=60), t0 + timedelta(minutes=90), 'Afternoon', ''),
        ]
        def block(start, title, available=True):
            return (0, 120, start, start + timedelta(minutes=15), title, '', available)
        geometry_a = [
            block(t0 + timedelta(minutes=10), 'Morning'),
            block(t0 + timedelta(minutes=30), 'Midday'),
            block(t0 + timedelta(minutes=45), 'Missing', False),
            block(t0 + timedelta(minutes=60), 'Afternoon'),
        ]
        geometry_b = [
            block(t0 + timedelta(minutes=25), 'Morning'),
            block(t0 + timedelta(minutes=40), 'Midday'),
            block(t0 + timedelta(minutes=75), 'Afternoon'),
        ]
        colours_a = epg_programme_color_indices('News|Channel A', programmes, geometry_a)
        colours_b = epg_programme_color_indices('News|Channel A', programmes, geometry_b)
        self.assertEqual(colours_a[0], colours_b[0])
        self.assertEqual(colours_a[1], colours_b[1])
        self.assertIsNone(colours_a[2])
        self.assertEqual(colours_a[3], colours_b[2])
        self.assertNotEqual(colours_a[0], colours_a[1])
        self.assertNotEqual(colours_a[1], colours_a[3])

    def test_css_has_white_labels_and_all_gradient_classes(self):
        css = epg_gradient_css()
        self.assertIn('color: #FFFFFF', css)
        self.assertEqual(css.count('linear-gradient(to right,'), 10)
        for idx in range(10):
            self.assertIn(f'window.iptv-tv .syn-guide-program-{idx}', css)

    def test_real_guide_uses_colour_from_programme_not_channel(self):
        src = (ROOT / 'syn.py').read_text(encoding='utf-8')
        self.assertIn('programme_colours = epg_programme_color_indices(', src)
        self.assertIn('channel.favorite_id, programmes, guide_segments)', src)
        self.assertIn("block.add_css_class('syn-guide-program-' + str(colour_index))", src)
        self.assertNotIn("str(sum(map(ord,channel.name)) % 6)", src)
        self.assertIn("block.add_css_class('syn-guide-gap')", src)
        self.assertIn("block.add_css_class('syn-guide-current')", src)


if __name__ == '__main__':
    unittest.main()
