"""Independent file-format and export-contract checks for firmware 4.23."""
import copy
import json
import struct
import unittest
import zlib
import core


class CustomFilter423Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = core.presets()[0]

    def test_sorted_roundtrip_all_slots_utf8_and_required_grid_plane_order(self):
        entries = copy.deepcopy(self.entries)
        entries[0]['short_name'] = '测试一'
        entries[0]['full_name'] = '独立配置的完整名称'
        entries[0]['grid_5x9x9']['coefficients'][2][4][8][8] = -64
        entries[11]['grid_5x9x9']['coefficients'][0][0][0][0] = 63
        binary, path, firmware, version = core.compile_config(core.config(entries[::-1]))
        self.assertEqual((firmware, version, len(binary)), ('4.23', 4, 29552))
        self.assertEqual(binary[:8], b'R5CUST4\0')
        self.assertEqual(binary[128+1232+1214], 192)
        self.assertEqual(binary[128+11*2452+1232], 63)
        self.assertEqual(core.compiler.unpack(binary), core.config(entries))
        self.assertEqual(path, core.COMPILER_PATH)

    def test_empty_set_canonical_clear_and_all_zero_grid(self):
        clear = core.compiler.pack(core.config([]))
        self.assertEqual(len(clear), 128)
        self.assertEqual(core.compiler.unpack(clear)['entries'], [])
        binary = core.compiler.pack(core.config(self.entries[:1]))
        self.assertEqual(binary[128+1232:128+2447], bytes(1215))
        self.assertNotIn('enabled', self.entries[0]['grid_5x9x9'])

    def test_legacy_schemas_switches_missing_grid_and_names_rejected(self):
        for schema in ['r5-native-overwrite-config/2', 'r5-native-overwrite-config/3']:
            value = core.config(copy.deepcopy(self.entries[:1]))
            value['schema'] = schema
            with self.assertRaises(ValueError): core.compile_config(value)
        for key in ['compensation_grid_enabled', 'additional_compensation_matrix_enabled']:
            value = core.config(copy.deepcopy(self.entries[:1])); value[key] = False
            with self.assertRaises(ValueError): core.compile_config(value)
        for key in ['grid_5x9x9', 'short_name', 'full_name']:
            value = core.config(copy.deepcopy(self.entries[:1])); del value['entries'][0][key]
            with self.assertRaises(ValueError): core.compile_config(value)
        value = core.config(copy.deepcopy(self.entries[:1]))
        value['entries'][0]['grid_5x9x9']['enabled'] = True
        with self.assertRaises(ValueError): core.compile_config(value)

    def test_name_byte_boundaries_and_control_characters(self):
        for key, limit in [('short_name', 23), ('full_name', 63)]:
            entry = copy.deepcopy(self.entries[0]); entry[key] = 'a'*limit
            core.compiler.pack(core.config([entry]))
            for bad in ['', 'a'*(limit+1), 'a\0b', 'a\nb', '\x80', '\ud800']:
                entry[key] = bad
                with self.subTest(key=key, bad=repr(bad)):
                    with self.assertRaises(ValueError): core.compiler.pack(core.config([entry]))

    def test_grid_dimensions_types_and_signed7_limits(self):
        for bad in [-65, 64, True, 1.0, '0']:
            entry = copy.deepcopy(self.entries[0])
            entry['grid_5x9x9']['coefficients'][0][0][0][0] = bad
            with self.assertRaises(ValueError): core.compiler.pack(core.config([entry]))
        entry = copy.deepcopy(self.entries[0]); entry['grid_5x9x9']['coefficients'][0].pop()
        with self.assertRaises(ValueError): core.compiler.pack(core.config([entry]))

    def test_repaired_crc_cannot_hide_padding_baseline_order_or_invalid_utf8(self):
        original = core.compiler.pack(core.config(self.entries[:2]))
        for offset, replacement in [(28, b'\x01'), (32, b'X'), (48, b'X'), (80, b'X'),
                                    (116, b'\x01'), (128+2447, b'\x01'),
                                    (128+4, b'\xc0\x80'), (128+7, b'X')]:
            bad = bytearray(original); bad[offset:offset+len(replacement)] = replacement
            struct.pack_into('<I', bad, 112, 0)
            struct.pack_into('<I', bad, 112, zlib.crc32(bad))
            with self.subTest(offset=offset):
                with self.assertRaises(ValueError): core.compiler.unpack(bytes(bad))
        bad = bytearray(original)
        bad[128:128+2452], bad[128+2452:] = bad[128+2452:], bad[128:128+2452]
        struct.pack_into('<I', bad, 112, 0);struct.pack_into('<I', bad, 112, zlib.crc32(bad))
        with self.assertRaises(ValueError): core.compiler.unpack(bytes(bad))


if __name__ == '__main__': unittest.main()
