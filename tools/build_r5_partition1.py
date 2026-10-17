#!/usr/bin/env python3
"""Build an R5 partition-1 key image offline, preserving all filesystem metadata.

Only the original compressed fragment containing VerificationKey.pem and the
32 ASCII characters for initrd's MD5 in p1chksum are changed. No USB commands.
A same-length zlib stream is required; no trailing padding is added.
"""
import argparse
import hashlib
import io
import json
import os
import stat
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/fwtool.py-a7iv'))
from fwtool.archive import fat as vendor_fat

ORIGINAL_SHA256 = 'd6cb0eb25e78dbfa09d29225485cc204b773d533d301af1ec54ea7bd2d1e1181'
ORIGINAL_SIZE = 25100288
TARGET = '/etc/VerificationKey.pem'
DEFAULT_SOURCE = ROOT / 'analysis/r5_live_system_20261014/boot_probe_B/nflasha1.logical.A.img'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def md5(data):
    return hashlib.md5(data).hexdigest()


class FatImage:
    def __init__(self, data):
        self.data = data
        self.sector = struct.unpack_from('<H', data, 11)[0]
        self.cluster_bytes = self.sector * data[13]
        reserved = struct.unpack_from('<H', data, 14)[0]
        copies = data[16]
        roots = struct.unpack_from('<H', data, 17)[0]
        spf = struct.unpack_from('<H', data, 22)[0]
        require(data[54:62] == b'FAT12   ', 'Expected original FAT12')
        self.fat_start = reserved * self.sector
        self.root_start = self.fat_start + copies * spf * self.sector
        self.root_size = ((roots * 32 + self.sector - 1) // self.sector) * self.sector
        self.data_start = self.root_start + self.root_size
        self.entries = {}
        self.walk([(self.root_start, self.root_size)], '')

    def chain(self, cluster):
        seen = set()
        result = []
        while cluster >= 2 and cluster < 0xff8:
            require(cluster not in seen, 'FAT cluster chain loop')
            seen.add(cluster)
            offset = self.data_start + (cluster - 2) * self.cluster_bytes
            require(offset + self.cluster_bytes <= len(self.data), 'FAT cluster outside image')
            result.append((offset, self.cluster_bytes))
            pos = self.fat_start + cluster * 3 // 2
            pair = struct.unpack_from('<H', self.data, pos)[0]
            cluster = (pair >> 4) if cluster & 1 else (pair & 0xfff)
        require(cluster >= 0xff8 or not result, 'FAT chain ended on bad/free cluster')
        return result

    def walk(self, extents, parent):
        name_parts = {}
        for start, size in extents:
            for off in range(start, start + size, 32):
                e = self.data[off:off + 32]
                if e[0] == 0:
                    return
                if e[0] == 0xe5:
                    name_parts = {}
                    continue
                if e[11] == 0x0f:
                    seq = e[0] & 0x1f
                    if e[0] & 0x40:
                        name_parts = {}
                    name_parts[seq] = e[1:11] + e[14:26] + e[28:32]
                    continue
                if e[11] & 8:
                    name_parts = {}
                    continue
                if name_parts:
                    name = b''.join(name_parts[i] for i in sorted(name_parts)).decode('utf-16le').rstrip('\0\uffff')
                else:
                    name = e[:8].decode('ascii').rstrip()
                    ext = e[8:11].decode('ascii').rstrip()
                    if ext:
                        name += '.' + ext
                name_parts = {}
                if name in ('.', '..'):
                    continue
                path = parent + '/' + name
                cluster = struct.unpack_from('<H', e, 26)[0]
                length = struct.unpack_from('<I', e, 28)[0]
                entry = {'path': path, 'size': length, 'directory_entry_offset': off,
                         'directory_entry_sha256': sha(e), 'extents': self.chain(cluster),
                         'is_directory': bool(e[11] & 16)}
                key = path.casefold()
                require(key not in self.entries, 'Duplicate FAT path')
                self.entries[key] = entry
                if entry['is_directory']:
                    self.walk(entry['extents'], path)

    def read(self, path):
        e = self.entries[path.casefold()]
        require(not e['is_directory'], 'Cannot read directory')
        raw = b''.join(self.data[o:o+n] for o, n in e['extents'])
        require(len(raw) >= e['size'], 'FAT allocation too short')
        return raw[:e['size']]

    def patch(self, output, path, content):
        entry = self.entries[path.casefold()]
        require(len(content) == entry['size'], 'FAT file length must be unchanged')
        pos = 0
        used = []
        for off, length in entry['extents']:
            take = min(length, len(content) - pos)
            if take <= 0:
                break
            output[off:off+take] = content[pos:pos+take]
            used.append((off, take))
            pos += take
        require(pos == len(content), 'Short FAT write')
        return used


class SquashImage:
    def __init__(self, data):
        self.data = data
        fields = struct.unpack_from('<5I6H8Q', data)
        require(fields[0] == 0x73717368 and fields[5] == 1 and fields[9:11] == (4, 0),
                'Expected zlib SquashFS 4.0')
        self.count, self.block_size, self.fragment_count = fields[1], fields[3], fields[4]
        self.root_ref, self.bytes_used = fields[11], fields[12]
        self.id_table, self.inode_table, self.dir_table, self.fragment_table = fields[13], fields[15], fields[16], fields[17]
        self.metadata_cache = {}
        self.fragments = []
        for i in range(self.fragment_count):
            table_off = struct.unpack_from('<Q', data, self.fragment_table + 8 * ((i * 16) // 8192))[0]
            start, size, unused = struct.unpack('<QII', self.meta(table_off, (i * 16) % 8192, 16))
            self.fragments.append({'start': start, 'size': size, 'unused': unused})
        self.nodes = {}
        self.walk(self.root_ref >> 16, self.root_ref & 65535, '/')
        require(len(self.nodes) == self.count, 'SquashFS traversal inode count mismatch')

    def metadata_block(self, offset):
        if offset not in self.metadata_cache:
            header = struct.unpack_from('<H', self.data, offset)[0]
            size = header & 0x7fff
            raw = self.data[offset+2:offset+2+size]
            require(len(raw) == size and size > 0, 'Invalid SquashFS metadata block')
            block = raw if header & 0x8000 else zlib.decompress(raw)
            self.metadata_cache[offset] = (block, offset + size + 2)
        return self.metadata_cache[offset]

    def meta(self, start, offset, size):
        result = bytearray()
        while len(result) < offset + size:
            block, start = self.metadata_block(start)
            result.extend(block)
        return bytes(result[offset:offset+size])

    def walk(self, block, offset, path):
        start = self.inode_table + block
        header = self.meta(start, offset, 16)
        inode_type, permissions, uid, gid, mtime, number = struct.unpack('<4H2I', header)
        node = {'path': path, 'inode_type': inode_type, 'permissions': oct(permissions),
                'uid_index': uid, 'gid_index': gid, 'mtime': mtime, 'inode_number': number,
                'inode_ref': (block << 16) | offset}
        require(path not in self.nodes, 'Duplicate SquashFS path')
        self.nodes[path] = node
        if inode_type in (1, 8):
            if inode_type == 1:
                db, links, length, do, parent = struct.unpack('<IIHHI', self.meta(start, offset+16, 16))
            else:
                links, length, db, parent, indexes, do, xattr = struct.unpack('<IIIIHHI', self.meta(start, offset+16, 24))
            directory = self.meta(self.dir_table + db, do, length - 3)
            pos = 0
            while pos < len(directory):
                count, child_block, base_inode = struct.unpack_from('<3I', directory, pos)
                pos += 12
                for _ in range(count + 1):
                    child_off, delta, dtype, name_size = struct.unpack_from('<HHHH', directory, pos)
                    pos += 8
                    name = directory[pos:pos+name_size+1].decode('ascii')
                    pos += name_size + 1
                    self.walk(child_block, child_off, path.rstrip('/') + '/' + name)
            require(pos == len(directory), 'Malformed directory')
        elif inode_type in (2, 9):
            if inode_type == 2:
                blocks_start, fragment, fragment_offset, length = struct.unpack('<4I', self.meta(start, offset+16, 16))
                extra = 16
            else:
                blocks_start, length, sparse, links, fragment, fragment_offset, xattr = struct.unpack('<QQQ4I', self.meta(start, offset+16, 40))
                extra = 40
            count = length // self.block_size if fragment != 0xffffffff else (length+self.block_size-1)//self.block_size
            sizes = struct.unpack('<' + str(count) + 'I', self.meta(start, offset+16+extra, count*4)) if count else ()
            node.update({'size': length, 'blocks_start': blocks_start, 'fragment_index': fragment,
                         'fragment_offset': fragment_offset, 'block_sizes': list(sizes)})
        elif inode_type in (3, 10):
            links, length = struct.unpack('<2I', self.meta(start, offset+16, 8))
            node['symlink_hex'] = self.meta(start, offset+24, length).hex()
        elif inode_type in (4, 5, 11, 12):
            links, rdev = struct.unpack('<2I', self.meta(start, offset+16, 8))
            node.update({'hard_links': links, 'rdev': rdev})
        elif inode_type in (6, 7, 13, 14):
            node['hard_links'] = struct.unpack('<I', self.meta(start, offset+16, 4))[0]
        else:
            raise ValueError('Unsupported SquashFS inode type ' + str(inode_type))

    def fragment_data(self, index):
        fragment = self.fragments[index]
        size = fragment['size'] & 0xffffff
        start = fragment['start']
        raw = self.data[start:start+size]
        return raw if fragment['size'] & (1 << 24) else zlib.decompress(raw)

    def read(self, path):
        node = self.nodes[path]
        require(node['inode_type'] in (2, 9), 'Expected regular file')
        out = bytearray()
        pos = node['blocks_start']
        for size in node['block_sizes']:
            length = min(node['size'] - len(out), self.block_size)
            if size == 0:
                out.extend(b'\0' * length)
            else:
                stored = size & 0xffffff
                raw = self.data[pos:pos+stored]
                block = raw if size & (1 << 24) else zlib.decompress(raw)
                require(len(block) == length, 'SquashFS data block length mismatch')
                out.extend(block)
                pos += stored
        if node['fragment_index'] != 0xffffffff:
            block = self.fragment_data(node['fragment_index'])
            off = node['fragment_offset']
            out.extend(block[off:off+node['size']-len(out)])
        require(len(out) == node['size'], 'SquashFS file size mismatch')
        return bytes(out)

    def inventory(self):
        records = []
        for path, node in sorted(self.nodes.items()):
            item = dict(node)
            if node['inode_type'] in (2, 9):
                item['content_sha256'] = sha(self.read(path))
            records.append(item)
        return records


def openssl(arguments, input_data=None):
    result = subprocess.run(['/usr/bin/openssl'] + arguments, input=input_data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, 'OpenSSL failed: ' + result.stderr.decode(errors='replace'))
    return result.stdout


def public_key(private):
    return openssl(['pkey', '-pubout'], private)


def generate_matching_key(fragment, key_offset, key_size, stored_size, supplied):
    attempts = 1 if supplied else 256
    for attempt in range(1, attempts + 1):
        private = supplied or openssl(['genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048'])
        public = public_key(private)
        require(len(public) == key_size, 'Public key PEM length differs from original')
        changed = fragment[:key_offset] + public + fragment[key_offset+key_size:]
        packed = zlib.compress(changed, 9)
        if len(packed) == stored_size:
            decoded = zlib.decompressobj()
            plain = decoded.decompress(packed) + decoded.flush()
            require(decoded.eof and not decoded.unused_data and not decoded.unconsumed_tail,
                    'Compressed fragment must be one complete stream without padding')
            require(plain == changed, 'Fragment compression round trip mismatch')
            return private, public, changed, packed, attempt
    raise ValueError('Could not produce exact-length fragment; no image was written. Try again with fresh key.')


def changed_ranges(before, after):
    ranges = []
    start = None
    for i, (a, b) in enumerate(zip(before, after)):
        if a != b and start is None:
            start = i
        elif a == b and start is not None:
            ranges.append([start, i])
            start = None
    if start is not None:
        ranges.append([start, len(before)])
    return ranges


def write_exclusive(path, data, mode=0o644):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    os.chmod(path, mode)


def build(source, output, supplied_key=None, verify_only=False):
    raw = source.read_bytes()
    require(len(raw) == ORIGINAL_SIZE and sha(raw) == ORIGINAL_SHA256,
            'Source is not the verified R5 4.00 partition-1 backup')
    require(output.is_dir() if verify_only else not output.exists(),
            'Verify mode requires existing output; build mode requires a new output directory')
    fat = FatImage(raw)
    initrd = fat.read('/boot/initrd.img')
    checksums = fat.read('/p1chksum')
    sq = SquashImage(initrd)
    node = sq.nodes[TARGET]
    require(node['size'] == 451 and node['fragment_index'] != 0xffffffff and not node['block_sizes'],
            'Target storage differs from inspected R5 layout')
    fragment = sq.fragments[node['fragment_index']]
    require(not fragment['size'] & (1 << 24), 'Expected compressed key fragment')
    frag_start = fragment['start']
    frag_size = fragment['size'] & 0xffffff
    original_fragment = sq.fragment_data(node['fragment_index'])
    original_key = sq.read(TARGET)
    require(sha(original_key) == '8281413b5607446939613e07d020b2c7d8ee2371349099de56bc8288f7be0a43',
            'Unexpected original verification key')
    require(zlib.compress(original_fragment, 9) == initrd[frag_start:frag_start+frag_size],
            'Original zlib stream not reproduced exactly')
    kernel_md5 = md5(fat.read('/boot/vmlinux.bin'))
    original_initrd_md5 = md5(initrd)
    expected_checksums = (kernel_md5 + '  ./boot/vmlinux.bin\n' +
                          original_initrd_md5 + '  ./boot/initrd.img\n').encode()
    require(checksums == expected_checksums, 'Unexpected original p1chksum content')
    supplied = supplied_key.read_bytes() if supplied_key else None
    private, public, patched_fragment, packed, attempts = generate_matching_key(
        original_fragment, node['fragment_offset'], node['size'], frag_size, supplied)
    patched_initrd = initrd[:frag_start] + packed + initrd[frag_start+frag_size:]
    new_initrd_md5 = md5(patched_initrd)
    patched_checksums = checksums.replace(original_initrd_md5.encode(), new_initrd_md5.encode(), 1)
    require(len(patched_checksums) == len(checksums), 'Checksum file size changed')
    image = bytearray(raw)
    initrd_extents = fat.patch(image, '/boot/initrd.img', patched_initrd)
    checksum_extents = fat.patch(image, '/p1chksum', patched_checksums)
    image = bytes(image)
    require(len(image) == len(raw), 'Partition size changed')
    new_fat = FatImage(image)
    require(fat.entries == new_fat.entries, 'FAT directory metadata changed')
    require(image[:fat.data_start] == raw[:fat.data_start], 'FAT header/allocation metadata changed')
    changed_files = []
    fat_inventory = []
    for path, entry in sorted(fat.entries.items()):
        if entry['is_directory']:
            continue
        before, after = fat.read(path), new_fat.read(path)
        if before != after:
            changed_files.append(path)
        fat_inventory.append({'path': entry['path'], 'size': len(after),
                              'original_sha256': sha(before), 'patched_sha256': sha(after)})
    require(changed_files == ['/boot/initrd.img', '/p1chksum'], 'Unexpected changed FAT file')
    new_sq = SquashImage(patched_initrd)
    require(sq.nodes == new_sq.nodes, 'SquashFS inode metadata changed')
    require(initrd[sq.inode_table:] == patched_initrd[sq.inode_table:], 'SquashFS metadata/footer changed')
    require(initrd[:frag_start] == patched_initrd[:frag_start] and
            initrd[frag_start+frag_size:] == patched_initrd[frag_start+frag_size:],
            'Unexpected initrd changes outside target fragment')
    key_offset = node['fragment_offset']
    require(original_fragment[:key_offset] == patched_fragment[:key_offset] and
            original_fragment[key_offset+451:] == patched_fragment[key_offset+451:],
            'Another file in shared fragment changed')
    original_inventory = sq.inventory()
    patched_inventory = new_sq.inventory()
    changed_squash = [a['path'] for a,b in zip(original_inventory, patched_inventory) if a != b]
    require(changed_squash == [TARGET] and new_sq.read(TARGET) == public,
            'SquashFS changes exceed the verification key')
    for label, data in [('original', raw), ('patched', image)]:
        parsed = {f.path.casefold(): f.contents.read() for f in vendor_fat.readFat(io.BytesIO(data))
                  if stat.S_ISREG(f.mode)}
        source_reader = fat if label == 'original' else new_fat
        require(parsed == {p:source_reader.read(p) for p,e in source_reader.entries.items() if not e['is_directory']},
                'Independent vendor FAT parser disagrees')
    diff = changed_ranges(raw, image)
    allowed = []
    for offset, length in sorted(initrd_extents + checksum_extents):
        end = offset + length
        if allowed and offset <= allowed[-1][1]:
            allowed[-1][1] = max(allowed[-1][1], end)
        else:
            allowed.append([offset, end])
    require(all(any(a <= begin and end <= b for a,b in allowed) for begin,end in diff),
            'Partition changes outside permitted file allocations')
    if verify_only:
        require(supplied_key is not None, 'Rebuild verification requires saved --private-key')
        image_path = output / 'nflasha1.R5_4.00.custom-key.logical.img'
        require(image_path.read_bytes() == image, 'Rebuilt image differs from saved artifact')
        require((output / 'nflasha1.R5_4.00.original.logical.img').read_bytes() == raw,
                'Saved recovery image differs from source')
        require((output / 'initrd.R5_4.00.custom-key.img').read_bytes() == patched_initrd,
                'Saved patched initrd differs')
        require((output / 'p1chksum.patched').read_bytes() == patched_checksums, 'Saved checksum file differs')
        require((output / 'r5-update-verification-public.pem').read_bytes() == public,
                'Saved public key differs from private key')
        require(stat.S_IMODE(supplied_key.stat().st_mode) == 0o600 and
                stat.S_IMODE(supplied_key.parent.stat().st_mode) == 0o700, 'Private key permissions unsafe')
        openssl(['rsa', '-in', str(supplied_key), '-check', '-noout'])
        original_manifest = json.loads((output / 'patch-manifest.json').read_text())
        require(original_manifest['output']['sha256'] == sha(image), 'Saved manifest image hash differs')
        print(json.dumps({'byte_identical_reproducible_rebuild': True, 'sha256': sha(image),
                          'SquashFS_inode_count': len(sq.nodes), 'only_changed_SquashFS_path': TARGET,
                          'metadata_preserved': True, 'private_key_permissions': '0600',
                          'private_key_directory_permissions': '0700'}, indent=2))
        return
    output.mkdir(parents=True, exist_ok=False)
    key_dir = output / 'keys'
    key_dir.mkdir(mode=0o700)
    os.chmod(key_dir, 0o700)
    private_path = key_dir / 'r5-update-signing-private.pem'
    public_path = output / 'r5-update-verification-public.pem'
    write_exclusive(private_path, private, 0o600)
    write_exclusive(public_path, public)
    openssl(['rsa', '-in', str(private_path), '-check', '-noout'])
    challenge = b'R5 partition-1 offline signing-key verification\n'
    signature = openssl(['dgst', '-sha256', '-sign', str(private_path)], challenge)
    signature_path = output / 'key-selftest.sig'
    write_exclusive(signature_path, signature)
    verify = openssl(['dgst', '-sha256', '-verify', str(public_path), '-signature', str(signature_path)], challenge)
    require(b'Verified OK' in verify, 'RSA signature self-test failed')
    write_exclusive(output / 'key-selftest-message.txt', challenge)
    image_path = output / 'nflasha1.R5_4.00.custom-key.logical.img'
    write_exclusive(image_path, image)
    restore_path = output / 'nflasha1.R5_4.00.original.logical.img'
    write_exclusive(restore_path, raw)
    write_exclusive(output / 'initrd.R5_4.00.custom-key.img', patched_initrd)
    write_exclusive(output / 'p1chksum.patched', patched_checksums)
    manifest = {
        'status': 'OFFLINE_VERIFIED_NOT_FLASHED_NOT_BOOT_TESTED',
        'builder': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__).read_bytes())},
        'target': {'model': 'ILCE-7RM5 (R5)', 'firmware': '4.00', 'partition': 'nflasha1',
                   'representation': 'logical bytes from oem partition dump; not encrypted NAND/raw backup'},
        'source': {'path': str(source.resolve()), 'size': len(raw), 'sha256': sha(raw)},
        'output': {'path': str(image_path.resolve()), 'size': len(image), 'sha256': sha(image)},
        'restore_image': {'path': str(restore_path.resolve()), 'size': len(raw), 'sha256': sha(raw)},
        'private_key': {'path': str(private_path.resolve()), 'mode': oct(stat.S_IMODE(private_path.stat().st_mode)),
                        'algorithm': 'RSA-2048', 'public_exponent': 65537, 'sha256': sha(private),
                        'key_generation_attempts_for_exact_fragment_size': attempts,
                        'key_source': 'supplied matching private key' if supplied_key else 'new RSA key generated locally'},
        'public_key': {'path': str(public_path.resolve()), 'size': len(public), 'sha256': sha(public),
                       'original_sha256': sha(original_key)},
        'initrd': {'size': len(initrd), 'original_md5': original_initrd_md5, 'patched_md5': new_initrd_md5,
                   'original_sha256': sha(initrd), 'patched_sha256': sha(patched_initrd),
                   'fragment_index': node['fragment_index'], 'fragment_offset_in_initrd': frag_start,
                   'stored_fragment_size': frag_size, 'uncompressed_fragment_size': len(original_fragment),
                   'key_offset_in_fragment': key_offset, 'zlib_level': 9, 'zlib_runtime_version': zlib.ZLIB_RUNTIME_VERSION,
                   'stream_padding_bytes': 0},
        'permitted_file_allocation_ranges_half_open': allowed,
        'partition_diff_ranges_half_open': diff,
        'changed_byte_count': sum(b-a for a,b in diff),
        'changed_FAT_paths': changed_files,
        'changed_SquashFS_paths': changed_squash,
        'verification': {'source_identity_checked': True, 'partition_size_unchanged': True,
                         'FAT_header_and_tables_unchanged': True, 'FAT_entries_and_allocation_unchanged': True,
                         'all_other_FAT_file_contents_unchanged': True, 'independent_vendor_FAT_parser_agrees': True,
                         'SquashFS_metadata_and_footer_byte_identical': True,
                         'all_SquashFS_inode_records_unchanged': True,
                         'all_other_SquashFS_file_contents_unchanged': True,
                         'shared_fragment_other_bytes_unchanged': True,
                         'single_complete_same_length_zlib_stream': True,
                         'original_and_updated_p1chksum_verified': True, 'RSA_sign_verify_selftest': True,
                         'camera_storage_written': False, 'camera_boot_tested': False,
                         'modified_update_package_installation_tested': False},
        'limitations': ['Host verification does not prove camera startup or acceptance of a modified update.',
                        'Use only the R5 4.00 image that supplied this exact original source hash.',
                        'Keep private key confidential and backed up; it is needed for future matching self-signed updates.',
                        'Other trust checks, partition checksum/signature boundaries, and rollback rules require separate verification.']
    }
    for name, records in [('squashfs-original-inventory.json', original_inventory),
                          ('squashfs-patched-inventory.json', patched_inventory),
                          ('fat-file-inventory.json', fat_inventory),
                          ('patch-manifest.json', manifest)]:
        write_exclusive(output / name, (json.dumps(records, indent=2, ensure_ascii=False) + '\n').encode())
    hashes = []
    for path in sorted(output.iterdir()):
        if path.is_file():
            hashes.append(sha(path.read_bytes()) + '  ' + path.name)
    write_exclusive(output / 'SHA256SUMS', ('\n'.join(hashes) + '\n').encode())
    print(json.dumps({'output': str(image_path.resolve()), 'sha256': sha(image),
                      'private_key': str(private_path.resolve()), 'checks': manifest['verification'],
                      'changed_byte_count': manifest['changed_byte_count'], 'key_generation_attempts': attempts},
                     indent=2, ensure_ascii=False))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--private-key', type=Path, help='Reuse matching saved private key for reproducible rebuild')
    parser.add_argument('--verify-only', action='store_true', help='Rebuild in memory and verify existing artifacts without writing')
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve(), args.private_key, args.verify_only)
