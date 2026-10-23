#!/usr/bin/env python3
"""Run the existing 4.23 offline AP/CP replay suite against one AP identity.

Requires the local Unicorn runtime. No device, USB, network, SD, or camera IO.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = CANDIDATE / 'ap/appFw.so'
    cp = CANDIDATE / 'cp/cp423.NONINSTALLABLE.bin'
    identity = sha(ap)
    bound = {path: sha(path) for path in (
        ap, cp, CANDIDATE / 'import/runtime_rx.bin',
        CANDIDATE / 'import/module_audit.json')}
    plans = (
        ('replay_ap_cp423.py', 'ap_cp_data_replay.json', 'dual'),
        ('replay_select_ap_cp423.py', 'ap_cp_select_replay.json', 'dual'),
        ('replay_retained_ap_cp423.py', 'ap_cp_retained_replay.json', 'dual'),
        ('replay_sd423.py', 'sd_replay.json', 'ap'),
        ('replay_sessions423.py', 'ap_session_replay.json', 'module'),
        ('replay_menu_foundation423.py', 'menu_foundation_replay.json', 'module'),
    )
    reports = []
    for source, output, kind in plans:
        assert all(sha(path) == digest for path, digest in bound.items()), 'Replay input changed during suite'
        command = [sys.executable, str(HERE / source)]
        if kind in ('dual', 'ap'):
            command += ['--candidate', str(CANDIDATE), '--output', str(HERE / output)]
        if kind == 'dual':
            command += ['--cp', str(cp)]
        with (HERE / (Path(source).stem + '.log')).open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise SystemExit(f'{source} failed; inspect its adjacent .log')
        data = json.loads((HERE / output).read_text())
        assert data['passed']
        reports.append(dict(source=source, output=output, passed=True,
                            candidate_sha256=data.get('candidate_sha256', data.get('AP_sha256')),
                            cases=data.get('cases'), sha256=sha(HERE / output)))
        print(json.dumps(reports[-1]), flush=True)
    assert all(sha(path) == digest for path, digest in bound.items()), 'Replay input changed during suite'
    inputs = [*HERE.glob('replay_*.py'), HERE / 'cp_bridge423.py',
              HERE / 'test_codec.py', *HERE.glob('test_*.c'), Path(__file__),
              HERE / 'run_host_tests423.py']
    output_names = ('codec_test.json', 'selection_store_test.json',
                    'runtime_test.json', 'runtime_restore_test.json',
                    *(output for _, output, _ in plans))
    outputs = []
    for name in output_names:
        path = HERE / name
        data = json.loads(path.read_text())
        outputs.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path),
                            passed=data['passed'],
                            candidate_sha256=data.get('candidate_sha256', data.get('AP_sha256')),
                            cases=data.get('cases', data.get('scenarios'))))
    inventory = dict(camera_io=False, ap_sha256=identity, cp_sha256=sha(cp),
                     replay_inputs=[dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
                                    for path in sorted(set(inputs))],
                     replay_outputs=outputs,
                     limits=['Host fixtures and bounded CPU replay do not establish actual camera startup, display pixels, ISP, or filesystem power-loss durability.'])
    (HERE / 'replay_inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')


if __name__ == '__main__':
    main()
