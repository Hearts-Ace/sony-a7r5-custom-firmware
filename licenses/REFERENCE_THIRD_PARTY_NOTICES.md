# 来源与许可

`source/crop_core.c` 和 `source/crop_core.h` 等字节取自 Erlla/sony-a7m4-custom-firmware，固定提交 `79c3663b1ac4fda98047c2c4f5769b9d60d25920` 的 `native/feature-integration/cp/`，原文件及 SHA-256 保存在 [参考来源](reference/a7m4/SOURCE.json)。适用 [MIT 许可](reference/a7m4/LICENSE)，保留 Copyright (c) 2026 A7M4 Fastboot Toolkit contributors；上游明确将原创离线构建器和补丁源码纳入许可，见 [第三方说明](reference/a7m4/THIRD_PARTY_NOTICES.md)。

`source/preview_core.c` 依据同一提交的公开整数几何和方向说明独立实现。上游 AP 地址、CP 任务字段及构建输入仅作参考，不能作为 A7R5 的配方。`reference/` 中的参考文件保持原始字节，不覆盖。

`source/ap_still_size.S` 依据同仓库提交 `c7e7fb37e571b2eced7ff4f5766bf0d2dd48c8b0` 的 `native/aspect-playback/still_size.S` 移植，改为A7R5的12组精确尺寸及本机入口。保留 Copyright (c) 2026 A7M4 Fastboot Toolkit contributors，适用同仓库MIT许可。原文和来源摘要保存在[上游对照证据](evidence/a7m4-comparison-20261108/README.md)，没有覆盖旧锁定参考快照。

Sony 原厂固件和提取组件由用户本地提供，未复制进本功能源码或重新授权。证据仅记录身份、局部菜单记录和入口前像，不分发完整固件文件。
