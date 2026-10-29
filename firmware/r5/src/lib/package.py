#!/usr/bin/env python3
"""Build the M4-method R5 4.03 or 4.04 FL2/FL3 SD package offline.

Inputs are original R5 images plus separately verified AP/CP/WBI components.
The complete original update body and every factory settings template stay
byte-for-byte original. Personal settings deployment is a separate host tool.
No camera or block-device access is performed.
"""
import argparse
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tarfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
from Cryptodome.Cipher import AES
from Cryptodome.PublicKey import RSA
from Cryptodome.Hash import SHA256
from Cryptodome.Signature import pkcs1_15
import numpy as np
from fwtool.sony import constants
from fwtool.sony.fdat import FdatHeader, FdatFileSystemHeader
from fdat_encrypt import FdatStreamEncrypter
from signature import (require, digest_file, inspect, hashes_and_signature, verifies,
                       openssl_verify, PUBLIC_SHA256, SONY_PUBLIC_SHA256)
from image_io import digest_stream

OUT=None
VERSION='4.34'
TAG='434'
TAR=None
NAME='BODYDATA.DAT'
CHUNK=4<<20
SOURCE_SHA='51e1176a255a9a4b4782dfbcfa6c5f332b71173bdfe9ed2bcf4fca6bcbc6c2e2'
STOCK_UPDATER_SHA='c4b18a82eea52a507fb82b86ad50bab6047070b8908d03c28edcce4a9577d348'
components=None

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def save(name, report):
    (OUT / 'evidence' / name).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')

def load(name):
    return json.loads((OUT / 'evidence' / name).read_text())

class OuterWriter:
    def __init__(self, stream):
        self.stream, self.crc = stream, 0
    def write(self, data):
        require(self.stream.write(data) == len(data), 'Short container write')
        self.crc = zlib.crc32(data, self.crc)
        return len(data)

class SignedWriter:
    def __init__(self, outer):
        self.outer, self.hash = outer, SHA256.new()
    def write(self, data):
        self.hash.update(data)
        return self.outer.write(data)

class PlainReader:
    def __init__(self,prefix):self.prefix=io.BytesIO(prefix);self.archive=TAR.open('rb')
    def read(self,n):
        data=self.prefix.read(n);return data+self.archive.read(n-len(data))
    def close(self):self.archive.close()

def verify_plain(package,layout,prefix,total,iv):
    body_size=layout['signed_size']-16
    ecb=AES.new(constants.key_aes,AES.MODE_ECB)
    cbc=AES.new(constants.key_cxd90057_k8,AES.MODE_CBC,iv)
    expected=PlainReader(prefix);digest=hashlib.sha256();blocks=done=offset=0
    with package.open('rb') as f:
        f.seek(layout['signed_offset'])
        while done<body_size:
            encoded=f.read(min(CHUNK,body_size-done))
            require(encoded and len(encoded)%1024==0,'Invalid encrypted extent')
            decoded=ecb.decrypt(encoded[:512])+cbc.decrypt(encoded[512:]) if done==0 else cbc.decrypt(encoded)
            words=np.frombuffer(decoded,dtype='<u2').reshape(-1,512)
            require(bool(np.all((words[:,1:].sum(axis=1,dtype=np.uint64)&65535)==words[:,0])),'Block checksum mismatch')
            sizes=words[:,1]&0x7fff;ends=words[:,1]>>15;final=done+len(encoded)==body_size
            want=np.zeros(len(words),dtype=np.uint16)
            if final:want[-1]=1
            require(bool(np.array_equal(ends,want)),'Wrong last-block flags')
            last=(total-1)%1020+1 if final else 1020
            require(bool(np.all(sizes[:-1]==1020)) and int(sizes[-1])==last,'Wrong block lengths')
            payload=np.frombuffer(decoded,dtype=np.uint8).reshape(-1,1024)[:,4:].tobytes()
            if final and last<1020:
                unused=1020-last;require(payload[-unused:]==b'\xff'*unused,'Wrong final padding');payload=payload[:-unused]
            require(payload==expected.read(len(payload)),'Decrypted payload differs from complete build inputs')
            digest.update(payload);offset+=len(payload);blocks+=len(words);done+=len(encoded)
    require(offset==total and expected.read(1)==b'','Incomplete verification');expected.close()
    head=FdatHeader.unpack(io.BytesIO(prefix[:512]));fs=FdatFileSystemHeader.unpack(head.fileSystemHeaders,0)
    require((head.versionMajor,head.versionMinor)==(4,int(VERSION.split('.')[1], 16)) and head.model==0x11030080 and head.region==0 and
            head.modeType==b'U' and head.luwFlag==b'N','Wrong '+VERSION+' target header')
    require(head.firmwareOffset==len(prefix) and head.firmwareSize==TAR.stat().st_size and
            fs.offset==512 and fs.size==len(prefix)-512 and zlib.crc32(prefix[12:512])==head.checksum,'Wrong FDAT geometry/CRC')
    return dict(independent_library='PyCryptodome AES; encryption uses cryptography',plaintext_bytes=offset,
                decrypted_blocks=blocks,plaintext_sha256=digest.hexdigest(),every_plaintext_byte_matches=True,
                all_block_checksums_lengths_flags_and_padding_valid=True)

def build_package():
    comp = components()
    ar = load(f'archive_verification_{TAG}.json')
    require(digest_file(TAR) == ar['output_sha256'], 'Archive changed after verification')
    updater = (ROOT/'inputs/updater.img').read_bytes()
    require(sha(updater) == STOCK_UPDATER_SHA, 'Update body must remain exactly original')
    donor=ROOT/'inputs/original.DAT'
    require(digest_file(donor)=='51e1176a255a9a4b4782dfbcfa6c5f332b71173bdfe9ed2bcf4fca6bcbc6c2e2','Wrong original DAT')
    public=ROOT/'inputs/public.pem'
    private=ROOT/'inputs/private.pem'
    require(digest_file(public)==PUBLIC_SHA256,'Wrong signing public key')
    pub,key=RSA.import_key(public.read_bytes()),RSA.import_key(private.read_bytes())
    require(key.has_private() and key.size_in_bits()==2048 and (key.n,key.e)==(pub.n,pub.e) and
            private.stat().st_mode&0o777==0o600,'Signing identity or permission mismatch')
    with (ROOT/'inputs/original.fdat').open('rb') as f:
        old_header=f.read(512)
        head=FdatHeader.unpack(io.BytesIO(old_header));oldfs=FdatFileSystemHeader.unpack(head.fileSystemHeaders,0)
        require(head.model==0x11030080 and head.region==0 and head.firmwareSize==TAR.stat().st_size and
                zlib.crc32(old_header[12:])==head.checksum,'Wrong original plaintext header')
        f.seek(oldfs.offset);require(f.read(oldfs.size)==(ROOT/'inputs/updater.img').read_bytes(),'Updater source mismatch')
    header=bytearray(old_header);header[32:34]=bytes((int(VERSION.split('.')[1], 16),4))
    struct.pack_into('<I',header,48,512+len(updater));struct.pack_into('<I',header,72,len(updater))
    struct.pack_into('<I',header,8,zlib.crc32(header[12:]))
    allowed={8,9,10,11,32}
    require(all(i in allowed for i,(a,b) in enumerate(zip(old_header,header)) if a!=b),'Unexpected header change')
    (OUT/f'FDAT.header.{VERSION}.bin').write_bytes(header)
    prefix=bytes(header)+updater;total=len(prefix)+TAR.stat().st_size;blocks=(total+1019)//1020
    donor_layout=inspect(donor)
    sony_path=ROOT/'inputs/sony_public.pem'
    require(digest_file(sony_path)==SONY_PUBLIC_SHA256,'Wrong original Sony public key')
    sony=RSA.import_key(sony_path.read_bytes())
    dh,_,dt,ds=hashes_and_signature(donor,donor_layout)
    require(verifies(sony,dh,ds) and not verifies(sony,dt,ds),'Original Sony signature check failed')
    with donor.open('rb') as f:f.seek(donor_layout['signature_offset']-16);iv=f.read(16)
    final=OUT/NAME
    package=OUT/'UNVERIFIED_DO_NOT_INSTALL.partial'
    require(not final.exists() and not package.exists(),'Refuse overwriting a DAT or partial build')
    print('Encrypting and signing complete R5 CN2 '+VERSION+'.',flush=True)
    with package.open('xb') as target,donor.open('rb') as df:
        writer=OuterWriter(target);writer.write(df.read(8))
        for chunk in donor_layout['chunks']:
            kind=chunk['kind'].encode()
            if kind==b'FDAT':
                writer.write(struct.pack('>I4s',blocks*1024+272,kind));signed=SignedWriter(writer)
                src=PlainReader(prefix);size=FdatStreamEncrypter(iv,batch_blocks=4096).encrypt_stream(src,signed,total);src.close()
                require(size==blocks*1024,'Wrong encrypted length');signed.write(iv)
                signature=pkcs1_15.new(key).sign(signed.hash)
                require(verifies(pub,signed.hash,signature),'Signature generation self-check failed')
                writer.write(signature)
            elif kind==b'DEND':writer.write(struct.pack('>I4sI',4,kind,writer.crc&0xffffffff))
            else:
                df.seek(chunk['offset']);data=df.read(chunk['size'])
                require(len(data)==chunk['size'],'Short source chunk')
                writer.write(struct.pack('>I4s',len(data),kind));writer.write(data)
        target.flush();os.fsync(target.fileno())
    layout=inspect(package)
    for a,b in zip(donor_layout['chunks'][:3],layout['chunks'][:3]):
        require(a==b,'Outer metadata geometry changed')
        with donor.open('rb') as f,package.open('rb') as g:
            f.seek(a['offset']);g.seek(b['offset']);require(f.read(a['size'])==g.read(b['size']),'Outer metadata bytes changed')
    h,_,tampered,s=hashes_and_signature(package,layout)
    require(h.digest()==signed.hash.digest() and s==signature and verifies(pub,h,s) and
            not verifies(pub,tampered,s),'Saved signature/tamper rejection failed')
    (OUT/'VerificationKey.pem').write_bytes(public.read_bytes())
    (OUT/'FDAT.signature.bin').write_bytes(s);(OUT/'FDAT.signed.sha256.bin').write_bytes(h.digest())
    openssl=openssl_verify(OUT/'VerificationKey.pem',OUT/'FDAT.signed.sha256.bin',OUT/'FDAT.signature.bin')
    print('Signature checked; independently decrypting every byte.',flush=True)
    plain=verify_plain(package,layout,prefix,total,iv)
    package.rename(final)
    package = final
    report = dict(
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        state='OFFLINE_VERIFIED_RESEARCH_PACKAGE_DEVICE_ACCEPTANCE_UNCONFIRMED',
        model='Sony ILCE-7RM5 / A7R V', target_region='CN2',
        version=VERSION, user_version=VERSION, base_firmware='Original R5 4.00',
        output=str(package), output_bytes=package.stat().st_size,
        output_sha256=digest_file(package), source_sha256=SOURCE_SHA,
        public_key_sha256=PUBLIC_SHA256,
        source_repository='https://github.com/Erlla/sony-a7m4-custom-firmware',
        source_commit=comp['upstream_commit'],
        components=comp['components'], archive_sha256=ar['output_sha256'],
        updater_sha256=STOCK_UPDATER_SHA, updater_byte_for_byte_stock=True,
        changed_tar_members=ar['changed_members'], exact_four_member_scope_verified=True,
        factory_defaults_and_backup_sum_unchanged=False,
        old_forced_slot_initialization_and_write_guards_removed=True,
        added_migration_sync_readback_finalizer_and_native_marker_absent=True,
        personal_settings_embedded=False, personal_settings_deployed=False,
        signing_algorithm='RSASSA-PKCS1-v1_5 / SHA-256', openssl_verification=openssl,
        saved_signature_valid=True, tampered_signature_rejected=True, outer_crc_valid=True,
        non_fdat_metadata_unchanged=True, plaintext_verification=plain,
        same_previously_installed_custom_key=True, same_version_bypass_added=False,
        camera_io_performed=False, device_acceptance_tested=False,
        boot_recovery_tested=False, nor_write_or_readback_performed=False,
        limitations=[
            'Uses author-method program changes adapted to R5; it is not an official Sony release.',
            'The author deploys per-camera nfa2/nfa6 separately; this SD package does not perform that deployment.',
            'Offline checks do not prove cold boot, camera settings persistence, FL2/FL3 operation or recovery after the incident.',
            'Current installed version and updater trust have not been read back after the incident; same-version checks are original.',
            'The original conditional CP NOR update chain is preserved; physical NOR contents are not verified by this offline build.',
        ])
    (OUT/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:report[k] for k in ('state','output','output_bytes','output_sha256')},ensure_ascii=False),flush=True)
