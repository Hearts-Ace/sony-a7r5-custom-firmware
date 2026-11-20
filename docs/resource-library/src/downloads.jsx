import React,{useEffect,useState} from 'react';
import {Download,Folder,Layers3,Search} from 'lucide-react';
import {toast} from 'sonner';
import {Button} from '@/components/ui/button';
import {FilterName} from './filters';
import {download,resourceURL} from './lib/resources';
import {loadDownloadCatalog,readDownload} from './lib/download-catalog.mjs';
import baselineDirectory from './generated/resource-directory.json';
export function SingleFilterLibrary({model}){
 const [state,setState]=useState({catalog:[],total:0,loading:true,error:''}),[group,setGroup]=useState(''),[query,setQuery]=useState(''),[busy,setBusy]=useState('');
 useEffect(()=>{
  const controller=new AbortController();setState({catalog:[],total:0,loading:true,error:''});
  loadDownloadCatalog(model,{signal:controller.signal,baselineDirectory,directoryURL:resourceURL('resource-directory.json'),localBase:resourceURL(''),onProgress:p=>{if(!controller.signal.aborted)setState({...p,loading:true,error:''});}}).then(r=>{if(!controller.signal.aborted)setState({...r,loading:false,error:''});}).catch(e=>{if(!controller.signal.aborted)setState(s=>({...s,loading:false,error:e.message}));});
  return()=>controller.abort();
 },[model]);
 const categories=new Map();for(const item of state.catalog){if(!categories.has(item.category))categories.set(item.category,[]);categories.get(item.category).push(item);}
 const match=item=>[item.name,item.short_name,item.category].join(' ').toLowerCase().includes(query.trim().toLowerCase());
 const sections=[...categories].filter(([name])=>!group||group===name).map(([name,items])=>[name,items.filter(match)]).filter(([,items])=>items.length);
 const count=sections.reduce((sum,[,items])=>sum+items.length,0),title=model.toUpperCase();
 async function save(item){setBusy(item.short_name);try{const data=await readDownload(item);download(data,item.filename,'application/json');toast.success(`已下载 ${item.short_name}`);}catch(e){toast.error(e.message);}finally{setBusy('');}}
 return <div className="filter-workspace download-workspace">
  <aside className="sidebar" aria-label={`${title} 滤镜分类`}><div className="panel-kicker"><Layers3 size={16}/>分类</div><button className={`category-button all ${!group?'active':''}`} aria-pressed={!group} onClick={()=>setGroup('')}><Layers3 size={15}/><span>全部滤镜</span><small>{state.total}</small></button>{[...categories].map(([name,items])=><button className={`category-button ${group===name?'active':''}`} key={name} aria-pressed={group===name} onClick={()=>setGroup(name)}><Folder size={15}/><span>{name}</span><small>{items.length}</small></button>)}</aside>
  <section className="catalog-panel" aria-labelledby={`${model}-heading`}>
   <div className="panel-title catalog-heading-row"><div><h2 id={`${model}-heading`}>{group||`${title} 单滤镜`}</h2><p aria-live="polite">{state.loading?`已加载 ${state.catalog.length} / ${state.total} 款`:`${count} 款滤镜`}</p></div><label className="search-field"><Search size={17}/><input type="search" aria-label={`搜索 ${title} 滤镜`} placeholder="搜索滤镜" value={query} onChange={e=>setQuery(e.target.value)}/></label></div>
   <p className="download-scope">{model==='c2'?'A7Look /2，内置文字图标。':'camera-look v2，照片与预览使用相同参数。'} 单款下载；参数转封装，尚未实机验收。</p>
   {state.error&&<p role="alert" className="empty-state">{state.error}，请刷新重试。</p>}
   {!state.catalog.length&&state.loading?<div className="loading-panel" role="status">正在加载滤镜…</div>:!count?<p className="empty-state">{state.loading?'正在加载其余滤镜…':'没有匹配的滤镜。'}</p>:<div className="filter-sections">{sections.map(([name,items])=><section className="filter-section" key={name}>{!group&&<h3 className="filter-section-title">{name}<span>{items.length} 款</span></h3>}<ul className="filter-grid">{items.map((item,index)=><li className="filter-card" key={item.short_name}><div className="film-perforations" aria-hidden="true">{Array.from({length:10},(_,i)=><i key={i}/>)}</div><div className="filter-card-body"><div className="film-identity"><span className="film-label">{title} FILM</span><span className="film-code" style={{fontSize:`${Math.min(26,Math.floor(60/item.short_name.length))}px`}}>{item.short_name}</span></div><div className="film-content"><FilterName name={item.name}/><p className="filter-error">{item.format}</p><Button className="card-add" variant="outline" size="sm" disabled={Boolean(busy)} aria-label={`下载 ${title} ${item.name}`} onClick={()=>save(item)}><Download size={15}/>{busy===item.short_name?'下载中…':'下载滤镜'}</Button></div></div><div className="film-edge" aria-hidden="true"><span>{String(index+1).padStart(2,'0')} ▸</span><span>{title}</span><span>PHOTO</span></div></li>)}</ul></section>)}</div>}
  </section>
 </div>;
}
