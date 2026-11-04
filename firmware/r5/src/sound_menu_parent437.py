"""Add Sound Option selection and independent private-volume peers.

This function does NOT pretend that changing a pointer alone is executable:
its returned RELATIVE relocation must be appended by the unified AP builder.
The existing 4.36 menu-parent builder already relocates .rela.plt and has to
reserve one more .rela.dyn record for this target; original relocs stay intact.
"""
import io,struct
from elftools.elf.elffile import ELFFile
GROUP=0x505fcc8
RECORD=0x505fd98
EXPECTED_IDS=list(range(0x451,0x459))
def patch_sound_group(image,descriptor,volume_descriptor):
 result=bytearray(image);elf=ELFFile(io.BytesIO(image))
 def offset(va,n):
  for s in elf.iter_segments():
   if s['p_type']=='PT_LOAD' and s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz']:return s['p_offset']+va-s['p_vaddr']
  raise ValueError('Unmapped native menu data')
 g=offset(GROUP,0xe8);a=offset(RECORD,48)
 if struct.unpack_from('<III',result,g)!=(0x3c,0x02006032,8):raise ValueError('Unexpected Sound Option header')
 if [struct.unpack_from('<Q',result,g+16+i*24)[0] for i in range(8)]!=EXPECTED_IDS:raise ValueError('Unexpected original peer IDs')
 if bytes(result[a:a+48])!=bytes(48):raise ValueError('New record reserve is not empty')
 for pointer in (descriptor,volume_descriptor):
  if not (0x8ea0000<=pointer<0x8ed0000) or pointer%8:raise ValueError('Descriptor outside current mapped private BSS')
 changes=[]
 def edit(at,after):
  before=bytes(result[at:at+len(after)]);result[at:at+len(after)]=after
  changes.append(dict(offset=at,before=before.hex(),after=after.hex()))
 edit(g+8,struct.pack('<I',10));edit(a,struct.pack('<6Q',0x636,descriptor,0,0x637,volume_descriptor,0))
 old_relas=elf.get_section_by_name('.rela.dyn')
 targets=(RECORD+8,RECORD+24+8)
 if any(r['r_offset'] in targets for r in old_relas.iter_relocations()):raise ValueError('New relative target already used')
 return result,changes,[(targets[0],1027,descriptor),(targets[1],1027,volume_descriptor)]
