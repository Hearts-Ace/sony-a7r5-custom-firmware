"""Read-only R5 AP instruction, branch, pointer and ADRP reference inspection."""
from pathlib import Path
import argparse, hashlib, io, json, struct, sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
import numpy as np

DEFAULT=ROOT/'unpacked/r5/usr_complete/lib/appFw.so'
class Image:
    def __init__(self,path=DEFAULT):
        self.path=Path(path);self.raw=self.path.read_bytes()
        self.elf=ELFFile(io.BytesIO(self.raw))
        self.loads=[s.header for s in self.elf.iter_segments() if s['p_type']=='PT_LOAD']
        self.md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    def offset(self,va):
        for s in self.loads:
            if s['p_vaddr']<=va<s['p_vaddr']+s['p_filesz']:
                return s['p_offset']+va-s['p_vaddr']
        raise ValueError(hex(va))
    def disasm(self,lo,hi):
        off=self.offset(lo)
        return '\n'.join(f'{i.address:08x}: {i.mnemonic:8} {i.op_str}' for i in self.md.disasm(self.raw[off:off+hi-lo],lo))
    def adrp_refs(self,va):
        rows=[]
        for s in self.loads:
            if not s['p_flags']&1:continue
            code=np.frombuffer(self.raw,dtype='<u4',count=s['p_filesz']//4,offset=s['p_offset'])
            idx=np.flatnonzero((code&0x9f000000)==0x90000000)
            words=code[idx].astype(np.int64)
            imm=((words>>29)&3)|(((words>>5)&0x7ffff)<<2)
            imm=np.where(imm&(1<<20),imm-(1<<21),imm)<<12
            pcs=idx*4+s['p_vaddr'];pages=(pcs&~4095)+imm
            for index,pc in zip(idx[pages==(va&~4095)],pcs[pages==(va&~4095)]):
                reg=int(code[index]&31)
                for j in range(1,9):
                    if index+j>=len(code):break
                    w=int(code[index+j]);rn=(w>>5)&31
                    if rn==reg and w&0xff000000==0x91000000:
                        immediate=((w>>10)&4095)<<(12 if w&(1<<22) else 0)
                        if (va&~4095)+immediate==va:
                            rows.append(dict(adrp=int(pc),use=int(pc+j*4),kind='adrp_add'))
                    if rn==reg and w&0xffc00000==0xf9400000:
                        if (va&~4095)+(((w>>10)&4095)*8)==va:
                            rows.append(dict(adrp=int(pc),use=int(pc+j*4),kind='adrp_ldr'))
                    if w&0x7c000000==0x14000000:break
        return rows
    def branches(self,target):
        rows=[]
        for s in self.loads:
            if not s['p_flags']&1:continue
            code=np.frombuffer(self.raw,dtype='<u4',count=s['p_filesz']//4,offset=s['p_offset'])
            idx=np.flatnonzero((code&0x7c000000)==0x14000000)
            words=code[idx].astype(np.int64)
            imm=words&0x3ffffff
            imm=np.where(imm&(1<<25),imm-(1<<26),imm)*4
            pcs=idx*4+s['p_vaddr'];targets=pcs+imm
            for pc,w in zip(pcs[targets==target],words[targets==target]):
                rows.append(dict(site=int(pc),kind='bl' if w&0x80000000 else 'b'))
        return rows
    def reloc_refs(self,target):
        s=self.elf.get_section_by_name('.rela.dyn')
        a=np.frombuffer(s.data(),dtype=[('offset','<u8'),('info','<u8'),('addend','<i8')])
        ds=self.elf.get_section_by_name('.dynsym')
        symbols=np.frombuffer(ds.data(),dtype=[('name','<u4'),('info','u1'),('other','u1'),('section','<u2'),('value','<u8'),('size','<u8')])
        values=a['addend']+symbols['value'][(a['info']>>32).astype(np.int64)].astype(np.int64)
        return [dict(offset=int(row['offset']),file=s['sh_offset']+int(i)*24,info=int(row['info']),addend=int(row['addend']),resolved=int(values[i])) for i,row in zip(np.flatnonzero(values==target),a[values==target])]
def main():
    p=argparse.ArgumentParser();p.add_argument('--image',type=Path,default=DEFAULT)
    p.add_argument('--disasm',nargs=2,type=lambda x:int(x,0));p.add_argument('--refs',nargs='+',type=lambda x:int(x,0))
    a=p.parse_args();im=Image(a.image)
    if a.disasm:print(im.disasm(*a.disasm))
    for target in a.refs or []:
        print(json.dumps(dict(target=hex(target),adrp=im.adrp_refs(target),branches=im.branches(target),relocations=im.reloc_refs(target))))
if __name__=='__main__':main()
