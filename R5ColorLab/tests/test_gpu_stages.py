"""Independent CPU definitions for every accelerated native objective."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from test_gpu_alternation import GPUAlternationTests
from gpu_optimizer import StageObjective,minimize_stage
from fit_anchor_native import SmoothNative
import v4_dataset
from parameter_smoothing import native_rows
from training_progress import TrainingProgress
import pc_stages


class GPUStageTests(GPUAlternationTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        arrays,_=v4_dataset.load()
        cls.gray=SmoothNative(cls.context,arrays['input'][arrays['sample_kind']=='gray'])
        cls.gray_target=cls.gray.render(cls.start)*.92
        cls.reference=cls.smooth.render(cls.start)

    def objective_for(self,mode):
        block=slice(104,None) if mode=='tone' else slice(0,104) if mode=='chroma' else slice(None)
        return StageObjective(self.smooth,self.gray,self.target*16383,self.gray_target,
            self.weights,self.start,self.bundle,.35,30,mode=mode,fixed=self.vector,
            indices=block,reference=self.reference,device='cpu',dtype=self.torch.float64),block

    def reference_residual(self,mode,values,block):
        vector=self.vector.copy();vector[block]=values
        gray=self.gray.render(vector);predicted=self.smooth.render(vector)
        regularization=native_rows(vector[8:104],self.smooth.gamma(vector)*16,
            self.context.axis,30)*np.sqrt(len(self.weights))
        if mode=='tone':
            data=[((gray-self.gray_target)@pc_stages.LUMA)/16383,
                np.diff(vector[104:],n=2)*.0002]
        elif mode=='gray':
            data=[(gray-self.gray_target).ravel()/16383,(vector[:104]-self.start[:104])*.0001,
                (predicted-self.reference).ravel()/16383*.5]
        elif mode=='chroma':
            delta=predicted/16383-self.target
            chroma=delta-(delta@pc_stages.LUMA)[:,None]
            data=[(chroma*np.sqrt(self.weights)[:,None]).ravel(),
                (gray-self.gray_target)@pc_stages.LUMA/16383,
                (predicted-self.reference).ravel()/16383*.1,(vector[:104]-self.start[:104])*.0001]
        else:return self.residual(vector)
        return np.concatenate([*data,regularization])

    def test_all_specialized_losses_and_gradients_match_cpu(self):
        for mode in ('tone','gray','chroma','joint'):
            with self.subTest(mode=mode):
                objective,block=self.objective_for(mode)
                values=self.vector[block]
                value,gradient=objective.value_gradient_stage(values)
                rows=self.reference_residual(mode,values,block)
                self.assertAlmostEqual(value,float(rows@rows)/len(self.weights),places=10)
                direction=np.random.default_rng(18).normal(size=len(values));direction/=np.linalg.norm(direction)
                lo=self.reference_residual(mode,values-direction*1e-6,block)
                hi=self.reference_residual(mode,values+direction*1e-6,block)
                derivative=(hi@hi-lo@lo)/(2e-6*len(self.weights))
                self.assertAlmostEqual(float(gradient@direction),derivative,delta=max(1e-7,abs(derivative)*.03))

    def test_bound_solver_never_accepts_cpu_loss_regression(self):
        objective,block=self.objective_for('chroma')
        values=self.vector[block]
        residual=lambda x:self.reference_residual('chroma',x,block)
        with tempfile.TemporaryDirectory() as directory:
            progress=TrainingProgress(Path(directory)/'progress.json')
            progress.update(stage='test',iteration=0)
            result=minimize_stage(lambda:objective,residual,values,
                dict(bounds=(values-.1,values+.1),max_nfev=40),progress)
        self.assertLessEqual(result.cpu_objective_after,result.cpu_objective_before)
        self.assertTrue(np.all(result.x>=values-.1))
        self.assertTrue(np.all(result.x<=values+.1))
        self.assertLessEqual(result.nfev,40)


if __name__=='__main__':unittest.main()
