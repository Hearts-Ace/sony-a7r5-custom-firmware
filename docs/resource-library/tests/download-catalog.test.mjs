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

test('model cards retain R5 source metrics and read only the shared operator summary',async()=>{
 const metrics={status:'available',mean:1,p95:2,maximum:3,samples:62715};
 const simulation={schema:'r5-simulation-error/1',mean:.2,p95:.5,maximum:1.5,samples:1627};
 const directory={...baselineDirectory,paths:[...baselineDirectory.paths,'resource-info/simulation-error.json']};
 const requests=[];
 const result=await loadDownloadCatalog('c2',{baselineDirectory:directory,directoryURL:'/resource-directory.json',localBase:'/',fetcher:async url=>{
  requests.push(url);
  if(url.includes('directory.json'))return {ok:true,json:async()=>directory};
  if(url.endsWith('simulation-error.json'))return {ok:true,json:async()=>simulation};
  assert.ok(url.startsWith('/c2-filters/')&&url.endsWith('.meta.json'));
  return {ok:true,json:async()=>({schema:'sony-single-filter-download/1',model:'c2',short_name:'NC',name:'Classic Negative',sha256:sha,training_error:metrics,metric_source_model:'r5'})};
 }});
 assert.deepEqual(result.catalog[0].training_error,metrics);
 assert.equal(result.catalog[0].metric_source_model,'r5');assert.deepEqual(result.simulationError,simulation);
 assert.equal(requests.filter(x=>x.endsWith('simulation-error.json')).length,1);
});
