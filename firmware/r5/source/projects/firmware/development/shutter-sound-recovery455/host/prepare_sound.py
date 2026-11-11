#!/usr/bin/env python3
"""Prepare/inspect R5 4.41 offline sound packs using only Python's stdlib.

Conversion compiles the bundled unchanged integer C encoder into a temporary
executable; inspection needs no compiler. No camera access or package install.
"""
import argparse
from contextlib import AbstractContextManager
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

MAGIC = b"R5SNDF0\0"
VERSION, HEADER_BYTES, RATE, STEPS = 1, 416, 24000, 10
MAX_WAV_BYTES, MAX_FRAMES, MAX_ENCODED = 1024 * 1024, 48000, 49568
MAX_PACK_BYTES = HEADER_BYTES + STEPS * MAX_ENCODED
ENCODER_DIR = Path(__file__).resolve().parent / "encoder"
FORMAT = "R5SNDF0/v1"


class SoundError(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_limited(path, maximum):
    path = Path(path)
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise SoundError("file exceeds {} bytes: {}".format(maximum, path))
    return data


def inspect_bytes(data):
    """Fail closed over all header fields, exact length and ten payloads."""
    if len(data) < HEADER_BYTES or len(data) > MAX_PACK_BYTES:
        raise SoundError("R5S size outside allowed bounds")
    if data[:8] != MAGIC:
        raise SoundError("invalid R5S magic")
    version, header, total, rate, frames, encoded, steps, flags = struct.unpack_from("<8I", data, 8)
    if (version, header, rate, steps, flags) != (VERSION, HEADER_BYTES, RATE, STEPS, 0):
        raise SoundError("unsupported R5S version/header/rate/steps/flags")
    if not 1 <= frames <= MAX_FRAMES:
        raise SoundError("R5S frame count outside 1..48000")
    if encoded != ((frames + 30) // 31) * 32 or encoded > MAX_ENCODED:
        raise SoundError("R5S encoded size does not match frame count")
    if total != HEADER_BYTES + STEPS * encoded or len(data) != total:
        raise SoundError("R5S total size mismatch or trailing bytes")
    if any(data[76:96]):
        raise SoundError("R5S reserved bytes must be zero")
    saved_crc = struct.unpack_from("<I", data, 72)[0]
    canonical_header = bytearray(data[:HEADER_BYTES])
    canonical_header[72:76] = bytes(4)
    if zlib.crc32(canonical_header) & 0xffffffff != saved_crc:
        raise SoundError("R5S header CRC32 mismatch")
    payloads = []
    for index in range(STEPS):
        start = HEADER_BYTES + index * encoded
        payload = data[start:start + encoded]
        digest = hashlib.sha256(payload).digest()
        if digest != data[96 + index * 32:128 + index * 32]:
            raise SoundError("R5S payload SHA256 mismatch at step {}".format(index + 1))
        if any(payload[block] > 7 for block in range(0, encoded, 32)):
            raise SoundError("R5S invalid F0 exponent at step {}".format(index + 1))
        remaining = frames % 31
        if remaining and any(payload[-32 + 1 + remaining:]):
            raise SoundError("R5S nonzero F0 padding at step {}".format(index + 1))
        payloads.append(dict(step=index + 1, percent=(index + 1) * 10,
                             bytes=encoded, sha256=digest.hex()))
    header_sha256 = sha256(data[:HEADER_BYTES])
    return dict(format=FORMAT, version=version, bytes=total, sample_rate=rate,
                pcm_frames=frames, duration_seconds=frames / rate,
                encoded_bytes_per_step=encoded, steps=steps,
                source_wav_sha256=data[40:72].hex(), header_crc32="{:08x}".format(saved_crc),
                sha256=sha256(data), header_sha256=header_sha256,
                catalog_identity=dict(algorithm="sha256", scope="first_416_bytes", value=header_sha256,
                                      purpose="camera catalog e.sha and internal R5SN filename; header commits all ten payload hashes"),
                payloads=payloads, guard_bytes_stored=0)


def inspect_file(path):
    result = inspect_bytes(read_limited(path, MAX_PACK_BYTES))
    result["path"] = str(Path(path).resolve())
    return result


def choose_compiler(explicit=None):
    # --cc is one executable path (including Windows paths with spaces).
    # Build flags are fixed; no shell is involved.
    choices = [explicit] if explicit else ([os.environ["CC"]] if os.environ.get("CC") else []) + ["clang", "gcc", "cc"]
    for item in choices:
        resolved = shutil.which(item)
        if resolved:
            return resolved
    raise SoundError("C compiler not found; install/use an existing clang or gcc, or pass --cc PATH (inspect needs none)")


class NativeEncoder(AbstractContextManager):
    def __init__(self, compiler=None, encoder_dir=ENCODER_DIR):
        self.compiler = choose_compiler(compiler)
        self.encoder_dir = Path(encoder_dir).resolve()
        self.temporary = None

    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="r5sound-encoder-")
        self.executable = Path(self.temporary.name) / ("r5encode.exe" if os.name == "nt" else "r5encode")
        sources = [self.encoder_dir / name for name in ("encode_main.c", "sound_parse.c", "sound_convert.c")]
        command = [self.compiler, "-O2", "-std=c11", "-fno-builtin", "-I", str(self.encoder_dir)]
        command.extend(str(path) for path in sources)
        command.extend(["-o", str(self.executable)])
        try:
            built = subprocess.run(command, capture_output=True, timeout=120)
            if built.returncode:
                raise SoundError("host encoder compile failed: " + built.stderr.decode("utf-8", "replace")[-6000:])
            identity = subprocess.run([self.compiler, "--version"], capture_output=True, timeout=15)
            self.compiler_identity = identity.stdout.decode("utf-8", "replace").splitlines()[0]
            return self
        except BaseException:
            self.temporary.cleanup()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        if self.temporary:
            self.temporary.cleanup()

    def convert(self, wav):
        if not 12 <= len(wav) <= MAX_WAV_BYTES:
            raise SoundError("WAV must be 12..1048576 bytes")
        completed = subprocess.run([str(self.executable)], input=wav, capture_output=True, timeout=180)
        if completed.returncode:
            raise SoundError(completed.stderr.decode("utf-8", "replace").strip() or "host encoder rejected WAV")
        raw = completed.stdout
        if len(raw) < 56 or raw[:8] != b"R5ENC01\0":
            raise SoundError("invalid host encoder reply")
        names = ("channels", "sample_rate", "bits_per_sample", "block_align", "data_offset", "data_bytes",
                 "source_frames", "pcm_frames", "encoded_bytes", "padded_frames", "source_peak", "gain_denominator")
        info = dict(zip(names, struct.unpack_from("<12I", raw, 8)))
        frames, encoded = info["pcm_frames"], info["encoded_bytes"]
        if not 1 <= frames <= MAX_FRAMES or encoded != ((frames + 30) // 31) * 32 or encoded > MAX_ENCODED:
            raise SoundError("host encoder returned out-of-range dimensions")
        if len(raw) != 56 + STEPS * encoded:
            raise SoundError("host encoder payload length mismatch")
        header = bytearray(HEADER_BYTES)
        header[:8] = MAGIC
        total = HEADER_BYTES + STEPS * encoded
        struct.pack_into("<8I", header, 8, VERSION, HEADER_BYTES, total, RATE, frames, encoded, STEPS, 0)
        header[40:72] = hashlib.sha256(wav).digest()
        payload = raw[56:]
        for index in range(STEPS):
            header[96 + index * 32:128 + index * 32] = hashlib.sha256(payload[index * encoded:(index + 1) * encoded]).digest()
        struct.pack_into("<I", header, 72, zlib.crc32(header) & 0xffffffff)
        package = bytes(header) + payload
        report = inspect_bytes(package)
        report.update(source_wav_bytes=len(wav), source_format=info, compiler=self.compiler_identity)
        return package, report


def save_output(path, data, overwrite=False):
    """Publish a fully validated file; default exclusive link prevents races."""
    path = Path(path)
    if not path.parent.is_dir():
        raise SoundError("output directory does not exist: " + str(path.parent))
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="." + path.name + "-", suffix=".tmp", dir=str(path.parent), delete=False) as stream:
            temporary_path = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(str(temporary_path), str(path))
        else:
            try:
                os.link(str(temporary_path), str(path))
            except FileExistsError:
                raise
            except OSError:
                # FAT/exFAT SD cards do not support hard links. Exclusive
                # creation still refuses an existing file, including races.
                created = False
                try:
                    with path.open("xb") as stream:
                        created = True
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                except BaseException:
                    if created:
                        path.unlink()
                    raise
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def convert_file(input_path, output_path=None, overwrite=False, compiler=None):
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path.with_suffix(".R5S")
    if input_path.suffix.lower() != ".wav":
        raise SoundError("input must be a PCM WAV file; MP3 decoding is not supported")
    if output_path.suffix.lower() != ".r5s":
        raise SoundError("output filename must end in .R5S")
    if output_path.resolve() == input_path.resolve():
        raise SoundError("output cannot replace the source WAV")
    if output_path.exists() and not overwrite:
        raise SoundError("output already exists; use a new path or explicit --force")
    wav = read_limited(input_path, MAX_WAV_BYTES)
    with NativeEncoder(compiler) as encoder:
        package, report = encoder.convert(wav)
    save_output(output_path, package, overwrite)
    report.update(input=str(input_path.resolve()), output=str(output_path.resolve()), passed=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    convert = commands.add_parser("convert", help="PCM WAV -> ten-step .R5S sound pack")
    convert.add_argument("input", type=Path)
    convert.add_argument("-o", "--output", type=Path, help="default: input stem plus .R5S")
    convert.add_argument("--cc", help="existing clang/gcc executable path")
    convert.add_argument("--force", action="store_true", help="explicitly replace an existing .R5S output")
    inspect = commands.add_parser("inspect", help="validate a pack and print JSON; no compiler needed")
    inspect.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "convert":
            report = convert_file(args.input, args.output, args.force, args.cc)
        else:
            report = inspect_file(args.input)
            report["passed"] = True
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, SoundError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(passed=False, error=str(error)), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
