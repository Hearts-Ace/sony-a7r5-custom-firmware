#!/usr/bin/env python3
"""Flash the exact offline-verified R5 verifyKey correction; complete raw/logical readback."""
if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import argparse, datetime, hashlib, json, re, struct, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/audit-python'))
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from build_r5_partition1 import require
RUN=ROOT/'analysis/r5_verifykey_skip_flash_20261014'
BASE=ROOT/'build_r5_partition1_20261014/nflasha1.R5_4.00.custom-key.logical.img'
CANDIDATE=ROOT/'build_r5_partition1_verifykey_skip_20261014/nflasha1.R5_4.00.custom-key.verifykey-skip.logical.img'
BASE_SHA='7d17697fb83a26bbcd53f49f7c791fea7cdd9e372ad6f4510d1f079e643a0b05'
NEW_SHA='0ec7813c78f121f5abced7fc24350e34ac4cffa4ec8be4d1ecccee22f3d4922d'
SIZE=25100288
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(path,obj):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n');tmp.replace(path)
def sparse(before,after):
 require(len(before)==len(after)==SIZE,'Wrong sparse source sizes')
 units=SIZE//512;changed=[before[i*512:(i+1)*512]!=after[i*512:(i+1)*512] for i in range(units)]
 chunks=[];count=0;pos=0
 while pos<units:
  start=pos;flag=changed[pos]
  while pos<units and changed[pos]==flag:pos+=1
  n=pos-start
  chunks.append(struct.pack('<2H2I',0xcac1 if flag else 0xcac3,0,n,12+(n*512 if flag else 0))+(after[start*512:pos*512] if flag else b''))
  if flag:count+=n
 out=struct.pack('<I4H4I',0xed26ff3a,1,0,28,12,512,units,len(chunks),0)+b''.join(chunks)
 # Independently apply RAW/DONT_CARE chunks to the complete prior image.
 rebuilt=bytearray(before);off=28;block=0
 for _ in chunks:
  typ,res,n,total=struct.unpack_from('<2H2I',out,off)
  require(res==0 and typ in (0xcac1,0xcac3),'Bad chunk')
  if typ==0xcac1:
   require(total==12+n*512,'Bad RAW size');rebuilt[block*512:(block+n)*512]=out[off+12:off+total]
  else:require(total==12,'Bad DONT_CARE size')
  block+=n;off+=total
 require(off==len(out) and block==units and rebuilt==after,'Sparse overlay mismatch')
 return out,count
def check_inputs():
 require(CANDIDATE.stat().st_size==BASE.stat().st_size==SIZE and sha(CANDIDATE)==NEW_SHA and sha(BASE)==BASE_SHA,'Image identity differs')
 b=ROOT/'backups/R5_4.00_20261014_full'
 require(json.loads((b/'verification.json').read_text())['state']=='verified','Backup not verified')
 require(sha(b/'nflasha1.logical.A.img')=='d6cb0eb25e78dbfa09d29225485cc204b773d533d301af1ec54ea7bd2d1e1181','Original backup differs')
 v=json.loads((CANDIDATE.parent/'verification.json').read_text())
 require(v['output_sha256']==NEW_SHA and v['verification']['four_RSA_verify_functions_unchanged'],'Candidate validation missing')
 return b
def prepare():
 check_inputs();require(not RUN.exists(),'Run directory exists');RUN.mkdir()
 patch,count=sparse(BASE.read_bytes(),CANDIDATE.read_bytes());restore,back_count=sparse(CANDIDATE.read_bytes(),BASE.read_bytes())
 require(count==back_count==233 and len(patch)<524288,'Unexpected changed sector count/download size')
 (RUN/'partition1.verifykey-skip.sparse.img').write_bytes(patch)
 (RUN/'partition1.previous-keyonly.restore.sparse.img').write_bytes(restore)
 c=(ROOT/'analysis/r5_partition1_flash_20261014/partition1_usb.c').read_text()
 old='if(strcmp(hex,"73b5132671588e04fa27a9bb86fa58a296a805f43020506123d717bc7dc7c388") && strcmp(hex,"3eeeb2a3794b5e43bcf301c61efcd97f9edd6abe57d33fa5a56a81f8e9ab1abf"))'
 require(c.count(old)==1,'USB host hash guard not found')
 c=c.replace(old,'if(strcmp(hex,"'+hashlib.sha256(patch).hexdigest()+'"))')
 (RUN/'partition1_usb.c').write_text(c)
 subprocess.run(['/usr/bin/clang','-O2',str(RUN/'partition1_usb.c'),'-o',str(RUN/'partition1_usb'),'-framework','IOKit','-framework','CoreFoundation'],check=True)
 boot=(ROOT/'tools/r5_partition1_boot.py').read_text()
 require(boot.count("ap.parse_args()")==1 and boot.count("'/dev/cu.usbmodem101'")==1,'Unexpected RAM-boot source')
 boot=boot.replace("args=ap.parse_args()","ap.add_argument('--port',required=True);args=ap.parse_args()")
 boot=boot.replace("'/dev/cu.usbmodem101'","args.port")
 boot=boot.replace("root=Path(__file__).resolve().parents[1]","root=Path("+repr(str(ROOT))+")")
 (RUN/'ram_boot_helper.py').write_text(boot)
 save(RUN/'preparation.json',{'state':'OFFLINE_PREPARED','changed_sectors':count,'sparse_bytes':len(patch),
  'sparse_sha256':sha(RUN/'partition1.verifykey-skip.sparse.img'),'restore_sparse_sha256':sha(RUN/'partition1.previous-keyonly.restore.sparse.img'),
  'usb_host_sha256':sha(RUN/'partition1_usb'),'ram_boot_helper_sha256':sha(RUN/'ram_boot_helper.py'),
  'script_sha256':sha(Path(__file__)),'candidate_sha256':NEW_SHA,'expected_live_before_sha256':BASE_SHA,
  'forward_and_reverse_sparse_overlays_verified':True,'camera_io_performed':False})
 print((RUN/'preparation.json').read_text(),flush=True)
def raw_verify(raw,logical):
 code=(ROOT/'analysis/sony_write_path_20261008/reference/DavidBuchanan314-ILCE-7M4-RE-2328d18/payloads/fastboot/src/spacc.c').read_text()
 arr=re.search(r'part_key\[64\]\s*=\s*\{(.*?)\}',code,re.S).group(1)
 key=bytes(int(v,16) for v in re.findall(r'0x([0-9a-fA-F]{2})',arr));require(len(key)==64,'Wrong XTS parameters')
 require(len(raw)==len(logical)==SIZE,'Raw/logical size differs')
 algo=algorithms.AES(key)
 for i in range(SIZE//512):
  dec=Cipher(algo,modes.XTS((128+i).to_bytes(16,'little'))).decryptor()
  require(dec.update(raw[i*512:(i+1)*512])+dec.finalize()==logical[i*512:(i+1)*512],'Independent AES-XTS mismatch at sector '+str(i))
def flash(port):
 backup=check_inputs();prep=json.loads((RUN/'preparation.json').read_text())
 for path,field in [('partition1.verifykey-skip.sparse.img','sparse_sha256'),('partition1_usb','usb_host_sha256'),('ram_boot_helper.py','ram_boot_helper_sha256')]:
  require(sha(RUN/path)==prep[field],'Prepared file differs: '+path)
 require(sha(Path(__file__))==prep['script_sha256'],'Flash script changed after preparation')
 require(not (RUN/'report.json').exists(),'Flash attempt already recorded; inspect before retrying')
 state={'state':'preparing','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'target':'nflasha1','candidate_sha256':NEW_SHA,'persistent_write_command_sent':False,'normal_reboot_acknowledged':False,'port':port}
 def persist():save(RUN/'report.json',state)
 def cmd(label,args):
  with (RUN/(label+'.log')).open('x') as log:
   proc=subprocess.Popen([str(RUN/'partition1_usb'),*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
   for line in proc.stdout:log.write(line);log.flush();print(line.rstrip(),flush=True)
   rc=proc.wait()
  state[label+'_returncode']=rc;persist();require(rc==0,label+' failed')
 def reboot(label):
  cmd(label,['reboot']);require('COMMAND reboot\nREPLY OKAY' in (RUN/(label+'.log')).read_text(),'No reboot acknowledgement')
  state['normal_reboot_acknowledged']=True;persist()
 try:
  persist()
  print('RAM BOOT START; no persistent write yet',flush=True)
  subprocess.run([sys.executable,'-B',str(RUN/'ram_boot_helper.py'),'--output',str(RUN/'ram_boot'),'--port',port],check=True,timeout=60)
  br=json.loads((RUN/'ram_boot/report.json').read_text())
  require(br['ready_line_observed'] and br['usb_queries_returncode']==0 and br['payload_sha256']=='330ac322bd0e40a7bb4974f69a2667e7d59a25e59c1322339690f30a3ceadbdc','RAM boot validation failed')
  require(re.search(r'INFOnflasha1\s+00000080 0000bf80 fat',(RUN/'ram_boot/usb_queries.txt').read_text()),'Live partition geometry differs')
  cmd('preflight',['getvar:max-download-size','oem partition dump nflasha 0 0x80','upload:'+str(RUN/'pre.sdm2.raw.bin'),'oem dumpbrom','upload:'+str(RUN/'pre.ap_bootrom.bin'),
    'oem partition dump nflasha1','upload:'+str(RUN/'pre.partition1.logical.img'),'oem partition dump nflasha 0x80 0xbf80','upload:'+str(RUN/'pre.partition1.raw.img')])
  require((RUN/'pre.sdm2.raw.bin').read_bytes()==(backup/'sdm2_partition_table.raw.bin').read_bytes(),'Live SDM2 differs')
  require((RUN/'pre.ap_bootrom.bin').read_bytes()==(backup/'ap_bootrom.raw.A.bin').read_bytes(),'Live ROM identity differs')
  pre=(RUN/'pre.partition1.logical.img').read_bytes();raw_pre=(RUN/'pre.partition1.raw.img').read_bytes()
  require(pre==BASE.read_bytes(),'Current partition1 is not the expected previous key-only image; no write')
  require(raw_pre==(ROOT/'analysis/r5_partition1_flash_20261014/attempt_B/post.partition1.raw.img').read_bytes(),'Current raw partition differs from prior verified readback')
  raw_verify(raw_pre,pre)
  state.update(state='preflight_verified',full_logical_raw_prior_image_match=True,independent_preflight_XTS_verified=True);persist()
  print('PREFLIGHT PASSED: writing exactly 233 changed sectors in nflasha1',flush=True)
  state.update(state='write_in_progress',persistent_write_command_sent=True);persist()
  cmd('flash',['download:'+str(RUN/'partition1.verifykey-skip.sparse.img'),'flash:nflasha1'])
  require('wrote 233 sectors to nflasha1' in (RUN/'flash.log').read_text(),'Unexpected flash reply')
  state.update(state='readback_in_progress',write_acknowledged=True);persist()
  cmd('readback',['oem partition dump nflasha1','upload:'+str(RUN/'post.partition1.logical.img'),'oem partition dump nflasha 0x80 0xbf80','upload:'+str(RUN/'post.partition1.raw.img'),
    'oem partition dump nflasha 0 0x80','upload:'+str(RUN/'post.sdm2.raw.bin')])
  post=(RUN/'post.partition1.logical.img').read_bytes();raw_post=(RUN/'post.partition1.raw.img').read_bytes()
  require(post==CANDIDATE.read_bytes() and sha(RUN/'post.partition1.logical.img')==NEW_SHA,'Complete logical readback mismatch')
  require((RUN/'post.sdm2.raw.bin').read_bytes()==(RUN/'pre.sdm2.raw.bin').read_bytes(),'Partition table changed')
  changes=[i for i in range(SIZE//512) if pre[i*512:(i+1)*512]!=post[i*512:(i+1)*512]]
  require(len(raw_post)==SIZE and changes==[i for i in range(SIZE//512) if raw_pre[i*512:(i+1)*512]!=raw_post[i*512:(i+1)*512]] and len(changes)==233,'Raw changed sector scope differs')
  raw_verify(raw_post,post)
  save(RUN/'independent-readback-verification.json',{'all_49024_raw_sectors_decrypt_to_complete_logical':True,'logical_sha256':sha(RUN/'post.partition1.logical.img'),'raw_sha256':sha(RUN/'post.partition1.raw.img'),'changed_sectors':233,'absolute_first_sector':128})
  state.update(state='readback_verified',complete_logical_readback_matches_candidate=True,independent_raw_XTS_all_sectors_verified=True,raw_changed_only_expected_233_sectors=True,partition_table_unchanged=True);persist()
  reboot('reboot')
  state.update(state='flashed_verified_reboot_acknowledged',finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  state['files']=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(RUN.iterdir()) if p.suffix in ('.img','.bin')]
  persist();print(json.dumps(state,indent=2,ensure_ascii=False),flush=True)
 except Exception as exc:
  state.update(error=repr(exc),state='write_needs_assessment' if state['persistent_write_command_sent'] else 'failed_before_write');persist()
  if not state['persistent_write_command_sent']:
   try:reboot('cleanup_reboot')
   except Exception as cleanup:state['cleanup_error']=repr(cleanup);persist()
  raise
if __name__=='__main__':
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--prepare-only',action='store_true');g.add_argument('--flash',action='store_true');ap.add_argument('--port')
 a=ap.parse_args()
 if a.prepare_only:prepare()
 else:require(a.port is not None,'Explicit port required');flash(a.port)
