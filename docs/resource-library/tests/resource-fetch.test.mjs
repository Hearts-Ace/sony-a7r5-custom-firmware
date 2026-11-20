import test from 'node:test';
import assert from 'node:assert/strict';
import {readResource,resourceSources,readResourceDirectory} from '../src/lib/resource-fetch.mjs';
const url='https://raw.githubusercontent.com/Hearts-Ace/sony-a7r5-custom-firmware/abc/filters/A/NC.bin';
test('keeps the exact revision, encoded path and query across sources',()=>{
 const sources=resourceSources(url+'?check=123');
 assert.equal(sources.length,2);
 assert.ok(sources[0].includes('@abc/filters/A/NC.bin?check=123'));
});
test('retries body connection failures and reads identical binary bytes',async()=>{
 const urls=[];
 const data=new Uint8Array([1,2,3]).buffer;
 const result=await readResource(url,{as:'arrayBuffer',fetcher:async u=>{
  urls.push(u);return {ok:true,arrayBuffer:async()=>{if(urls.length===1)throw new TypeError('connection reset');return data;}};
 }});
 assert.equal(urls.length,2);assert.equal(result,data);
});
test('falls back on HTTP failure',async()=>{
 let calls=0;
 assert.deepEqual(await readResource(url,{fetcher:async()=>++calls===1?{ok:false,status:503}:{ok:true,json:async()=>({ok:true})}}),{ok:true});
 assert.equal(calls,2);
});
test('cancellation never starts another source',async()=>{
 const controller=new AbortController();let calls=0;
 await assert.rejects(readResource(url,{signal:controller.signal,fetcher:async()=>{calls++;controller.abort();throw new Error('aborted');}}));
 assert.equal(calls,1);
});
test('times out a stalled source and advances to the next',async()=>{
 let calls=0;
 const value=await readResource(url,{timeoutMs:10,fetcher:async(u,{signal})=>{
  if(++calls>1)return {ok:true,json:async()=>42};
  return new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(new Error('timeout')),{once:true}));
 }});
 assert.equal(value,42);assert.equal(calls,2);
});

test('mutable directory selects the latest publication rather than the first stale CDN',async()=>{
 const directory={schema:'r5-resource-directory/1',paths:[]};
 const result=await readResourceDirectory(url,{fetcher:async u=>{
  const fresh=u.startsWith('https://cdn.');
  return {ok:true,json:async()=>({...directory,revision:(fresh?'b':'a').repeat(40),revision_time:fresh?200:100})};
 }});
 assert.equal(result.revision,'b'.repeat(40));
});

test('legacy directories without timestamps cannot beat the deployment baseline',async()=>{
 const paths=count=>Array.from({length:count},(_,i)=>`filters/A/F${i}.bin`);
 const legacy={schema:'r5-resource-directory/1',revision:'a'.repeat(40),paths:paths(98)};
 const fresh={schema:'r5-resource-directory/1',revision:'b'.repeat(40),paths:paths(146)};
 const baselineDirectory={...fresh,revision_time:300};
 for(const onlyFastly of [false,true]){
  const result=await readResourceDirectory(url,{baselineDirectory,fetcher:async u=>{
   if(u.startsWith('https://raw.'))throw Error('connection reset');
   return {ok:true,json:async()=>u.startsWith('https://cdn.')?legacy:fresh};
  }});
  assert.equal(result.revision,baselineDirectory.revision);
  assert.equal(result.paths.length,146);
 }
});
test('a newer publication may remove filters and still replace the baseline',async()=>{
 const baselineDirectory={schema:'r5-resource-directory/1',revision:'a'.repeat(40),revision_time:100,paths:['filters/A/NC.bin']};
 const newer={...baselineDirectory,revision:'b'.repeat(40),revision_time:200,paths:[]};
 const result=await readResourceDirectory(url,{baselineDirectory,fetcher:async()=>({ok:true,json:async()=>newer})});
 assert.equal(result.revision,newer.revision);
 assert.equal(result.paths.length,0);
});

test('same-origin directory is requested first; Fastly is never requested',async()=>{
 const requests=[];
 const directory={schema:'r5-resource-directory/1',revision:'d'.repeat(40),revision_time:400,paths:[]};
 const result=await readResourceDirectory(url,{directoryURL:'/resource-directory.json',fetcher:async u=>{
  requests.push(u);assert.ok(!u.includes('fastly.jsdelivr.net'));
  return {ok:true,json:async()=>directory};
 }});
 assert.equal(requests[0],'/resource-directory.json');
 assert.equal(result.revision,directory.revision);
 assert.equal(requests.length,3);
});
