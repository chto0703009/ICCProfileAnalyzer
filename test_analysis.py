# Copyright (c) 2026 Christer Törnkvist.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run with: python -m unittest"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import app
from colour_math import delta_e00, xyz_to_lab
from profile_analysis import measurement_file

SRGB = Path('/System/Library/ColorSync/Profiles/sRGB Profile.icc')
GRAY = Path('/System/Library/ColorSync/Profiles/Generic Gray Profile.icc')
CGATS = ('DESCRIPTOR "{}"\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B LAB_L LAB_A LAB_B\nEND_DATA_FORMAT\n'
         'BEGIN_DATA\n1 100 100 100 100 0 0\n2 0 0 0 0 0 0\nEND_DATA\n')


class ColourMath(unittest.TestCase):
    def test_delta_e00_sharma(self):
        for a, b, expected in [((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
                               ((50, 2.49, -0.001), (50, -2.49, 0.0011), 7.2195),
                               ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082)]:
            self.assertAlmostEqual(float(delta_e00(a, b)), expected, places=4)

    def test_d50_white(self):
        for value, expected in zip(xyz_to_lab([96.42, 100, 82.49]), (100, 0, 0)):
            self.assertAlmostEqual(value, expected)


class MeasurementFile(unittest.TestCase):
    def read(self, content):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'm.txt'
            path.write_bytes(content)
            return measurement_file(path)

    def test_latin1(self):
        self.assertEqual(len(self.read(CGATS.format('Hahnemühle 2°').encode('latin-1'))['rgb']), 2)

    def test_not_cgats(self):
        with self.assertRaisesRegex(ValueError, 'CGATS'):
            self.read(b'hej\n')


@unittest.skipUnless(SRGB.exists() and GRAY.exists(), 'macOS system profiles required')
class Calculate(unittest.TestCase):
    def test_all_modes(self):
        for mode in app.MODES:
            profile = app.calculate([SRGB], None, '', mode)[0][0]
            self.assertNotIn('error', profile)
            self.assertGreater(profile['volume'][3], 0)

    def test_gray_has_no_volume(self):
        profile = app.calculate([GRAY], None, '', app.MODES[0])[0][0]
        self.assertEqual(profile['volume'], {3: None, 1: None})


if __name__ == '__main__':
    unittest.main()
