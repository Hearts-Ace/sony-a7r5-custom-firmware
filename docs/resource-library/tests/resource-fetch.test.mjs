import test from 'node:test';
import assert from 'node:assert/strict';
import {readResource,resourceSources} from '../src/lib/resource-fetch.mjs';
const url='https://raw.githubusercontent.com/Hearts-Ace/sony-a7r5-custom-firmware/abc/filters/A/NC.bin';
test('keeps the exact revision, encoded path and query across sources',()=>{
 const sources=resourceSources(url+'?check=123');
 assert.equal(sources.length,3);
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
