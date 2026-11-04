"""R5 six-slot builder: only existing LOOK bytes and bank0 checksums."""
import struct
from filesystem import FatImage, require
from sparse import SIZE, changed_sectors, digest
from bk4 import BK4Bank
SLOTS={0x02cf0b69:10,0x02cf0b6f:11,0x02cf0b93:10,0x02cf0b95:11,0x02cf0b97:10,0x02cf0b99:11}
FILES=('/backup.bin','/backup.bak')
EXPECTED_BANKS=(0,0xef000)

def banks(raw):
    # Check both known banks explicitly. find_banks silently skips bad later
    # banks, which is unsuitable for a live write gate.
    result = [BK4Bank(raw, offset) for offset in EXPECTED_BANKS]
    require(result[0].size <= EXPECTED_BANKS[1], 'Overlapping backup banks')
    require(len(raw) == 2372469, 'Unexpected personal backup size')
    return result


def patch_backup(raw):
    original = banks(raw)
    output = bytearray(raw)
    allowed = set(range(0x20, 0x24))
    slots = {}
    for key, value in SLOTS.items():
        prop = original[0].property(key)
        require(prop.attributes == 0x60 and prop.capacity == len(prop.data) == 1,
                f'Unexpected metadata for {key:08x}')
        require(prop.data in (b'\x00', bytes([value])), f'Unexpected LOOK value for {key:08x}')
        require(prop.file_offset not in allowed, 'Overlapping LOOK properties')
        allowed.add(prop.file_offset)
        output[prop.file_offset] = value
        slots[f'{key:08x}'] = dict(before=prop.data.hex(), after=f'{value:02x}',
                                  file_offset=prop.file_offset)
    checksum = sum(output[:0x20]) + sum(output[0x24:original[0].size])
    struct.pack_into('<I', output, 0x20, checksum)
    output = bytes(output)
    final = banks(output)
    diffs = [i for i, (a, b) in enumerate(zip(raw, output)) if a != b]
    require(set(diffs) <= allowed and len(diffs) <= 10, 'Backup change exceeds six slots and checksum')
    require(raw[original[0].size:] == output[original[0].size:], 'Non-target bank or tail changed')
    for key, value in SLOTS.items():
        require(final[0].property(key).data == bytes([value]), 'Target readback mismatch')
    return output, allowed, dict(slots=slots, changed_file_offsets=diffs,
        before_sha256=digest(raw), after_sha256=digest(output),
        banks_before=[dict(offset=b.offset, bytes=b.size, checksum=b.checksum) for b in original],
        banks_after=[dict(offset=b.offset, bytes=b.size, checksum=b.checksum) for b in final],
        other_bank_and_tail_byte_exact=True)


def build_image(before):
    require(len(before) == SIZE, 'Expected full 20MiB fresh logical settings')
    fs = FatImage(before)
    after = bytearray(before)
    allowed = set()
    records = {}
    for name in FILES:
        old = fs.read(name)
        new, local_allowed, facts = patch_backup(old)
        fs.patch(after, name, new)
        logical = 0
        for offset, length in fs.entries[name]['extents']:
            for i in local_allowed:
                if logical <= i < logical + length:
                    allowed.add(offset + i - logical)
            logical += length
        records[name] = facts
    after = bytes(after)
    diffs = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    require(set(diffs) <= allowed and len(diffs) <= 20, 'Change exceeds six LOOK slots and bank checksums')
    other = FatImage(after)
    require(other.entries == fs.entries, 'FAT layout or directory changed')
    for name, entry in fs.entries.items():
        if not entry['is_directory'] and name not in FILES:
            require(fs.read(name) == other.read(name), 'Unrelated file changed: ' + name)
    sectors = changed_sectors(before, after)
    require(len(sectors) <= 14, 'Unexpectedly broad slot patch')
    return after, dict(scope='Six LOOK bytes in each BACKUP plus first-bank checksums only',
        source_sha256=digest(before), output_sha256=digest(after), files=records,
        changed_bytes=len(diffs), changed_partition_offsets=diffs, changed_sectors=sectors,
        all_BK4_checksums_valid=True, all_other_files_and_filesystem_layout_unchanged=True,
        colour_data_and_updater_unchanged=True, firmware_version_unchanged=True,
        nflasha6_modified=False, camera_io=False)


def diagnostic_snapshot(image):
    """Read slots independently of later-bank validity; never repairs checksums."""
    fs = FatImage(image)
    report = dict(partition_sha256=digest(image), backups={}, updater={})
    for name in FILES:
        raw = fs.read(name)
        item = dict(bytes=len(raw), sha256=digest(raw), banks=[], slots={})
        for offset in EXPECTED_BANKS:
            try:
                bank = BK4Bank(raw, offset)
                item['banks'].append(dict(offset=offset, valid=True, checksum=bank.checksum, bytes=bank.size))
                if offset == 0:
                    for key in SLOTS:
                        prop = bank.property(key)
                        item['slots'][f'{key:08x}'] = dict(value=prop.data.hex(), attrs=prop.attributes,
                                                          bytes=len(prop.data), offset=prop.file_offset)
            except (ValueError, KeyError) as exc:
                item['banks'].append(dict(offset=offset, valid=False, error=repr(exc)))
        report['backups'][name] = item
    for name, entry in fs.entries.items():
        if name.startswith('/updater/') and not entry['is_directory']:
            data = fs.read(name)
            report['updater'][name] = dict(bytes=len(data), sha256=digest(data),
                                          value_hex=data.hex() if len(data) <= 16 else None)
    return report
