"""Write 4.32 notes and append records after final independent DAT verification."""
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=ROOT/'research/r5_custom_lut/build_r5_4.32_wheel_20261028'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def sums():
 (OUT/'SHA256SUMS').write_text('\n'.join(sha(p)+'  '+str(p.relative_to(OUT)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS')+'\n')
def readme():
 v=read(OUT/'verification.json');assert v['version']=='4.32'
 assert sha(OUT/'BODYDATA.DAT')==v['output_sha256']
 note=f'''# R5 4.32：控制轮与菜单同步

BODYDATA.DAT，{(OUT/'BODYDATA.DAT').stat().st_size}字节，BCD3204。

SHA256 `{v['output_sha256']}`。

控制轮旋转与上下按键共用自定义滤镜选择通路：同步移动左侧焦点、更新右侧全称并应用保存；连续滚动按每个事件一步选择，在首尾边界停止，不进入原厂创意外观设置器。完成后保留页面，确认/返回经原生资源解析核对后，由原生pop重建父菜单。

本版生产源码只改页面；4.31原生列表、父级生命周期和错误分类，4.30启动提速与同次开机SD更新，以及CP423/422参数和网格生命周期保持。无更新按钮/右侧调整入口，BIN只支持v4，全部配置强制网格。

当前AP完整菜单/原生列表、控制轮、父级及生命周期回放，180项SD、15项worker、7项诊断、实际跨核30次选择及丢SEAL ACK恢复，最终容器检查由新版本回执绑定。独立验签/CRC/全量解密结果见源码目录release_tests/delivery_verified.json。

用户确认4.31上下按键正常，但控制轮切滤镜时UI未同步；4.32控制轮、实机LCD/事件时序和拍摄仍待验收。离线模拟未替代实际机身验证。无相机、SD实物、Web或GitHub操作。

源码：analysis/r5_custom_menu432_wheel_20261028/；原始镜像与历史包未改。
'''
 (OUT/'README.md').write_text(note);sums()
def records():
 v=read(OUT/'verification.json');d=read(HERE/'release_tests/delivery_verified.json');g=read(HERE/'release_tests/final_gate.json');b=read(HERE/'ap/ap_build.json')
 assert d['passed'] and d['version']=='4.32' and d['output_sha256']==v['output_sha256']
 heading='### 2026-10-28：4.32控制轮与自定义滤镜菜单同步'
 body=f'''\n\n{heading}

用户确认4.31上下按键已正常，但旋转控制轮仅切换滤镜、界面不动。因此4.31控制轮同步未通过实机验收，不能以其离线按键/触摸测试宣称覆盖旋转事件。

4.32让控制轮与上下按键共用自定义选择通路，联动焦点、全称、原生列表和应用保存，连续滚动按每个事件一步选择，首尾边界不越界，不读取消息内的步数或方向；不进入原厂Look设置器。生产源码仅页面相对4.31变化；4.31原生列表与父级重建/错误分类，4.30四个启动worker源码，以及CP423/422参数和网格生命周期精确保持。

AP {g['AP_sha256']}，RX{b['rx_bytes']}/BSS{b['bss_bytes']}。当前AP控制轮/交互/原生控件/生命周期、180项SD、15项worker、7项诊断、跨核30选择及两路丢SEAL ACK恢复通过；{len(g['required_receipts'])}份必需回执、{len(g['required_checks'])}项门控；DAT独立签名/CRC/篡改拒绝/AP与CP提取及751577088明文字节逐字核对通过。交付research/r5_custom_lut/build_r5_4.32_wheel_20261028/BODYDATA.DAT，754525608字节/BCD3204，SHA256 {v['output_sha256']}。

本轮仅本地开发及离线封装，无相机、SD实物、Web/GitHub操作。真实控制轮速度与GUI事件队列、字体/透明度/触摸、冷启动和拍摄仍待机身验收；未用合成时钟推定相机耗时。
'''
 p=ROOT/'DEVELOPMENT_RECORD.md';assert heading not in p.read_text()
 with p.open('a') as f:f.write(body)
 p=ROOT/'README.md';s=p.read_text();entry=f'2026-10-28最新本地交付：[4.32 控制轮与自定义滤镜菜单同步](research/r5_custom_lut/build_r5_4.32_wheel_20261028/BODYDATA.DAT)，754525608字节/BCD3204，SHA256 `{v["output_sha256"]}`。旋转控制轮与按键共用选择通路，焦点/全称/应用同步；保留4.31原生列表和父级重建、4.30加载优化及422网格生命周期。当前AP控制轮与完整回归、DAT独立全量核对通过。4.31上下按键获用户确认，控制轮UI不同步未通过；4.32实机旋转/时序仍待验收。无设备/Web/GitHub操作。[实现与边界](analysis/r5_custom_menu432_wheel_20261028/README.md)／[独立回执](analysis/r5_custom_menu432_wheel_20261028/release_tests/delivery_verified.json)。\n\n'
 assert '4.32 控制轮与自定义滤镜菜单同步' not in s
 split=s.index('\n\n')+2;p.write_text(s[:split]+entry+s[split:])
 p=ROOT/'analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md';assert heading not in p.read_text()
 with p.open('a') as f:f.write(body)
 print(json.dumps(dict(passed=True,version='4.32',output_sha256=v['output_sha256'])))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['readme','records'],required=True);a=p.parse_args()
 readme() if a.stage=='readme' else records()
