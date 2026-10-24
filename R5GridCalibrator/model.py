"""Empirical grid response calibration; no assertion of recovered ISP internals."""
import numpy as np
from scipy.optimize import least_squares

SCHEMA='r5-grid-response-calibration/1'
BT=np.array([[.299,.587,.114],[-.299/(2*.886),-.587/(2*.886),.5],[.5,-.587/(2*.701),-.114/(2*.701)]])*255/np.array([219,224,224])[:,None]
OFFSET=np.array([-16/219,0,0])

def delta(rgb, grid, affine):
    c=np.asarray(rgb)@np.asarray(affine)[:,:3].T+np.asarray(affine)[:,3]
    a=np.clip(c*np.array([4,8,8])+[0,4,4],0,[4,8,8])
    lo=np.minimum(np.floor(a).astype(int),[3,7,7]); f=a-lo
    out=np.zeros_like(rgb,dtype=float);g=np.asarray(grid).reshape(405,3)/256
    for y in (0,1):
        for u in (0,1):
            for v in (0,1):
                w=(f[:,0] if y else 1-f[:,0])*(f[:,1] if u else 1-f[:,1])*(f[:,2] if v else 1-f[:,2])
                out+=w[:,None]*g[(lo[:,0]+y)*81+(lo[:,1]+u)*9+lo[:,2]+v]
    return out

def features(x,d,smooth=False):
    if not smooth:return d
    # No intercept: a zero grid predicts exactly the baseline image.
    return np.concatenate([d,np.einsum('ni,nj->nij',d,x-.5).reshape(-1,9)],axis=1)

def predict(rgb,grid,model):
    d=delta(np.asarray(rgb),grid,model['coordinate_affine'])
    return np.clip(np.asarray(rgb)+features(np.asarray(rgb),d,model['smooth'])@np.asarray(model['response_weights']),0,1)

def metric(pred,target):
    e=(pred-target)*255
    return dict(rmse=float(np.sqrt(np.mean(e*e))),mae=float(np.mean(abs(e))),p95=float(np.percentile(abs(e),95)))

def optimization_options(value=None):
    defaults=dict(max_nfev=150,starts=4,alternations=3,samples_per_pair=480)
    if value is not None:
        if type(value) is not dict or set(value)-set(defaults):raise ValueError('未知优化选项')
        defaults.update(value)
    for key,lo,hi in [('max_nfev',10,1000),('starts',1,8),('alternations',1,6),('samples_per_pair',40,2000)]:
        if type(defaults[key]) is not int or not lo<=defaults[key]<=hi:raise ValueError(key+' 超出允许范围')
    return defaults


def stratified_indices(x,indices,limit):
    # RGB-derived luminance/hue/saturation; only baseline TRAIN colors are read.
    colors=x[indices];hi=colors.max(axis=1);lo=colors.min(axis=1);span=hi-lo
    hue=np.zeros(len(colors));chromatic=span>1e-8
    channel=colors.argmax(axis=1)
    for c in range(3):
        mask=chromatic & (channel==c)
        hue[mask]=((colors[mask,(c+1)%3]-colors[mask,(c+2)%3])/span[mask]+2*c)%6
    lum=colors@np.array([.2126,.7152,.0722]);sat=span/np.maximum(hi,1e-8)
    keys=np.minimum((lum*6).astype(int),5)*48+np.minimum((hue*2).astype(int),11)*4+np.minimum((sat*4).astype(int),3)
    groups=[list(indices[keys==k]) for k in np.unique(keys)]
    rng=np.random.default_rng(20261024)
    for group in groups:rng.shuffle(group)
    chosen=[]
    while groups and len(chosen)<limit:
        for group in groups:
            if len(chosen)>=limit:break
            chosen.append(group.pop())
        groups=[g for g in groups if g]
    return np.array(chosen,dtype=int)


def fit(pairs,progress=lambda value:None,refine=True,options=None):
    options=optimization_options(options)
    if not pairs:raise ValueError('请先添加样本')
    if not any(p['role']=='train' for p in pairs):raise ValueError('至少一组训练样本')
    affine=np.column_stack([BT,OFFSET]);grids=[np.asarray(p['grid']) for p in pairs]
    xs=[];ys=[];ids=[];splits=[];weights=[]
    for i,p in enumerate(pairs):
        x=np.asarray(p['x']);y=np.asarray(p['y']);n=len(x)
        if n<40:raise ValueError('每组至少需要40个有效色块')
        # Block split fixed by image position, not shuffled neighboring pixels.
        bucket=np.asarray(p['buckets']);split=np.where(bucket<7,0,np.where(bucket<9,1,2))
        if p['role']=='validation':split[:]=1
        if p['role']=='test':split[:]=2
        xs.append(x);ys.append(y);ids.extend([i]*n);splits.extend(split);weights.extend([1/np.sqrt(n)]*n)
    x=np.concatenate(xs);y=np.concatenate(ys);ids=np.asarray(ids);splits=np.asarray(splits);weights=np.asarray(weights)
    tr=splits==0;va=splits==1;te=splits==2
    if min(tr.sum(),va.sum(),te.sum())<10:raise ValueError('训练、验证、测试各需至少10个块；请增加样本')
    def deltas(a):
        out=np.empty_like(x)
        for i,g in enumerate(grids):out[ids==i]=delta(x[ids==i],g,a)
        return out
    # Bounded coordinate search uses a deterministic subset of TRAINING only.
    search=np.zeros(len(x),bool)
    for i in range(len(pairs)):
        indices=np.flatnonzero(tr & (ids==i));search[stratified_indices(x,indices,options["samples_per_pair"])]=True
    def solve(d,smooth,mask=None):
        mask=tr if mask is None else mask
        f=features(x,d,smooth);w=weights[mask,None];mat=f[mask]*w;tar=(y-x)[mask]*w
        reg=1e-6 if not smooth else 3e-5
        coef=np.linalg.solve(mat.T@mat+reg*np.eye(mat.shape[1]),mat.T@tar)
        return coef,np.clip(x+f@coef,0,1)
    def candidate(a,smooth,name):
        d=deltas(a);coef,pred=solve(d,smooth)
        return dict(name=name,coordinate_affine=a.tolist(),smooth=smooth,response_weights=coef.tolist(),validation=metric(pred[va],y[va]),training=metric(pred[tr],y[tr])),pred
    progress('拟合固定坐标响应与平滑响应')
    candidates=[]
    for smooth in (False,True):candidates.append(candidate(affine,smooth,'fixed-smooth' if smooth else 'fixed-matrix'))
    coord_note='未请求坐标微调'
    # Constant-axis probes cannot identify coordinates: variation across grid nodes required.
    spatial_variation=max(float(np.std(g.reshape(405,3),axis=0).max()) for i,g in enumerate(grids) if np.any(tr & (ids==i)))
    diagnostics=[]
    if refine and spatial_variation>1:
        rng=np.random.default_rng(20261024)
        starts=[affine.copy()]+[affine+rng.uniform(-.12,.12,affine.shape) for _ in range(options['starts']-1)]
        lower=(affine-.3).ravel();upper=(affine+.3).ravel()
        sx=x[search];sy=y[search];si=ids[search];sw=weights[search,None]
        def search_delta(a):
            out=np.empty_like(sx)
            for i,g in enumerate(grids):
                mask=si==i
                if mask.any():out[mask]=delta(sx[mask],g,a)
            return out
        for start_number,initial in enumerate(starts,1):
            for smooth in (False,True):
                a=initial.copy()
                for turn in range(1,options['alternations']+1):
                    progress(f'起点 {start_number}/{options["starts"]} · {"颜色相关响应" if smooth else "矩阵响应"} · 交替 {turn}/{options["alternations"]} · 每轮最多 {options["max_nfev"]} 次评估')
                    # Conditional response solve, then coordinate update with response fixed.
                    coef,_=solve(deltas(a),smooth,search)
                    calls=[0]
                    def residual(flat):
                        calls[0]+=1
                        d=search_delta(flat.reshape(3,4))
                        e=(np.clip(sx+features(sx,d,smooth)@coef,0,1)-sy)*sw
                        return np.r_[e.ravel(),.02*(flat-affine.ravel())]
                    opt=least_squares(residual,a.ravel(),bounds=(lower,upper),max_nfev=options['max_nfev'],ftol=1e-6)
                    a=opt.x.reshape(3,4)
                    name=f'refined-{"smooth" if smooth else "matrix"}-s{start_number}-a{turn}'
                    candidates.append(candidate(a,smooth,name))
                    diagnostics.append(dict(candidate=name,start=start_number,alternation=turn,smooth=smooth,nfev=int(opt.nfev),residual_calls=calls[0],status=int(opt.status),success=bool(opt.success),message=str(opt.message),cost=float(opt.cost),optimality=float(opt.optimality),bound_parameters=int(np.count_nonzero(opt.active_mask)),budget_exhausted=bool(opt.status==0)))
        coord_note='多起点、训练颜色分层抽样、响应与坐标交替优化；每轮验证选模，测试不参与。局部收敛不等于唯一ISP解'
    elif refine:coord_note='网格缺少节点变化，坐标不可辨识；保持暂定BT.601坐标'
    best,pred=min(candidates,key=lambda v:v[0]['validation']['rmse'])
    d=deltas(np.asarray(best['coordinate_affine']));sing=np.linalg.svd(d[tr],compute_uv=False)
    rank=int(np.linalg.matrix_rank(d[tr],tol=max(float(sing[0])*1e-3,1e-8)))
    warnings=[]
    if any(d["budget_exhausted"] for d in diagnostics):warnings.append("部分坐标求解达到评估上限，可增大预算后比较验证误差；不保证更准确")
    if rank<3:warnings.append('网格探针通道激励不足：只能约束已激励方向，需三轴独立探针')
    if len(pairs)<2:warnings.append('只有一对图：空间留出不能代替独立场景/探针验证')
    if not any(p['role']=='test' for p in pairs):warnings.append('测试为同图空间留出，尚无独立测试图')
    observed=float(np.sqrt(np.mean(((y-x)*255)**2)))
    if observed<.8:warnings.append('图像差异低于0.8级：可能网格未生效或被噪声掩盖，不足以恢复可靠响应')
    basepred=np.clip(x+deltas(affine),0,1)
    per_pair=[]
    for i,p in enumerate(pairs):
        keep=ids==i
        per_pair.append(dict(name=p.get('audit',{}).get('name',str(i+1)),role=p['role'],samples=int(keep.sum()),predicted=metric(pred[keep],y[keep]),baseline=metric(x[keep],y[keep])))
    coords=x[tr]@np.asarray(best['coordinate_affine'])[:,:3].T+np.asarray(best['coordinate_affine'])[:,3]
    cells=np.floor(np.clip(coords*[4,8,8]+[0,4,4],0,[3.99999,7.99999,7.99999])).astype(int)
    occupied=len(np.unique(cells,axis=0))
    coverage=dict(occupied_cells=occupied,total_cells=256,fraction=occupied/256,
                  coordinate_min=coords.min(axis=0).tolist(),coordinate_max=coords.max(axis=0).tolist())
    if occupied<64:warnings.append('训练颜色覆盖少于四分之一网格单元，未覆盖区域仍是外推')
    test_error=metric(pred[te],y[te])['rmse']
    if test_error>=metric(basepred[te],y[te])['rmse']:warnings.append('留出测试未优于原暂定模型；当前结果不应作为更准确模型替换')
    if test_error>=metric(x[te],y[te])['rmse']:warnings.append('留出测试未优于零修正，尚未证明模型可预测实际网格效果')
    selected=dict(best);selected.pop('training');selected.pop('validation');selected['schema']=SCHEMA
    report=dict(optimization=dict(options=options,search_samples=int(search.sum()),sampling="training-only luminance/hue/saturation stratified",runs=diagnostics),selected_model=best['name'],training=metric(pred[tr],y[tr]),validation=metric(pred[va],y[va]),test=metric(pred[te],y[te]),
                baseline_test=metric(x[te],y[te]),legacy_identity_test=metric(basepred[te],y[te]),
                counts=dict(train=int(tr.sum()),validation=int(va.sum()),test=int(te.sum()),pairs=len(pairs)),
                per_pair=per_pair,coordinate_coverage=coverage,excitation_rank=rank,singular_values=sing.tolist(),warnings=warnings,coordinate_note=coord_note,
                observed_change_rmse=observed,candidates=[a for a,_ in candidates],
                acceptance='empirical fit only; held-out image errors do not establish unique ISP recovery')
    selected['report']=report
    progress('完成')
    return selected
