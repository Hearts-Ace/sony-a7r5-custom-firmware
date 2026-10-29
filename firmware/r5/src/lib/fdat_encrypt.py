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

from fwtool.sony import constants  # noqa: E402
from fwtool.sony import dat as datmod  # noqa: E402

BLOCK = 1024
BODY_HEADER = 4
PAYLOAD = BLOCK - BODY_HEADER      # 1020
TAIL = 0x110                        # 16 IV + 256 trailing

def _numpy():
    import numpy as np
    return np


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
