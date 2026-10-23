"""Static conservative original-native-access-footprint containment proof.

This is not a recovered C array size, allocator extent or runtime safety proof.
No execution or device access. Frozen replay and firmware are read only.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'analysis/r5_custom_filter423_20261023/menu_research')]
from read_menu import Image

def main():
 old=ROOT/'analysis/r5_custom_filter423_20261023/ap/appFw.so'
 new=HERE/'ap/appFw.so'
 stock=ROOT/'unpacked/r5/usr_complete/lib/appFw.so'
 images=[Image(x)for x in (stock,old,new)]
 spans=[('native_primary_normalize',0x1bd1dd4,0x124),
        ('native_public_normalize_caller',0x1bd851c,0x30),
        ('cached_gate_consumer',0x1be03ac,0x84),
        ('cached_profile_consumer',0x1be04b4,0x84),
        ('cache_flag_initializer',0x1bdfcc0,0x218)]
 receipts=[]
 for name,va,size in spans:
  b=images[0].read(va,size);previous=images[1].read(va,size);candidate=images[2].read(va,size)
  assert previous==candidate
  if name=='native_public_normalize_caller':
   assert b[:0x24]==previous[:0x24] and b[0x28:]==previous[0x28:]
  else:assert previous==b
  receipts.append(dict(name=name,va=hex(va),bytes=size,stock_sha256=hashlib.sha256(b).hexdigest(),candidate_sha256=hashlib.sha256(candidate).hexdigest(),stock_exact_bytes=b.hex(),candidate_exact_bytes=candidate.hex(),stock423424_identical=previous==b,versions423424_identical=True,exception='423 retains the exact private-635 normalization wrapper at BL1BD8540; all other native fallback behavior remains original' if previous!=b else None,disassembly=images[0].dis(va,size)))
 # The native fallback is an explicit returned canonical value, not guessed
 # from a neighboring pointer or the virtual memory mapping.
 assert images[0].read(0x1bd1eb8,4)==bytes.fromhex('c0c68052') # mov w0,#636
 assert images[0].read(0x1bd1ec4,4)==bytes.fromhex('40000054') # beq return
 assert images[0].read(0x1be0404,4)==bytes.fromhex('46e0ff97') # bl public normalize
 assert images[0].read(0x1be0410,4)==bytes.fromhex('020380d2') # stride=24
 assert images[0].read(0x1be041c,4)==bytes.fromhex('0004029b') # madd x0,index,24,base
 assert images[0].read(0x1be0424,4)==bytes.fromhex('00084039') # ldrb w0,[x0,#2]
 assert images[0].read(0x1be052c,4)==bytes.fromhex('00304039') # ldrb w0,[x0,#12]
 got=0x5928070;base=images[0].pointer(got)
 assert base==0x7532ed0 and all(x.pointer(got)==base for x in images)
 private=0x635;fallback=0x636;stride=24
 lo=base+private*stride;end=lo+stride
 fallback_lo=base+fallback*stride
 fallback_reads=[dict(pc='0x1be0424',address=hex(fallback_lo+2),bytes=1),dict(pc='0x1be052c',address=hex(fallback_lo+12),bytes=1)]
 assert end==fallback_lo and end<=min(int(x['address'],16)for x in fallback_reads)
 bss=images[0].sections['.bss'];bsslo=bss[3];bssend=bsslo+bss[5]
 assert bsslo<=lo<end<fallback_lo+13<=bssend
 primary=list(struct.iter_unpack('<II',images[0].read(0x3e44de0,0x31a8)))
 assert len(primary)==1589 and max(v for k,v in primary)==0x634
 next_ref=min(v for _,v in images[0].relocs.values() if v>base)
 result=dict(schema='r5-menu424-cache-native-footprint/1',passed=True,
  AP_sha256=hashlib.sha256(new.read_bytes()).hexdigest(),
  source423_sha256=hashlib.sha256(old.read_bytes()).hexdigest(),
  stock_sha256=hashlib.sha256(stock.read_bytes()).hexdigest(),
  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  private_index_in_bounds=True,bounds_meaning='original_native_access_footprint',
  cache_got=hex(got),cache_base=hex(base),record_stride=stride,
  private_record=dict(index=hex(private),start=hex(lo),end_exclusive=hex(end)),
  native_fallback=dict(index=hex(fallback),record_start=hex(fallback_lo),actual_native_reads=fallback_reads,
   provenance='Native primary normalization returns 636 on missing key; original cached consumers call that normalizer then access base + 636*24 + 2 or +12 without an intervening upper-bound rejection.'),
  original_alias=dict(table='0x3e44de0',entries=len(primary),maximum_mapped_value='0x634',missing_key_return='0x636'),
  initialization=dict(section='.bss',section_start=hex(bsslo),section_end_exclusive=hex(bssend),loader_zero_fill=True,
   native_flags='1BDFCC0 iterates registered menu records and initializes bytes +0/+1/+4 and optional +10 pointer using 24-byte indexing. No separate whole-array size/clear loop was recovered; untouched entries begin as loader-zeroed BSS.'),
  neighboring_reference=dict(address=hex(next_ref),distance=hex(next_ref-base),not_used_as_array_size_proof=True),
  ranges=receipts,
  limitations=['Exact C object/array extent is unknown; this receipt proves only containment within the access footprint already used by original native fallback consumers, plus BSS mapping/zero-fill.','No claim that a particular original GUI event actually requests fallback 636, no complete invalid-ID caller enumeration, no heap/cache/device-runtime proof.','No firmware changes. The additional menu 635 is below the original fallback 636 access range; original normalization fallback and cache consumers are byte-identical across stock, 423 and 424.'])
 out=HERE/'cache_capacity424.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k]for k in ('passed','AP_sha256','private_index_in_bounds','bounds_meaning','private_record','native_fallback')},ensure_ascii=False))
if __name__=='__main__':main()
