import React,{useEffect,useState,lazy,Suspense}from'react';
import{createRoot}from'react-dom/client';
import{AudioLines,BookOpen,ExternalLink,Layers3,Aperture}from'lucide-react';
import{Toaster}from'sonner';
import{Tabs,TabsList,TabsTrigger,TabsContent}from'@/components/ui/tabs';
import{FilterLibrary}from'./filters';
const SoundLibrary=lazy(()=>import('./sounds').then(m=>({default:m.SoundLibrary})));
import{resourceURL}from'@/lib/resources';
import{loadFilterCatalog}from'./lib/filter-catalog.mjs';
import{SimulationError}from'./metrics';
import {useFilmMotion} from './film-motion';
import './index.css';
const repo='https://github.com/Hearts-Ace/sony-a7r5-custom-firmware';
function useCatalog(path){const [state,setState]=useState({catalog:[],loading:true,error:''});useEffect(()=>{const ctrl=new AbortController();(async()=>{try{const r=await fetch(resourceURL(path),{cache:'no-cache',signal:ctrl.signal});if(!r.ok)throw Error(`目录读取失败 (${r.status})`);const catalog=await r.json();if(!Array.isArray(catalog)||new Set(catalog.map(x=>x.id)).size!==catalog.length)throw Error('目录格式错误');setState({catalog,loading:false,error:''});}catch(e){if(!ctrl.signal.aborted)setState({catalog:[],loading:false,error:e.message});}})();return()=>ctrl.abort();},[path]);return state;}
const tabFromHash=()=>location.hash==='#audio'?'audio':'filters';
function useFilters(){
 const [state,setState]=useState({catalog:[],loading:true,error:''});
 useEffect(()=>{
  const ctrl=new AbortController();let previous,lastCheck=0,busy=false;
  const refresh=async()=>{
   if(document.visibilityState==='hidden'||busy||Date.now()-lastCheck<60000)return;
   busy=true;lastCheck=Date.now();
   try{
    const result=await loadFilterCatalog({signal:ctrl.signal,previous});
    if(!ctrl.signal.aborted&&result!==previous){previous=result;setState({...result,loading:false,error:''});}
   }catch(e){
    if(!ctrl.signal.aborted&&!previous)setState({catalog:[],loading:false,error:e.message});
   }finally{busy=false;}
  };
  refresh();
  window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);
  const timer=setInterval(refresh,300000);
  return()=>{ctrl.abort();clearInterval(timer);window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh);};
 },[]);
 return state;
}
function App(){const reducedMotion=useFilmMotion(true);const [tab,setTab]=useState(tabFromHash);const [audioOpened,setAudioOpened]=useState(()=>tabFromHash()==='audio');useEffect(()=>{if(tab==='audio')setAudioOpened(true);},[tab]);const filters=useFilters(),sounds=useCatalog('sounds/catalog.json');useEffect(()=>{const change=()=>{if(['#audio','#filters',''].includes(location.hash))setTab(tabFromHash());};window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change);},[]);
 return <><div className="glass-atmosphere" aria-hidden="true" data-paused={reducedMotion}><div className="film-leak film-leak-amber"/><div className="film-leak film-leak-red"/><div className="film-leak film-leak-magenta"/></div><a className="skip" href="#main">跳到主要内容</a><header className="site-header"><div className="site-frame header-inner"><a className="brand" href={location.pathname}><span className="brand-mark"><Aperture size={19}/></span><span>R5 <span className="brand-sub">FILM LAB</span></span></a><div className="header-actions"><a className="guide" href={`${repo}/blob/main/${tab==='audio'?'sounds':'docs/resource-library'}/README.md`}><BookOpen size={15}/> 使用说明 <ExternalLink size={12}/></a></div></div></header>
 <main id="main" className="site-frame" tabIndex={-1}><div className="intro" data-enter><div><p className="eyebrow">SONY A7R V</p><h1 className="heading-1">滤镜与声音资源库</h1><p className="intro-text body-6">选择滤镜、安排相机槽位，或试听和转换快门声音。</p></div>{tab==='filters'&&<SimulationError metrics={filters.simulationError}/>}</div>
 <Tabs value={tab} onValueChange={x=>{setTab(x);history.replaceState(null,'',x==='audio'?'#audio':'#filters');}}>
 <TabsList aria-label="资源类型"><TabsTrigger value="filters"><Layers3 size={17}/>色彩滤镜<span className="tab-count">{filters.catalog.length}</span></TabsTrigger><TabsTrigger value="audio"><AudioLines size={17}/>快门声音<span className="tab-count">{sounds.catalog.length}</span></TabsTrigger></TabsList>
 <TabsContent value="filters" forceMount><FilterLibrary {...filters}/></TabsContent><TabsContent value="audio" forceMount>{audioOpened&&<Suspense fallback={<div className="loading-panel" role="status"><span className="skeleton"/><span className="skeleton"/>正在打开声音工作台…</div>}><SoundLibrary {...sounds}/></Suspense>}</TabsContent></Tabs>
 <footer className="site-footer"><span>{tab==='filters'?'适用于支持自定义滤镜 v4 的 Sony A7R V 固件。':'相机使用 R5S；WAV 文件可在本页转换。'}</span><a href={repo}>GitHub 源码 <ExternalLink size={12}/></a></footer></main><Toaster theme="dark" position="bottom-center" richColors closeButton/></>;
}
createRoot(document.getElementById('root')).render(<App/>);
