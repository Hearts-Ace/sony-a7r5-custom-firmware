import {readResource,readResourceDirectory,resourceSources} from './resource-fetch.mjs';
const RAW='https://raw.githubusercontent.com/Hearts-Ace/sony-a7r5-custom-firmware';
const encoded=path=>path.split('/').map(encodeURIComponent).join('/');
export async function loadDownloadCatalog(model,{fetcher=fetch,signal,baselineDirectory,directoryURL,localBase,onProgress}={}){
 if(!['c2','m4'].includes(model))throw Error('未知机型');
 const directory=await readResourceDirectory(`${RAW}/resource-index/directory.json?check=${Date.now()}`,{fetcher,signal,baselineDirectory,directoryURL});
 const paths=new Set(directory.paths),root=model+'-filters';
 const descriptors=[...paths].filter(p=>p.startsWith(root+'/')&&p.split('/').length===3&&p.endsWith('.meta.json'));
 const catalog=[];let next=0,stopped=false;
 const sort=items=>[...items].sort((a,b)=>(a.order??10000)-(b.order??10000)||a.category.localeCompare(b.category)||a.name.localeCompare(b.name));
 const sources=path=>[...(localBase&&directory.revision===baselineDirectory?.revision?[localBase+encoded(path)]:[]),...resourceSources(`${RAW}/${directory.revision}/${encoded(path)}`)];
 const read=async(path)=>{
  let error;
  for(const source of sources(path))try{return await readResource(source,{fetcher,signal,singleSource:true});}catch(e){if(signal?.aborted)throw e;error=e;}
  throw error;
 };
 onProgress?.({catalog:[],total:descriptors.length});
 await Promise.all(Array.from({length:Math.min(6,descriptors.length)},async()=>{
  while(!stopped&&next<descriptors.length){
   const path=descriptors[next++];
   try{
    const item=await read(path),stem=path.slice(0,-10),file=stem+(model==='c2'?'.a7look':'.json');
    if(item.schema!=='sony-single-filter-download/1'||item.model!==model||!paths.has(file)||item.short_name!==stem.split('/').at(-1)||typeof item.name!=='string'||!item.name||!/^[a-f0-9]{64}$/.test(item.sha256))throw Error('滤镜描述无效：'+path);
    if(catalog.some(x=>x.short_name===item.short_name))throw Error('重复滤镜简称');
    catalog.push({...item,category:path.split('/')[1],file,filename:file.split('/').at(-1),sources:sources(file)});
    if(!stopped&&(catalog.length===1||catalog.length%6===0||catalog.length===descriptors.length))onProgress?.({catalog:sort(catalog),total:descriptors.length});
   }catch(e){stopped=true;throw e;}
  }
 }));
 return {catalog:sort(catalog),total:catalog.length,revision:directory.revision};
}
export async function readDownload(item,{fetcher=fetch,signal}={}){
 let error;
 for(const source of item.sources){
  try{
   const data=await readResource(source,{fetcher,signal,as:'arrayBuffer',singleSource:true});
   const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',data))].map(x=>x.toString(16).padStart(2,'0')).join('');
   if(hash!==item.sha256)throw Error('文件校验失败');
   return data;
  }catch(e){if(signal?.aborted)throw e;error=e;}
 }
 throw Error('下载失败：'+(error?.message||'网络不可用'));
}
