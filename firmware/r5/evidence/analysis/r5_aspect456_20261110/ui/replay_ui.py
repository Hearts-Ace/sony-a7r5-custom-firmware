#!/usr/bin/env python3
"""Final-ELF five-page mask, native Guide/Image and capacity replay.

All source geometry is checked against an independent Python integer oracle.
Native graphics/constructors run from exact libraries; only listed OS services,
resource lookup and object-tree connectivity are fixtures.
"""
from pathlib import Path
import argparse, hashlib, json, random, struct, sys, traceback
from unicorn import UC_HOOK_CODE
from unicorn import arm64_const as A
from replay_ui_support import (UIReplay, require, sha, WIDGET, INIT, COMMON,
                               SNAPSHOT, FLAGS, VIEW, ARENA, PRESENTER, PARAMETERS,
                               STACK, STOP, LIBRARIES, PALETTE_SHA)

HERE = Path(__file__).resolve().parent
RATIOS = ((809, 500), (239, 100), (5, 4), (37, 20))
X = [getattr(A, 'UC_ARM64_REG_X' + str(i)) for i in range(31)]
Q = [getattr(A, 'UC_ARM64_REG_Q' + str(i)) for i in range(32)]

def bars(selected, direction=0, mapping=0, route=0, fmt=0, viewport=(0,26,640,426)):
    x,y,w,h = viewport
    pn,pd = (4,3) if route == 1 and fmt == 2 else (9,8) if route == 1 and fmt == 3 else (1,1)
    n,d = RATIOS[selected - 4]
    n *= pd; d *= pn
    if w*d > h*n:
        t=(w*d-h*n+d)//(2*d)
        result=[(x,y,t,h),(x+w-t,y,t,h)]
    else:
        t=(h*n-w*d+n)//(2*n)
        result=[(x,y,w,t),(x,y+h-t,w,t)]
    if direction:
        if (direction == 1) != (mapping == 4):
            result=[(480-y-h,x,h,w) for x,y,w,h in result]
        else:
            result=[(y,640-x-w,h,w) for x,y,w,h in result]
    return result

def register(m, config, layer=3, flags=1, table_index=1):
    page=m.layout['pages'][config]
    m.invoke(0x182ad30, VIEW, layer, 0, ARENA, 0x400000, 0, 0, 0)
    m.u.mem_write(FLAGS, bytes([flags])*page['count'])
    token=m.invoke('r5_ui_before_create', VIEW, 0xca4,
                   page['tables'][table_index]['VA']+m.bias,page['count'],0,FLAGS)
    require(token>>31 and ((token>>16)&7)==layer,'Native canvas not retained')
    m.write(VIEW+0x3e90,page['count'])
    m.write(VIEW+0x3ec8+page['row']*8,WIDGET,'<Q')
    m.invoke('r5_ui_after_create',VIEW,FLAGS,token)
    require(m.u.mem_read(FLAGS+page['row'],1)==bytes([flags]),'Flags not restored')
    if config >= 3:
        slot=m.addr('r5_ui_guides')+((config-3)*6+layer)*24
        require(m.read(slot,'<Q')==WIDGET+0x1d8,'Real parameter not registered')
        return slot

def creation(m):
    cases=0
    m.invoke(0x182ad30, VIEW, 0, 0, ARENA, 0x400000, 0, 0, 0)
    for config,page in enumerate(m.layout['pages']):
        for index,table in enumerate(page['tables']):
            total=sum(m.layout['allocation_bytes'][str(k)] for k in table['types'])
            mixed=sum(m.layout['allocation_bytes'][str(k)] if i==page['row'] else
                      m.layout['disabled_allocation_bytes'][str(k)] for i,k in enumerate(table['types']))
            for layer in range(6):
                for direction in range(3):
                    masks=bytearray([1]*page['count']);masks[page['row']]=7
                    m.write(VIEW+8,layer);m.write(VIEW+0x3ea0,total+128)
                    m.write(VIEW+0x3e90,page['count'])
                    m.write(VIEW+0x3ec8+page['row']*8,WIDGET,'<Q')
                    m.u.mem_write(FLAGS,bytes(masks))
                    result=m.invoke('r5_ui_before_create',VIEW,0xca4,table['VA']+m.bias,
                                    page['count'],direction,FLAGS)
                    require(result>>31 and m.u.mem_read(FLAGS+page['row'],1)==b'\0','Target row not enabled')
                    m.invoke('r5_ui_after_create',VIEW,FLAGS,result)
                    require(bytes(m.u.mem_read(FLAGS,page['count']))==bytes(masks),'Masks changed')
                    cases+=1
            for disabled,need in ((False,total),(True,mixed)):
                for capacity in (need,need-128):
                    masks=bytes([int(disabled)])*page['count']
                    m.u.mem_write(FLAGS,masks);m.write(VIEW+0x3ea0,capacity)
                    result=m.invoke('r5_ui_before_create',VIEW,0xca4,table['VA']+m.bias,
                                    page['count'],0,FLAGS)
                    require(result==0 and bytes(m.u.mem_read(FLAGS,page['count']))==masks,
                            'Arena equality/underflow or disabled-parameter allocation not rejected')
                    cases+=1
    return cases

def shooting(m):
    # Creation cases intentionally reuse one fixture widget for multiple pages;
    # discard those synthetic connections before constructing the real Guide.
    m.u.mem_write(m.addr('r5_ui_guides'), bytes(12*24))
    m.construct_guide()
    slot=register(m,3)
    m.snapshot()
    cases=[]
    for selected in range(4,8):
        for direction in range(3):
            m.invoke(0x182cb84,WIDGET,direction);m.invoke(0x182d764,WIDGET)
            for mapping in (0,4):
                for route,fmt in ((0,0),(1,1),(1,2),(1,3)):
                    for offset,value in ((0x25c0,route),(0x25e0,fmt),(0x2688,mapping)):
                        m.write(SNAPSHOT+offset,value)
                    token=0x100|8|selected
                    m.write(m.addr('r5_aspect_selection'),token)
                    m.invoke('r5_ui_guide_produce',0,WIDGET+0x1d8,0,SNAPSHOT)
                    require(m.read(slot+12)==token,('Producer did not bind complete token',hex(token),hex(m.read(slot+12)),m.u.mem_read(WIDGET+0x1d8,0x60).hex()))
                    require(m.u.mem_read(WIDGET+0x21c,1)==b'\1','Native producer did not enable')
                    m.invoke('r5_ui_guide_update',WIDGET)
                    children=[m.child(i) for i in range(8)]
                    expected=bars(selected,direction,mapping,route,fmt)
                    require(m.u.mem_read(WIDGET+0x41,1)==b'\2','Native Guide parent not visible')
                    for i,c in enumerate(children):
                        if i<2:
                            require(c['mode']==1 and c['rgba']=='000000ff','Native child not opaque black')
                            require(tuple(c['rectangle'])==expected[i],('Native child geometry',selected,direction,mapping,route,fmt,c,expected[i]))
                        else:require(c['mode']==3,'Unused Guide child visible')
                    cases.append(dict(selected=selected,direction=direction,mapping=mapping,route=route,format=fmt,
                                      rectangles=expected))
    # Full-token stale publications and unregister invalidate recognition.
    m.write(m.addr('r5_aspect_selection'),0x208|4)
    require(m.read(slot+12)!=(0x208|4),'Fixture requires old producer token')
    m.invoke('r5_ui_guide_unregister',WIDGET)
    require(m.read(slot,'<Q')==0 and m.read(slot+12)==0,'Unregister did not invalidate owned pointer')
    return cases

def page_masks(m):
    m.construct_image()
    cases=[];negative=[]
    for page,count,row,vo,po,do,ro in ((0,98,4,0x80,0x88,0x7278,0x10e8),
                                     (1,38,6,0x40,0x48,0x1340,0x3210),
                                     (2,76,6,0x68,0x70,0x1378,0x5338)):
        m.write(VIEW+0x3e90,count);m.write(VIEW+0x3ec8+row*8,WIDGET,'<Q')
        m.write(PRESENTER+vo,VIEW,'<Q');m.write(PRESENTER+po,PARAMETERS,'<Q')
        m.write(PARAMETERS+row*16,0);m.write(PARAMETERS+row*16+8,WIDGET+0x1d8,'<Q')
        for selected in range(4,8):
            for direction in range(3):
                for mapping in (0,4):
                    for route,fmt in ((0,0),(1,1),(1,2),(1,3)):
                        values=dict(x=0,y=26,w=640,h=426,route=route,format=fmt,
                                    direction=direction,mapping=mapping,mode=2,aspect=0)
                        m.write(PRESENTER+8,direction);m.write(PRESENTER+do,direction);m.write(PRESENTER+ro,route)
                        m.write(m.addr('r5_aspect_selection'),0x308|selected)
                        if page:m.model(values)
                        else:
                            m.write(PRESENTER+0x5830,33);m.write(PRESENTER+0x7180,0x1660+selected-4)
                            for off,name in ((0x128,'x'),(0x148,'y'),(0x168,'w'),(0x188,'h'),
                                             (0x1e8,'route'),(0x208,'format'),(0x6378,'direction'),(0x5a60,'mapping')):
                                m.write(PRESENTER+0xf00+off,values[name])
                            # Highlight browsing must work independently of the accepted ID.
                            m.write(m.addr('r5_aspect_selection'),0)
                        m.invoke('r5_ui_page_draw',PRESENTER,page)
                        rects=m.sprite_rects();expected=bars(selected,direction,mapping,route,fmt)
                        require(m.u.mem_read(WIDGET+0x41,1)==b'\2','Actual Image not shown')
                        require(m.local_position(WIDGET)==(0,0),'Actual Image position not reset')
                        for i,r in enumerate(rects):
                            if i<2:
                                require(tuple(r['rectangle'])==expected[i] and r['rgba']=='000000ff',('Actual Sprite mismatch',page,selected,r,expected[i]))
                            else:require(tuple(r['rectangle'][2:])==(0,0),'Unused Sprite dimensions retained')
                        require(m.locked==0,'Model lock unbalanced')
                        cases.append(dict(page=page,selected=selected,direction=direction,mapping=mapping,
                                          route=route,format=fmt,rectangles=expected))
        for case in ('native','direction_pending','route_pending','bad_route','bad_format','invalid_viewport','epoch_during_unlock'):
            values=dict(x=0,y=26,w=640,h=426,route=0,format=0,direction=0,mapping=0,mode=2,aspect=0)
            m.write(PRESENTER+8,0);m.write(PRESENTER+do,0);m.write(PRESENTER+ro,0)
            m.write(m.addr('r5_aspect_selection'),0x408|4)
            if page:m.model(values)
            else:
                m.write(PRESENTER+0x5830,33);m.write(PRESENTER+0x7180,0x1660)
                for off,name in ((0x128,'x'),(0x148,'y'),(0x168,'w'),(0x188,'h'),
                                 (0x1e8,'route'),(0x208,'format'),(0x6378,'direction'),(0x5a60,'mapping')):
                    m.write(PRESENTER+0xf00+off,values[name])
            if case=='native':
                if page:m.write(m.addr('r5_aspect_selection'),0)
                else:m.write(PRESENTER+0x7180,126)
            elif case=='direction_pending':m.write(PRESENTER+8,1)
            elif case=='route_pending':m.write(PRESENTER+ro,1)
            elif case in ('bad_route','bad_format','invalid_viewport'):
                name,value={'bad_route':('route',2),'bad_format':('format',9),'invalid_viewport':('w',0)}[case]
                if case=='bad_format':
                    if page:m.model({'route':1})
                    else:m.write(PRESENTER+0xf00+0x1e8,1)
                    m.write(PRESENTER+ro,1)
                if page:m.model({name:value})
                else:m.write(PRESENTER+0xf00+{'route':0x1e8,'format':0x208,'w':0x168}[name],value)
                if case=='bad_route':m.write(PRESENTER+ro,value)
            elif case=='epoch_during_unlock':
                if not page:continue
                m.on_unlock=lambda:m.write(m.addr('r5_aspect_selection'),0x508|4)
            m.invoke('r5_ui_page_draw',PRESENTER,page);m.on_unlock=None
            require(m.u.mem_read(WIDGET+0x41,1)==b'\3' and all(tuple(r['rectangle'][2:])==(0,0) for r in m.sprite_rects()),
                    ('Invalid/pending snapshot not cleared',page,case))
            negative.append(dict(page=page,case=case))
    return cases,negative

def abi(candidate,module,bias):
    # Pure ABI probes use controlled native callbacks and clobber extension
    # callbacks. UI algorithm behavior is verified separately above.
    m=UIReplay(candidate,module,bias);u=m.u;rng=random.Random(20261110);cases=0
    for name in ('r5_ui_create_hook','r5_ui_page_hook_0','r5_ui_page_hook_1','r5_ui_page_hook_2'):
        for flags in range(16):
            initial=[rng.getrandbits(64) for _ in X];initial[30]=STOP
            initial[8 if name=='r5_ui_create_hook' else 2]=STOP+0x80
            post=initial[:]
            for i in range(19):post[i]=rng.getrandbits(64)
            vectors=[rng.getrandbits(128) for _ in Q]
            for reg,v in zip(X,initial):u.reg_write(reg,v)
            for reg,v in zip(Q,vectors):u.reg_write(reg,v)
            u.reg_write(A.UC_ARM64_REG_SP,STACK+0x1f000)
            u.reg_write(A.UC_ARM64_REG_NZCV,(flags^15)<<28)
            calls=[]
            def hook(machine,address,size,data):
                if address==STOP+0x80:
                    calls.append('native');lr=m.x(30)
                    for reg,v in zip(X[:19],post[:19]):u.reg_write(reg,v)
                    for reg,v in zip(Q,vectors):u.reg_write(reg,v)
                    u.reg_write(A.UC_ARM64_REG_NZCV,flags<<28)
                    u.reg_write(A.UC_ARM64_REG_FPCR,0x400000);u.reg_write(A.UC_ARM64_REG_FPSR,0x10)
                    u.reg_write(A.UC_ARM64_REG_PC,lr)
                elif address in [m.addr(s) for s in ('r5_ui_before_create','r5_ui_after_create','r5_ui_page_draw')]:
                    calls.append('extra');lr=m.x(30)
                    for reg in X[:19]:u.reg_write(reg,rng.getrandbits(64))
                    for reg in Q:u.reg_write(reg,rng.getrandbits(128))
                    for reg in (A.UC_ARM64_REG_NZCV,A.UC_ARM64_REG_FPCR,A.UC_ARM64_REG_FPSR):u.reg_write(reg,0)
                    m.putx(0,0);u.reg_write(A.UC_ARM64_REG_PC,lr)
            handle=u.hook_add(UC_HOOK_CODE,hook)
            u.emu_start(m.addr(name),STOP,count=2000);u.hook_del(handle)
            require(u.reg_read(A.UC_ARM64_REG_PC)==STOP,'ABI return')
            require([u.reg_read(r) for r in X]==post,'ABI GPR preservation')
            require([u.reg_read(r) for r in Q]==vectors,'ABI SIMD preservation')
            require(u.reg_read(A.UC_ARM64_REG_SP)==STACK+0x1f000 and u.reg_read(A.UC_ARM64_REG_NZCV)==flags<<28,'ABI SP/NZCV')
            require(u.reg_read(A.UC_ARM64_REG_FPCR)==0x400000 and u.reg_read(A.UC_ARM64_REG_FPSR)==0x10,'ABI FP state')
            require(calls==(['extra','native','extra'] if name=='r5_ui_create_hook' else ['native','extra']),'ABI call order')
            cases+=1
    for flags in range(16):
        for value in (0,1):
            for match in (False,True):
                regs=[rng.getrandbits(64) for _ in X];regs[0]=value;regs[20]=0x20001000
                for reg,v in zip(X,regs):u.reg_write(reg,v)
                m.write(m.addr('r5_ui_guide_cookie'),regs[20] if match else 0,'<Q')
                u.reg_write(A.UC_ARM64_REG_SP,STACK+0x1f000);u.reg_write(A.UC_ARM64_REG_NZCV,flags<<28)
                target=m.sy['r5_ui_native_guide_show_yes' if match or value==0 else 'r5_ui_native_guide_show_no']
                u.emu_start(m.addr('r5_ui_guide_show'),target,count=50)
                require(u.reg_read(A.UC_ARM64_REG_PC)==target and [u.reg_read(r) for r in X]==regs,'Scoped show branch/GPR')
                require(u.reg_read(A.UC_ARM64_REG_NZCV)==flags<<28 and u.reg_read(A.UC_ARM64_REG_SP)==STACK+0x1f000,'Show SP/flags')
                cases+=1
    return cases

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--module',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    require(not a.output.exists(),'Never overwrite evidence')
    results=[]
    try:
        for bias in (0x4000000000,0x6000000000):
            m=UIReplay(a.candidate,a.module,bias)
            creation_cases=creation(m)
            shoot=shooting(m)
            page,negative=page_masks(m)
            results.append(dict(bias=hex(bias),creation_cases=creation_cases,shooting_cases=shoot,
                                page_cases=page,negative_cases=negative,
                                relocated=m.graphics_relocated,unexecuted_TLS=len(m.deferred_tls),
                                modeled_calls=sorted(set(m.external_calls)),palette_resources=sorted(set(m.resource_reads))))
            del m
        abi_cases=sum(abi(a.candidate,a.module,b) for b in (0x4000000000,0x6000000000))
        result=dict(passed=True,AP_sha256=sha(a.candidate.read_bytes()),
                    module_manifest_sha256=sha((a.module/'module.json').read_bytes()),
                    test_sha256=sha(Path(__file__).read_bytes()),support_sha256=sha((HERE/'replay_ui_support.py').read_bytes()),
                    ratios=['1.618:1','2.39:1','5:4','1.85:1'],cases=results,ABI_cases=abi_cases,
                    no_runtime_module_overlay=True,actual_Guide_Image_constructors=True,
                    actual_native_producer_and_child_and_Sprite_output=True,
                    libraries={k:v[1] for k,v in LIBRARIES.items()},palette_sha256=PALETTE_SHA,
                    fixtures=['ELF relocation, libc allocation/memory services, native OS locks',
                              'Object tree connects actual native-constructed target widgets; other rows are not constructed',
                              'Presenter completed snapshots/window/model scalar inputs; no synthetic Guide produced flag or viewport',
                              'Global UX layer registration/engine counter and palette lookup from actual resource bank',
                              'ABI probes explicitly replace native/extension call endpoints with register-clobber fixtures'],
                    limits=['No complete native GUI event loop, device LCD, IPC, encoder or camera startup',
                            'TLS paths unexecuted; no arbitrary SMP schedule proof','RAW and encoded outputs not touched by these UI hooks'])
    except Exception as e:
        result=dict(passed=False,error=repr(e),traceback=traceback.format_exc(),cases=results)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','fixtures','limits','libraries')}))
    require(result['passed'],'Replay failed; retain negative receipt')

if __name__=='__main__':main()
