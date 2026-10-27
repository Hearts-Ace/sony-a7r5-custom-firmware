# Sony A7R V / R5 自定义滤镜 4.32

4.32修复控制轮只切换滤镜、菜单焦点和全称不更新的问题。旋转、上下键和触摸共用选择通路，移动即应用保存；确认或返回等待应用完成，再由原生菜单重建父页。保留4.31原生列表与错误分类、4.30启动/SD加载优化及4.22参数和网格生命周期。

- [4.32源码、最新版工作台和100MP色卡下载](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware/releases/tag/v4.32)
- [色彩工作台：直接目标网格拟合、100MP色卡、批量训练](R5ColorLab/README.md)
- [反推网格工作台：探针生成与JPG文件夹训练](R5GridCalibrator/README.md)
- [最新12款模拟滤镜：BIN及可编辑配置](filters/FUJ_12_direct_target/README.md)
- [R5实拍网格标定参数与来源](R5ColorLab/web/data/r5/PROVENANCE.md)
- [4.32实现与证据边界](analysis/r5_custom_menu432_wheel_20261028/README.md)
- [唯一研究总结](analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md)
- [独立交付校验](publication/4.32/firmware_delivery_verified.json)

固件仅用于ILCE-7RM5；本地构建产物754525608字节（不分发），SHA256 `f75f4a6efa286e3a6af0ed60cda6b92824d5ab18a8866cd167b9d2ec2b910e8b`。仅支持BIN v4，CC1、block13、129点Gamma及5×9×9网格统一导入/切换/关闭/原厂恢复。自定义编号与创意外观独立，原厂外观名称保持。SD有效BIN会完整替换配置集合。

当前工作台使用unity-WB 100MP合成输入、PT基线、中心5点均值；自动训练默认最终405节点整数网格直接拟合目标图，压缩后交替和灰阶微调关闭。R5实拍v2响应用于训练、网格压缩及预览，覆盖42/256颜色单元，未覆盖部分外推。下载色卡是GFX100S II RAF，非R5机身实拍；用于软件调色后导出同尺寸TIFF/JPG。

4.32的24份回执、30项检查及签名/CRC/全包逐字独立解密通过。用户确认4.31上下键正常，控制轮UI失败；4.32真实滚轮时序、LCD、冷启动及拍摄仍待机身验收。模拟与离线误差不代表机内成像通过。公开源码缺少Sony原机镜像、签名输入和部分研究依赖，不能从干净克隆一键重建完整固件。

旧问题升级包已撤下，历史源码/散列/日志保留。首次备份、原始DAT、密钥和私人照片不发布。第三方来源见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
