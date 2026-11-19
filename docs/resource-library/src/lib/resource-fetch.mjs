const RAW='https://raw.githubusercontent.com/';
const CDN=['https://fastly.jsdelivr.net/gh/','https://cdn.jsdelivr.net/gh/'];
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
export async function readResource(url,{fetcher=fetch,signal,as='json',timeoutMs=6000}={}){
 const sources=resourceSources(url),order=sources.map((_,i)=>(i+preferred)%sources.length);
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
