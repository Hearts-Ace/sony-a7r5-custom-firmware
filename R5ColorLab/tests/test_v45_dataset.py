import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import core,baseline,chart_datasets,chart_target,v4_dataset,v45_dataset,anchor_dataset
from edit_color_pipeline import RuntimeColor
from edit_raw_front import itp_flatfield

class V45Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arrays,cls.audit=core.measured_inputs()
        cls.model=RuntimeColor.from_capture(*baseline.resolve(v45_dataset.DATASET_ID))

    def test_default_matches_physical_5300k_front_and_rejects_tamper(self):
        a=self.arrays
        self.assertEqual(self.audit['dataset_id'],v45_dataset.DATASET_ID)
        self.assertTrue(self.audit['edit_validated'])
        self.assertFalse(self.audit['edit_capture'])
        self.assertFalse(self.audit['frontend_approximate'])
        self.assertTrue(v45_dataset.runtime_validation()['comparisons']['simulated_front_vs_actual_all9']['exact'])
        np.testing.assert_array_equal(a['input'],np.repeat(self.model.sscs(
            itp_flatfield(a['sensor_codes'],self.model.raw,self.model.settings))[:,None,:],9,axis=1))
        self.assertTrue(anchor_dataset.validate(a)['passed'])
        changed=copy.deepcopy(a);changed['input'][100,4,0]+=1
        with self.assertRaises(ValueError):anchor_dataset.validate(changed)
        gray=self.model.color_only(a['input'][:256])[:,4]
        np.testing.assert_array_equal(gray[:,0],gray[:,1])
        np.testing.assert_array_equal(gray[:,1],gray[:,2])

    def test_no_duplicate_leak_and_all_required_tracks(self):
        a=self.arrays
        _,g=np.unique(a['sensor_codes'],axis=0,return_inverse=True)
        sets=[set(g[a['split']==s]) for s in ('train','valid','test')]
        for i in range(3):
            for j in range(i):self.assertFalse(sets[i]&sets[j])
        import precision_sampling
        mandatory=np.isin(a['sample_kind'],precision_sampling.TONAL)|(a['anchor_index']>=0)
        self.assertTrue(np.all(a['split'][mandatory]=='train'))
        old,_=v4_dataset.load()
        np.testing.assert_array_equal(a['reference_sensor'],old['sensor'])

    def test_legacy_upload_identity_is_preserved_and_conflicts_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            self.assertEqual(chart_datasets.upload_version(folder),v4_dataset.DATASET_ID)
            with self.assertRaises(ValueError):chart_datasets.upload_version(folder,v45_dataset.DATASET_ID)
            (folder/'audit.json').write_text(json.dumps(dict(schema=v45_dataset.DATASET_ID)))
            self.assertEqual(chart_datasets.upload_version(folder),v45_dataset.DATASET_ID)
            with self.assertRaises(ValueError):chart_datasets.upload_version(folder,v4_dataset.DATASET_ID)

    def test_real_target_preparation_and_version_bound_fit(self):
        # New 16-bit reference is a reproducible synthetic smoke target only.
        data=(v45_dataset.FOLDER/v45_dataset.metadata()['reference_file']).read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=folder/'source.bin';source.write_bytes(data)
            output=folder/'job';output.mkdir()
            chart_target.prepare(data,output,source_path=source,dataset_id=v45_dataset.DATASET_ID)
            audit=json.loads((output/'input_audit.json').read_text())
            self.assertEqual(audit['dataset_id'],v45_dataset.DATASET_ID)
            with np.load(output/'pairs.npz') as p:
                np.testing.assert_array_equal(p['input'],self.arrays['input'])
                self.assertEqual(p['0_target'].shape,(99372,3))
            import server
            upload=folder/'chart_uploads'/('e'*32);upload.mkdir(parents=True)
            (upload/'source.bin').write_bytes(data)
            (upload/'audit.json').write_text(json.dumps(dict(schema=v45_dataset.DATASET_ID)))
            body=dict(target_kind='chart-image',dataset_id=v45_dataset.DATASET_ID,target_id='e'*32,
                number=1,evaluations=1,short_name='test',full_name='test')
            with patch.object(core,'HERE',folder):
                self.assertEqual(server.validate_fit(body)['dataset_id'],v45_dataset.DATASET_ID)
                body['dataset_id']=v4_dataset.DATASET_ID
                with self.assertRaisesRegex(ValueError,'版本不符'):server.validate_fit(body)

    def test_new_and_historical_baselines_remain_bound(self):
        for identifier in baseline.PT_IDS:
            capture,context=baseline.resolve(identifier)
            with tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);(folder/'fit').mkdir()
                source=dict(dataset_id=identifier,context=context,capture_report_sha256=core.sha((capture/'report.json').read_bytes()))
                (folder/'fit/recipe.json').write_text(json.dumps(dict(source=source)))
                self.assertEqual(baseline.for_job(folder),(capture,context))
                source['dataset_id']=next(i for i in baseline.PT_IDS if i!=identifier)
                (folder/'fit/recipe.json').write_text(json.dumps(dict(source=source)))
                with self.assertRaises(ValueError):baseline.for_job(folder)

    def test_continuity_probes_do_not_apply_5300k_twice(self):
        from output_continuity import ProbeBank
        from sensor_encoding import encode_reference
        bank=ProbeBank()
        old=RuntimeColor.from_capture(*baseline.resolve(baseline.PT_ID))
        rgb=bank.rgb[:bank.domain_size]
        linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
        codes=np.rint(512+linear*15871).astype('<u2')
        np.testing.assert_array_equal(encode_reference(codes,old),codes)
        encoded=encode_reference(codes,self.model)
        delta=itp_flatfield(encoded,self.model.raw,self.model.settings).astype(int)-itp_flatfield(codes,old.raw,old.settings).astype(int)
        self.assertLessEqual(np.abs(delta).max(),3)
        # The native pre-matrix domain is deliberately independent of RAW WB.
        np.testing.assert_array_equal(bank.inputs(self.model)[bank.domain_size:],bank.inputs(old)[bank.domain_size:])

    def test_downloads_are_exact_and_unknown_paths_rejected(self):
        for format in ('arw','dng','raf'):
            name,data=chart_target.raw_file(format=format)
            self.assertEqual(core.sha(data),v45_dataset.metadata()[format+'_sha256'])
        for format in ('../../README.md','tiff'):
            with self.assertRaises(ValueError):chart_target.raw_file(format=format)
        with self.assertRaises(ValueError):chart_datasets.get('unknown')

    def test_lut_target_keeps_previous_color_reference(self):
        from raw_slog3_reference import RawSLog3Reference
        # The LUT must receive the pre-existing reference sensor basis, rather
        # than the new lower red/blue Bayer codes that compensate 5300K WB.
        lut=core.ROOT/'research/r5_custom_lut/evidence/web_anchors_20261021'
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);cube=folder/'test.cube'
            cube.write_text('LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n')
            with patch.object(RawSLog3Reference,'__call__',return_value=np.zeros((99372,3))) as reference:
                core.prepare_target(cube,'S-Gamut3',folder)
                np.testing.assert_array_equal(reference.call_args.args[0],self.arrays['reference_sensor'])

if __name__=='__main__':unittest.main()
