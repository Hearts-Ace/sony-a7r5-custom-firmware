import {useEffect,useState} from 'react';

// The camera and rotation pivot follow the visual viewport, not the document.
export function useFilmMotion(enabled){
 const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches);
 useEffect(()=>{const media=window.matchMedia('(prefers-reduced-motion: reduce)');const change=()=>setReduced(media.matches);media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);
 useEffect(()=>{
  if(!enabled||reduced||!('IntersectionObserver' in window))return;
  const cards=new Map(),visible=new Set(),viewport=window.visualViewport;let frame=0,current=0,velocity=0,lastY=window.scrollY,lastScroll=0,lastPaint=0;
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  const flatten=card=>{card.style.removeProperty('transform');card.style.removeProperty('--film-depth');card.style.removeProperty('--film-content-depth');card.style.removeProperty('transform-origin');card.style.removeProperty('will-change');};
  const request=()=>{if(!frame&&!document.hidden)frame=requestAnimationFrame(paint);};
  function paint(now){
   frame=0;if(document.hidden)return;
   const dt=Math.min(40,lastPaint?now-lastPaint:16);lastPaint=now;
   const decay=Math.exp(-Math.max(0,now-lastScroll-80)/210);
   const target=velocity*decay;
   current+=(target-current)*(1-Math.exp(-dt/65));
   if(now-lastScroll>1400||Math.abs(current)<.003&&Math.abs(target)<.003){current=0;for(const item of cards.values())flatten(item.panel);return;}
   const viewWidth=viewport?.width||window.innerWidth,viewHeight=viewport?.height||window.innerHeight;
   const centerX=window.scrollX+(viewport?.offsetLeft||0)+viewWidth*.5,centerY=window.scrollY+(viewport?.offsetTop||0)+viewHeight*.5;
   const small=viewWidth<760,tilt=current*(small?12:20),turn=current*(small?0:1.4);
   const z=-Math.abs(current)*48,perspective=Math.max(1800,viewHeight*2.6);
   for(const stage of visible){
    const item=cards.get(stage);if(!item)continue;const card=item.panel;
    // Allow the pivot outside the panel at its ends: it must stay at screen center.
    card.style.transformOrigin=`${(centerX-item.left).toFixed(2)}px ${(centerY-item.top).toFixed(2)}px`;
    card.style.transform=`perspective(${perspective.toFixed(0)}px) translateZ(${z.toFixed(3)}px) rotateX(${tilt.toFixed(3)}deg) rotateY(${turn.toFixed(3)}deg)`;
    card.style.willChange='transform';
   }
   request();
  }
  const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting)visible.add(entry.target);else{visible.delete(entry.target);const item=cards.get(entry.target);if(item)flatten(item.panel);}}if(current)request();},{rootMargin:'64px'});
  function sync(){
   const found=[...document.querySelectorAll('.filter-catalog-stage')],next=new Set(found);
   for(const stage of cards.keys())if(!next.has(stage)){observer.unobserve(stage);cards.delete(stage);visible.delete(stage);}
   // Read the stage's stable layout; the transformed panel cannot move its stage.
   found.forEach(stage=>{const panel=stage.querySelector('.filter-catalog'),fresh=!cards.has(stage),rect=stage.getBoundingClientRect();cards.set(stage,{panel,top:rect.top+window.scrollY,left:rect.left+window.scrollX});if(fresh)observer.observe(stage);});
   if(current)request();
  }
  function scroll(){const now=performance.now(),elapsed=now-lastScroll,delta=window.scrollY-lastY;lastY=window.scrollY;if(!delta)return;velocity=clamp(delta/(elapsed>60?16:Math.max(8,elapsed))/1.3,-1,1);lastScroll=now;request();}
  function visibility(){if(document.hidden){cancelAnimationFrame(frame);frame=0;current=0;velocity=0;for(const item of cards.values())flatten(item.panel);}lastY=window.scrollY;lastPaint=0;}
  const mutations=new MutationObserver(sync),root=document.getElementById('root');
  mutations.observe(root,{childList:true,subtree:true});window.addEventListener('scroll',scroll,{passive:true});window.addEventListener('resize',sync,{passive:true});viewport?.addEventListener('resize',sync,{passive:true});document.addEventListener('visibilitychange',visibility);sync();
  return()=>{cancelAnimationFrame(frame);observer.disconnect();mutations.disconnect();window.removeEventListener('scroll',scroll);window.removeEventListener('resize',sync);viewport?.removeEventListener('resize',sync);document.removeEventListener('visibilitychange',visibility);for(const item of cards.values())flatten(item.panel);};
 },[enabled,reduced]);
 return reduced;
}
