"""Validate the offline owner-handoff receipt before source freeze/signing.

Report digests are portable references, not implicit claims that their external
files are present in a source ZIP. An explicitly identified unverified candidate
may retain open owner boundaries, but may not represent them as passed.
"""
from pathlib import Path
import json
import re

GATES = (
    'prepare_outside_settings_lock', 'exact_E4_cookie_handoff', 'live_root',
    'pending_gamma', 'AA_three_routes', 'capture_freeze_clone',
    'successful_pool_return', 'off_control_reclamation',
)
COMPONENTS = {'AP', 'CP', 'AVCAM', 'MPR'}
HEX = re.compile(r'[0-9a-f]{64}')


def load_validation(path):
    receipt = json.loads(Path(path).read_text())
    status = receipt.get('release_status', 'reviewed_offline')
    candidate = status == 'unverified_candidate'
    if not (status in ('reviewed_offline', 'unverified_candidate')
            and receipt.get('passed') is (not candidate)
            and receipt.get('version') == '4.67'
            and receipt.get('offline_only') is True
            and receipt.get('device_acceptance_tested') is False):
        raise ValueError('Require an explicitly classified offline 4.67 validation receipt')
    components = receipt.get('components', {})
    if set(components) != COMPONENTS or any(not isinstance(v, str) or not HEX.fullmatch(v) for v in components.values()):
        raise ValueError('Validation must bind all four exact component SHA256 identities')
    gates = receipt.get('owner_handoff', {})
    reports = receipt.get('reports', [])
    report_ids = set()
    for report in reports:
        if not (isinstance(report, dict) and isinstance(report.get('id'), str)
                and report['id'] and isinstance(report.get('path'), str)
                and report['path'] and not Path(report['path']).is_absolute()
                and HEX.fullmatch(report.get('sha256', ''))):
            raise ValueError('Validation evidence requires unique id, portable path and SHA256')
        if report['id'] in report_ids:
            raise ValueError('Duplicate validation report id')
        report_ids.add(report['id'])
    if not report_ids:
        raise ValueError('Validation receipt has no evidence references')
    for name in GATES:
        gate = gates.get(name)
        documented = (isinstance(gate, dict)
                      and isinstance(gate.get('boundary'), str) and gate['boundary'].strip()
                      and isinstance(gate.get('evidence'), list)
                      and set(gate['evidence']) <= report_ids)
        confirmed = documented and gate.get('passed') is True and gate['evidence']
        open_candidate = (documented and candidate and gate.get('passed') is False
                          and isinstance(gate.get('reason'), str) and gate['reason'].strip())
        if not (confirmed or open_candidate):
            raise ValueError('Unproven or undocumented owner handoff boundary: ' + name)
    if not isinstance(receipt.get('limits'), list) or not receipt['limits']:
        raise ValueError('Validation receipt must preserve fixture/physical-test limitations')
    return receipt


def match_components(receipt, actual):
    if set(actual) != COMPONENTS:
        raise ValueError('Incomplete component identities')
    for key, expected in receipt['components'].items():
        if actual[key]['sha256'] != expected:
            raise ValueError('Output differs from SHA-bound receipt component: ' + key)
