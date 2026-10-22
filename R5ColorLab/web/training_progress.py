"""Atomic, observational training progress; never changes optimization decisions."""
import json
import os
import time
from pathlib import Path


def read_progress(path):
    try:
        value=json.loads(Path(path).read_text())
        return value if isinstance(value,dict) else None
    except (OSError,ValueError):
        return None


class TrainingProgress:
    def __init__(self,path,total=0):
        self.path=Path(path)
        self.value=dict(round=0,total_rounds=total,stage='准备训练')

    def update(self,**values):
        self.value.update(values,updated=time.time())
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.value,ensure_ascii=False)+'\n')
        os.replace(temp,self.path)

    def solve(self,solver,stage,*args,**kwargs):
        self.update(stage=stage,round=self.value['round']+1,iteration=0,
                    evaluations=0,max_evaluations=kwargs.get('max_nfev'),state='running',
                    candidate=None,sweep=None,total_sweeps=None,point=None,total_points=None,family=None)
        def callback(intermediate_result):
            self.update(iteration=self.value['iteration']+1,
                        evaluations=int(intermediate_result.nfev))
        result=solver(*args,callback=callback,**kwargs)
        self.update(evaluations=int(result.nfev),state='round_done')
        return result
