import{mkdir,cp,copyFile,rm}from'node:fs/promises';
await mkdir('public',{recursive:true});
await cp('data','public/data',{recursive:true});
await rm('public/data/audio',{recursive:true,force:true});
await mkdir('public/sounds',{recursive:true});
// On GitHub, the root /sounds is canonical. Local working copy retains the same catalog.
const {existsSync}=await import('node:fs');
const source=existsSync('../../sounds/catalog.json')?'../../sounds':'sounds';
const {readdir}=await import('node:fs/promises');for(const f of await readdir(source)){if(f.endsWith('.R5S')||f==='catalog.json')await copyFile(`${source}/${f}`,`public/sounds/${f}`);}
await copyFile('kernel.json','public/kernel.json');
