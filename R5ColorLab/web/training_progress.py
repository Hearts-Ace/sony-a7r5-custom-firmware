"""Atomic, observational training progress; never changes optimization decisions."""
import json
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threadpoolctl import threadpool_limits


def read_progress(path):
    try:
        value=json.loads(Path(path).read_text())
        return value if isinstance(value,dict) else None
    except (OSError,ValueError):
        return None


class TrainingProgress:
    def __init__(self,path,total=0,gradient_workers=1):
        if type(gradient_workers) is not int or gradient_workers<1:
            raise ValueError('gradient_workers must be a positive integer')
        self.path=Path(path)
        self.gradient_workers=gradient_workers
        self.value=dict(round=0,total_rounds=total,stage='准备训练')
        self.convergence=[]

    def update(self,**values):
        self.value.update(values,updated=time.time())
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.value,ensure_ascii=False)+'\n')
        os.replace(temp,self.path)

    def solve(self,solver,stage,*args,**kwargs):
        gpu_factory=kwargs.pop('gpu_objective',None)
        self.update(stage=stage,round=self.value['round']+1,iteration=0,
                    evaluations=0,max_evaluations=kwargs.get('max_nfev'),state='running',
                    candidate=None,sweep=None,total_sweeps=None,point=None,total_points=None,family=None,
                    gradient_workers=self.gradient_workers,gpu_backend=None)
        from gpu_runtime import available
        if gpu_factory is not None and available():
            try:
                self.update(gradient_workers=0,gpu_fallback=None)
                from gpu_optimizer import minimize_stage
                result=minimize_stage(gpu_factory,args[0],args[1],kwargs,self)
            except (RuntimeError,ValueError,NotImplementedError) as error:
                if os.environ.get('R5_GPU_STRICT','0') == '1':
                    raise RuntimeError('GPU训练失败，严格模式已停止：'+str(error)) from error
                self.convergence.append(dict(stage=stage,backend='GPU fallback',error=str(error)))
                self.update(gpu_fallback=str(error),gpu_backend=None,gradient_workers=self.gradient_workers)
            else:
                self.convergence.append(dict(stage=stage,evaluations=int(result.nfev),
                    evaluation_limit=kwargs.get('max_nfev'),status=int(result.status),
                    converged=bool(result.success),budget_exhausted=bool(result.status==0),
                    cost=float(result.cost),optimality=float(result.optimality),message=str(result.message),
                    backend=result.backend,cpu_objective_accepted=result.cpu_objective_accepted,
                    cpu_objective_before=result.cpu_objective_before,cpu_objective_after=result.cpu_objective_after,
                    seconds=result.seconds))
                self.update(evaluations=int(result.nfev),state='round_done',gpu_backend=None)
                return result
        def callback(intermediate_result):
            self.update(iteration=self.value['iteration']+1,
                        evaluations=int(intermediate_result.nfev))
        # Ordered thread mapping shares read-only model arrays and preserves
        # finite-difference column order. Candidate selection stays serial.
        if self.gradient_workers>1:
            with ThreadPoolExecutor(max_workers=self.gradient_workers,
                                    thread_name_prefix='r5-gradient') as pool:
                def ordered_map(function,values):
                    # Derivative jobs each use one BLAS thread; after their
                    # barrier the solver's dense factorization can use eight.
                    with threadpool_limits(limits=1):
                        return list(pool.map(function,values))
                with threadpool_limits(limits=self.gradient_workers):
                    result=solver(*args,callback=callback,workers=ordered_map,**kwargs)
        else:
            result=solver(*args,callback=callback,**kwargs)
        self.convergence.append(dict(stage=stage,evaluations=int(result.nfev),
            evaluation_limit=kwargs.get('max_nfev'),status=int(result.status),
            converged=bool(result.success),budget_exhausted=bool(result.status==0),
            cost=float(result.cost),optimality=float(result.optimality),message=str(result.message),
            gradient_workers=self.gradient_workers))
        self.update(evaluations=int(result.nfev),state='round_done')
        return result
