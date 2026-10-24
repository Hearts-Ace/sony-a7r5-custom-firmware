#!/bin/zsh
set -eu
cd "${0:A:h}"
grid_python="${R5_GRID_PYTHON:-python3}"
if [[ -x .venv/bin/python && -z "${R5_GRID_PYTHON:-}" ]]; then grid_python=.venv/bin/python; fi
"$grid_python" launcher.py "$@" || { read '?启动失败，按回车关闭…'; exit 1; }
