#!/usr/bin/env python3
"""Host validation of production codec and record-only IO (not camera replay)."""
import ctypes as C
import argparse
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

HERE=Path(__file__).resolve().parents[1]
def fixture():
    """Independent v4 fixture with twelve different legal parameter records."""
    header=bytearray(128)
    header[:8]=b'R5CUST4\0'
    struct.pack_into('<6I',header,8,4,128,29552,12,4095,0)
    header[32:48]=b'ILCE-7RM5'+bytes(7)
    header[48:80]=bytes.fromhex('8ee4d5876b7e127df39f8f820b9d21834c300ff895e02ca522636ed4733efc4b')
    header[80:112]=bytes.fromhex('8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32')
    records=[]
    for slot in range(1,13):
        record=bytearray(2452)
        struct.pack_into('<I',record,0,slot)
        short=('Test'+str(slot)).encode();full=('Independent test filter '+str(slot)).encode()
        record[4:4+len(short)]=short;record[28:28+len(full)]=full
        for group in range(3):
            for index in range(8):
                value=(slot*2-8 if index<4 else 128+index) if not group else group-slot
                struct.pack_into('<h',record,92+group*16+index*2,value)
        for index in range(288):struct.pack_into('<h',record,140+2*index,((index+slot)%17-8)*13)
        for index in range(129):struct.pack_into('<I',record,716+4*index,index*131071//128)
        for index in range(1215):record[1232+index]=((index+slot)%64-32)&255
        records.append(record)
    data=header+b''.join(records)
    struct.pack_into('<I',data,112,zlib.crc32(data))
    return bytes(data)
class Entry(C.Structure):
    _fields_=[('offset',C.c_uint32),('crc',C.c_uint32),('short',C.c_char*24),('full',C.c_char*64)]
class Index(C.Structure):
    _fields_=[('header',C.c_uint8*128),('mask',C.c_uint32),('entry',Entry*12)]
READ=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint8),C.c_size_t,C.POINTER(C.c_size_t))
class Reader(C.Structure):
    _fields_=[('context',C.c_void_p),('read_at',READ)]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,help='Optional external full twelve-record v4 package; default is an independent synthetic fixture')
    args=parser.parse_args()
    records=[]
    with tempfile.TemporaryDirectory() as td:
        libpath=Path(td)/'file.dylib'
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(HERE/'r5_filter_file.c'),'-o',str(libpath)],check=True)
        lib=C.CDLL(str(libpath));lib.r5f_index_bytes.argtypes=[C.c_void_p,C.c_size_t,C.POINTER(Index)]
        lib.r5f_read_one.argtypes=[C.POINTER(Reader),C.POINTER(Index),C.c_uint,C.c_void_p]
        data=args.fixture.read_bytes() if args.fixture else fixture()
        index=Index();assert len(data)==29552 and not lib.r5f_index_bytes(C.c_char_p(data),len(data),C.byref(index));assert index.mask==4095
        assert C.sizeof(Index)==1284
        for slot in range(1,13):
            calls=[]
            @READ
            def read(_,offset,out,n,got):
                chunk=data[offset:offset+n];calls.append((offset,n,len(chunk)));C.memmove(out,chunk,len(chunk));got[0]=len(chunk);return 0
            output=(C.c_uint8*2392)();reader=Reader(None,read)
            assert not lib.r5f_read_one(C.byref(reader),C.byref(index),slot,output)
            off=128+(slot-1)*2452;r=data[off:off+2452]
            expected=r[4:28]+bytes(8)+r[92:140]+r[140:716]+r[716:1232]+b'\1\0\0\0'+r[1232:2447]+b'\0'
            assert bytes(output)==expected and index.entry[slot-1].crc==zlib.crc32(r)
            assert sum(x[2] for x in calls)==2581
            assert calls==[(0,128,128),(len(data)-1,1,1),(len(data),1,0),(off,2452,2452)]
            records.append({'slot':slot,'read_bytes':sum(x[2] for x in calls),'record_offset':off,'compact_crc':zlib.crc32(expected)})
        unchanged=bytes(index)
        for off in [0,8,20,24,48,80,112,128,128+2447,len(data)-1]:
            damaged=bytearray(data);damaged[off]^=1
            assert lib.r5f_index_bytes(C.c_char_p(bytes(damaged)),len(damaged),C.byref(index))==-1
            assert bytes(index)==unchanged
        for length in [0,127,128,29551,29553]:
            malformed=data[:length] if length<=len(data) else data+b'x'
            assert lib.r5f_index_bytes(C.c_char_p(malformed),len(malformed),C.byref(index))==-1
        for defect in ['record_changed','header_changed','truncated','appended','io','short','one_byte']:
            calls=[];bad=bytearray(data)
            if defect=='record_changed':bad[128+800]^=1
            elif defect=='header_changed':bad[112]^=1
            elif defect=='truncated':bad=bad[:-1]
            elif defect=='appended':bad+=b'x'
            @READ
            def faulty(_,offset,out,n,got):
                got[0]=0
                if defect=='io':return -1
                if defect=='short':return 0
                if defect=='one_byte':n=min(1,n)
                chunk=bytes(bad[offset:offset+n]);C.memmove(out,chunk,len(chunk));got[0]=len(chunk);calls.append((offset,len(chunk)));return 0
            output=(C.c_uint8*2392)(*[0x5a]*2392);reader=Reader(None,faulty)
            rc=lib.r5f_read_one(C.byref(reader),C.byref(index),1,output)
            if defect=='one_byte':assert rc==0 and len(calls)==2582
            else:assert rc==-1 and bytes(output)==b'\x5a'*2392
        empty=(C.c_uint8*128)();lib.r5f_empty(empty);empty_index=Index()
        assert not lib.r5f_index_bytes(empty,128,C.byref(empty_index)) and empty_index.mask==0
    print(json.dumps({'index_bytes':1284,'validated_records':records,'invalid_package_atomicity':15,'record_io_failure_cases':6,'one_byte_read':True,'empty_clear_header':True},indent=2))
if __name__=='__main__':main()
