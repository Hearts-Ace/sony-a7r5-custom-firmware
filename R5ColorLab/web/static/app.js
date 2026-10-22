const measuredGridResponse={"schema": "r5-measured-grid-response/1", "preset": "qaq-a7c2-2.01-c8328ad5", "sha256": "7e183f46f7acd739a12b7c2989e0ce245628a1f0d72d4f673f48945f4493b0af", "proxy_for": "ILCE-7RM5"};
'use strict';
const $ = id => document.getElementById(id);
const clone = value => structuredClone(value);
let boot, draft, selected = 1, collection = [], lutText = '', jobId, timer, busy = false;
const names = ['ST','PT','NT','VV','VV2','FL','FL2','FL3','IN','SH','BW','SE'];
const chineseNames = ['标准','人像','中性','鲜艳','鲜艳二','胶片','胶片二','胶片三','即时','柔和高调','黑白','棕褐'];
let validationJob, rawFile, rawBusy = false, diagnosticData;
let photoFile, photoBusy=false, photoId, photoTask, photoTimer;
let actualUrl,photoSourceSha;
const pcView=()=>$('resultMode').value!=='native';
const gridKeys=new Map();
let diagnosticSerial=0,compressionTimer,compressionBusy=false;
const selectedGrid=()=>$('resultMode').value==='compressed'?gridKeys.get(jobId):undefined;
const algorithmName=()=>$('resultMode').value==='compressed'?'压缩后单网格':pcView()?'压缩前完整补偿':'原生参数';
const pcJobs=new Set();
function clearActual(){if(actualUrl)URL.revokeObjectURL(actualUrl);actualUrl=undefined;$('photoActual').removeAttribute('src');$('photoActual').hidden=true;$('photoActualEmpty').hidden=false;$('photoActualClear').hidden=true;$('photoActualName').textContent='此栏为实际软件输出，不由模拟函数生成。';$('photoActualInput').value='';}
function photoReady(){ $('photoRender').disabled=photoBusy||!photoFile||!validationJob; }
function showPhoto(value){
  if(value.job!==validationJob)return;
  if(Boolean(value.result.pc_compensation_enabled)!==pcView())return;
  if((value.result.grid_key||undefined)!==selectedGrid())return;
  if(value.result.grid_key&&value.result.grid_sha256!==diagnosticData?.grid_sha256)return;
  if(value.result.pc_compensation_enabled && value.result.pc_compensation_sha256!==diagnosticData?.pc_sha256)return;
  photoSourceSha=value.result.source_sha256;
  const base='/api/previews/'+value.id+'/';
  $('photoResults').hidden=false;
  $('photoModel').alt=algorithmName()+' RAW 预览';$('photoModelTitle').textContent='拟合结果 · '+algorithmName();
  for(const [key,file]of[['Lut','lut.png'],['Model','model.png']]){ $('photo'+key).src=base+file;$('photo'+key+'Download').href=base+file; }
  $('photoAudit').href=base+'result.json';
  const r=value.result;
  $('photoProvenance').textContent=`任务 ${value.job} · ${r.gamut} · ${r.width} × ${r.height} ${r.preview_long_edge===3840?'4K 对照图':'历史采样预览'} · ${r.samples} 个采样点 · 同一 RAW SHA256：${r.source_sha256.slice(0,16)}…`;
  $('photoStatus').textContent=('当前 RAW 算法：'+algorithmName()+'；')+'RAW 前端为近似。第三栏可导入 Edit 实际导出图。';
}
async function pollPhoto(){
  try{const value=await(await api('/api/previews/'+photoId)).json();
    if(value.status==='done'||value.status==='error'){
      photoBusy=false;photoReady();
      if(value.status==='done'){showPhoto(value);if(value.job===validationJob&&((value.result.grid_key||undefined)!==selectedGrid()||Boolean(value.result.pc_compensation_enabled)!==pcView()))loadDiagnostics(validationJob);}else if(value.job===validationJob)$('photoStatus').textContent='预览失败：'+value.error;
      return;
    }
    if(value.job===validationJob)$('photoStatus').textContent=value.phase;
    photoTimer=setTimeout(pollPhoto,2000);
  }catch(e){photoBusy=false;photoReady();$('photoStatus').textContent='读取预览失败：'+e.message;}
}
const drafts = new Map();
let toastTimer;
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 6500); }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-R5-Token':boot.token}, body:JSON.stringify(body)});
  if (!response.ok) { let value; try { value = await response.json(); } catch { value = {error:response.statusText}; } throw Error(value.error || '请求失败'); }
  return response;
}
function project(entries = collection) { const grid=entries.some(e=>e.grid_5x9x9?.enabled);const v3=$('exportFormat').value==='3'||grid;return {...boot.template,schema:v3?'r5-native-overwrite-config/3':boot.template.schema,compensation_grid_enabled:grid,entries:clone(entries).map(e=>{if(v3&&!e.grid_5x9x9)e.grid_5x9x9={enabled:false,coefficients:Array.from({length:3},()=>Array.from({length:5},()=>Array.from({length:9},()=>Array(9).fill(0))))};if(!v3)delete e.grid_5x9x9;return e;})}; }
function remember() { if (draft) { draft.name = $('lookName').value; drafts.set(selected, clone(draft)); } }
function syncRaw() { $('rawEditor').value = JSON.stringify(draft, null, 2); $('editStatus').textContent = '参数已更新；点击“加入导出集”保存本项。'; }
function selectLook(number) {
  remember(); selected = number;
  draft = clone(drafts.get(number) || collection.find(e => e.number === number) || boot.presets[number-1]);
  $('lookName').value = draft.name;
  document.querySelectorAll('.looks button').forEach(b => { b.classList.toggle('active', +b.dataset.number === number); b.setAttribute('aria-pressed', +b.dataset.number === number ? 'true' : 'false'); });
  const p = boot.provenance[number-1];
  $('sourceNote').textContent = number > 10 ? 'BW / SE 普通场景基线；矩阵以原生恒等旁路表示。黑白 / 棕褐语义与特殊场景分支仍保留。' : number === 7 || number === 8 ? '现有 FL2 / FL3 适配：FX2 完整端点与已验证 Gamma。' : 'R5 原生普通场景完整颜色参数；保留三端点差异。';
  $('sourceNote').title = JSON.stringify(p);
  renderEditors();
}
function renderEditors() { renderGamma(); renderCC(); renderMatrix(); syncRaw(); }
function cell(value, low, high, change) {
  const td = document.createElement('td'), input = document.createElement('input');
  input.type = 'number'; input.step = '1'; input.min = low; input.max = high; input.value = value;
  input.addEventListener('change', () => { const v = Number(input.value); if (input.value === '' || !Number.isInteger(v) || v < low || v > high) { input.classList.add('invalid'); toast(`请输入 ${low}…${high} 的整数`); return; } input.classList.remove('invalid'); change(v); syncRaw(); });
  td.append(input); return td;
}
function header(table, values) { table.replaceChildren(); const tr = document.createElement('tr'); for (const text of values) { const th = document.createElement('th'); th.textContent = text; tr.append(th); } table.append(tr); }
function renderCC() {
  const table = $('ccTable'); header(table,['端点','色度混合一','色度混合二','色度混合三','色度混合四','色度增益一','色度增益二','色度增益三','色度增益四']);
  ['基准值','照明一差值','照明二差值'].forEach((label,g)=>{const tr=document.createElement('tr'), title=document.createElement('td'); title.textContent=label;tr.append(title);draft.cc1_delta[g].forEach((v,i)=>tr.append(cell(v,-32768,32767,n=>draft.cc1_delta[g][i]=n)));table.append(tr);});
}
function renderMatrix() {
  const table=$('matrixTable'), g=+$('matrixEndpoint').value;header(table,['色相','红减绿','红减蓝','绿减红','绿减蓝','蓝减红','蓝减绿']);
  draft.block13[g].forEach((row,s)=>{const tr=document.createElement('tr'), title=document.createElement('td');title.textContent=String(s).padStart(2,'0');tr.append(title);row.forEach((v,i)=>tr.append(cell(v,-8192,8191,n=>draft.block13[g][s][i]=n)));table.append(tr);});
}
function renderGamma() {
  let point=Math.max(0,Math.min(128,+$('gammaIndex').value || 0));$('gammaIndex').value=point;$('gammaValue').value=draft.gamma_native_129[point];
  const canvas=$('gammaChart'), ctx=canvas.getContext('2d'), w=canvas.width,h=canvas.height,pad={l:52,r:16,t:20,b:28}, iw=w-pad.l-pad.r,ih=h-pad.t-pad.b;
  ctx.clearRect(0,0,w,h);ctx.font='12px system-ui';
  for(let i=0;i<=4;i++){const y=pad.t+ih*i/4;ctx.strokeStyle='#e9ede4';ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.fillStyle='#87917f';ctx.fillText(Math.round(131071*(1-i/4)).toLocaleString(),0,y+4);}
  for(let i=0;i<=4;i++){const x=pad.l+iw*i/4;ctx.fillStyle='#87917f';ctx.fillText(String(i*32),x-7,h-5);}
  const plot=(values,color,width)=>{ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();values.forEach((v,i)=>{const x=pad.l+iw*i/128,y=pad.t+ih*(1-v/131071);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();};
  plot(boot.presets[selected-1].gamma_native_129,'#ced6c6',2);plot(draft.gamma_native_129,'#31583f',2.8);
  ctx.fillStyle='#31583f';ctx.beginPath();ctx.arc(pad.l+iw*point/128,pad.t+ih*(1-draft.gamma_native_129[point]/131071),5,0,Math.PI*2);ctx.fill();
}
function renderCollection() {
  const node=$('collection');node.replaceChildren();collection.sort((a,b)=>a.number-b.number);
  if(!collection.length){const p=document.createElement('p');p.className='empty';p.textContent='尚未添加外观';node.append(p);}
  for(const entry of collection){const row=document.createElement('div');row.className='collection-row';const n=document.createElement('span');n.className='number';n.textContent=entry.number;const info=document.createElement('div'),name=document.createElement('strong'),sub=document.createElement('small');name.textContent=entry.name;sub.textContent=`覆盖 ${chineseNames[entry.number-1]}（${names[entry.number-1]}） · 完整三端点${entry.grid_5x9x9?.enabled?' · 含 5×9×9 网格':''}`;info.append(name,sub);const edit=document.createElement('button');edit.textContent='编辑';edit.onclick=()=>selectLook(entry.number);const remove=document.createElement('button');remove.textContent='×';remove.setAttribute('aria-label','从导出集移除 '+entry.name);remove.onclick=()=>{collection=collection.filter(e=>e.number!==entry.number);renderCollection();};row.append(n,info,edit,remove);node.append(row);}
  $('export').disabled=!collection.length;$('saveProject').disabled=!collection.length;
  const grids=collection.filter(e=>e.grid_5x9x9?.enabled).length;if(grids)$('exportFormat').value='3';$('exportStatus').textContent=collection.length?`${collection.length} 项 · ${grids} 项含 5×9×9 网格 · ${$('exportFormat').value==='3'?'v3 / 需要 4.20，完整替换':'v2 / 4.18 原生参数'}`:'添加至少一项以导出。';
}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function palette(id,colors){const canvas=$(id),ctx=canvas.getContext('2d'),cols=24,rows=4;ctx.clearRect(0,0,canvas.width,canvas.height);for(let i=0;i<cols*rows;i++){const c=colors[Math.floor(i*colors.length/(cols*rows))];ctx.fillStyle=`rgb(${c.map(v=>Math.round(v*255)).join(',')})`;ctx.fillRect(i%cols*canvas.width/cols,Math.floor(i/cols)*canvas.height/rows,canvas.width/cols+1,canvas.height/rows+1);}}
function showResult(result){
  for(const id of ['before','target','after'])palette(id,result.preview[id]);
  const b=result.heldout.before,a=result.heldout.after;
  $('metrics').replaceChildren();for(const [key,title]of[['mae_8bit','平均绝对误差 / 8位'],['rmse_8bit','均方根误差 / 8位'],['p95_8bit','95%误差分位 / 8位']]){const div=document.createElement('div'),label=document.createElement('span'),value=document.createElement('strong'),sub=document.createElement('small');label.textContent=title;value.textContent=a[key].toFixed(2);sub.textContent=`基线 ${b[key].toFixed(2)}`;div.append(label,value,sub);$('metrics').append(div);}
  $('previewBadge').textContent=result.white_balance?.enabled?'实验白平衡模型 · BIN 不含白平衡':'模型结果 · 实拍待验收';
  const entry=clone(result.config.entries[0]);drafts.set(entry.number,entry);
  if(selected===entry.number){draft=entry;$('lookName').value=draft.name;renderEditors();}else toast('拟合结果已保存到对应外观，点击该外观查看。');
  toast('拟合完成；结果已载入编辑器，检查后加入导出集。');
}
function setBusy(value){busy=value;for(const id of ['endpoint','wbTraining','weightRandom','weightPrimaries','weightGray','weightCC24','weightSector16','resetWeights','parameterSmoothing','searchStarts','adaptiveRounds','perceptualWeight','quantizationSweeps','pcCurveMode','pcGridEnabled','gridResponseModel'])$(id).disabled=value;$('pcTraining').disabled=value;$('fit').disabled=value;$('distillGrid').disabled=value||compressionBusy;$('cancel').hidden=!value;if(value){validationJob=undefined;$('rawExport').disabled=true;$('rawTask').textContent='拟合运行中，等待当前任务配方。';photoReady();$('photoResults').hidden=true;$('photoStatus').textContent='拟合运行中，等待当前任务配方。';}}
function histogram(canvas, target, after, color) {
  const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height,left=54,top=15,bottom=h-30,iw=w-left-12,ih=bottom-top;
  const peak=Math.max(...target,...after,1e-9);
  ctx.clearRect(0,0,w,h);ctx.font='12px system-ui';ctx.lineWidth=1;ctx.setLineDash([]);
  for(let i=0;i<=4;i++){const y=top+ih*i/4;ctx.strokeStyle='#e3e8de';ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-12,y);ctx.stroke();ctx.fillStyle='#74816e';ctx.fillText((peak*(1-i/4)*100).toFixed(1)+'%',0,y+4);}
  ctx.fillStyle=color+'30';for(let i=0;i<256;i++){const v=Math.min(target[i],after[i]);ctx.fillRect(left+iw*i/256,bottom-ih*v/peak,iw/256+1,ih*v/peak);}
  for(const [values,dash,stroke]of[[target,[],color],[after,[7,4],'#263b30']]){ctx.strokeStyle=stroke;ctx.lineWidth=1.8;ctx.setLineDash(dash);ctx.beginPath();values.forEach((v,i)=>{const x=left+iw*i/255,y=bottom-ih*v/peak;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();}ctx.setLineDash([]);
  for(const i of [0,64,128,192,255]){ctx.fillStyle='#74816e';ctx.fillText(String(i),left+iw*i/255-7,h-8);}
}
function strip(id, colors){const c=$(id),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);colors.forEach((rgb,i)=>{ctx.fillStyle=`rgb(${rgb.map(v=>Math.round(Math.min(1,Math.max(0,v))*255)).join(',')})`;ctx.fillRect(i*c.width/colors.length,0,c.width/colors.length+1,c.height);});}
function chart24(id,colors){const c=$(id),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);colors.forEach((rgb,i)=>{ctx.fillStyle=`rgb(${rgb.map(v=>Math.round(Math.max(0,Math.min(1,v))*255)).join(',')})`;ctx.fillRect(i%6*120,Math.floor(i/6)*120,118,118);});}
function renderComparison(){
  if(!diagnosticData)return;
  const groups=diagnosticData.tonal.groups,key=$('comparisonMode').value,g=groups[key],h=g.histogram;
  $('tonalMetrics').replaceChildren();
  const table=document.createElement('table');header(table,['分区','样本数','平均绝对误差','均方根误差','95%误差分位','平均 ΔE00','亮度 L* RMSE','染色 a*b* RMSE']);
  for(const item of Object.values(groups)){const tr=document.createElement('tr');for(const value of [item.label,item.samples,...(item.metrics?[item.metrics.mae,item.metrics.rmse,item.metrics.p95,item.metrics.perceptual?.delta_e00_mean,item.metrics.perceptual?.lightness_rmse,item.metrics.perceptual?.ab_rmse].map(v=>v===undefined?'—':v.toFixed(2)):Array(6).fill('—'))]){const td=document.createElement('td');td.textContent=value;tr.append(td);}table.append(tr);}$('tonalMetrics').append(table);
  ['Red','Green','Blue'].forEach((c,i)=>{if(h){histogram($('hist'+c),h.target[i],h.after[i],['#be4f4b','#4e8958','#4a73b7'][i]);$('hist'+c+'Title').textContent=['红色','绿色','蓝色'][i]+'通道 · 重合 '+h.overlap_percent[i].toFixed(2)+'% · RMSE '+g.metrics.channel_rmse[i].toFixed(2);}else{const canvas=$('hist'+c);canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);$('hist'+c+'Title').textContent=['红色','绿色','蓝色'][i]+'通道 · 无样本';}});
  $('histMean').textContent=h?'平均重合 '+h.mean_overlap_percent.toFixed(2)+'%':'无样本';
  $('histStatus').textContent=`${g.label}：${g.samples} 个独立测试样本。表格误差为真实 8 位整数 RGB 的码值误差；不扣黑。`;
  const m=groups.all.metrics,values=[m.mae,m.rmse,m.p95];
  document.querySelectorAll('#metrics strong').forEach((el,i)=>el.textContent=values[i].toFixed(2));
  document.querySelectorAll('#metrics small').forEach(el=>el.textContent='双方量化为 8 位后计算');
}

function renderNativeStages(fitting){
  const area=$('nativeStages');area.replaceChildren();
  if(!fitting?.training_pipeline){area.textContent='历史任务未使用新版分阶段原生训练；重新拟合后生效。';return;}
  const table=document.createElement('table');header(table,['训练阶段','灰阶训练 RMSE','验证 RMSE','验证 ΔE00','固定评分']);
  const labels={'baseline':'原厂基线','monotone-seed':'初始单调曲线','native-gray-tone-gamma-only':'① 仅 Gamma · 灰阶明暗','train-precondition':'② 原生颜色初始化','train-precondition-tone':'② 明暗曲线后的颜色初始化','gray-first':'③ 历史灰阶优先','gray-refinement-candidate':'③ 灰阶专项候选（等权选优）','native-chroma-cc1-block13-gamma-frozen':'④ 固定 Gamma · CC1 / block13','gray-priority-joint':'⑤ 历史灰阶优先联合优化','balanced-joint':'⑤ 四组等权联合优化','weighted-joint':'⑤ 按设置权重联合优化'};
  for(const row of fitting.history){const [stage,strategy]=row.label.split(' / ');if(!labels[stage]&&!/^(integrated-native-PC-|multi-start-|adaptive-round-|integer-refinement|PC-integer-refinement)/.test(stage))continue;const tr=document.createElement('tr');const suffix=strategy==='dense-compressed'?' · 大网格压缩':strategy==='direct'?' · 直接小网格':'';for(const value of [(labels[stage]||(stage.startsWith('multi-start-')?'多起点 '+stage.split('-').at(-1):stage.startsWith('adaptive-round-')?'动态权重第 '+stage.split('-').at(-1)+' 轮':stage.includes('integer-refinement')?'量化后微调':'⑥ 原生与 PC 交替 '+stage.split('-').at(-1)))+suffix+(row.label===fitting.selected?' · 已选':''),row.gray_training?.rmse_8bit?.toFixed(3)??'—',row.validation.rmse_8bit.toFixed(3),row.perceptual_validation?.delta_e00_mean?.toFixed(3)??'—',row.selection_score?.toFixed(3)??'—']){const td=document.createElement('td');td.textContent=value;tr.append(td);}table.append(tr);}
  const note=document.createElement('p');note.className='hint';note.textContent=(fitting.pc_compensation_training?'阶段指标按原生参数 + PC 残差整链评估。':'阶段指标按原生参数评估。')+(fitting.group_total_weights?`本任务总权重：随机色 ${fitting.group_total_weights.random} / 正色 ${fitting.group_total_weights.primaries} / 灰阶 ${fitting.group_total_weights.gray} / 24色 ${fitting.group_total_weights.colorchecker24}${fitting.group_total_weights.sector16!=null?' / 矩阵16色相 '+fitting.group_total_weights.sector16:''}。`:'')+'验证集只参与候选选择；独立测试不参与求解或选择。';area.append(table,note);if(fitting.tonal_balance){const tone=document.createElement('p');tone.className='hint';const c=fitting.tonal_balance.counts.random;tone.textContent=`已启用亮度分层平衡：以固定 ST 基线分区，组内阴影／中间调／高光等总权重；随机训练样本原始覆盖 ${c.train.join(' / ')}，验证 ${c.valid.join(' / ')}，独立测试 ${c.test.join(' / ')}。上述为完整数据分组计数，求解保留既有随机子采样；缺失分区不虚构样本。上方输出分区统计仍按 LUT 目标划分。`;area.append(tone);}if(fitting.search_options){const extra=document.createElement('p');extra.className='hint';extra.textContent=`本任务平滑 ${fitting.search_options.parameter_smoothing ?? 0} / ${fitting.search_options.starts} 个搜索起点 / 动态权重 ${fitting.search_options.adaptive_rounds} 轮 / 感知权重 ${fitting.search_options.perceptual_weight} / 量化微调 ${fitting.search_options.quantization_sweeps} 轮。`;area.append(extra);if(fitting.adaptive_history?.length){const log=document.createElement('p');log.className='hint';log.textContent=fitting.adaptive_history.map(r=>`第 ${r.round} 轮权重：`+Object.values(r.weights).map(v=>v.toFixed(2)).join(' / ')).join('；');area.append(log);}}
}
function renderPCReport(report){
  const area=$('pcStages');area.replaceChildren();area.hidden=!report;$('pcCurves').hidden=!report?.curves;
  if(!report)return;
  const qaqMode=report.curves?.mode==='qaq-grid';
  const rgbMode=report.curves?.mode==='rgb-independent';
  if(qaqMode)$('pcCurves').hidden=true;
  const table=document.createElement('table');header(table,['阶段','灰阶训练 RMSE','独立测试 RMSE','独立测试 ΔE00']);
  for(const [key,label]of [['native','原生模型'],['tone',rgbMode?'① RGB 独立曲线':'① 灰阶明暗'],['tint',rgbMode?'RGB 曲线输出':'② 灰阶染色'],['compensated',report.curves?(report.fitting?.strategy==='none'?'最终输出（未启用网格）':(qaqMode?'实测响应代理网格':'③ 彩色网格（保护灰阶）')):'旧版单网格']]){
    if(qaqMode&&['tone','tint'].includes(key))continue;const gray=report.metrics.gray_training[key],test=report.metrics.test[key];if(!gray||!test)continue;
    const tr=document.createElement('tr');for(const value of [label,gray.rmse.toFixed(3),test.rmse.toFixed(3),test.perceptual?.delta_e00_mean?.toFixed(3)??'—']){const td=document.createElement('td');td.textContent=value;tr.append(td);}table.append(tr);
  }area.append(table);
  if(report.fitting?.strategy){const note=document.createElement("p");note.className="hint";note.textContent=report.fitting.strategy==='none'?'仅独立曲线／曲线阶段，未启用三维网格。':report.fitting.strategy==="dense-compressed"?"已选：17×33×33 大网格 → 密集采样压缩 → 5×9×9 / 7位。":"已选：直接拟合 5×9×9 小网格。";area.append(note);}
  if(qaqMode){const note=document.createElement("p");note.className="hint";note.textContent="网格响应："+JSON.stringify(report.response)+"。新任务使用 A7C2 实测代理：内部坐标 → 网格偏移 → 非线性响应；非 R5 实测。";area.append(note);return;}
  if(!report.curves)return;
  const v=report.curves;
  function plot(id,series,low,high){
    const canvas=$(id),ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height,p=30;
    ctx.clearRect(0,0,w,h);ctx.strokeStyle='#d7dce2';ctx.lineWidth=1;
    for(let i=0;i<=4;i++){const y=p+(h-2*p)*i/4;ctx.beginPath();ctx.moveTo(p,y);ctx.lineTo(w-p,y);ctx.stroke();ctx.fillStyle='#667085';ctx.font='12px sans-serif';ctx.fillText(((high-(high-low)*i/4)*255).toFixed(0),1,y+4);}
    if(low<0){const y=p+high/(high-low)*(h-2*p);ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(p,y);ctx.lineTo(w-p,y);ctx.stroke();ctx.setLineDash([]);}
    for(const [values,color]of series){ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=2;values.forEach((y,i)=>{const x=p+v.axis[i]*(w-2*p),yy=p+(high-y)/(high-low)*(h-2*p);if(i)ctx.lineTo(x,yy);else ctx.moveTo(x,yy);});ctx.stroke();}
    ctx.fillStyle='#667085';ctx.fillText('0',p,h-5);ctx.fillText('255',w-p-22,h-5);
  }
  $('pcToneTitle').textContent=rgbMode?'RGB 独立曲线 · 各通道输入 → 输出':'灰阶亮度曲线';$('pcTintTitle').textContent=rgbMode?'RGB 独立曲线 · 相对恒等映射偏移':'灰阶染色曲线 · 红 / 绿 / 蓝通道偏移';
  if(rgbMode){const colors=['#be4f4b','#4e8958','#4a73b7'];plot('pcToneCurve',[0,1,2].map(c=>[v.rgb.map(row=>row[c]),colors[c]]),0,1);const offset=v.rgb.map((row,i)=>row.map(x=>x-v.axis[i]));const range=Math.max(8/255,...offset.flat().map(Math.abs))*1.15;plot('pcTintCurve',[0,1,2].map(c=>[offset.map(row=>row[c]),colors[c]]),-range,range);return;}
  plot('pcToneCurve',[[v.tone,'#5e6977']],0,1);
  const bound=Math.max(8/255,...v.tint.flat().map(Math.abs))*1.15;
  plot('pcTintCurve',[0,1,2].map((c)=>[v.tint.map(row=>row[c]),['#be4f4b','#4e8958','#4a73b7'][c]]),-bound,bound);
}

async function loadDiagnostics(identifier){
  $('resultMode').disabled=true;
  const request=++diagnosticSerial;const changingJob=validationJob!==identifier;
  let compression;
  try{compression=await(await api('/api/jobs/'+identifier+'/grid-training')).json();}
  catch(e){if(request===diagnosticSerial){$('resultMode').disabled=false;$('histStatus').textContent='压缩状态读取失败：'+e.message;}return;}
  if(request!==diagnosticSerial||identifier!==jobId)return;
  if(compression.key)gridKeys.set(identifier,compression.key);else gridKeys.delete(identifier);
  $('resultMode').querySelector('option[value=compressed]').disabled=!compression.key;

  if(['queued','running'].includes(compression.status)){compressionBusy=true;pollCompression(identifier);}

  $('distillGrid').disabled=busy||compressionBusy;$('distillStatus').textContent='';$('distillMetrics').replaceChildren();$('distillGray').hidden=true;$('distillDownload').hidden=true;$('gridFirmwareDownload').hidden=true;$('addCompressed').hidden=true;
  if(changingJob){photoSourceSha=undefined;clearActual();$('resultMode').value=gridKeys.has(identifier)?'compressed':pcJobs.has(identifier)?'pc':'native';}
  if($('resultMode').value==='compressed'&&!gridKeys.has(identifier))$('resultMode').value=pcJobs.has(identifier)?'pc':'native';
  $('resultMode').querySelector('option[value=pc]').disabled=!pcJobs.has(identifier);$('pcDownload').hidden=!pcJobs.has(identifier);$('pcDownload').href='/api/jobs/'+identifier+'/pc-download';$('trainingResult').hidden=false;
  if(compression.report)renderCompression(compression.report,compression.key,identifier);
  validationJob=undefined;$('rawExport').disabled=true;$('rawTask').textContent='正在读取当前任务配方…';
  photoReady();$('photoResults').hidden=true;$('photoStatus').textContent='正在载入任务配方…';
  $('histStatus').textContent='正在计算测试集直方图与必拟合色卡…';
  try{const data=await(await api('/api/jobs/'+identifier+'/diagnostics?pc='+(pcView()?'1':'0')+'&grid='+(selectedGrid()||''))).json();if(identifier!==jobId||request!==diagnosticSerial)return;
    diagnosticData=data;$('datasetStatus').textContent=data.dataset?.dataset_id==='balanced-chart-20261022-manual-context2'?'本任务使用新分层色卡 · 最后一次 ST 实采（context 2） · 3700 个色块 · 镜头几何校正未进入渲染链路':'本任务使用历史色卡；重新拟合后使用新分层色卡。';renderComparison();renderNativeStages(data.training_fitting);renderPCReport(data.grid_key?null:data.pc_report);$('trainingPolicy').textContent=data.fitting_policy+(data.white_balance?.enabled?` 白平衡联合训练（实验）：冷暖 ${data.white_balance.parameters.temperature_shift} K，绿／洋红 ${data.white_balance.parameters.tint}；LUT 目标固定，前端动态响应近似。BIN 不含白平衡。`:'');$('trainingBadge').textContent=pcJobs.has(identifier)?'含 PC 补偿':'仅原生参数';
    if(data.pc_enabled){palette('after',data.test_preview);$('previewBadge').textContent=algorithmName()+' · 非机内';}else{const native=await(await api('/api/jobs/'+identifier)).json();palette('after',native.result.preview.after);$('previewBadge').textContent='原生参数模型 · 实拍待验收';}
    const n=data.native_tonal.groups.all.metrics,c=data.tonal.groups.all.metrics;
    $('pcStatus').textContent=data.pc_enabled?`${algorithmName()} · 独立测试 RMSE：原生 ${n.rmse.toFixed(2)} → 当前 ${c.rmse.toFixed(2)}；灰阶色卡已显示补偿后结果。4.18 导出不含补偿。`:'当前显示原生结果；新任务可在导入 LUT 后开启 PC 补偿整体训练。';
    if(data.colorchecker24){
      for(const [key,title]of[['before','Before'],['target','Target'],['after','After']])chart24('cc24'+title,data.colorchecker24[key]);
      $('cc24Status').textContent='24 色全部参与优化 · 训练 RMSE / 8位：'+data.colorchecker24.metrics.after.rmse_8bit.toFixed(2)+'；顺序：'+data.colorchecker24.names.join('、');
    }else{
      for(const id of ['cc24Before','cc24Target','cc24After']){const c=$(id);c.getContext('2d').clearRect(0,0,c.width,c.height);}
      $('cc24Status').textContent='此历史任务未包含标准 24 色，请重新拟合。';
    }
    if(data.sector16){
      const sector=data.sector16;
      for(const [key,title]of[['before','Before'],['target','Target'],['after','After']]){
        const canvas=$('sector16'+title),ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
        sector[key].forEach((rgb,i)=>{const row=i<48?i%3:3,col=i<48?Math.floor(i/3):i-48;ctx.fillStyle=`rgb(${rgb.map(v=>Math.round(v*255)).join(',')})`;ctx.fillRect(col*48,row*30,48,30);});
      }
      $('sector16Status').textContent=`64 个实采训练代表色 · RMSE / 8位 ${sector.metrics.after.rmse_8bit.toFixed(2)}（基线 ${sector.metrics.before.rmse_8bit.toFixed(2)}）。前三行为每节点三种明暗，末行为过渡色。基准最大坐标偏差 ${sector.audit.maximum_sector_error}/1024 圈。`;
      const table=document.createElement('table');header(table,['节点','目标坐标','基准实测坐标','当前实测坐标','RMSE / 8位']);
      for(let i=0;i<16;i++){const row=table.insertRow();for(const value of [i+1,sector.audit.knots[i],sector.audit.records.slice(i*3,i*3+3).map(r=>r.measured_sector).join(' / '),sector.current_sectors.slice(i*3,i*3+3).join(' / '),sector.nodes[i].metrics.rmse_8bit.toFixed(2)])row.insertCell().textContent=String(value);}
      $('sector16Details').replaceChildren(table);
    }else{
      for(const id of ['sector16Before','sector16Target','sector16After']){const c=$(id);c.getContext('2d').clearRect(0,0,c.width,c.height);}
      $('sector16Details').replaceChildren();$('sector16Status').textContent='历史任务未启用矩阵16色相训练分组，请重新拟合。';
    }
    if(data.anchors){
      for(const [key,title]of[['input','Input'],['target','Target'],['after','After']]){strip('primary'+title,data.anchors[key].slice(0,4));strip('gray'+title,data.anchors[key].slice(4,260));}
      const m=data.anchors.metrics;
      $('anchorStatus').textContent=`${data.fitting_policy||'历史任务；请重新拟合以应用当前四组等权设置。'} 全部 ${data.anchors.input.length} 个色块参与优化${data.white_balance?.enabled?'，白平衡前端使用实验近似':'，前端为实采数据'}。正色训练 RMSE / 8位：${m.primaries.after.rmse_8bit.toFixed(2)}（基线 ${m.primaries.before.rmse_8bit.toFixed(2)}）；灰阶训练 RMSE / 8位：${m.gray.after.rmse_8bit.toFixed(2)}（基线 ${m.gray.before.rmse_8bit.toFixed(2)}）。`;
    }else{
      for(const id of ['primaryInput','primaryTarget','primaryAfter','grayInput','grayTarget','grayAfter']){const c=$(id);c.getContext('2d').clearRect(0,0,c.width,c.height);}
      $('anchorStatus').textContent='旧任务未使用正色与完整灰阶训练。请使用原 LUT 重新拟合；旧结果不会自动变成新版结果。';
      $('histStatus').textContent=`旧任务独立测试集 ${data.histogram.samples} 个样本；该任务未纳入新增色卡。`;
    }
    validationJob=identifier;const wbActive=data.white_balance&&Object.values(data.white_balance.parameters).some(v=>v!==0);$('rawTask').textContent=wbActive?'此任务含实验白平衡，验证 ARW 暂不能完整复现；请使用浏览器预览。':'配方任务：'+identifier+'；写入 RAW 的标准外观。';$('rawExport').disabled=wbActive||!rawFile||rawBusy;
    photoReady();$('photoStatus').textContent='当前任务：'+identifier+'；选择 RAW 后生成两张图。';
    const saved=await(await api('/api/jobs/'+identifier)).json();
    if(identifier===validationJob&&request===diagnosticSerial){
      const previews=saved.photo_previews|| (saved.photo_preview?[saved.photo_preview]:[]);
      const sourceSha=photoSourceSha||previews.at(-1)?.result.source_sha256;
      const currentPreviews=previews.filter(p=>p.result.source_sha256===sourceSha&&p.result.preview_long_edge===3840);
      if(!currentPreviews.length&&previews.some(p=>p.result.source_sha256===sourceSha))$('photoStatus').textContent='历史预览为低分辨率，请重新导入 RAW 生成 4K 对照图';
      const matching=currentPreviews.filter(p=>Boolean(p.result.pc_compensation_enabled)===pcView()&&(p.result.grid_key||undefined)===selectedGrid()&&(!pcView()||p.result.pc_compensation_sha256===data.pc_sha256)&&(!selectedGrid()||p.result.grid_sha256===data.grid_sha256));
      if(matching.length)showPhoto(matching.at(-1));
      else if(currentPreviews.length&&!photoBusy){
        try{const r=await(await api('/api/preview-reuse',{job:identifier,preview:currentPreviews.at(-1).id,pc:pcView(),grid:selectedGrid()})).json();photoBusy=true;photoReady();photoId=r.id;pollPhoto();}
        catch(e){if(photoFile)$('photoRender').click();else $('photoStatus').textContent=e.message;}
      }
    }
  }catch(e){if(identifier!==jobId)return;$('histStatus').textContent='诊断生成失败：'+e.message;}
  finally{if(request===diagnosticSerial)$('resultMode').disabled=false;}
}

function renderCompression(r,key,identifier){
        const table=document.createElement('table'),head=table.createTHead().insertRow();
        for(const text of ['样本','原组合→LUT RMSE','单网格→LUT RMSE','压缩损失 RMSE']){const th=document.createElement('th');th.textContent=text;head.append(th);}
        const labels={gray_training:'灰阶（训练）',primaries_training:'正色（训练）',colorchecker24_training:'24色（训练）',validation:'验证集',test:'独立测试',unseen_synthetic:'独立合成探针'};
        for(const [name,m]of Object.entries(r.metrics)){const row=table.insertRow();for(const text of [labels[name]||name,m.combined_vs_lut?.groups.all.metrics.rmse.toFixed(3)??'—',m.grid_vs_lut?.groups.all.metrics.rmse.toFixed(3)??'—',m.grid_vs_combined.groups.all.metrics.rmse.toFixed(3)])row.insertCell().textContent=text;}
        $('distillMetrics').replaceChildren(table);
        strip('distillTeacherGray',r.samples.gray_combined);strip('distillStudentGray',r.samples.gray_grid);$('distillGray').hidden=false;
        $('distillStatus').textContent=`已压缩为 405×3 个7位系数（1215 字节），触及幅度边界 ${(r.fitting.limit_fraction*100).toFixed(2)}%。所有 RMSE 均为实际 8 位码值。此结果的模型来源见报告：新任务使用 A7C2 实测代理，并非 R5 实机验收。${r.white_balance?.enabled?' 白平衡仍在网格前单独运算，未压入网格；BIN 不含白平衡。':''}`;
        $('distillDownload').href='/api/jobs/'+identifier+'/grid-distillation-download?key='+key;$('distillDownload').hidden=false;$('gridFirmwareDownload').href='/api/jobs/'+identifier+'/grid-firmware-download?key='+key;$('gridFirmwareDownload').hidden=false;$('addCompressed').hidden=false;

}

function trainingProgressText(p){
  if(!p)return '';
  let text=` · ${p.stage} · 求解轮 ${p.round}/${p.total_rounds}`;
  if(p.iteration!=null && p.stage!=='压缩网格求解')text+=` · 迭代 ${p.iteration}（评估 ${p.evaluations}/${p.max_evaluations} 上限）`;
  if(p.candidate)text+=` · 候选 ${p.candidate}`;
  if(p.sweep!=null)text+=` · 微调 ${p.sweep}/${p.total_sweeps} 轮`;
  if(p.point!=null)text+=` · ${p.family||'网格'} 点位 ${p.point}/${p.total_points}`;
  return text;
}

async function pollCompression(identifier){
  clearTimeout(compressionTimer);
  try{
    const state=await(await api('/api/jobs/'+identifier+'/grid-training')).json();
    if(identifier!==jobId){compressionBusy=false;return;}
    $('compressionTrainingStatus').textContent=(state.phase||'准备压缩训练')+trainingProgressText(state.training_progress);
    if(state.status==='done'||state.status==='error'){
      compressionBusy=false;$('distillGrid').disabled=busy;
      if(state.status==='error')throw Error(state.error);
      gridKeys.set(identifier,state.key);$('resultMode').querySelector('option[value=compressed]').disabled=false;
      $('resultMode').value='compressed';await loadDiagnostics(identifier);return;
    }
    compressionTimer=setTimeout(()=>pollCompression(identifier),1500);
  }catch(e){compressionBusy=false;$('distillGrid').disabled=busy;$('compressionTrainingStatus').textContent='压缩训练：'+e.message;}
}
async function poll(){
  try{const job=await(await api('/api/jobs/'+jobId)).json();$('jobStatus').textContent=job.phase+trainingProgressText(job.training_progress)+` · ${Math.round(((job.finished||Date.now()/1000)-job.started)/60)} 分钟`;$('log').textContent=job.log||'正在校验输入资料…';
    if(job.status==='done'||job.status==='error'){setBusy(false);$('jobDownload').hidden=false;$('jobDownload').href='/api/jobs/'+jobId+'/download';$('jobDownload').download='r5-fit.zip';if(job.status==='done'){if(job.result.pc_compensation?.enabled)pcJobs.add(job.id);if(job.result.grid_key)gridKeys.set(job.id,job.result.grid_key);showResult(job.result);}else{$('jobStatus').textContent=job.error;toast(job.error);}loadDiagnostics(jobId);return;}
    timer=setTimeout(poll,2000);
  }catch(e){setBusy(false);$('jobStatus').textContent='连接中断：'+e.message+'。重载页面可重新连接运行中任务。';}
}
async function loadLut(file){if(!file)return;if(!file.name.toLowerCase().endsWith('.cube')||file.size>64*1024*1024){toast('请选择 64 MiB 内的 .cube 文件');return;}lutText=await file.text();$('lutLabel').textContent=file.name;$('jobStatus').textContent=`已导入 ${(file.size/1024).toFixed(1)} KiB；请选择正确的输入色域。`;}
async function init(){
  try{boot=await(await api('/api/bootstrap')).json();
    names.forEach((name,i)=>{const b=document.createElement('button');b.textContent=chineseNames[i];b.title=name;b.dataset.number=i+1;b.onclick=()=>selectLook(i+1);$('looks').append(b);});
    selectLook(1);renderCollection();
    $('lookName').oninput=()=>{draft.name=$('lookName').value;syncRaw();};
    $('reset').onclick=()=>{draft=clone(boot.presets[selected-1]);$('lookName').value=draft.name;drafts.set(selected,clone(draft));renderEditors();};
    $('matrixEndpoint').onchange=renderMatrix;
    $('comparisonMode').onchange=renderComparison;
    $('resultMode').onchange=()=>{if(validationJob){$('photoResults').hidden=true;loadDiagnostics(validationJob);}};
    $('photoInput').onchange=e=>{const file=e.target.files[0];if(!file)return;if(!/\.arw$/i.test(file.name)||file.size>512*1024*1024){toast('请选择 512 MiB 内的 R5 RAW');return;}photoFile=file;clearActual();$('photoResults').hidden=true;$('photoName').textContent=file.name+' · '+(file.size/1024/1024).toFixed(1)+' MiB';photoReady();};
    $('photoRender').onclick=async()=>{
      if(photoBusy||!photoFile||!validationJob)return;
      photoBusy=true;photoReady();photoTask=validationJob;$('photoResults').hidden=true;$('photoStatus').textContent='正在上传 RAW，随后进行本地解码和渲染…';
      try{const response=await fetch('/api/preview?job='+photoTask+'&pc='+(pcView()?'1':'0')+'&grid='+(selectedGrid()||''),{method:'POST',headers:{'Content-Type':'application/octet-stream','X-R5-Token':boot.token},body:photoFile});const value=await response.json();if(!response.ok)throw Error(value.error);photoId=value.id;clearTimeout(photoTimer);pollPhoto();}
      catch(e){photoBusy=false;photoReady();$('photoStatus').textContent='预览失败：'+e.message;}
    };
    $('photoZoom').onchange=()=>{for(const id of ['photoLut','photoModel','photoActual'])$(id).style.width=(+$('photoZoom').value*100)+'%';};
    $('photoActualInput').onchange=e=>{const file=e.target.files[0];if(!file)return;if(!['image/jpeg','image/png'].includes(file.type)||file.size>65*1024*1024){toast('请选择 65 MiB 内的 JPG / PNG');return;}clearActual();actualUrl=URL.createObjectURL(file);$('photoActual').onload=()=>{$('photoActual').hidden=false;$('photoActualEmpty').hidden=true;$('photoActualClear').hidden=false;$('photoActualName').textContent=file.name+' · '+$('photoActual').naturalWidth+' × '+$('photoActual').naturalHeight+'；请确认是同一 RAW、同一配方，裁切和方向一致。';};$('photoActual').onerror=()=>{clearActual();toast('软件导出图无法解码');};$('photoActual').src=actualUrl;};
    $('photoActualClear').onclick=clearActual;
    const panes=document.querySelectorAll('.photo-scroll');let syncing=false;panes.forEach(pane=>pane.onscroll=()=>{if(syncing)return;syncing=true;for(const other of panes){if(other===pane)continue;other.scrollLeft=pane.scrollLeft;other.scrollTop=pane.scrollTop;}requestAnimationFrame(()=>syncing=false);});
    $('gammaIndex').onchange=renderGamma;
    $('gammaLast').onclick=()=>{$('gammaIndex').value=128;renderGamma();$('gammaValue').focus();};
    $('gammaValue').onchange=()=>{const i=+$('gammaIndex').value,v=+$('gammaValue').value;if($('gammaValue').value===''||!Number.isInteger(v)||v<0||v>131071){toast('Gamma 必须为 0–131071 的整数');return;}draft.gamma_native_129[i]=v;renderGamma();syncRaw();};
    $('gammaChart').onclick=e=>{const rect=e.target.getBoundingClientRect();$('gammaIndex').value=Math.max(0,Math.min(128,Math.round(((e.clientX-rect.left)/rect.width*1000-52)/932*128)));renderGamma();};
    $('gammaReset').onclick=()=>{draft.gamma_native_129=clone(boot.presets[selected-1].gamma_native_129);renderGamma();syncRaw();};
    document.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b===button));document.querySelectorAll('.tab-panel').forEach(panel=>panel.hidden=panel.id!==button.dataset.tab);});
    $('applyRaw').onclick=async()=>{try{const value=JSON.parse($('rawEditor').value);if(value.number!==selected)throw Error('序号必须与当前外观一致');await api('/api/validate',project([value]));draft=value;$('lookName').value=value.name;renderEditors();toast('JSON 已应用');}catch(e){toast(e.message);}};
    $('add').onclick=async()=>{try{remember();const response=await(await api('/api/validate',project([draft]))).json();collection=collection.filter(e=>e.number!==selected);collection.push(clone(draft));renderCollection();$('editStatus').textContent=`已加入导出集 · 文件检查通过 · 单项 ${response.bytes} 字节`;}catch(e){$('editStatus').textContent=e.message;toast(e.message);}};
    $('exportFormat').onchange=renderCollection;
    $('addCompressed').onclick=async()=>{try{const key=gridKeys.get(jobId);if(!jobId||!key)throw Error('请先完成压缩训练');const value=await(await api('/api/jobs/'+jobId+'/grid-firmware-config?key='+key)).json();const entry=value.entries[0];collection=collection.filter(e=>e.number!==entry.number);collection.push(clone(entry));drafts.set(entry.number,clone(entry));$('exportFormat').value='3';renderCollection();draft=undefined;selectLook(entry.number);toast('本任务原生参数与压缩网格已一起加入导出集');}catch(e){toast(e.message);}};
    $('export').onclick=async()=>{try{const response=await api('/api/export',project());download(await response.blob(),'r5-native-config.zip');toast('已导出 BIN、JSON 与校验回执');}catch(e){toast(e.message);}};
    $('saveProject').onclick=()=>download(new Blob([JSON.stringify(project(),null,2)],{type:'application/json'}),'native_config.json');
    $('importProject').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>131072)throw Error('配置 JSON 超过 128 KiB');const value=JSON.parse(await file.text());await api('/api/validate',value);collection=clone(value.entries);$('exportFormat').value=value.schema==='r5-native-overwrite-config/3'?'3':'2';drafts.clear();draft=undefined;renderCollection();selectLook(collection[0]?.number||1);toast('配置已载入，导出集已替换');}catch(error){toast(error.message);}finally{e.target.value='';}};
    $('lut').onchange=e=>loadLut(e.target.files[0]);
    $('dropzone').ondragover=e=>{e.preventDefault();$('dropzone').classList.add('drag');};$('dropzone').ondragleave=()=>$('dropzone').classList.remove('drag');$('dropzone').ondrop=e=>{e.preventDefault();$('dropzone').classList.remove('drag');loadLut(e.dataTransfer.files[0]);};
    $('distillGrid').onclick=async()=>{
      if(busy||compressionBusy)return;
      if(lutText){$('fit').onclick(true);return;}
      try{
        if(!jobId)throw Error('请导入LUT，或选择已完成的PC补偿任务');
        await api('/api/grid-training',{job:jobId,response:measuredGridResponse});
        compressionBusy=true;$('distillGrid').disabled=true;pollCompression(jobId);
      }catch(e){toast(e.message);}
    };
    $('pcCurveMode').onchange=()=>{if($('pcCurveMode').value==='qaq-grid')$('pcGridEnabled').checked=true;};
    $('resetWeights').onclick=()=>{for(const id of ['weightRandom','weightPrimaries','weightGray','weightCC24','weightSector16'])$(id).value='1';};
    $('parameterSmoothing').oninput=()=>{$('parameterSmoothingValue').textContent=$('parameterSmoothing').value;};
    $('fit').onclick=async(compression=false)=>{compression=compression===true;try{if(!lutText)throw Error('请先导入 .cube LUT');remember();const endpoint=$('endpoint').value===''?null:Number($('endpoint').value);if(endpoint!==null&&(!Number.isInteger(endpoint)||endpoint<0||endpoint>131071))throw Error('伽马最后一点必须为 0–131071 的整数，或留空');const group_weights={random:+$('weightRandom').value,primaries:+$('weightPrimaries').value,gray:+$('weightGray').value,colorchecker24:+$('weightCC24').value,sector16:+$('weightSector16').value};if(Object.values(group_weights).some(v=>!Number.isFinite(v)||v<0.05||v>64))throw Error('训练权重需在 0.05–64 之间');const search_options={parameter_smoothing:+$('parameterSmoothing').value,starts:+$('searchStarts').value,adaptive_rounds:+$('adaptiveRounds').value,perceptual_weight:+$('perceptualWeight').value,quantization_sweeps:+$('quantizationSweeps').value};const body={white_balance:$('wbTraining').checked,compression_training:compression,pc_options:{curve_mode:$('pcCurveMode').value,grid_enabled:$('pcCurveMode').value==='qaq-grid'?true:$('pcGridEnabled').checked,response:measuredGridResponse},search_options,group_weights,pc_compensation:$('pcTraining').checked,lut:lutText,gamut:$('gamut').value,evaluations:+$('evaluations').value,number:selected,name:draft.name,gamma_endpoint128:endpoint};const response=await(await api('/api/fit',body)).json();jobId=response.id;setBusy(true);$('jobDownload').hidden=true;$('jobStatus').textContent='任务已提交';clearTimeout(timer);poll();}catch(e){toast(e.message);}};
    $('cancel').onclick=async()=>{try{await api('/api/cancel',{id:jobId});$('jobStatus').textContent='正在取消…';}catch(e){toast(e.message);}};
    $('rawInput').onchange=e=>{const f=e.target.files[0];if(!f)return;if(!/\.arw$/i.test(f.name)||f.size>512*1024*1024){toast('请选择 512 MiB 内的 R5 ARW');return;}rawFile=f;$('rawName').textContent=f.name+' · '+(f.size/1024/1024).toFixed(1)+' MiB';$('rawExport').disabled=!validationJob||rawBusy||Boolean(diagnosticData?.white_balance&&Object.values(diagnosticData.white_balance.parameters).some(v=>v!==0));};
    $('rawExport').onclick=async()=>{if(!rawFile||!validationJob||rawBusy)return;const identifier=validationJob;rawBusy=true;$('rawExport').disabled=true;$('rawStatus').textContent='正在本地上传、校验并生成 ARW 副本，请稍候…';try{const response=await fetch('/api/raw-export?job='+identifier,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-R5-Token':boot.token},body:rawFile});if(!response.ok){const error=await response.json();throw Error(error.error);}download(await response.blob(),rawFile.name.replace(/\.arw$/i,'')+'-Edit验证.zip');$('rawStatus').textContent='验证包已下载。打开 fitted-ST.ARW，在 Edit 显式选择“标准（ST）”。内嵌预览未重绘；请以 Edit 实际渲染为准。';}catch(e){$('rawStatus').textContent='生成失败：'+e.message;toast(e.message);}finally{rawBusy=false;$('rawExport').disabled=!rawFile||!validationJob||Boolean(diagnosticData?.white_balance&&Object.values(diagnosticData.white_balance.parameters).some(v=>v!==0));}};
    for(const job of boot.history){if(job.pc_available)pcJobs.add(job.id);const option=document.createElement('option');option.value=job.id;option.textContent=new Date(job.started*1000).toLocaleString()+' · '+job.phase;$('history').append(option);}
    $('history').onchange=()=>{if(!$('history').value)return;if(busy){toast('当前任务运行中，请完成后查看历史');return;}jobId=$('history').value;clearTimeout(timer);poll();};
    $('history').addEventListener('focus',async()=>{try{const value=await(await api('/api/bootstrap')).json();for(const job of value.history){if([...$('history').options].some(o=>o.value===job.id))continue;const option=document.createElement('option');option.value=job.id;option.textContent=new Date(job.started*1000).toLocaleString()+' · '+job.phase;$('history').append(option);}}catch{}});
    document.querySelector('.brand').onclick=e=>{e.preventDefault();document.querySelector('header').scrollIntoView({behavior:'smooth'});};
    if(boot.jobs.length){jobId=boot.jobs[0];setBusy(true);poll();}
  }catch(e){$('jobStatus').textContent=e.message;toast('初始化失败：'+e.message);}
}
init();
