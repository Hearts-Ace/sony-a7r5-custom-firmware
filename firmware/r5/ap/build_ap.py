#!/usr/bin/env python3
"""Stock AP -> final 4.67 AP in one explicit compile/link/patch recipe.

The custom filter loader has no legacy bank/probe/transfer objects. Retained
menu, sound, aspect, UI/cancel and playback consumers link together once; every
stock hook and relocation has exactly one final destination.
"""
from pathlib import Path
import argparse,hashlib,io,json,struct,subprocess,sys
HERE=Path(__file__).resolve().parent
SUPPORT=HERE.parent/'build_support'
sys.path[:0]=[str(SUPPORT),str(SUPPORT/'lib'),str(HERE)]
from stock_inputs import apply_recipe,sha,save
from strict_ap_link import link,align,branch
from elftools.elf.elffile import ELFFile
from menu_parent423 import patch_menu_parent
from patch_fn434 import apply_fn_patch
RX,RW=0x8e90000,0x8eb0000
CAPACITY=0x20000
EXTRA_RX,EXTRA_BYTES=0x16d3ba0,22392
CREATE=(0x1db602c,0x1d0ae64,0x1da5d24,0x1d0bc64,0x1df4e50,0x1d0bb84,0x1d9ba18,0x1d1574c,0x1e179e0,0x1d15664)
DRAW=(0x1db648c,0x1da61f8,0x1df5600)
STARTUP_HOOKS=[('startup',0x18012e4,'60a26e39'),('initial',0x34dae68,'60c21091'),('completed',0x34e5140,'60c21091'),('media',0x33c3cd4,'a003168b'),('inbound',0x3554d4c,'20008052'),('power',0x35b2a78,'fd7bbba9')]
PLAYBACK=[(0x2dbf3b0,'aspect_native_still_size',False,'fd7bbfa9'),(0x23de638,'aspect_playback_badge',False,'00008012'),(0x23dfa30,'aspect_playback_pixels',False,'031c8252'),(0x30c6f1c,'aspect_playback_zoom_map',True,branch(0x30c6f1c,0x2dbf7f0,True).hex()),(0x249069c,'aspect_playback_zoom_policy',False,'020c80b9'),(0x2492230,'aspect_playback_zoom_domain',False,'f30b40f9')]
def digest(raw):return hashlib.sha256(raw).hexdigest()
def layout_header(raw,elf,out):
    report=json.loads((HERE/'contracts/ui-layout.json').read_text());assert report['passed']
    def offset(va):
        for s in elf.iter_segments():
            if s['p_type']=='PT_LOAD'and s['p_vaddr']<=va<s['p_vaddr']+s['p_filesz']:return s['p_offset']+va-s['p_vaddr']
        raise ValueError(hex(va))
    count=max(map(int,report['allocation_bytes']))+1
    lines=['#ifndef R5_UI_LAYOUT_H','#define R5_UI_LAYOUT_H','#include <stdint.h>',f'#define R5_UI_ALLOCATOR_COUNT {count}']
    for name,key in [('allocation','allocation_bytes'),('disabled','disabled_allocation_bytes')]:lines.append('static const uint32_t r5_ui_'+name+'_bytes[] = {'+','.join(str(report[key].get(str(i),0))for i in range(count))+'};')
    for key in ['count','row','kind']:lines.append('static const unsigned r5_ui_page_'+key+'[5] = {'+','.join(str(p[key])for p in report['pages'])+'};')
    lines+=['static inline const void *r5_ui_page_table(unsigned page,unsigned direction){','switch(page*2+direction){']
    bindings={}
    for i,page in enumerate(report['pages']):
        for j,table in enumerate(page['tables']):
            at=offset(table['VA']);assert digest(raw[at:at+page['count']*52])==table['sha256']
            name=f'r5_ui_table_{i}_{j}';bindings[name]=table['VA'];lines.append(f'case {i*2+j}: {{extern const unsigned char {name}[];return {name};}}')
    lines+=['default:return 0;}}','#endif'];(out/'ui_layout.h').write_text('\n'.join(lines)+'\n');return bindings

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stock-ap',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();assert not out.exists();out.mkdir(parents=True);objects_dir=out/'objects';objects_dir.mkdir()
    baseline=out/'ap_baseline.so';baseline_report=apply_recipe(a.stock_ap,baseline,'ap_baseline')
    raw=baseline.read_bytes();elf=ELFFile(io.BytesIO(raw));assert elf['e_phnum']==6
    native=json.loads((HERE/'contracts/native.json').read_text());native.update(layout_header(raw,elf,objects_dir))
    manifest=json.loads((HERE/'shared_sources.json').read_text())
    main_sources=[HERE/name for name in ['r5_filter_file.c','r5_filter_store.c','r5_filter_runtime.c','r5_filter_boot.c','r5_runtime_session.c','r5_filter_dispatch.c','job.c']]
    main_sources += [HERE/'shared'/name for name in manifest['main']if name!='r5_sound_menu437.c']
    sound_menu=HERE/'shared/r5_sound_menu437.c'
    sound_sources=[HERE/'shared'/name for name in manifest['sound']]
    amalgam=objects_dir/'sound_all.c';amalgam.write_text(''.join('#include "'+str(s.resolve())+'"\n'for s in sound_sources))
    sources=main_sources+[sound_menu,amalgam];objects=[];commands=[]
    for source in sources:
        obj=objects_dir/(source.stem+('_asm'if source.suffix=='.S'else'')+'.o')
        cmd=['clang','--target=aarch64-none-elf','-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-ffunction-sections','-fdata-sections','-mno-outline-atomics','-mllvm','-enable-machine-outliner=always','-mllvm','-machine-outliner-reruns=2','-mllvm','-enable-merge-functions','-fno-jump-tables','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(HERE),'-I',str(HERE.parent/'common'),'-I',str(HERE/'shared'),'-I',str(objects_dir)]
        if source.suffix!='.S':cmd+=['-std=c11']
        if source.suffix=='.c' and source.name not in ['r5_stage411_hooks.c','ui_draw.c']:cmd+=['-mgeneral-regs-only']
        if source in [sound_menu,amalgam]:cmd+=['-DR5SS_SHARED_MEMSET','-I',str(HERE/'shared/include')]
        if source==amalgam:cmd+=['-DR5SS_NATIVE_SHA256']
        cmd+=['-fstack-usage','-c',str(source),'-o',str(obj)]
        r=subprocess.run(cmd,capture_output=True,text=True);(objects_dir/(source.name+'.log')).write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError(source.name+'\n'+r.stderr)
        objects.append(obj);commands.append(cmd)
    extra={};gc={};extra_objects=objects[-2:]
    code,data,memory,symbols,relocations,sections=link(objects,RX,RW,bytes(align(8*56,16)),native,gc_objects=[objects[-1]],gc_report=gc,extra_rx_objects=extra_objects,extra_rx_base=EXTRA_RX,extra_rx_size=EXTRA_BYTES,extra_rx_output=extra,merge_strings=True)
    assert not data and 0<memory<0x30000 and align(len(code),8)+22464+64<=CAPACITY,(len(code),len(data),memory)
    assert all(r['kind']!=257 for r in relocations)
    assert 'r5_filter_pt_native_get' not in symbols and 'r5_filter_pt_native_set' not in symbols
    assert not any(n.startswith(('r5_transfer_','r5_stage413_','r5_boot_','r5_stage411_probe','r5_filter_bank_'))for n in symbols)
    code=bytearray(code)
    for name,site,before in STARTUP_HOOKS:
        symbol='r5_stage411_'+name+'_hook';section=next(s for s in sections if s['name']=='.text.'+symbol);at=symbols[symbol]-RX
        nops=[i for i in range(at,at+section['size'],4)if code[i:i+4]==bytes.fromhex('1f2003d5')]
        assert len(nops)==(2 if name=='inbound'else 1)
        for off,dest in zip(nops,[0x3554ec8,0x3554d50]if name=='inbound'else[site+4]):code[off:off+4]=branch(RX+off,dest)
    rxfile=align(len(raw),65536);rwfile=rxfile+CAPACITY
    types={'PT_LOAD':1,'PT_DYNAMIC':2,'PT_GNU_EH_FRAME':0x6474e550,'PT_GNU_STACK':0x6474e551,'PT_GNU_RELRO':0x6474e552}
    def ph(h):return struct.pack('<II6Q',types[h['p_type']],h['p_flags'],*[h[k]for k in ['p_offset','p_vaddr','p_paddr','p_filesz','p_memsz','p_align']])
    headers=b''.join(ph(s.header)for s in elf.iter_segments())+struct.pack('<II6Q',1,5,rxfile,RX,RX,len(code),len(code),65536)+struct.pack('<II6Q',1,6,rwfile,RW,RW,0,memory,65536)
    assert len(headers)==448;code[:448]=headers
    image=bytearray(raw);image.extend(bytes(rxfile-len(image)));image.extend(code);image.extend(bytes(rwfile-len(image)))
    changes=[]
    def edit(at,after,before=None,reason=''):
        old=bytes(image[at:at+len(after)]);assert len(old)==len(after)
        if before is not None:assert old==before,(hex(at),old.hex(),before.hex(),reason)
        if old!=after:image[at:at+len(after)]=after;changes.append(dict(offset=at,before=old.hex(),after=after.hex(),reason=reason))
    def off(va):
        for s in elf.iter_segments():
            if s['p_type']=='PT_LOAD'and s['p_vaddr']<=va<s['p_vaddr']+s['p_filesz']:return s['p_offset']+va-s['p_vaddr']
        raise ValueError(hex(va))
    plan=json.loads((HERE/'contracts/patches.json').read_text());patches={r['va']:r for r in plan['patches']}
    for name,site,before in STARTUP_HOOKS:patches[site]=dict(va=site,kind='B',symbol='r5_stage411_'+name+'_hook',before=before)
    for va in CREATE:patches[va]=dict(va=va,kind='BL',symbol='r5_ui_create_hook',before='00013fd6')
    for i,va in enumerate(DRAW):patches[va]=dict(va=va,kind='BL',symbol='r5_ui_page_hook_'+str(i),before='40003fd6')
    for va,symbol,before in [(0x2146224,'r5_ui_guide_model_0','003c4191'),(0x2156e70,'r5_ui_guide_model_1','001c4191'),(0x182e138,'r5_ui_guide_update','fd7bbea9'),(0x182e1ac,'r5_ui_guide_destroy','fd7bbea9'),(0x240de2c,'r5_ui_guide_show',struct.pack('<I',0x35000000|(((0x240db10-0x240de2c)//4)&0x7ffff)<<5).hex())]:patches[va]=dict(va=va,kind='B',symbol=symbol,before=before)
    for va in [0x1d9bb74,0x1e17b1c]:patches[va]=dict(va=va,kind='BL',symbol='r5_ui_guide_produce',before=branch(va,0x240dae0,True).hex())
    for va,symbol,bl,before in PLAYBACK:assert va not in patches;patches[va]=dict(va=va,kind='BL'if bl else'B',symbol=symbol,before=before)
    for row in patches.values():
        va=row['va'];after=branch(va,symbols[row['symbol']],row['kind']=='BL')if row['kind']in ['B','BL']else bytes.fromhex(row['after']);edit(off(va),after,bytes.fromhex(row['before']),row.get('reason',row.get('symbol','')))
    edit(off(0x434eabc),struct.pack('<I',0x507a),struct.pack('<I',0x5049),'Custom ratio playback badge count')
    for at,after in [(32,struct.pack('<Q',rxfile)),(56,struct.pack('<H',8))]:edit(at,after)
    rel=elf.get_section_by_name('.rela.dyn');relindex={address:(i,info,addend)for i,(address,info,addend)in enumerate(struct.iter_unpack('<QQq',rel.data()))}
    for row in plan['rela_remaps']:
        i,info,addend=relindex[row['va']];assert info==1027 and addend==row['before_addend'],row
        edit(rel['sh_offset']+i*24+16,struct.pack('<q',symbols[row['symbol']]),struct.pack('<q',addend),row['symbol'])
    audit=dict(rx=RX,rw=RW,rx_bytes=len(code),bss_bytes=memory,symbols=symbols,relocations=relocations,sections=sections)
    image,rows,menu_report=patch_menu_parent(image,rxfile,code,audit,rx_capacity=CAPACITY);changes+=rows
    plt=elf.get_section_by_name('.rela.plt');assert EXTRA_RX==plt['sh_addr']+72 and EXTRA_BYTES==plt['sh_size']-72
    edit(plt['sh_offset']+72,extra['data'])
    # Preserve native secondary identity for registered private menu IDs.
    at=align(menu_report['final_rx_bytes'],16);wrapper=RX+at;entry=0x1bd2020
    delta=(0x5959000//4096)-((wrapper+32)//4096);assert -(1<<20)<=delta<(1<<20)
    adrp=0x90000000|((delta&3)<<29)|(((delta>>2)&0x7ffff)<<5)
    secondary=struct.pack('<8I',0x7100003f|(0x635<<10),0x540000a0,0x7100003f|(0x636<<10),0x54000060,0x7100003f|(0x637<<10),0x54000061,0x2a0103e0,0xd65f03c0)+struct.pack('<I',adrp)+branch(wrapper+36,entry+4)
    final_rx_size=at+len(secondary);assert final_rx_size<=CAPACITY
    edit(rxfile+at,secondary,bytes(len(secondary)));edit(off(entry),branch(entry,wrapper),bytes.fromhex('20ec01f0'))
    finalelf=ELFFile(io.BytesIO(image));index=next(i for i,s in enumerate(finalelf.iter_segments())if s['p_type']=='PT_LOAD'and s['p_vaddr']==RX)
    edit(finalelf['e_phoff']+index*56+32,struct.pack('<QQ',at+len(secondary),at+len(secondary)))
    image,fn_report=apply_fn_patch(image);changes += [dict(offset=r['file_offset'],before=r['before'],after=r['after'])for r in fn_report['patches']]
    reverse=bytearray(image[:len(raw)])
    for row in reversed(changes):
        at=row['offset'];before=bytes.fromhex(row['before'])
        if at<len(raw):reverse[at:at+min(len(before),len(raw)-at)]=before[:min(len(before),len(raw)-at)]
    assert reverse==raw,'All final patches must reverse to stock-derived baseline'
    finalelf=ELFFile(io.BytesIO(image));assert finalelf['e_phnum']==8
    assert [dict(s.header)for s in list(finalelf.iter_segments())[:6]]==[dict(s.header)for s in elf.iter_segments()]
    loads=[s for s in finalelf.iter_segments()if s['p_type']=='PT_LOAD']
    for s in loads:assert s['p_filesz']<=s['p_memsz']and s['p_offset']%65536==s['p_vaddr']%65536 and s['p_flags']&3!=3
    for x,y in zip(loads,loads[1:]):assert align(x['p_vaddr']+x['p_memsz'],65536)<=y['p_vaddr']
    for name in ['.dynsym','.dynstr','.init_array','.fini_array']:assert elf.get_section_by_name(name).data()==finalelf.get_section_by_name(name).data()
    (out/'appFw.so').write_bytes(image);(out/'runtime_rx.bin').write_bytes(code);(out/'runtime_extra_rx.bin').write_bytes(extra['data'])
    save(out/'module_audit.json',dict(**audit,commands=commands,section_gc=gc,extra_rx_bytes=len(extra['data']),sources={str(p.relative_to(HERE)):sha(p)for p in sorted(set(main_sources+[sound_menu]+sound_sources))}))
    save(out/'ap_build.json',dict(passed=True,version='4.67',sha256=digest(image),bytes=len(image),stock_recipe=baseline_report,reverse_to_baseline_exact=True,patches=changes,menu_parent=menu_report,fn=fn_report,rx_bytes=final_rx_size,bss_bytes=memory,all_features_linked_once=True,legacy_bank_flow_present=False,device_tested=False))
    print(json.dumps(dict(passed=True,version='4.67',AP_sha256=digest(image),bytes=len(image),rx_bytes=final_rx_size,bss_bytes=memory)))
if __name__=='__main__':main()
