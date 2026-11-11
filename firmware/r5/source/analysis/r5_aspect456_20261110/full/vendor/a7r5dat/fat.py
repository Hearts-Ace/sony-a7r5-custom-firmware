"""冻结的FAT12读取与定长替换辅助。"""
import hashlib
import struct


def require(condition, message):
    if not condition:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

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
