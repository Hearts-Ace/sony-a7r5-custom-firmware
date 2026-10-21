#!/usr/bin/env python3
"""Offline actual C codec/transfer state-machine tests, no camera IO."""
from pathlib import Path
import ctypes as C,importlib.util,json,subprocess,struct,zlib,hashlib
H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native12',H/'native_overwrite_config.py');py=importlib.util.module_from_spec(spec);spec.loader.exec_module(py)
class Look(C.Structure):_fields_=[('name',C.c_char*32),('cc1',(C.c_int16*8)*3),('block13',((C.c_int16*6)*16)*3),('gamma',C.c_uint32*129)]
class Set(C.Structure):_fields_=[('mask',C.c_uint32),('look',Look*12)]
class Tx(C.Structure):_fields_=[('set',C.POINTER(Set)),*[(n,C.c_uint32)for n in ('token','mask','crc','slot','sequence','phase','error')],*[(n,C.c_uint64)for n in ('deadline','last','retry')]]
SEND=C.CFUNCTYPE(C.c_int,C.c_void_p,C.POINTER(C.c_ubyte),C.c_size_t)
class IO(C.Structure):_fields_=[('context',C.c_void_p),('send',SEND)]
def entry(number):return dict(number=number,name='Native-%02d'%number,cc1_delta=[[0,0,0,0,256,256,256,256],[0]*8,[0]*8],block13=[[[0]*6 for s in range(16)]for g in range(3)],gamma_native_129=[i*1023 for i in range(129)])
def config(mask):return dict(schema=py.SCHEMA,model='ILCE-7RM5',baseline_ap_sha256=py.AP_SHA,baseline_cp_sha256=py.CP_SHA,additional_compensation_matrix_enabled=False,compensation_grid_enabled=False,entries=[entry(i)for i in range(1,13)if mask>>(i-1)&1])
def patch_crc(blob):
 b=bytearray(blob);b[112:116]=bytes(4);struct.pack_into('<I',b,112,zlib.crc32(b));return bytes(b)
def main():
 (H/'objects').mkdir(exist_ok=True);shared=H/'objects/host_codec.dylib';subprocess.run(['clang','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror','-I',str(H),str(H/'r5_stage410_codec.c'),str(H/'r5_stage413_transfer_core.c'),'-o',str(shared)],check=True)
 lib=C.CDLL(str(shared));lib.r5_decode_look_file.argtypes=[C.c_void_p,C.c_size_t,C.POINTER(Set)];lib.r5_encode_look_file.argtypes=[C.POINTER(Set),C.c_void_p,C.c_size_t];lib.r5_encode_look_file.restype=C.c_size_t
 lib.r5_transfer_ap_begin.argtypes=[C.POINTER(Tx),C.POINTER(Set),C.c_uint32,C.c_uint32,C.c_uint64,C.c_uint64]
 lib.r5_transfer_ap_step.argtypes=[C.POINTER(Tx),C.POINTER(IO),C.c_uint64,C.c_void_p];lib.r5_transfer_ap_ack.argtypes=[C.POINTER(Tx),C.c_void_p,C.c_size_t,C.c_uint64]
 counters=dict(codec_roundtrips=0,invalid_files=0,transfer_masks=0,transfer_packets=0,hostile_acks=0)
 for mask in range(1,4096):
  packed=py.pack(config(mask));s=Set();assert lib.r5_decode_look_file(packed,len(packed),C.byref(s))==0 and s.mask==mask
  out=C.create_string_buffer(14528);n=lib.r5_encode_look_file(C.byref(s),out,14528);assert out.raw[:n]==packed;counters['codec_roundtrips']+=1
  tx=Tx();assert not lib.r5_transfer_ap_begin(C.byref(tx),C.byref(s),0x12345678,0xaabbccdd,0,3000)
  captured=[]
  @SEND
  def sender(_,p,n):captured.append(C.string_at(p,n));return 0
  io=IO(None,sender);wire=C.create_string_buffer(1204);seen=0
  for step in range(14):
   assert not lib.r5_transfer_ap_step(C.byref(tx),C.byref(io),step,C.byref(wire))
   p=captured[-1];op=p[2];assert p[:2]==bytes([0xe7,2])and p[4:8]==b'R5NX'
   assert zlib.crc32(p[:28]+bytes(4)+p[32:])==struct.unpack_from('<I',p,28)[0]
   slot=struct.unpack_from('<I',p,16)[0]
   if op==2:
    assert len(p)==1204 and p[32:]==bytes(s.look[slot-1]);seen|=1<<(slot-1)
   else:assert len(p)==32
   a=bytearray(p[:32]);a[2]=0x80;a[28:32]=bytes(4);a+=struct.pack('<III',0x35424c53 if op==3 else 0x35424c44,0,seen);struct.pack_into('<I',a,28,zlib.crc32(a))
   rc=lib.r5_transfer_ap_ack(C.byref(tx),bytes(a),len(a),step);assert rc==(1 if op==3 else 0)
   counters['transfer_packets']+=1
   if rc==1:break
  assert tx.phase==4 and seen==mask;counters['transfer_masks']+=1
 # Every invalid file leaves the destination entirely untouched.
 good=py.pack(config(4095));mutations=[]
 for off,val in [(0,ord('X')),(8,1),(20,13),(24,0),(25,0xf0),(128,0),(128,13),(132,0),(128+1176,1),(128+660,1)]:
  b=bytearray(good);b[off]=val;mutations.append(patch_crc(b))
 mutations +=[good[:-1],good+bytes(1)]
 for b in mutations:
  s=Set();C.memset(C.byref(s),0xa5,C.sizeof(s));before=bytes(s);assert lib.r5_decode_look_file(b,len(b),C.byref(s))==2 and bytes(s)==before;counters['invalid_files']+=1
 # Wrong CRC/ABI/token/sequence/state cannot publish.
 for off in (1,4,8,12,16,20,24,28,32,36,40):
  s=Set();s.mask=1;tx=Tx();assert lib.r5_transfer_ap_begin(C.byref(tx),C.byref(s),123,456,0,3000)==0
  @SEND
  def sink(_,p,n):return 0
  io=IO(None,sink);wire=C.create_string_buffer(1204);assert not lib.r5_transfer_ap_step(C.byref(tx),C.byref(io),1,wire)
  ack=bytearray(wire.raw[:32]);ack[2]=0x80;ack[28:32]=bytes(4);ack+=struct.pack('<III',0x35424c44,0,0);ack[off]^=1
  if off!=28:struct.pack_into('<I',ack,28,zlib.crc32(ack))
  assert lib.r5_transfer_ap_ack(C.byref(tx),bytes(ack),44,2)==-1 and tx.phase==5;counters['hostile_acks']+=1
 # Non-ASCII labels roundtrip by encoded byte length, not Unicode count.
 utf_ok=0;utf_bad=0
 for name in ('人像暖色','FL2 自定义','a'*31,'😀'*7+'abc'):
  cfg=config(1);cfg['entries'][0]['name']=name;b=py.pack(cfg);s=Set();assert not lib.r5_decode_look_file(b,len(b),C.byref(s));assert bytes(s.look[0].name)==name.encode();utf_ok+=1
 for invalid in (b'\xc0\x80',b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\xe4\xb8',b'\xc2\x9f',b'a'*32):
  b=bytearray(py.pack(config(1)));b[132:164]=invalid+bytes(32-len(invalid));b=patch_crc(b);s=Set();assert lib.r5_decode_look_file(b,len(b),C.byref(s))==2;utf_bad+=1
 counters.update(utf8_valid_names=utf_ok,utf8_invalid_names=utf_bad)
 report=dict(passed=True,**counters,wire_bytes=1204,record_bytes=C.sizeof(Look),set_bytes=C.sizeof(Set),limitations=['Host C ABI/state machine only. Native filesystem, queues, hardware and menu/display remain separate acceptance.'])
 (H/'host_tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
