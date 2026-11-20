const RAW='https://raw.githubusercontent.com/';
const CDN=['https://cdn.jsdelivr.net/gh/'];
let preferred=0;
export function resourceSources(url){
 const parsed=new URL(url,'https://local.invalid');
 let match;
 if(parsed.origin==='https://raw.githubusercontent.com')match=parsed.pathname.match(/^\/([^/]+\/[^/]+)\/([^/]+)\/(.+)$/);
 else if(CDN.some(base=>parsed.origin===new URL(base).origin))match=parsed.pathname.match(/^\/gh\/([^/]+\/[^/@]+)@([^/]+)\/(.+)$/);
 if(!match)return [url];
 const [,repo,ref,path]=match;
 return [...CDN.map(base=>`${base}${repo}@${ref}/${path}${parsed.search}`),`${RAW}${repo}/${ref}/${path}${parsed.search}`];
}
export async function readResource(url,{fetcher=fetch,signal,as='json',timeoutMs=6000,singleSource=false}={}){
 const sources=singleSource?[url]:resourceSources(url),order=sources.map((_,i)=>(i+preferred)%sources.length);
 let last;
 for(const index of order){
  if(signal?.aborted)throw signal.reason||new DOMException('Aborted','AbortError');
  const controller=new AbortController();
  const abort=()=>controller.abort(signal.reason);
  signal?.addEventListener('abort',abort,{once:true});
  const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
   const response=await fetcher(sources[index],{signal:controller.signal,cache:'no-cache'});
   if(!response.ok){
    if(response.status===403||response.status===429)throw Error('资源目录请求受限，请稍后刷新');
    throw Error(`资源读取失败 (${response.status})`);
   }
   const result=await response[as]();
   if(sources.length>1)preferred=index;
   return result;
  }catch(error){if(signal?.aborted)throw signal.reason||error;last=error;}
  finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
 }
 throw Error(`资源加载失败，请检查网络后重试：${last?.message||'连接不可用'}`);
}

// Mutable branch pointers can differ between CDN edges even with a cache-busting query.
export async function readResourceDirectory(url,options={}){
 const sources=resourceSources(url);
 // Read the page's own directory first; remote directories may advance this baseline.
 const local=options.directoryURL?await Promise.allSettled([readResource(options.directoryURL,{...options,singleSource:true})]):[];
 const results=[...local,...await Promise.allSettled(sources.map(source=>readResource(source,{...options,singleSource:true})))];
 if(options.signal?.aborted)throw options.signal.reason||new DOMException('Aborted','AbortError');
 const candidates=results.filter(x=>x.status==='fulfilled').map(x=>x.value);
 if(options.baselineDirectory)candidates.push(options.baselineDirectory);
 const valid=candidates.filter(value=>value?.schema==='r5-resource-directory/1'&&
  /^[a-f0-9]{40}$/.test(value.revision)&&Array.isArray(value.paths)&&
  value.paths.every(p=>typeof p==='string'&&!p.startsWith('/')&&!p.split('/').includes('..')));
 if(!valid.length)throw results.find(x=>x.status==='rejected')?.reason||Error('资源目录不完整，请稍后刷新');
 return valid.sort((a,b)=>(Number(b.revision_time)||0)-(Number(a.revision_time)||0))[0];
}
