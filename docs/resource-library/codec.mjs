export function crc32(bytes){let c=0xffffffff;for(const b of bytes){c^=b;for(let k=0;k<8;k++)c=(c>>>1)^((c&1)?0xedb88320:0);}return(c^0xffffffff)>>>0;}
export function mergeBins(inputs){
 if(!inputs.length||inputs.length>12)throw Error('请选择 1–12 个滤镜');
 const arrays=inputs.map(x=>new Uint8Array(x));
 const first=arrays[0], out=new Uint8Array(128+2452*arrays.length),v=new DataView(out.buffer);
 arrays.forEach(a=>{const d=new DataView(a.buffer,a.byteOffset,a.byteLength);if(a.length!==2580||String.fromCharCode(...a.slice(0,8))!=='R5CUST4\0'||d.getUint32(8,true)!==4||d.getUint32(12,true)!==128||d.getUint32(16,true)!==2580||d.getUint32(20,true)!==1)throw Error('单滤镜文件格式不兼容');let copy=a.slice();new DataView(copy.buffer).setUint32(112,0,true);if(crc32(copy)!==d.getUint32(112,true))throw Error('滤镜文件校验失败');if(a.slice(32,112).some((x,i)=>x!==first[32+i]))throw Error('滤镜机型或固件基线不同');});
 out.set(first.slice(0,128));v.setUint32(16,out.length,true);v.setUint32(20,arrays.length,true);v.setUint32(24,(1<<arrays.length)-1,true);v.setUint32(112,0,true);
 arrays.forEach((a,i)=>{out.set(a.slice(128),128+i*2452);v.setUint32(128+i*2452,i+1,true);});v.setUint32(112,crc32(out),true);return out;
}
