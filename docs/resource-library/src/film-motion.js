import {useEffect,useState} from 'react';

// Scroll velocity tilts the complete filter panel; at rest it returns to its plane.
export function useFilmMotion(enabled){
 const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches);
 useEffect(()=>{const media=window.matchMedia('(prefers-reduced-motion: reduce)');const change=()=>setReduced(media.matches);media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);
 useEffect(()=>{
  if(!enabled||reduced||!('IntersectionObserver' in window))return;
  const cards=new Map(),visible=new Set();let frame=0,current=0,velocity=0,lastY=window.scrollY,lastScroll=0,lastPaint=0;
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  const flatten=card=>{card.style.removeProperty('transform');card.style.removeProperty('--film-depth');card.style.removeProperty('--film-content-depth');card.style.removeProperty('transform-origin');card.style.removeProperty('will-change');};
  const request=()=>{if(!frame&&!document.hidden)frame=requestAnimationFrame(paint);};
  function paint(now){
   frame=0;if(document.hidden)return;
   const dt=Math.min(40,lastPaint?now-lastPaint:16);lastPaint=now;
   const decay=Math.exp(-Math.max(0,now-lastScroll-80)/210);
   const target=velocity*decay;
   current+=(target-current)*(1-Math.exp(-dt/65));
   if(now-lastScroll>1400||Math.abs(current)<.003&&Math.abs(target)<.003){current=0;for(const card of cards.keys())flatten(card);return;}
   const small=window.innerWidth<760,angle=small?12:20;
   for(const card of visible){
    const item=cards.get(card);if(!item)continue;
    const position=clamp((item.top-window.scrollY+item.height/2-window.innerHeight/2)/(window.innerHeight/2+item.height/2),-1,1);
    const tilt=current*angle*(1+.15*position),turn=current*(small?0:1.4),y=-current*(small?12:22),z=-Math.abs(current)*Math.max(120,item.height*(small?.13:.08)),perspective=Math.max(3000,item.height*2);
    card.style.transformOrigin=`50% ${clamp(window.scrollY+window.innerHeight*.5-item.top,0,item.height).toFixed(1)}px`;
    card.style.transform=`perspective(${perspective.toFixed(0)}px) translate3d(0,${y.toFixed(3)}px,${z.toFixed(3)}px) rotateX(${tilt.toFixed(3)}deg) rotateY(${turn.toFixed(3)}deg)`;
    card.style.willChange='transform';
   }
   request();
  }
  const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting)visible.add(entry.target);else{visible.delete(entry.target);flatten(entry.target);}}if(current)request();},{rootMargin:'64px'});
  function sync(){
   const found=[...document.querySelectorAll('.filter-catalog')],next=new Set(found);
   for(const card of cards.keys())if(!next.has(card)){observer.unobserve(card);visible.delete(card);cards.delete(card);}
   // Measure the untransformed layout once, outside the scroll loop.
   for(const card of found)flatten(card);
   found.forEach((card,index)=>{const fresh=!cards.has(card);cards.set(card,{top:card.getBoundingClientRect().top+window.scrollY,height:card.offsetHeight,index});if(fresh)observer.observe(card);});
   if(current)request();
  }
  function scroll(){const now=performance.now(),elapsed=now-lastScroll,delta=window.scrollY-lastY;lastY=window.scrollY;if(!delta)return;velocity=clamp(delta/(elapsed>60?16:Math.max(8,elapsed))/1.3,-1,1);lastScroll=now;request();}
  function visibility(){if(document.hidden){cancelAnimationFrame(frame);frame=0;current=0;velocity=0;for(const card of cards.keys())flatten(card);}lastY=window.scrollY;lastPaint=0;}
  const mutations=new MutationObserver(sync),root=document.getElementById('root');
  mutations.observe(root,{childList:true,subtree:true});window.addEventListener('scroll',scroll,{passive:true});window.addEventListener('resize',sync,{passive:true});document.addEventListener('visibilitychange',visibility);sync();
  return()=>{cancelAnimationFrame(frame);observer.disconnect();mutations.disconnect();window.removeEventListener('scroll',scroll);window.removeEventListener('resize',sync);document.removeEventListener('visibilitychange',visibility);for(const card of cards.keys())flatten(card);};
 },[enabled,reduced]);
 return reduced;
}
