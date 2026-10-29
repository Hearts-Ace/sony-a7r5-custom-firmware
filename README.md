# Sony A7R V / R5 自定义滤镜 4.34

4.34修正自定义滤镜动态图标：沿用原厂Creative Look当前状态，ST时显示ST、切换其它外观时同步取图。4.33误将帮助文字资源当图片的问题已纠正。白色优先改为97，氛围优先保持−1；12地区通用Backup模板与backup.sum同步，保留R6可恢复ST参数、FL2/FL3和原有参数／网格生命周期。

- [4.34源码、最新工具和滤镜下载](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware/releases/tag/v4.34)
- [色彩工作台](R5ColorLab/README.md) · [最新高精度训练方案](R5ColorLab/TRAINING.md)
- [新版12款滤镜：BIN、可编辑配置与完整训练设置](filters/FUJ_12_continuity30/README.md)
- [反推网格工作台](R5GridCalibrator/README.md) · [R5实拍v2响应及来源](R5ColorLab/web/data/r5/PROVENANCE.md)
- [唯一固件构建入口与复现说明](firmware/r5/README.md)
- [固件本地交付回执](publication/4.34/firmware_delivery_verified.json) · [训练完成回执](publication/4.34/training_completion_verified.json)
- [唯一研究总结](analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md)

## 固件构建入口

2026-10-29：构建代码已合并为 [firmware/r5/build.py](firmware/r5/build.py)。独立重编AP、CP和完整DAT，散列精确等于已发布4.34；版本及机内行为不变。目录内含完整源码、补丁配方、原始输入/源码锁、恢复说明和复现回执；没有引用旧目录。

## 当前训练方案

正式默认：参数平滑30、输出连续性30、每阶段2000评估、12起点、8动态轮、3轮Gamma/色彩交替、3轮原生整数量化微调。最终5×9×9整数网格直接拟合目标，压缩后原生/网格交替和灰阶专项微调关闭。支持Apple Metal/MPS可选训练、文件夹批量和独立简称／全称。

输入采用unity-WB 100MP合成色卡、PT前端、中心横向5点均值；R5实拍v2响应用于训练、压缩及预览，覆盖42/256颜色单元，其他区域外推。输出连续性在训练阶段约束明暗／色相／饱和度轨迹上的色度折返和过度放大，同时约束原生整数参数与最终整数网格；不增加照片处理步骤或BIN格式。

新版12项已全部完成，BIN v4共29,552字节，SHA256 `e3375e9f5fb8e32ae4dce5edab42c6024f1bc7d969abf7c2e01ded2b53419bc2`。下载的配置会完整替换自定义集合；名称用于说明模拟目标，非品牌官方产品。

## 固件发布范围

沿用用户指定的源码发布方式：公开4.34生产源码、构建／打包脚本与脱敏回执，不上传BODYDATA.DAT。完整固件的本地身份为754525608字节／BCD3404，SHA256 `1aeccd8f7fd6c1672b8fcd60ee1389c9b85a40a8aef51d6a720d898ecf9a1da9`。统一入口 `firmware/r5/build.py` 已合并全部固件构建代码；自行提供散列匹配的原始R5 4.00输入、外部签名材料和匹配工具链即可重建，无需旧版脚本、旧版产物或研究目录。详见固件目录的输入清单。

动态图标12状态对照、Fn注册／激活／返回、25项现有离线回归和最终DAT独立签名／CRC／全量解密已通过。实际LCD／刷新、升级／冷启动、AWB与新批滤镜机内成像仍待实机验收。Fn只增加手动可注册项，不自动分配槽位。主菜单左侧小logo按用户要求未继续研究。

旧Release和旧滤镜交付入口由本版替代；历史提交及发布回执保留。旧版构建目录已从当前分支撤下，当前构建代码全部在 `firmware/r5/`。原机备份、密钥、私人照片和训练运行目录不发布。第三方来源见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
