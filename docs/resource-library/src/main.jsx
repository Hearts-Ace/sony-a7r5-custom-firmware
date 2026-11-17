import React,{useEffect,useState}from'react';
import{createRoot}from'react-dom/client';
import{AudioLines,BookOpen,ExternalLink,Layers3,Aperture}from'lucide-react';
import{Toaster}from'sonner';
import{Tabs,TabsList,TabsTrigger,TabsContent}from'@/components/ui/tabs';
import{FilterLibrary}from'./filters';
import{SoundLibrary}from'./sounds';
import{resourceURL}from'@/lib/resources';
import './index.css';
const repo='https://github.com/Hearts-Ace/sony-a7r5-custom-firmware';
function useCatalog(path){const [state,setState]=useState({catalog:[],loading:true,error:''});useEffect(()=>{const ctrl=new AbortController();(async()=>{try{const r=await fetch(resourceURL(path),{cache:'no-cache',signal:ctrl.signal});if(!r.ok)throw Error(`目录读取失败 (${r.status})`);const catalog=await r.json();if(!Array.isArray(catalog)||new Set(catalog.map(x=>x.id)).size!==catalog.length)throw Error('目录格式错误');setState({catalog,loading:false,error:''});}catch(e){if(!ctrl.signal.aborted)setState({catalog:[],loading:false,error:e.message});}})();return()=>ctrl.abort();},[path]);return state;}
const tabFromHash=()=>location.hash==='#audio'?'audio':'filters';
function App(){const [tab,setTab]=useState(tabFromHash);const filters=useCatalog('data/catalog.json'),sounds=useCatalog('sounds/catalog.json');useEffect(()=>{const change=()=>{if(['#audio','#filters',''].includes(location.hash))setTab(tabFromHash());};window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change);},[]);
 return <><a className="skip" href="#main">跳到主要内容</a><header className="site-header"><div className="site-frame header-inner"><a className="brand" href={location.pathname}><span className="brand-mark"><Aperture size={19}/></span><span>R5 资源库</span></a><a className="guide" href={`${repo}/blob/main/${tab==='audio'?'sounds':'docs/resource-library'}/README.md`}><BookOpen size={15}/> 使用说明 <ExternalLink size={12}/></a></div></header>
 <main id="main" className="site-frame" tabIndex={-1}><div className="intro" data-enter><div><p className="eyebrow">SONY A7R V</p><h1>滤镜与声音资源库</h1><p className="intro-text">选择滤镜、安排相机槽位，或试听和转换快门声音。</p></div></div>
 <Tabs value={tab} onValueChange={x=>{setTab(x);history.replaceState(null,'',x==='audio'?'#audio':'#filters');}}>
 <TabsList aria-label="资源类型"><TabsTrigger value="filters"><Layers3 size={17}/>色彩滤镜<span className="tab-count">{filters.catalog.length}</span></TabsTrigger><TabsTrigger value="audio"><AudioLines size={17}/>快门声音<span className="tab-count">{sounds.catalog.length}</span></TabsTrigger></TabsList>
 <TabsContent value="filters" forceMount><FilterLibrary {...filters}/></TabsContent><TabsContent value="audio"><SoundLibrary {...sounds}/></TabsContent></Tabs>
 <footer className="site-footer"><span>{tab==='filters'?'适用于支持自定义滤镜 v4 的 Sony A7R V 固件。':'相机使用 R5S；WAV 文件可在本页转换。'}</span><a href={repo}>GitHub 源码 <ExternalLink size={12}/></a></footer></main><Toaster position="bottom-center" richColors closeButton/></>;
}
createRoot(document.getElementById('root')).render(<App/>);
