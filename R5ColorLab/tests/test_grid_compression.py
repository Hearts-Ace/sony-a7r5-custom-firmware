"""Numerical contracts for dense teacher and packed runtime student."""
import unittest
import numpy as np
import core
import pc_stages
from residual_grid import stencil, coordinates, pack, unpack


class GridCompressionTests(unittest.TestCase):
    def test_arbitrary_grid_matches_exact_small_runtime_interpolation(self):
        rng=np.random.default_rng(441)
        rgb=np.r_[rng.uniform(-.2,1.2,(150,3)), [[0,0,0],[1,1,1]]]
        grid=rng.integers(-64,64,(405,3))
        ids,w=stencil(coordinates(rgb))
        expected=np.sum(w[...,None]*grid[ids],axis=1)
        actual=pc_stages.grid_design(rgb,(5,9,9))@grid
        np.testing.assert_allclose(actual,expected,atol=1e-12)
        np.testing.assert_allclose(np.asarray(pc_stages.grid_design(rgb,(17,33,33)).sum(axis=1)).ravel(),1)

    def test_identity_teacher_compresses_and_packs_without_color_or_gray_drift(self):
        rng=np.random.default_rng(442)
        gray=np.repeat(np.linspace(0,1,256)[:,None],3,axis=1)
        base=np.r_[rng.random((100,3)),gray]
        mask=np.r_[np.zeros(100,dtype=bool),np.ones(256,dtype=bool)]
        curve,grid,audit=pc_stages.fit_training(base,base,mask,np.ones(len(base)),strategy='dense-compressed')
        self.assertEqual(audit['teacher_shape'],[17,33,33])
        self.assertEqual(audit['synthetic_probes'],25**3)
        self.assertEqual(grid.shape,(405,3))
        np.testing.assert_array_equal(grid,unpack(pack(grid)))
        np.testing.assert_array_equal(grid,0)
        np.testing.assert_allclose(pc_stages.render(base,curve,grid),base,atol=1e-5)


if __name__=='__main__':unittest.main()
