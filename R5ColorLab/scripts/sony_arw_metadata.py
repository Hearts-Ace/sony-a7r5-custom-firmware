#!/usr/bin/env python3
"""Add the tested FL2/FL3 SR2 payloads to compatible Sony ARW copies; Python 3 standard library only.

Default: scan cwd (not recursively), save under FL2_FL3副本, never overwrite.
Sony crypt implementation follows the previously audited experiment / ExifTool Sony.pm.
This is an experimental cross-camera parameter transfer, not a Sony-supported tool.
"""
import argparse
import base64
from datetime import datetime
import errno
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import zlib

PROFILE_B85 = 'c%1E6U8@|q5&bXoJP%SyDoOj8hmb&60t=f5V-~eOvL;^NaP0)b;{TpgrM}a(!GXmNBoL38Tc_1heW_GO<DYNi>D|-w5AT0$l=$||EqKmH$?Iq}IDdpOI~StPJ@*kxEk~rWXf941jvk3>Ep^lt>JeI^+x_<Z^z`9}_x;EDQ@efh>J`<P_#W=@^<8lW_9rg)@))ldW(OQj>`xqAE(y4tm<`Sb7lZ4Ct25Z2wgl4y7cYA1iHpJY!sHD029v?z(n;~M6*YEuJ|L_+ogNvjnM}mG`otmK^PMuEZ_>Tq{bN1<;wj&~=2&nsxSqKeZSEW=>|ZqF-uM{Eya)zIGbz#KV+sZv-%~P}4bBD^gX@JK)gaj9hK*e|cG=ivV>e#Wm&z9|&S3w*)sw-&;An6%m<`Sb7lSV!DmjCVT{3pb*d=3^j9oHz$=D@h*X%sbwZX=&+3adIy9Q%77`s9C@damti^286(HZOwCWFHR=W1~@I2p|5Bxi$77pUR`?frFTuT8wg#9N{nk9Is6EIAJ+&IT7V$JAT8VlT-XOa=#oqru5wHaHtBcFT#yE}gB2oqf1=yReCpO_Y4?cFKIGyXW)aYTTkIJusa(c$XgO1@;C%!UPUxJeu)j#@UQ#GhPg?7iMFZjom9qU}N_R64=;fHrUu@W0#HH?5><t{~)=drAsF+W=?(J>Rwtt#z9)~?5Ey2bn;!t-e2_!taX#mhhSc4!#gXmJopSRl9|MIwZujzmZL&14WBQz2v;x3p%`pfBszmFbL>O(@(?bqF&doAYTJ>`R(Xfi(CgRt+xrjycstF-;>#`ppHJ|gadG(%)4QScU&GK}+3qXbePz4PWV`=gRzu5udVcfgH}BfpAKtZ}=6f{V+jk$@yV0Hpe&>Dv=I?Jremnp6;kms9`s33x(3=l{zx{*E_+EYw{{CD1`R;f4^P4{jnty%MZczUA>FF=f`7`E{2<_*vA;o-KVa-_9T6N9h)?Cf`UL2vQiP=R_ppE`zK|Y-Gam|{Y6WVBftsb3ob1nRJFAM6+0vTMi7Jgq~rE`tf^3i!NzgR#{7u5T$i(*V9yr$_~3{E}dwq1?W@wq4@EYfa%zljg<BC8c9*G2Xur<2gqT@<zD&{=*?cf_?0I1g@h3u*(#2gYJlH$5!7)E!04naE6lqT!GzjEfQKGIy<1)*Sd&d|h1l@xBK1O}vK->u??8@{FVrB-Tvm9AZbp3DA+DH@Vd-z8>%3+rTb>tr0ioNG!pv0iAQ=UG3{&><|*~39bl+K9#@v8*ylgWD5D|E+*(YipIyte99fE>n^W|0|JR$@C23}L8+t>b$6&l7eaSIq<oP(bSbSOU%UFHc}<9+Attd6eK0Fq@+DudTU}&_Px+~T@_CWA-sA`<+3yn7Pj^+zqexZ}Tl88l0Z3(|Au@81Vn$;MTEYo+DUw?fpXBFoQ?tZD<>W51wwy#Z&Qe|Oa3!nkb(=3$!H7-mPuJA`?1$Q4<xu-Bc3tP)e)MhVI^wD80?qCBT)Hl{r4tilE8!vbe5stih|G=T0x0dfiLBUBl^q)^M;0t4@`yNlUec7Z%FenAqi|Jya#8hSFAv=vVG7Y3i>@17^?9|b&kLDQy`|}M;zOUi#3^Txy4nrY)eq`J{lbA$d#z8kA9&{N@6>fTt~w7bMB~wdL1s|CNhHef5E(oA4CElsTau0k*;kUhCVhW^7WA32N~WyuaR#-Jsbk+r_brO-XjNL^^JqG+_n_~4*ZH{&^`rJN)Q>s!Ik6U-To_rT?^H!DoGg)zqmCb(NM!D5hzy;xNRo02a>TOE*Yg&nPRo8z*oPo>h-*{Oa&P)Po6ZZZss75SJFz3}QtY}TZ9Rw1AMQ{+z924H=ep`gcskzt(D|bb)sx!v+t0~6zNva*pE|$HrSFr}tLQ09=b>$s^S#bTCc5fD3sgyKp5yCF<O`dC9$(2%C}{{U%ooBn7#}m^9&~#Yo(wpOYzNr@bkzXDQU1cYBaBntD{=Y3O1b`kusHTW?%#fHuRjXEhfi~M04oeIkT8=J84`r1^l8pkb;+p4cE^+Uwxv&ScJTY9v`*n~A^9|4T>BT!ZrG0uVjmi>R&vmm2seexXTK8q1)M$P3>L{M)S`7E(|!~!3oq}4e~=OnZW3Ki+9nHAbiL8|7FRFe<sw`Pp6-yiz|7TE%6$MQV;$h-4&Lr8Jne*w@kP;rdnfpQLB{}R&yKZNfQEw5_j3nl55ZDg8GPU53;ru|X^J|IK7@Q0(Iq~@cHG>q8IxNB^h4K3=e+@XMpRuIU&xzR71v#5XhO>4L5?iwhU69}XC6mL?lQEbHSHJ|<~hW+STAq5-@vxS=<&rJWH5ZhJp?QQpCzuSF;DkD$l1}gJ>TzYYJL|fE?ZhQw9lC5pd5@E;9XApK#<#9O_6my71s6C^Dbcdp9+z&==vZW=CoJp`Y<<$v^hHRq3dJox<2+n`}hrApW@tihq6ys>Py$NM6$VAxiHe^=1H5IBZHfiv%{W;p0n?%kx!1EoAWj|(@bk~Cg;t?y!O1T^Qq;zIlpXf$H7qUomIK>m{qy6w5Ik$Y3fgpo2vsIx~|ZnejVKXUf=iK03@(EdUJM;o3n|=+MGY*$=&<TF{h4C;Q;k-b9a>A6<%A9aw~RAxi(6kgnK1F!tIQGCgsSmIX0=}$vR$z8)YXXZsF)&l$&R-yyrJMrE>C$M^-6uk=$YWvF{E;{ot~>8!e&lai2F=(&n@nm7_;b%8{NqZ0_3}om=iFC+oUHuAah)tt#hx6!PZqwmDGpE*vR$LA?VUb#wRTVxrB(sJoNv`{r=BIT>uB`rOIQlZVc8Z77$b?Dc&vQ{OMS<m>#|H@9!Dj<mTN-CpfwT4{6p$~)f8*(q+$Zf&U_lQwsw*{VG>r1d58zsT9aeey#gC2;n~kN*S{)$T_'
PROFILE = json.loads(zlib.decompress(base64.b85decode(PROFILE_B85)))
SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4}
OUTPUT_DIR = 'FL2_FL3副本'


class Unsupported(ValueError):
    """Unknown or malformed layout: refuse rather than guess."""


class Skip(ValueError):
    """Not a target / already converted."""


def require(condition, message):
    if not condition:
        raise Unsupported(message)


def crypt(data, key):
    out = bytearray(data)
    pad = [0] * 128
    for i in range(4):
        key = (key * 0x02e90edd + 1) & 0xffffffff
        pad[i] = key
    pad[3] = ((pad[3] << 1) | ((pad[0] ^ pad[2]) >> 31)) & 0xffffffff
    for i in range(4, 127):
        pad[i] = (((pad[i-4] ^ pad[i-2]) << 1) | ((pad[i-3] ^ pad[i-1]) >> 31)) & 0xffffffff
    for j in range(len(data) // 4):
        i = j + 127
        pad[i & 127] = pad[(i+1) & 127] ^ pad[(i+65) & 127]
        struct.pack_into('>I', out, j*4, struct.unpack_from('>I', data, j*4)[0] ^ pad[i & 127])
    return out


def bounded(buf, offset, size):
    require(offset >= 0 and size >= 0 and offset + size <= len(buf), '数据越界或文件不完整')
    return memoryview(buf)[offset:offset+size]


def u32(buf, offset):
    return struct.unpack('<I', bounded(buf, offset, 4))[0]


def ifd(buf, offset, base=0):
    local = offset - base
    count = struct.unpack('<H', bounded(buf, local, 2))[0]
    require(0 < count < 1000, '不支持的 IFD 条目数量')
    bounded(buf, local+2, count*12)
    entries = []
    seen = set()
    for i in range(count):
        pos = local + 2 + 12*i
        tag, typ, n = struct.unpack_from('<HHI', buf, pos)
        require(typ in SIZES and tag not in seen, '不支持的 TIFF 类型或重复标签')
        seen.add(tag)
        size = SIZES[typ]*n
        ptr = pos+8 if size <= 4 else u32(buf, pos+8)-base
        entries.append(dict(tag=tag, type=typ, count=n,
                            data=bytes(bounded(buf, ptr, size)), entry=pos+base))
    return entries


def one(entries, tag):
    for entry in entries:
        if entry['tag'] == tag:
            return entry
    raise Unsupported('缺少必要标签 0x%04x' % tag)


def scalar(entries, tag):
    entry = one(entries, tag)
    require(entry['type'] == 4 and entry['count'] == 1, 'SR2 指针/长度类型不匹配')
    return struct.unpack('<I', entry['data'])[0]


def text(entry):
    require(entry['type'] == 2, '名称字段不是 ASCII')
    return entry['data'].split(b'\0', 1)[0].decode('ascii')


def look_name(entries):
    return text(one(entries, 0x7770))


def schema(entries):
    return [[e['tag'], e['type'], e['count']] for e in entries]


def payloads(entries):
    return [(e['tag'], e['type'], e['count'], e['data']) for e in entries]


def parse(data):
    require(data[:4] == b'II*\0', '不是支持的小端 TIFF/ARW')
    root = ifd(data, u32(data, 4))
    make = text(one(root, 0x10f)).strip()
    model = text(one(root, 0x110)).strip()
    # Do not whitelist a single camera model here.  The payload/layout checks
    # below are the compatibility gate; this lets other Sony ARW files (such
    # as ILCE-7CM2) reach those checks instead of being rejected by name.
    if 'SONY' not in make.upper():
        raise Skip('非 Sony RAW：' + make + ' / ' + model)
    private_entry = one(root, 0xc634)
    require(len(private_entry['data']) == 4, '不支持的 Sony 私有目录指针')
    private = ifd(data, struct.unpack('<I', private_entry['data'])[0])
    offset = scalar(private, 0x7200)
    length = scalar(private, 0x7201)
    key_entry = one(private, 0x7221)
    require(len(key_entry['data']) == 4, '不支持的 SR2 密钥字段')
    key = struct.unpack('<I', key_entry['data'])[0]
    require(0 < length <= 16*1024*1024, 'SR2 数据长度异常')
    dec = crypt(bounded(data, offset, length), key)
    sr = ifd(dec, offset, offset)
    listing = one(sr, 0x74c0)
    require(listing['type'] == 4 and 1 <= listing['count'] <= 32, '不支持的外观列表')
    offsets = list(struct.unpack('<' + 'I'*listing['count'], listing['data']))
    require(len(set(offsets)) == len(offsets), '重复的外观目录指针')
    styles = [ifd(dec, p, offset) for p in offsets]
    return dict(root=root, make=make, model=model, private=private,
                offset=offset, length=length, key=key, dec=dec, sr=sr,
                offsets=offsets, styles=styles)


def align(buf, n=4):
    buf.extend(b'\0' * ((-len(buf)) % n))


def append_ifd(buf, entries, base):
    align(buf)
    start = len(buf)
    buf.extend(struct.pack('<H', len(entries)) + b'\0'*(12*len(entries)))
    for i, e in enumerate(entries):
        pos = start + 2 + 12*i
        struct.pack_into('<HHI', buf, pos, e['tag'], e['type'], e['count'])
        value = e['data']
        require(len(value) == SIZES[e['type']]*e['count'], '参数负载长度异常')
        if len(value) <= 4:
            buf[pos+8:pos+12] = value.ljust(4, b'\0')
        else:
            align(buf, 2)
            struct.pack_into('<I', buf, pos+8, base+len(buf))
            buf.extend(value)
    return base+start


def verified_root_schema(a):
    actual = schema(a['sr'])
    if actual == PROFILE['root_schema']:
        return True
    # Exact ILCE-7M4 layout verified with DSC02779.ARW (2026-10-16).
    # These six optional root fields are absent; all remaining fields and
    # all 114 fields in each original look must still match exactly.
    m4_absent = {0x78a2, 0x78a3, 0x7921, 0x7922, 0x7983, 0x7984}
    return (a['model'] == 'ILCE-7M4' and actual ==
            [e for e in PROFILE['root_schema'] if e[0] not in m4_absent])


def transform(data):
    a = parse(data)
    names = [look_name(s) for s in a['styles']]
    if 'FL2' in names and 'FL3' in names:
        raise Skip('已含 FL2 / FL3')
    require(names == PROFILE['original_names'], '外观列表与已验证的样片不一致')
    # Refuse unknown firmware/metadata layouts instead of blindly rebasing pointers.
    require(verified_root_schema(a), 'SR2 根目录结构未经验证')
    require(all(schema(s) == PROFILE['style_schema'] for s in a['styles']),
            '创意外观参数结构未经验证')
    additions = []
    for label in ('FL2', 'FL3'):
        style = [dict(e) for e in a['styles'][0]]
        for e in style:
            replacement = PROFILE['looks'][label].get(str(e['tag']))
            if replacement:
                typ, count, raw = replacement
                require([e['type'], e['count']] == [typ, count], '移植字段结构不匹配')
                e['data'] = bytes.fromhex(raw)
        additions.append(style)
    image = bytearray(data)
    align(image)
    base = len(image)
    require(base + a['length'] + 65536 < 2**32, '文件过大，超出 32 位 TIFF 偏移范围')
    delta = base - a['offset']
    block = bytearray(a['dec'])
    for entries in [a['sr']] + a['styles']:
        for e in entries:
            if len(e['data']) > 4:
                pos = e['entry'] - a['offset'] + 8
                original = u32(block, pos)
                bounded(a['dec'], original-a['offset'], len(e['data']))
                struct.pack_into('<I', block, pos, original+delta)
    listing = one(a['sr'], 0x74c0)
    list_pos = u32(a['dec'], listing['entry']-a['offset']+8)-a['offset']
    offsets = [p+delta for p in a['offsets']]
    struct.pack_into('<'+'I'*len(offsets), block, list_pos, *offsets)
    for style in additions:
        offsets.append(append_ifd(block, style, base))
    align(block)
    ptr = base+len(block)
    block.extend(struct.pack('<'+'I'*len(offsets), *offsets))
    struct.pack_into('<II', block, listing['entry']-a['offset']+4, len(offsets), ptr)
    align(block)
    image.extend(crypt(block, a['key']))
    changed = [one(a['private'], tag)['entry']+8 for tag in (0x7200, 0x7201)]
    for pos, value in zip(changed, (base, len(block))):
        struct.pack_into('<I', image, pos, value)
    # Verify every original byte, not only the pixel strip locations.
    cursor = 0
    for pos in sorted(changed):
        require(memoryview(data)[cursor:pos] == memoryview(image)[cursor:pos], '原文件字节保护校验失败')
        cursor = pos+4
    require(memoryview(data)[cursor:] == memoryview(image)[cursor:len(data)], '原文件字节保护校验失败')
    actual = parse(image)
    require(len(actual['styles']) == 12, '新增外观数量校验失败')
    for before, after in zip(a['styles']+additions, actual['styles']):
        require(payloads(before) == payloads(after), '外观参数回读校验失败')
    require(payloads([e for e in a['sr'] if e['tag'] != 0x74c0]) ==
            payloads([e for e in actual['sr'] if e['tag'] != 0x74c0]), '原始处理参数校验失败')
    result = dict(make=a['make'], model=a['model'],
                  source_sha256=hashlib.sha256(data).hexdigest(),
                  output_sha256=hashlib.sha256(image).hexdigest(),
                  donor_sha256=PROFILE['donor_sha256'],
                  original_bytes_preserved_except=[{'offset':p, 'length':4} for p in changed],
                  original_10_looks_preserved=True, added_looks=['FL2', 'FL3'],
                  render_verified_by_script=False, cross_camera_color_accuracy_verified=False)
    return image, result


def save_exclusive(path, data, expected_hash):
    """Verify a temporary file, then publish with a no-clobber hard link."""
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(path.parent), prefix='.fl2fl3-', suffix='.tmp', delete=False) as f:
            temp = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        digest = hashlib.sha256()
        with temp.open('rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                digest.update(chunk)
        require(digest.hexdigest() == expected_hash, '写入后 SHA-256 校验失败')
        # Unlike rename(), link() fails if the destination already exists.
        try:
            os.link(str(temp), str(path))
        except OSError as exc:
            unsupported = {errno.EPERM, errno.EXDEV, errno.ENOSYS, errno.EINVAL,
                           errno.ENOTSUP, errno.EOPNOTSUPP}
            if exc.errno not in unsupported:
                raise
            # exFAT has no hard links: exclusive creation still forbids overwrite.
            # This fallback is not atomic; remove our partial file on normal errors
            # or Ctrl-C. A power loss can leave a partial file (documented in README).
            created = False
            try:
                with path.open('xb') as final:
                    created = True
                    digest = hashlib.sha256()
                    with temp.open('rb') as source:
                        for chunk in iter(lambda: source.read(1024*1024), b''):
                            final.write(chunk)
                            digest.update(chunk)
                    final.flush()
                    os.fsync(final.fileno())
                    require(digest.hexdigest() == expected_hash, '副本复制校验失败')
                written_hash = hashlib.sha256()
                with path.open('rb') as final_read:
                    for chunk in iter(lambda: final_read.read(1024*1024), b''):
                        written_hash.update(chunk)
                require(written_hash.hexdigest() == expected_hash, '最终副本回读校验失败')
            except BaseException:
                if created:
                    path.unlink()
                raise
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def run(folder):
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise ValueError('输入文件夹不存在：' + str(folder))
    files = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == '.arw'),
                   key=lambda p: p.name.lower())
    print('扫描文件夹：', folder)
    print('输出子文件夹：', folder / OUTPUT_DIR)
    if not files:
        print('当前文件夹没有 ARW 文件（不扫描子文件夹）。')
        return 0
    outdir = folder / OUTPUT_DIR
    if outdir.is_symlink():
        raise ValueError('为避免误写，输出子文件夹不能是符号链接')
    outdir.mkdir(exist_ok=True)
    records = []
    failed = 0
    for i, source in enumerate(files, 1):
        record = {'source': str(source), 'output': str(outdir / source.name)}
        image = data = None
        try:
            if source.is_symlink():
                raise Skip('符号链接，不处理')
            dest = outdir / source.name
            if os.path.lexists(str(dest)):
                raise Skip('同名副本已存在，不覆盖')
            data = source.read_bytes()
            image, verification = transform(data)
            save_exclusive(dest, image, verification['output_sha256'])
            record.update(status='ok', verification=verification)
            print('[%d/%d] 完成：%s' % (i, len(files), source.name), flush=True)
        except Skip as exc:
            record.update(status='skipped', reason=str(exc))
            print('[%d/%d] 跳过：%s — %s' % (i, len(files), source.name, exc), flush=True)
        except Exception as exc:
            failed += 1
            record.update(status='error', reason=str(exc))
            print('[%d/%d] 失败：%s — %s' % (i, len(files), source.name, exc), flush=True)
        finally:
            image = data = None
        records.append(record)
    # Unique logs avoid overwriting previous run records.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=str(outdir),
                                     prefix='处理记录_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_',
                                     suffix='.json', delete=False) as f:
        json.dump({'created_at': datetime.now().astimezone().isoformat(), 'files': records},
                  f, ensure_ascii=False, indent=2)
        log = f.name
    ok = sum(r['status'] == 'ok' for r in records)
    print('\n完成 %d；跳过 %d；失败 %d。' % (ok, len(records)-ok-failed, failed))
    print('处理记录：', log)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description='RAW创意外观解锁：为 Sony ARW 副本添加 FL2/FL3；不改原片、不覆盖、不递归。')
    parser.add_argument('folder', nargs='?', type=Path, default=Path.cwd(), help='待处理文件夹，默认终端当前文件夹')
    args = parser.parse_args()
    try:
        return run(args.folder)
    except KeyboardInterrupt:
        print('\n已中断。原片未修改；已完成副本保留。', file=sys.stderr)
        return 130
    except Exception as exc:
        print('错误：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
