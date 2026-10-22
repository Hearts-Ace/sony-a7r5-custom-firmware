import unittest
import core
import numpy as np
from parameter_smoothing import native_rows,grid_cost
from optimizer_policy import search_options,refine_grid

class ParameterSmoothingTests(unittest.TestCase):
 def test_nonuniform_gamma_linear_is_unpenalized_and_spike_is_penalized(self):
  x=np.geomspace(1,1000,128)-1;y=x/x[-1]*262143;c=np.ones((6,16))
  self.assertLess(np.linalg.norm(native_rows(c,y,x,100)),1e-12)
  y[50]+=1000
  self.assertGreater(np.linalg.norm(native_rows(c,y,x,100)),.0001)
  self.assertEqual(np.linalg.norm(native_rows(c,y,x,0)),0)
 def test_periodic_hue_boundary(self):
  x=np.arange(128);y=x/x[-1]*262143;c=np.zeros((6,16));c[0,0]=1
  r=native_rows(c,y,x,100)
  self.assertNotEqual(r[15],0);self.assertNotEqual(r[1],0)
 def test_policy_validation(self):
  self.assertEqual(search_options()['parameter_smoothing'],0)
  for value in [True,-1,101,float('nan'),'30']:
   with self.assertRaises(ValueError):search_options({'parameter_smoothing':value})
 def test_quantized_grid_search_keeps_regularized_objective(self):
  rng=np.random.default_rng(22);base=rng.uniform(.1,.9,(80,3));grid=rng.integers(-3,4,(405,3),dtype=np.int8)
  updated,audit=refine_grid(grid,base,base,np.ones(len(base)),np.ones(len(base)),sweeps=1,parameter_smoothing=80)
  self.assertLessEqual(audit['after'],audit['before']+1e-10)
  self.assertGreater(grid_cost(grid,80),0)
 def test_pc_curve_roughness_reduces_with_control(self):
  from pc_stages import fit_curves
  y=np.linspace(0,1,256);b=np.repeat(y[:,None],3,axis=1)
  t=b+.01*np.sin(y[:,None]*150)*np.array([[1,-.2,0]])
  old=fit_curves(b,t,strength=.002);smooth=fit_curves(b,t,strength=.042)
  rough=lambda v:np.sum(np.diff(v['tint'],n=2,axis=0)**2)
  self.assertLess(rough(smooth),rough(old))
