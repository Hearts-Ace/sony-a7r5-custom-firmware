#!/usr/bin/env python3
"""Stream a fully verified local 4.65 DAT from the original archive.

Only the final DAT and replacement members are stored. No second complete TAR,
FDAT plaintext or previous custom-firmware archive is created or consumed.
"""
from pathlib import Path
import argparse
import json
import sys
import tarfile

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / 'lib'), str(HERE.parent)]
from image_io import digest_stream, update_sum
from overlay import Overlay
from stock_inputs import identity, load_inputs, save, sha
import package
from freeze_sources import check
from validation465 import load_validation, match_components


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inputs', 'build', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--reference-dat', type=Path, help='Regenerate and compare every output byte to an existing read-only DAT')
    args = parser.parse_args()
    assert __debug__, 'Do not run with python -O'
    check()
    validation = load_validation(HERE.parent / 'validation.lock.json')
    config = load_inputs(args.inputs, signing=True)
    report = json.loads((args.build / 'build.json').read_text())
    match_components(validation, report['components'])
    assert report['passed'] and report['version'] == '4.65'
    assert set(report['partitions']) == {'nflasha3', 'nflasha5', 'nflasha8', 'nflasha15'}
    for name, row in report['partitions'].items():
        assert identity(args.build / 'partitions' / name) == row
    out = args.output.resolve()
    source = HERE.parent
    if out.exists() or out == source or out.is_relative_to(source) or source.is_relative_to(out):
        parser.error('Output must be a new directory outside the source distribution')
    out.mkdir(parents=True)
    evidence, inputs = out / 'evidence', out / 'work' / 'inputs'
    evidence.mkdir()
    inputs.mkdir(parents=True)
    for key, name in {'original_dat': 'original.DAT', 'original_fdat': 'original.fdat',
        'updater': 'updater.img', 'public_key': 'public.pem',
        'sony_public_key': 'sony_public.pem', 'private_key': 'private.pem'}.items():
        (inputs / name).symlink_to(config[key])
    replacements = {'0700_part_image/dev/' + name: args.build / 'partitions' / name
        for name in report['partitions']}
    with tarfile.open(config['original_tar'], 'r:') as archive:
        members = archive.getmembers()
        by_name = {member.name: member for member in members}
        assert len(by_name) == len(members)
        sum_name = '0701_part_image_sum/part_image.sum'
        mapping = {'dev/' + name: args.build / 'partitions' / name for name in report['partitions']}
        text, changes = update_sum(archive.extractfile(sum_name).read().decode('ascii'), mapping,
            {key: path.stat().st_size for key, path in mapping.items()})
        assert len(changes) == 4
        sums = out / 'part_image.sum'
        sums.write_text(text)
        replacements[sum_name] = sums
    ranges = []
    for name, path in sorted(replacements.items(), key=lambda item: by_name[item[0]].offset_data):
        member = by_name[name]
        assert member.isfile() and path.stat().st_size == member.size
        ranges.append((member.offset_data, member.offset_data + member.size, path))
    overlay = Overlay(config['original_tar'], ranges)
    with overlay.open('rb') as stream:
        archive_sha = digest_stream(stream)
    facts = []
    with tarfile.open(config['original_tar'], 'r:') as original, overlay.open('rb') as stream, tarfile.open(fileobj=stream, mode='r:') as result:
        assert [member.get_info() for member in original.getmembers()] == [member.get_info() for member in result.getmembers()]
        for member in members:
            if not member.isfile():
                continue
            before = digest_stream(original.extractfile(member))
            after = digest_stream(result.extractfile(member))
            assert after == (sha(replacements[member.name]) if member.name in replacements else before)
            facts.append(dict(member=member.name, sha256=after, changed_from_stock=before != after))
    archive_receipt = dict(passed=True, output_sha256=archive_sha, changed_members=list(replacements),
        members=facts, original_headers_padding_trailer_preserved=True,
        previous_custom_firmware_input=False,
        factory_defaults_and_backup_sum_unchanged=True)
    expected_changed = {'0700_part_image/dev/' + name for name in ('nflasha3','nflasha5','nflasha8','nflasha15')}
    expected_changed.add('0701_part_image_sum/part_image.sum')
    assert {row['member'] for row in facts if row['changed_from_stock']} == expected_changed
    assert set(replacements) == expected_changed
    save(evidence / 'archive_verification_465.json', archive_receipt)
    package.ROOT = out / 'work'
    package.OUT = out
    package.TAR = overlay
    package.VERSION = '4.65'
    package.TAG = '465'
    package.NAME = 'BODYDATA.DAT'
    package.REFERENCE_DAT = args.reference_dat.expanduser().resolve() if args.reference_dat else None
    package.components = lambda: dict(upstream_commit='086df3b1e33dfa0206553ac2bb003535c58ddb80', components=report['components'])
    original_digest = package.digest_file
    package.digest_file = lambda path: archive_sha if path is overlay else original_digest(path)
    package.build_package()
    receipt = json.loads((out / 'verification.json').read_text())
    status = validation.get('release_status', 'reviewed_offline')
    receipt.update(state=('OFFLINE_SIGNED_UNVERIFIED_CANDIDATE' if status == 'unverified_candidate'
                          else 'OFFLINE_VERIFIED_LOCAL_PACKAGE_CAMERA_UNTESTED'),
        release_status=status,
        open_owner_boundaries=[key for key, gate in validation['owner_handoff'].items() if not gate['passed']],
        source='Original R5 4.00 and reviewed source patches', previous_custom_firmware_input=False,
        exact_five_member_scope_verified=True,
        source_component_hashes=report['components'],
        validation_receipt_sha256=sha(HERE.parent / 'validation.lock.json'),
        factory_defaults_and_backup_sum_unchanged=True,
        device_acceptance_tested=False)
    save(out / 'verification.json', receipt)
    check()
    print(json.dumps(dict(passed=True, version='4.65', output_sha256=receipt['output_sha256'],
        all_plaintext_verified=True, camera_io=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
