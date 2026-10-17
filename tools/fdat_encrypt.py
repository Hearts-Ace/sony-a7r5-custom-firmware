#!/usr/bin/env python3
"""FDAT encryption for Sony 4th-gen (CXD90057_k8) images - the inverse of
fwtool.py's AesCbcCrypter.decrypt(), which upstream leaves unimplemented.

Layout (from fwtool/fwtool/sony/fdat.py):
  * body            : encrypted bytes, 1024-byte blocks, each carrying its own
                      4-byte header (sum16, sizeAndEndFlag) before encryption
  * body[-0x110:]   : 16-byte IV followed by 256 bytes of trailing data

Block cipher shape for CXD90057_k8 (decryptBlock):
  first block : AES-ECB(key_aes) over bytes [0:512]
                AES-CBC(key_cxd90057_k8, IV) over bytes [512:1024]
  later blocks: AES-CBC continues over the whole block

Encryption is the exact inverse, with the CBC chain carried across blocks.

Round-trip test:
    python3 fdat_encrypt.py roundtrip <BODYDATA.DAT>
"""
from __future__ import annotations

import io
import struct
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/fwtool.py-a7iv"))

from fwtool.sony import constants  # noqa: E402
from fwtool.sony import dat as datmod  # noqa: E402

BLOCK = 1024
BODY_HEADER = 4
PAYLOAD = BLOCK - BODY_HEADER      # 1020
TAIL = 0x110                        # 16 IV + 256 trailing


def _sum16(data: bytes) -> int:
    """Sum of little-endian 16-bit words, truncated to 16 bits."""
    if len(data) % 2:
        data = data + b"\x00"
    try:
        import numpy as np
        return int(np.frombuffer(data, dtype="<u2").sum(dtype=np.uint64) & 0xFFFF)
    except ImportError:
        total = 0
        for i in range(0, len(data), 2):
            total += data[i] | (data[i + 1] << 8)
        return total & 0xFFFF


def _sum16_batch(payloads: list[bytes]) -> list[int]:
    """Vectorised _sum16 for many equal-length payloads at once."""
    if not payloads:
        return []
    try:
        import numpy as np
    except ImportError:
        return [_sum16(p) for p in payloads]
    lens = {len(p) for p in payloads}
    if len(lens) != 1 or (lens.pop() % 2):
        return [_sum16(p) for p in payloads]
    arr = np.frombuffer(b"".join(payloads), dtype="<u2")
    per = len(payloads[0]) // 2
    sums = arr.reshape(len(payloads), per).sum(axis=1, dtype=np.uint64)
    return [int(s & 0xFFFF) for s in sums]


def pack_blocks(payloads: list[bytes], is_last_flags: list[bool]) -> list[bytes]:
    """Batch version of pack_block, used by the fast path."""
    bodies = []
    for payload, is_last in zip(payloads, is_last_flags):
        size_and_end = len(payload) | (0x8000 if is_last else 0)
        body = struct.pack("<H", size_and_end) + payload
        bodies.append(body + b"\xff" * (BLOCK - BODY_HEADER - len(payload)))
    sums = _sum16_batch(bodies)
    return [struct.pack("<H", s) + b for s, b in zip(sums, bodies)]


def pack_block(payload: bytes, is_last: bool) -> bytes:
    """Prepend the block header and pad to 1024 bytes (fwtool's packBlock)."""
    size_and_end = len(payload) | (0x8000 if is_last else 0)
    body = struct.pack("<H", size_and_end) + payload
    body += b"\xff" * (BLOCK - BODY_HEADER - len(payload))
    return struct.pack("<H", _sum16(body)) + body


class FdatEncrypter:
    """Encrypts a plaintext FDAT body into the on-disk block stream."""

    def __init__(self, iv: bytes):
        if len(iv) != 16:
            raise ValueError("IV must be 16 bytes")
        self.iv = iv
        self.ecb = Cipher(algorithms.AES(constants.key_aes), modes.ECB()).encryptor()
        self.cbc = Cipher(
            algorithms.AES(constants.key_cxd90057_k8), modes.CBC(iv)
        ).encryptor()

    def encrypt_block(self, block: bytes, first: bool) -> bytes:
        if len(block) != BLOCK:
            raise ValueError("block must be 1024 bytes")
        if first:
            head = self.ecb.update(block[:512])
            tail = self.cbc.update(block[512:])
            return head + tail
        return self.cbc.update(block)

    def encrypt_body(self, plaintext: bytes) -> bytes:
        out = bytearray()
        pos = 0
        n = len(plaintext)
        # fwtool reads 1020-byte chunks and marks the final one with 0x8000.
        while pos < n:
            chunk = plaintext[pos:pos + PAYLOAD]
            pos += len(chunk)
            is_last = pos >= n
            packed = pack_block(chunk, is_last)
            out += self.encrypt_block(packed, first=(len(out) == 0))
        if n == 0:
            out += self.encrypt_block(pack_block(b"", True), first=True)
        return bytes(out)


class FdatStreamEncrypter:
    """Streaming FDAT encrypter: 750 MB cannot be held in memory.

    Reads plaintext in batches of payload chunks, packs each chunk into a
    1024-byte block (numpy-vectorised sum16), and pushes the packed blocks
    through the AES pipeline. The CBC chain is carried across batches by a
    single CBC encryptor instance, which is exactly equivalent to calling
    encrypt_block() per block because every batch is a whole number of blocks.
    """

    BATCH_BLOCKS = 4096

    def __init__(self, iv: bytes, batch_blocks: int | None = None):
        if len(iv) != 16:
            raise ValueError("IV must be 16 bytes")
        self.iv = iv
        self.batch_blocks = batch_blocks or self.BATCH_BLOCKS
        self.ecb = Cipher(algorithms.AES(constants.key_aes), modes.ECB()).encryptor()
        self.cbc = Cipher(
            algorithms.AES(constants.key_cxd90057_k8), modes.CBC(iv)
        ).encryptor()
        self.blocks_done = 0
        self.first_batch = True

    def encrypt_stream(self, src, dst, total_size: int) -> int:
        """Encrypt exactly total_size plaintext bytes. Returns bytes written."""
        np = _numpy()
        batch_payload = self.batch_blocks * PAYLOAD
        written = 0
        remaining = total_size
        while remaining > 0:
            take = min(batch_payload, remaining)
            chunk = src.read(take)
            if len(chunk) != take:
                raise IOError(
                    "short read: wanted %d got %d (plaintext truncated?)"
                    % (take, len(chunk))
                )
            remaining -= take
            # split into 1020-byte payloads; the final payload of the whole
            # stream is the only short one
            is_final_batch = remaining == 0
            if len(chunk) % PAYLOAD == 0 and is_final_batch:
                # exact multiple: last chunk is full-size and flagged last
                n = len(chunk) // PAYLOAD
                payloads = np.frombuffer(chunk, dtype=np.uint8).reshape(n, PAYLOAD)
                packed = self._pack_batch(n, payloads, last_index=n - 1)
            elif is_final_batch:
                n = len(chunk) // PAYLOAD + 1
                tail = len(chunk) % PAYLOAD
                arr = np.zeros((n, PAYLOAD), dtype=np.uint8)
                arr[:n - 1] = np.frombuffer(chunk[:len(chunk) - tail],
                                            dtype=np.uint8).reshape(n - 1, PAYLOAD)
                arr[n - 1, :tail] = np.frombuffer(chunk[len(chunk) - tail:],
                                                  dtype=np.uint8)
                packed = self._pack_batch(n, arr, last_index=n - 1,
                                          sizes=[PAYLOAD] * (n - 1) + [tail])
            else:
                n = len(chunk) // PAYLOAD
                payloads = np.frombuffer(chunk, dtype=np.uint8).reshape(n, PAYLOAD)
                packed = self._pack_batch(n, payloads, last_index=None)
            if self.first_batch:
                out = self.ecb.update(bytes(packed[:512])) + \
                      self.cbc.update(bytes(packed[512:]))
                self.first_batch = False
            else:
                out = self.cbc.update(bytes(packed))
            dst.write(out)
            written += len(out)
            self.blocks_done += n
        return written

    def _pack_batch(self, n, payloads, last_index, sizes=None):
        """Pack n payloads into n 1024-byte blocks as one contiguous buffer.

        Block layout: [0:2] sum16, [2:4] sizeAndEnd (little endian), [4:] payload,
        padded with 0xff. sum16 covers bytes [2:1024], which the reference
        pack_block computes with the sum field still zeroed.
        """
        np = _numpy()
        buf = np.full((n, BLOCK), 0xFF, dtype=np.uint8)
        buf[:, 4:] = payloads
        # a short final payload is padded with 0xff, not with the caller's zeros
        if sizes is not None:
            for i, sz in enumerate(sizes):
                if sz < PAYLOAD:
                    buf[i, 4 + sz:] = 0xFF
        # zero the header (both the sum field and the sizeAndEnd field)
        buf[:, 0:4] = 0
        sae = np.array(sizes, dtype=np.uint16) if sizes is not None \
            else np.full(n, PAYLOAD, dtype=np.uint16)
        if last_index is not None:
            sae[last_index] |= 0x8000
        # explicit little-endian split; avoids depending on host byte order
        buf[:, 2] = (sae & 0xFF).astype(np.uint8)
        buf[:, 3] = (sae >> 8).astype(np.uint8)
        words = buf.view(np.uint16).reshape(n, BLOCK // 2)
        sums = (words.sum(axis=1, dtype=np.uint64) & 0xFFFF).astype(np.uint16)
        buf[:, 0] = (sums & 0xFF).astype(np.uint8)
        buf[:, 1] = (sums >> 8).astype(np.uint8)
        return buf.reshape(-1)


def _numpy():
    import numpy as np
    return np


def encrypt_file_stream(src_path, dst_path, iv: bytes, total_size: int,
                        batch_blocks: int | None = None) -> int:
    """Convenience wrapper: encrypt src_path (total_size bytes) into dst_path."""
    enc = FdatStreamEncrypter(iv, batch_blocks)
    with open(src_path, "rb") as s, open(dst_path, "wb") as d:
        return enc.encrypt_stream(s, d, total_size)


def decrypt_body(encrypted: bytes, iv: bytes) -> bytes:
    """Reference decryptor using the same primitives, to self-check."""
    ecb = Cipher(algorithms.AES(constants.key_aes), modes.ECB()).decryptor()
    cbc = Cipher(algorithms.AES(constants.key_cxd90057_k8), modes.CBC(iv)).decryptor()
    out = bytearray()
    for i in range(0, len(encrypted), BLOCK):
        blk = encrypted[i:i + BLOCK]
        if i == 0:
            dec = ecb.update(blk[:512]) + cbc.update(blk[512:])
        else:
            dec = cbc.update(blk)
        out += dec
    # strip the per-block headers
    plain = bytearray()
    for i in range(0, len(out), BLOCK):
        blk = out[i:i + BLOCK]
        if len(blk) < BODY_HEADER:
            break
        size_and_end = struct.unpack_from("<H", blk, 2)[0]
        size = size_and_end & 0x7FFF
        plain += blk[BODY_HEADER:BODY_HEADER + size]
    return bytes(plain)


def load_encrypted_payload(dat_path: Path):
    """Return (body, iv, trailing) from the FDAT chunk of a .DAT file."""
    with dat_path.open("rb") as f:
        container = datmod.readDat(f)
        f.seek(container.firmwareData.offset)
        blob = f.read(container.firmwareData.size)
    if len(blob) < TAIL:
        raise ValueError("FDAT chunk too small")
    body = blob[:-TAIL]
    iv = blob[-TAIL:-TAIL + 16]
    trailing = blob[-256:]
    return body, iv, trailing


def roundtrip(dat_path: Path) -> int:
    print(f"input: {dat_path}")
    body, iv, trailing = load_encrypted_payload(dat_path)
    print(f"  fdAT body : {len(body)} bytes")
    print(f"  IV        : {iv.hex()}")
    print(f"  trailing  : 256 bytes, all-zero={trailing == bytes(256)}")

    plain = decrypt_body(body, iv)
    print(f"  decrypted : {len(plain)} bytes")

    enc = FdatEncrypter(iv)
    re_body = enc.encrypt_body(plain)
    print(f"  re-encrypt: {len(re_body)} bytes")

    if len(re_body) != len(body):
        print(f"  LENGTH MISMATCH {len(re_body)} vs {len(body)}")
        return 1

    if re_body == body:
        print("  ROUND-TRIP: identical to the original encrypted body")
        # confirm our decryptor agrees too
        if decrypt_body(re_body, iv) == plain:
            print("  self-check decrypt: OK")
            return 0
        print("  self-check decrypt: FAILED")
        return 1

    diff = sum(1 for a, b in zip(re_body, body) if a != b)
    first = next(i for i, (a, b) in enumerate(zip(re_body, body)) if a != b)
    print(f"  ROUND-TRIP: {diff} differing bytes, first at 0x{first:x}")
    return 1


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, target = sys.argv[1], Path(sys.argv[2])
    if cmd == "roundtrip":
        return roundtrip(target)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
