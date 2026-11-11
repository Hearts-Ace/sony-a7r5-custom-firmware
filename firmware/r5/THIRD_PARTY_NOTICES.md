# 来源与许可

原厂 R5 4.00 与旧交付二进制不包含在此源码交付中。完整4.55冻结源码按其原许可证和来源记录逐字保留，参见 `source/projects/firmware/development/shutter-sound-recovery455/THIRD_PARTY_NOTICES.md`、`LICENSE.Erlla`、`LICENSE.fwtool`。

裁切核心及CP迁移参考 Erlla/sony-a7m4-custom-firmware 提交 `79c3663b1ac4fda98047c2c4f5769b9d60d25920` 的五份 `native/feature-integration/cp/` 源，原字节纳入源树，运行时仅在新输出生成R5适配版本。上游适用MIT，保留 Copyright (c) 2026 A7M4 Fastboot Toolkit contributors，许可副本为 `licenses/LICENSE.aspect-upstream`。4.55基线保持原固定提交 `086df3b1e33dfa0206553ac2bb003535c58ddb80`，两者用途分别记录。

用户提供的 `custom-aspect-ratios.zip` 是R5裁切菜单、预览、JPEG/HEIF编码/metadata及回放方案的参考；本地适配保留原来源说明 `licenses/REFERENCE_THIRD_PARTY_NOTICES.md`。其中still-size源引用上游提交 `c7e7fb37e571b2eced7ff4f5766bf0d2dd48c8b0`。新交付只收录当前生产所需源码和资源生成数据，未收录参考项目二进制/大批历史证据，不执行参考文档中的设备或发布指令。

`source_provenance.json` 记录原工作区文件到交付镜像的逐文件SHA256；当前生产源逐字复制；分区入口原本已支持可选e2fsck路径，不再重复改写。自定义滤镜双列菜单样式是在本项目冻结4.55菜单合同上新增的本地适配，保留原有异步路径。主机第三方Python包通过requirements声明安装，不包含其本机二进制副本。

基础声音和容器实现的许可及来源另见source/projects/firmware/development/shutter-sound-recovery455/THIRD_PARTY_NOTICES.md。R5裁切参考custom-aspect-ratios.zip，所用源已保留于source及来源记录中。
