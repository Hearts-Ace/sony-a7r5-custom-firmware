#!/usr/bin/env python3
"""Source-bound D9 String/Guide output and unchanged transaction contract replay.
OS, worker completion and graphics text submission are explicit boundaries.
No fixture writes native widget geometry, resource IDs, row visibility or focus.
"""
from pathlib import Path
import argparse,hashlib,json,struct,sys
from replay_style import StyleReplay,R,VIEW,require,sha
H=Path(__file__).resolve().parent
SHORT=['AS','CC','EBB','ET','NC','NH','NN','NS','RE','SN','SS','ST']
FULL=['Astia Soft','Classic Chrome','Eterna Bleach Bypass','Eterna','Classic Negative','Nostalgic Negative','Pro Neg Hi','Pro Neg Std','Reala Ace','Superia','Acros','Standard']
class FinalStyle(StyleReplay):
 def __init__(self,*a):
  super().__init__(*a);self.mode='success';self.delay=0;self.draws=[]
  self.callbacks[self.sy['name_char']]=lambda:(self.draws.append(dict(sprite=self.x(0),text=self.cstr(self.x(1)))),self.ret())[-1]
  self.callbacks[self.sy['name_id']]=lambda:(_ for _ in()).throw(AssertionError('Private row reached ID renderer'))
  self.callbacks[self.bias+0x1bd55fc]=lambda:self.ret(0x2ff4300+self.selected)
 def publish(self,mask=0xfff):
  # A validated file/set snapshot is supplied through the actual names publisher.
  # Complete compact parameter validation runs; only OS/worker IO is modeled.
  self.mask=mask;ptr=0x20410000;lookbytes=2444
  data=bytearray(4+12*lookbytes);struct.pack_into('<I',data,0,mask)
  for i,(short,full) in enumerate(zip(SHORT,FULL)):
   at=4+i*lookbytes;data[at:at+len(short)]=short.encode();data[at+24:at+24+len(full)]=full.encode()
   struct.pack_into('<129I',data,at+88+48+576,*[i*1023 for i in range(129)])
  self.u.mem_write(ptr,bytes(data));require(self.invoke('r5_filter_names_publish',ptr)==1,'Actual native names publication')
 def request(self):
  n=self.x(0);self.requests.append(n)
  if self.mode=='failure':return self.ret(1)
  self.sequence+=1;self.requested=n
  if self.mode=='pending':self.command=1;self.pending=1
  else:self.selected=n;self.command=2;self.pending=0
  self.ret(0)
 def sleep(self):
  self.sleeps+=1
  if self.delay and self.sleeps>=self.delay:self.selected=self.requested;self.command=2;self.pending=0
  self.ret()
 def event(self,e,message=0):return self.invoke('LOCAL:dispatch',self.controller,message,e)
 def output(self,layout):
  require(self.invoke('LOCAL:project',self.presenter)==1,'Real native project')
  pmap=self.read(self.presenter+0x48,'<Q');rows=[];focus=self.read(self.g+8)
  allowed=[0]+[i for i in range(1,13) if self.mask&(1<<(i-1))];at=allowed.index(focus)
  first=max(0,at-3);first=min(first,max(0,len(allowed)-7));expected=allowed[first:first+7]
  for i in range(7):
   row=expected[i] if i<len(expected) else None
   for index,resource in ((i+2,0x2ff4520+i),(15+i if i else 9,0x2ff4510+i)):
    require(self.read(pmap+index*16)==2,'Every text row native String')
    own=self.read(VIEW+0x3ec8+index*8,'<Q');param=self.read(pmap+index*16+8,'<Q')
    require(own and param==own+0x1d8,'Actual constructed String parameter is output')
    require(self.read(param+0x30)==resource and self.read(param+0x2c,'<B')==int(row is not None),'Actual resource/visibility')
    if row is not None:
     want='关闭' if row==0 else (FULL[row-1] if index<9 else SHORT[row-1])
     # Execute unchanged455 actual resource dispatcher to gfx text submission.
     self.invoke('r5_filter_menu_name_draw',own+0x830,resource)
     require(self.draws[-1]['text']==want,'Actual menu dispatcher full/short UTF8 output')
   own=self.read(VIEW+0x3ec8+(22+i)*8,'<Q');param=self.read(pmap+(22+i)*16+8,'<Q')
   require(own and param==own+0x1d8 and self.read(param+0x2c,'<B')==int(row==focus),'Exactly focused native Guide background')
   # Actual native background apply/update and libObj local geometry.
   self.invoke(0x18900e4,own);self.invoke(0x1890440,own)
   require(self.local_position(own)==(8.,float(64+i*(46 if layout==0 else 70))),'Actual Guide geometry')
   rows.append(dict(slot=i,filter=row,focus=row==focus))
  for index in (10,11,14,15,29,30,31,32,33):require(self.read(VIEW+0x3ec8+index*8,'<Q')==0,'No removed operation widget')
  require(self.read(pmap+13*16+8,'<Q')!=0,'Native footer parameter')
  return dict(focus=focus,rows=rows,requests=list(self.requests),status=self.read(self.g+12))
def function(source,name):
 import re
 match=re.search(r'\b'+re.escape(name)+r'\([^;]*?\)\s*\{',source);require(match is not None,name)
 depth=1;at=match.end()
 while depth:
  depth+=(source[at]=='{')-(source[at]=='}');at+=1
 return source[match.start():at]
def main():
 p=argparse.ArgumentParser();p.add_argument('--ap',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();require(not a.output.exists(),'New receipt only')
 baseline=R/'projects/firmware/development/shutter-sound-recovery455/src/menu_research/r5_filter_page425.c'
 current=H/'r5_filter_page_style.c';old=baseline.read_text();new=current.read_text()
 preserved=['owned','valid','close_page','r5_filter_parent_refresh425','wait_command','return_parent','finish_command','submit','next','private_input','dispatch','exit_page','destroy','controller_destroy','sound_parent_presenter','sound_menu_event','r5sound_menu_event2d6_443','r5sound_menu_event425']
 for name in preserved:require(function(old,name)==function(new,name),'455 contract source changed: '+name)
 build=json.loads((a.build/'build.json').read_text());require(sha(a.ap.read_bytes())==build['sha256'] and build['reverse_exact'],'Final binary bound to build')
 require(not any('renderer' in s for s in build['sources']),'No unnecessary renderer overrides')
 cases=[]
 for bias,capacity,layout in ((0,0x20000,0),(0x4000000000,0x400000,1),(0,0x400000,1),(0x4000000000,0x20000,0)):
  m=FinalStyle(a.ap,a.build,bias);m.publish();m.begin(capacity,layout);outputs=[m.output(layout)]
  for i in range(12):m.event(0x2050000);outputs.append(m.output(layout));require(m.selected==i+1,'Wheel commits exact next filter')
  m.event(0x2050000);require(m.selected==12,'End does not wrap')
  for i in range(12):m.event(0x2050001);require(m.selected==11-i,'Reverse wheel')
  # Touch uses actual background row number and current visible projection.
  msg=0x20408000;m.write(msg,1);m.write(msg+0x18,0xd9);m.write(msg+0xc,25);m.event(0x3010002,msg);require(m.selected==3,'Touch row commits matching filter')
  m.mode='failure';m.event(0x2050000);require(m.read(m.g+12)==3 and m.selected==3,'Request failure preserves durable state');fail=m.output(layout)
  m.mode='pending';m.delay=m.sleeps+2;m.event(0x2050000);require(m.selected==5 and m.read(m.g+12)==0,'Delayed worker completion');m.delay=0
  m.event(0x2050000);require(m.pending==1 and m.read(m.g+12)==4,'Long running command is pending')
  m.selected=m.requested;m.pending=0;m.command=2;m.event(0x201000c);require(m.closed and m.read(m.g+4)==0,'Completion followed by confirm requests parent return')
  require(m.event(0x2050000)==1,'Retired private input consumed')
  require(m.event(0x20f0000)==0x555,'Native lifecycle traffic retained')
  cases.append(dict(bias=bias,capacity=capacity,layout=layout,outputs=outputs,failure=fail,text_submissions=len(m.draws),sleeps=m.sleeps,closed=len(m.closed)))
  print(json.dumps(dict(passed=True,bias=bias,capacity=capacity,layout=layout)),flush=True)
 # Sparse asset set: omitted rows never produce nonexistent names.
 m=FinalStyle(a.ap,a.build);m.publish(0x809);m.begin(0x20000,0)
 sparse=[m.output(0)]
 for i in (1,4,12):m.event(0x2050000);require(m.selected==i,'Sparse mask skip');sparse.append(m.output(0))
 result=dict(passed=True,AP_sha256=sha(a.ap.read_bytes()),build_sha256=sha((a.build/'build.json').read_bytes()),cases=cases,sparse=sparse,preserved455_functions=preserved,source_hashes={str(q):sha(q.read_bytes()) for q in (Path(__file__),H/'replay_style.py',current,baseline)},
 native=['Actual Sony D9 controller and factory create native String/type2 and Guide/type20','Actual parameters belong to native widget+1d8; projected resources/visibility/geometry observed','Actual names publisher/getters and unchanged resource dispatcher consume both columns','Actual Guide update/libObj geometry, source-identical455 transaction and lifecycle handlers'],
 fixtures=['OS allocators/locks, global GUI manager callbacks, worker command/request completion and validated synthetic look-set input','Graphics TextSprite submission boundary records exact UTF8; font rasterization and LCD not executed','Native String construction update deferred until services initialized; no fixture paints native parameters'],device_tested=False,camera_io=False,
 limits=['No real LCD glyph rasterization or camera installation/boot','Synthetic asset names validate both columns; actual SD contents are not read','Return is observed at original manager pop request, parent scene reconstruction not modeled here; source455 lifecycle preserved'])
 a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
