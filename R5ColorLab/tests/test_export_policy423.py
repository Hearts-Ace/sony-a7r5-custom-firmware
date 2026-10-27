"""Export eligibility is checked independently of client controls."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import core
import export_policy423 as policy
import test_compression_workflow as fixtures


class ExportPolicyTests(unittest.TestCase):
    def project(self):
        return core.config(copy.deepcopy(core.presets()[0][:1]))

    def test_unselected_legacy_and_unknown_sources_rejected_but_clear_allowed(self):
        p = self.project()
        with self.assertRaises(ValueError): policy.validate(p, Path('/tmp'))
        for source in ({'kind': 'manual'}, {'kind': 'stock', 'id': 'invented'},
                       {'kind': 'compressed', 'job': '../secret', 'key': '0'*64}):
            p['export_sources'] = {'1': source}
            with self.assertRaises(ValueError): policy.validate(p, Path('/tmp'))
        for schema in ('r5-native-overwrite-config/2', 'r5-native-overwrite-config/3'):
            p['schema'] = schema
            with self.assertRaises(ValueError): policy.validate(p, Path('/tmp'))
        clear = core.config([])
        clear['export_sources'] = {}
        self.assertEqual(len(core.compile_config(policy.validate(clear, '/tmp')[0])[0]), 128)

    def test_each_stock_grid_exact_but_native_parameters_and_names_independent(self):
        from stock_grids import catalog
        self.assertTrue(catalog())
        for item in catalog():
            p = self.project()
            p['entries'][0]['grid_5x9x9'] = copy.deepcopy(item['grid_5x9x9'])
            p['entries'][0]['short_name'] = 'NEW'
            p['entries'][0]['block13'][0][0][0] += 1
            p['export_sources'] = {'1': {'kind': 'stock', 'id': item['id']}}
            cfg, receipts = policy.validate(p, '/tmp')
            self.assertEqual(receipts[0]['provenance'], item['provenance'])
            self.assertEqual(core.compiler.unpack(core.compiler.pack(cfg)), cfg)
            p['entries'][0]['grid_5x9x9']['coefficients'][0][0][0][0] += 1
            with self.assertRaises(ValueError): policy.validate(p, '/tmp')

    def test_compression_binding_rename_renumber_and_stale_sources(self):
        import grid_distillation as gd
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture, key, _, _ = fixtures.CompressionWorkflowTests().fixture(root)
            job = root / ('a'*32)
            fixture.rename(job)
            (job/'input_audit.json').write_text(json.dumps(dict(target_kind='lut',lut_sha256=core.sha((job/'input.cube').read_bytes()))))
            (job/'native_config.json').write_text(json.dumps(self.project()))
            p = gd.firmware_config(job, key, configuration_only=True)
            p['entries'][0].update(number=12, short_name='RENAME', full_name='New name')
            p['export_sources'] = {'12': dict(kind='compressed', job=job.name, key=key)}
            policy.validate(p, root)
            for field in policy.PARAMETERS:
                changed = copy.deepcopy(p)
                node = changed['entries'][0][field]
                if field == 'grid_5x9x9': node['coefficients'][0][0][0][0] += 1
                elif field == 'gamma_native_129': node[64] += 1
                elif field == 'block13': node[0][0][0] += 1
                else: node[0][0] += 1
                with self.subTest(field=field):
                    with self.assertRaises(ValueError): policy.validate(changed, root)
            with zipfile.ZipFile(io.BytesIO(gd.firmware_config(job, key))) as archive:
                project = json.loads(archive.read('native_config.json'))
                cfg, _ = policy.validate(project, root)
                self.assertEqual(core.compiler.pack(cfg), archive.read('R5NATIVE.BIN'))
            (job/'pc_compensation.json').write_text('changed')
            with self.assertRaises(ValueError): policy.validate(p, root)


if __name__ == '__main__': unittest.main()
