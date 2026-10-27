"""Block descent on a shared training objective with frozen complementary blocks."""
import numpy as np


def solve_round(vector, residual, lower, upper, solve, evaluations, round_index, gpu_factory=None):
    """Gamma, then CC1/block13; accept each block only on training loss.

    The caller freezes PC for the entire round, then assesses integer native
    parameters and rebuilds PC. Validation and test data never enter this solve.
    """
    current=np.clip(np.asarray(vector,dtype=float),lower+1e-5,upper-1e-5).copy()
    audit=[]
    def cost(v):
        rows=residual(v)
        return float(rows@rows)
    for name,indices in [('Gamma',slice(104,None)),('CC1 / block13',slice(0,104))]:
        frozen=current.copy()
        def block_residual(values):
            trial=frozen.copy();trial[indices]=values
            return residual(trial)
        before=cost(frozen)
        gpu_options={} if gpu_factory is None else dict(gpu_objective=lambda:gpu_factory(frozen,indices))
        result=solve('Gamma 与色彩交替 '+str(round_index)+'：'+name,
                     block_residual,frozen[indices],bounds=(lower[indices],upper[indices]),
                     max_nfev=evaluations,ftol=1e-7,xtol=1e-7,gtol=1e-8,diff_step=1e-4,**gpu_options)
        trial=frozen.copy();trial[indices]=result.x
        after=cost(trial)
        accepted=bool(np.isfinite(after) and after<before)
        if accepted:current=trial
        audit.append(dict(block=name,before=before,after=after,accepted=accepted,
                          nfev=int(result.nfev),converged=bool(result.success)))
    return current,audit
