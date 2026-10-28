"""Actual v3 codec and persistence C, bounded synthetic filesystem callbacks."""
from pathlib import Path
import ctypes as C,json,subprocess
from test_import import Set,config,py
H=Path(__file__).resolve().parent
OPEN=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_char_p,C.POINTER(C.c_size_t))
READ=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t))
CLOSE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_size_t)
RENAME=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_char_p,C.c_char_p)
class Ops(C.Structure):_fields_=[('ctx',C.c_void_p),('open',OPEN),('read',READ),('close',CLOSE),('directory',OPEN),('rename',RENAME),('sync',CLOSE)]
subprocess.run(['clang','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror','-I',str(H),str(H/'r5_stage410_codec.c'),str(H/'sd_native_persist.c'),'-o',str(H/'objects/host_persist.dylib')],check=True)
lib=C.CDLL(str(H/'objects/host_persist.dylib'));lib.r5_decode_look_file.argtypes=[C.c_void_p,C.c_size_t,C.POINTER(Set)]
lib.r5_load_persisted_look.argtypes=[C.POINTER(Ops),C.POINTER(Set),C.c_void_p,C.c_size_t]
lib.r5_publish_staged_look.argtypes=[C.POINTER(Ops),C.POINTER(Set),C.c_void_p,C.c_size_t]
payload=py.pack(config(4095));expected=Set();assert lib.r5_decode_look_file(payload,len(payload),C.byref(expected))==0
rows=[]
for fault in ('valid','read','rename','sync','corrupt'):
 state={'pos':0,'renamed':False};files={'active':payload,'pending':payload}
 if fault=='corrupt':files['pending']=payload[:-1]+bytes([payload[-1]^1])
 @OPEN
 def op(_,name,out):
  name=name.decode();state['key']='pending' if name.endswith('.NEW') else 'active';state['pos']=0;out[0]=1;return 0
 @READ
 def read(_,fd,dst,n,out):
  if fault=='read':return -1
  src=files[state['key']];part=src[state['pos']:state['pos']+min(n,127)];state['pos']+=len(part);C.memmove(dst,part,len(part));out[0]=len(part);return 0
 @CLOSE
 def close(_,fd):return 0
 @OPEN
 def directory(_,name,out):out[0]=2;return 0
 @RENAME
 def rename(_,a,b):
  if fault=='rename':return -1
  files['active']=files['pending'];state['renamed']=True;return 0
 @CLOSE
 def sync(_,fd):return -1 if fault=='sync' else 0
 ops=Ops(None,op,read,close,directory,rename,sync);scratch=C.create_string_buffer(28929)
 rc=lib.r5_publish_staged_look(C.byref(ops),C.byref(expected),scratch,len(scratch))
 if fault=='valid':
  assert rc==0 and state['renamed'];got=Set()
  assert lib.r5_load_persisted_look(C.byref(ops),C.byref(got),scratch,len(scratch))==0 and bytes(got)==bytes(expected)
 else:
  assert rc!=0
  if fault in ('read','corrupt'):assert not state['renamed']
 rows.append(dict(fault=fault,result=rc,renamed=state['renamed']))
(H/'grid_persist_tests.json').write_text(json.dumps(dict(passed=True,rows=rows,actual_C=True,camera_filesystem_verified=False),indent=2)+'\n');print('PASS v3 persistence/reload and four failure cases')
