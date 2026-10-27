"""Train-only final integer grid polish, with an overall color-loss guard."""
import numpy as np
from residual_grid import evaluate,pack,unpack
from optimizer_policy import display_cost_rows
from parameter_smoothing import grid_cost


def enabled(value=False):
    if type(value) is not bool:raise ValueError('压缩后灰阶微调开关须为布尔值')
    return value


def refine(grid,base,target,gray,weights,response,parameter_smoothing=0,progress=None,sweeps=3):
    grid=unpack(pack(grid)).astype(int)
    base,target=np.asarray(base,float),np.asarray(target,float)
    gray=np.asarray(gray,bool);weights=np.asarray(weights,float)
    if gray.shape!=(len(base),) or gray.sum()!=256:
        raise ValueError('压缩后微调需要完整256级训练灰阶')
    if weights.shape!=(len(base),) or np.any(weights<=0):raise ValueError('Invalid weights')
    weights=weights/weights.sum()
    if isinstance(response,dict):
        from measured_response import get
        _,ids,w=get(response).stencil(base)
    else:
        from residual_grid import coordinates,stencil
        ids,w=stencil(coordinates(base))
    nodes=np.unique(ids[gray][w[gray]>0])
    pred=evaluate(base,grid,response)
    costs=display_cost_rows(pred,target,.35)
    gray_cost=lambda c:float(c[gray].mean())
    before_gray=gray_cost(costs);before_color=float(costs@weights)
    # Gray nodes also influence neighboring colors: cap overall weighted
    # training degradation at 1%, with 0.25 code-squared numerical allowance.
    cap=before_color+max(.25,before_color*.01)
    objective=gray_cost(costs)+grid_cost(grid,parameter_smoothing)
    accepted=0;rounds=0
    for sweep in range(sweeps):
        changed=False;rounds+=1
        for node in nodes:
            if progress:progress(stage='压缩后灰阶微调',sweep=sweep+1,total_sweeps=sweeps,point=int(node),total_points=405,state='running')
            rows=np.any((ids==node)&(w>0),axis=1)
            for channel in range(3):
                winner=None;best=objective
                for step in (-1,1):
                    trial=grid.copy();trial[node,channel]+=step
                    if not -64<=trial[node,channel]<=63:continue
                    revised=costs.copy()
                    revised[rows]=display_cost_rows(evaluate(base[rows],trial,response),target[rows],.35)
                    gc=gray_cost(revised)
                    score=gc+grid_cost(trial,parameter_smoothing)
                    if gc<gray_cost(costs)-1e-12 and float(revised@weights)<=cap and score<best-1e-12:
                        best=score;winner=(trial,revised)
                if winner is not None:
                    grid,costs=winner;objective=best;changed=True;accepted+=1
        if not changed:break
    return unpack(pack(grid)),dict(enabled=True,accepted_moves=accepted,sweeps=rounds,
        gray_samples=int(gray.sum()),affected_nodes=len(nodes),training_only=True,
        gray_loss_before=before_gray,gray_loss_after=gray_cost(costs),
        color_loss_before=before_color,color_loss_after=float(costs@weights),color_loss_cap=cap,
        parameter_smoothing=parameter_smoothing,objective='floating RGB MSE + .35*(2.55*DE00)^2; native integer grid',
        policy='gray loss strictly decreases; smoothing penalized; weighted train color loss capped; heldout excluded')
