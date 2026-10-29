import json,tempfile,unittest
from pathlib import Path
import numpy as np
import core,baseline,v4_dataset

class PTBaselineTests(unittest.TestCase):
    def test_source_bound_history_and_unknown_fail_closed(self):
        for dataset_id in (None,baseline.PT_ID):
            capture,context=baseline.resolve(dataset_id)
            with tempfile.TemporaryDirectory() as tmp:
                job=Path(tmp);(job/'fit').mkdir()
                recipe=dict(source=dict(context=context,capture_report_sha256=core.sha((capture/'report.json').read_bytes())))
                (job/'fit/recipe.json').write_text(json.dumps(recipe))
                self.assertEqual(baseline.for_job(job),(capture,context))
                recipe['source']['capture_report_sha256']='0'*64
                (job/'fit/recipe.json').write_text(json.dumps(recipe))
                with self.assertRaises(ValueError):baseline.for_job(job)

    def test_real_probes_and_all_tonal_tracks(self):
        a,audit=v4_dataset.load()
        self.assertFalse(audit['edit_capture'])
        self.assertTrue(audit['edit_validated'])
        self.assertFalse(audit['frontend_approximate'])
        self.assertNotIn('measured_PT_final',a)
        # NR-off flat patches may have identical probes: verify actual capture
        # provenance instead of requiring artificial spatial variation.
        from edit_color_pipeline import RuntimeColor
        from edit_raw_front import itp_flatfield
        model=RuntimeColor.from_capture(*baseline.resolve(baseline.PT_ID))
        simulated=model.sscs(itp_flatfield(a['sensor_codes'],model.raw,model.settings))
        np.testing.assert_array_equal(a['input'],np.repeat(simulated[:,None,:],9,axis=1))
        source=Path(__file__).parent/'fixtures/v4-verified-input-probes.npz'
        with np.load(source) as z:
            np.testing.assert_array_equal(a['input'],z['input'])
        import precision_sampling
        tracks=np.isin(a['sample_kind'],precision_sampling.TONAL)
        self.assertTrue(np.all(a['split'][tracks]=='train'))

if __name__=='__main__':unittest.main()
