#!/usr/bin/env python3
"""Apply the FL2/FL3 property data to a *copy* of the R5 backup container.

Fills the four map bytes (profile 0x36..0x39 -> rows) and the four row slots,
then repairs the BK4 bank sum-check (additive, not CRC) so the container stays
self-consistent.

Writes only into <build>/patched/. Reads the baseline read-only.

Usage:
    python3 apply_fl2_fl3_property.py <build_dir> [--dry-run]
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import hashlib
import json
import struct
import sys
from pathlib import Path

BACKUP = "CX89200_ALLLANG.bin"
BACKUP_SHA = "a3b036d3e1dbeeb7c6e2fc7f02d41e5fc2731b8ba8165c3ee9927d9b504a876c"

# Verified against evidence.json for this build.
BANK2_OFFSET = 0xEF000          # second BK4 bank
PROPERTY_FILE_OFFSET = 0x1B7620  # property 0x02a40001 data, complete file offset
PROPERTY_SIZE = 0x2000
PROPERTY_SHA = "1fdae63d018d6f9d73de43273cb2694ef93d78dea8dff68779751956401b1f8a"

# profile -> (map byte offset within property, new map value, row index)
MAP_SLOTS = {
    0x36: (0x1236, 0x16, 0x16),   # FL2 still
    0x37: (0x1237, 0x18, 0x18),   # FL3 still
    0x38: (0x1238, 0x17, 0x17),   # FL2 movie
    0x39: (0x1239, 0x19, 0x19),   # FL3 movie
}

ROW_STRIDE = 64
ROW_BASE = 0x1250               # row_address = property + 0x1250 + 64*row


def row_data() -> dict[int, bytes]:
    """The four converted (delta-format) rows, from the verified component bundle.

    Source: analysis/fx2_fl2_fl3_20261011/verified/r5_delta_rows_RESEARCH_ONLY.bin
    Layout there: FL2 still, FL3 still, FL2 movie, FL3 movie (64 bytes each).
    """
    build_hint = Path(__file__).resolve().parent.parent / \
        "analysis/fx2_fl2_fl3_20261011/verified/r5_delta_rows_RESEARCH_ONLY.bin"
    if not build_hint.exists():
        raise SystemExit(f"missing donor rows: {build_hint}")
    blob = build_hint.read_bytes()
    if len(blob) != 256:
        raise SystemExit(f"unexpected donor bundle size {len(blob)} (want 256)")
    order = [0x36, 0x37, 0x38, 0x39]   # FL2 still, FL3 still, FL2 movie, FL3 movie
    out = {}
    for i, prof in enumerate(order):
        chunk = blob[i * 64:(i + 1) * 64]
        # first 48 bytes are the 24 int16 coefficients; last 16 are reserved
        out[prof] = chunk[:48]
    return out


def bank_sum(data: bytes) -> int:
    """BK4 checksum: sum of header bytes 0x00..0x1f plus everything from 0x24 on."""
    return sum(data[:0x20]) + sum(data[0x24:])


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if not args:
        print(__doc__)
        return 2
    build = Path(args[0]).resolve()
    base, patched, evid = build / "baseline", build / "patched", build / "evidence"
    if not (base / BACKUP).exists():
        print(f"missing baseline {BACKUP}")
        return 1

    raw = (base / BACKUP).read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    print(f"{'ok ' if got == BACKUP_SHA else 'BAD'} baseline {BACKUP} {got}")
    if got != BACKUP_SHA:
        print("ABORT: baseline hash mismatch")
        return 1

    rep: dict = {"container": BACKUP, "dry_run": dry, "checks": {}, "changes": []}

    # ---- sanity: property must be where we think it is
    prop = raw[PROPERTY_FILE_OFFSET:PROPERTY_FILE_OFFSET + PROPERTY_SIZE]
    psha = hashlib.sha256(prop).hexdigest()
    print(f"{'ok ' if psha == PROPERTY_SHA else 'BAD'} property 0x02a40001 sha {psha}")
    if psha != PROPERTY_SHA:
        print("ABORT: property hash mismatch - addresses are for a different build")
        return 1
    rep["checks"]["property_sha256"] = psha

    # ---- original map bytes must still be the neutral 0x00 we expect
    for prof, (moff, newval, row) in MAP_SLOTS.items():
        cur = prop[moff]
        rep["changes"].append({
            "kind": "map", "profile": hex(prof), "prop_offset": hex(moff),
            "row": hex(row), "before": cur, "after": newval,
        })
        if cur != 0x00:
            print(f"ABORT: map byte for profile {prof:#x} is {cur:#04x}, expected 0x00")
            return 1

    rows = row_data()
    for prof, (moff, newval, row) in MAP_SLOTS.items():
        roff = ROW_BASE + ROW_STRIDE * row
        cur = prop[roff:roff + 48]
        new = rows[prof]
        rep["changes"].append({
            "kind": "row", "profile": hex(prof), "prop_offset": hex(roff),
            "row": hex(row), "before_sha256": hashlib.sha256(cur).hexdigest(),
            "after_sha256": hashlib.sha256(new).hexdigest(),
            "before_is_zero": cur == b"\x00" * 48,
        })
        if cur != b"\x00" * 48:
            print(f"ABORT: row {row:#x} for profile {prof:#x} is not zero-filled")
            return 1

    print(f"all {len(MAP_SLOTS)} map bytes are 0x00 and all rows are zero-filled")

    # ---- build the new property image
    new_prop = bytearray(prop)
    for prof, (moff, newval, row) in MAP_SLOTS.items():
        new_prop[moff] = newval
        roff = ROW_BASE + ROW_STRIDE * row
        new_prop[roff:roff + 48] = rows[prof]

    rep["checks"]["property_sha256_after"] = hashlib.sha256(bytes(new_prop)).hexdigest()

    # ---- compute the BK4 bank checksum before/after
    # bank extent comes from the bank's own header
    ns, np_, start, size, checksum = struct.unpack_from("<5I", raw, BANK2_OFFSET + 0x10)
    bank_len = start + size
    bank = bytearray(raw[BANK2_OFFSET:BANK2_OFFSET + bank_len])
    before_sum = bank_sum(bytes(bank))
    rep["checks"]["bank2_stored_checksum"] = hex(checksum)
    rep["checks"]["bank2_calculated_before"] = hex(before_sum)
    print(f"bank2: stored 0x{checksum:x}, calculated 0x{before_sum:x}, "
          f"{'match' if checksum == before_sum else 'MISMATCH'}")
    if checksum != before_sum:
        print("ABORT: baseline bank checksum does not validate")
        return 1

    # property is inside bank2; recompute bank sum with the patched property
    p_rel = PROPERTY_FILE_OFFSET - BANK2_OFFSET
    bank[p_rel:p_rel + PROPERTY_SIZE] = new_prop
    after_sum = bank_sum(bytes(bank))
    rep["checks"]["bank2_calculated_after"] = hex(after_sum)
    delta = after_sum - before_sum
    rep["checks"]["checksum_delta"] = delta
    print(f"bank2 sum after property edit: 0x{after_sum:x} (delta {delta:+#x})")

    # patch the stored checksum field (offset +0x10+0x10 within bank header)
    chk_field = BANK2_OFFSET + 0x10 + 0x10
    struct.pack_into("<I", bank, 0x20, after_sum & 0xFFFFFFFF)
    rep["checks"]["checksum_field_file_offset"] = hex(chk_field)
    # verify the repaired bank validates
    if bank_sum(bytes(bank)) != (after_sum & 0xFFFFFFFF):
        print("ABORT: checksum repair did not validate")
        return 1
    # NOTE: patching the checksum field changes the sum, because bytes 0x24.. are
    # included but 0x20..0x23 (the checksum itself) are excluded by the format.
    print(f"bank2 sum with repaired field: 0x{bank_sum(bytes(bank)):x}")

    if dry:
        print("\ndry-run: nothing written")
        (evid / "apply_property_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
        return 0

    # ---- write the whole container copy
    out = bytearray(raw)
    out[PROPERTY_FILE_OFFSET:PROPERTY_FILE_OFFSET + PROPERTY_SIZE] = new_prop
    struct.pack_into("<I", out, chk_field, after_sum & 0xFFFFFFFF)
    dst = patched / BACKUP
    dst.write_bytes(bytes(out))
    dst.chmod(0o644)

    rep["container_sha256_before"] = got
    rep["container_sha256_after"] = hashlib.sha256(bytes(out)).hexdigest()
    (evid / "apply_property_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    print(f"\nwrote {dst}")
    print(f"  before {rep['container_sha256_before']}")
    print(f"  after  {rep['container_sha256_after']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
