import test from 'node:test';
import assert from 'node:assert/strict';
import {loadFilterCatalog} from '../src/lib/filter-catalog.mjs';
const commit='a'.repeat(40),hash='b'.repeat(64);
function filter(id){return {schema:'r5-filter-description/1',id,name:id,short_name:id,sha256:hash};}
function server(files,{truncated=false,status=200}={}){
 const requests=[];
 const fetcher=async(url,options)=>{
  requests.push({url,options});
  let data;
  if(/[@/]resource-index\/directory\.json$/.test(new URL(url).pathname))data=truncated?{}:{schema:'r5-resource-directory/1',revision:commit,paths:Object.keys(files)};
  else{const path=decodeURIComponent(url.split(new URL(url).hostname==='raw.githubusercontent.com'?`/${commit}/`:`@${commit}/`)[1]||'');assert.ok(path in files,`missing mock ${path}`);data=files[path];}
  return {ok:status===200,status,json:async()=>data};
 };
 return {fetcher,requests};
}
test('discovers a newly added category and filter without catalog/build changes',async()=>{
 const files={'filters/富士数码/NC.json':filter('NC'),'filters/富士数码/NC.bin':'BIN'};
 const mock=server(files);let result=await loadFilterCatalog(mock);
 assert.equal(result.catalog.length,1);assert.equal(result.catalog[0].category,'富士数码');
 assert.ok(result.catalog[0].bin.includes(`/${commit}/filters/`));
 files['filters/New Film/TX400.json']=filter('TX400');files['filters/New Film/TX400.bin']='BIN';
 result=await loadFilterCatalog(mock);assert.equal(result.catalog.length,2);
 assert.equal(result.catalog.find(c=>c.id==='TX400').category,'New Film');
 assert.equal(mock.requests.filter(r=>r.url.startsWith('https://api.github.com/')).length,0);
 assert.ok(mock.requests.every(r=>r.options.cache==='no-cache'));
});
test('fails clearly on missing BIN and missing descriptor',async()=>{
 await assert.rejects(loadFilterCatalog(server({'filters/A/NC.json':filter('NC')})),/缺少滤镜 BIN/);
 await assert.rejects(loadFilterCatalog(server({'filters/A/NC.bin':'BIN'})),/缺少滤镜描述/);
});
test('rejects duplicate identifiers and stale metadata names',async()=>{
 await assert.rejects(loadFilterCatalog(server({'filters/A/NC.json':filter('NC'),'filters/A/NC.bin':'BIN','filters/B/NC.json':filter('NC'),'filters/B/NC.bin':'BIN'})),/ID 重复/);
 await assert.rejects(loadFilterCatalog(server({'filters/A/NC.json':filter('CC'),'filters/A/NC.bin':'BIN'})),/描述无效/);
});
test('does not serve a partial tree or silently hide rate limits',async()=>{
 await assert.rejects(loadFilterCatalog(server({}, {truncated:true})),/目录不完整/);
 await assert.rejects(loadFilterCatalog(server({}, {status:403})),/请求受限/);
});
test('does not fetch or expose repository bundles in the page catalog',async()=>{
 const ids=Array.from({length:12},(_,i)=>'F'+i),files={};
 for(const id of ids){files[`filters/A/${id}.json`]=filter(id);files[`filters/A/${id}.bin`]='BIN';}
 files['filter-bundles/常用十二款.bin']='BIN';
 files['filter-bundles/常用十二款.json']={schema:'r5-filter-bundle/1',name:'常用十二款',filters:ids,sha256:hash};
 const mock=server(files),result=await loadFilterCatalog(mock);assert.equal(result.catalog.length,12);
 assert.equal('bundle' in result,false);
 assert.equal(mock.requests.some(r=>r.url.includes('/filter-bundles/')),false);
});
test('loads the whole catalog when raw GitHub is blocked',async()=>{
 const mock=server({'filters/A/NC.json':filter('NC'),'filters/A/NC.bin':'BIN'});
 const fetcher=async(url,options)=>{assert.ok(!url.startsWith('https://raw.githubusercontent.com/'));return mock.fetcher(url,options);};
 assert.equal((await loadFilterCatalog({fetcher})).catalog[0].id,'NC');
});

test('unchanged directory reuses the catalog; a new revision reloads metrics',async()=>{
 const files={'filters/A/NC.json':filter('NC'),'filters/A/NC.bin':'BIN'};
 const mock=server(files),previous=await loadFilterCatalog(mock);
 mock.requests.length=0;
 assert.equal(await loadFilterCatalog({...mock,previous}),previous);
 assert.equal(mock.requests.length,3);
 files['filters/A/NC.json']={...filter('NC'),training_error:{mean:1.057279}};
 const next='c'.repeat(40);
 const fetcher=async(url,options)=>{
  const response=await mock.fetcher(url.replaceAll(next,commit),options);
  if(url.includes('/directory.json'))return {...response,json:async()=>({...await response.json(),revision:next})};
  return response;
 };
 const result=await loadFilterCatalog({fetcher,previous});
 assert.equal(result.revision,next);
 assert.equal(result.catalog[0].training_error.mean,1.057279);
 assert.notEqual(result,previous);
});

test('publishes usable cards before a slow descriptor finishes; no BIN is prefetched',async()=>{
 const files={'filters/A/NC.json':filter('NC'),'filters/A/NC.bin':'BIN','filters/A/CC.json':filter('CC'),'filters/A/CC.bin':'BIN'};
 const mock=server(files),snapshots=[];
 let release,firstCard;
 const blocked=new Promise(resolve=>{release=resolve;});
 const visible=new Promise(resolve=>{firstCard=resolve;});
 const pending=loadFilterCatalog({fetcher:async(url,options)=>{
  if(url.endsWith('/CC.json'))await blocked;
  return mock.fetcher(url,options);
 },onProgress:partial=>{snapshots.push(partial);if(partial.catalog.length===1)firstCard();}});
 await visible;
 assert.equal(snapshots.at(-1).catalog[0].id,'NC');
 assert.equal(snapshots.at(-1).total,2);
 release();
 const result=await pending;
 assert.equal(result.catalog.length,2);
 assert.deepEqual(snapshots[0],{catalog:[],total:2});
 assert.equal(mock.requests.some(x=>x.url.endsWith('.bin')),false);
});
