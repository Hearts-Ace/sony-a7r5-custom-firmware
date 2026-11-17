const tabs=[document.querySelector('#tab-filters'),document.querySelector('#tab-audio')],panels=[document.querySelector('#panel-filters'),document.querySelector('#audio')];
function activate(i,focus=false){tabs.forEach((t,n)=>{t.setAttribute('aria-selected',String(n===i));t.tabIndex=n===i?0:-1;panels[n].hidden=n!==i;panels[n].style.display=n===i?(n===1?'grid':'block'):'none';});if(focus)tabs[i].focus();}
function fromHash(){activate(location.hash==='#audio'?1:0);}
tabs.forEach((t,i)=>{t.onclick=()=>{history.replaceState(null,'',i?'#audio':'#filters');activate(i);};t.onkeydown=e=>{let n;if(e.key==='ArrowRight')n=(i+1)%2;else if(e.key==='ArrowLeft')n=(i+1)%2;else if(e.key==='Home')n=0;else if(e.key==='End')n=1;else return;e.preventDefault();history.replaceState(null,'',n?'#audio':'#filters');activate(n,true);};});
window.addEventListener('hashchange',fromHash);fromHash();
