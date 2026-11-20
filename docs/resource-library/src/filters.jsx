import {useState,useEffect,useLayoutEffect,useRef} from 'react';
import {DndContext, PointerSensor, KeyboardSensor, closestCenter, useSensor, useSensors} from '@dnd-kit/core';
import {SortableContext, useSortable, verticalListSortingStrategy, sortableKeyboardCoordinates, arrayMove} from '@dnd-kit/sortable';
import {CSS} from '@dnd-kit/utilities';
import {Layers3, Folder, Search, Plus, Check, GripVertical, X, Download, ListOrdered, ArrowUp, ArrowDown, Info, SlidersHorizontal} from 'lucide-react';
import {toast} from 'sonner';
import {FilterTrainingError,cardError} from './metrics';
import {Button} from '@/components/ui/button';
import {Dialog,DialogTrigger,DialogContent,DialogTitle,DialogDescription} from '@/components/ui/dialog';
import {verifiedResource,mergeBins,download,resourceURL} from '@/lib/resources';
const pad=n=>String(n).padStart(2,'0');
const limit=12;
function stored(){try{const s=JSON.parse(localStorage.getItem('r5-selection'));const renamed={'正片':'RP','负片':'RN',Portra400:'P400'};return Array.isArray(s)?[...new Set(s.map(id=>renamed[id]||id))].slice(0,limit):[];}catch{return [];}}
function FilterDetail({item}){return <Dialog><DialogTrigger asChild><Button variant="ghost" size="icon" title="滤镜详情" aria-label={`查看 ${item.name} 详情`}><Info size={16}/></Button></DialogTrigger><DialogContent><span className="code-badge">{item.id}</span><DialogTitle className="dialog-title">{item.name}</DialogTitle><DialogDescription className="muted">{item.description||item.category}</DialogDescription><FilterTrainingError item={item}/><dl className="detail-grid"><dt>更新日期</dt><dd>{item.version||item.updated}</dd><dt>配置格式</dt><dd>{item.format||"R5 自定义滤镜 v4"}</dd><dt>实机验收</dt><dd>{item.camera_tested?'已验收':'尚未验收'}</dd></dl><Button variant="outline" asChild><a href={resourceURL(item.json)} download><Download size={16}/>下载描述 JSON</a></Button></DialogContent></Dialog>}
// Catalog previews are optional and are rendered from the same site as the BIN files.
function FilterPreview({path,name}){
 const [failed,setFailed]=useState(false);
 if(failed)return null;
 return <div className="filter-preview"><img src={resourceURL(path)} alt={`${name} 滤镜渲染预览`} loading="lazy" decoding="async" onError={()=>setFailed(true)}/></div>;
}
export function FilterName({name}){
 const viewport=useRef(null),text=useRef(null),[overflow,setOverflow]=useState(0);
 useLayoutEffect(()=>{
  const measure=()=>{
   const distance=Math.max(0,text.current.scrollWidth-viewport.current.clientWidth);
   setOverflow(distance>1?distance:0);
  };
  const observer=new ResizeObserver(measure);
  observer.observe(viewport.current);
  observer.observe(text.current);
  measure();
  return()=>observer.disconnect();
 },[name]);
 return <strong ref={viewport} className="filter-card-name" title={name} data-overflow={overflow>0} style={{'--name-pan':`${-overflow}px`}}><span ref={text}>{name}</span></strong>;
}
export function FilterCard({item,index,slot,busy,onAdd,model="r5",onDownload}){
 return <li className={`filter-card ${slot?'is-selected':''}`}>
 {item.preview&&<FilterPreview key={item.preview} path={item.preview} name={item.name}/>}
 <div className="film-perforations" aria-hidden="true">{Array.from({length:10},(_,i)=><i key={i}/>)}</div><div className="filter-card-body">
 <div className="film-identity"><span className="film-label" aria-hidden="true">{model.toUpperCase()} FILM</span><span className="film-code" aria-hidden="true" style={{fontSize:`${Math.min(26,Math.floor(60/(item.short_name||item.id).length))}px`}}>{(item.short_name||item.id)}</span><FilterDetail item={item}/></div><div className="film-content">
 <FilterName name={item.name}/>
 <p className="filter-error" title={item.training_error?.label||"等待原始色差记录"}>{cardError(item)}</p>
 <Button className="card-add" variant={slot?'secondary':'outline'} size="sm" disabled={busy||Boolean(slot)} aria-label={onDownload?`下载 ${item.name}`:slot?`${item.name} 已加入资源栏，槽位 ${pad(slot)}`:`加入 ${item.name}`} onClick={onDownload||onAdd}>{onDownload?<Download size={15}/>:slot?<Check size={15}/>:<Plus size={15}/>} {onDownload?'下载滤镜':slot?`槽位 ${pad(slot)}`:'加入资源栏'}</Button>
 </div></div><div className="film-edge" aria-hidden="true"><span>{pad(index+1)} <span className="film-arrow">▸</span></span><span>{model==='r5'?'R5 · V4':model.toUpperCase()}</span><span>{pad(index+1)}A</span></div>
 </li>;
}
function Slot({item,index,total,remove,reorder}){const {attributes,listeners,setNodeRef,transform,transition,isDragging}=useSortable({id:item.id});return <li className={`slot-row ${isDragging?'dragging':''}`} ref={setNodeRef} style={{transform:CSS.Transform.toString(transform),transition}}><button className="grip" {...attributes} {...listeners} aria-label={`拖动排序 ${item.name}`}><GripVertical size={16}/></button><span className="slot-number">{pad(index+1)}</span><span className="slot-name" title={item.name}><b>{(item.short_name||item.id)}</b><small>{item.name}</small></span><div className="slot-actions"><Button variant="ghost" size="icon" aria-label={`上移 ${item.name}`} disabled={index===0} onClick={()=>reorder(index,index-1)}><ArrowUp size={14}/></Button><Button variant="ghost" size="icon" aria-label={`下移 ${item.name}`} disabled={index===total-1} onClick={()=>reorder(index,index+1)}><ArrowDown size={14}/></Button><Button variant="ghost" size="icon" aria-label={`移除 ${item.name}`} onClick={()=>remove(item.id)}><X size={16}/></Button></div></li>}
function TrayBody({selected,ids,limit,busy,setSelection,reorder,exportSelected,sensors,mobile=false}){const Heading=mobile?DialogTitle:'h2';return <><div className="panel-title"><div><div className="panel-kicker"><ListOrdered size={15}/> 相机槽位</div><Heading id={mobile?undefined:"tray-title"}>资源栏 <span className="tray-count">{selected.length} / {limit}</span></Heading></div><Button size="sm" variant="ghost" disabled={!selected.length||busy} onClick={()=>setSelection([])}>清空</Button></div><div className="tray-meter" aria-hidden="true">{Array.from({length:limit},(_,i)=><i key={i} className={i<selected.length?'filled':''}/>)}</div>{!selected.length?<div className="tray-empty"><SlidersHorizontal size={24}/><p>还没有选择滤镜</p><small>可跨系列添加，列表顺序对应相机槽位。</small></div>:<DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={({active,over})=>{if(over)reorder(selected.indexOf(active.id),selected.indexOf(over.id));}}><SortableContext items={selected} strategy={verticalListSortingStrategy}><ol className="slots-list">{selected.map((id,index)=><Slot key={id} item={ids.get(id)} index={index} total={selected.length} reorder={reorder} remove={id=>setSelection(current=>current.filter(x=>x!==id))}/>)}</ol></SortableContext></DndContext>}<div className="tray-footer"><Button disabled={!selected.length||busy} onClick={exportSelected}><Download size={17}/>{busy?'正在生成…':'下载整合 BIN'}</Button><p>R5NATIVE.BIN · 最多 12 槽</p></div></>}
export function FilterLibrary({catalog,loading,error,total=catalog.length}){
 const [mobile,setMobile]=useState(()=>matchMedia('(max-width:900px)').matches),[trayOpen,setTrayOpen]=useState(false);
 useEffect(()=>{const media=matchMedia('(max-width:900px)'),change=()=>{setMobile(media.matches);setTrayOpen(false);};media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);
 const [selection,setSelection]=useState(stored),[group,setGroup]=useState(''),[query,setQuery]=useState(''),[busy,setBusy]=useState(false);
 const ids=new Map(catalog.map(x=>[x.id,x]));const selected=selection.filter(id=>ids.has(id));
 useEffect(()=>{try{localStorage.setItem('r5-selection',JSON.stringify(selection));}catch{}},[selection]);
 const sensors=useSensors(useSensor(PointerSensor,{activationConstraint:{distance:5}}),useSensor(KeyboardSensor,{coordinateGetter:sortableKeyboardCoordinates}));
 const matches=x=>[x.id,x.short_name,x.name,x.category,x.series].join(' ').toLowerCase().includes(query.trim().toLowerCase());
 const categories=new Map();
 for(const item of catalog){
  if(!categories.has(item.category))categories.set(item.category,[]);
  categories.get(item.category).push(item);
 }
 const sections=[...categories]
  .filter(([name])=>!group||name===group)
  .map(([name,items])=>[name,items.filter(matches)])
  .filter(([,items])=>items.length);
 const shown=sections.flatMap(([,items])=>items);
 const add=item=>{if(selected.includes(item.id))return;if((loading?selection.length:selected.length)>=limit){toast.error('资源栏已满，最多 12 款滤镜');return;}setSelection([...new Set([...(loading?selection:selected),item.id])]);toast.success('已加入 1 款滤镜');};
 const reorder=(i,j)=>{if(i>=0&&j>=0&&i!==j){const from=selected[i],to=selected[j];setSelection(current=>arrayMove(current,current.indexOf(from),current.indexOf(to)));}};
 async function exportSelected(){if(loading&&selected.length!==selection.length){toast.info('正在加载已选滤镜，请稍后下载');return;}setBusy(true);try{const inputs=await Promise.all(selected.map(id=>verifiedResource(ids.get(id))));download(mergeBins(inputs),'R5NATIVE.BIN');toast.success(`已生成 ${selected.length} 槽 R5NATIVE.BIN`);}catch(e){toast.error(e.message);}finally{setBusy(false);}}
 return <div className="filter-workspace">
 <aside className="sidebar" aria-label="滤镜分类"><div className="panel-kicker"><Layers3 size={16}/> 分类</div><button className={`category-button all ${!group?'active':''}`} aria-pressed={!group} onClick={()=>setGroup('')}><Layers3 size={15}/><span>全部滤镜</span><small>{total}</small></button>
 {[...categories].map(([name,items])=><button key={name} className={`category-button ${group===name?'active':''}`} aria-pressed={group===name} onClick={()=>setGroup(name)}><Folder size={15}/><span>{name}</span><small>{items.length}</small></button>)}
 </aside>
 <div className="filter-catalog-stage"><section className="catalog-panel filter-catalog" aria-labelledby="catalog-heading"><div className="panel-title catalog-heading-row"><div><h2 id="catalog-heading">{group||'全部滤镜'}</h2><p aria-live="polite">{loading?`已加载 ${catalog.length} / ${total} 款`:`${shown.length} 款滤镜`}</p></div>
 <label className="search-field"><Search size={17}/><input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索滤镜" aria-label="搜索滤镜"/></label></div>
 {loading&&!catalog.length?<div className="loading-panel" role="status"><span className="skeleton"/><span className="skeleton"/>正在加载滤镜…</div>:error?<p className="empty-state" role="alert">{error}，请刷新重试。</p>:!shown.length?<p className="empty-state">{loading?'正在加载其余滤镜…':'没有匹配的滤镜。'}</p>:<div className="filter-sections">{sections.map(([name,items])=><section key={name} className="filter-section">{!group&&<h3 className="filter-section-title">{name}<span>{items.length} 款</span></h3>}<ul className="filter-grid">{items.map(item=><FilterCard key={item.id} item={item} index={catalog.indexOf(item)} slot={selected.indexOf(item.id)+1} busy={busy} onAdd={()=>add(item)}/>)}</ul></section>)}</div>}
 </section></div>
 {mobile?<Dialog open={trayOpen} onOpenChange={setTrayOpen}><DialogTrigger asChild><button className="tray-jump" type="button" aria-label={`打开资源栏，已选 ${selected.length} 款`}><ListOrdered size={17}/> 资源栏 <b>{selected.length}</b></button></DialogTrigger><DialogContent className="tray-dialog" closeLabel="关闭资源栏"><TrayBody selected={selected} ids={ids} limit={limit} busy={busy} setSelection={setSelection} reorder={reorder} exportSelected={exportSelected} sensors={sensors} mobile/><DialogDescription className="sr-only">调整滤镜槽位顺序，或下载整合 BIN。</DialogDescription></DialogContent></Dialog>:<aside className="tray" id="tray" aria-labelledby="tray-title"><TrayBody selected={selected} ids={ids} limit={limit} busy={busy} setSelection={setSelection} reorder={reorder} exportSelected={exportSelected} sensors={sensors}/></aside>}
 </div>;
}
