"""Append private MID 0x635 to the native Fn Color/Tone candidate group.

Only the group's item count and one originally zero item slot change. No
executable bytes or relocation entries are introduced. Does not run camera IO.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct

GROUP_VA = 0x3E6F218
COUNT_VA = GROUP_VA + 8
CREATIVE_VA = 0x3E6F264
INSERT_VA = 0x3E6F3A4
PRIVATE_MID = 0x635
CREATIVE_FLAGS = bytes.fromhex(
    "010100010100010100010100010100010100010100010100000000010100"
    "010100010100010100010100010100010100010100010100010100010100"
)


def apply_fn_patch(raw):
    """Return patched bytes and source-bound ledger; strict 4.32 preconditions."""
    raw = bytes(raw)
    assert raw[:6] == b"\x7fELF\x02\x01"
    # These are file-backed original RX rodata addresses (VA == file offset).
    assert struct.unpack_from("<III", raw, GROUP_VA) == (21, 0x0200604E, 6)
    assert struct.unpack_from("<I", raw, CREATIVE_VA)[0] == 0x1F2
    flags = raw[CREATIVE_VA + 4:CREATIVE_VA + 64]
    assert flags == CREATIVE_FLAGS and len(flags) == 60
    assert all(flags[i] == 0 for i in range(2, 60, 3)), "play must remain excluded"
    assert raw[INSERT_VA:INSERT_VA + 64] == bytes(64)
    old_group = raw[GROUP_VA:GROUP_VA + 0x68C]
    old_ids = [struct.unpack_from("<I", old_group, 12 + 64 * i)[0] for i in range(6)]
    assert old_ids == [0x1F1, 0x1F2, 0x1F3, 0x1F4, 0x1F5, 0x1F9]
    out = bytearray(raw)
    struct.pack_into("<I", out, COUNT_VA, 7)
    out[INSERT_VA:INSERT_VA + 64] = struct.pack("<I", PRIVATE_MID) + flags
    assert out[CREATIVE_VA:CREATIVE_VA + 64] == raw[CREATIVE_VA:CREATIVE_VA + 64]
    spans = [dict(va=hex(COUNT_VA), file_offset=COUNT_VA,
                  before=raw[COUNT_VA:COUNT_VA + 4].hex(), after=out[COUNT_VA:COUNT_VA + 4].hex()),
             dict(va=hex(INSERT_VA), file_offset=INSERT_VA,
                  before=raw[INSERT_VA:INSERT_VA + 64].hex(), after=out[INSERT_VA:INSERT_VA + 64].hex())]
    ledger = dict(source_sha256=hashlib.sha256(raw).hexdigest(),
                  patched_sha256=hashlib.sha256(out).hexdigest(),
                  added_rx_bytes=0, added_bss_bytes=0,
                  changed_bytes=sum(a != b for a, b in zip(raw, out)),
                  native_builder="0x1bdd6f8", native_valid="0x1bd8d9c",
                  group_va=hex(GROUP_VA), original_ids=list(map(hex, old_ids)),
                  appended_mid=hex(PRIVATE_MID), still_movie_flags_from="0x1f2",
                  play_enabled=False, patches=spans)
    return bytes(out), ledger


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--ledger", required=True, type=Path)
    a = p.parse_args()
    patched, ledger = apply_fn_patch(a.source.read_bytes())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(patched)
    a.ledger.write_text(json.dumps(ledger, indent=2) + "\n")
    print(json.dumps({k: v for k, v in ledger.items() if k != "patches"}))


if __name__ == "__main__":
    main()
