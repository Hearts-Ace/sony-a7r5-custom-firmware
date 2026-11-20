import React,{useEffect,useState,lazy,Suspense}from'react';
import{createRoot}from'react-dom/client';
import{AudioLines,BookOpen,ExternalLink,Layers3,Aperture}from'lucide-react';
import{Toaster}from'sonner';
import{Tabs,TabsList,TabsTrigger,TabsContent}from'@/components/ui/tabs';
import{FilterLibrary}from'./filters';
const SoundLibrary=lazy(()=>import('./sounds').then(m=>({default:m.SoundLibrary})));
import{resourceURL}from'@/lib/resources';
import{loadFilterCatalog}from'./lib/filter-catalog.mjs';
import baselineDirectory from './generated/resource-directory.json';
import{SimulationError}from'./metrics';
import{SingleFilterLibrary}from'./downloads';
import {useFilmMotion} from './film-motion';
import './index.css';
const repo='https://github.com/Hearts-Ace/sony-a7r5-custom-firmware';
function useCatalog(path,enabled){const [state,setState]=useState({catalog:[],loading:true,error:''});useEffect(()=>{if(!enabled)return;const ctrl=new AbortController();(async()=>{try{const r=await fetch(resourceURL(path),{cache:'no-cache',signal:ctrl.signal});if(!r.ok)throw Error(`目录读取失败 (${r.status})`);const catalog=await r.json();if(!Array.isArray(catalog)||new Set(catalog.map(x=>x.id)).size!==catalog.length)throw Error('目录格式错误');setState({catalog,loading:false,error:''});}catch(e){if(!ctrl.signal.aborted)setState({catalog:[],loading:false,error:e.message});}})();return()=>ctrl.abort();},[path,enabled]);return state;}
const tabFromHash=()=>['audio','c2','m4'].includes(location.hash.slice(1))?location.hash.slice(1):'filters';
function useFilters(enabled){
 const [state,setState]=useState({catalog:[],loading:true,error:''});
 useEffect(()=>{
  if(!enabled)return;
  const ctrl=new AbortController();let previous,lastCheck=0,busy=false;
  const refresh=async()=>{
   if(document.visibilityState==='hidden'||busy||Date.now()-lastCheck<60000)return;
   busy=true;lastCheck=Date.now();
   try{
    const result=await loadFilterCatalog({signal:ctrl.signal,previous,baselineDirectory,directoryURL:resourceURL('resource-directory.json'),onProgress:partial=>{
     if(!ctrl.signal.aborted&&!previous)setState({...partial,loading:true,error:''});
    }});
    if(!ctrl.signal.aborted&&result!==previous){previous=result;setState({...result,loading:false,error:''});}
   }catch(e){
    if(!ctrl.signal.aborted&&!previous)setState({catalog:[],loading:false,error:e.message});
   }finally{busy=false;}
  };
  refresh();
  window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);
  const timer=setInterval(refresh,300000);
  return()=>{ctrl.abort();clearInterval(timer);window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh);};
 },[enabled]);
 return state;
}
function App(){const [modelMetrics,setModelMetrics]=useState(null);const reducedMotion=useFilmMotion(true);const [tab,setTab]=useState(tabFromHash);const [opened,setOpened]=useState(()=>[tabFromHash()]);useEffect(()=>{setOpened(current=>current.includes(tab)?current:[...current,tab]);},[tab]);const [audioOpened,setAudioOpened]=useState(()=>tabFromHash()==='audio');useEffect(()=>{if(tab==='audio')setAudioOpened(true);},[tab]);const filters=useFilters(opened.includes('filters')),sounds=useCatalog('sounds/catalog.json',opened.includes('audio'));useEffect(()=>{const change=()=>{if(['#audio','#filters','#c2','#m4',''].includes(location.hash))setTab(tabFromHash());};window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change);},[]);
 return <><div className="glass-atmosphere" aria-hidden="true" data-paused={reducedMotion}><div className="film-leak film-leak-amber"/><div className="film-leak film-leak-red"/><div className="film-leak film-leak-magenta"/></div><a className="skip" href="#main">跳到主要内容</a><header className="site-header"><div className="site-frame header-inner"><a className="brand" href={location.pathname}><span className="brand-mark"><Aperture size={19}/></span><span>R5 <span className="brand-sub">FILM LAB</span></span></a><div className="header-actions"><a className="guide" href={`${repo}/blob/main/${tab==='audio'?'sounds':tab==='c2'?'c2-filters':tab==='m4'?'m4-filters':'docs/resource-library'}/README.md`}><BookOpen size={15}/> 使用说明 <ExternalLink size={12}/></a></div></div></header>
 <main id="main" className="site-frame" tabIndex={-1}><div className="intro" data-enter><div><p className="eyebrow">{tab==='c2'?'SONY A7C II':tab==='m4'?'SONY A7 IV':'SONY A7R V'}</p><h1 className="heading-1">滤镜与声音资源库</h1><p className="intro-text body-6">下载各机型滤镜，或试听和转换快门声音。</p></div>{tab!=='audio'&&<SimulationError metrics={tab==='filters'?filters.simulationError:modelMetrics?{...modelMetrics,source_note:'R5 来源算子色卡校验；C2/M4 尚未经实机校验。'}:null}/>}</div>
 <Tabs value={tab} onValueChange={x=>{setTab(x);history.replaceState(null,'','#'+x);}}>
 <TabsList aria-label="资源类型"><TabsTrigger value="filters"><Layers3 size={17}/>R5 滤镜{opened.includes('filters')&&<span className="tab-count">{filters.total??filters.catalog.length}</span>}</TabsTrigger><TabsTrigger value="c2"><Layers3 size={17}/>C2 滤镜</TabsTrigger><TabsTrigger value="m4"><Layers3 size={17}/>M4 滤镜</TabsTrigger><TabsTrigger value="audio"><AudioLines size={17}/>快门声音{opened.includes('audio')&&<span className="tab-count">{sounds.catalog.length}</span>}</TabsTrigger></TabsList>
 <TabsContent value="filters" forceMount><FilterLibrary {...filters}/></TabsContent><TabsContent value="c2">{tab==='c2'&&<SingleFilterLibrary model="c2" onSimulationError={setModelMetrics}/>}</TabsContent><TabsContent value="m4">{tab==='m4'&&<SingleFilterLibrary model="m4" onSimulationError={setModelMetrics}/>}</TabsContent><TabsContent value="audio" forceMount>{audioOpened&&<Suspense fallback={<div className="loading-panel" role="status"><span className="skeleton"/><span className="skeleton"/>正在打开声音工作台…</div>}><SoundLibrary {...sounds}/></Suspense>}</TabsContent></Tabs>
 <footer className="site-footer"><span>{tab==='filters'?'适用于支持自定义滤镜 v4 的 Sony A7R V 固件。':tab==='c2'?'适用于支持 A7Look /2 的 Sony A7C II 工具。':tab==='m4'?'适用于支持 camera-look v2 的 Sony A7 IV 固件。':'相机使用 R5S；WAV 文件可在本页转换。'}</span><a href={repo}>GitHub 源码 <ExternalLink size={12}/></a></footer></main><Toaster theme="dark" position="bottom-center" richColors closeButton/></>;
}
createRoot(document.getElementById('root')).render(<App/>);
