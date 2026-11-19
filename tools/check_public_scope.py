"""Reject private training material in the public firmware repository."""
from pathlib import Path, PurePosixPath
import subprocess

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git', '-C', str(root), '-c', 'core.quotepath=false', 'ls-files', '-z']).decode().split('\0')
blocked = []
for path in filter(None, paths):
    parts = PurePosixPath(path).parts
    name = parts[-1].lower()
    if (parts[0] in {'R5ColorLab', 'R5GridCalibrator'}
        or path.startswith('research/r5_custom_lut/')
        or path.startswith('publication/colorlab-')
        or name in {'latent_response.py', 'stack_training.py', 'grid_distillation.py',
                    'formal_training.py', 'fit_edit_native.py', 'fit_full_chain_native.py'}
        or name.startswith('r5-grid-response')
        or (name.startswith('r5-') and name.endswith('.json') and any(s in name for s in ['asymmetric-perceptual', 'differential-refit']))):
        blocked.append(path)
if blocked:
    raise SystemExit('Private training material is not permitted:\n' + '\n'.join(blocked))
print('Public scope OK: firmware, resources and numerical summaries only')
