"""Output-space constraints: topology, gradients, stage parity and integer acceptance."""
import copy
import unittest
from unittest.mock import patch
import numpy as np
from output_continuity import ProbeBank, TensorPenalty
from optimizer_policy import search_options, refine_native


class OutputContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = ProbeBank()

    def test_input_only_deterministic_bank_and_disabled_compatibility(self):
        bank = self.bank
        np.testing.assert_array_equal(bank.rgb, ProbeBank().rgb)
        self.assertEqual(search_options()['output_continuity'], 0)
        for value in (True, -1, 101, float('nan')):
            with self.assertRaises(ValueError): search_options(dict(output_continuity=value))
        self.assertEqual(bank.cost(bank.rgb, 0), 0)
        self.assertAlmostEqual(bank.mass.sum(), 1.)
        self.assertTrue(np.any(np.all(bank.rgb == 0, axis=1)))
        self.assertTrue(np.any(np.all(bank.rgb == 1, axis=1)))
        self.assertGreater(len(bank.rgb), 20000)

    def test_color_reversal_costs_more_than_smooth_or_neutral_tracks(self):
        base = self.bank.rgb.copy()
        neutral = np.full_like(base, .1)
        self.assertLess(self.bank.cost(neutral, 30), 1e-20)
        changed = base.copy()
        at = np.argmin(np.linalg.norm(base - [.04, .025, .01], axis=1))
        changed[at] = [.001, .08, .001]
        self.assertGreater(self.bank.cost(changed, 30), self.bank.cost(base, 30) + .01)
        self.assertTrue(np.isfinite(self.bank.rows(changed, 30)).all())

    def test_numpy_torch_loss_and_gradient_including_neutral(self):
        try: import torch
        except ImportError: self.skipTest('optional torch unavailable')
        from gpu_tensor import TensorTools
        torch.set_num_threads(8)
        tools = TensorTools('cpu', torch.float64)
        penalty = TensorPenalty(self.bank, tools, 30)
        values = np.clip(self.bank.rgb + np.random.default_rng(17).normal(0, .006, self.bank.rgb.shape), .001, .999)
        rgb = tools.tensor(values).requires_grad_(True)
        loss = penalty.loss(rgb); loss.backward()
        self.assertAlmostEqual(float(loss.detach()), self.bank.cost(values, 30) / 255**2, places=12)
        direction = np.random.default_rng(5).normal(size=values.shape)
        direction /= np.linalg.norm(direction)
        epsilon = 1e-6
        hi = self.bank.cost(values + epsilon * direction, 30)
        lo = self.bank.cost(values - epsilon * direction, 30)
        self.assertAlmostEqual(float((rgb.grad * tools.tensor(direction)).sum()),
            (hi - lo) / (2 * epsilon * 255**2), delta=1e-8)
        gray = tools.tensor(np.full_like(values, .1)).requires_grad_(True)
        penalty.loss(gray).backward()
        self.assertTrue(bool(torch.isfinite(gray.grad).all()))

    def test_native_quantization_cannot_ignore_output_penalty(self):
        class Model:
            def __init__(self, p): self.p = p
            def color_only(self, x): return np.full((len(x), 9, 3), 5000 + self.p['cc1'][0] * 16.)
        class Context:
            def build(self, **params): return Model(params)
        params = dict(cc1=np.r_[np.zeros(4, dtype=int), np.full(4, 64)],
            gamma_y=np.arange(128) * 16, matrix_payload=b'fixture')
        with patch('edit_native_model.decode_matrix16', return_value=bytes(552)), \
             patch('edit_parameter_context.quantize_matrix_coefficients', side_effect=lambda payload, c: (payload, c)):
            result, audit = refine_native(Context(), params, np.zeros((8, 9, 3)),
                np.full((8, 3), 5064 / 16383), np.ones(8), None, 1, .35,
                output_penalty=lambda p: float(p['cc1'][0]**2) * 100)
        self.assertEqual(result['cc1'][0], 0)
        self.assertTrue(audit['output_continuity'])
        self.assertLessEqual(audit['after'], audit['before'])

    def test_all_native_gpu_stages_match_cpu_with_output_constraint(self):
        from test_gpu_stages import GPUStageTests
        GPUStageTests.setUpClass()
        fixture = GPUStageTests('test_all_specialized_losses_and_gradients_match_cpu')
        from fit_anchor_native import SmoothNative
        from gpu_optimizer import StageObjective
        probes = SmoothNative(fixture.context, self.bank.inputs(fixture.context.base))
        smooth = copy.copy(fixture.smooth)
        smooth.output_continuity = (self.bank, probes, 30)
        for mode in ('joint', 'tone', 'gray', 'chroma'):
            block = slice(104, None) if mode == 'tone' else slice(0, 104) if mode == 'chroma' else slice(None)
            objective = StageObjective(smooth, fixture.gray, fixture.target * 16383, fixture.gray_target,
                fixture.weights, fixture.start, fixture.bundle, .35, 30, mode=mode, fixed=fixture.vector,
                indices=block, reference=fixture.reference, device='cpu', dtype=fixture.torch.float64)
            value, gradient = objective.value_gradient_stage(fixture.vector[block])
            rows = fixture.reference_residual(mode, fixture.vector[block], block)
            expected = rows @ rows / len(fixture.weights) + self.bank.cost(probes.render(fixture.vector) / 16383, 30) / 255**2
            self.assertAlmostEqual(value, expected, places=10)
            self.assertTrue(np.isfinite(gradient).all())

    def test_final_grid_accepts_only_integer_objective_descent(self):
        from continuity_grid import constrain
        bank = self.bank
        base = bank.rgb[::101]
        grid = np.zeros((405, 3), np.int8)
        grid[::2] = [25, -25, 25]
        grid[1::2] = [-25, 25, -25]
        result, audit = constrain(grid, base, base, np.ones(len(base)), np.eye(3), 30,
            (bank, bank.rgb, 30), evaluations=8, device='cpu')
        self.assertLessEqual(audit['after'], audit['before'])
        self.assertEqual(result.dtype, np.int8)
        self.assertTrue(np.all((result >= -64) & (result <= 63)))
        self.assertTrue(audit['integer_output_acceptance'])

    def test_direct_target_grid_passes_same_constraint_to_every_candidate(self):
        from grid_distillation import fit_target
        table=np.zeros((405,3),np.int8)
        rgb=np.array([[.1,.2,.3],[.3,.4,.5]])
        continuity=(self.bank,self.bank.rgb,30)
        with patch('pc_stages.fit_response_grid',return_value=(table,{})), \
             patch('optimizer_policy.refine_grid',return_value=(table,{})), \
             patch('continuity_grid.constrain',return_value=(table,{'enabled':True})) as constrained:
            _,report=fit_target(rgb,rgb,np.ones(2),np.eye(3),continuity=continuity)
        self.assertEqual(constrained.call_count,3)
        for call in constrained.call_args_list:self.assertIs(call.args[6],continuity)
        self.assertTrue(all(row['output_continuity']['enabled'] for row in report['candidates']))


if __name__ == '__main__': unittest.main()
