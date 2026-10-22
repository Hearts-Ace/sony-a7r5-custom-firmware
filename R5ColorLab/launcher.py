"""Start the local UI with dependencies installed by the user."""
import argparse, importlib.util, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def main():
    if sys.version_info < (3, 11):
        raise SystemExit('需要 Python 3.11 或更新版本（推荐 3.12）。')
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--test', action='store_true')
    args, extra = parser.parse_known_args()
    missing = [name for name in ('numpy', 'scipy', 'PIL', 'rawpy') if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit('缺少依赖：' + ', '.join(missing) + '\n请先在项目目录运行：python3 -m pip install -r requirements.txt（Windows：py -3 -m pip install -r requirements.txt）')
    env = {**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    if args.check or args.test:
        command = [sys.executable, str(ROOT / 'self_check.py')] + (['--test'] if args.test else [])
    else:
        command = [sys.executable, str(ROOT / 'web/server.py'), *extra]
    return subprocess.call(command, cwd=ROOT, env=env)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except OSError as e:
        raise SystemExit('启动失败：' + str(e))
