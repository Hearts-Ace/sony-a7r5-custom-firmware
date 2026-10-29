# 来源与许可

本工作台用于个人非商业研究。

- USB／MSC 认证、会话、固定文件协议、备份和信任短事务参考并改编自 [Liwenru88/a7r5-rea](https://github.com/Liwenru88/a7r5-rea)，快照 `290c79e`。保留根 LICENSE、README 用途声明和 THIRD_PARTY_NOTICES，位于 `licenses/a7r5-rea-*`。原作者声明其原创部分仅个人非商业研究；第三方分别遵循各自许可。本项目不将仓库整体重新宣称为 Apache 许可。
- 改动：原生 SwiftUI 界面、独立运行封装、删除 SSH/强制安装入口；换用我们的签名公钥和严格原像/目标；信任写入计划改为26扇区；主机与载荷回执同步修改；固件构建与参考项目功能配方彻底分离。原始导入散列与来源见 REFERENCE.json；已改文件均注明改编。
- Sony-PMCA-RE、PyUSB 代码来自参考项目的固定 vendor 快照；许可证保存在 `licenses/trust`、`licenses/exec` 及相关包内。libusb 为 libusb-package 1.0.30.0 提供的 macOS arm64 动态库，LGPL-2.1-or-later，源项目 https://github.com/libusb/libusb ，源码标记 v1.0.30。随包保留许可证及来源说明。
- Python、NumPy、cryptography、cffi、PyCryptodome、Capstone、pyelftools 保留各包中的版权和许可证（engine/site 对应 dist-info）。Python 来自可搬迁 CPython3.12 运行时。
- 固件唯一构建入口来自本项目 `firmware/r5/`；其 fwtool 派生代码许可随该目录 `LICENSE.fwtool` 保存。原始 Sony 固件和签名私钥不随工作台分发。
- 相机端载荷采用源码构建，不包含参考项目的私钥、完整固件、原机分区镜像或四功能修改配方。Zig／Apple clang 仅用于开发机编译，不打进应用。
