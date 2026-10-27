"""Write release notes and append current evidence after independent DAT verification."""
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=ROOT/'research/r5_custom_lut/build_r5_4.31_interaction_20261027'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def sums():
 (OUT/'SHA256SUMS').write_text('\n'.join(sha(p)+'  '+str(p.relative_to(OUT)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS')+'\n')
def readme():
 v=read(OUT/'verification.json');assert v['version']=='4.31'
 assert sha(OUT/'BODYDATA.DAT')==v['output_sha256']
 note=f'''# R5 4.31：自定义滤镜交互与原生列表

BODYDATA.DAT，{(OUT/'BODYDATA.DAT').stat().st_size}字节，BCD3104。

SHA256 `{v['output_sha256']}`。

上下移动或触摸即应用并保存，完成后保留菜单；确认/返回先通过原生资源解析核对已提交选择，再由原生pop重建并更新父菜单，已完成的相同选择不重复提交。左侧使用原生列表高亮，右侧保留全称，删除文本标记。原生显示资源核对未完成使用独立提示，不再把已成功的滤镜应用误报为应用失败；真正CP ACK、原厂执行或保存失败仍保留失败语义。

保留4.30启动提速、同次开机SD更新与有限重试，原worker四源精确继承。无更新按钮/右侧调整入口，BIN只支持v4，全部配置强制网格；CP精确继承4.23及4.22参数/网格生命周期。

当前AP页面/原生列表、父值及生命周期回放，180项SD、15项worker、7项诊断、实际跨核30次选择及两路丢SEAL ACK同次恢复，最终容器检查均由当前版本回执绑定。独立验签/CRC/全量解密结果见源码目录release_tests/delivery_verified.json。

本地离线交付，尚未刷入相机。用户确认4.30加载改善，但4.30操作、样式及错误提示未通过验收；本版离线回放不等于实机LCD/事件时序/预览或JPG验收，原厂Fsys长期阻塞仍可能延迟操作。

源码：analysis/r5_custom_menu431_interaction_20261027/；原始镜像与历史包未改。
'''
 (OUT/'README.md').write_text(note);sums()
def records():
 v=read(OUT/'verification.json');d=read(HERE/'release_tests/delivery_verified.json');g=read(HERE/'release_tests/final_gate.json');b=read(HERE/'ap/ap_build.json')
 assert d['passed'] and d['version']=='4.31' and d['output_sha256']==v['output_sha256']
 heading='### 2026-10-28：4.31菜单移动应用、原生列表及错误分类'
 body=f'''\n\n{heading}

用户确认4.30加载快了，但上下移动必须确认才应用，左侧样式简陋，实际应用后仍显示应用失败；因此4.30菜单交互/样式/提示实机验收失败。原生路由回放确认进入同层D9时旧父presenter已销毁，旧代码仍持有last_parent并直接调用其update；此外worker成功后的父页核对失败被错误归为应用失败。未取得机身崩溃/阶段日志，未把全部实机异常定为同一个原因。

4.31上下移动/触摸立即完整应用并保存、保留页面；确认/返回等待精确请求完成并用原生资源解析器核对提交值，再交给原生pop重建父菜单；删除旧父对象缓存及解引用，已完成同项不重复请求。左侧恢复原生列表高亮和选中，右侧仅全称，无更新/调整入口。显示资源核对独立分类，真正ACK/E4/保存失败仍失败。4.30四个worker/启动生产源码精确保持，CP423与422参数/网格生命周期保持。

AP {g['AP_sha256']}，RX{b['rx_bytes']}/BSS{b['bss_bytes']}。当前AP交互/原生控件/生命周期、180项SD、15项worker、7项诊断、跨核30选择及两路丢SEAL ACK恢复通过；{len(g['required_receipts'])}份必需回执、{len(g['required_checks'])}项门控；DAT独立签名/CRC/篡改拒绝/AP与CP提取及751577088明文字节逐字核对通过。交付research/r5_custom_lut/build_r5_4.31_interaction_20261027/BODYDATA.DAT，754525608字节/BCD3104，SHA256 {v['output_sha256']}。

本轮仅本地开发与离线封装，无相机、SD实物、Web/GitHub操作。物理字体/遮挡/透明度/触摸、原厂事件时序、冷启动及拍摄仍待实机；没有用离线模拟替代用户验收。
'''
 p=ROOT/'DEVELOPMENT_RECORD.md';assert heading not in p.read_text()
 with p.open('a') as f:f.write(body)
 p=ROOT/'README.md';s=p.read_text();entry=f'2026-10-28最新本地交付：[4.31 自定义滤镜交互与原生列表](research/r5_custom_lut/build_r5_4.31_interaction_20261027/BODYDATA.DAT)，754525608字节/BCD3104，SHA256 `{v["output_sha256"]}`。上下移动/触摸即应用保存、确认返回，恢复原生列表高亮，区分应用失败与父页刷新；保留4.30加载优化及422网格生命周期。当前AP交互与生命周期、180项SD、跨核及最终DAT独立全量核对通过。用户确认4.30加载改善，但其菜单操作/样式/错误提示验收失败；4.31实机LCD和时序仍待验收。无设备/Web/GitHub操作。[实现与边界](analysis/r5_custom_menu431_interaction_20261027/README.md)／[独立回执](analysis/r5_custom_menu431_interaction_20261027/release_tests/delivery_verified.json)。\n\n'
 assert '4.31 自定义滤镜交互与原生列表' not in s
 split=s.index('\n\n')+2;p.write_text(s[:split]+entry+s[split:])
 p=ROOT/'analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md';assert heading not in p.read_text()
 with p.open('a') as f:f.write(body)
 print(json.dumps(dict(passed=True,version='4.31',output_sha256=v['output_sha256'])))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['readme','records'],required=True);a=p.parse_args()
 readme() if a.stage=='readme' else records()
