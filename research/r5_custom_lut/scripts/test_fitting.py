"""Numerical anchors, known-transform recovery and corrupt-file rejection.

Uses the independently compiled C reader when --c-reader is supplied. No camera.
"""
from pathlib import Path
import argparse
import json
import struct
import subprocess
import tempfile
import unittest
import zlib

from fit_native_proxy import Cube, dot, fit, matrix, metrics, np, predict, rgb_to_xyz, slog3
from look_recipe import HEADER, decode, encode

C_READER = None


def metadata():
    return dict(schema='r5-look-proxy/1', camera_apply_allowed=False,
        model='neutral-matrix-then-shared-curve-hypothesis',
        cc1_policy='preserve-not-fitted',
        curve_encoding='explicit-float-axis-NOT-CP-gamma')


def repair_crc(raw):
    struct.pack_into('<I', raw, 20, zlib.crc32(raw[32:]))
    return bytes(raw)


class NumericalTests(unittest.TestCase):
    def test_log_anchors_and_neutral_gamut(self):
        np.testing.assert_allclose(slog3(np.array([0, .01125, .18])),
                                   np.array([95, 171.2102946929, 420])/1023, atol=1e-12)
        for gamut in ('linear-bt709', 'sgamut3', 'sgamut3cine'):
            np.testing.assert_allclose(np.einsum('ij,j->i', rgb_to_xyz(gamut), np.ones(3)),
                np.array([.3127/.3290, 1, (1-.3127-.3290)/.3290]), atol=1e-12)

    def test_cube_order_domain_and_interpolation(self):
        # Non-unit domain and an affine transform: exact off-grid answer.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'identity.cube'
            rows = ['TITLE "fixture"', 'LUT_3D_SIZE 2',
                    'DOMAIN_MIN -1 -1 -1', 'DOMAIN_MAX 1 1 1']
            for b in (0, 1):
                for g in (0, 1):
                    for r in (0, 1):
                        rows.append(f'{r} {g} {b}')
            path.write_text('\n'.join(rows))
            cube = Cube(path)
            np.testing.assert_allclose(cube.sample(np.array([[.2, -.4, .8]])), [[.6, .3, .9]])
            path.write_text('\n'.join(rows[:-1]))
            with self.assertRaises(ValueError): Cube(path)

    def test_known_matrix_and_curve_recovery(self):
        rng = np.random.default_rng(94)
        train, holdout = rng.random((3000, 3)), rng.random((2048, 3))
        q_expected = np.array([-100, -80, -70, -110, -90, -60])
        # An independently defined mixing matrix with row sums one.
        expected_m = np.array([[844,100,80], [70,844,110], [90,60,874]])/1024
        np.testing.assert_allclose(matrix(q_expected), expected_m)
        target = np.sqrt(dot(train, expected_m.T))
        q, axis, curve, _ = fit(train, target, 1., iterations=24)
        actual = predict(holdout, q, axis, curve)
        expected = np.sqrt(dot(holdout, expected_m.T))
        self.assertLess(metrics(actual, expected)['rgb_mae'], .002)
        self.assertLess(np.max(np.abs(q-q_expected)), 5)


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.raw = encode(metadata(), [1,-2,3,-4,5,-6],
                          np.linspace(0,1,129).tolist(), np.linspace(0,1,129).tolist())

    def reject(self, raw):
        with self.assertRaises((ValueError, UnicodeError, json.JSONDecodeError)):
            decode(raw)
        if C_READER:
            with tempfile.TemporaryDirectory() as folder:
                file = Path(folder)/'bad.r5lookdev'
                file.write_bytes(raw)
                p = subprocess.run([C_READER, str(file)], capture_output=True)
                self.assertEqual(p.returncode, 1, p.stderr.decode())

    def test_valid_roundtrip_and_c(self):
        self.assertEqual(decode(self.raw)['q'], [1,-2,3,-4,5,-6])
        if C_READER:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'good.r5lookdev'
                path.write_bytes(self.raw)
                out = subprocess.check_output([C_READER, str(path)])
                result = json.loads(out)
                self.assertTrue(result['structural_read_ok'])
                self.assertFalse(result['camera_apply_allowed'])
                self.assertEqual(result['matrix_q10'], decode(self.raw)['q'])

    def test_every_truncation(self):
        # Python validates all truncation boundaries. Representative C cases
        # cover header/section/data boundaries without spawning 1k processes.
        for at in range(len(self.raw)):
            with self.assertRaises(ValueError): decode(self.raw[:at])
        for at in (0, 8, 31, 32, 39, 100, len(self.raw)-1):
            self.reject(self.raw[:at])

    def test_corruption_and_semantically_bad_binary(self):
        mutated = bytearray(self.raw); mutated[-1] ^= 1
        self.reject(bytes(mutated))
        mutated = bytearray(self.raw); mutated[12] = 0
        self.reject(bytes(mutated))  # live/applicable flag forbidden
        mutated = bytearray(self.raw); mutated[24] = 1
        self.reject(bytes(mutated))
        mutated = bytearray(self.raw); mutated.extend(b'x')
        self.reject(bytes(mutated))
        positions, at = {}, HEADER.size
        while at < len(self.raw):
            tag, length = struct.unpack_from('<4sI', self.raw, at)
            positions[tag] = at
            at += 8+length
        for tag, value in ((b'AXIS', float('nan')), (b'CURV', 1.1), (b'CURV', -1)):
            mutated = bytearray(self.raw)
            struct.pack_into('<f', mutated, positions[tag]+8+40, value)
            self.reject(repair_crc(mutated))  # valid CRC, invalid numeric payload
        mutated = bytearray(self.raw)
        struct.pack_into('<h', mutated, positions[b'B13Q']+8, 4097)
        self.reject(repair_crc(mutated))
        mutated = bytearray(self.raw)
        mutated[positions[b'CURV']:positions[b'CURV']+4] = b'AXIS'
        self.reject(repair_crc(mutated))  # duplicate section with valid CRC
        mutated = bytearray(self.raw)
        struct.pack_into('<I', mutated, positions[b'AXIS']+4, 0xffffffff)
        self.reject(repair_crc(mutated))  # section length overflow


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--c-reader')
    args, remainder = parser.parse_known_args()
    C_READER = args.c_reader
    unittest.main(argv=[__file__, *remainder])
