"""Write local delivery notes, then append current findings after DAT verification."""
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=ROOT/'research/r5_custom_lut/build_r5_4.30_startup_20261027'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def sums():
 (OUT/'SHA256SUMS').write_text('\n'.join(sha(p)+'  '+str(p.relative_to(OUT)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS')+'\n')
def readme():
 v=read(OUT/'verification.json');assert v['version']=='4.30'
 assert sha(OUT/'BODYDATA.DAT')==v['output_sha256']
 note=f'''# R5 4.30：启动切换及 SD 更新

BODYDATA.DAT，{(OUT/'BODYDATA.DAT').stat().st_size}字节，BCD3004。

SHA256 `{v['output_sha256']}`。

修复恢复当前滤镜后，SD扫描/网格诊断占住切换worker的问题；等待期间继续处理选择，诊断仅期待当前滤镜。相同配置不重复保存或上传。已就绪卡槽先加载，卡发现和文件读取使用独立预算。恢复启动若先按旧drive读取，迟到的新READY会触发本次开机重读。新配置传输失败本次开机最多三次重试，自动应用失败带退避重试；明确选择仍等待应用、保存及真实父菜单值核对后退出。

保留4.29左简写右全称、无更新按钮/右侧调整入口。BIN只支持v4，全部配置强制网格；CP精确继承4.23及4.22网格生命周期。

180项当前AP SD回放、15项选择worker、7项诊断等待、实际跨核30次选择及两路丢SEAL ACK同次恢复、原生菜单回归及最终容器检查。最终独立验签/CRC/全量解密结果以源码目录release_tests/delivery_verified.json为准。

本地离线交付，尚未刷入相机。真实冷启动/恢复启动、卡初始化延迟、LCD和ISP/JPG待实机验收；没有测量机身毫秒性能，持续的原厂服务/存储/传输失败仍会导致本次应用失败。

源码：analysis/r5_custom_menu430_startup_20261027/；原始镜像与历史包未改。
'''
 (OUT/'README.md').write_text(note);sums()
def records():
 v=read(OUT/'verification.json');d=read(HERE/'release_tests/delivery_verified.json');g=read(HERE/'release_tests/final_gate.json');b=read(HERE/'ap/ap_build.json')
 assert d['passed'] and d['version']=='4.30' and d['output_sha256']==v['output_sha256']
 heading='### 2026-10-27：4.30启动切换等待与同次开机SD更新'
 body=f'''\n\n{heading}

用户报告当前自定义滤镜开机数秒可预览，但几十秒不能切换；SD新BIN需两次重启。源码确认恢复后同一worker还阻塞于SD发现和最多30秒、期待全部配置mask的网格诊断；新配置存盘后，CP传输/初始E4失败缺少完整同次恢复。未取得本次机身日志，不定为唯一实机原因。

新目录analysis/r5_custom_menu430_startup_20261027仅改四个生产文件：thread、session、grid log、filter runtime。无fd等待点服务选择；诊断只期待当前配置；双槽独立就绪选择、30秒发现与15秒读文件独立预算；完整内容相同跳过写入及重复上传；有效清空/无效保持/原子保存不变。完整bank最多三次同次重试，自动选择一秒退避最多30次，主动选择绕过退避。恢复启动先复用旧drive后，迟到的当前epoch READY会触发同次开机重读，重复通知不重复提交。4.29菜单源码及CP423/422生命周期精确保持，未增加新线程或修改ACK/父值退出标准。

AP {g['AP_sha256']}，RX{b['rx_bytes']}/BSS{b['bss_bytes']}。当前AP执行180项双PIE SD、worker15、诊断7；实际AP/CP30次选择和两路丢SEAL ACK复用已封口bank的同次恢复；原生菜单/名称/对象生命周期等回归通过。本版不沿用旧162项SD精确继承证明。{len(g['required_receipts'])}份必需回执、{len(g['required_checks'])}项门控；最终DAT签名/CRC/篡改拒绝、AP/CP提取及751577088明文字节完整独立核对。交付research/r5_custom_lut/build_r5_4.30_startup_20261027/BODYDATA.DAT，754525608字节/BCD3004，SHA256 {v['output_sha256']}。

没有相机、SD、Web或远端操作，原镜像和历史交付保持。合成时钟不代表机身耗时；同步原厂Fsys仍可能超时，永久失败仍会阻止本次应用。实际冷启动/恢复/菜单及预览JPG待用户验收。
'''
 p=ROOT/'DEVELOPMENT_RECORD.md';s=p.read_text();assert heading not in s;p.write_text(s+body)
 p=ROOT/'README.md';s=p.read_text();entry=f'2026-10-27最新本地交付：[4.30 启动切换与同次开机SD更新](research/r5_custom_lut/build_r5_4.30_startup_20261027/BODYDATA.DAT)，754525608字节/BCD3004，SHA256 `{v["output_sha256"]}`。无fd等待点继续处理切换、诊断只观察当前滤镜；相同内容跳过重复保存/上传，双槽独立就绪，新配置传输和启动应用在本次开机内有限重试。保留4.29全称菜单和422网格生命周期。180项当前AP SD、15项worker、7项诊断、跨核30次选择及两路丢SEAL ACK恢复、菜单回归与实际DAT独立全量核验通过。尚无本次机身日志或启动耗时验收，无相机/Web/GitHub操作。[实现与边界](analysis/r5_custom_menu430_startup_20261027/README.md)／[独立回执](analysis/r5_custom_menu430_startup_20261027/release_tests/delivery_verified.json)。\n\n'
 assert '4.30 启动切换与同次开机SD更新' not in s
 split=s.index('\n\n')+2;p.write_text(s[:split]+entry+s[split:])
 p=ROOT/'analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md';s=p.read_text();assert heading not in s;p.write_text(s+body)
 print(json.dumps(dict(passed=True,version='4.30',output_sha256=v['output_sha256'])))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['readme','records'],required=True);a=p.parse_args()
 readme() if a.stage=='readme' else records()
