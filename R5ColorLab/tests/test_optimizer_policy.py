"""Search and discrete refinement contracts; no independent-test feedback."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import core
from optimizer_policy import (search_options, adaptive_importance, perturbed_starts,
                              smooth_loss_rows, display_cost_rows, refine_grid, refine_native)


class OptimizerPolicyTests(unittest.TestCase):
    def test_options_and_bounded_train_adaptation(self):
        self.assertEqual(search_options()['starts'],4)
        self.assertEqual(search_options()['gamma_color_rounds'],0)
        self.assertEqual(search_options(dict(gamma_color_rounds=3))['gamma_color_rounds'],3)
        for value in [dict(starts=True),dict(starts=13),dict(adaptive_rounds=-1),
                      dict(perceptual_weight=float('nan')),dict(quantization_sweeps=4),dict(unknown=1),
                      dict(gamma_color_rounds=True),dict(gamma_color_rounds=-1),dict(gamma_color_rounds=13)]:
            with self.assertRaises(ValueError):search_options(value)
        base=dict(random=1,primaries=2,gray=3,colorchecker24=4)
        errors=dict(random=1e6,primaries=2,gray=1,colorchecker24=0)
        result=adaptive_importance(base,errors)
        for key in base:self.assertTrue(.5<=result[key]/base[key]<=2)
        self.assertEqual(base['gray'],3)
        self.assertEqual(adaptive_importance(base,errors),result)

    def test_starts_reproducible_bounded_and_distinct(self):
        seed=np.zeros(232);lower=np.full(232,-1);upper=np.full(232,1)
        a=perturbed_starts(seed,3,lower,upper);b=perturbed_starts(seed,3,lower,upper)
        np.testing.assert_array_equal(a,b)
        self.assertFalse(np.array_equal(a[0],a[1]))
        self.assertTrue(np.all(np.abs(a)<1))

    def test_smooth_loss_has_gradient_before_uint8_and_real_loss_zero_at_identity(self):
        rgb=np.array([[0.,0.,0.],[.3,.4,.5],[1.,1.,1.]])
        self.assertTrue(np.isfinite(smooth_loss_rows(rgb,rgb,.35)).all())
        np.testing.assert_array_equal(smooth_loss_rows(rgb,rgb,.35),0)
        np.testing.assert_array_equal(display_cost_rows(rgb,rgb,.35),0)
        moved=rgb.copy();moved[1,0]+=1e-5
        self.assertGreater(np.linalg.norm(smooth_loss_rows(moved,rgb,.35)),0)
        self.assertEqual(smooth_loss_rows(moved,rgb,.35).shape,(3,6))

    def test_grid_integer_moves_lower_actual_uint8_perceptual_objective(self):
        rng=np.random.default_rng(445)
        rgb=rng.uniform(.1,.8,(200,3));target=rgb+np.array([2,-1,1])/256
        grid,audit=refine_grid(np.zeros((405,3),dtype=np.int8),rgb,target,np.ones(200),np.ones(200),1,.35)
        self.assertLess(audit['after'],audit['before'])
        self.assertGreater(audit['accepted'],0)
        self.assertEqual(grid.dtype,np.int8)
        self.assertTrue(np.all((grid>=-64)&(grid<=63)))

    def test_native_integer_moves_preserve_gamma_and_lower_exact_cost(self):
        class Model:
            def __init__(self,p):self.p=p
            def color_only(self,x):return np.full((len(x),9,3),5000+self.p['cc1'][0]*16.)
        class Context:
            def build(self,**params):return Model(params)
        params=dict(cc1=np.r_[np.zeros(4,dtype=int),np.full(4,64)],
                    gamma_y=np.arange(128)*16,matrix_payload=b'fixture')
        target=np.full((8,3),(5000+4*16)/16383)
        with patch('edit_native_model.decode_matrix16',return_value=bytes(552)), \
             patch('edit_parameter_context.quantize_matrix_coefficients',side_effect=lambda payload,c:(payload,c)):
            refined,audit=refine_native(Context(),params,np.zeros((8,9,3)),target,np.ones(8),None,1,.35)
        self.assertLess(audit['after'],audit['before'])
        self.assertEqual(refined['gamma_y'][0],0)
        self.assertTrue(np.all(refined['gamma_y']%2==0))
        self.assertTrue(np.all(refined['cc1'][4:]%2==0))
        self.assertTrue(np.all(np.diff(refined['gamma_y'])>=0))
        self.assertEqual(params['cc1'][0],0)

    def test_large_search_history_is_projected_without_changing_source_or_parameters(self):
        class Stop(Exception):pass
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'fit').mkdir()
            recipe=dict(source={'context':4,'capture_report_sha256':core.sha((core.CAPTURE/'report.json').read_bytes())},parameters={'example':123},fitting={'history':'x'*150000})
            original=json.dumps(recipe).encode();(root/'fit/recipe.json').write_bytes(original)
            def compile(path,*args):
                projected=json.loads(path.read_text())
                self.assertEqual(projected['source'],recipe['source'])
                self.assertEqual(projected['parameters'],recipe['parameters'])
                self.assertLess(path.stat().st_size,128*1024)
                raise Stop()
            with patch.object(core.compiler,'from_fit',side_effect=compile):
                with self.assertRaises(Stop):core.finish_fit(root,1,'ST','ST')
            self.assertEqual((root/'fit/recipe.json').read_bytes(),original)


if __name__=='__main__':unittest.main()
