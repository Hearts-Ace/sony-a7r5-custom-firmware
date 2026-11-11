#!/usr/bin/env python3
"""Actual native Fn-style widgets and unchanged filter transaction replay.
Graphics resource lookup, font rasterization, OS and worker completion are
explicit services. No fixture writes widget output, styles, focus or names.
"""
from pathlib import Path
import argparse,hashlib,json,sys,struct
H=Path(__file__).resolve().parent;R=H.parents[1]
sys.path.insert(0,str(R/'analysis/r5_filter_native_style_20261110'))
from verify_style import FinalStyle,SHORT,FULL,function,VIEW,require,sha

class FnReplay(FinalStyle):
 def __init__(self,*args):
  super().__init__(*args);b=self.bias;self.image_requests=[];self.native_names=[];self.after_begin=False
  self.callbacks[self.sy['name_id']]=lambda:(self.native_names.append(self.x(1)),self.ret())[-1]
  for at in (0x16db2d0,0x16dae50,0x16dcd90,0x16d9620,0x16dab50,0x16d9800):
   self.callbacks[b+at]=lambda:self.ret(0)
  # Empty original language-dependent resource maps; font backend not running.
  empty=0x20420000
  for ptr in (0x74d81a0,0x74d81d8,0x74d8210,0x74d8248,0x74d8280,0x74d82b8,0x74d82f0):
   self.write(b+ptr,empty,'<Q');self.write(b+ptr+8,1,'<Q')
 def begin(self,*args):
  result=super().begin(*args);self.after_begin=True
  # Original widget lifecycle sends through its constructor-supplied manager.
  # The offline manager implements delivery/recording, not the row producer.
  self.manager_events=[];vt=self.read(self.manager,'<Q');cb=0x20403100
  self.write(vt,cb,'<Q')
  self.callbacks[cb]=lambda:(self.manager_events.append([self.x(i) for i in range(5)]),self.ret(0))[-1]
  # Original libObj Engine registry is an OS/graphics service, not a widget.
  # A valid empty registry permits original register/unregister functions.
  engine_ptr=self.read(0x50000000+0x2651a0,'<Q')
  engine=self.read(engine_ptr,'<Q');registry=0x60f08000
  self.write(engine+0x7a0,registry,'<Q')
  self.callbacks[self.bias+0x1848360]=self.image_boundary
  return result
 def image_boundary(self):
  owner=self.x(0)
  # Original Image apply has already accepted actual resource and show fields.
  self.image_requests.append(dict(owner=owner,resource=self.read(owner+0x214),visible=self.read(owner+0x204,'<B')))
  self.ret()
 def native_update(self,owner):
  vt=self.read(owner,'<Q');apply=self.read(vt+0x148,'<Q');update=self.read(vt+0x150,'<Q')
  self.invoke(apply-self.bias,owner)
  if update==self.bias+0x1885688:self.callbacks.pop(update,None)
  self.invoke(update-self.bias,owner)
 def scroll_invoke(self,target,*args):
  from unicorn.arm64_const import UC_ARM64_REG_SP,UC_ARM64_REG_X29,UC_ARM64_REG_X30,UC_ARM64_REG_PC
  from replay_final_ap import STACK,STOP
  for i,arg in enumerate(args):self.putx(i,arg)
  self.u.reg_write(UC_ARM64_REG_SP,STACK+0x1f000)
  self.u.reg_write(UC_ARM64_REG_X29,0);self.u.reg_write(UC_ARM64_REG_X30,STOP)
  self.u.emu_start(self.bias+target,STOP,count=10000000)
  require(self.u.reg_read(UC_ARM64_REG_PC)==STOP,('Bounded native scrolling instruction limit',hex(target),hex(self.u.reg_read(UC_ARM64_REG_PC)),hex(self.heap)))
 def output(self,layout):
  require(self.invoke('LOCAL:project',self.presenter)==1,'Private project output')
  pmap=self.read(self.presenter+0x48,'<Q');focus=self.read(self.g+8)
  allowed=[0]+[i for i in range(1,13) if self.mask&(1<<(i-1))];at=allowed.index(focus)
  def owner(index,kind):
   require(self.read(pmap+index*16)==kind,'Actual widget type')
   own=self.read(VIEW+0x3ec8+index*8,'<Q');p=self.read(pmap+index*16+8,'<Q')
   require(own and p==own+0x1d8,'Actual native owned parameter')
   return own,p
  # Full-name/title consume the actual String update, existing dispatcher and
  # UTF8 name getter. Rendering to an LCD/font glyph atlas is outside this run.
  text_before=len(self.draws)
  for index,want,xy in ((11,'关闭' if focus==0 else FULL[focus-1],(128.,64.) if layout==0 else (8.,58.)),
                         (12,'自定义滤镜',(128.,8.) if layout==0 else (8.,10.))):
   own,p=owner(index,2);self.native_update(own)
   require(self.draws[-1]['text']==want,'Actual selected full name/title submitted')
   require(self.local_position(own)==xy,'Actual native title/fullname geometry')
  own,p=owner(5,24);require(self.read(p+0x30)==8 and self.read(p+0x34)==1,'Native Fn footer scheme8')
  image_at=len(self.image_requests);name_at=len(self.native_names)
  self.callbacks.pop(self.bias+0x1885688,None)
  self.native_update(own)
  footer=[q['resource'] for q in self.image_requests[image_at:] if q['visible']]
  footer_names=self.native_names[name_at:]
  require(all(x in footer_names for x in (0x0200a28c,0x0200a2b0,0x0200a26d)),('Actual native OK/Cancel/Help String producers',footer_names,footer))
  require(footer==[0x02002357]*3,'Three original native footer button backgrounds')
  for index,resource in ((4,0x02000321),(8,0x02002cac)):
   own,p=owner(index,0);self.native_update(own)
   require(self.image_requests[-1]['resource']==resource,'Actual native footer/divider Image apply resource')
  for index,enabled,xy in ((30,at>0,(39.,28.)),(31,at<len(allowed)-1,(39.,380.))):
   own,p=owner(index,15)
   require(self.read(p+0x39,'<B')==1 and self.read(p+0x3a,'<B')==0,'Native Fn arrow rendering flags')
   require(self.read(p+0x2c,'<B')==enabled,'Native arrow end visibility')
   if layout==0:require(self.local_position(own)==xy,'Native arrow geometry')
  if self.read(self.g+28):
   own,p=owner(9,28);self.native_update(own)
   # Native async cache may be empty at initial return. Complete its actual
   # pending row callbacks with existing child objects, never fabricate children.
   self.invoke(0x1892068,own)
   try:
    if focus and not self.complete_scroll:raise RuntimeError('Offline Engine lacks natural scrolling scheduler')
    root=own+0x12a0
    if self.read(root+0x480):self.invoke(0x1843678,root)
    from unicorn.arm64_const import UC_ARM64_REG_S0
    self.u.reg_write(UC_ARM64_REG_S0,0)
    self.scroll_invoke(0x1844250,root,self.read(own+0xf10),0)
    self.scroll_invoke(0x1843f94,root)
   except RuntimeError:
    pass
   before=len(self.draws);count=0
   for n in range(19):
    child=self.invoke(0x1842aec,own+0x12a0,n)
    if not child:continue
    self.callbacks.pop(self.bias+0x1885688,None)
    self.invoke(0x18929b4,own,n);count+=1
   require(count>0,'Actual native scroll root produced children')
   actual=[q['text'] for q in self.draws[before:]]
   if focus==0 or self.complete_scroll:
    require(any(x==('关闭' if focus==0 else SHORT[focus-1]) for x in actual),'Actual native selected abbreviation String consumer')
   else:
    # Native row producer runs and contains the selected text; the offline
    # Engine does not complete the natural animated child relocation.
    logical=self.read(p+0xd38)+2
    require(self.read(own+0x1de8+logical*0x9e8)==0x2ff4300+focus,'Actual native selected cache text producer')
  else:
   actual=[]
   for i in range(5):
    own,p=owner(9 if i==0 else 15+i,2)
    position=at+i-2;visible=0<=position<len(allowed)
    require(self.read(p+0x2c,'<B')==visible,'Five original Fn positions only')
    require(self.read(p+0x44)==0x0207a00e and self.read(p+0x4c)==0x02066026 and self.read(p+0x50)==1,'Original native kind13 text style/font')
    require(self.read(p+0x48)==(0x0207a001 if visible and allowed[position]==focus else 0x0207a000),'Original focused/normal text style')
    if visible:
     selected=allowed[position];self.native_update(own)
     want='关闭' if not selected else SHORT[selected-1];require(self.draws[-1]['text']==want,'Actual fallback native abbreviation String')
     actual.append(want)
     xy=(1.,51.+i*66) if layout==0 else (49.+i*76,501.)
     require(self.local_position(own)==xy,'Fallback same native Fn five row geometry')
  for index in (3,6,7,10,15,20,21,27,28,29,32,33):
   require(self.read(VIEW+0x3ec8+index*8,'<Q')==0,'No removed adjustment/fullscreen widget')
  return dict(focus=focus,left_names=actual,selected_left_child_observed=not self.read(self.g+28) or focus==0 or self.complete_scroll,footer=footer,footer_names=footer_names,text_submissions=len(self.draws)-text_before,arena_used=self.read(VIEW+0x3ea4))

def main():
 a=argparse.ArgumentParser();a.add_argument('--ap',type=Path,required=True);a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--complete-scroll',action='store_true');a=a.parse_args()
 require(not a.output.exists(),'New evidence path')
 old=(R/'projects/firmware/development/shutter-sound-recovery455/src/menu_research/r5_filter_page425.c').read_text()
 new=(H/'r5_filter_page_style.c').read_text()
 names=['owned','valid','close_page','r5_filter_parent_refresh425','wait_command','return_parent','finish_command','submit','next','private_input','dispatch','exit_page','destroy','controller_destroy','sound_parent_presenter','sound_menu_event','r5sound_menu_event2d6_443','r5sound_menu_event425']
 for name in names:require(function(old,name)==function(new,name),'Unchanged455 transaction/lifecycle '+name)
 cases=[]
 for bias,capacity,layout in ((0,0x20000,0),(0,0x400000,0),(0x4000000000,0x20000,1),(0x4000000000,0x400000,1)):
  m=FnReplay(a.ap,a.build,bias);m.complete_scroll=a.complete_scroll;m.publish();m.begin(capacity,layout);rows=[m.output(layout)]
  for i in range(12):m.event(0x2050000);require(m.selected==i+1,'Forward wheel durable selection')
  rows.append(m.output(layout));m.event(0x2050000);require(m.selected==12,'No end wrap')
  for i in range(6):m.event(0x2050001)
  require(m.selected==6,'Reverse selection');rows.append(m.output(layout))
  m.mode='failure';m.event(0x2050000);require(m.selected==6 and m.read(m.g+12)==3,'Failure preserves committed selection');rows.append(m.output(layout))
  m.mode='pending';m.delay=m.sleeps+2;m.event(0x2050000);require(m.selected==8 and m.read(m.g+12)==0,'Delayed exact completion')
  m.delay=0;m.event(0x2050000);require(m.pending==1 and m.read(m.g+12)==4,'Long request remains pending')
  m.selected=m.requested;m.pending=0;m.command=2;m.event(0x201000c);require(m.closed and m.read(m.g+4)==0,'Confirm closes through existing manager')
  require(m.event(0x2050000)==1 and m.event(0x20f0000)==0x555,'Retired input/native lifecycle')
  cases.append(dict(bias=bias,capacity=capacity,layout=layout,outputs=rows,requests=m.requests))
  print(json.dumps(dict(passed=True,bias=bias,capacity=capacity,layout=layout)),flush=True)
 m=FnReplay(a.ap,a.build);m.complete_scroll=a.complete_scroll;m.publish(0x809);m.begin(0x20000,0)
 sparse=[m.output(0)]
 for n in (1,4,12):
  m.event(0x2050000);require(m.selected==n,'Sparse omitted filters skipped');sparse.append(m.output(0))
 m.event(0x201000f);require(m.closed and m.read(m.g+4)==0,'Cancel uses existing manager close path')
 status='NATIVE_DISPLAY_WITH_EXPLICIT_IMMEDIATE_SCROLL_AND_TRANSACTIONS_VERIFIED' if a.complete_scroll else 'SMALL_POOL_DISPLAY_AND_LARGE_POOL_INITIAL_DISPLAY_CACHE_OUTPUT_VERIFIED'
 result=dict(passed=True,status=status,AP_sha256=sha(a.ap.read_bytes()),build_sha256=sha((a.build/'build.json').read_bytes()),source_sha256=sha(new.encode()),test_sha256=sha(Path(__file__).read_bytes()),cases=cases,sparse_cancel=sparse,preserved455_functions=names,
  fixtures=['Original OS/library services, empty language/font lookup caches, font raster and image engine submit boundaries','Global scene/manager/worker services; actual widget constructors/apply/producers and names publisher/getters execute','Actual original list children generated; native pending row callbacks invoked explicitly','Large pool scrolling uses original stop-animation and immediate-position setters, with bounded10M instructions for native child construction; no fixture writes focus, child IDs or output'],
  limits=['No font glyph rasterization, physical LCD, device installation/startup or encoding test','Natural Engine animation scheduling is not simulated; original immediate layout is explicitly requested' if a.complete_scroll else 'Large pool animated child relocation after selection is not simulated','Parent native pop is observed; full parent reconstruction is not simulated'],camera_io=False,device_tested=False)
 a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
