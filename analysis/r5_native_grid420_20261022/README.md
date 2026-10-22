# 4.20：SD 完整替换与 5×9×9 网格诊断

2026-10-22。本目录是本地冻结实现的固件源码公开副本。4.20 是离线验证候选，尚未完成新版本实机导入、启动、重启保持及成像验收；当前用户已确认的机身版本仍是 4.18。用户报告 4.19 SD 未覆盖，本轮没有该次实机失败日志，不能断言实际根因。

## 行为变化

- SD 根目录存在有效 `R5NATIVE.BIN`：按原生外观序号完整替换机内自定义配置，不合并，不以名称匹配，不因内容相同跳过写入。
- BIN 未列出的外观：清除其自定义名称、CC1、block13、Gamma 和网格，恢复原厂路径。原厂参数文件本身不改写。
- 零字节 BIN 或合法的零记录 v3 BIN：清空全部自定义参数，并持久保存规范空配置。
- SD 无 BIN：沿用已保存配置；损坏、读取或关闭失败时保留旧配置。
- 有效 SD 配置可替换损坏的内部旧文件。先清理本 worker 拥有的旧 `.NEW`，再暂存、fsync、读回检查、rename、目录 fsync。提交失败重载实际文件；rename 后同步失败属于提交状态不确定，不能保证断电持久性或声称已回滚。

仍是开机导入，未实现拍摄期间热更新。两个卡槽同时存在时沿用首个就绪卡规则，请把 BIN 放在选中卡根目录。

## 配置格式和清空工具

v2 非空配置兼容；v3 使用 `r5-native-overwrite-config/3`，每项增加 `grid_5x9x9: {enabled, coefficients}`，系数形状 `[3][5][9][9]`、整数 -64..63。每项独立启用，禁用项系数必须全零，顶层 `compensation_grid_enabled` 与记录启用状态一致。

BIN 头 128 字节，v3 每记录 2400 字节，最多 12 项、28928 字节。记录偏移 0–1175 与 v2 一致；1176 是 uint32 启用标记，1180–2394 是 1215 个有符号系数，2395–2399 必须全零。空 v3 是带正确型号、基线和 CRC 的 128 字节文件。PC response 矩阵和额外曲线不属于机内配置。

在仓库根目录生成并编译合成格式示例：

```sh
python tools/example_native420_config.py --output native_config.json
python analysis/r5_native_grid420_20261022/import/native_overwrite_config.py pack native_config.json --output R5NATIVE.BIN
```

清空全部自定义配置：

```sh
python analysis/r5_native_grid420_20261022/import/native_overwrite_config.py pack analysis/r5_native_grid420_20261022/clear_all/native_config.json --output R5NATIVE.BIN
```

清空操作仅适用于 4.20；清空后移除卡上的 BIN，避免之后开机再次清空。示例网格为合成开发参数，不是原厂或推荐拍摄配方。

## 原厂网格运行路径

以 4.18 原生颜色子链为基础，加入各外观独立的 5×9×9 网格，接入原厂选择点 `0x230ee0`、建表器 `0x231654` 和上传器 `0x414f44`。这一阶段替换原表，没有新增逐像素矩阵或曲线运算。AP/CP 参数容量同步扩展；CP 分配 52308 字节，其中最后 56 字节为诊断，原 bank/Gamma 偏移保持。

4.20 在建表、上传函数返回后记录状态，上传包装器保留两个栈参数。CP/render 回调只更新内存；文件写入由有限 AP worker 执行。真实 ISP 坐标、响应、完整控制器前置条件和实际颜色尚未验证，不能保证 PC 与机内逐像素一致。

## SD 诊断

选中 SD 根目录 `R5IMPORT.LOG`，每次开机首条截断，之后追加、flush 并 close。卡不可写、未就绪或底层文件系统失败时无法保证日志落盘。

数字为八位十六进制。mask 位 0..11 对应 ST/PT/NT/VV/VV2/FL/FL2/FL3/IN/SH/BW/SE。

- `BOOT420_SD_SELECTED`：构建号、卡槽（0/1）。
- `IMPORT_REPLACED_OR_CLEARED` / `IMPORT_KEPT_OR_FAILED`：结果、SD 字节数、解析 mask、当前 mask、原生读取状态、关闭状态、目录状态、旧文件加载状态、暂存状态、发布状态、目录释放状态、已保存 mask、卡槽。结果 0=导入，1=缺失，2=无效，3=I/O，5=提交失败；未执行状态 -99 显示 ffffff9d。
- `CP_CAPACITY_OK` / `CP_CAPACITY_FAILED`：phase、result、matched、mask、send 状态。
- `CP_PARAMETERS_SEALED` / `CP_PARAMETERS_NOT_APPLIED`：phase、result、matched、发送数、事务 phase、error、slot、mask。空配置没有参数需要传输，NOT_APPLIED 不单独代表清空失败。
- `GRID_STATUS`：启用 mask、选择 mask、建表 mask、上传返回 mask、最近回退原因、选择/建表/上传次数、最近 slot。
- `GRID_QUERY_SEND_FAILED` / `GRID_QUERY_TIMEOUT` / `GRID_QUERY_CLOCK_FAILED`：通信或时钟错误。
- `GRID_UPLOAD_RETURNED` / `GRID_NOT_OBSERVED_OR_FAILED`：预期网格、启用、选择、建表、上传返回、未观察到上传的 mask。

回退原因 1=空上下文，2=特殊模式/无效 bank，3=bank 未就绪/未封存/外观不匹配或缺项，4=网格关闭。E9 诊断使用 token/CRC、128 字节回复；最多 30 次查询、30 秒时钟预算。未在观察窗口选择某外观会记录未观察到，不能据此直接认定应用失败；上传返回不证明 ISP 像素正确。

## 本地冻结版本的验证

公开 JSON 来自本地候选的离线验证，已移除个人绝对路径，不代表在公开副本重新完成整包重建。

- 实际 AP worker：两种 PIE 基址共 152 场景；另有 6 次独立清空/无卡重启回放。
- C codec/传输：4095 个非空集合往返、4095 个传输集合及 32766 包；完整替换、规范空配置、UTF8 和畸形输入。
- AP/CP 实际指令：108 次参数传输、9 类恶意事务；104 次容量握手；E9 状态及 6 类畸形请求。
- 12 外观 × 4 种系数，三个 bank 原厂建表/模拟 MMIO 上传一致；8 种回退。原厂与包装上传器的两种栈参数路径、内存/MMIO/返回值/保留寄存器对照通过。
- 12 类日志/查询故障、持久化故障及 CC1/block13/BW/SE/loader/Gamma 回归通过。
- AP 分区只读 e2fsck、原有段/动态表和其余字节检查通过；4.20 DAT 验签、逐字节独立解密通过，BCD `2004`。

本地 DAT SHA256 `c6483a0a3f421251e08cb742b7dd5bfd7f2a5e65d3497dbcf8dec1b8255448be`，754525608 字节；AP `27c68273926a872955d88f89d6c5dec2eb13352559e983ce43e98a19e42fb039`，CP `c25b64c288a0b582363361771b424edcf1c86df44525e5c7aea9a55a2b1114ae`。本仓库不分发这些二进制。

## 复现依赖和公开调整

沿用 [公开范围](../../PUBLICATION.md) 的固定原厂输入、严格 4.04 分区/TAR、4.07 AP、4.13 AP 分区及外部参考树/签名依赖。网格回放另需匹配 `audit_sources.py` 固定散列的原厂 R5 CP；loader 回放需所列 NOR loader 描述符，均不公开。不是干净环境一键构建。

依次生成 `gamma/getter_build_dynamic`（通过 `getter_gates.build`）、执行 `cp/build_cp.py`、`import/build_ap_image.py --output <本目录>/ap --partition`，运行对应 test/replay，最后 `package_grid420.py --stage images` 和 `--stage package`。`ap/link_audit.json` 为本地链接产物的冻结索引，重建 AP 后须按实际符号和组件散列更新，不能拿旧索引替代新产物核验。

公开副本仅移除临时依赖路径、为 host 测试创建 objects 目录，并从固件打包 recipe 移除独立 Web 导出回执门控；固件回放与分区门控保留。SOURCE_MANIFEST.json 区分原件和公开副本散列。未提交 Web 页面、服务、训练任务或数据，未修改历史冻结源码和机身资料。
