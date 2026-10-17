#!/usr/bin/env python3
"""Integrate corrected components without using the obsolete patch manifest.

Derives exact component byte differences, inserts them through ext2 blocks and
FAT clusters, rebuilds the archive/package, then independently decrypts and
checks every archive member. No camera I/O or execution of firmware.
"""
from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit('Historical reference/helper only; standalone execution is disabled. See PUBLICATION.md.')

import argparse
import binascii
import hashlib
import io
import json
import mmap
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "vendor/audit-python"), str(ROOT / "tools"),
               str(ROOT / "vendor/fwtool.py-a7iv")]
from Cryptodome.Cipher import AES
from ext2read import Ext2
from patch_images import Fat12, SHA
from apply_fl2_fl3_cn2_property import NAME as BACKUP_NAME, BASELINE as CN2_BASELINE, verify as verify_cn2_backup
from fwtool.sony import constants, dat
from fwtool.sony.fdat import FdatHeader
from fwtool.io import FilePart
from fwtool.util import crc32
from rebuild_tar import REPLACE, SUM_UPDATES

BUILD = ROOT / "build_fl2_fl3_20261014_cn2_slotfix"
OLD = ROOT / "build_fl2_fl3_20261012"
PACKAGE = "BODYDATA_R5_CN2_FL2_FL3_SLOTFIX_RESEARCH.DAT"
CHUNK = 4 * 1024 * 1024
SLOTFIX_COMPONENTS = {
    "appFw.so": "ea49741c9d918c861993f2c748099e86f3f4e49cce6acf2003aa1292defd2d4b",
    "cpapp-b.bin": "32aa9882dee918a7367d0f33b6dd50cc6c958f0135f8560956a0d5e32f701cd5",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_file(path):
    with Path(path).open("rb") as f:
        return digest_stream(f)


def digest_stream(f):
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(CHUNK), b""):
        h.update(chunk)
    return h.hexdigest()


def diff_runs(old, new):
    """Return exact unequal-byte spans; equality checks skip most large files."""
    require(len(old) == len(new), "component/image size changed")
    out = []
    for start in range(0, len(old), CHUNK):
        a, b = old[start:start + CHUNK], new[start:start + CHUNK]
        if a == b:
            continue
        i = 0
        while i < len(a):
            if a[i] == b[i]:
                i += 1
                continue
            end = i + 1
            while end < len(a) and a[end] != b[end]:
                end += 1
            lo, hi = start + i, start + end
            if out and out[-1][1] == lo:
                out[-1] = (out[-1][0], hi)
            else:
                out.append((lo, hi))
            i = end
    return out


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


def integrate_image(build, component, image_name):
    baseline = build / "baseline" / image_name
    corrected = (build / "patched" / component).read_bytes()
    original = (build / "baseline" / component).read_bytes()
    require(hashlib.sha256(original).hexdigest() == SHA[component],
            f"wrong baseline identity for {component}")
    embedded, offsets, unit_size, meta = geometry(baseline, component)
    require(embedded == original, f"embedded baseline {component} mismatch")
    runs = diff_runs(original, corrected)
    require(runs, f"{component} has no corrections")
    dst = build / "patched" / image_name
    shutil.copyfile(baseline, dst)
    physical_expected = {}
    slices = []
    with dst.open("r+b") as f:
        for lo, hi in runs:
            p = lo
            while p < hi:
                # A logical patch may cross a noncontiguous block boundary.
                count = min(hi - p, unit_size - p % unit_size)
                physical = offsets[p // unit_size] + p % unit_size
                require(physical + count <= dst.stat().st_size,
                        "physical patch outside partition")
                payload = corrected[p:p + count]
                f.seek(physical)
                f.write(payload)
                for j, value in enumerate(payload):
                    require(physical + j not in physical_expected,
                            "overlapping physical filesystem blocks")
                    physical_expected[physical + j] = value
                slices.append({"logical_offset": hex(p),
                               "image_offset": hex(physical), "length": count})
                p += count
        f.flush()
        os.fsync(f.fileno())
    extracted, after_offsets, after_unit, _ = geometry(dst, component)
    require(extracted == corrected, f"full embedded readback {component} differs")
    require(after_offsets == offsets and after_unit == unit_size,
            "filesystem geometry changed")
    with baseline.open("rb") as a, dst.open("rb") as b:
        with mmap.mmap(a.fileno(), 0, access=mmap.ACCESS_READ) as ma, \
                mmap.mmap(b.fileno(), 0, access=mmap.ACCESS_READ) as mb:
            image_runs = diff_runs(ma, mb)
            physical_actual = {i: mb[i] for lo, hi in image_runs for i in range(lo, hi)}
    require(physical_actual == physical_expected,
            "partition changes extend beyond exact component differences")
    return dict(meta, component=component, baseline_sha256=digest_file(baseline),
                corrected_component_sha256=hashlib.sha256(corrected).hexdigest(),
                image_sha256=digest_file(dst), changed_bytes=len(physical_actual),
                component_runs=[dict(offset=hex(lo), length=hi-lo,
                                     before=original[lo:hi].hex(),
                                     after=corrected[lo:hi].hex()) for lo, hi in runs],
                physical_slices=slices, readback_equal=True,
                exact_partition_diff_verified=True)


def run_tool(name, build, extra_args=()):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "vendor/audit-python")
    log = build / "evidence" / (Path(name).stem + ".log")
    with log.open("w") as f:
        result = subprocess.run([sys.executable, str(ROOT / "tools" / name), str(build), *extra_args],
                                env=env, stdout=f, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{name} failed; see {log}")


def verify_embedded_partition(build, image, component):
    """Check extracted package partition against original physical byte layout."""
    baseline = build / "baseline" / image.name
    original, offsets, unit_size, _ = geometry(baseline, component)
    corrected = (build / "patched" / component).read_bytes()
    embedded, new_offsets, new_unit, _ = geometry(image, component)
    require(embedded == corrected, f"package embedded {component} differs")
    require(new_offsets == offsets and new_unit == unit_size,
            "package filesystem geometry changed")
    expected = {}
    for lo, hi in diff_runs(original, corrected):
        for pos in range(lo, hi):
            physical = offsets[pos // unit_size] + pos % unit_size
            require(physical not in expected, "overlapping physical blocks")
            expected[physical] = corrected[pos]
    with baseline.open("rb") as a, image.open("rb") as b:
        with mmap.mmap(a.fileno(), 0, access=mmap.ACCESS_READ) as ma, \
                mmap.mmap(b.fileno(), 0, access=mmap.ACCESS_READ) as mb:
            actual = {pos: mb[pos] for lo, hi in diff_runs(ma, mb)
                      for pos in range(lo, hi)}
    require(actual == expected, "package partition changes exceed component plan")
    return {"component_sha256": hashlib.sha256(embedded).hexdigest(),
            "partition_sha256": digest_file(image),
            "exact_partition_diff_verified": True, "changed_bytes": len(actual)}


def independent_package_verification(build):
    """Different crypto library from encryptor; check every block and member."""
    report = {}
    package = build / "package" / PACKAGE
    verified_fdat = build / "work/independently_decrypted.fdat"
    donor_plain = ROOT / "unpacked/r5/firmware.fdat"
    donor_tar = ROOT / "unpacked/r5/firmware.tar"
    corrected_tar = build / "patched/firmware.tar"
    with donor_plain.open("rb") as f:
        header = FdatHeader.unpack(f)
    with package.open("rb") as f, (ROOT / "BODYDATA.DAT").open("rb") as original:
        container, baseline = dat.readDat(f), dat.readDat(original)
        chunks, total_size = dat.readChunks(f)
        original_chunks, original_size = dat.readChunks(original)
        require(total_size == package.stat().st_size == original_size,
                "DAT total size changed or trailing bytes")
        require([(kind, part.size) for kind, part in chunks] ==
                [(kind, part.size) for kind, part in original_chunks],
                "DAT chunk geometry changed")
        for (kind, part), (_, oldpart) in zip(chunks, original_chunks):
            if kind not in (b"FDAT", b"DEND"):
                require(part.read() == oldpart.read(), "non-FDAT chunk changed")
        body_size = container.firmwareData.size - 272
        f.seek(container.firmwareData.offset + body_size)
        tail = f.read(272)
        original.seek(baseline.firmwareData.offset + baseline.firmwareData.size - 272)
        require(tail == original.read(272), "IV/trailer changed")
        ecb = AES.new(constants.key_aes, AES.MODE_ECB)
        cbc = AES.new(constants.key_cxd90057_k8, AES.MODE_CBC, tail[:16])
        f.seek(container.firmwareData.offset)
        count, offset = 0, 0
        with verified_fdat.open("wb") as output, donor_plain.open("rb") as prefix, \
                corrected_tar.open("rb") as archive:
            while count * 1024 < body_size:
                encrypted = f.read(min(CHUNK, body_size - count * 1024))
                require(len(encrypted) % 1024 == 0, "truncated ciphertext")
                decoded = (ecb.decrypt(encrypted[:512]) + cbc.decrypt(encrypted[512:])
                           if count == 0 else cbc.decrypt(encrypted))
                plain = bytearray()
                for pos in range(0, len(decoded), 1024):
                    block = decoded[pos:pos + 1024]
                    words = struct.unpack("<512H", block)
                    size, last = words[1] & 0x7fff, bool(words[1] & 0x8000)
                    require(sum(words[1:]) & 65535 == words[0],
                            f"FDAT block {count} sum16 mismatch")
                    require(last == (count == body_size // 1024 - 1), "wrong end flag")
                    require(size <= 1020 and (size == 1020 or last), "wrong payload size")
                    require(block[4 + size:] == b"\xff" * (1020 - size),
                            "FDAT last block padding mismatch")
                    plain.extend(block[4:4 + size])
                    count += 1
                take = min(len(plain), max(0, header.firmwareOffset - offset))
                require(plain[:take] == prefix.read(take), "FDAT prefix differs")
                require(plain[take:] == archive.read(len(plain) - take),
                        "decrypted archive differs")
                output.write(plain)
                offset += len(plain)
            require(not archive.read(1), "archive suffix not decrypted")
        require(offset == donor_plain.stat().st_size, "plaintext length mismatch")
    with verified_fdat.open("rb") as f:
        new_header = FdatHeader.unpack(f)
        require(new_header == header, "FDAT header metadata changed")
        require(crc32(FilePart(f, 12, FdatHeader.size - 12)) == new_header.checksum,
                "FDAT header CRC mismatch")
    report.update(outer_dend_crc_valid=True, non_fdat_dat_chunks_equal=True,
                  original_iv_trailer_equal=True, decrypted_blocks=count,
                  block_checksums_endflags_padding_valid=True,
                  plaintext_bytes=offset, plaintext_sha256=digest_file(verified_fdat),
                  full_plaintext_matches_original_prefix_and_corrected_archive=True)
    with verified_fdat.open("rb") as fd:
        region = FilePart(fd, header.firmwareOffset, header.firmwareSize)
        with tarfile.open(fileobj=region, mode="r:") as actual, \
                tarfile.open(donor_tar, "r:") as baseline:
            am, bm = actual.getmembers(), baseline.getmembers()
            require(len(am) == len(bm), "archive member count changed")
            changed, records = [], []
            for a, b in zip(am, bm):
                require(a.get_info() == b.get_info() and
                        a.offset == b.offset and a.offset_data == b.offset_data and
                        a.pax_headers == b.pax_headers,
                        f"tar metadata changed: {a.name}")
                hnew = digest_stream(actual.extractfile(a)) if a.isfile() else None
                hold = digest_stream(baseline.extractfile(b)) if b.isfile() else None
                if hnew != hold:
                    changed.append(a.name)
                records.append({"member": a.name, "size": a.size,
                                "baseline_sha256": hold, "output_sha256": hnew,
                                "changed": hnew != hold})
            require(set(changed) == set(REPLACE) | set(SUM_UPDATES),
                    f"unexpected changed archive members: {changed}")
            for member, local in REPLACE.items():
                local_path = build / "patched" / local
                if local_path.exists():
                    require(digest_stream(actual.extractfile(member)) ==
                            digest_file(local_path), "archive local replacement mismatch")
                else:
                    require(local in ("nflasha15", "nflasha8"),
                            "required non-partition replacement missing")
                    # Cleaned partition copies are verified from the DAT below,
                    # including every physical difference against the original.
            checked = []
            for sum_name, prefix in [("0111_backup_sum/backup.sum", "0110_backup/"),
                                     ("0701_part_image_sum/part_image.sum", "0700_part_image/")]:
                rows = actual.extractfile(sum_name).read().decode("ascii").splitlines()
                for row in rows:
                    parts = row.split(",")
                    if len(parts) < 11 or parts[0] != "0":
                        continue
                    name = prefix + parts[10]
                    member = actual.getmember(name)
                    c = 0
                    with actual.extractfile(member) as stream:
                        for chunk in iter(lambda: stream.read(CHUNK), b""):
                            c = binascii.crc32(chunk, c)
                    require(int(parts[1], 16) == c & 0xffffffff, f"CRC differs: {name}")
                    require(int(parts[2], 16) == member.size, f"sum size differs: {name}")
                    checked.append(name)
            # Extract from the independently decrypted DAT, not local build images.
            partition_checks = {}
            for component, member in [("appFw.so", "0700_part_image/dev/nflasha15"),
                                      ("cpapp-b.bin", "0700_part_image/dev/nflasha8")]:
                image = build / "work" / Path(member).name
                with actual.extractfile(member) as src, image.open("wb") as dst:
                    shutil.copyfileobj(src, dst, CHUNK)
                verification = verify_embedded_partition(build, image, component)
                partition_checks[member] = verification
                report["embedded_" + component + "_sha256"] = verification["component_sha256"]
                image.unlink()
    report.update(archive_member_count=len(records), archive_members=records,
                  package_partition_byte_verification=partition_checks,
                  exact_five_member_scope_verified=True, changed_members=changed,
                  mainland_china_only=True, other_region_backups_unchanged=True,
                  checksum_entries_checked=checked,
                  unchanged_tar_metadata_verified=True,
                  package_sha256=digest_file(package), package_size=package.stat().st_size,
                  verified_archive_sha256=digest_file(corrected_tar),
                  limitations=["No camera I/O, boot, capture, or live property loading tested",
                               "Only original R5 CX89201_CN2 backup changed; current camera region/runtime property delivery not observed"])
    verified_fdat.unlink()
    return report


def main():
    global PACKAGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=BUILD)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--slot-types", action="store_true", default=True,
                        help="CN2 slot-type correction is required (flag retained for existing commands)")
    args = parser.parse_args()
    if args.slot_types:
        PACKAGE = 'BODYDATA_R5_CN2_FL2_FL3_SLOTFIX_RESEARCH.DAT'
    build = args.build.resolve()
    require(build != OLD, "must preserve previous build")
    for folder in ("baseline", "patched", "evidence", "work", "package"):
        (build / folder).mkdir(parents=True, exist_ok=True)
    for filename in ("appFw.so", "cpapp-b.bin", "nflasha15", "nflasha8"):
        dst = build / "baseline" / filename
        if not dst.exists():
            dst.symlink_to(OLD / "baseline" / filename)
    cn2_reference = build / "baseline" / BACKUP_NAME
    if not cn2_reference.exists():
        cn2_reference.symlink_to(CN2_BASELINE)
    if args.prepare_only:
        print("Build directories and read-only baseline references prepared:", build)
        return
    slotfix_identities = {}
    if args.slot_types:
        for component, expected in SLOTFIX_COMPONENTS.items():
            actual = digest_file(build / "patched" / component)
            require(actual == expected,
                    f"slot-types requires the validated matching {component}")
            slotfix_identities[component] = actual
    if not args.verify_only:
        report = {"images": []}
        for component in ("appFw.so", "cpapp-b.bin"):
            require((build / "patched" / component).exists(), f"await corrected {component}")
        for component, image in (("appFw.so", "nflasha15"), ("cpapp-b.bin", "nflasha8")):
            report["images"].append(integrate_image(build, component, image))
            print("Integrated and verified", component, flush=True)
        backup = build / "patched" / BACKUP_NAME
        if not backup.exists():
            run_tool("apply_fl2_fl3_cn2_property.py", build,
                     ('--slot-types',) if args.slot_types else ())
        report["backup"] = verify_cn2_backup(backup, slot_types=args.slot_types)
        (build / "evidence/integration.json").write_text(json.dumps(report, indent=2) + "\n")
        run_tool("rebuild_tar.py", build)
        (build / "patched/firmware.tar.new").replace(build / "patched/firmware.tar")
        print("Archive rebuilt", flush=True)
        run_tool("build_package.py", build)
        (build / "package/BODYDATA_SELFSIGNED.DAT").replace(build / "package" / PACKAGE)
        package_record = json.loads((build / "evidence/build_package.json").read_text())
        package_record["output"]["path"] = str(build / "package" / PACKAGE)
        (build / "evidence/build_package.json").write_text(json.dumps(package_record, indent=2) + "\n")
        print("DAT built; independently decrypting and checking all archive members", flush=True)
    backup_verification = verify_cn2_backup(build / 'patched' / BACKUP_NAME,
                                            slot_types=args.slot_types)
    verification = independent_package_verification(build)
    verification['backup_property_verification'] = backup_verification
    verification['slotfix_component_identities'] = slotfix_identities
    (build / "evidence/independent_package_verification.json").write_text(
        json.dumps(verification, indent=2) + "\n")
    print(json.dumps({k: verification[k] for k in
                      ("package_sha256", "package_size", "archive_member_count",
                       "exact_five_member_scope_verified", "decrypted_blocks")}, indent=2))


if __name__ == "__main__":
    main()
