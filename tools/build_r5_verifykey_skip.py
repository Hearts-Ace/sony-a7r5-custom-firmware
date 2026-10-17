#!/usr/bin/env python3
"""Offline R5 partition-1 correction: retain custom key and skip verifyKey only."""
if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import argparse, hashlib, io, json, os, stat, struct, subprocess, sys, zlib
from pathlib import Path
from build_r5_partition1 import FatImage, SquashImage, require, sha, md5, write_exclusive, changed_ranges
from elf_study import Image
from sign_r5_firmware import inspect, hashes_and_signature, digest_file
from Cryptodome.PublicKey import RSA
from Cryptodome.Signature import pkcs1_15
from fwtool.archive import fat as vendor_fat
from fwtool.archive import squashfs as vendor_sq
ROOT = Path(__file__).resolve().parents[1]
PATCH = bytes.fromhex('00008052c0035fd6')  # mov w0,#0; ret
BASE_SHA = '7d17697fb83a26bbcd53f49f7c791fea7cdd9e372ad6f4510d1f079e643a0b05'
KEY_SHA = '4cb3cf8cc7a847a5b6108863c2defa327ceb06280c1dda468cd57c3dd3cae859'
# ELF VA, VerifySignature ELF VA, original file SHA256, optional zlib Z_BLOCK split.
TARGETS = {
 'libupdaterapi.so': (0x13324,0x1356c,'1b334b9fb100601b1f8bc764cd9244bb32c2906101f4b2a8c0bd2e8d684df351',71767),
 'libsdfileinputupdaterapi.so': (0xa9a8,0xabf0,'257164d1cdf88757b8c0e2ba08ac47b06c46007410af308b7a8571b442b00cd2',None),
 'libseninputupdaterapi.so': (0x5244,0x548c,'3240c3c70aaa645de3af74101cd4fb85263ec478cff830993a5cd4ba0a6bd704',1349),
 'libuudfileinputupdaterapi.so': (0x95ac,0x97f4,'f8a622fd2b038080cf682b22febe60e379b916f72d8890687b1a6b2109c5182e',321),
}
NAME = 'nflasha1.R5_4.00.custom-key.verifykey-skip.logical.img'

def build(output, verify_only=False):
 raw = (ROOT/'build_r5_partition1_20261014/nflasha1.R5_4.00.custom-key.logical.img').read_bytes()
 require(sha(raw)==BASE_SHA and len(raw)==25100288,'Wrong existing custom-key partition')
 fat=FatImage(raw); initrd=fat.read('/boot/initrd.img'); sq=SquashImage(initrd)
 public=sq.read('/etc/VerificationKey.pem')
 require(sha(public)==KEY_SHA,'Wrong custom public key')
 patched=bytearray(initrd); records=[]; expected={}
 for name,(va,rsa_va,file_sha,cut) in TARGETS.items():
  path='/usr/lib/'+name; before=sq.read(path)
  require(sha(before)==file_sha,'Unexpected library identity: '+name)
  im=Image(ROOT/'analysis/r5_live_system_20261014/boot_probe_B/update_initrd'/path.lstrip('/'))
  sy=im.elf.get_section_by_name('.dynsym')
  symbols={s.name:s for s in sy.iter_symbols()}
  fn=symbols['_ZN7Updater21SignatureVerification9verifyKeyEPKc']
  require(fn['st_value']==va and fn['st_size']==584,'Wrong verifyKey symbol')
  rsa=symbols['_ZN7Updater21SignatureVerification15VerifySignatureENS_13verify_info_tEPKc']
  require(rsa['st_value']==rsa_va and rsa['st_size']==372,'Wrong VerifySignature symbol')
  off=im.offset(va); require(before[off:off+8]==bytes.fromhex('fd7bb2a9e00301aa'),'Wrong function entry')
  decoded=list(im.md.disasm(PATCH,va))
  require([(i.mnemonic,i.op_str) for i in decoded]==[('mov','w0, #0'),('ret','')],'Patch decoding mismatch')
  after=before[:off]+PATCH+before[off+8:]; expected[path]=after
  require(after[:off]==before[:off] and after[off+8:]==before[off+8:],'Patch scope exceeded')
  rsa_off=im.offset(rsa_va)
  require(after[rsa_off:rsa_off+372]==before[rsa_off:rsa_off+372],'RSA verification changed')
  node=sq.nodes[path]; idx=node['fragment_index']; require(not node['block_sizes'] and idx!=0xffffffff,'Unexpected storage')
  frag=sq.fragments[idx]; start=frag['start']; size=frag['size']&0xffffff
  plain=sq.fragment_data(idx); where=node['fragment_offset']+off
  updated=plain[:where]+PATCH+plain[where+8:]
  c=zlib.compressobj(9,zlib.DEFLATED,15,8,zlib.Z_DEFAULT_STRATEGY)
  packed=c.compress(updated)+c.flush() if cut is None else c.compress(updated[:cut])+c.flush(zlib.Z_BLOCK)+c.compress(updated[cut:])+c.flush()
  require(len(packed)==size,'Compressed fragment length changed')
  dc=zlib.decompressobj(); unpacked=dc.decompress(packed)+dc.flush()
  require(dc.eof and not dc.unused_data and not dc.unconsumed_tail and unpacked==updated,'Incomplete/padded zlib stream')
  require(initrd[start:start+size]==zlib.compress(plain,9),'Unexpected original compression')
  patched[start:start+size]=packed
  records.append({'path':path,'original_sha256':sha(before),'patched_sha256':sha(after),
    'verifyKey_ELF_VA':hex(va),'verifyKey_ELF_file_offset':hex(off),'old_entry_hex':before[off:off+8].hex(),
    'new_entry_hex':PATCH.hex(),'decoded_instructions':['mov w0, #0','ret'],
    'VerifySignature_ELF_VA':hex(rsa_va),'VerifySignature_372_bytes_unchanged':True,
    'fragment_index':idx,'compressed_start':start,'compressed_size':size,'zlib_block_split':cut,
    'uncompressed_fragment_changed_range':[where,where+8]})
 patched=bytes(patched); ns=SquashImage(patched)
 require(ns.nodes==sq.nodes and ns.fragments==sq.fragments,'Filesystem metadata changed')
 require(patched[sq.inode_table:]==initrd[sq.inode_table:] and patched[:96]==initrd[:96],'Metadata/footer changed')
 changed=[]
 for p,n in sq.nodes.items():
  if n['inode_type'] in (2,9):
   a,b=sq.read(p),ns.read(p)
   require(b==expected.get(p,a),'Unexpected file contents: '+p)
   if a!=b:changed.append(p)
 require(set(changed)==set(expected),'Wrong changed files')
 require(ns.read('/etc/VerificationKey.pem')==public,'Public key changed')
 vendor_files={f.path:f.contents.read() for f in vendor_sq.readSquashfs(io.BytesIO(patched)) if stat.S_ISREG(f.mode)}
 custom_files={p:ns.read(p) for p,n in ns.nodes.items() if n['inode_type'] in (2,9)}
 require(vendor_files==custom_files,'Independent SquashFS parser disagrees')
 checksums=fat.read('/p1chksum')
 require(checksums==(md5(fat.read('/boot/vmlinux.bin'))+'  ./boot/vmlinux.bin\n'+md5(initrd)+'  ./boot/initrd.img\n').encode(),'Old p1chksum invalid')
 new_checksums=checksums.replace(md5(initrd).encode(),md5(patched).encode(),1)
 out=bytearray(raw); allowed=fat.patch(out,'/boot/initrd.img',patched)+fat.patch(out,'/p1chksum',new_checksums);out=bytes(out)
 nf=FatImage(out); require(nf.entries==fat.entries and out[:fat.data_start]==raw[:fat.data_start],'FAT metadata changed')
 for p,e in fat.entries.items():
  if not e['is_directory']:require(nf.read(p)==({'/boot/initrd.img':patched,'/p1chksum':new_checksums}.get(p,fat.read(p))),'Unexpected FAT file')
 vfat={f.path.casefold():f.contents.read() for f in vendor_fat.readFat(io.BytesIO(out)) if stat.S_ISREG(f.mode)}
 require(vfat=={p:nf.read(p) for p,e in nf.entries.items() if not e['is_directory']},'Independent FAT parser disagrees')
 original=(ROOT/'backups/R5_4.00_20261014_full/nflasha1.logical.A.img').read_bytes()
 require(sha(original)=='d6cb0eb25e78dbfa09d29225485cc204b773d533d301af1ec54ea7bd2d1e1181','Wrong original backup')
 orig_sq=SquashImage(FatImage(original).read('/boot/initrd.img'));orig_changed=[]
 for p,n in orig_sq.nodes.items():
  if n['inode_type'] in (2,9) and orig_sq.read(p)!=ns.read(p):orig_changed.append(p)
 require(set(orig_changed)==set(expected)|{'/etc/VerificationKey.pem'},'Original comparison exceeded five files')
 private=ROOT/'build_r5_partition1_20261014/keys/r5-update-signing-private.pem'
 require(RSA.import_key(private.read_bytes()).public_key().export_key()==public.strip(),'Existing private key does not match')
 dat=ROOT/'build_r5_4.01_customkey_firmware_20261014/BODYDATA_R5_CN2_FL2_FL3_SLOTFIX_4.01_CUSTOMKEY_RESEARCH.DAT'
 require(digest_file(dat)=='f4dc8cd5793c84d29845451171cda354c332dfffd3f046d5249ee353791edc06','DAT identity differs')
 layout=inspect(dat); hashes=hashes_and_signature(dat,layout)
 # API returns SHA256 objects for signed/body/tampered and the signature.
 signed,body,tampered,sig=hashes
 pkcs1_15.new(RSA.import_key(public)).verify(signed,sig)
 try:pkcs1_15.new(RSA.import_key(public)).verify(tampered,sig)
 except (ValueError,TypeError):pass
 else:raise ValueError('Tampered signature accepted')
 report={'state':'OFFLINE_VERIFIED_NOT_FLASHED','partition':'nflasha1','model':'ILCE-7RM5','firmware_base':'4.00',
  'source_sha256':BASE_SHA,'output':str(output/NAME),'output_bytes':len(out),'output_sha256':sha(out),
  'original_restore_image':str(ROOT/'backups/R5_4.00_20261014_full/nflasha1.logical.A.img'),
  'custom_public_key_sha256':KEY_SHA,'custom_public_key_sha1':hashlib.sha1(public).hexdigest(),
  'patches':records,'changed_files_vs_existing_image':sorted(changed),'changed_files_vs_factory_image':sorted(orig_changed),
  'initrd_md5_before':md5(initrd),'initrd_md5_after':md5(patched),'inode_count':len(ns.nodes),
  'changed_bytes_vs_existing_image':sum(a!=b for a,b in zip(raw,out)),
  'changed_sectors_vs_existing_image':sum(raw[i:i+512]!=out[i:i+512] for i in range(0,len(out),512)),
  'verification':{'two_independent_filesystem_parsers_agree':True,'all_other_file_contents_unchanged':True,
   'all_inode_FAT_and_fragment_metadata_unchanged':True,'single_complete_zlib_streams_same_length_no_padding':True,
   'four_verifyKey_entries_return_zero':True,'four_RSA_verify_functions_unchanged':True,
   'p1chksum_valid':True,'existing_private_key_matches':True,'existing_4_01_DAT_signature_valid':True,
   'tampered_signature_rejected':True,'camera_io_performed':False,'camera_boot_tested':False,'update_acceptance_tested':False},
  'matching_DAT':str(dat),'matching_DAT_sha256':digest_file(dat),
  'evidence':{'verifyKey':'ev_a000b1130d7645a35e8fe2042675d87dcbf5b002a354b15d237dc17ecec1341d',
   'VerifySignature':'ev_fa3c527ce4d2ee67374d6a2d666a6655677eed70bdcc24b565f26a99e5060ad2'},
  'limitations':['Host verification does not prove camera boot or successful update installation.',
   '5 slow + 6 fast is shared by several failures; no runtime failure log was captured.',
   'Reference SHA1 storage/provider remains unlocated; this patch deliberately skips that check.',
   '4.01 is the update-header version; firmware payload remains modified R5 4.00.',
   'Skipping verifyKey removes original manufacturer key-file protection; RSA signatures remain required.']}
 if verify_only:
  require((output/NAME).read_bytes()==out,'Saved image not reproducible')
  require((output/'initrd.R5_4.00.custom-key.verifykey-skip.img').read_bytes()==patched,'Saved initrd differs')
  print(json.dumps({'byte_identical_rebuild':True,'output_sha256':sha(out)},indent=2));return
 require(not output.exists(),'Output already exists');output.mkdir()
 for name,data in [(NAME,out),('initrd.R5_4.00.custom-key.verifykey-skip.img',patched),
                   ('p1chksum.patched',new_checksums),('r5-update-verification-public.pem',public)]:
  write_exclusive(output/name,data)
 for r in records:
  result=subprocess.run(['/opt/homebrew/bin/unsquashfs','-cat',str(output/'initrd.R5_4.00.custom-key.verifykey-skip.img'),r['path'].lstrip('/')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  require(result.returncode==0 and result.stdout==expected[r['path']],'unsquashfs independent extraction failed')
 report['verification']['system_unsquashfs_all_four_libraries_match']=True
 write_exclusive(output/'verification.json',(json.dumps(report,indent=2,ensure_ascii=False)+'\n').encode())
 text=('R5 公钥信任检查修正版（离线验证，尚未刷入）\n\n'
       '保留已有 RSA 密钥对；四个更新库 verifyKey() 入口仅覆盖 8 字节，返回 0。后续 VerifySignature / RSA 验签代码逐字节不变。\n'
       '相对原厂备份，仅 PEM 和四个 SO 文件内容变化；FAT / SquashFS 元数据保持一致，更新 p1chksum。\n'
       '已独立解析文件系统，并用 unsquashfs 提取四个库核对；现有 4.01 DAT 验签通过、篡改负测失败。无需再次签名。\n'
       '恢复镜像：'+report['original_restore_image']+'\n'
       '私钥仍在原 keys 目录，本次没有复制或更换。\n'
       '当前没有实机启动或卡刷成功证据；摘要提供端尚未定位。5 慢 6 快不能唯一定位公钥错误。\n')
 write_exclusive(output/'README.md',text.encode())
 files=sorted(p for p in output.iterdir() if p.is_file())
 write_exclusive(output/'SHA256SUMS',(''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in files)).encode())
 print(json.dumps({'output':str(output/NAME),'sha256':sha(out),'checks':report['verification']},indent=2,ensure_ascii=False))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--verify-only',action='store_true');args=ap.parse_args()
 build(ROOT/'build_r5_partition1_verifykey_skip_20261014',args.verify_only)
