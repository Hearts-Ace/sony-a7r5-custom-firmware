"""Plan new RAW patches with approximate baseline bins, never training inputs."""
import numpy as np
from tonal_sampling import classify


def select_codes(shape, anchor_index, model, seed):
    from edit_raw_front import itp_flatfield
    rng=np.random.default_rng(seed)
    # Stratified sensor-axis marginals without optional SciPy runtime imports.
    n=131072
    points=np.column_stack([(rng.permutation(n)+rng.random(n))/n for _ in range(3)])
    # Cover the sensor cube and dark exposure range; select in output strata.
    unit=np.concatenate([points,points*2**rng.uniform(-10,0,(len(points),1))])
    codes=np.unique(np.rint(512+15871*unit).astype(np.uint16),axis=0)
    tone=[];hue=[];sat=[]
    for start in range(0,len(codes),2048):
        front=itp_flatfield(codes[start:start+2048],model.raw,model.settings)
        x=np.repeat(front[:,None,:],9,axis=1)
        color=np.clip(model.color_only(x)[:,4]/16383,0,1)
        tone.extend(classify(color))
        hue.extend(((model.sectors(x)[:,4]+32)//64)%16)
        sat.extend(np.minimum((np.ptp(color,axis=1)/np.maximum(color.max(axis=1),1/16383)*3).astype(int),2))
    tone=np.asarray(tone);hue=np.asarray(hue);sat=np.asarray(sat)
    rgb=np.zeros((*shape,3),dtype=np.uint16);bins=np.full(shape,-1,dtype=np.int16)
    missing=[];used=set();counts={}
    for split in range(5):
        coords=[(y,x) for y in range(shape[0]) for x in range(shape[1]) if (y*shape[1]+x)%5==split and anchor_index[y,x]<0]
        # Round-robin all reachable hue/saturation cells in each brightness stratum.
        pools={}
        for t in range(3):
            cells=[]
            for h in range(16):
                for s in range(3):
                    indices=np.flatnonzero((tone==t)&(hue==h)&(sat==s))
                    if len(indices):cells.append(list(rng.permutation(indices)))
                    elif split==0:missing.append([t,h,s])
            if not cells:raise ValueError('No reachable brightness stratum')
            pools[t]=cells
        counts[str(split)]=[0,0,0]
        for j,(y,x) in enumerate(coords):
            t=j%3;cells=pools[t]
            cell_index=(j//3)%len(cells)
            chosen=None
            for shift in range(len(cells)):
                cell=cells[(cell_index+shift)%len(cells)]
                while cell and cell[-1] in used:cell.pop()
                if cell:chosen=cell.pop();break
            if chosen is None:raise ValueError('Insufficient unique candidates for brightness stratum')
            used.add(chosen);rgb[y,x]=codes[chosen];bins[y,x]=t;counts[str(split)][t]+=1
    return rgb,bins,dict(schema='r5-stratified-RAW-chart/1',candidate_count=len(codes),seed=seed,
        basis='ST color model after flatfield ITP only; Vatr/SSCS not measured; provisional sampling coordinates',
        brightness_thresholds_8bit=[85,170],hue_cells=16,saturation_cells=3,
        missing_reachable_cells=missing,random_counts_by_mod5_split=counts,
        training_admitted=False,requires='independent sensor decode and measured new Edit frontend before training admission')
