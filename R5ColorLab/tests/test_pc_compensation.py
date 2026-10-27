"""PC correction contract and source binding, independent of camera export."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import core
from pc_compensation import load, apply
from residual_grid import pack
import pc_stages
import pc_compensation
from perceptual import compare, de2000

class PCCompensationTests(unittest.TestCase):
    def test_separated_tone_tint_and_gray_protection(self):
        y=np.linspace(0,1,256)
        base=np.repeat(y[:,None],3,axis=1)
        tint=np.array([.03,-.01,.02]);tint-=tint@pc_stages.LUMA
        target=(.08+.8*y[:,None])+tint
        value=pc_stages.fit_curves(base,target)
        pc_stages.validate(value)
        tone,colored,gate=pc_stages.curves(base,value)
        self.assertTrue(np.all(gate==0))
        self.assertTrue(np.all(np.diff(value['tone'])>=0))
        np.testing.assert_allclose((colored-tone)@pc_stages.LUMA,0,atol=1e-12)
        self.assertLess(np.sqrt(np.mean((colored-target)**2)),1/255)
        grid=np.full((405,3),63,dtype=np.int8)
        np.testing.assert_allclose(pc_stages.render(base,value,grid),np.clip(colored,0,1))
        value['tone'][5]=-1
        with self.assertRaises(ValueError):pc_stages.validate(value)

    def test_solver_never_uses_validation_or_test_targets(self):
        rng=np.random.default_rng(31)
        gray=np.repeat(np.linspace(0,1,256)[:,None],3,axis=1)
        base=np.r_[rng.random((4,3)),gray,rng.random((24+32+8+8,3))]
        ids=np.r_[np.arange(284),np.full(48,-1)]
        split=np.array(['train']*(284+32)+['valid']*8+['test']*8)
        x=np.repeat((base*16383)[:,None,:],9,axis=1)
        class Model:
            def color_only(self,values):return values
        with tempfile.TemporaryDirectory() as directory:
            job=Path(directory);(job/'fit').mkdir()
            (job/'fit/recipe.json').write_text('{}');(job/'input.cube').write_text('fixture')
            (job/'input_audit.json').write_text(json.dumps(dict(lut_sha256=core.sha(b'fixture'))))
            target=.85*base+.04
            def save():np.savez(job/'pairs.npz',input=x,split=split,anchor_index=ids,**{'0_target':target*16383})
            with patch('baseline.read_job',return_value=({},Model())):
                save();a=pc_compensation.generate(job)
                target[split!='train']=rng.random((16,3))
                save();b=pc_compensation.generate(job)
            self.assertEqual(a['payload_hex'],b['payload_hex'])
            self.assertEqual(a['curves'],b['curves'])
            self.assertNotEqual(a['pairs_sha256'],b['pairs_sha256'])
            self.assertEqual(len(list(job.glob('pc_compensation-*.json'))),1)
            result=apply(job,base.reshape(2,166,3))
            self.assertEqual(result.shape,(2,166,3))
            self.assertTrue(np.isfinite(result).all())

    def test_display_perceptual_metrics_reference_and_quantization(self):
        a=np.array([[50,2.6772,-79.7751],[50,3.1571,-77.2803],[50,2.8361,-74.0200],[50,-1.3802,-84.2814]])
        b=np.array([[50,0,-82.7485]]*4)
        np.testing.assert_allclose(de2000(a,b),[2.0425,2.8615,3.4412,1.0000],atol=.0001)
        rgb=np.array([[.2,.4,.8],[0,0,0],[1,1,1]])
        self.assertEqual(compare(rgb,rgb)['delta_e00_mean'],0)
        self.assertEqual(compare(np.zeros((1,3)),np.full((1,3),.4/255))['delta_e00_mean'],0)

    def test_source_binding_and_black_tint(self):
        with tempfile.TemporaryDirectory() as directory:
            job=Path(directory);(job/'fit').mkdir()
            for name in ['fit/recipe.json','input.cube','pairs.npz']:(job/name).write_bytes(b'fixture')
            (job/'input_audit.json').write_text(json.dumps(dict(lut_sha256=core.sha(b'fixture'))))
            grid=np.full((405,3),[8,4,12],dtype=np.int8)
            value=dict(schema='r5-PC-compensation/1',camera_apply_allowed=False,
                stage='after-color-subchain-PC-only',coordinate_model='provisional-bt601-limited',response=np.eye(3).tolist(),
                recipe_sha256=core.sha(b'fixture'),lut_sha256=core.sha(b'fixture'),
                pairs_sha256=core.sha(b'fixture'),payload_hex=pack(grid).hex())
            (job/'pc_compensation.json').write_text(json.dumps(value))
            rgb=np.zeros((2,3,3));out=apply(job,rgb)
            np.testing.assert_allclose(out,np.broadcast_to(np.array([8,4,12])/256,rgb.shape))
            self.assertTrue(np.all(rgb==0))
            (job/'input.cube').write_bytes(b'changed')
            with self.assertRaises(ValueError):load(job)

if __name__=='__main__':unittest.main()
