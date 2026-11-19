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
  if(url.endsWith('/commits/main'))data={sha:commit};
  else if(url.includes('/git/trees/'))data={truncated,tree:Object.keys(files).map(path=>({type:'blob',path}))};
  else{const path=decodeURIComponent(url.split(`/${commit}/`)[1]||'');assert.ok(path in files,`missing mock ${path}`);data=files[path];}
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
 assert.equal(mock.requests.filter(r=>r.url.startsWith('https://api.github.com/')).length,4);
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
test('discovers current twelve-filter bundle separately from categories',async()=>{
 const ids=Array.from({length:12},(_,i)=>'F'+i),files={};
 for(const id of ids){files[`filters/A/${id}.json`]=filter(id);files[`filters/A/${id}.bin`]='BIN';}
 files['filter-bundles/常用十二款.bin']='BIN';
 files['filter-bundles/常用十二款.json']={schema:'r5-filter-bundle/1',name:'常用十二款',filters:ids,sha256:hash};
 const result=await loadFilterCatalog(server(files));assert.equal(result.catalog.length,12);
 assert.ok(result.bundle.bin.includes(encodeURIComponent('常用十二款')));
});
