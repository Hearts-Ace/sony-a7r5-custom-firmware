"""Final ELF segment address translator for native replay.
"""
from pathlib import Path
import io
from elftools.elf.elffile import ELFFile
class Image:
 def __init__(self,path):
  self.path=Path(path);self.raw=self.path.read_bytes();self.elf=ELFFile(io.BytesIO(self.raw))
  self.loads=[s.header for s in self.elf.iter_segments() if s['p_type']=='PT_LOAD']
 def offset(self,va):
  for s in self.loads:
   if s['p_vaddr']<=va<s['p_vaddr']+s['p_filesz']:return s['p_offset']+va-s['p_vaddr']
  raise ValueError(hex(va))
