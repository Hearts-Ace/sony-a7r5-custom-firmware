import React from 'react';
const number=value=>Number.isFinite(value)?value.toFixed(3):'—';
export function cardError(item){const m=item.training_error;return m?.status==='available'?`ΔE00 ${number(m.mean)} · P95 ${number(m.p95)}`:'误差数据待补';}
function Values({metrics}){return <dl className="error-values"><div><dt>平均</dt><dd>{number(metrics.mean)}</dd></div><div><dt>P95</dt><dd>{number(metrics.p95)}</dd></div><div><dt>最大</dt><dd>{number(metrics.maximum)}</dd></div></dl>;}
export function SimulationError({metrics}){
 if(!metrics)return null;
 return <aside className="simulation-error" aria-label="模拟到实机的误差"><div className="error-title"><span>模拟到实机的误差</span><small>ΔE00</small></div><Values metrics={metrics}/><p className="error-scope">{metrics.protocol} · {metrics.samples.toLocaleString()} 色块</p><details><summary>测试范围</summary><p>{metrics.scope}</p></details></aside>;
}
export function FilterTrainingError({item}){
 const m=item.training_error;
 return <section className="training-error" aria-label="滤镜训练误差"><div className="error-title"><span>滤镜训练误差</span><small>ΔE00</small></div>{m?.status==='available'?<><Values metrics={m}/><p className="error-scope">{m.label} · {m.samples.toLocaleString()} 点</p><p className="muted">留出测试结果；不同测试集的数值不直接横向比较。</p></>:<><p className="muted">误差数据待补</p><p className="error-scope">{m?.reason||'尚未提供色差统计。'}</p>{Number.isFinite(m?.validation_objective)&&<p className="error-scope">复合验证目标值 {m.validation_objective.toFixed(3)}，不等于 ΔE00。</p>}</>}</section>;
}
