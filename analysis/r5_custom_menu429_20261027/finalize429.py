"""Write release notes/checksums, then update local indexes after verification.

No device, Web process or remote publication operations are performed.
"""
from pathlib import Path
import argparse, hashlib, json
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT/'research/r5_custom_lut/build_r5_4.29_name_only_20261027'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''): h.update(block)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=('readme', 'records'), required=True)
    args = parser.parse_args()
    v = json.loads((OUT/'verification.json').read_text())
    assert v['version'] == '4.29' and sha(OUT/'BODYDATA.DAT') == v['output_sha256']
    digest = v['output_sha256']
    source = 'analysis/r5_custom_menu429_20261027'
    delivery = 'research/r5_custom_lut/build_r5_4.29_name_only_20261027'
    if args.stage == 'readme':
        (OUT/'README.md').write_text(f'''# R5 4.29：修复自定义菜单全称与残留调整栏

针对用户报告的4.28右侧无全称、出现只能+1/−1的操作栏，本版修正私有菜单ID判断，移除自定义页原厂参数调整控件和按键入口。原厂创意外观的组件与算法保持。

- 左侧显示关闭及配置简写，右侧显示对应全称。
- 上下/长按只移动滤镜选择；移除右侧调整和更新按钮及页面内操作逻辑。
- 按M4接入契约处理真实布局虚表槽、首帧、专用对象及构造/析构，隔离关闭/MID变化后的残留输入。
- 确认后等待应用、持久保存及父级选中值核对完成再退出；失败留页。
- 开机/媒体自动导入、BIN v4与4.22网格生命周期保持，CP逐字节继承4.23。

文件：BODYDATA.DAT，754525608字节，版本4.29/BCD2904。

SHA256：`{digest}`

AP SHA256：`{v['components']['appFw.so']['sha256']}`

CP SHA256：`{v['components']['cpapp-b.bin']['sha256']}`

离线检查包括22项页面场景、13项名称、连续/长按与稀疏配置、真实Enter/布局/query/widget分配及构造析构、11项worker、76项请求、10项包装器和28次跨核选择。162项历史SD执行通过完整实现身份继承，未冒称当前AP重新执行全部案例。原厂.text除等价635 resolver跳转外逐字等于4.28，两套原D9 styles保持。

实际DAT的独立签名/CRC/篡改拒绝、AP/CP提取和完整逐字解密结果，以 `{source}/release_tests/delivery_verified.json` 为准。离线通过不代表实际LCD、冷启动或拍摄已通过；低层UX/字体/显示后端及部分系统服务是fixture，三页RW实际装载仍需机身验收。

本次仅本地开发和打包，没有访问相机、SD、块设备、Web或GitHub。历史包、原机镜像和原始采集不改。源码与证据：`{source}/README.md`。
''')
        (OUT/'SHA256SUMS').write_text('\n'.join(sha(p)+'  '+str(p.relative_to(OUT))
            for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS')+'\n')
        print('release README and checksums ready')
        return
    q = json.loads((HERE/'release_tests/delivery_verified.json').read_text())
    assert q['passed'] and q['output_sha256'] == digest and not q['device_acceptance_tested']
    notice = f'''2026-10-27最新本地交付：[4.29 自定义菜单全称与调整栏修复]({delivery}/BODYDATA.DAT)，754525608字节，BCD2904，SHA256 `{digest}`。用户确认4.28自定义页全称缺失、残留参数栏异常，原厂创意外观组件正常；本版修正MID/ROW误用，右侧仅显示全称，删除私有调整及更新入口，按M4真实布局/生命周期接入。选择等待应用、保存和真实父值核对后退出；CP与4.22网格生命周期保持。20份必需回执、15项检查及最终DAT独立签名/CRC/篡改拒绝、AP/CP提取、全部751577088明文字节核对通过。仅本地开发，无相机/Web/GitHub操作，实机菜单、冷启动及拍摄待验收。[交付说明]({delivery}/README.md)／[源码与边界]({source}/README.md)／[最终回执]({source}/release_tests/delivery_verified.json)。以下旧交付按时间读取。

'''
    p = ROOT/'README.md'
    text = p.read_text()
    assert notice not in text
    first, rest = text.split('\n', 1)
    p.write_text(first+'\n\n'+notice+rest.lstrip('\n'))
    p = ROOT/'research/r5_custom_lut/README.md'
    text = p.read_text(); first, rest = text.split('\n', 1)
    p.write_text(first+'\n\n'+notice.replace(delivery+'/', 'build_r5_4.29_name_only_20261027/').replace('('+source+'/', '(../../'+source+'/')+rest.lstrip('\n'))
    p = ROOT/'DEVELOPMENT_RECORD.md'
    with p.open('a') as f:
        f.write(f'''\n\n### 2026-10-27：4.29自定义菜单全称与残留参数栏修复

用户报告4.28右侧无全称且只能+1/−1，进一步确认原厂创意外观组件正常。新目录{source}以427已复核M4契约为参考，生产源码仅改私有页面，保留428无更新操作。正确PID3b2菜单身份、VT+40布局/原query、静态专用对象/完整ctor-dtor与首帧0；白名单排除全部右侧调整和更新控件，私有及退页残留输入不进原Look setter。左简写/右全称；确认仍等待应用/保存/真实父选中值后单次pop。

AP74a8923e…4728315，97452032字节，RX61624/BSS136368，native arena42752。CP精确8b38e753继承423，BIN v4及422参数/网格生命周期不变。22项页面、13名称及连续/长按/稀疏配置、真实主菜单/控件/allocator/生命周期、worker11/请求76/wrapper10/跨核28选择通过；SD162按完整实现身份继承。20必需回执、15项门控、{q['frozen_source_inputs']}冻结输入；最终DAT签名/CRC/篡改拒绝、AP/CP提取及751577088明文字节/736841块全部独立校验通过。DAT {digest}，754525608字节/BCD2904，见{delivery}/BODYDATA.DAT。

此前已清理的旧依赖目录不重建；新构建读取同散列assets镜像，小依赖从保留公开源码副本按冻结428清单校验复制到新dependencies；历史缺失项显式记录，当前打包输入全部绑定。未修改历史证据、原机资料或旧包，未操作相机、Web或GitHub。实际LCD/触摸/透明度、三页RW机身loader、冷启动及ISP/JPG待实机验收，未取得426崩溃PC。
''')
    p = ROOT/'analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md'
    text = p.read_text()
    text = text.replace('# R5 4.28 ', '# R5 4.29 ', 1)
    text = text.replace('更新：2026-10-24。', '更新：2026-10-27。', 1)
    text = text.replace('判断4.28。', '判断4.29。', 1)
    marker = '## 4.28：'
    at = text.index(marker)
    section = f'''## 4.29：自定义菜单右侧全称与输入隔离（2026-10-27）

用户报告4.28自定义页右侧没有全称，残留参数栏只能变为+1/−1；原厂创意外观里的组件正常。这纠正了把428回退离线通过视作右侧布局已验收的解读。428保留425错误MID getter和旧布局ABI：真实菜单属性PID3b2与行属性PID3b7不能混用；原生调整控件也不能作为自定义名称页的可交互组件。没有本轮机身RAM/崩溃栈，不能把静态缺陷称为唯一实机触发原因。

429保留428“无更新操作”要求，合入427按M4查明的真实MID、VT+40布局/原VT+30 query、首帧0和专用对象生命周期修正。私有白名单只创建实时取景壳、名称和左侧触摸区域；右侧仅全称，原生调整/箭头/footer及旧更新入口均不创建。上下/长按只切换配置；当前及关闭/MID变化后的私有输入不进原Look setter，原厂创意外观代码及原D9样式保持。选择按CP确认、原厂E4返回、再次CP确认、持久保存/发布、真实父值核对后退出；旧表“先保存再SELECT”只代表425之前顺序。

名称getter/UTF8桥接覆盖关闭及12项，连续/长按/稀疏配置、真实原生Enter、控件allocator、构造析构和manager/query通过。AP `74a8923e208790d4794a4790e9d8abf8c324795529ef6bcbc544b48af4728315`，RX61624/BSS136368，native arena42752；CP仍精确继承423，BIN v4、Gamma尾部和422网格生命周期不改。20回执、15项门控、最终DAT签名/CRC/篡改拒绝及751577088明文字节/736841块独立对照通过；DAT SHA256 `{digest}`，754525608字节/BCD2904。

交付：`{delivery}/BODYDATA.DAT`；源码及证据：`{source}/README.md`。物理LCD/触摸/字体/透明度、三页RW实际装载、冷启动及ISP/JPG仍待机身验收；没有相机、Web或GitHub操作。旧版本、原始采集、首次镜像和历史回执保持。

'''
    text = text[:at]+section+text[at:]
    text = text.replace('当前交付改为4.28。', '当时交付改为4.28。', 1)
    text = text.replace('版本与验收状态（4.28见前节，以下为历史）', '版本与验收状态（4.29见前节，以下为历史）', 1)
    p.write_text(text)
    print(json.dumps(dict(passed=True, DAT_sha256=digest, indexes_updated=True), ensure_ascii=False))

if __name__ == '__main__': main()
