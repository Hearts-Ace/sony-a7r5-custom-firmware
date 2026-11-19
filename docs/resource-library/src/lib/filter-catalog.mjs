// Discover resource files at runtime. No generated catalog or Pages rebuild.
export const FILTER_REPOSITORY = 'Hearts-Ace/sony-a7r5-custom-firmware';
const RAW = 'https://raw.githubusercontent.com';
const encodePath = path => path.split('/').map(encodeURIComponent).join('/');

async function json(fetcher, url, signal) {
 const response = await fetcher(url, {signal, cache:'no-cache'});
 if (!response.ok) {
  if (response.status === 403 || response.status === 429) throw Error('资源目录请求受限，请稍后刷新');
  throw Error(`资源读取失败 (${response.status})`);
 }
 return response.json();
}

async function mapLimit(items, count, callback) {
 const result = new Array(items.length); let next = 0;
 await Promise.all(Array.from({length:Math.min(count,items.length)}, async () => {
  while (next < items.length) {const index=next++;result[index]=await callback(items[index]);}
 }));
 return result;
}

export async function loadFilterCatalog({fetcher=fetch, signal, repository=FILTER_REPOSITORY}={}) {
 const api=`https://api.github.com/repos/${repository}`;
 const commit=await json(fetcher,`${api}/commits/main`,signal);
 if (!/^[a-f0-9]{40}$/.test(commit.sha)) throw Error('资源版本信息无效');
 const tree=await json(fetcher,`${api}/git/trees/${commit.sha}?recursive=1`,signal);
 if (tree.truncated || !Array.isArray(tree.tree)) throw Error('资源目录不完整，请稍后刷新');
 const paths=new Set(tree.tree.filter(x=>x.type==='blob').map(x=>x.path));
 const raw=path=>`${RAW}/${repository}/${commit.sha}/${encodePath(path)}`;
 // Folder name is the category; same-stem BIN and JSON form a filter.
 const descriptors=[...paths].filter(p=>/^filters\/[^/]+\/[^/]+\.json$/.test(p));
 for(const path of paths)if(/^filters\/[^/]+\/[^/]+\.bin$/.test(path)&&!paths.has(path.replace(/\.bin$/,'.json')))throw Error(`缺少滤镜描述：${path}`);
 if (!descriptors.length) throw Error('资源目录中暂无滤镜');
 const catalog=await mapLimit(descriptors,8,async path=>{
  const bin=path.replace(/\.json$/,'.bin');
  if(!paths.has(bin))throw Error(`缺少滤镜 BIN：${path}`);
  const item=await json(fetcher,raw(path),signal);
  if(item.schema!=='r5-filter-description/1' || typeof item.id!=='string' || !item.id ||
     typeof item.name!=='string' || !item.name || typeof item.short_name!=='string' || !item.short_name ||
     !/^[a-f0-9]{64}$/.test(item.sha256) || item.short_name!==path.split('/').at(-1).slice(0,-5))throw Error(`滤镜描述无效：${path}`);
  if(item.preview && (!paths.has(item.preview) || !item.preview.startsWith('filters/')))throw Error(`缺少预览图片：${path}`);
  return {...item,category:path.split('/')[1],series:item.series||path.split('/')[1],
   version:item.updated||'',json:raw(path),bin:raw(bin),preview:item.preview?raw(item.preview):undefined};
 });
 if(new Set(catalog.map(x=>x.id)).size!==catalog.length)throw Error('滤镜 ID 重复');
 if(new Set(catalog.map(x=>x.short_name)).size!==catalog.length)throw Error('滤镜菜单简称重复');
 catalog.sort((a,b)=>(a.order??10000)-(b.order??10000)||a.category.localeCompare(b.category)||a.name.localeCompare(b.name));
 const bundlePath='filter-bundles/常用十二款.json';
 let bundle=null;
 if(paths.has(bundlePath)){
  bundle=await json(fetcher,raw(bundlePath),signal);
  const bin='filter-bundles/常用十二款.bin';
  if(!paths.has(bin)||bundle.schema!=='r5-filter-bundle/1'||!/^[a-f0-9]{64}$/.test(bundle.sha256)||
     !Array.isArray(bundle.filters)||bundle.filters.length!==12||bundle.filters.some(id=>!catalog.some(c=>c.id===id)))throw Error('十二款合并包描述无效');
  bundle={...bundle,bin:raw(bin),json:raw(bundlePath)};
 }
 let simulationError=null;
 const errorPath='resource-info/simulation-error.json';
 if(paths.has(errorPath)){
  simulationError=await json(fetcher,raw(errorPath),signal);
  if(simulationError.schema!=='r5-simulation-error/1'||!['mean','p95','maximum','samples'].every(k=>Number.isFinite(simulationError[k])))throw Error('模拟误差说明无效');
 }
 return {catalog,bundle,simulationError,revision:commit.sha};
}
