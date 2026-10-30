# R5 刷写工作台 · macOS 研究版 0.2.1

面向 Apple Silicon Mac；最低编译目标 macOS 14。原生 SwiftUI 界面、包内独立 Python 和 libusb。运行备份、校验、导出无需安装 Python、Homebrew 或 Node；从源码重建固件另需 Apple Command Line Tools。

连接使用普通 USB／MSC，参考 Liwenru88/a7r5-rea 的固定事务协议。固件内容只使用我们的 4.36 统一源码，未采用参考项目的固件功能补丁和签名身份。个人非商业研究使用，来源及各自许可见 THIRD_PARTY_NOTICES.md 和 licenses/。

## 使用

1. 解压后将「R5 刷写工作台.app」移到「应用程序」。应用临时签名，未公证；系统若拦截，可在系统设置「隐私与安全性」中允许打开。启动不扫描 USB。
2. 首页「导出最新滤镜」选择存储卡根目录或文件夹即可。随包附带最新已完成的 12 款 `R5NATIVE.BIN`，不带滤镜训练工作台。需要固件时点击「固件＋滤镜一起准备」，选择我们的 4.36 DAT 与目标目录。离线自检可检查应用完整性。
3. 需要准备更新信任时，使用普通数据线连接一台 ILCE-7RM5，机身选择 MSC。在「USB 维护」先备份更新器分区；macOS 会请求管理员授权。备份会短暂进入服务会话，使用 RAM 临时载荷两次读取更新器分区，保存并完整核对后清理本次 RAM 副本。没有整机备份功能。
4. 备份回执若显示「已匹配我们的签名公钥」，无需重复安装。只有精确原厂前像才支持安装公钥；未知前像停止。标准安装只写我们公钥与更新器校验所需的 26 个逻辑扇区（13,312 字节），写前核对整个当前分区，写后两次完整回读。无强制安装、自动回滚、设置分区改写或 fastboot 流程。
5. 「固件＋滤镜一起准备」将 BODYDATA.DAT 和 R5NATIVE.BIN 放到存储卡根目录，复制后完整读回。相同文件跳过，不同旧文件先保留到 `.R5Workbench-backups/`。导出完成不代表升级完成。随后在机身固件版本页启动存储卡更新，按机身提示操作。
6. 失败时查看「任务记录」。服务进入后没有完整回执时，设备锁会阻止重复事务。只在前次完整终态允许的情况下执行「USB 恢复观察」；不会重发写入或 STOP。不要删除锁绕过失败现场。

设备日志保存在 `~/Library/Application Support/R5FlashWorkbench/Tasks/`。全应用设备事务锁和未完成记录在 `/private/var/db/R5FlashWorkbench/`，不与训练工作台共享目录、端口或进程。

## 附带滤镜与 AI 操作

附带最新已完成的 v4.5 连续性30合包，2026-10-29完成，12款：AS、CC、EBB、ET、NC、NH、PV、RA、VN、理光正片、理光负片和 Portra400NB。后三项简称为正片、负片、Portra400。29,552字节，SHA256 `19e020fa48c79643aaf9526e9c720d38ec5a92c3df11d0852b0a93a25ee880b6`；精确来源见 `engine/filters/manifest.json`。这里 v4.5 是训练数据版本，BIN 结构仍为固件支持的 v4。

「AI 助手」可复制给 AI 的说明，粘贴后补充自然语言要求。支持本地 AI 直接调用应用内 `Contents/MacOS/r5wb`：describe 发现能力、plan 查看计划、prepare 导出、status/result 查看回执。stdout 单一 JSON，进度 stderr；无需内置模型或 API Key。详见 [AI_GUIDE.md](AI_GUIDE.md) 与结构化 `engine/agent-manifest.json`。

## 固件内容

4.36：固定 C.Look 图标、自定义滤镜 Fn 手动注册、R6 ST 可反推参数、FL2／FL3 参数保留、白色优先 97／氛围 −1、自定义滤镜及网格。导出仅接受冻结 DAT：

```
754525608 bytes
57cfc5ff55a71685e95b7b6420d1270bd09dbb140822ad8dceb0a0c9002d9938
```

重建功能直接调用随应用附带的 `firmware/r5/build.py`，无需旧脚本或旧产物。普通入口选择原厂 R5 4.00 DAT 和匹配公钥的外部签名私钥；工作台只读解码原厂 DAT，自动提取、逐项核对输入，然后交给统一构建入口。高级入口支持该目录 `inputs.example.json` 所列的已有原始输入。私钥要求 0600；应用、ZIP、日志均不包含私钥内容，任务配置仅记录输入路径。请自行保留所选输入配置的隐私。

原始输入提取约需 2.3 GB，另需完整构建空间，建议预留 8 GB。提取产物保存在该次任务的 original-inputs 目录，便于复用和恢复；原始 DAT 与私钥不复制进应用。以后可在高级入口选择其 inputs.json。不会自动清理这些已核验输入。

此版不把完整固件或原机镜像打进应用。工作台不通过普通 USB 直接刷 AP／CP；MSC 维护用于准备更新信任，完整固件通过存储卡交由原厂更新器安装。

## 验证边界

离线验证涵盖：固定载荷 AArch64 ELF、配置字段替换与独立编译一致、26 扇区配方完整重建、未知前像与模拟备份拒绝、USB 会话失败/STOP约束、固件 SHA 和导出读回、应用签名及搬迁后隔离自检。历史0.2离线验证仅对应当时版本；当前源码发布检查见仓库 publication/4.36/validation.json。

**本工作台未做实机 USB 接管、公钥安装、卡刷、正常启动或拍摄验收。** 本机编译及测试结果不替代上述验收。最低系统版本是构建目标，尚未在所有 macOS 14+ 版本测试；Intel Mac 未支持。

## 源码构建

应用源码独立位于本目录；`engine/` 是已适配固定协议，`sources/trust/` 是对应相机端源码，`scripts/prepare_payloads.py` 编译固定载荷，`native/Workbench.swift` 是原生界面。

首次从上游导入和生成信任配方使用 `scripts/import_reference.py`，只处理本地文件。调用需显式提供参考源码、经散列锁定的原厂和候选逻辑分区；历史整分区不作为设备写入输入，运行时只使用新备份并核对当前完整前像。

准备载荷需 Apple clang、Zig 0.13 的 ELF lld 和 pyelftools；调用 `prepare_payloads.py --zig /path/to/zig`。打包调用 `scripts/package.py --python-runtime /path/to/python3.12-runtime --extra-site /path/to/packages --firmware /path/to/firmware/r5 --public-key /path/to/public.pem --sony-public-key /path/to/original-public.pem --output /new/output`；额外 packages 包含 pycryptodomex、capstone、pyelftools、libusb-package，基础运行时提供 numpy、cryptography、cffi。完整依赖版本、来源和构建命令保存在交付证据中。

本次提交为0.2.1完整源码，固件校验目标同步4.36；已有应用ZIP保留各自历史固件目标；本次只更新源码，未重打应用包。签名公钥也由打包者外部提供，不在Git中附带。
