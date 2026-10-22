import unittest
import numpy as np
import core
import white_balance as wb
from edit_color_pipeline import RuntimeColor
from edit_raw_front import itp_flatfield


class WhiteBalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = RuntimeColor.from_capture(core.CAPTURE, 4)

    def test_zero_preserves_measured_input_and_legacy_recipes(self):
        x = np.full((2, 9, 3), 2000, dtype=np.uint16)
        self.assertIs(wb.inputs(self.model, x, None), x)
        result = wb.render_pairs(self.model, {'input': x}, {})
        np.testing.assert_array_equal(result, self.model.color_only(x)[:, 4])

    def test_sensor_stage_delta_and_fixed_target(self):
        codes = np.array([[1000, 2000, 3000], [7000, 5000, 6000]])
        measured = np.full((2, 9, 3), 6000, dtype=np.uint16)
        original = measured.copy()
        target = np.array([[.1, .2, .3], [.4, .5, .6]])
        frozen_target = target.copy()
        value = dict(temperature_shift=200, tint=10)
        before = itp_flatfield(codes, self.model.raw, self.model.settings).astype(float)
        after = itp_flatfield(codes, self.model.raw, wb.settings_for(self.model, value)).astype(float)
        expected = np.clip(measured + (after-before)[:, None, :], 0, 16383).astype('<u2')
        np.testing.assert_array_equal(wb.inputs(self.model, measured, codes, value), expected)
        np.testing.assert_array_equal(measured, original)
        np.testing.assert_array_equal(target, frozen_target)

    def test_photo_tint_direction_and_identity(self):
        np.testing.assert_array_equal(wb.photo_gains(self.model, [2.5, 1, 1.8], wb.ZERO), np.ones(3))
        ratio = wb.photo_gains(self.model, [2.5, 1, 1.8], dict(temperature_shift=0, tint=20))
        self.assertGreater(ratio[0], 1)
        self.assertGreater(ratio[2], 1)
        self.assertAlmostEqual(ratio[1], 1)

    def test_validation_and_numpy_optimizer_parameters(self):
        self.assertEqual(wb.validate(dict(temperature_shift=np.float64(200), tint=np.float64(10)))['tint'], 10)
        for value in [True, float('nan'), 1001, '100']:
            with self.assertRaises(ValueError):
                wb.validate(dict(temperature_shift=value, tint=0))
        self.assertFalse(wb.report(wb.ZERO, True)['camera_apply_allowed'])


if __name__ == '__main__':
    unittest.main()
