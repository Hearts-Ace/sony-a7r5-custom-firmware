"""Document an independently verified local release; never access a camera."""
from pathlib import Path
import hashlib,json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'research/r5_custom_lut/build_r5_4.34_icon_awb_20261028'

def read(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()

def main():
    v=read(OUT/'verification.json')
    d=read(HERE/'release_tests/delivery_verified.json')
    g=read(HERE/'release_tests/final_gate.json')
    assert d['passed'] and d['version']==v['version']=='4.34'
    assert d['output_sha256']==v['output_sha256']==sha(OUT/'BODYDATA.DAT')
    assert d['plaintext_verification']['every_plaintext_byte_matches']
    assert d['regional_BK4_templates_verified']==12
    assert (v['AWB_ambience'],v['AWB_white_priority'])==(-1,97)
    fn=read(HERE/'fn/fn434_verified.json')
    assert fn['passed'] and fn['AP_sha256']==g['AP_sha256']
    note=f'''# R5 4.34：动态图标修复与白色优先97

BODYDATA.DAT，{d['output_bytes']}字节，BCD3404。
SHA256 `{v['output_sha256']}`。

自定义滤镜的图标改为调用原厂Creative Look当前外观的图片路径：原厂为ST时显示ST，切换其它外观时跟随原厂。4.33误将帮助文字资源当成图片，是此前无法加载的原因；本版保留帮助文字字段，移除错误图片fallback，仅在原厂取图入口将自定义MID635转到Creative Look的MID1E6。菜单名称、独立滤镜选择及Fn手动注册保持。按用户最新要求，主菜单左侧小logo不再继续追查。

白色优先由4.33的112改为97，氛围优先保持−1。12份地区通用BK4模板与backup.sum同步更新；相对4.33每份仅白色字节和必要校验变化，整个CC1／block13、R6 ST与FL2／FL3保持。白色局部主系数由原厂公式自动得到450，不另加硬编码系数。

AP `{g['AP_sha256']}`，新增20字节图标转发包装器，描述符只移除错误图片fallback，其它22份原编译对象与4.33逐字相同。RX63480／BSS136384，CP精确保持423及422参数／网格生命周期。

已通过原厂12状态动态图标对照、真实图片资源解码、Fn注册／调用／返回回放和25项现有离线回归。12地区模板、原生迁移／CC1／矩阵／AWB检查，以及最终DAT独立签名／CRC／篡改拒绝、16个TAR替换成员和全部{d['plaintext_verification']['plaintext_bytes']}明文字节核对通过。

本轮仅本地构建，没有操作相机或远端发布。实体LCD图标显示及刷新、实际升级／冷启动与AWB成像仍待实机验收。

源码与回执：analysis/r5_firmware434_20261028/。
'''
    (OUT/'README.md').write_text(note)
    (OUT/'SHA256SUMS').write_text('\n'.join(sha(p)+'  '+str(p.relative_to(OUT)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS')+'\n')
    heading='### 2026-10-28：4.34动态图标资源修复及白色优先97'
    body=f'''\n\n{heading}

用户报告4.33自定义滤镜图标无法加载，要求与原厂Creative Look动态状态一致，并将白色优先112改97。已确认0x021C6410为string_english_f.uxc中的Creative Look帮助文字，descriptor+0x0C和getter1BD5630属于帮助通路；4.33将其写到图片fallback+0x60是资源类别错误。旧回放只检查资源ID送入sprite，不能证明图片存在，不能沿用其图标通过结论。

4.34保留合法帮助字段+C，将+60恢复sentinel，新增20字节A64 wrapper，仅在原厂图片取图入口1BD63B4把MID635转为MID1E6，重放原cmp w1,#CA4后回1BD63B8。原厂PID690当前状态getter28AE4B0／BSS7F207E8决定所选行，真实动态链1BD642C→1BC50EC取原厂当前图标；type保持原生6，不改私有选择／路由／标题。原厂12状态与候选动态图标、真实UXC图片记录和解码分别核对。用户最新要求不再追查主菜单左侧小logo，本版不据此认定其类型或含义。

AP {g['AP_sha256']}，24个编译对象中新增1个icon ASM、原menu初始化移除错误fallback，其余22个与4.33逐字相同。RX63480／BSS136384；原生前缀反向恢复精确，Fn候选表仍41字节变化，CP {g['CP_sha256']}精确保持423。原厂12状态的Fn图片resource／type与候选同状态对照，注册／激活／返回及现有25项菜单／控制轮／生命周期／SD／跨核回归全部绑定当前AP。

AWB property02A40000+930白色97／+931氛围−1，连续61ff0006，局部系数自动450；12地区模板与4.33逐字节仅白色112→97和BK4校验差异，backup.sum仅12CRC。CC1／block13整属性、R6 ST／FL23及Gamma保持。原生迁移72例、异常拒绝4例、CC1 63例、矩阵320例、AWB336例通过，标准AWB112例保持。该系数是后段修正参数，不直接表述为可见光／红外硬件权重。

交付research/r5_custom_lut/build_r5_4.34_icon_awb_20261028/BODYDATA.DAT，{d['output_bytes']}字节／BCD3404，SHA256 {v['output_sha256']}。独立签名／CRC／篡改拒绝、AP／CP提取、16个TAR替换成员、12地区模板及全部{d['plaintext_verification']['plaintext_bytes']}明文字节核对通过。详见analysis/r5_firmware434_20261028/release_tests/delivery_verified.json。未操作相机、SD、fastboot或远端；实机LCD图标与刷新、升级／冷启动、AWB收敛与成像仍待分别验收。
'''
    for name in ('DEVELOPMENT_RECORD.md','analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md'):
        p=ROOT/name
        assert heading not in p.read_text(),'Refuse duplicate record'
        with p.open('a') as f:f.write(body)
    p=ROOT/'README.md';text=p.read_text()
    entry=f'''2026-10-28最新本地交付：[4.34 动态图标修复与白色优先97](research/r5_custom_lut/build_r5_4.34_icon_awb_20261028/BODYDATA.DAT)，{d['output_bytes']}字节／BCD3404，SHA256 `{v['output_sha256']}`。修正4.33将帮助文字误当图片的问题，自定义滤镜沿用原厂Creative Look当前状态动态图标；白色112→97，氛围−1，12地区模板及必要校验同步，R6 ST／FL23保持。动态图标原厂对照与资源解码、Fn／25项离线回归及最终DAT独立全量核对通过。按用户要求停止主菜单左侧小logo追查；无相机或远端操作，实际LCD／刷新、升级／冷启动与拍摄待验收。[实现及边界](analysis/r5_firmware434_20261028/README.md)／[独立回执](analysis/r5_firmware434_20261028/release_tests/delivery_verified.json)。此前4.33图标通过结论已由本次资源类别证据纠正。\n\n'''
    assert '4.34 动态图标修复与白色优先97' not in text
    at=text.index('\n\n')+2;p.write_text(text[:at]+entry+text[at:])
    print(json.dumps(dict(passed=True,version='4.34',output_sha256=v['output_sha256']),ensure_ascii=False))

if __name__=='__main__':main()
