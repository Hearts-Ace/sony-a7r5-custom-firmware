import unittest
import numpy as np
from measured_response import default_response,get,legacy_proxy_response
from residual_grid import evaluate
import pc_stages
from optimizer_policy import pc_options,refine_grid

class MeasuredResponseTests(unittest.TestCase):
    def test_pinned_r5_and_zero_anchor(self):
        response=default_response();model=get(response)
        self.assertFalse(model.proxy)
        self.assertEqual(response['preset'],'r5-paired-20261024-v2')
        self.assertTrue(get(legacy_proxy_response()).proxy)
        x=model.probes(30)
        np.testing.assert_allclose(evaluate(x,np.zeros((405,3),np.int8),response),x,atol=2e-15)
        self.assertEqual(pc_options()['response'],response)
        altered=dict(response,sha256='0'*64)
        with self.assertRaises(ValueError):get(altered)

    def test_same_nonlinear_render_and_fit(self):
        response=default_response();model=get(response);x=model.probes(30)
        table=np.zeros((405,3),np.int8);table[:,0]=12
        q,ids,w=model.stencil(x)
        expected=np.clip(x+np.einsum('nc,nco->no',(table[ids]*w[...,None]).sum(1),model.response(x)),0,1)
        curve=dict(mode='qaq-grid',response=response)
        np.testing.assert_array_equal(pc_stages.render(x,curve,table),evaluate(x,table,response))
        np.testing.assert_allclose(evaluate(x,table,response),expected,atol=1e-14)
        fitted,audit=pc_stages.fit_response_grid(x,expected,np.ones(len(x)),response,strength=.0001)
        before=np.mean((x-expected)**2)
        self.assertLess(np.mean((evaluate(x,fitted,response)-expected)**2),before/10)
        improved,report=refine_grid(fitted,x,expected,np.ones(len(x)),np.ones(len(x)),sweeps=1,response=response)
        self.assertLessEqual(report['after'],report['before']+1e-10)
        self.assertTrue(np.isfinite(evaluate(x,improved,response)).all())

    def test_compression_uses_same_response(self):
        from grid_distillation import compress
        response=default_response();model=get(response);x=model.probes(26)
        table=np.zeros((405,3),np.int8);table[:,0]=6
        teacher=lambda colors:evaluate(colors,table,response)
        grid,audit=compress(x,np.ones(len(x)),teacher,response,probe_side=2,sweeps=0)
        self.assertEqual(model.sha256,response['sha256'])
        self.assertLess(np.mean((evaluate(x,grid,response)-teacher(x))**2),np.mean((x-teacher(x))**2))
