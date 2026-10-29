"""Prepare exact inputs for the one supported firmware builder from original DAT.

Only format decoding and extraction live here. Firmware modifications and DAT
packaging remain exclusively in firmware/r5/build.py.
"""
from pathlib import Path
import io, json, os, shutil, struct, sys, tarfile, zlib
from common import safe, sha, save, progress

def prepare(original,private,folder,firmware,engine):
    sys.path.insert(0,str(firmware/'src/lib'))
    from Cryptodome.Cipher import AES
    from Cryptodome.PublicKey import RSA
    import numpy as np
    from fwtool.sony import constants
    from fwtool.sony.fdat import FdatHeader,FdatFileSystemHeader
    from signature import inspect,hashes_and_signature,verifies
    from image_io import geometry
    lock=json.loads((firmware/'inputs.lock.json').read_text())
    # Offline user-selected inputs may be aliases; validate their resolved regular files.
    original=safe(Path(original).expanduser().resolve(),file=True);private=safe(Path(private).expanduser().resolve(),file=True)
    def check(name,path):
        row=lock[name]
        if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
            raise ValueError('原始输入散列不符：'+name)
    progress('核对原始 R5 4.00 DAT 与外部签名身份')
    check('original_dat',original)
    for name,file in [('public_key','public.pem'),('sony_public_key','sony-public.pem')]:check(name,engine/file)
    key=RSA.import_key(private.read_bytes());public=RSA.import_key((engine/'public.pem').read_bytes())
    if private.stat().st_mode&0o777!=0o600 or not key.has_private() or (key.n,key.e)!=(public.n,public.e):
        raise ValueError('外部私钥须为 0600，并与本项目公钥匹配')
    if folder.exists():raise ValueError('原始输入目录必须不存在')
    if shutil.disk_usage(folder.parent).free<3_000_000_000:raise ValueError('原始输入提取至少需要 3 GB 可用空间')
    folder.mkdir(mode=0o700)
    layout=inspect(original);signed,_,_,signature=hashes_and_signature(original,layout)
    if not verifies(RSA.import_key((engine/'sony-public.pem').read_bytes()),signed,signature):
        raise ValueError('原厂 DAT 签名不符')
    with original.open('rb') as f:
        f.seek(layout['signature_offset']-16);iv=f.read(16)
    ecb=AES.new(constants.key_aes,AES.MODE_ECB);cbc=AES.new(constants.key_cxd90057_k8,AES.MODE_CBC,iv)
    fdat=folder/'firmware.fdat';progress('解码原始 DAT；原始文件保持只读')
    with original.open('rb') as f,fdat.open('xb') as out:
        f.seek(layout['signed_offset']);left=layout['signed_size']-16;first=True
        while left:
            encoded=f.read(min(4<<20,left))
            if not encoded or len(encoded)%1024:raise ValueError('加密块边界不完整')
            decoded=ecb.decrypt(encoded[:512])+cbc.decrypt(encoded[512:]) if first else cbc.decrypt(encoded)
            first=False;words=np.frombuffer(decoded,dtype='<u2').reshape(-1,512)
            sizes=words[:,1]&0x7fff;ends=words[:,1]>>15
            if not np.all((words[:,1:].sum(axis=1,dtype=np.uint64)&65535)==words[:,0]):raise ValueError('原始块校验失败')
            if np.any(sizes>1020) or np.any(sizes==0):raise ValueError('块长度异常')
            final=len(encoded)==left
            if np.any(sizes[:-1]!=1020) or (not final and sizes[-1]!=1020):raise ValueError('中间块被截短')
            if np.any(ends[:-1]) or bool(ends[-1])!=final:raise ValueError('末块标记不符')
            payload=np.frombuffer(decoded,dtype=np.uint8).reshape(-1,1024)[:,4:].tobytes()
            if final:
                size=int(sizes[-1]);padding=1020-size
                if padding and payload[-padding:]!=b'\xff'*padding:raise ValueError('末块填充异常')
                if padding:payload=payload[:-padding]
            out.write(payload);left-=len(encoded)
        out.flush();os.fsync(out.fileno())
    check('original_fdat',fdat)
    with fdat.open('rb') as f:
        header=f.read(512);head=FdatHeader.unpack(io.BytesIO(header));fs=FdatFileSystemHeader.unpack(head.fileSystemHeaders,0)
        if head.model!=0x11030080 or (head.versionMajor,head.versionMinor)!=(4,0) or zlib.crc32(header[12:])!=head.checksum:
            raise ValueError('原始机型、版本或头部校验失败')
        def extent(name,offset,length):
            target=folder/name;f.seek(offset)
            with target.open('xb') as out:
                left=length
                while left:
                    raw=f.read(min(left,4<<20))
                    if not raw:raise ValueError('原始输入被截短')
                    out.write(raw);left-=len(raw)
            return target
        updater=extent('updater.img',fs.offset,fs.size)
        archive=extent('firmware.tar',head.firmwareOffset,head.firmwareSize)
    check('updater',updater);check('original_tar',archive)
    values=dict(original_dat=str(original),original_fdat=str(fdat),original_tar=str(archive),updater=str(updater),private_key=str(private))
    progress('提取原厂 AP／CP 和固定分区，逐项核对统一构建输入锁')
    with tarfile.open(archive,'r:') as t:
        for name in ('nflasha5','nflasha8','nflasha15'):
            member=t.getmember('0700_part_image/dev/'+name)
            if not member.isfile():raise ValueError('原厂分区不是普通文件')
            target=folder/name
            with t.extractfile(member) as src,target.open('xb') as out:shutil.copyfileobj(src,out,4<<20)
            check('stock_'+name,target);values['stock_'+name]=str(target)
    for key,partition,name in [('stock_ap','nflasha15','appFw.so'),('stock_cp','nflasha8','cpapp-b.bin')]:
        raw,_,_,_=geometry(folder/partition,name);target=folder/name;target.write_bytes(raw)
        check(key,target);values[key]=str(target)
    for key,name in [('public_key','public.pem'),('sony_public_key','sony-public.pem')]:
        target=folder/name;shutil.copyfile(engine/name,target);values[key]=str(target)
    config=folder/'inputs.json';save(config,values)
    save(folder/'verification.json',dict(passed=True,source='original R5 4.00 DAT',inputs=lock,
        original_DAT_modified=False,private_key_copied=False,camera_IO=False))
    return config
