import unittest
import numpy as np
import core,precision_sampling as sampling
from optimizer_policy import display_cost_rows

class PrecisionTests(unittest.TestCase):
    def test_coarse_preserves_tracks_and_excludes_heldout(self):
        a,_=core.measured_inputs()
        selected=sampling.coarse(a)
        self.assertTrue(np.all(a['split'][selected]=='train'))
        tracks=np.isin(a['sample_kind'],sampling.TONAL)
        self.assertTrue(np.all(a['split'][tracks]=='train'))
        required=np.flatnonzero(tracks&(a['anchor_index']<0)&(a['sector16_index']<0))
        self.assertTrue(np.isin(required,selected).all())
        print('coarse',len(selected),'all train',int(np.sum(a['split']=='train')))

    def test_sub_8bit_error_retained(self):
        p=np.array([[.5,.5,.5]]);t=p+.0001
        self.assertGreater(float(display_cost_rows(p,t)[0]),0)

    def test_hard_mining_is_finite_and_bounded(self):
        error=np.array([0.,1.,100.,4.,10.]);groups=np.array([0,0,0,1,1])
        w=sampling.hard_weights(error,groups)
        self.assertTrue(np.all((w>=1)&(w<=4)))
        self.assertGreater(w[2],w[0])

if __name__=='__main__':unittest.main()
