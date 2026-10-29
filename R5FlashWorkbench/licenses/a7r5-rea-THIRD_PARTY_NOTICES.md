# 来源与许可说明

项目作者声明：对于其有权授权的原创代码、文档和整合实现，**仅限个人非商业研究使用，禁止商用**。具体使用范围见 [README 用途声明](README.md#使用范围与非商用声明)。公开托管与提供研究签名身份，不表示授予商业用途。

这项声明不修改、撤销或额外限制第三方原有许可证授予的权利；不能将其作为覆盖整个仓库中所有第三方材料的新许可证。

第三方材料保留原有权利与许可证，不能由根目录说明覆盖：

- DAT 工具：[现有许可证](a7r5-dat-tool/licenses/)、[源码来源清单](a7r5-dat-tool/SOURCE_FILES.json)。
- 转存与执行工具：[实施工具包许可证](a7r5-implementation-kit/licenses/)、[执行工具许可证](a7r5-exec/licenses/)。冻结的 Sony-PMCA-RE、PyUSB、PyCryptodome 代码与发行包许可证也保存在各依赖快照中。
- 信任模块：[第三方说明](a7r5-updater-trust/THIRD_PARTY_NOTICES.md)、[上游许可证](a7r5-updater-trust/reference-LICENSE)、[其他许可证](a7r5-updater-trust/licenses/)。
- 四项功能：[材料说明](a7r5-firmware-features/materials/NOTICE.txt)；配方不赋予原厂固件或商标的所有权。
- QEMU：[固定源码清单](a7r5-qemu/source/qemu/manifest.json)、[许可证目录](a7r5-qemu/source/qemu/licenses/)及源码补丁；原始源码压缩包仅保留本地。
- Rust 依赖版本保存在 `a7r5-desktop/src-tauri/Cargo.lock`，Python 依赖保存在各 requirements 文件中。最终应用版权汇总由 `a7r5-desktop/scripts/notices.py` 在本地生成。

完整 Sony 升级包、提取分区/库、设备快照和本地测试安装包不属于本次 Git 候选文件集。对外分发这些材料前，需要另行确认相应分发条件；公开源码仓库不携带它们。
