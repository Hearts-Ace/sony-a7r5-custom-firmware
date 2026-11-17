import {useEffect,useRef,useState} from 'react';
import {AudioLines, CircleAlert, Clock3, Download, FileAudio, Headphones, Pause, Play, Upload} from 'lucide-react';
import {Button} from '@/components/ui/button';
import {convertWav} from '../audio-codec.mjs';
import {download,previewWav,resourceURL,verifiedResource} from '@/lib/resources';
import {toast} from 'sonner';
const seconds=n=>`${n.toFixed(2)} 秒`;
function Waveform({blob}){
 const host=useRef(null),instance=useRef(null);const [ready,setReady]=useState(false),[playing,setPlaying]=useState(false),[error,setError]=useState(''),[duration,setDuration]=useState(0),[time,setTime]=useState(0);
 useEffect(()=>{if(!blob)return;let alive=true,ws;setReady(false);setPlaying(false);setError('');setTime(0);setDuration(0);
 (async()=>{try{const {default:WaveSurfer}=await import('wavesurfer.js');if(!alive)return;ws=WaveSurfer.create({container:host.current,height:74,waveColor:'#adbddb',progressColor:'#234fbd',cursorColor:'#234fbd',cursorWidth:1,barWidth:3,barGap:2,barRadius:3,normalize:true});instance.current=ws;ws.on('ready',d=>{if(alive){setDuration(d);setReady(true);}});ws.on('play',()=>setPlaying(true));ws.on('pause',()=>setPlaying(false));ws.on('timeupdate',setTime);await ws.loadBlob(blob);}catch(e){if(alive)setError('无法生成试听波形。');}})();
 return()=>{alive=false;ws?.destroy();instance.current=null;};},[blob]);
 return <div className="wave-player"><div className="wave-controls"><Button size="icon" variant="secondary" aria-label={playing?'暂停试听':'播放试听'} disabled={!ready} onClick={()=>instance.current?.playPause().catch(()=>setError('播放未启动，请重试。'))}>{playing?<Pause size={16}/>:<Play size={16}/>}</Button><span>{ready?`${time.toFixed(2)} / ${duration.toFixed(2)} 秒`:'正在读取波形…'}</span></div><div className="wave-host" aria-hidden="true" ref={host}/>{error&&<p className="inline-error" role="alert">{error}</p>}</div>;
}
export function SoundLibrary({catalog,loading,error}){
 const [chosen,setChosen]=useState(null),[clip,setClip]=useState(null),[clipStatus,setClipStatus]=useState(''),[file,setFile]=useState(null),[working,setWorking]=useState(false);const fileInput=useRef(null);const current=useRef(0);
 useEffect(()=>()=>{current.current++;},[]);
 async function select(item){const n=++current.current;setChosen(item);setClip(null);setClipStatus('正在读取音频…');try{const data=await verifiedResource(item,item.file);if(n!==current.current)return;setClip(new Blob([previewWav(data)],{type:'audio/wav'}));setClipStatus('');}catch(e){if(n===current.current)setClipStatus(e.message);}}
 async function soundDownload(item){try{download(await verifiedResource(item,item.file),`${item.id}.R5S`);}catch(e){toast.error(e.message);}}
 async function convert(){if(!file)return;setWorking(true);try{const r=await fetch(resourceURL('kernel.json'));if(!r.ok)throw Error('读取转换数据失败');const out=await convertWav(await file.arrayBuffer(),await r.json());download(out,`${file.name.replace(/\.wav$/i,'')}.R5S`);toast.success('已生成 R5S，包含十档音量');}catch(e){toast.error(e.message);}finally{setWorking(false);}}
 return <div className="sound-workspace" id="sound-library"><section className="catalog-panel sound-list" aria-labelledby="sounds-title"><div className="panel-title"><div><h2 id="sounds-title">快门声音</h2><p>{catalog.length} 款现成 R5S</p></div><Headphones className="panel-icon" size={22}/></div>
 {loading?<p className="empty-state" role="status">正在加载声音…</p>:error?<p className="empty-state" role="alert">{error}，请刷新重试。</p>:<ul>{catalog.map(x=><li key={x.id} className={`sound-row ${chosen?.id===x.id?'active':''}`}><button aria-pressed={chosen?.id===x.id} onClick={()=>select(x)}><AudioLines size={18}/><strong>{x.name}</strong><small><Clock3 size={13}/>{seconds(x.duration)}</small></button><Button variant="ghost" size="icon" aria-label={`下载 ${x.name}`} title="下载 R5S" onClick={()=>soundDownload(x)}><Download size={17}/></Button></li>)}</ul>}</section>
 <aside className="sound-side"><section className="catalog-panel audio-preview" aria-labelledby="preview-title"><div className="panel-title"><div><div className="panel-kicker"><AudioLines size={15}/> 试听</div><h2 id="preview-title">{chosen?.name??'声音预览'}</h2></div></div>{clip?<Waveform blob={clip}/>:<p className="empty-state" role="status">{clipStatus||'从声音列表选择一款，查看波形并试听。'}</p>}{clip&&<p className="wave-note">试听采用 R5S 中的 50% 音量档。</p>}</section>
 <section className="catalog-panel converter" aria-labelledby="convert-title"><div className="panel-title"><div><h2 id="convert-title">转换本地 WAV</h2><p>生成相机使用的十档音量 R5S。</p></div><FileAudio className="panel-icon" size={21}/></div>
 <input className="sr-only" ref={fileInput} type="file" id="audio-file" aria-label="选择本地 PCM WAV" accept=".wav,audio/wav" disabled={working} onChange={e=>{const f=e.target.files?.[0];if(f&&f.size>1048576){toast.error('WAV 不得超过 1 MiB');e.target.value='';setFile(null);}else setFile(f??null);}}/>
 <Button variant="outline" className="file-picker" disabled={working} onClick={()=>fileInput.current.click()}><Upload size={17}/><span>{file?.name??'选择 PCM WAV'}</span></Button>
 {file&&<Waveform key={`${file.name}/${file.lastModified}`} blob={file}/>}
 <div className="converter-note"><CircleAlert size={15}/><p>最长 2 秒，最大 1 MiB。文件只在浏览器处理。</p></div><Button className="convert-download" disabled={!file||working} onClick={convert}><Download size={17}/>{working?'正在转换…':'转换并下载 R5S'}</Button></section></aside></div>;
}
