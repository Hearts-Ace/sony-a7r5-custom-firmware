# Sony A7R V / R5 自定义滤镜 4.35

4.35将冷启动与恢复启动分开：冷启动先校验SD上的BIN并原子替换内部配置，再激活一份CP配置；恢复启动仅加载内部配置，不扫描SD。正常冷启动避免先分配旧bank；坏BIN保留原配置。白色优先97、氛围−1、动态图标、Fn手动注册、R6 ST和FL2/FL3保持。实际机身电源/WBI、更新和拍摄仍待验收。

- [4.35完整固件源码与构建说明](firmware/r5/README.md)
- [macOS R5刷写工作台完整源码（Swift、scripts、AI CLI）](R5FlashWorkbench/README.md)
- [v4.5训练台与三格式色卡下载](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware/releases/tag/colorlab-v4.5) · [训练台源码](https://github.com/Hearts-Ace/sony-r5-colorlab/tree/main/R5ColorLab) · [高精度训练方案](https://github.com/Hearts-Ace/sony-r5-colorlab/blob/main/R5ColorLab/TRAINING.md)
- [新版12款滤镜：BIN、可编辑配置与完整训练设置](filters/FUJ_12_v45/README.md)
- [反推网格工作台](https://github.com/Hearts-Ace/sony-r5-colorlab/tree/main/R5GridCalibrator) · [R5实拍v2响应及来源](https://github.com/Hearts-Ace/sony-r5-colorlab/blob/main/R5ColorLab/web/data/r5/PROVENANCE.md)
- [唯一固件构建入口与复现说明](firmware/r5/README.md)
- [固件本地交付回执](publication/4.35/validation.json) · [训练完成回执](https://github.com/Hearts-Ace/sony-r5-colorlab/blob/main/publication/4.34/training_completion_verified.json)
- [唯一研究总结](https://github.com/Hearts-Ace/sony-r5-colorlab/blob/main/analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md)

## 固件构建入口

2026-10-30：4.35构建代码统一为 [firmware/r5/build.py](firmware/r5/build.py)。独立重编AP、CP和完整DAT，散列精确匹配4.35冻结输出。目录内含完整源码、补丁配方、原始输入/源码锁、恢复说明和复现回执；没有引用旧目录。

## Color training project

Color training, grid calibration and related technical documentation are now maintained in the separate public project: https://github.com/Hearts-Ace/sony-r5-colorlab. This repository retains firmware, flash workbench and the latest ready-to-use BIN.

## 固件发布范围

沿用用户指定的源码发布方式：公开4.35生产源码、构建／打包脚本与脱敏回执，不上传BODYDATA.DAT。完整固件的本地身份为754525608字节／BCD3504，SHA256 `76b06194aacd7b78553ad524e6d6fe0d7fc73edfae671e5ebc1e54bafe17ff74`。统一入口 `firmware/r5/build.py` 已合并全部固件构建代码；自行提供散列匹配的原始R5 4.00输入、外部签名材料和匹配工具链即可重建，无需旧版脚本、旧版产物或研究目录。详见固件目录的输入清单。

动态图标12状态对照、Fn注册／激活／返回、25项现有离线回归和最终DAT独立签名／CRC／全量解密已通过。实际LCD／刷新、升级／冷启动、AWB与新批滤镜机内成像仍待实机验收。Fn只增加手动可注册项，不自动分配槽位。主菜单左侧小logo按用户要求未继续研究。

既有Release保留其历史身份；当前源码与BIN以main为准。历史提交及发布回执保留。旧版构建目录已从当前分支撤下，当前构建代码全部在 `firmware/r5/`。原机备份、密钥、私人照片和训练运行目录不发布。第三方来源见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
