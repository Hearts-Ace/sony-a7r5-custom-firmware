#!/usr/bin/env python3
"""Apply the FL2/FL3 patches inside the nflasha partition images.

The components do NOT live at the top of firmware.tar -- they are inside ext2
and FAT file systems carried by the partition images:

    appFw.so     -> 0700_part_image/dev/nflasha15  (ext2, /lib/appFw.so)
    cpapp-b.bin  -> 0700_part_image/dev/nflasha8   (/CPAPP-B.BIN, FAT12)

Both are patched by in-place byte replacement, so no file-system metadata
inode/FAT) has to be touched: the file sizes never change.

Every patch site carries its expected original bytes, and the physical mapping
from ELF offset to image offset is re-derived from the file system itself on
each run, so a layout change in a different firmware build fails loudly instead
of silently corrupting an unrelated block.

Usage:
    python3 patch_images.py <build_dir> [--dry-run]
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import hashlib
import json
import mmap
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "vendor/fwtool.py-a7iv"))

import ext2read  # noqa: E402

NFLASHA15 = "0700_part_image/dev/nflasha15"
NFLASHA8 = "0700_part_image/dev/nflasha8"

SHA = {
    "appFw.so": "41bd8f4cda1f44c7038912837737e1ce6a650065f2108061ada30e5c7f9ce7c7",
    "cpapp-b.bin": "3269bf62426339791fcfbe8529698cd4accbe6c3d2ea61cd7c368a90ab7ee7c8",
}


# --------------------------------------------------------------- FAT12 reader
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


# ------------------------------------------------------- offset translation
def ext2_file_map(img_path: Path, inner_path: str):
    """Return (size, list_of_data_blocks, block_size) for a file inside ext2."""
    e = ext2read.Ext2(str(img_path))
    ino = e.walk(inner_path)
    _, size, _ = e.inode(ino)
    blocks = e.inode_blocks(ino)
    return size, blocks, e.block_size, e


def elf_to_image_offset(off: int, blocks, block_size: int) -> int:
    """Translate an in-file (ELF) offset to a physical image offset."""
    blk = off // block_size
    if blk >= len(blocks):
        raise ValueError("offset 0x%x beyond file (%d blocks)" % (off, len(blocks)))
    b = blocks[blk]
    if b == 0:
        raise ValueError("offset 0x%x falls in a sparse hole" % off)
    return b * block_size + (off % block_size)


# ------------------------------------------------------------- patch tables
def patch_table():
    """Every patch, keyed by the component it belongs to, in ELF/file offsets."""
    P = {"appFw.so": [], "cpapp-b.bin": []}

    def add(comp, off, orig_hex, new_hex, desc):
        o = bytes.fromhex(orig_hex)
        n = bytes.fromhex(new_hex)
        assert len(o) == len(n), desc
        P[comp].append({"offset": off, "orig": o, "new": n, "desc": desc})

    CP = "cpapp-b.bin"
    add(CP, 0x12B8F0, "4ff00c0b", "4ff0360b", "still colour19 -> FL2 (fp=0x36)")
    add(CP, 0x12B920, "4ff00c0b", "4ff0370b", "still colour20 -> FL3 (fp=0x37)")
    add(CP, 0x12BE36, "4ff0ff0b", "4ff0380b", "movie colour19 -> FL2 (fp=0x38)")
    add(CP, 0x12BE66, "4ff0ff0b", "4ff0390b", "movie colour20 -> FL3 (fp=0x39)")

    # --- reader gate. Baseline (Thumb-2):
    #       0x61668c  bcc 0x616692      ; r6 < 0x34 -> body
    #       0x61668e  cmp r6,#0x35
    #       0x616690  bne 0x616746      ; anything else -> epilogue (no store)
    #       body: 0x61669c cmp r6,#0x33 / 0x61669e bhi 0x6166bc
    #     So the baseline accepts 0x00..0x33 and 0x35 only; 0x34 and >0x35
    #     return without writing anything.
    #
    #     First attempt used  cmp r6,#0x3a  +  bcc 0x616692  at 0x616690.
    #     That branch is at 0x616690 and its taken target equals its own
    #     fall-through (0x616692), i.e. a NO-OP: every r6 fell into the body.
    #     r6 >= 0x50 would then read past the 80-byte map table (property+0x1200)
    #     into the row data and could select an unrelated row.
    #
    #     Corrected: reject 0x34 explicitly (it used to return with no store),
    #     bound at 0x39, and keep >0x39 rejected.
    add(CP, 0x61668C, "01d3", "5bd0", "reader gate: eq 0x34 -> reject (0x616746)")
    add(CP, 0x61668E, "352e", "392e", "reader gate: cmp r6,#0x35 -> #0x39 (upper bound)")
    add(CP, 0x616690, "59d1", "59d8", "reader gate: bne -> bhi 0x616746 (reject >0x39)")
    add(CP, 0x61669C, "332e", "352e", "reader split: cmp r6,#0x33 -> #0x35")
    add(CP, 0x61669E, "0dd8", "0fd0", "reader split: bhi -> beq 0x6166c0 (0x35 -> special)")

    # --- CP: ALTERNATE reader 0x6169c8. Without this, profiles 0x36..0x39 are
    #     reported invalid (r6=0), the routine logs 0x257 and returns WITHOUT
    #     storing anything -- the new looks silently do nothing on these paths.
    #     Validity here is r6 = (r5 < 0x34) | (r5 == 0x35), computed at
    #     0x6169de/0x6169ec and tested at 0x616a06.
    #
    #     0x6169ec: widen the lower-bound test so 0x36..0x39 count as valid.
    add(CP, 0x6169EC, "342d", "3a2d", "alt reader: validity cmp r5,#0x34 -> #0x3a")

    #     0x616a14: reroute into a new dispatcher. The original
    #     `cmp r5,#0x33 / bhi 0x616a3e` sent >0x33 to the special/0x35 path;
    #     we need a three-way decision, which lives in the cave below.
    add(CP, 0x616A14, "332d12d8", "1ae000bf", "alt reader: -> new dispatcher (b + nop)")

    #     0x616a4c: 24 bytes of DEAD code in the baseline (proved unreachable:
    #     reaching it needs r5>0x33 AND r6==1, and r6==1 forces r5==0x35,
    #     which makes the guard `cmp r5,#0x35 / bne` fall through). Reused as:
    #         cmp r5,#0x34 ; beq 0x616a9a   -> reject, no store
    #         cmp r5,#0x35 ; beq 0x616a3e   -> keep the special table
    #         b 0x616a18                    -> map[r5] path
    add(CP, 0x616A4C,
        "40f614714ff49050c0f26b11085c272888bf002001eb8010",
        "342d24d0352df4d0e0e700bf00bf00bf00bf00bf00bf00bf",
        "alt reader: new dispatcher in dead code")

    AF = "appFw.so"
    add(AF, 0x3550368, "3f240071", "3f2c0071", "option guard cmp w1,#9 -> #0xb")
    add(AF, 0x3550370,
        "00b100d00040139100486138610000102088208b00001fd6",
        "e94b009029610491205961b820c1208b00001fd61f2003d5",
        "dispatch: PIC 4-byte relative table + nop")

    # relocated payload (table + two case bodies) written into the rodata cave
    P["appFw.so"].append(_relocated_payload())
    return P


CAVE_TABLE = 0x3ECC118
CASE_FL2 = CAVE_TABLE + 48
CASE_FL3 = CAVE_TABLE + 60
OLD_CASES = [0x35503D0, 0x3550388, 0x3550390, 0x3550398, 0x35503A0,
             0x35503A8, 0x35503B0, 0x35503B8, 0x35503C0, 0x35503C8]


def _relocated_payload():
    targets = OLD_CASES + [CASE_FL2, CASE_FL3]
    table = b"".join(struct.pack("<i", t - CAVE_TABLE) for t in targets)

    def body(colour):
        return (struct.pack("<I", 0x52800000 | (colour << 5)) +   # mov w0,#colour
                struct.pack("<I", 0x39000040) +                   # strb w0,[x2]
                struct.pack("<I", 0xD65F03C0))                    # ret

    blob = table + body(0x13) + body(0x14)
    return {"offset": CAVE_TABLE, "orig": b"\x00" * len(blob), "new": blob,
            "desc": "relocated dispatch table + FL2/FL3 case bodies"}


# ------------------------------------------------------------------- driver
def main() -> int:
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2

    build = Path(args[0]).resolve()
    base = build / "baseline"
    patched = build / "patched"
    evid = build / "evidence"

    src15 = base / Path(NFLASHA15).name
    src8 = base / Path(NFLASHA8).name
    for p in (src15, src8):
        if not p.exists():
            print("missing baseline image: %s" % p)
            return 1

    rep: dict = {"dry_run": dry, "images": {}, "patches": []}
    work = []

    # ---- 1. locate appFw.so inside nflasha15's ext2
    print("=== nflasha15 (ext2) ===")
    size, blocks, bsize, ext = ext2_file_map(src15, "lib/appFw.so")
    print("  /lib/appFw.so size=%d blocks=%d block_size=%d" % (size, len(blocks), bsize))
    jumps = sum(1 for i in range(1, len(blocks)) if blocks[i] != blocks[i - 1] + 1)
    print("  non-contiguous block jumps: %d (physical mapping is NOT linear)" % jumps)

    # read it through the block chain and verify identity
    buf = bytearray()
    for b in blocks:
        need = size - len(buf)
        if need <= 0:
            break
        take = min(bsize, need)
        buf += ext.mm[b * bsize:b * bsize + take]
    got = hashlib.sha256(bytes(buf)).hexdigest()
    ok = got == SHA["appFw.so"]
    print("  sha256 %s  %s" % (got, "OK" if ok else "MISMATCH"))
    if not ok:
        print("  ABORT: the ext2 copy of appFw.so is not the build we patched")
        return 1
    rep["images"]["nflasha15"] = {"sha256": got, "blocks": len(blocks),
                                  "jumps": jumps}

    # ---- 2. locate cpapp-b.bin inside nflasha8's FAT12
    print("\n=== nflasha8 (FAT12) ===")
    fat = Fat12(src8)
    name, cluster, csize = fat.find("CPAPP-B.BIN")
    chain = fat.chain(cluster)
    off8 = fat.cluster_offset(chain[0])
    print("  %s cluster=%d size=%d chain=%d clusters" % (name, cluster, csize, len(chain)))
    cjumps = sum(1 for i in range(1, len(chain)) if chain[i] != chain[i - 1] + 1)
    print("  cluster jumps: %d, file starts at image offset 0x%x" % (cjumps, off8))
    cbuf = bytearray()
    for c in chain:
        need = csize - len(cbuf)
        if need <= 0:
            break
        take = min(fat.cluster_size, need)
        o = fat.cluster_offset(c)
        cbuf += fat.mm[o:o + take]
    cgot = hashlib.sha256(bytes(cbuf)).hexdigest()
    cok = cgot == SHA["cpapp-b.bin"]
    print("  sha256 %s  %s" % (cgot, "OK" if cok else "MISMATCH"))
    if not cok:
        print("  ABORT: the FAT copy of cpapp-b.bin is not the build we patched")
        return 1
    rep["images"]["nflasha8"] = {"sha256": cgot, "clusters": len(chain),
                                 "jumps": cjumps, "file_offset": hex(off8)}

    # ---- 3. translate every patch offset and verify anchors
    print("\n=== anchor check ===")
    tables = patch_table()
    problems = []
    for comp, entries in tables.items():
        if comp == "appFw.so":
            data = bytes(buf)
            to_img = lambda off: elf_to_image_offset(off, blocks, bsize)  # noqa: E731
        else:
            data = bytes(cbuf)
            if cjumps:
                print("  ABORT: cpapp-b.bin is fragmented; cluster-aware patching needed")
                return 1
            to_img = lambda off: off8 + off  # noqa: E731
        for e in entries:
            cur = data[e["offset"]:e["offset"] + len(e["orig"])]
            ok = cur == e["orig"]
            rec = {"component": comp, "offset": e["offset"], "desc": e["desc"],
                   "anchor_ok": ok, "image_offset": hex(to_img(e["offset"]))}
            rep["patches"].append(rec)
            if not ok:
                problems.append((comp, e, cur))
            print("  %s %-12s 0x%08x -> img %-10s %s"
                  % ("ok " if ok else "BAD", comp, e["offset"],
                     hex(to_img(e["offset"])), e["desc"]))
    if problems:
        print("\nABORT: %d anchor mismatch(es)" % len(problems))
        for comp, e, cur in problems[:10]:
            print("   %s @0x%x want %s got %s" % (comp, e["offset"], e["orig"].hex(), cur.hex()))
        return 1
    print("all %d anchors verified" % len(rep["patches"]))

    if dry:
        print("\ndry-run: nothing written")
        (evid / "patch_images_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
        return 0

    # ---- 4. copy the images, patch them in place
    print("\n=== writing patched images ===")
    for src, name in ((src15, Path(NFLASHA15).name), (src8, Path(NFLASHA8).name)):
        dst = patched / name
        print("  %s -> %s (%d bytes)" % (src.name, dst, src.stat().st_size))
        with src.open("rb") as s, dst.open("wb") as d:
            while True:
                chunk = s.read(1 << 22)
                if not chunk:
                    break
                d.write(chunk)
        dst.chmod(0o644)
        work.append(dst)

    for comp, entries in tables.items():
        dst = patched / (NFLASHA15.split("/")[-1] if comp == "appFw.so" else NFLASHA8.split("/")[-1])
        with dst.open("r+b") as f:
            mm = mmap.mmap(f.fileno(), 0)
            for e in entries:
                if comp == "appFw.so":
                    off = elf_to_image_offset(e["offset"], blocks, bsize)
                else:
                    off = off8 + e["offset"]
                mm[off:off + len(e["new"])] = e["new"]
            mm.flush()
            mm.close()
        print("  applied %d patch(es) to %s" % (len(entries), dst.name))

    # ---- 5. read back and confirm
    print("\n=== read-back verification ===")
    allok = True
    for comp, entries in tables.items():
        if comp == "appFw.so":
            with (patched / Path(NFLASHA15).name).open("rb") as f:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            for e in entries:
                off = elf_to_image_offset(e["offset"], blocks, bsize)
                got = mm[off:off + len(e["new"])]
                ok = got == e["new"]
                allok &= ok
                print("  %s %s @0x%x img 0x%x -> %s"
                      % ("ok " if ok else "BAD", comp, e["offset"], off, got.hex()))
            mm.close()
        else:
            with (patched / Path(NFLASHA8).name).open("rb") as f:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            for e in entries:
                off = off8 + e["offset"]
                got = mm[off:off + len(e["new"])]
                ok = got == e["new"]
                allok &= ok
                print("  %s %s @0x%x img 0x%x -> %s"
                      % ("ok " if ok else "BAD", comp, e["offset"], off, got.hex()))
            mm.close()

    # ---- 6. nothing else may have changed
    # The correct invariant is not "same number of bytes" -- a patch whose new
    # bytes happen to equal the old ones changes fewer bytes than its length.
    # What must hold is: every changed region lies inside a patch footprint, and
    # the patched bytes match the intended new values (already checked above).
    print("\n=== diff scope check (only patch footprints may differ) ===")
    for comp, src, dst in (("appFw.so", src15, patched / Path(NFLASHA15).name),
                           ("cpapp-b.bin", src8, patched / Path(NFLASHA8).name)):
        # build the set of allowed edit ranges for this component
        allowed = []
        for e in tables[comp]:
            off = (elf_to_image_offset(e["offset"], blocks, bsize)
                   if comp == "appFw.so" else off8 + e["offset"])
            allowed.append((off, off + len(e["new"])))
        # merge adjacent/overlapping footprints: two neighbouring patches that
        # both change bytes form ONE contiguous diff region, which is still
        # entirely legal. Only bytes outside the union are stray.
        allowed.sort()
        merged = []
        for lo, hi in allowed:
            if merged and lo <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        allowed = [(lo, hi) for lo, hi in merged]
        with src.open("rb") as a, dst.open("rb") as b:
            ma = mmap.mmap(a.fileno(), 0, access=mmap.ACCESS_READ)
            mb = mmap.mmap(b.fileno(), 0, access=mmap.ACCESS_READ)
            n = min(len(ma), len(mb))
            regions = []
            i = 0
            while i < n:
                if ma[i] != mb[i]:
                    j = i
                    while j < n and ma[j] != mb[j]:
                        j += 1
                    regions.append((i, j))
                    i = j
                else:
                    i += 1
            ma.close()
            mb.close()
        stray = []
        for s, e_ in regions:
            # a changed region must lie within one of the allowed footprints
            if not any(s >= lo and e_ <= hi for lo, hi in allowed):
                stray.append((s, e_))
        changed = sum(e_ - s for s, e_ in regions)
        print("  %-12s %d changed region(s), %d byte(s), %d outside patch footprints"
              % (comp, len(regions), changed, len(stray)))
        for s, e_ in regions:
            tag = "ok" if any(s >= lo and e_ <= hi for lo, hi in allowed) else "STRAY"
            print("      %-5s @0x%x..0x%x (%d bytes)" % (tag, s, e_, e_ - s))
        rep.setdefault("diff_regions", {})[comp] = [
            {"start": hex(s), "end": hex(e_), "len": e_ - s,
             "inside_footprint": any(s >= lo and e_ <= hi for lo, hi in allowed)}
            for s, e_ in regions]
        if stray:
            print("      FAIL: %d region(s) changed outside every patch footprint" % len(stray))
            allok = False

    rep["readback_ok"] = allok
    (evid / "patch_images_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    print("\nreport: %s" % (evid / "patch_images_report.json"))
    print("RESULT:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit('Obsolete defective patch manifest disabled. Use build_corrected_fl2_fl3.py for exact component integration.')
