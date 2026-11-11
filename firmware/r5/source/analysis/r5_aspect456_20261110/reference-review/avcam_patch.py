"""适配锁定 AVCAM 的 JPEG 窗口与 HEIF 原生编码 ROI。"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from elftools.elf.elffile import ELFFile
import sys
ROOT=HERE.parents[2] if False else Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"projects/firmware/development/shutter-sound-recovery455/src/lib"))
from strict_ap_link import link,branch

HERE=Path(__file__).resolve().parent


def compile_objects(sources, output):
    objects=[];commands=[]
    for source in sources:
        obj=output/(source.stem+source.suffix+'.o')
        command=[shutil.which('clang'),'--target=aarch64-none-elf','-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-vectorize','-fno-slp-vectorize','-I',str(HERE/'source'),'-c',str(source),'-o',str(obj)]
        r=subprocess.run(command,capture_output=True,text=True)
        (output/(source.name+'.log')).write_text(r.stdout+r.stderr)
        if r.returncode: raise ValueError(r.stdout+r.stderr)
        commands.append(command);objects.append(obj)
    return objects,commands

def assemble(source,address,output,bindings=''):
    objects,commands=compile_objects([source],output)
    ext={}
    for row in bindings.split(';'):
        if row.strip():
            k,v=row.split('=');ext[k.strip()]=int(v.strip(),0)
    code,rw,memory,symbols,relocations,layout=link(objects,address,0x1100000,b'',ext)
    if rw or memory: raise ValueError('AVCAM helper has writable state')
    return code,symbols,commands

def assemble_heif(output):
    address=0xc5b380
    objects,commands=compile_objects([HERE/'source'/n for n in ('avcam_heif.c','crop_core.c','avcam_heif.S')],output)
    externals=dict(aspect_native_prepare=0x206378,aspect_native_headers=0x1f52d4,
        aspect_native_header_size=0x1f30c8,aspect_native_makernote_full_size=0x1f377c,
        aspect_native_encode_body=0x200738,aspect_native_request_body=0x1f9978,
        aspect_native_raw_headers=0x1f5388)
    code,rw,memory,symbols,relocations,layout=link(objects,address,0x1100000,b'',externals)
    if rw or memory or address+len(code)>0xc5c000: raise ValueError('AVCAM helper layout exceeds bound')
    return code,symbols,commands


def patch_avcam(raw,output):
    lock=json.loads((HERE/'native-inspection/identities.json').read_text())['AVCAM']
    if len(raw)!=lock['bytes'] or hashlib.sha256(raw).hexdigest()!=lock['sha256']:
        raise ValueError('AVCAM 原厂身份不匹配')
    if output.exists():raise ValueError('输出目录已存在')
    output.mkdir(parents=True);(output/'INCOMPLETE.json').write_text('{"state":"PATCHING"}\n')
    bindings='aspect_avcam_construct = 0x1f4160; aspect_avcam_assert = 0x20bb10; aspect_avcam_assert_file = 0x42977a; aspect_avcam_assert_function = 0x429c59;'
    jpeg,symbols,commands=assemble(HERE/'source/avcam_jpeg.S',0x1f4dbc,output,bindings)
    thm,_,more=assemble(HERE/'source/avcam_thm.S',0x20684c,output);commands+=more
    heif,heif_symbols,more=assemble_heif(output);commands+=more;symbols.update(heif_symbols)
    if len(jpeg)>296 or len(thm)!=104 or symbols['aspect_avcam_set_slot']!=0x1f4dfc:
        raise ValueError(f'AVCAM 窗口容量/入口不匹配：JPEG={len(jpeg)}, THM={len(thm)}')
    image=bytearray(raw);patches=[]
    def edit(at,code):
        patches.append(dict(offset=at,before=image[at:at+len(code)].hex(),after=code.hex()))
        if bytes(image[at:at+len(code)]) != raw[at:at+len(code)]: raise ValueError('overlapping patches')
        image[at:at+len(code)]=code
    edit(0x1f4dbc,jpeg+bytes.fromhex('1f2003d5')*((296-len(jpeg))//4))
    for at in (0x1f40ec,0x1f4110):edit(at,branch(at,symbols['aspect_avcam_jpeg'],True))
    # SCN mode 1 的目标尺寸沿用实际 source valid WH。
    scn_source=output/'scn.S';scn_source.write_text('.text\nldr w0,[x27,#4]\nstr w0,[sp,#0xd8]\nb aspect_scn_continue\n')
    scn,_,more=assemble(scn_source,0x2066b4,output,'aspect_scn_continue = 0x206490;');commands+=more
    if len(scn)!=12:raise ValueError('SCN 窗口长度错误')
    edit(0x2066b4,scn);edit(0x20684c,thm)
    # 保持原生 L plan；只裁编码的局部 view，M/S 原有 resize 先裁输入。
    edit(0x20746c,branch(0x20746c,symbols['aspect_avcam_heif_prepare'],True))
    for at in (0x207048,0x2071e8,0x207264):
        edit(at,branch(at,symbols['aspect_avcam_raw_preview_prepare'],True))
    edit(0x200734,branch(0x200734,symbols['aspect_avcam_heif_entry']))
    edit(0x1f9970,branch(0x1f9970,symbols['aspect_avcam_heif_request'])+bytes.fromhex('1f2003d5'))
    # 原RAM/BSS范围保持。程序自身的RAM快照搬到新增代码之后，防止恢复覆盖代码。
    code_end=0xc5b380+len(heif)
    backup_start=(code_end+127)&~127
    ram_bytes=0xc5b378-0xba7fc0
    backup_end=backup_start+ram_bytes
    tail_end=(backup_end+127)&~127
    if tail_end+4>0x1000000:raise ValueError('AVCAM 布局超出原厂16MiB可执行保留区')
    for at,register in ((0x2db28,9),(0x2db58,20),(0x2dc30,0),(0x2dc50,0),(0x2e22c,1)):
        delta=((backup_start&~4095)-(at&~4095))//4096
        immediate=delta&0x1fffff
        adrp=0x90000000|((immediate&3)<<29)|((immediate>>2)<<5)|register
        add=0x91000000|((backup_start&4095)<<10)|(register<<5)|register
        edit(at,adrp.to_bytes(4,'little')+add.to_bytes(4,'little'))
    base=0xffffffc001000000
    edit(0x32d9b0,(base+backup_start).to_bytes(8,'little'))
    edit(0x32d9b8,(base+backup_end).to_bytes(8,'little'))
    edit(0x1cc,(base+tail_end).to_bytes(8,'little'))
    image.extend(bytes(0xc5b380-len(image))+heif)
    reverse=bytearray(image)
    del reverse[len(raw):]
    for p in reversed(patches):
        b=bytes.fromhex(p['before']);reverse[p['offset']:p['offset']+len(b)]=b
    if reverse!=raw:raise AssertionError('AVCAM 定长反向审计失败')
    (output/'av-cam.bin').write_bytes(image)
    report=dict(passed=True,camera_io=False,device_tested=False,bytes=len(image),
        sha256=hashlib.sha256(image).hexdigest(),input_sha256=lock['sha256'],patches=patches,
        symbols=symbols,jpeg_code_bytes=len(jpeg),heif_code_bytes=len(heif),appended_bytes=len(image)-len(raw),
        original_bytes=len(raw),commands=commands,reverse_exact=True,
        snapshot_layout=dict(code_start=0xc5b380,code_end=code_end,ram_start=0xba7fc0,
            ram_end=0xc5b378,ram_bytes=ram_bytes,backup_start=backup_start,backup_end=backup_end,
            tail_end=tail_end,executable_reserved_bytes=0x1000000,header_ram_size_unchanged=True),
        sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (HERE/'source'/n for n in ('avcam_jpeg.S','avcam_thm.S','avcam_heif.c','avcam_heif.S','crop_core.c'))})
    (output/'patch.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(output/'INCOMPLETE.json').unlink()
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=patch_avcam((ROOT/'unpacked/r5/system_main/av-cam.bin').read_bytes(),a.output)
    print(json.dumps({k:r[k] for k in ('passed','sha256','bytes','heif_code_bytes','reverse_exact')}))
