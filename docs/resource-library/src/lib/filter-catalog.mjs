import {readResource,readResourceDirectory} from './resource-fetch.mjs';
// Discover resource files at runtime. No generated catalog or Pages rebuild.
export const FILTER_REPOSITORY = 'Hearts-Ace/sony-a7r5-custom-firmware';
const RAW = 'https://raw.githubusercontent.com';
const encodePath = path => path.split('/').map(encodeURIComponent).join('/');

const json=(fetcher,url,signal)=>readResource(url,{fetcher,signal});

async function mapLimit(items, count, callback, onItem) {
 const result = new Array(items.length); let next = 0, stopped = false;
 await Promise.all(Array.from({length:Math.min(count,items.length)}, async () => {
  while (!stopped && next < items.length) {
   const index=next++;
   try{result[index]=await callback(items[index]);if(!stopped)onItem?.(result[index]);}
   catch(error){stopped=true;throw error;}
  }
 }));
 return result;
}

export async function loadFilterCatalog({fetcher=fetch, signal, repository=FILTER_REPOSITORY, previous, onProgress, baselineDirectory}={}) {
 const directory=await readResourceDirectory(`${RAW}/${repository}/resource-index/directory.json?check=${Date.now()}`,{fetcher,signal,baselineDirectory});
 if(directory.schema!=='r5-resource-directory/1'||!Array.isArray(directory.paths))throw Error('资源目录不完整，请稍后刷新');
 if(!/^[a-f0-9]{40}$/.test(directory.revision))throw Error('资源版本信息无效');
 if(directory.paths.some(p=>typeof p!=='string'||p.startsWith('/')||p.split('/').includes('..')))throw Error('资源路径无效');
 if(previous?.revision===directory.revision || (previous?.revisionTime||0)>(Number(directory.revision_time)||0))return previous;
 const paths=new Set(directory.paths);
 const raw=path=>`${RAW}/${repository}/${directory.revision}/${encodePath(path)}`;
 // Folder name is the category; same-stem BIN and JSON form a filter.
 const descriptors=[...paths].filter(p=>/^filters\/[^/]+\/[^/]+\.json$/.test(p));
 for(const path of paths)if(/^filters\/[^/]+\/[^/]+\.bin$/.test(path)&&!paths.has(path.replace(/\.bin$/,'.json')))throw Error(`缺少滤镜描述：${path}`);
 if (!descriptors.length) throw Error('资源目录中暂无滤镜');
 const compare=(a,b)=>(a.order??10000)-(b.order??10000)||a.category.localeCompare(b.category)||a.name.localeCompare(b.name);
 const ready=[],ids=new Set(),names=new Set();
 const progress=()=>onProgress?.({catalog:[...ready].sort(compare),total:descriptors.length});
 progress();
 const catalog=await mapLimit(descriptors,8,async path=>{
  const bin=path.replace(/\.json$/,'.bin');
  if(!paths.has(bin))throw Error(`缺少滤镜 BIN：${path}`);
  const item=await json(fetcher,raw(path),signal);
  if(item.schema!=='r5-filter-description/1' || typeof item.id!=='string' || !item.id ||
     typeof item.name!=='string' || !item.name || typeof item.short_name!=='string' || !item.short_name ||
     !/^[a-f0-9]{64}$/.test(item.sha256) || item.short_name!==path.split('/').at(-1).slice(0,-5))throw Error(`滤镜描述无效：${path}`);
  if(item.preview && (!paths.has(item.preview) || !item.preview.startsWith('filters/')))throw Error(`缺少预览图片：${path}`);
  if(ids.has(item.id))throw Error('滤镜 ID 重复');
  if(names.has(item.short_name))throw Error('滤镜菜单简称重复');
  ids.add(item.id);names.add(item.short_name);
  return {...item,category:path.split('/')[1],series:item.series||path.split('/')[1],
   version:item.updated||'',json:raw(path),bin:raw(bin),preview:item.preview?raw(item.preview):undefined};
 },item=>{
  ready.push(item);
  if(ready.length===1||ready.length%8===0||ready.length===descriptors.length)progress();
 });
 catalog.sort(compare);
 let simulationError=null;
 const errorPath='resource-info/simulation-error.json';
 if(paths.has(errorPath)){
  simulationError=await json(fetcher,raw(errorPath),signal);
  if(simulationError.schema!=='r5-simulation-error/1'||!['mean','p95','maximum','samples'].every(k=>Number.isFinite(simulationError[k])))throw Error('模拟误差说明无效');
 }
 return {catalog,total:catalog.length,simulationError,revision:directory.revision,revisionTime:Number(directory.revision_time)||0};
}
