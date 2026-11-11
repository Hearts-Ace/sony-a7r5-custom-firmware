import mmap, struct
from pathlib import Path

class Fat12:
    """Minimal FAT12 reader, enough to locate one file and its cluster chain."""

    def __init__(self, path):
        self.path = Path(path)
        self.f = self.path.open("rb")
        self.mm = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        d = self.mm
        self.bps = struct.unpack_from("<H", d, 11)[0]
        self.spc = d[13]
        self.reserved = struct.unpack_from("<H", d, 14)[0]
        self.nfats = d[16]
        self.rootent = struct.unpack_from("<H", d, 17)[0]
        self.spf = struct.unpack_from("<H", d, 22)[0]
        self.fs_type = d[54:62]
        self.cluster_size = self.bps * self.spc
        self.fat_off = self.reserved * self.bps
        self.root_off = self.fat_off + self.nfats * self.spf * self.bps
        self.data_off = self.root_off + \
            ((self.rootent * 32 + self.bps - 1) // self.bps) * self.bps

    def next_cluster(self, c):
        if self.fs_type.startswith(b"FAT12"):
            off = self.fat_off + c + c // 2
            v = struct.unpack_from("<H", self.mm, off)[0]
            return (v >> 4) if (c & 1) else (v & 0xFFF)
        if self.fs_type.startswith(b"FAT16"):
            return struct.unpack_from("<H", self.mm, self.fat_off + c * 2)[0]
        raise NotImplementedError(self.fs_type)

    def chain(self, c):
        out, seen = [], set()
        while 2 <= c < 0xFF8:
            if c in seen:
                raise ValueError("cluster loop at %d" % c)
            seen.add(c)
            out.append(c)
            c = self.next_cluster(c)
        return out

    def entries(self):
        pos = self.root_off
        for _ in range(self.rootent):
            e = self.mm[pos:pos + 32]
            if len(e) < 32 or e[0] == 0:
                return
            if e[0] == 0xE5 or e[11] == 0x0F or (e[11] & 0x08):
                pos += 32
                continue
            name = (e[:8].decode("latin1").rstrip() + "." +
                    e[8:11].decode("latin1").rstrip()).strip(".")
            yield name, struct.unpack_from("<H", e, 26)[0], \
                struct.unpack_from("<I", e, 28)[0]
            pos += 32

    def find(self, want):
        for name, cluster, size in self.entries():
            if name.lower() == want.lower():
                return name, cluster, size
        raise KeyError(want)

    def cluster_offset(self, c):
        return self.data_off + (c - 2) * self.cluster_size
