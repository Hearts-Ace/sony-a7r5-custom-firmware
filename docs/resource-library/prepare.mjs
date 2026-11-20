import{mkdir,cp,copyFile,rm}from'node:fs/promises';
await mkdir('public',{recursive:true});
// Filter assets live only in repository /filters and are discovered at runtime.
await rm('public/data',{recursive:true,force:true});
await rm('public/sounds',{recursive:true,force:true});
await mkdir('public/sounds',{recursive:true});
// On GitHub, the root /sounds is canonical. Local working copy retains the same catalog.
const {existsSync}=await import('node:fs');
const source=existsSync('../../sounds/catalog.json')?'../../sounds':'sounds';
const {readdir}=await import('node:fs/promises');for(const f of await readdir(source)){if(f.endsWith('.R5S')||f==='catalog.json')await copyFile(`${source}/${f}`,`public/sounds/${f}`);}
await copyFile('kernel.json','public/kernel.json');
await copyFile('favicon.svg','public/favicon.svg');

// Ship a generated minimum directory with the UI, so legacy CDN caches cannot roll it back.
// Newer directories still arrive dynamically; resource-only releases need no page rebuild.
const baselineFile='src/generated/resource-directory.json';
if(existsSync('../../filters')){
 const {execFileSync}=await import('node:child_process');
 const {writeFile}=await import('node:fs/promises');
 const git=(...args)=>execFileSync('git',['-C','../..',...args],{encoding:'utf8'}).trim();
 const revision=git('rev-parse','HEAD');
 const paths=git('-c','core.quotepath=false','ls-tree','-r','--name-only',revision,'--','filters','filter-bundles','resource-info').split('\n').filter(Boolean);
 await mkdir('src/generated',{recursive:true});
 await writeFile(baselineFile,JSON.stringify({schema:'r5-resource-directory/1',revision,revision_time:Number(git('show','-s','--format=%ct',revision)),paths}));
}else if(!existsSync(baselineFile)){
 throw Error('Missing public resource tree; build from the public repository or copy its generated directory for local preview.');
}

await copyFile(baselineFile,'public/resource-directory.json');
