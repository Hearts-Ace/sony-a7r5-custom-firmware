import unittest
import core
import numpy as np
import pc_stages
from grid_distillation import compress
from residual_grid import evaluate, pack, unpack


class TotalGridTests(unittest.TestCase):
    def test_nonidentity_total_tone_and_tint_are_baked_into_single_payload(self):
        rng=np.random.default_rng(621)
        gray=np.repeat(np.linspace(0,1,256)[:,None],3,axis=1)
        target=np.clip(gray+.025+np.array([.008,-.003,.006]),0,1)
        curve=pc_stages.fit_curves(gray,target)
        color_grid=np.tile([2,-1,1],(405,1)).astype(np.int8)
        teacher=lambda rgb:pc_stages.render(rgb,curve,color_grid)
        train=np.r_[gray,rng.random((120,3))]
        grid,audit=compress(train,np.ones(len(train)),teacher,np.eye(3),probe_side=5,sweeps=1)
        packed=pack(grid)
        self.assertEqual(len(packed),1215)
        self.assertTrue(audit['training_only'])
        probes=rng.uniform(.1,.8,(100,3))
        student=evaluate(probes,unpack(packed),np.eye(3))
        self.assertLess(np.mean((student-teacher(probes))**2),np.mean((probes-teacher(probes))**2)*.1)
        self.assertGreater(np.max(np.abs(student-probes)),.01)
        # In particular, nonzero gray changes survive without runtime curves/gate.
        neutral=np.full((1,3),.4)
        self.assertGreater(float(np.max(np.abs(evaluate(neutral,grid,np.eye(3))-neutral))),.015)

    def test_teacher_receives_training_and_synthetic_queries_only(self):
        train=np.array([[.123,.234,.345],[.456,.567,.678]])
        seen=[]
        def teacher(rgb):seen.append(rgb.copy());return rgb
        grid,audit=compress(train,np.array([1.,3.]),teacher,np.eye(3),probe_side=3,sweeps=0)
        self.assertEqual(len(seen),1)
        np.testing.assert_array_equal(seen[0][:2],train)
        self.assertEqual(len(seen[0]),2+27)
        np.testing.assert_array_equal(grid,0)
        self.assertEqual(audit['train_probe_mass'],[.5,.5])

    def test_rejects_invalid_response_and_weights(self):
        for response,weights in [(np.zeros((3,3)),[1,1]),(np.eye(3),[0,1])]:
            with self.assertRaises(ValueError):
                compress(np.ones((2,3)),weights,lambda x:x,response,probe_side=3,sweeps=0)


if __name__=='__main__':unittest.main()
