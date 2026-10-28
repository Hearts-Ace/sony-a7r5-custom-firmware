'''Write release notes and append project records after independent validation.'''
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'research/r5_custom_lut/build_r5_4.33_color_fn_20261028'

def read(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def sums():
    (OUT/'SHA256SUMS').write_text('\n'.join(sha(p)+'  '+str(p.relative_to(OUT)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS')+'\n')
def readme():
    v=read(OUT/'verification.json')
    assert v['version']=='4.33' and sha(OUT/'BODYDATA.DAT')==v['output_sha256']
    text=f'''# R5 4.33：参数保留、R6 ST、Fn与白平衡

BODYDATA.DAT，{(OUT/'BODYDATA.DAT').stat().st_size}字节，BCD3304。
SHA256 `{v['output_sha256']}`。

1. 补全全部12份地区默认Backup模板中的FL2/FL3映射、CC1和block13三端点，重算BK4校验及backup.sum。升级时沿用原厂迁移，避免旧原厂模板回写覆盖颜色；保持现有动态B/A1/A2，不切换fixed-a1。
2. ST照片采用R6 RAW精确反算的三组CC1和block13 A1全部16槽。R6未保存的B/A2、bank尾、视频及完整Gamma沿用R5；可见Gamma128点、Knee/YGain与R5相同。
3. Fn菜单设置的颜色/色调分类增加自定义滤镜可注册项，由用户手动分配，不自动占用或替换任何Fn槽位；沿用原生Fn注册、保存和调用路径。普通菜单和Fn同时复用创意外观图标，名称仍为自定义滤镜。自定义滤镜仍使用现有菜单、选择保存及SD读取流程，原创意外观保留。
4. 氛围优先由-24改为-1，白色优先由88改为112；12份模板同时更新，升级后采用新值，配套参数保持。

升级包包含通用默认模板，不包含个人设置分区镜像。没有新增AP/CP强制写回、Backup专同步或finalizer。AP追加Fn候选数据（41字节差异），生产源码仅菜单描述符初始化中的两个图标常数变化，其余22份编译对象与4.32逐字相同；重链接会调整地址，RX63464/BSS136384预留不增。CP精确保持4.32所用423版本及422参数/网格生命周期。

已完成原生迁移72案例、CC1 63例、矩阵320例、AWB336例及Fn专项回放；当前AP完整菜单/轮盘/生命周期、180项SD、worker及跨核回归通过。独立DAT签名/CRC/全量解密、全部16个TAR替换成员和12地区模板核对以源码目录release_tests/delivery_verified.json为准。

本轮没有操作相机或发布远端。实际升级、Fn界面/事件时序、冷启动及预览/JPG仍待实机验收；离线回放不代表实际拍摄通过。以后刷入不含这些颜色及AWB默认值的固件，仍可能恢复该固件的模板值。

源码与证据：analysis/r5_firmware433_20261028/。上游文档锁定d4649e21f72e9074031c0c95c9ec2dc23ecb6807，仅采用其generic模板保留方法；其fixed-a1默认不纳入本版。
'''
    (OUT/'README.md').write_text(text)
    sums()
def records():
    v=read(OUT/'verification.json');d=read(HERE/'release_tests/delivery_verified.json');g=read(HERE/'release_tests/final_gate.json')
    assert d['passed'] and d['version']=='4.33' and d['output_sha256']==v['output_sha256']==sha(OUT/'BODYDATA.DAT')
    assert d['regional_BK4_templates_verified']==12 and d['plaintext_verification']['every_plaintext_byte_matches']
    heading='### 2026-10-28：4.33升级参数保留、R6 ST、Fn注册及AWB'
    body=f'''\n\n{heading}

按用户四项需求，以冻结4.32为功能基线生成4.33／BCD3304。参考指定Erlla文档并锁定最新d4649e21f72e9074031c0c95c9ec2dc23ecb6807，其文档与已保存20261019版本一致；采用完整generic模板+backup.sum方法，保留原086df3b的动态B/A1/A2，不引入fixed-a1或运行时强制写回。

已确认4.32所继承strict4.04 TAR中的12份地区模板颜色仍为原厂默认，原厂attrs8迁移会从新模板取CC1/block13/AWB，导致仅在个人设置里部署的颜色被覆盖。4.33补全12份模板每份10处FL23、2处R6 ST和1处AWB，共13个参数范围/2746字节范围，另维护BK4校验。每份实际1976字节变化，FL23完整四个768字节bank均等于既有动态供体；backup.sum仅12项CRC更新，MainDest和目录行保持。两份原始迁移核72案例与4项异常拒绝、独立模板字节复核通过；LOOK保留证明对应所验证mode5，不将政策核心回放冒充整机升级。

ST照片bank0更换CC1全部24项和block13 A1全部96项，其他bank/映射保持；bank0原厂别名仍按原映射共用新数据。B/A2、尾部、视频和完整Gamma保持R5，可见Gamma128点及Knee/YGain相同。AWB模板930/931为70/FF（白色112、氛围-1），932/933为00/06保持。当前CP原生CC1 63例、矩阵320例和AWB336例验证新值进入消费，标准AWB112例保持；CC1调整子服务输入为声明fixture，完整矩阵/AWB无helper桩。

Fn在原生颜色/色调候选组追加MID635，复用原厂Creative Look的still/movie标志，play不启用；仅增加手动可注册项，不自动占用或替换Fn槽位，保留原有选项、保存和调用通路。普通菜单与Fn共用Creative Look图标021C6410，名称仍为自定义滤镜。AP {g['AP_sha256']}，候选表41字节差异；生产源码仅menu描述符初始化+c/+60两处图标常数变化，其余22份编译对象逐字等于4.32。重链接会更新相关地址，RX63464/BSS136384预留不增。CP {g['CP_sha256']}精确继承423，原422参数/网格生命周期保持。Fn专项验证及完整菜单/轮盘/生命周期、180项SD、worker15、grid7、跨核30次选择和丢SEAL ACK恢复全部绑定最终AP。原生注册handler和24槽两种目标/两PIE共96例影子保存恢复通过；物理BKID/eMMC提交和冷启动持久性不由影子回放代替。

交付research/r5_custom_lut/build_r5_4.33_color_fn_20261028/BODYDATA.DAT，{d['output_bytes']}字节，SHA256 {v['output_sha256']}。独立验签/CRC/篡改拒绝、AP/CP提取、16个TAR替换成员及{d['plaintext_verification']['plaintext_bytes']}明文字节完整核对通过。来源与门控、Fn及原生消费/迁移回执见analysis/r5_firmware433_20261028。无个人设置镜像、相机/SD实物/fastboot或远端发布操作；实际升级、Fn/LCD/事件时序、冷启动及预览/JPG仍待实机，离线不代替功能验收。
'''
    for name in ('DEVELOPMENT_RECORD.md','analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md'):
        path=ROOT/name
        assert heading not in path.read_text(),'Refuse duplicate records'
        with path.open('a') as f:f.write(body)
    path=ROOT/'README.md';text=path.read_text()
    entry=f'2026-10-28最新本地交付：[4.33 参数保留、R6 ST、Fn及AWB](research/r5_custom_lut/build_r5_4.33_color_fn_20261028/BODYDATA.DAT)，{d["output_bytes"]}字节／BCD3304，SHA256 `{v["output_sha256"]}`。12地区Backup模板与backup.sum补全FL23、R6 ST照片及AWB（氛围-1／白色112）；自定义滤镜接入Fn，普通菜单/Fn复用创意外观图标。AP仅Fn候选表和菜单图标初始化变化，CP保持423；原生迁移/参数消费、Fn与现有回归、最终DAT独立全量核对通过。无设备或远端操作，实际升级、Fn/LCD/冷启动及拍摄待验收。[实现及边界](analysis/r5_firmware433_20261028/README.md)／[独立回执](analysis/r5_firmware433_20261028/release_tests/delivery_verified.json)。\n\n'
    assert '4.33 参数保留、R6 ST、Fn及AWB' not in text
    at=text.index('\n\n')+2;path.write_text(text[:at]+entry+text[at:])
    print(json.dumps(dict(passed=True,version='4.33',output_sha256=v['output_sha256'])))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['readme','records'],required=True);a=p.parse_args()
    readme() if a.stage=='readme' else records()
