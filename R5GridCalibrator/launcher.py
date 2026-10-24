"""Launch with the user's selected environment; never install implicitly."""
import sys
if sys.version_info<(3,11):
    raise SystemExit('需要Python 3.11–3.13，推荐3.12。请安装后使用对应python3启动。')
try:
    import numpy,scipy,PIL,tifffile
except ImportError as error:
    raise SystemExit('缺少依赖，请先运行：python3 -m pip install -r requirements.txt\n'+str(error))
from server import main
if __name__=='__main__':main()
