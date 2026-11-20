import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {loadDownloadCatalog,readDownload} from '../src/lib/download-catalog.mjs';
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const revision='a'.repeat(40),sha='b'.repeat(64);
const baselineDirectory={schema:'r5-resource-directory/1',revision,revision_time:300,paths:['c2-filters/富士数码/NC.a7look','c2-filters/富士数码/NC.meta.json','m4-filters/富士数码/NC.json','m4-filters/富士数码/NC.meta.json']};
test('model catalogs use same-site metadata and never prefetch filter payloads',async()=>{
 for(const model of ['c2','m4']){
  const requests=[];
  const result=await loadDownloadCatalog(model,{baselineDirectory,directoryURL:'/resource-directory.json',localBase:'/',fetcher:async url=>{
   requests.push(url);
   if(url.includes('directory.json'))return {ok:true,json:async()=>baselineDirectory};
   assert.ok(url.startsWith('/'+model+'-filters/'));assert.ok(url.endsWith('.meta.json'));
   return {ok:true,json:async()=>({schema:'sony-single-filter-download/1',model,short_name:'NC',name:'Classic Negative',sha256:sha})};
  }});
  assert.equal(result.catalog.length,1);
  assert.equal(result.catalog[0].filename,model==='c2'?'NC.a7look':'NC.json');
  assert.ok(result.catalog[0].sources[0].startsWith('/'+model+'-filters/'));
  assert.equal(requests.filter(x=>!x.includes('directory.json')).length,1);
 }
});
test('download verifies bytes and retries the pinned CDN when local bytes are stale',async()=>{
 const data=new TextEncoder().encode('{"format":"valid"}');
 const hash=Buffer.from(await crypto.subtle.digest('SHA-256',data)).toString('hex');
 const calls=[];
 const result=await readDownload({sha256:hash,sources:['/local','https://cdn.example/file']},{fetcher:async url=>{calls.push(url);return {ok:true,arrayBuffer:async()=>url==='/local'?new Uint8Array([1]).buffer:data.buffer};}});
 assert.deepEqual(new Uint8Array(result),data);assert.equal(calls.length,2);
});
