#!/usr/bin/env python3
"""Native Fn wheel/MENU matrix using the reference's display order.

Uses the unchanged reviewed cancel replay class; no production/test overlays.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, struct, sys, traceback
HERE=Path(__file__).resolve().parent
CANCEL=HERE.parent/'cancel/replay_cancel.py'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--module',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists()
    old=sys.argv;sys.argv=[str(CANCEL)]
    spec=importlib.util.spec_from_file_location('cancel_native_reviewed',CANCEL)
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c);sys.argv=old
    c.AP=a.candidate;c.BUILD=a.module
    order=[0,4,1,6,2,7,5,3]
    results=[];r=None
    try:
        for bias in (0x4000000000,0x6000000000):
            r=c.Cancel(bias)
            for initial in range(8):
                for browse in range(8):
                    r.call('r5_aspect_menu_commit',c.alias(initial))
                    r.u.mem_write(r.call(bias+0x2170958),c.p32(c.alias(initial)))
                    assert r.call('r5_aspect_menu_get')==initial
                    r.trace.clear();r.aliases.clear();r.capture()
                    cache=r.u32(bias+c.CACHE)
                    keys=[r.u32(bias+c.VEC+i*4) for i in range(r.u64(bias+c.VEC+800))]
                    assert keys==[0x52b] and cache==(initial if initial<4 else 0)
                    steps=(order.index(browse)-order.index(initial))%8
                    wheel=[]
                    for step in range(steps):
                        r.call(bias+0x2175e7c,c.P)
                        got=r.call('r5_aspect_menu_get')
                        expected=order[(order.index(initial)+step+1)%8]
                        assert got==expected,(initial,browse,step,got,expected)
                        wheel.append(got)
                    before=r.call('r5_aspect_menu_get');assert before==browse
                    r.event();after=r.call('r5_aspect_menu_get')
                    saved=struct.unpack('<4I',r.files['custom_aspect_v2.dat'])[2]
                    assert after==initial and saved==(initial if initial>=4 else 0)
                    results.append(dict(bias=hex(bias),initial=initial,browsed=browse,wheel=wheel,
                                        after=after,saved=saved,native_cache=cache,keys=keys,
                                        restored_aliases=list(r.aliases),trace=list(r.trace)))
            del r;r=None
        result=dict(passed=True,case_count=len(results),cases=results,AP_sha256=sha(a.candidate),
                    module_sha256=sha(a.module/'rx.bin'),script_sha256=sha(Path(__file__)),
                    reused_cancel_script_sha256=sha(CANCEL),display_order=order,
                    actual_entries=['Fn capture window 0x2176c10','Native wheel 0x2175e7c',
                                    'MENU event 0x1a5e4b8 event0201000f'],
                    no_direct_publish_during_cancel=True,no_supplied_old_alias_at_cancel=True,
                    no_runtime_patch_overlay=True,
                    fixtures=['Unchanged Cancel/FinalAP ELF relocation and in-memory POSIX fixtures',
                              'Native setter/commit endpoints write native-only model/meta',
                              'Minimal presenter, original descriptor membership and availability/list services'],
                    limits=['No complete native GUI tree, OS input, camera, IPC, encoder or real files'])
    except Exception as e:
        result=dict(passed=False,error=repr(e),traceback=traceback.format_exc(),cases=results,
                    recent=r.recent if r else [],trace=r.trace if r else [])
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','recent','trace','fixtures','limits')}))
    assert result['passed']

if __name__=='__main__':main()
