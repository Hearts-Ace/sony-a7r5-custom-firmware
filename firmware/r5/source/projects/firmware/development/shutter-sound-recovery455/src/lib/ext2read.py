"""Targeted ext2 reader: walk a path and report the real block layout."""
import mmap, struct, sys

class Ext2:
    def __init__(self, path):
        self.f = open(path, "rb")
        self.mm = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        d = self.mm
        self.inodes_count, self.blocks_count = struct.unpack_from("<II", d, 1024)
        self.block_size = 1024 << struct.unpack_from("<I", d, 1024+24)[0]
        self.blocks_per_group = struct.unpack_from("<I", d, 1024+32)[0]
        self.inodes_per_group = struct.unpack_from("<I", d, 1024+40)[0]
        self.inode_size = struct.unpack_from("<H", d, 1024+88)[0]
        self.magic = d[1024+56:1024+58]
        assert self.magic == b"\x53\xef", self.magic
        self.bgd_off = max(self.block_size, 2048)
        self.ngroups = (self.blocks_count - 1)//self.blocks_per_group + 1

    def inode_table(self, group):
        return struct.unpack_from("<I", self.mm, self.bgd_off + group*32 + 8)[0]

    def inode(self, i):
        g = (i-1)//self.inodes_per_group
        off = self.inode_table(g)*self.block_size + ((i-1) % self.inodes_per_group)*self.inode_size
        mode, uid, size = struct.unpack_from("<HHI", self.mm, off)
        blocks_raw = self.mm[off+40:off+100]
        ptrs = list(struct.unpack("<15I", blocks_raw))
        return mode, size, ptrs

    def inode_blocks(self, i):
        """Yield (block_number, is_hole) for data blocks of inode i."""
        mode, size, ptrs = self.inode(i)
        n = (size + self.block_size - 1)//self.block_size
        bs = self.block_size
        out = []
        # direct 0..11
        for k in range(12):
            if len(out) >= n: break
            out.append(ptrs[k])
        # single indirect 12
        if len(out) < n and ptrs[12]:
            cnt = bs//4
            arr = struct.unpack_from("<%dI" % cnt, self.mm, ptrs[12]*bs)
            for p in arr:
                if len(out) >= n: break
                out.append(p)
        # double indirect 13
        if len(out) < n and ptrs[13]:
            cnt = bs//4
            arr = struct.unpack_from("<%dI" % cnt, self.mm, ptrs[13]*bs)
            for p in arr:
                if len(out) >= n: break
                if not p: continue
                arr2 = struct.unpack_from("<%dI" % cnt, self.mm, p*bs)
                for q in arr2:
                    if len(out) >= n: break
                    out.append(q)
        # triple indirect 14
        if len(out) < n and ptrs[14]:
            cnt = bs//4
            arr = struct.unpack_from("<%dI" % cnt, self.mm, ptrs[14]*bs)
            for p in arr:
                if len(out) >= n: break
                if not p: continue
                arr2 = struct.unpack_from("<%dI" % cnt, self.mm, p*bs)
                for q in arr2:
                    if len(out) >= n: break
                    if not q: continue
                    arr3 = struct.unpack_from("<%dI" % cnt, self.mm, q*bs)
                    for r in arr3:
                        if len(out) >= n: break
                        out.append(r)
        return out[:n]

    def read_inode(self, i):
        _, size, _ = self.inode(i)
        blocks = self.inode_blocks(i)
        buf = bytearray()
        for b in blocks:
            want = min(self.block_size, size - len(buf))
            if want <= 0: break
            if b == 0:
                buf += b"\x00"*want
            else:
                buf += self.mm[b*self.block_size:b*self.block_size+want]
        return bytes(buf)

    def dir_entries(self, i):
        _, size, _ = self.inode(i)
        blocks = self.inode_blocks(i)
        data = bytearray()
        for b in blocks:
            if b == 0: data += b"\x00"*self.block_size
            else: data += self.mm[b*self.block_size:(b+1)*self.block_size]
        data = data[:size]
        pos = 0
        while pos + 8 <= len(data):
            ino, rec, nlen, ftype = struct.unpack_from("<IHBB", data, pos)
            if rec == 0: break
            name = data[pos+8:pos+8+nlen]
            if ino: yield ino, name.decode("latin1"), ftype
            pos += rec

    def walk(self, path):
        parts = [p for p in path.split("/") if p]
        cur = 2  # root inode
        for pi, part in enumerate(parts):
            found = None
            for ino, name, ftype in self.dir_entries(cur):
                if name == part:
                    found = ino; break
            if found is None:
                raise KeyError("not found: %s (at %s)" % (part, "/".join(parts[:pi])))
            cur = found
        return cur

if __name__ == "__main__":
    img, path = sys.argv[1], sys.argv[2]
    e = Ext2(img)
    print("block_size=%d inode_size=%d inodes=%d blocks=%d groups=%d"
          % (e.block_size, e.inode_size, e.inodes_count, e.blocks_count, e.ngroups))
    ino = e.walk(path)
    mode, size, ptrs = e.inode(ino)
    print("inode %d mode=0o%o size=%d" % (ino, mode, size))
    print("ptrs:", [hex(p) for p in ptrs])
    blocks = e.inode_blocks(ino)
    print("data blocks: %d" % len(blocks))
    print("first 12 blocks:", [hex(b) for b in blocks[:12]])
    # detect non-contiguity
    breaks = [i for i in range(1, len(blocks)) if blocks[i] != blocks[i-1]+1]
    print("non-contiguous jumps: %d" % len(breaks))
    if breaks:
        print("  first 10 break points at block indices", breaks[:10])
        print("  around first break:", [hex(b) for b in blocks[max(0,breaks[0]-2):breaks[0]+3]])
