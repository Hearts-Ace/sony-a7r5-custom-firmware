"""Run final 4.22 CP regressions without opening any camera/device.

The AP is deliberately unchanged. These are fresh CP-bound receipts, not copies
of the 4.21 results. Run with the workspace Python and Unicorn outside the macOS
sandbox when its executable mapping is unavailable there.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
CP = HERE / 'cp/cp420-grid.NONINSTALLABLE.bin'
SUITES = {
    'loader': ('cp/replay_loader.py', 'cp/loader_replay.json'),
    'native_color': ('cp/replay_native_color.py', 'cp/native_color_replay.json'),
    'native53': ('cp/replay_b13_native53.py', 'cp/native53_replay.json'),
    'grid': ('cp/replay_grid.py', 'cp/grid_replay.json'),
    'observer_abi': ('cp/replay_observer_abi.py', 'cp/observer_abi_replay.json'),
    'grid_status': ('import/replay_grid420_status.py', 'import/grid_status_replay.json'),
    'gamma_route': ('gamma/replay_final_gamma.py', 'gamma/final_route_replay.json'),
    'same_look_gamma': ('gamma/replay_gamma_updates.py', 'gamma/same_look_gamma_updates.json'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=list(SUITES), action='append')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    csha = digest(CP)
    assert json.loads((HERE / 'cp/build.json').read_text())['candidate_sha256'] == csha
    run_rows = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for name in args.only or SUITES:
        script, receipt = SUITES[name]
        script_sha = digest(HERE / script)
        log = OUT / f'{stamp}_{name}.log'
        with log.open('x') as output:
            result = subprocess.run([sys.executable, str(HERE / script)],
                                    cwd=HERE, env=env, stdout=output,
                                    stderr=subprocess.STDOUT)
        row = dict(name=name, script=script, script_sha256=script_sha,
                   log=str(log.relative_to(HERE)), log_sha256=digest(log),
                   returncode=result.returncode, CP_sha256=csha)
        run_rows.append(row)
        print(name, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
        if result.returncode:
            save(OUT / f'{stamp}_run.json', dict(passed=False, rows=run_rows, CP_sha256=csha))
            print(log.read_text()[-10000:], flush=True)
            return result.returncode
        value = json.loads((HERE / receipt).read_text())
        assert value['passed'] and value.get('CP_sha256', value.get('candidate_sha256')) == csha
        assert digest(CP) == csha, 'CP changed during component regression'
        assert digest(HERE / script) == script_sha, 'Test source changed during component regression'
        save(OUT / f'{name}_binding.json', dict(row, receipt=receipt,
             receipt_sha256=digest(HERE / receipt), passed=True))
    save(OUT / f'{stamp}_run.json', dict(passed=True, rows=run_rows, CP_sha256=csha,
                                       camera_io=False))
    # An --only retry can complete a previously interrupted full run. All eight
    # final receipts must nevertheless exist and be bound to this exact CP.
    rows = []
    for name, (script, receipt) in SUITES.items():
        path = HERE / receipt
        if not path.exists():
            return 0
        value = json.loads(path.read_text())
        if not value.get('passed') or value.get('CP_sha256', value.get('candidate_sha256')) != csha:
            return 0
        binding_path = OUT / f'{name}_binding.json'
        if not binding_path.exists():
            return 0
        binding = json.loads(binding_path.read_text())
        assert binding['CP_sha256'] == csha and binding['passed']
        assert binding['script_sha256'] == digest(HERE / script)
        assert binding['receipt_sha256'] == digest(path)
        rows.append(dict(name=name, script=script, script_sha256=digest(HERE / script),
                         receipt=receipt, receipt_sha256=digest(path),
                         execution_binding=str(binding_path.relative_to(HERE)),
                         execution_binding_sha256=digest(binding_path), passed=True))
    save(OUT / 'component_replays.json', dict(schema='r5-422-fresh-cp-components/1',
         passed=True, CP_sha256=csha, suites=len(rows), rows=rows, camera_io=False,
         limits=['Offline native instruction replays use the explicit fixtures described in each receipt.',
                 'No ISP pixel output, real shutter scheduling or device acceptance is asserted.']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
