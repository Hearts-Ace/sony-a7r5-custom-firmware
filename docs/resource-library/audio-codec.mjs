import{crc32}from './codec.mjs';
const trunc=Math.trunc;
export async function convertWav(buffer,packed){
 const a=new Uint8Array(buffer),d=new DataView(buffer),text=(p,n)=>String.fromCharCode(...a.slice(p,p+n));
 if(a.length<12||a.length>1048576||text(0,4)!=='RIFF'||text(8,4)!=='WAVE'||d.getUint32(4,true)+8!==a.length)throw Error('请选择不超过 1 MiB 的完整 PCM WAV');
 let fmt=null,data=null;
 for(let p=12;p<a.length;){if(p+8>a.length)throw Error('WAV 块不完整');const n=d.getUint32(p+4,true),start=p+8,end=start+n+(n&1);if(end>a.length)throw Error('WAV 数据被截断');const t=text(p,4);if(t==='fmt '){if(fmt||![16,18].includes(n)||d.getUint16(start,true)!==1||(n===18&&d.getUint16(start+16,true)))throw Error('仅支持 PCM WAV');fmt={channels:d.getUint16(start+2,true),rate:d.getUint32(start+4,true),align:d.getUint16(start+12,true),bits:d.getUint16(start+14,true),byteRate:d.getUint32(start+8,true)};}else if(t==='data'){if(data||!n)throw Error('WAV 数据块无效');data={start,n};}p=end;}
 if(!fmt||!data||![1,2].includes(fmt.channels)||![8,16,24,32].includes(fmt.bits)||fmt.rate<8000||fmt.rate>192000||fmt.align!==fmt.channels*fmt.bits/8||fmt.byteRate!==fmt.rate*fmt.align||data.n%fmt.align)throw Error('WAV 参数不受支持');
 const sourceFrames=data.n/fmt.align;if(!sourceFrames||sourceFrames>fmt.rate*2)throw Error('快门声必须在 2 秒以内');const frames=Math.ceil(sourceFrames*24000/fmt.rate),encoded=Math.ceil(frames/31)*32;
 let value=13421773,step=-3542,d2=-7079,d3=10,index=0;const kernel=[value,value+=step];step+=d2;kernel.push(value+=step);d2+=d3;step+=d2;kernel.push(value+=step);
 const nibble=()=>{const v=packed[index>>1],n=index++&1;return n?v>>4:v&15;};
 for(let i=4;i<769;i++){let delta=nibble();if(delta===8){delta=nibble();delta=delta<5?delta+8:-delta-3;}else if(delta>8)delta-=16;d3+=delta;d2+=d3;step+=d2;kernel.push(value+=step);}
 const mono=new Int32Array(sourceFrames),bytes=fmt.bits/8;
 function decode(p){if(fmt.bits===8)return(a[p]-128)*256;if(fmt.bits===16)return d.getInt16(p,true);if(fmt.bits===24){let v=a[p]|a[p+1]<<8|a[p+2]<<16;if(v>=8388608)v-=16777216;return trunc(v/256);}return trunc(d.getInt32(p,true)/65536);}
 for(let i=0;i<sourceFrames;i++){const p=data.start+i*fmt.align;mono[i]=fmt.channels===1?decode(p):trunc((decode(p)+decode(p+bytes))/2);}
 const Q=16777216,scale=fmt.rate>24000?Math.floor(24000*Q/fmt.rate):Q,half=fmt.rate>24000?Math.ceil(12*fmt.rate/24000):12,pcm=new Int32Array(frames);let center=0,phase=0,last=-1,weights=[],sum=0,peak=0;
 for(let i=0;i<frames;i++){if(phase!==last){last=phase;weights=[];sum=0;for(let j=0;j<=2*half;j++){const x=-half*Q-trunc(phase*Q/24000)+j*Q,distance=Math.floor(Math.abs(x)*scale/Q),k=Math.floor(distance/262144),f=distance%262144,w=k>=768?0:kernel[k]+trunc((kernel[k+1]-kernel[k])*f/262144);weights.push(w);sum+=w;}}let acc=0;for(let j=0;j<weights.length;j++)acc+=mono[Math.max(0,Math.min(sourceFrames-1,center+j-half))]*weights[j];const v=trunc(acc/sum);pcm[i]=v;peak=Math.max(peak,Math.abs(v));const p=phase+fmt.rate;center+=Math.floor(p/24000);phase=p%24000;}
 const denominator=Math.max(peak,32768),out=new Uint8Array(416+10*encoded),v=new DataView(out.buffer);out.set(new TextEncoder().encode('R5SNDF0\0'));[1,416,out.length,24000,frames,encoded,10,0].forEach((x,i)=>v.setUint32(8+4*i,x,true));out.set(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),40);
 for(let volume=1;volume<=10;volume++){const base=416+(volume-1)*encoded;for(let start=0;start<frames;start+=31){const samples=[];let peak=0;for(let i=start;i<Math.min(frames,start+31);i++){const n=trunc(trunc(pcm[i]*7864/denominator)*volume/5);samples.push(n);peak=Math.max(peak,Math.abs(n));}let shift=0;while(shift<7&&peak>(127<<shift))shift++;const pos=base+Math.floor(start/31)*32;out[pos]=shift;samples.forEach((n,i)=>{let q=Math.floor((Math.abs(n)+(shift?1<<(shift-1):0))/(1<<shift));q=Math.min(q,n<0?128:127);out[pos+1+i]=n<0?-q:q;});}out.set(new Uint8Array(await crypto.subtle.digest('SHA-256',out.slice(base,base+encoded))),96+(volume-1)*32);}
 v.setUint32(72,crc32(out.slice(0,416)),true);return out;
}
