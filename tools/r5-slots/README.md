# R5 六槽回读与解放脚本

读取 ILCE-7RM5 的 `nflasha2`，在本机 `BACKUP.BIN` 和 `BACKUP.BAK` 中把六个 FL2/FL3 外观编号补为十进制 `10/11`（十六进制 `0A/0B`）。这能处理“菜单选择 FL2/FL3，拍摄页面仍按 ST 使用”的一种已验证存储原因。工具只修改槽位及其第一 BK4 bank 校验，保留颜色参数、第二 bank、UPDATER、FAT 和其他个人设置。

它配合已适配 FL2/FL3 的 R5 固件使用，不负责安装固件、颜色数据或公钥；也不添加固件内自动补写。每次 `unlock` 都重新读取当前机身，禁止把旧镜像或另一台机身镜像直接写回。

## 环境与自备材料

设备操作当前支持 macOS、Xcode Command Line Tools、Python 3.9+ 和 `cryptography`。需要对应的 RP2040 魔改线。`inspect`、`offline` 不访问设备。

```sh
python3 -m pip install -r tools/r5-slots/requirements.txt
cp tools/r5-slots/config.example.json tools/r5-slots/config.local.json
```

在 `config.local.json` 填入四份本机文件路径：

- 自备的原 RAM 入口 `bootloader脚本.zip`，其中包含 `bootloader脚本/a7m4fb.py`、`bin/fastboot.bin` 和 `lib/pyserial.zip`。三份输入分别按源内固定 SHA256 验证；入口包本身不随此仓库分发。
- **这台相机首次完整备份**的 65536 字节 SDM2 原始分区表和 49152 字节 AP BootROM，用于和当前新读内容逐字核对。不能使用项目作者或另一台相机的备份。这两份参考可能在同型号机身间相同，不是唯一序列号认证；本次设置的新采集及写前全区再次读取一致，才将写入绑定到当前连续会话。
- 公开上游 [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) 的 `payloads/fastboot/src/spacc.c`，用于独立验证当前 raw 与 logical 扇区。要求源码 SHA256 为 `e799ee731d5781ec6d41c998da77eb87c8c0e089df2614669e90f77e58523310`。仓库不分发密钥或该源码的提取内容。

USB 主机程序从本目录 `native/` 在新证据目录旁编译，无需预编译二进制。输出父目录必须存在，输出目录必须是新的；将输出放在仓库外，并保留原始设置/回读文件私密。

## 只读回读

连接魔改线，指定当前真实串口：

```sh
python3 -B tools/r5-slots/r5_slots.py read \
  --config tools/r5-slots/config.local.json \
  --port /dev/cu.usbmodem1401 --output /absolute/private/r5-read-001
```

命令会通过 RAM 入口复位机身，读取完整设置 logical/raw、分区表及 BootROM，逐扇区验证 AES-XTS、核对自备参考一致，然后正常 reboot。它不发送持久写入命令。槽位结果见 `pre.slots.json`，原始文件保存在同目录。异常时保留已经读到的证据。

## 六槽解放

```sh
python3 -B tools/r5-slots/r5_slots.py unlock \
  --config tools/r5-slots/config.local.json \
  --port /dev/cu.usbmodem1401 --output /absolute/private/r5-unlock-001
```

`unlock` 是明确的设备写入命令，按以下连续流程执行：新读当前全区并核对自备参考一致 → 双 BK4 校验及目标元数据检查 → 三次稳定只读 watchdog 检查 → 生成本次差异 sparse → 写前再次完整读取 logical/raw/分区表并确认不变 → Python 会话调用一次固定 hash 的 download/`flash:nflasha2` → 完整 20MiB logical 和 40960 个 raw 扇区回读核验 → 正常 reboot。

这里的一次写入由 Python 连续会话保证。原生 C writer 要求每次 flash 前先完整下载且 hash 精确匹配，但它并非全局单次写入状态机：单独调用它、再次下载相同 hash 后仍可再次 flash。公开命令行只提供上述完整 `unlock` 会话。

| Key | 目标 |
|---|---|
| `02cf0b69`、`02cf0b93`、`02cf0b97` | `0A` |
| `02cf0b6f`、`02cf0b95`、`02cf0b99` | `0B` |

仅接受原值 `00` 或对应目标，已正确的值跳过；其他值、bank 校验异常、设备变化或未识别 watchdog 状态均停止。最多允许两文件共20个字节、14个扇区变化，实际数量由新读镜像计算。全部槽位正确时不发 flash，只正常 reboot。写后核验异常时保留维护现场，不自动回滚。

完成后查看 `report.json`、`readback_verification.json`、`flash.log` 和 `reboot.log`。reboot 应答不替代实际启动、重启后保持、HUD 名称和照片颜色验收。`prepared/restore.sparse.img` 只对应那次写入前状态，工具没有把它作为自动恢复入口，后续不能直接刷回。

## 离线查看与候选

```sh
python3 -B tools/r5-slots/r5_slots.py inspect --image /private/current.logical.img
python3 -B tools/r5-slots/r5_slots.py offline --image /private/current.logical.img \
  --output /private/new-offline-candidate
```

离线候选只用于核对，不能跳过 `unlock` 的当前设备新采集与写前检查。请勿使用 `python -O`。

## 来源与验证

`PROVENANCE.json` 记录从本项目已执行六槽 builder、D/T 连续传输、FAT/BK4 和 sparse 工具提取、去除本机绝对路径的来源散列；`sources.lock.json` 约束这个公开目录的执行源。2026-11-05本机原流程已完成两文件六槽从 `00` 补成 `0A/0B`，实际6扇区/15字节、完整回读及 reboot 应答通过。公开路径/配置适配版通过离线同输入候选逐字对照、损坏 bank/未知槽拒绝、raw 解密和 native 编译；它尚未再次连接相机实测。原实机执行源和原始证据未改写。

此目录不包含个人设置、BootROM、镜像、私钥、分区密钥、RAM 载荷或设备原始日志。
