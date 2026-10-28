"""Bind replays to the candidate's actual rebuilt AP, never an old hash."""
from pathlib import Path
import hashlib
import json


def verify_ap_binding(path):
    path = Path(path)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    build_path = path.parent / 'ap_build.json'
    build = json.loads(build_path.read_text())
    assert build['AP_sha256'] == actual, (str(build_path), build['AP_sha256'], actual)
    assert path.parent.parent.name == 'r5_firmware434_20261028'
    return actual
