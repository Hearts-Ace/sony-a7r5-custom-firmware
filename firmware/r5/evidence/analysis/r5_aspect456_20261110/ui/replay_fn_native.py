#!/usr/bin/env python3
"""Two actual native Fn completed-snapshot constructors and parameter producer.

Uses real constructed Image/Sprite and final-ELF draw code. It never populates
the Fn completed direction/route fields directly for positive cases.
"""
from pathlib import Path
import argparse,json,struct,traceback
from replay_ui_support import (UIReplay,require,sha,WIDGET,VIEW,PARAMETERS,PRESENTER)
from replay_ui import bars

class Fn(UIReplay):
    def hook(self,u,address,size,data):
        if address-self.bias in (0x16d9770,0x16d9380):
            destination,source,length=[self.x(i) for i in range(3)]
            require(length<0x10000,'Native snapshot copy too large')
            if length:u.mem_write(destination,bytes(u.mem_read(source,length)))
            return self.returning(destination)
        return super().hook(u,address,size,data)

def verify(m):
    m.construct_image();cases=[];transitions=[]
    pages=[dict(page=1,entry=0x1ce7ca0,direction=0x1340,route=0x3210,mode=0x3680,
                block=0x1270,count=38,view=0x40,parameters=0x48),
           dict(page=2,entry=0x1ce7c98,direction=0x1378,route=0x5338,mode=0x6e30,
                block=0x12a8,count=76,view=0x68,parameters=0x70)]
    for page in pages:
        m.write(PRESENTER+page['view'],VIEW,'<Q');m.write(PRESENTER+page['parameters'],PARAMETERS,'<Q')
        m.write(VIEW+0x3e90,page['count']);m.write(VIEW+0x3ec8+6*8,WIDGET,'<Q')
        m.write(PARAMETERS+6*16,0);m.write(PARAMETERS+6*16+8,WIDGET+0x1d8,'<Q')
        for direction in range(3):
            for route,fmt in ((0,0),(1,1),(1,2),(1,3)):
                for mapping in (0,4):
                    values=dict(x=8,y=26,w=624,h=416,route=route,format=fmt,
                                direction=direction,mapping=mapping,mode=2,aspect=0)
                    m.model(values)
                    m.invoke(page['entry'],PRESENTER)
                    require(m.locked==0,'Native snapshot lock imbalance')
                    require(m.read(PRESENTER+page['direction'])==direction,'Wrong native completed direction offset')
                    require(m.read(PRESENTER+page['route'])==route,'Wrong native completed route offset')
                    require(m.read(PRESENTER+page['mode'])==2,'Wrong native completed mode')
                    m.invoke(0x2405c9c,0,0x20150000,0x20150100,PRESENTER+page['block'])
                    expected=(640,480) if direction==0 else (480,640)
                    require(struct.unpack('<2I',m.u.mem_read(0x20150020,8))==expected,'Native parameter dimensions differ')
                    m.write(PRESENTER+8,direction)
                    for selected in range(4,8):
                        m.write(m.addr('r5_aspect_selection'),0x108|selected)
                        m.invoke('r5_ui_page_draw',PRESENTER,page['page'])
                        rects=m.sprite_rects();expected=bars(selected,direction,mapping,route,fmt,(8,26,624,416))
                        require(m.u.mem_read(WIDGET+0x41,1)==b'\2','Native completed Fn did not draw')
                        require([tuple(r['rectangle']) for r in rects[:2]]==expected,'Native completed Fn geometry mismatch')
                        require(all(r['rgba']=='000000ff' for r in rects[:2]),'Native completed Fn opacity mismatch')
                        cases.append(dict(page=page['page'],direction=direction,route=route,format=fmt,mapping=mapping,selected=selected))
        for name in ('direction','route'):
            values=dict(x=8,y=26,w=624,h=416,route=0,format=0,direction=0,mapping=0,mode=2,aspect=0)
            m.model(values);m.invoke(page['entry'],PRESENTER);m.write(PRESENTER+8,0)
            m.model({name:1});m.invoke('r5_ui_page_draw',PRESENTER,page['page'])
            require(m.u.mem_read(WIDGET+0x41,1)==b'\3','Pending Fn snapshot retained old mask')
            m.invoke(page['entry'],PRESENTER)
            if name=='direction':m.write(PRESENTER+8,1)
            # route1 requires a native defined format to become eligible again.
            else:m.model({'format':1});m.invoke(page['entry'],PRESENTER)
            m.invoke('r5_ui_page_draw',PRESENTER,page['page'])
            require(m.u.mem_read(WIDGET+0x41,1)==b'\2','Completed Fn snapshot did not resume')
            transitions.append(dict(page=page['page'],changed=name))
    return dict(cases=cases,transitions=transitions)

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--module',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    require(not a.output.exists(),'Never overwrite evidence');results=[]
    try:
        for bias in (0x4000000000,0x6000000000):
            m=Fn(a.candidate,a.module,bias);r=verify(m);r['bias']=hex(bias);results.append(r);del m
        result=dict(passed=True,results=results,AP_sha256=sha(a.candidate.read_bytes()),
                    module_sha256=sha((a.module/'module.json').read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),
                    actual_Fn_snapshot_constructors=True,actual_Fn_parameter_producer=True,
                    no_test_written_positive_completed_fields=True,
                    fixtures=['Native scalar model inputs and presenter object connectivity',
                              'OS locks, libc memory/allocation, UX engine and palette lookup from support'],
                    limitations=['No full Fn event lifecycle or native rendering engine/device LCD'])
    except Exception as e:result=dict(passed=False,error=repr(e),traceback=traceback.format_exc(),results=results)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('results','fixtures','limitations')}))
    require(result['passed'],'Native Fn replay failed; retain failure receipt')
if __name__=='__main__':main()
