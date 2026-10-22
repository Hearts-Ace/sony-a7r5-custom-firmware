#!/bin/zsh
set -eu
cd "${0:A:h}"
if ! command -v python3 >/dev/null; then
  print '请先安装 Python 3.12：https://www.python.org/downloads/'
  read '?按回车关闭…'
  exit 1
fi
python3 launcher.py "$@" || { read '?启动失败，按回车关闭…'; exit 1; }
