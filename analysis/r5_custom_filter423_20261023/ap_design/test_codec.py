#!/usr/bin/env python3
from pathlib import Path
import ctypes as C, hashlib,json,struct,subprocess,zlib
HERE=Path(__file__).resolve().parent;SRC=HERE/'source';ROOT=HERE.parents[2]
class Look(C.Structure):
 _fields_=[('short_name',C.c_char*24),('full_name',C.c_char*64),('cc1',(C.c_int16*8)*3),('block13',((C.c_int16*6)*16)*3),('gamma',C.c_uint32*129),('grid',(C.c_int8*405)*3),('padding',C.c_uint8)]
class Set(C.Structure):_fields_=[('mask',C.c_uint32),('look',Look*12)]
class Request(C.Structure):_fields_=[('seq',C.c_uint32),('selected',C.c_uint32),('crc',C.c_uint32),('alias',C.c_uint32)]
assert C.sizeof(Look)==2444 and C.sizeof(Set)==29332
libpath=HERE/'codec_test.dylib'
cmd=['clang','-dynamiclib','-std=c11','-Wall','-Wextra','-Werror','-I',str(SRC),'-I',str(ROOT/'analysis/r5_runtime_load421_20261022/import'),*[str(SRC/x)for x in ('r5_stage423_codec.c','r5_filter_names423.c','r5_filter_selection423.c','sd_native_store.c','sd_native_persist.c')],'-o',str(libpath)]
subprocess.run(cmd,check=True);lib=C.CDLL(str(libpath))
lib.r5_encode_look_file.restype=C.c_size_t
lib.r5_filter_compact_set_crc.restype=C.c_uint32
lib.r5_filter_short_name.restype=C.c_char_p;lib.r5_filter_full_name.restype=C.c_char_p
s=Set();s.mask=4095
for i,v in enumerate(s.look):
 v.short_name=('滤镜'+str(i+1)).encode();v.full_name=('自定义滤镜 全称 '+str(i+1)).encode()
 for j in range(129):v.gamma[j]=min(j*1024,131071)
 for g in range(3):
  for j in range(8):v.cc1[g][j]=0 if g or j<4 else 512
  for j in range(405):v.grid[g][j]=((i+g+j)%128)-64
out=C.create_string_buffer(29552);size=lib.r5_encode_look_file(C.byref(s),out,len(out));assert size==29552
raw=out.raw[:size];h=bytearray(raw);struct.pack_into('<I',h,112,0);assert zlib.crc32(h)==struct.unpack_from('<I',raw,112)[0]
assert raw[:8]==b'R5CUST4\0' and struct.unpack_from('<I',raw,8)[0]==4
restored=Set();assert lib.r5_decode_look_file(out,size,C.byref(restored))==0;assert bytes(s)==bytes(restored)
rows=[]
def invalid(label,b,reseal=True):
 b=bytearray(b)
 if reseal:struct.pack_into('<I',b,112,0);struct.pack_into('<I',b,112,zlib.crc32(b))
 previous=bytes(restored);buf=C.create_string_buffer(bytes(b));assert lib.r5_decode_look_file(buf,len(b),C.byref(restored))==2,label;assert bytes(restored)==previous;rows.append(label)
for off in (0,8,12,16,20,24,28,32,48,80,116,128,128+2447):
 b=bytearray(raw);b[off]^=0xff;invalid('header/record '+str(off),b)
for label,payload in [('empty',b'\0'*24),('no_nul',b'a'*24),('overlong',b'\xc0\xaf\0'+b'\0'*21),('surrogate',b'\xed\xa0\x80\0'+b'\0'*20),('c0',b'a\n\0'+b'\0'*21),('c1',b'\xc2\x80\0'+b'\0'*21),('tail',b'a\0b'+b'\0'*21),('truncated',b'a'*22+b'\xe4\0')]:
 b=bytearray(raw);b[132:156]=payload;invalid('short '+label,b)
for field,value,fmt in [('CC1',-1025,'h'),('B13',8192,'h'),('gamma',131072,'I'),('grid',64,'b')]:
 off={'CC1':92,'B13':140,'gamma':716+128*4,'grid':1232}[field];b=bytearray(raw);struct.pack_into('<'+fmt,b,128+off,value);invalid(field,b)
b=bytearray(raw);struct.pack_into('<I',b,128+2452,1);invalid('duplicate slot',b)
invalid('truncated',raw[:-1]);invalid('checksum',raw[:-1]+bytes([raw[-1]^1]),False)
# Independent canonical projection and CRC, including full_name exclusion.
c=bytearray(struct.pack('<I',s.mask))
for i,v in enumerate(s.look):
 packed=C.create_string_buffer(2392);assert lib.r5_filter_pack_compact(C.byref(v),packed)==1
 expected=bytes(v)[:24]+b'\0'*8+bytes(v)[88:1228]+struct.pack('<I',1)+bytes(v)[1228:2443]+b'\0'
 assert packed.raw==expected
 c+=struct.pack('<I',i+1)+expected
assert lib.r5_filter_compact_set_crc(C.byref(s))==zlib.crc32(c)
crc=lib.r5_filter_compact_set_crc(C.byref(s));C.memset(C.addressof(s.look[0])+24,0,64);s.look[0].full_name=b'Changed full name';assert lib.r5_filter_compact_set_crc(C.byref(s))==crc
# Immutable name pointers survive later publication; slot0 not a config.
assert lib.r5_filter_names_publish(C.byref(s))==1;assert lib.r5_filter_available_mask()==4095
assert lib.r5_filter_short_name(1)=='滤镜1'.encode();assert lib.r5_filter_full_name(1)==b'Changed full name'
assert not lib.r5_filter_short_name(0) and not lib.r5_filter_full_name(13)
# SELECT ACK binds exact transfer identity, serial, selection and CRC.
r=Request(1,7,crc,0x12345678);p=C.create_string_buffer(32);assert lib.r5_filter_select_encode(C.byref(r),p)==1
b=bytearray(p.raw);assert b[:8]==b'\xea\x01\x01\x20R5FS';b[2]=0x81;struct.pack_into('<I',b,28,0);struct.pack_into('<I',b,28,zlib.crc32(b));ack=C.create_string_buffer(bytes(b));assert lib.r5_filter_select_ack(C.byref(r),ack,32)==1
for off in (8,12,16,20):
 bad=bytearray(b);bad[off]^=1;struct.pack_into('<I',bad,28,0);struct.pack_into('<I',bad,28,zlib.crc32(bad));assert lib.r5_filter_select_ack(C.byref(r),C.create_string_buffer(bytes(bad)),32)==-256
for status in range(1,6):
 bad=bytearray(b);struct.pack_into('<I',bad,24,status);struct.pack_into('<I',bad,28,0);struct.pack_into('<I',bad,28,zlib.crc32(bad));assert lib.r5_filter_select_ack(C.byref(r),C.create_string_buffer(bytes(bad)),32)==-status
empty=Set();assert lib.r5_encode_look_file(C.byref(empty),out,len(out))==128;assert lib.r5_decode_look_file(out,128,C.byref(restored))==0 and restored.mask==0
interop=HERE.parent/'web_tests/interop_v4.bin'
if interop.exists():
 data=interop.read_bytes();decoded=Set();buf=C.create_string_buffer(data)
 assert lib.r5_decode_look_file(buf,len(data),C.byref(decoded))==0
 encoded=C.create_string_buffer(29552);n=lib.r5_encode_look_file(C.byref(decoded),encoded,len(encoded));assert encoded.raw[:n]==data
 interop_hash=hashlib.sha256(data).hexdigest()
else:interop_hash=None
report={'passed':True,'camera_io':False,'look_bytes':C.sizeof(Look),'set_bytes':C.sizeof(Set),'record_bytes':2452,'full_file_bytes':size,'malformed_rejections_preserve_output':rows,'canonical_cp_records':12,'canonical_crc':hex(crc),'selection_ack_positive':1,'selection_ack_rejects':9,'python_c_interop_sha256':interop_hash,'compiler':cmd,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SRC.glob('*')if p.suffix in('.c','.h')}}
(HERE/'codec_test.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k]for k in('passed','look_bytes','record_bytes','full_file_bytes','canonical_cp_records')}))
