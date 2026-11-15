#!/usr/bin/env python3
"""Compile ASan/UBSan AP worker and exercise protocol and native job fixtures."""
from pathlib import Path
import argparse,subprocess,json,hashlib,tempfile
HERE=Path(__file__).resolve().parent
AP=HERE.parent
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
with tempfile.TemporaryDirectory(prefix='r5-owner465-ap-') as td:
 target=Path(td)/'runtime'
 cmd=['clang','-std=c11','-O1','-g','-fsanitize=address,undefined','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(AP),'-I',str(AP/'shared'),'-I',str(AP.parent/'common'),str(AP/'r5_filter_runtime.c'),str(AP/'job.c'),str(HERE/'runtime.c'),'-o',str(target)]
 subprocess.run(cmd,check=True,capture_output=True,text=True)
 rows=[]
 for look in (0,1,8,17,18):
  for mode in range(15):
   r=subprocess.run([str(target),str(mode),str(look)],capture_output=True,text=True)
   assert not r.returncode,(mode,look,r.stdout,r.stderr)
   rows.append(dict(mode=mode,look=look,output=r.stdout.strip()))
 result=dict(passed=True,cases=len(rows),rows=rows,compile_command=cmd,sources={str(s.relative_to(AP)):hashlib.sha256(s.read_bytes()).hexdigest()for s in [AP/'r5_filter_runtime.c',AP/'job.c',HERE/'runtime.c']},limits=['Host production C worker and job helper with ASan/UBSan; file, native sequence/timing and CP control/accept callbacks are explicit stateful fixtures.','No hardware task scheduling or native firmware instructions execute here; final ELF replay is separate.'])
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows))))
