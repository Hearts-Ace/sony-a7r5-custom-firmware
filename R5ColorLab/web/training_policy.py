"""Shared user-facing cohort importance, independent of cohort sample count."""
import math

GROUPS = ('random', 'primaries', 'gray', 'colorchecker24')


def group_importance(value=None):
    if value is None:
        return dict.fromkeys(GROUPS, 1.0)
    if not isinstance(value, dict) or set(value) not in (set(GROUPS),set(GROUPS)|{'sector16'}):
        raise ValueError('需提供四组基础权重，可附加矩阵16色相权重')
    if any(type(v) not in (int, float) or not math.isfinite(v) or not .05 <= v <= 64 for v in value.values()):
        raise ValueError('每组权重需为 0.05–64 的有限数值')
    return {name:float(value[name]) for name in (*GROUPS, *(['sector16'] if 'sector16' in value else []))}


def composite_score(rmses, importance):
    policy = group_importance(importance)
    names = (GROUPS+('sector16',))[:len(rmses)]
    policy.setdefault('sector16',1.0)
    return math.sqrt(sum(policy[k]*float(v)**2 for k,v in zip(names,rmses))/sum(policy[k] for k in names))
