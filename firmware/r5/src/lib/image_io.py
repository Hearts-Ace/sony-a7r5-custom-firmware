from pathlib import Path
import hashlib, binascii
from ext2read import Ext2
from fat_reader import Fat12
CHUNK=4<<20

def require(ok,message):
    if not ok: raise ValueError(message)

def digest_file(path):
    with Path(path).open("rb") as f:
        return digest_stream(f)

def digest_stream(f):
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(CHUNK), b""):
        h.update(chunk)
    return h.hexdigest()

def close_image(reader):
    reader.mm.close()
    reader.f.close()

def geometry(path, component):
    if component == "appFw.so":
        e = Ext2(str(path))
        ino = e.walk("lib/appFw.so")
        _, size, _ = e.inode(ino)
        units, unit_size = e.inode_blocks(ino), e.block_size
        require(len(units) == (size + unit_size - 1) // unit_size,
                "ext2 incomplete logical block chain")
        require(all(units), "sparse ext2 component unsupported")
        offsets = [b * unit_size for b in units]
        inner = e.read_inode(ino)
        meta = {"type": "ext2", "inode": ino}
    else:
        e = Fat12(path)
        _, cluster, size = e.find("CPAPP-B.BIN")
        units, unit_size = e.chain(cluster), e.cluster_size
        offsets = [e.cluster_offset(c) for c in units]
        require(len(units) == (size + unit_size - 1) // unit_size,
                "FAT chain length differs from directory size")
        inner = b"".join(e.mm[o:o + unit_size] for o in offsets)[:size]
        meta = {"type": "FAT12", "first_cluster": cluster}
    require(len(inner) == size, "short embedded component")
    meta.update(size=size, logical_units=len(units), unit_size=unit_size,
                discontinuities=sum(b != a + unit_size
                                    for a, b in zip(offsets, offsets[1:])))
    close_image(e)
    return inner, offsets, unit_size, meta

def crc32_file(p: Path) -> int:
    c = 0
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            c = binascii.crc32(chunk, c)
    return c & 0xFFFFFFFF

def update_sum(text: str, mapping: dict, sizes: dict) -> tuple[str, list]:
    """Rewrite crc32 (and size, should it ever change) for the given paths.

    Line layout (12 comma-separated fields, trailing empty field):
        0,<crc32>,<size>,<mode>,<uid>,<gid>,<user>,<group>,<a>,<b>,<path>,
    """
    out = []
    changes = []
    for line in text.splitlines():
        parts = line.split(",")
        if len(parts) >= 11:
            path_in_sum = parts[10]
            if path_in_sum in mapping:
                old_crc, old_size = parts[1], parts[2]
                new_crc = "%08x" % crc32_file(mapping[path_in_sum])
                parts[1] = new_crc
                if sizes.get(path_in_sum):
                    parts[2] = "%08x" % sizes[path_in_sum]
                changes.append({"path": path_in_sum, "crc_before": old_crc,
                                "crc_after": new_crc, "size_before": old_size,
                                "size_after": parts[2]})
                line = ",".join(parts)
        out.append(line)
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(out) + trailing, changes
