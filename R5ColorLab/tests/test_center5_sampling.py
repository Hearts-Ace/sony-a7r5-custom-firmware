import unittest
import numpy as np
from patch_sampling import center_mean

class CenterFiveTests(unittest.TestCase):
    def test_uses_five_outputs_instead_of_center_or_outer_probes(self):
        a=np.zeros((2,9,3));a[:,0]=9000;a[:,8]=9000
        a[:,2:7]=np.arange(5)[None,:,None]**2
        np.testing.assert_array_equal(center_mean(a),np.full((2,3),6.0))
        self.assertEqual(center_mean(a).dtype,np.float64)

    def test_layout_mismatch_rejected(self):
        with self.assertRaises(ValueError):center_mean(np.zeros((2,5,3)))
