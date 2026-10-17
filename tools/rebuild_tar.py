#!/usr/bin/env python3
"""Rebuild firmware.tar with the patched partition images, streaming.

The tar members we touch keep their exact size, so the archive layout is
unchanged and no member headers need rewriting. We copy the archive through

once and splice in four same-size replacements:

    0700_part_image/dev/nflasha15   <- patched/ (has the patched appFw.so inside)
    0700_part_image/dev/nflasha8    <- patched/ (has the patched cpapp-b.bin inside)
    0110_backup/.../CX89201_CN2.bin  (mainland-China FL2/FL3 property data)
    0111_backup_sum/backup.sum      (CRC of the file above)
    0701_part_image_sum/part_image.sum  (CRC of the two images above)

The .sum files carry `binascii.crc32` per entry, so they have to be updated or
the updater will reject the images.

Usage:
    python3 rebuild_tar.py <build_dir> [--dry-run]
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import binascii
import hashlib
import io
import json
import os
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DONOR_TAR = ROOT / "unpacked/r5/firmware.tar"

# tar member -> local file supplying its new contents
REPLACE = {
    "0700_part_image/dev/nflasha15": "nflasha15",
    "0700_part_image/dev/nflasha8": "nflasha8",
    "0110_backup/SYSIPSX-DSLR/GL/CX89201_CN2.bin": "CX89201_CN2.bin",
}

# .sum entries that need their crc32 refreshed: member -> {path_in_sum: local}
SUM_UPDATES = {
    "0111_backup_sum/backup.sum": {
        "SYSIPSX-DSLR/GL/CX89201_CN2.bin": "CX89201_CN2.bin",
    },
    "0701_part_image_sum/part_image.sum": {
        "dev/nflasha15": "nflasha15",
        "dev/nflasha8": "nflasha8",
    },
}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


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


def main() -> int:
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2

    build = Path(args[0]).resolve()
    patched = build / "patched"
    evid = build / "evidence"
    out_tar = patched / "firmware.tar.new"

    src_tar = DONOR_TAR
    if not src_tar.exists():
        print("missing donor tar: %s" % src_tar)
        return 1

    locals_ = {name: patched / fn for name, fn in REPLACE.items()}
    for name, p in locals_.items():
        if not p.exists():
            print("missing patched input for %s: %s" % (name, p))
            return 1

    rep: dict = {"dry_run": dry, "members": []}

    # ---- 1. inspect the donor tar, record member geometry
    print("=== donor tar ===")
    print("  %s (%d bytes, sha %s)" % (src_tar, src_tar.stat().st_size,
                                       sha256_file(src_tar)[:16]))
    with tarfile.open(src_tar, "r:") as tf:
        members = {m.name: m for m in tf.getmembers()}
    print("  %d members" % len(members))

    plan = []
    for name, local in locals_.items():
        m = members.get(name)
        if m is None:
            print("  ABORT: member not in tar: %s" % name)
            return 1
        new_size = local.stat().st_size
        ok = new_size == m.size
        print("  %-48s tar=%d local=%d %s"
              % (name, m.size, new_size, "size match" if ok else "SIZE MISMATCH"))
        if not ok:
            print("  ABORT: sizes must match for in-place replacement")
            return 1
        plan.append((name, m.offset_data, new_size))
        rep["members"].append({"member": name, "offset_data": m.offset_data,
                               "size": new_size,
                               "sha256": sha256_file(local)})

    # ---- 2. build the new .sum contents
    print("\n=== .sum updates ===")
    sum_replacements = {}
    for member, mapping in SUM_UPDATES.items():
        m = members.get(member)
        if m is None:
            print("  ABORT: sum member missing: %s" % member)
            return 1
        with tarfile.open(src_tar, "r:") as tf:
            text = tf.extractfile(member).read().decode("ascii")
        # map sum-internal paths to real files
        real = {}
        sizes = {}
        for path_in_sum, fn in mapping.items():
            p = patched / fn
            if not p.exists():
                print("  ABORT: missing %s for %s" % (p, member))
                return 1
            real[path_in_sum] = p
            sizes[path_in_sum] = p.stat().st_size
        new_text, changes = update_sum(text, real, sizes)
        print("  %s: %d entr%s updated" % (member, len(changes),
                                           "y" if len(changes) == 1 else "ies"))
        for c in changes:
            print("      %-34s %s -> %s (size %s -> %s)"
                  % (c["path"], c["crc_before"], c["crc_after"],
                     c["size_before"], c["size_after"]))
        nb = new_text.encode("ascii")
        if len(nb) != m.size:
            print("  ABORT: new %s is %d bytes, tar member is %d"
                  % (member, len(nb), m.size))
            return 1
        sum_replacements[member] = nb
        rep.setdefault("sum_updates", {})[member] = changes

    if dry:
        print("\ndry-run: nothing written")
        (evid / "rebuild_tar_dryrun.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
        return 0

    # ---- 3. stream the tar through, splicing replacements
    print("\n=== rebuilding tar (streaming) ===")
    # every replacement, including the .sum members
    all_repl = {name: (off, size, locals_[name])
                for name, off, size in plan}
    with tarfile.open(src_tar, "r:") as tf:
        for member, blob in sum_replacements.items():
            m = members[member]
            all_repl[member] = (m.offset_data, m.size, None)
    # order by offset for a single sequential pass
    order = sorted(all_repl.items(), key=lambda kv: kv[1][0])

    written = 0
    with src_tar.open("rb") as s, out_tar.open("wb") as d:
        pos = 0
        for name, (off, size, local) in order:
            if off < pos:
                print("  ABORT: overlapping replacements at %s" % name)
                return 1
            # copy the gap
            gap = off - pos
            while gap > 0:
                chunk = s.read(min(1 << 22, gap))
                if not chunk:
                    print("  ABORT: unexpected EOF")
                    return 1
                d.write(chunk)
                gap -= len(chunk)
                written += len(chunk)
            # write the replacement
            if local is not None:
                with local.open("rb") as lf:
                    left = size
                    while left > 0:
                        chunk = lf.read(min(1 << 22, left))
                        if not chunk:
                            print("  ABORT: short read from %s" % local)
                            return 1
                        d.write(chunk)
                        left -= len(chunk)
                        written += len(chunk)
            else:
                d.write(sum_replacements[name])
                written += size
            s.seek(off + size)
            pos = off + size
            print("  spliced %-48s @0x%x (%d bytes)" % (name, off, size))
        # copy the remainder
        s.seek(pos)
        while True:
            chunk = s.read(1 << 22)
            if not chunk:
                break
            d.write(chunk)
            written += len(chunk)

    out_tar.chmod(0o644)
    src_size = src_tar.stat().st_size
    print("  wrote %s (%d bytes)" % (out_tar, written))
    if written != src_size:
        print("  ABORT: size changed %d != %d" % (written, src_size))
        return 1
    print("  size preserved: %d" % written)

    # ---- 4. verify by re-reading the produced tar
    print("\n=== verification ===")
    allok = True
    with tarfile.open(out_tar, "r:") as tf:
        names = tf.getnames()
        print("  members: %d (donor had %d)" % (len(names), len(members)))
        if len(names) != len(members):
            allok = False
            print("  FAIL: member count changed")
        for name, off, size in plan:
            import hashlib as _h
            data = tf.extractfile(name).read()
            want = (patched / REPLACE[name]).read_bytes()
            same = data == want
            allok &= same
            print("  %s %-48s %s" % ("ok " if same else "BAD", name,
                                     "matches local file" if same
                                     else "DIFFERS (%d vs %d bytes)" % (len(data), len(want))))
        for member, changes in rep.get("sum_updates", {}).items():
            text = tf.extractfile(member).read().decode("ascii")
            for c in changes:
                found = ("%s,%s" % (c["path"], c["crc_after"])) in text or \
                        (",%s," % c["crc_after"]) in text
                # more precise: confirm the path's line carries the new crc
                bad = False
                for line in text.splitlines():
                    if line.rstrip(",").endswith(c["path"]):
                        parts = line.split(",")
                        bad = parts[1] != c["crc_after"]
                ok = not bad
                allok &= ok
                print("  %s %-48s crc=%s" % ("ok " if ok else "BAD",
                                             c["path"], c["crc_after"]))

    rep["output"] = {"path": str(out_tar), "size": written,
                     "sha256": sha256_file(out_tar)}
    rep["verification_ok"] = allok
    (evid / "rebuild_tar.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    print("\n  sha256 %s" % rep["output"]["sha256"])
    print("  report: %s" % (evid / "rebuild_tar.json"))
    print("RESULT:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
