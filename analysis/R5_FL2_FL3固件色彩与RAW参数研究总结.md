# R5 FL2／FL3固件色彩与RAW参数研究总结

> 公开整理版：完整保留研究与历史刷写步骤。脚本散列表记录D／T本地执行原件；公开副本的路径调整及禁用旧入口见发布说明（本地证据：`../PUBLICATION.md`，未公开）与[SOURCE_MANIFEST.json](../SOURCE_MANIFEST.json)。本仓库不含机身镜像和引导载荷，不是克隆即可刷写的安装包。

更新于2026-10-17。本文是本工作区这项研究的唯一总结，合并原十字段分析、换算表、共用字段追查及刷写／跨代色彩总结。后续结论在本文更新；原始JSON、核验脚本、反汇编及实机日志仍保存在原目录。

研究对象为Sony A7R V（R5）4.04，按Erlla A7M4方案适配，固定上游提交`086df3b1e33dfa0206553ac2bb003535c58ddb80`。当前状态以开发记录（本地证据：`../DEVELOPMENT_RECORD.md`，未公开）及对应实机日志为准。

**结论：CC1、block13和Gamma与RAW十字段已有精确数值对应；此前共用的780C／D／E和780F其余84字节，也已找到原厂来源并补齐分段指令核验，未发现因此遗漏滤镜参数。没有依据为这些共用字段额外刷写。** 这些证据不能穷尽完整ISP，也不能替代重启保持、全部拍摄模式与实际成像验收。

本次仅整理本地文档，未操作相机，未修改固件、部署脚本、照片或初始备份。较早报告中“共用字段未定位”的调查状态已由本次追查结果替代，不再保留相互矛盾的阶段性说明。

## 一、完整刷写方案

### 0．适用范围、当前状态与执行顺序

本方案针对本工作区已核验的R5 4.00 CN2基线、匹配的本机签名身份与4.04交付物，不能直接套用到另一机身／地区／版本。文中命令供后续实际部署时使用；本次文档整理没有运行设备命令。

从原厂状态首次安装时，作者顺序是：**进入fastboot并备份→建立自签信任环境→部署本机个人设置／颜色→正常启动并SD升级→升级后重新读取和验收，必要时重建设置。** 用户要求的四部分按“备份、校验镜像、SD升级、升级后系统覆盖参数”组织；作者的SD前设置部署使用第4步同一套流程，SD后仍须核查。

本机的实际记录是：一号分区信任环境已部署；D在4.03状态写入设置并回读；之后手动升级4.04；I发现六槽及颜色记录等于原厂，但两处CP已是目标4.04；T再次基于新回读部署设置成功。只有D／I两快照不能确定设置恢复发生于首次重启、SD更新或后续初始化，因此不把“SD必定清零”写成规则。

| 机身目前状态 | 需要做什么 |
|---|---|
| 首次安装、未建立本机自签信任环境 | 完成本节全部环节，先核实一号分区基线，再制作对应候选 |
| 已建立匹配信任环境、尚未安装4.04 | 核对当前状态与备份，按作者顺序部署设置，再SD更新，更新后重新验收 |
| 已是4.04且设置缺失 | 基于当前新回读执行第4步；不要为补设置而重刷DAT或一号分区 |
| 已写入目标设置、仅缺重启后验收 | 先执行只读回查和实拍；确认缺失后才重新部署 |
| 正在SD更新、升级中断或不能正常启动 | 不套用正常安装命令；先保留现场与日志，单独判断恢复路径 |

### 准备：设备、文件与主机依赖

1. 使用供电稳定、达到原厂更新电量要求的本机电池；确认没有正在进行SD更新，记录当前版本及电源状态。同一电脑只连接这台待处理机身。
2. 改装线连接相机Multi口，负责复位和串行引导；另用USB-C数据线连接相机与电脑，负责fastboot数据传输。已有成功记录不能证明ON或OFF是进入的必要条件，操作前须记录实际状态。
3. 使用现有RP2040 `uart_boot 1`固件：GPIO28→相机RX、GPIO29→相机TX、GPIO27→复位，`OPEN_DRAIN`构建，链路48000波特。构建和UF2身份见魔改线构建记录（本地证据：`../build_uart_boot_20261013/README.md`，未公开）。已正常工作的改装线不需重新刷写UF2。
4. 主机使用本工作区`.venv/bin/python`；USB工具在`analysis/r5_live_system_20261014/host_tools/`；部署过程中用macOS的`/usr/bin/clang`、IOKit、CoreFoundation编译限定写入程序。先准备好依赖再进入，不能在fastboot内等待安装工具。
5. 原工具包位于`${R5_BOOTLOADER_ZIP}`。已执行源码副本保存在D会话的`execution_source_snapshot/`，但当前脚本仍读取原工具包路径；不可仅移动工具包而不检查依赖。
6. 首次备份、源DAT、R5／FX2原始解包、严格4.03构建源、本机公私钥、4.04构建及执行脚本保持原样。历史失败4.03和旧两槽脚本不作为入口。

以下命令从工作区根目录执行。先用只读文件枚举确认本次串口，再填写`R5_PORT`；示例`/dev/cu.usbmodem101`不是永久端口。所有会话目录必须是新的、尚不存在的路径：

```sh
cd ${R5_WORKSPACE}
python3 -c 'from pathlib import Path; print("\n".join(str(p) for p in Path("/dev").glob("cu.usbmodem*")))'
R5_PORT=/dev/cu.usbmodem101
R5_SESSION_TAG=$(date +%Y%m%d_%H%M%S)
```

执行前核对四个核心脚本，预期值如下；不要修改脚本来放宽校验或调整进入时序：

```sh
shasum -a 256 tools/run_r5_m4strict_personal.py tools/deploy_r5_m4strict_personal.py tools/r5_settings_ram_boot.py tools/build_r5_m4strict_personal.py
```

| 脚本 | D／T使用的SHA-256 |
|---|---|
| `run_r5_m4strict_personal.py` | `658afda1a6eb9235f9d48096b604e943a2b71fbf99dc9c19a68af355df978675` |
| `deploy_r5_m4strict_personal.py` | `e189cda6405ca03fd9f0617ebf4677d63c90d17553a3623efc6adacbdc716120` |
| `r5_settings_ram_boot.py` | `80b79977a51bdfdfb5d8947ff92192ec04d803df3dbc2d0f79d2a634500329d8` |
| `build_r5_m4strict_personal.py` | `a95187c2d6dcb5633f74c35f10ab5a687216b624f542a7af56a5dd79763132ce` |

### 1．进入fastboot与备份

#### 1.1 入口动作和成功判据

原入口依次执行RP2040握手→相机复位→开启载波→等待原工具的`TRANSMIT_START`（0.5秒）→按`boot_script`发送引导记录及间隔→关闭载波→切换115200波特接收输出→配置相机USB接口并查询fastboot。

发送的是临时SRAM载荷及引导参数，不是向机内存储分区刷写`fastboot.bin`。这一步仍会复位并运行临时代码，不能承诺零风险，也不能把历史红屏直接诊断为持久fastboot分区损坏。保持已核验载荷SHA-256：`330ac322bd0e40a7bb4974f69a2667e7d59a25e59c1322339690f30a3ceadbdc`。

需要单独进入并进行最小只读身份探测时，可使用：

```sh
R5_ENTRY_RUN="analysis/r5_entry_${R5_SESSION_TAG}"
.venv/bin/python -B tools/r5_settings_ram_boot.py --port "$R5_PORT" --output "$R5_ENTRY_RUN"
```

该入口会查询版本、分区表和设置区首扇区，保存UART、USB查询及`report.json`；**不会主动正常reboot，也不执行持久flash**。成功要求`usb_transport_verified=true`及协议`OKAY0.5`，不能只看短暂黑屏或串口是否出现ready文字。USB描述符和product来自载荷常量，必须继续用本机分区表／ROM核验身份，不能据此认定机型。

首次完整备份和第4步连续部署都自带入口，不应在它们之前机械执行这条单独进入命令。仅单独探测结束且没有待评估写入时，正常退出命令为：

```sh
analysis/r5_live_system_20261014/host_tools/read_fastboot_usb reboot
```

#### 1.2 首次完整采集的范围

本机首次资料固定保留在原机备份目录（本地证据：`../backups/R5_4.00_20261014_full/`，未公开）和[首次采集目录](r5_live_system_20261014/)，禁止覆盖、删除、移动或改写。已采集内容包括：

| 对象 | 保存与核验要求 |
|---|---|
| 17个有效SDM2用户分区 | 各完整logical镜像，记录分区起点、扇区数、长度和SHA-256 |
| 已分配用户区raw与SDM2表 | raw覆盖表内最大已分配范围；按绝对扇区AES-XTS独立解密，与所有logical逐字节比较 |
| eMMC boot0／boot1 | 原始镜像各重复采集两份并比较；不作为日常设置恢复目标 |
| 独立CP NOR | 保存原始物理NOR、分段及拼接证据，不能用eMMC CP镜像替代 |
| AP／CP BootROM | 保存ROM参考、采集日志及散列；ROM不是刷写目标 |
| 清单与恢复边界 | 保留`manifest.json`、`verification.json`、`SHA256SUMS`及`restore_inventory.json` |

这是现有清单范围的完整采集；未独立读取EXT_CSD证明整颗eMMC物理容量，不能称已经克隆芯片全部物理空间。

完整采集入口为[backup_r5_all.py](../tools/backup_r5_all.py)，离线核验为[verify_r5_full_backup.py](../tools/verify_r5_full_backup.py)。**它们是历史采集工具：采集间接调用的`r5_boot_probe.py`写死串口`/dev/cu.usbmodem101`，不是通用的`--port`入口；端口不匹配时不能照抄执行，也不要修改已留证源码。** 仅在端口、目标和依赖均匹配、已决定新采集时，命令形式为：

```sh
R5_FULL_RUN="backups/R5_new_acquisition_${R5_SESSION_TAG}"
.venv/bin/python -B tools/backup_r5_all.py --output "$R5_FULL_RUN"
.venv/bin/python -B tools/verify_r5_full_backup.py "$R5_FULL_RUN"
```

第二条会在指定目录写核验结果与恢复清单，因此只能用于本次新目录，**不得对首次备份目录重跑**。前一条只有完成采集后才能进入完整核验；`partial`需按原日志和`resume_r5_raw_backup.py`的限定条件评估补采，不能当成功。原采集包含正常reboot，长传输可能因接口消失分会话补读；没有完整日志、大小和散列就不能进入持久写入阶段。

当前机身已有首次完整备份，后续个人设置修复不必每次重读全部分区，但必须由第4步重新采集当次设置logical/raw、SDM2与AP ROM。历史备份用于身份和恢复参考，不能替代当前设置输入。

### 2．刷写校验相关镜像，建立匹配签名环境

#### 2.1 具体修改与作用

此步处理更新器信任，与FL2／FL3颜色设置、DAT的AES解密不同。使用本机原有RSA密钥对，机内`nflasha1`的`/boot/initrd.img`中替换`/etc/VerificationKey.pem`；四个更新库的`verifyKey()`入口各覆盖8字节，使其返回0：

- `/usr/lib/libupdaterapi.so`
- `/usr/lib/libsdfileinputupdaterapi.so`
- `/usr/lib/libseninputupdaterapi.so`
- `/usr/lib/libuudfileinputupdaterapi.so`

后续`VerifySignature`／RSA验签代码保持原样，DAT仍需由匹配私钥签名，不能安装任意未签名文件。同步重算`p1chksum`，保留FAT和SquashFS元数据。这里绕过的是原公钥信任检查；**4.04没有新增同版本／降级条件绕过**，其检查仍按交付包原有逻辑执行。

#### 2.2 候选、写入与回读

已有候选位于一号分区构建目录（本地证据：`../build_r5_partition1_verifykey_skip_20261014/`，未公开），logical镜像为`nflasha1.R5_4.00.custom-key.verifykey-skip.logical.img`，25,100,288字节，SHA-256：`0ec7813c78f121f5abced7fc24350e34ac4cffa4ec8be4d1ecccee22f3d4922d`。公钥身份SHA-256为`4cb3cf8cc7a847a5b6108863c2defa327ceb06280c1dda468cd57c3dd3cae859`；不在本文复制私钥。

实际已执行的流程是：

1. 核验首次备份、候选、公钥、私钥配对及四处RSA函数未改；两个独立文件系统解析器核对目标仅涉及PEM／四个库及对应校验。
2. 基于当时机内已验证的“仅换公钥”一号分区制作正向／反向稀疏差异，限定USB写入程序接受的目标与下载散列。
3. 在同一新会话进入fastboot，读取当前SDM2、AP ROM、完整一号分区logical/raw。目标几何应为起始`0x80`、长度`0xbf80`个512字节扇区；独立解密与当前预期基线完全相同才继续。
4. 只发送候选稀疏数据及`flash:nflasha1`，当次设备应答写入233扇区。
5. 重新读取25,100,288字节完整logical/raw及SDM2：logical精确等于候选，49,024个raw扇区独立AES-XTS核验通过，logical/raw变化扇区一致，分区表不变。
6. 全部通过才正常reboot；记录应答和用户恢复拍摄确认。

历史入口为[flash_r5_verifykey_skip.py](../tools/flash_r5_verifykey_skip.py)，其`--prepare-only`与`--flash --port …`分别对应准备和写入。但它固定旧基线、旧候选、旧会话目录，并拒绝已有记录；**不能作为当前新会话的可直接重跑命令**。旧稀疏文件与`restore`同样绑定当时前置状态，不能覆盖当前机身。新机身／不同基线需要另行制作适配的新会话入口，不通过删除历史目录或改固定散列来重用它。

本机该步骤已实际完成，原始部署报告（本地证据：`r5_verifykey_skip_flash_20261014/report.json`，未公开）、flash日志（本地证据：`r5_verifykey_skip_flash_20261014/flash.log`，未公开）及独立回读核验（本地证据：`r5_verifykey_skip_flash_20261014/independent-readback-verification.json`，未公开）均保留。已具备匹配信任环境时跳过重复写入；若怀疑当前环境变化，先新读判断，不能据历史记录断言当前仍相同。

为保留完整历史顺序：本机先通过`build_r5_partition1.py`／`flash_r5_partition1.py`部署仅换公钥的中间镜像，再完成上述verifyKey修正。该中间态SHA-256为`7d17697fb83a26bbcd53f49f7c791fea7cdd9e372ad6f4510d1f079e643a0b05`；它不是最终信任环境，不能只刷中间态就认为全部完成。已有两个历史写入入口均绑定当时状态；新部署应先新读并生成从当前状态到最终候选的已核验差异，不要求机械重走两次历史写入。

### 3．准备已核验DAT，通过SD卡升级

#### 3.1 交付文件和离线检查

使用当前4.04 DAT（本地证据：`../build_r5_m4strict_4.04_20261015/BODYDATA.DAT`，未公开），754,525,608字节；不要使用工作区根目录同名原始包或失败旧4.03。核对文件身份：

```sh
shasum -a 256 build_r5_m4strict_4.04_20261015/BODYDATA.DAT
```

预期`370cd17d50b086e466b987918a95297213eee5dc9f962c77a88f65afdc117dd1`。本次构建的verification.json（本地证据：`../build_r5_m4strict_4.04_20261015/verification.json`，未公开）记录736,841块完整独立解密、751,577,088字节明文逐字节匹配，RSA／OpenSSL验签、篡改拒绝、外层CRC及组件一致性全部通过。这里只证明封装与输入一致，不能替代实机安装结果。

已有交付包无需重新构建。开发时如需复现，两种离线入口任选其一，输出目录必须新建：

```sh
.venv/bin/python -B tools/build_r5_m4strict404.py --build "build_r5_404_repack_${R5_SESSION_TAG}"
```

```sh
.venv/bin/python -B tools/build_r5_m4strict_release.py --version 4.04 --build "build_r5_404_from_stock_${R5_SESSION_TAG}"
```

第一条依赖保留的严格4.03构建源；第二条从原厂组件及固定供体重建，需要全部本地依赖和可运行的CP指令模拟环境。两者都不访问相机，不以失败旧4.03为输入。新构建核对它自己的报告与组件身份；不能直接拿旧DAT散列代替新产物核验。

#### 3.2 SD包改了哪些内容

| 组件／位置 | 部署内容 |
|---|---|
| `nflasha15`中的AP | FL2／FL3已有菜单资源、flags、look支持及look10／11→CP color19／20路由 |
| `nflasha8`中的CP | profile54～57选择、CC1／矩阵读取与合法范围、四行内嵌CC1、六条完整Gamma及ID47～50路由、名称和元数据支持 |
| `nflasha5`暖启动镜像 | 经审查的`WBI2→WBI3`标识变化，用于避免恢复旧暖启动快照 |
| 分区校验清单／DAT头部 | 依赖CRC、版本4.04及匹配签名 |
| 原厂更新主体 | 保持原字节；包含原有条件性CP NOR更新链 |

TAR只改AP／CP／WBI三个镜像成员及分区校验成员；原厂默认模板和`backup.sum`不变，个人设置不嵌入通用DAT。不加入旧两槽强制默认／初始化／写保护，不加入项目曾多加的SD设置迁移、Backup专项同步、回读、finalizer、重复WBI清头、成功标记或完成门槛。

#### 3.3 存储卡与机身操作

1. 若是首次按作者顺序安装，先完成第4步的SD前个人设置部署，并确认写后回读和正常启动；不能以DAT签名完成代替颜色数据已部署。
2. 使用相机支持、符合原厂更新要求的存储卡。将**已验散列**的4.04文件以精确文件名`BODYDATA.DAT`放到卡根目录，复制后再次核对卡上文件散列。
3. 线刷会话须已正常结束、相机已恢复拍摄界面。断开改装线及USB数据连接，按本机原厂菜单／指定卡槽的SD更新流程操作，遵守机身电量和版本提示。
4. 更新中保持供电、不要取卡或拔电。1／3／5次闪灯是原厂计时显示，不能视为写入进度或某个分区已完成；不要按灯的次数决定拔电。
5. 以机身更新完成提示、正常重新启动及版本页为基础确认安装，再进入更新后回读。版本页4.04仅是一个验收项，不单独证明AP／CP／NOR及颜色设置全部正确。
6. 若原厂拒绝同版本，停止并保存提示；本4.04没有增加同版本绕过。若长时间异常或出现错误，记录开始时间、屏幕、灯节奏及供电状态后单独排查，不能把本方案当作升级中断后的恢复保证。

原厂`nor_loader_writer.sh`／`nor_update`链受LSI和boot type等条件控制，可能处理loader区域；“保留该链”不等于每次都已经运行成功。只通过fastboot写`nflasha8`不会执行这条原厂链，不能用其替代本步，也不手工照搬M4 NOR写入命令。

### 4．基于新回读，线刷个人设置与颜色覆盖参数

#### 4.1 允许改动的完整清单

设置位于本机`nflasha2`的`BACKUP.BIN`和`BACKUP.BAK`；20MiB、40,960个512字节扇区，起始绝对扇区`0xc000`。R5 `nflasha6`已识别为gridline／Jiritsu相关存储，保留，不照搬M4分区号。

| 记录 | current／still／movie属性ID或范围 | 目标 |
|---|---|---|
| FL2六槽中的三项 | `02cf0b69`／`02cf0b93`／`02cf0b97` | 均为`0A` |
| FL3六槽中的三项 | `02cf0b6f`／`02cf0b95`／`02cf0b99` | 均为`0B` |
| CC1 `02a40001`映射 | 属性内`0x1236..0x1239` | `[22,24,23,25]` |
| CC1四行有效系数 | `0x1250 + bank×64`，bank22～25各48字节 | 作者转换后的FX2差分系数，保留原格式和其余标定 |
| block13 `02a4000d`映射 | 属性内`0x1cc..0x1cf` | `[22,24,23,25]` |
| block13四bank | 属性内`[0x43e0,0x4fe0)`，共3072字节 | 指定FX2供体矩阵 |
| BK4校验和 | 各段`+0x20`的4字节字段 | 重算该段byte sum，排除自身4字节 |

BIN和BAK两份同时处理；六槽记录必须长度1、属性`0x60`，前值仅接受00或对应目标值。颜色基线、供体、结构均有固定散列及范围核对；其他文件、FAT布局、个人标定、版本文件及升级标志保持原值。

#### 4.2 实际连续部署入口

准备新会话目录并确认相机正常、未更新、两条线已接好后，使用D／T验证过的入口：

```sh
R5_SETTINGS_RUN="analysis/r5_personal_deploy_${R5_SESSION_TAG}"
.venv/bin/python -B tools/run_r5_m4strict_personal.py --port "$R5_PORT" --run "$R5_SETTINGS_RUN"
```

**该命令会复位相机、进入fastboot、执行限定持久写入，成功后正常reboot。** 不另行先进入fastboot，不在备份后停几分钟再接着写。该脚本连续完成：

1. 校验核心源码、工具包模块、pyserial与原始RAM载荷身份，并保存本次执行工具散列。
2. 进入接口后核对协议和分区几何；采集当前SDM2、AP ROM、完整设置logical/raw，与本机首次身份资料比较，并逐扇区独立AES-XTS解密核对。
3. 只读执行3次`oem darwin`，间隔5秒，要求状态稳定；写前再查一次。接受已审查的FF或持续00停走状态，不发送看门狗修改命令；未知／活动／变化状态直接停止。
4. 在新备份上生成候选、正反向稀疏差异和限定写入程序。检查两套BK4解析、六槽、颜色字段、所有非目标文件与FAT布局不变；候选重复处理应幂等。超出64扇区或6600字节的保护上限拒绝，不把上限当每次应写数量。
5. 若候选已经等于当前设置，记`already_target_no_write_needed`，不发送flash并正常reboot；这不是又刷了一次。
6. 写前完整重读设置logical/raw及SDM2，要求与本次刚采集完全一致。检查下载散列和候选未变化，禁止拿历史D／T的patch或restore替代本次生成物。
7. 在同一USB写入进程完整接收已批准的稀疏下载后，只发送一次`flash:nflasha2`，核对设备应答的扇区数与本次差异一致。
8. 完整读取写后20MiB logical/raw及SDM2；logical逐字节等于候选，全部40,960个raw扇区独立解密匹配，raw／logical变化扇区一致，SDM2不变，再核验目标字段和非目标范围。
9. 全部通过保存`readback_verification.json`，才发送正常reboot；用户确认恢复拍摄。完成状态应为`written_verified_reboot_acknowledged`。

会话D为30扇区／3710字节，T为30扇区／3711字节；差1字节与各自设置／校验前态有关。它们是历史结果，不是可盲套到每台机身的固定写入数。

#### 4.3 本次目录必须留存的文件

| 文件 | 用途 |
|---|---|
| `report.json`、`ram_boot/`与各阶段日志 | 入口、时间、接口、执行散列、是否已发送持久写入及reboot结果 |
| `pre.settings.logical.img`／`pre.settings.raw.img` | 当次新读取的写前完整设置 |
| `pre.sdm2.raw.bin`、`pre.ap_bootrom.bin` | 同机身及几何核对资料 |
| `prepared/candidate.logical.img`、`prepared/verification.json` | 当次候选、目标字段与实际差异 |
| `prepared/patch.sparse.img`、`prepared/restore.sparse.img` | 仅绑定本次前置状态的正反向差异；restore生成不代表已执行或随时可回滚 |
| `prewrite.*`、`immediate_prewrite.log` | 发送flash前最后一次完整再读 |
| `flash.log`、`post.settings.*`、`readback.log` | 唯一写入应答及完整设备回读 |
| `readback_verification.json`、`reboot.log` | 独立解密、目标一致性及正常重启应答 |

底层`deploy_r5_m4strict_personal.py`的`acquire`／`prepare`／`write`用于实现上述环节；日常部署使用连续入口，避免手工拆步导致接口超时。`build_r5_m4strict_personal.py`仅生成离线副本，不读设备、不证明输入新鲜，也不能用其输出直接覆盖现在的相机。旧`modify_r5_slot_settings.py`等仅保留被导入的通用函数，不运行其旧独立入口。

### 5．SD更新与正常重启后的只读回查

第4步写后回读发生在reboot之前，只证明“当次写入已落盘”。正常启动后需再次采集，验证六槽和颜色是否保持；同时核查SD更新后的CP存储和WBI。采用I会话成功过的只读入口，另开新目录：

```sh
R5_CHECK_RUN="analysis/r5_postboot_check_${R5_SESSION_TAG}"
.venv/bin/python -B analysis/r5_fl23_st_color_audit_20261016/acquire_readonly.py --port "$R5_PORT" --run "$R5_CHECK_RUN"
```

该脚本载入原固定RAM入口，核实SDM2／AP ROM，读取20MiB设置logical/raw、eMMC `nflasha8`、CP NOR窗口、`nflasha10`和WBI头，最后尝试正常reboot。它不调用prepare／flash；要求报告`state=acquired`、`persistent_write_commands_sent=false`、`normal_reboot_acknowledged=true`后再分析。

| 回查对象 | 通过标准 |
|---|---|
| 设置logical/raw | 完整20MiB；40960扇区独立解密逐字节匹配 |
| BIN／BAK六槽 | 两份均为本节列出的FL2三项0A、FL3三项0B，BK4校验有效 |
| CC1／block13 | 两份完整记录的目标映射和颜色范围等于作者方案；使用`build_image(当前logical)`应不再产生差异 |
| 版本／更新文件 | 4.04状态与本次预期一致；设置部署前后保持非目标文件原值，不能用全区散列跨重启强求所有正常设置字节不变 |
| eMMC CP | 从新读`nflasha8`提取`CPAPP-B.BIN`，完整17,617,008字节及SHA-256等于最终4.04 CP |
| 物理CP NOR | 在已核实布局和字节序后比较同一目标CP；本机I从`0x200000`直接顺序读取后全字节匹配，无需swap16 |
| WBI | 读取头部为目标`WBI3`；不等同于取得拍摄时RAM |
| AP | 完整验收还需新读`nflasha15`并提取`/lib/appFw.so`，完整SHA-256等于4.04 AP；以上只读入口未采集AP，不能声称此项自动通过 |

AP目标SHA-256为`8ee4d5876b7e127df39f8f820b9d21834c300ff895e02ca522636ed4733efc4b`，CP目标SHA-256为`8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32`。AP可参考`read_r5_installed_fl2_fl3.py --port … --output … --partitions nflasha15`在独立新会话采集；该工具使用较早的ready文字判据且最终会reboot，不能嵌入正在进行的连续写入。其旧配套`compare_r5_installed_fl2_fl3.py`固定旧包和旧目录，不作为4.04比较器。

NOR采集脚本固定本机已核实的`0x200000`起点和`0x1100000`窗口，不能直接当另一机身通用布局。eMMC CP匹配不能替代NOR，M4样例的swap16也不适用于本机I记录。

**原`verify_post404_readback.py`是I事故快照核验器：其中断言六槽全00、颜色等于原厂。它不能作为T后“目标设置保持”的通用验收脚本；正确目标0A／0B会被它判失败。** 新回查应按本表目标核验并写入本次新结果，不改旧脚本或旧JSON来适配新状态。

下面是针对上述新采集目录的离线检查命令：只读取已保存文件，要求六槽／颜色已经是目标、CP两处匹配及WBI3；任何断言失败都应调查，不自动修复。它不访问相机，也不将用户启动确认或AP验收写成已通过：

```sh
.venv/bin/python -B - "$R5_CHECK_RUN" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / 'tools'))
from build_r5_m4strict_personal import build_image, Fat
from modify_r5_slot_settings import raw_verify
run = Path(sys.argv[1]).resolve()
acquisition = json.loads((run / 'report.json').read_text())
assert acquisition['state'] == 'acquired'
assert acquisition['persistent_write_commands_sent'] is False
assert acquisition['normal_reboot_acknowledged'] is True
assert (run / 'sdm2.raw.bin').read_bytes() == (root / 'backups/R5_4.00_20261014_full/sdm2_partition_table.raw.bin').read_bytes()
assert (run / 'ap_bootrom.bin').read_bytes() == (root / 'backups/R5_4.00_20261014_full/ap_bootrom.raw.A.bin').read_bytes()
logical = (run / 'settings.logical.img').read_bytes()
raw = (run / 'settings.raw.img').read_bytes()
raw_verify(raw, logical)
assert len(logical) == len(raw) == 20 * 1024 * 1024
target_settings, _ = build_image(logical)
assert target_settings == logical, 'Six slots or author color ranges differ from target'
cp = Fat((run / 'nflasha8.logical.img').read_bytes()).read('CPAPP-B.BIN')
expected_cp = (root / 'build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin').read_bytes()
assert hashlib.sha256(expected_cp).hexdigest() == '8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32'
assert cp == expected_cp
nor = (run / 'cp_nor_00200000_01100000.bin').read_bytes()
assert len(nor) == 0x1100000 and nor[:len(expected_cp)] == expected_cp
assert (run / 'nflasha5.header.bin').read_bytes()[:4] == b'WBI3'
assert Fat(logical).read('UPDATER/DAT4') == bytes.fromhex('0404')
report = {
    'scope': 'Offline verification of saved post-boot acquisition',
    'camera_io': False,
    'settings_logical_sha256': hashlib.sha256(logical).hexdigest(),
    'all_40960_raw_sectors_match_logical': True,
    'six_slots_and_author_color_ranges_are_target': True,
    'emmc_and_physical_nor_cp_match_final404': True,
    'wbi3_and_dat4_0404': True,
    'AP_verified': False,
    'shooting_and_video_verified': False
}
with (run / 'target_postboot_verification.json').open('x') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
PY
```

当前T写后完整回读已通过，U重启后回查未进入接口，故仍缺独立持久性验收。任何设置缺失应基于这次新回读重新生成差异，不回刷首次备份或历史完整设置区。

### 6．实拍验收、停止条件与失败处理

正常启动、设备回读和实际功能分别留证。先确认版本页4.04，再在相同曝光、白平衡及拍摄条件下新拍ST／FL／FL2／FL3的JPG／ARW，保留原片与菜单选择对应关系。核对拍摄界面右侧名称、回放名称和颜色；FL2／FL3 MakerNote预期B020为对应外观，B029分别为22／23，不应继续记录Standard／0。再验证视频、旧外观、关机后重新开机的选择保持；特殊模式及恢复出厂后的行为单独记录，不能用一次普通照片通过代替。

与Edit对照时使用重新显影结果，不看未更新的内嵌预览。用户视觉一致反馈、元数据标记、像素量化分别说明；RAW参数数值相等不能替代机内实际选择与成像证明。

| 发生位置／现象 | 如何处理 |
|---|---|
| 载荷或源码散列不符、分区／ROM不符、设置基线未知 | 停止，不放宽校验、不改未知标定、不写入 |
| 入口未成功、接口消失，`persistent_write_command_sent=false` | 保存本次目录；未写入时可由脚本尝试正常reboot，确认相机状态后再决定新会话，不从旧prepare续写 |
| 只读看门狗状态活动／未知或前后变化 | 写入前停止，不加入看门狗写命令规避 |
| 写前重读与刚备份不同 | 停止；重新采集、分析变化，不使用已生成patch |
| 已发送flash后异常、写后回读不符 | 按`write_needs_assessment`处理，保留现场和所有日志；脚本不自动回滚，也不在此路径自动reboot；按当次前后状态单独判断 |
| SD更新异常、黑屏或0x77灯码 | 保留时间／介质／提示和供电状态；灯码不单独证明分区损坏，不发送无关分区恢复命令 |
| 菜单可选但拍摄显示ST或新照片标记Standard | 先回查六槽／映射与当前程序，不以菜单成功或旧回读证明功能成功 |
| 只有已保存RAW或离线模拟一致 | 记录为离线数学／指令证据，继续独立验收持久性和实拍 |

此流程不包含降级、全盘还原、boot0／boot1重刷、NOR直接写入或自动修复升级中断。原始raw用户区含加密内容及SDM2表，不能当logical镜像刷进某个分区；历史`restore`绑定生成时状态，使用前同样需要新读核对。

完整完成标准是：**当次身份与备份可靠→信任环境匹配→DAT离线核验及机身更新完成→AP／CP／NOR／WBI目标一致→六槽和颜色写后及重启后核验通过→实拍／视频／回放与保持分别验收。** 任一未完成项继续标记待验，不以其它环节通过代替。

## 二、RAW研究与跨机型FL2／FL3证据

### 1．IED与RAW创意外观解锁研究：RAW携带外观参数

Sony Imaging Edge Desktop（IED）／Edit研究发现，兼容Sony ARW的加密SR2元数据中保存了多套创意外观参数。Edit可以读取这些参数，对同一份RAW像素选择不同外观重新显影。

独立“RAW创意外观解锁”工具以原片Standard外观目录为基础，补入FL2／FL3的十个目标字段；原有外观、RAW像素、原片白平衡和其他非目标字段保持原值。处理副本在Edit中可选择新外观，说明这些元数据确实能够参与外观渲染，而不只是菜单名称。

在已对照样片的外观目录中，跨全部外观出现变化的是同一套十个标签；ST与FL之间十项均不同。这里“十个数据块”包括九个数值／二进制字段与一个名称字段，不是十个菜单滑块，也不表示任意两个滤镜都十项全不同——例如FL2与FL3共享780C／780D／780E。

| 参数组 | RAW字段 |
|---|---|
| 三组颜色系数 | 0x7842、0x7844、0x7845 |
| 3×3矩阵及扩展颜色参数块 | 0x7800、0x780F |
| 曲线及附属参数 | 0x7806、0x780C、0x780D、0x780E |
| 外观名称 | 0x7770 |

### 2．FX2、M5、R6的FL2／FL3参数比较

从FX2、A7M5、A7R6原始样片中解密并提取SR2，按同一外观逐项比较TIFF类型、元素数量和完整负载：

- FL2：九个数值／二进制字段严格相等，名称完整负载也相等。
- FL3：九个数值／二进制字段严格相等，名称文本均为FL3；16字节名称负载的最后两字节不同，位于NUL终止符之后，仅作注明。
- 因此，“三机型采用相同FL2／FL3核心外观数值”有直接文件证据；“十个字段所有字节都严格相等”则不符合FL3名称尾部的实际记录。

三机型各使用一张原始样片，结论限于这批数据。FL2与FL3彼此仍是不同的外观，相同指跨机型比较同一种外观。

## 三、固件参数与RAW十字段换算

本表的RAW指解密后的SR2外观字段，不是RAW传感器像素，也不是菜单上的十个调节滑块。

所有索引从0开始。公式中的CC1、block13偏移均相对于对应BK4属性内容；Gamma偏移相对于最终4.04的cpapp-b.bin文件。数组按已验证解析器的小端格式解释。

| RAW字段 | 数据形式 | 对应机内参数 | 机内→RAW换算 | 部署方式／核查结果 |
|---|---|---|---|---|
| 0x7842 | 8×int16 | CC1差分表达第0组 | 每组v：`[v3,v0,v1,v2,2v7,2v4,2v5,2v6]` | 设置区线刷；CP内嵌副本随SD包。逐项一致 |
| 0x7844 | 8×int16 | CC1差分表达第1组 | 同上 | 同上，逐项一致 |
| 0x7845 | 8×int16 | CC1差分表达第2组 | 同上 | 同上，逐项一致 |
| 0x7800 | 9×int16，按行组成3×3 | block13照片bank的group1、slot0，共6项 | 六项展开矩阵，公式见下文 | 设置区线刷；9项逐项一致 |
| 0x780F | 276字节位打包结构 | block13颜色系数、公共分区及控制参数 | 系数区[24,216)按列、相邻槽交换后×4；其余部分见第四节 | 设置区线刷目标bank；完整276字节已分段回放匹配 |
| 0x7806 | 128×int32 | CP照片Gamma内部槽6 | `RAW[i]=2×CP[i]`，i=0..127 | SD卡4.04；128点逐项一致 |
| 0x780C | 1×uint16 | Gamma可选Knee point，空指针走默认512 | `2 × point`，FL2／FL3为1024 | SD部署完整Gamma记录，沿用原厂输出；已回放匹配 |
| 0x780D | 1×uint16 | Gamma可选Knee slope，空指针走默认1024 | `16 × slope`，FL2／FL3为16384 | 同上 |
| 0x780E | 10×uint16 | 原厂Baseband YGain，Gamma可覆盖首项 | 每项×32，FL2／FL3为下述数组 | 沿用原厂表及Gamma默认路径；已回放匹配 |
| 0x7770 | 16字节名称 | 外观名称和枚举 | FL2／FL3名称文本 | 名称支持随SD包；FL3的NUL后尾字节差异仅注明 |

0x780E：`[16384,15616,14976,14208,13568,12928,12160,11520,10752,10112]`。

780C／780D／780E的上述值在FL、FL2、FL3间相同，但不是所有外观都相同：ST的780C=4096、780D=14848，780E首项=17280，其余九项相同。

### 外观与数据位置

| 外观／模式 | CP profile | CC1／block13 bank | CC1有效48字节起点 | block13整bank起点 |
|---|---:|---:|---|---|
| ST照片 | 0 | 0 | 0x1250 | 0x01E0 |
| FL照片 | 41 | 8 | 0x1450 | 0x19E0 |
| FL2照片 | 54 | 22 | 0x17D0 | 0x43E0 |
| FL3照片 | 55 | 24 | 0x1850 | 0x49E0 |
| FL2视频 | 56 | 23 | 0x1810 | 0x46E0 |
| FL3视频 | 57 | 25 | 0x1890 | 0x4CE0 |

CC1属性ID为0x02A40001，block13为0x02A4000D，位于本机nflasha2中的BACKUP.BIN／BACKUP.BAK。视频行仅记录部署位置，本文RAW精确公式验证范围为照片外观记录，不外推视频实时输入。

CC1位置：`0x1250 + bank×64`，每bank有效24个int16，共48字节；不是64字节全部为系数。

block13位置：`0x1E0 + bank×768 + group×192 + slot×12`；每bank有3组，每组16槽，每槽6个int16。本文RAW对应group1，即第二组。

### CC1的正反换算

先统一差分表示：FX2的三组绝对值A、B、C转换成`A、B−A、C−A`；R5目标数据已经是这种表示。三组依次对应7842、7844、7845。

对任意一组机内v和RAW r：

```
r = [v3,v0,v1,v2,2*v7,2*v4,2*v5,2*v6]
v = [r1,r2,r3,r0,r5/2,r6/2,r7/2,r4/2]
```

反算除2在已核对样本中均为整数。若要恢复FX2绝对表示，则把第0组分别加回第1／2差分组；不能把RAW差分数组直接当作FX2绝对数组。

| RAW字段 | FL2照片 | FL3照片 |
|---|---|---|
| 7842 | `[-269,-184,-263,-384,506,712,520,1126]` | `[-269,-189,-51,-448,570,778,566,1126]` |
| 7844 | `[123,-492,151,305,-84,196,-242,0]` | `[0,5,0,0,10,68,-8,0]` |
| 7845 | `[0,-14,118,1,-90,276,-152,0]` | `[0,-207,0,8,-14,196,94,0]` |

CP内嵌FL2／FL3四行与设置区对应四行系数相同，是作者主读取路径使用的副本，不是新增一层独立调色。

### block13到7800矩阵

读取group1、slot0的(a,b,c,d,e,f)，在本批保存元数据的1024对角基准下：

```
M = [a+b+1024,   -a,          -b,
     -c,          c+d+1024,   -d,
     -e,         -f,           e+f+1024]
```

反算：`a=−M01, b=−M02, c=−M10, d=−M12, e=−M20, f=−M21`。该反算对应矩阵还应满足每行和为1024。

| 外观 | 机内六项 | RAW7800，按三行排列 |
|---|---|---|
| FL2照片 | `[-17,-47,-46,113,406,184]` | `[960,17,47]`；`[46,1091,-113]`；`[-406,-184,1614]` |
| FL3照片 | `[138,-221,-42,-128,253,-17]` | `[941,-138,221]`；`[42,854,128]`；`[-253,17,1260]` |

1024基准在本批数值对照中精确成立，不能据此替代所有实时标定输入。

### block13到780F参数块

将group1的16槽记为`q[slot][k]`，k=0..5依次是a,b,c,d,e,f。

```
RAW780F的byte offset = 24 + 2*(16*k+j)
该处little-endian int16 = 4*q[j XOR 1][k]
k=0..5，j=0..15
```

即先输出a列16项，再b、c、d、e、f列；每列槽顺序：

```
[1,0,3,2,5,4,7,6,9,8,11,10,13,12,15,14]
```

反算为对应int16除4，再按同一槽交换顺序放回。192字节系数区完整对应；头24字节与尾60字节在本次所比较ST／FL／FL2／FL3记录间共用，原厂生成来源及完整重建见第四节。

7800和780F来自同一block13颜色组的不同表达。每bank另两组的机内数据不由这两个RAW标签完整描述，不能据此删减作者的复制范围。

### CP Gamma到7806

移植共六条完整Gamma记录，将FX2的580字节布局适配为R5的576字节，保留附属参数；不是只复制采样点。Gamma ID扩展至47～50，旧ID0～46表项保留。照片RAW只描述其中一种内部曲线，不能因此删减其他记录。

```
RAW7806[i] = 2*CP_still_slot6[i]，i=0..127
反算CP[i] = RAW7806[i]/2
```

CP有129个u32点，RAW只含前128点；最后一点不能由本标签直接反算。

| 外观／曲线用途 | 最终4.04 CP文件偏移 | 是否对应本表7806 |
|---|---|---|
| FL2照片内部槽0～5共用 | 0xAE74C0 | 否 |
| FL2照片内部槽6 | 0xAE7700 | 是 |
| FL2视频内部槽6 | 0xAE7940 | 本表未验证视频RAW对应 |
| FL3照片内部槽0～5共用 | 0xAE7B80 | 否 |
| FL3照片内部槽6 | 0xAE7DC0 | 是 |
| FL3视频内部槽6 | 0xF76728 | 本表未验证视频RAW对应 |

这里“内部槽6”是Gamma表内部索引，不是用户菜单第六个创意外观，也不是设置区current／still／movie六槽。

FL2前8点：CP=`[0,1158,2316,3474,4632,5789,6947,8105]`；RAW=`[0,2316,4632,6948,9264,11578,13894,16210]`。

### 核验覆盖

R5／FX2各ST、FL、FL2、FL3，共8组：CC1的24个8元素数组、7800的8个矩阵、780F每组96项、7806每组128点，均精确通过上述数值关系。FX2／M5／R6的FL2／FL3九个数值字段与保存R5 RAW对应负载相同，共54项字段比较通过；没有独立从M5／R6固件推导。

R5文件DSC00430／431／432中的对应外观十字段负载互相完全相同，比较以430为主；拍摄／编辑来源未独立认证，只作为保存文件的数学对照。不能据此证明当时机内正确选中bank或未经RAW工具修改。最初完整字节搜索未命中只说明存储编码不同，不能当作缺项证据；旧`evidence.json`保留其原调查范围。

## 四、共用字段的原厂来源与遗漏检查

### 780C／780D／780E

以下使用CP文件偏移；Thumb地址为文件偏移加`0x108000`。

| RAW字段 | 原厂来源 | FL2／FL3换算 | 结果 |
|---|---|---|---|
| `780C` | Knee高光拐点point | 未指定覆盖时`512 × 2` | `1024` |
| `780D` | Knee斜率slope | 未指定覆盖时`1024 × 16` | `16384` |
| `780E` | Baseband十档YGain | 原厂uint16表逐项`×32`，Gamma可覆盖首项 | 见下文 |

模块名称有原厂字符串支持：`PQD_Knee.cpp`、`Cetus/PQD_Baseband_SystemDepend.cpp`、`GetRawParam...IFD of Fader/YGain`。Knee计算代码`0x9a221e..0x9a2246`在超过point后按`(x-point)*1024/slope`计算，支持拐点／斜率的角色判断。这些不是菜单里的十个调整滑块。

Gamma记录的三个指针：

| 记录内偏移 | 原厂载入后偏移 | 用途 |
|---|---|---|
| `+0x228` | `+0x28` | 可选YGain首项 |
| `+0x22c` | `+0x2c` | 可选Knee point |
| `+0x230` | `+0x30` | 可选Knee slope |

原厂加载块为`0x30c05e..0x30c0be`，已在当前Gamma表重定向清单中。逐外观RAW路径的公式为：

```text
780C = uint16(2  * (point_ptr ? uint16(*point_ptr) : 512))
780D = uint16(16 * (slope_ptr ? uint16(*slope_ptr) : 1024))
780E[i] = uint16(32 * base_YGain[i])
若YGain_ptr非零，780E[0]改为uint16(32 * uint16(*YGain_ptr))。
```

R5原厂表位于`0xdbf28c`，FX2对应表位于`0xeb8be0`，十项完全相同：

```text
固件：512,488,468,444,424,404,380,360,336,316
RAW：16384,15616,14976,14208,13568,12928,12160,11520,10752,10112
```

之前直接搜索RAW二十字节没有命中，是因为固件存的是乘32之前的值，不能据此判断缺失。

RAW生成主链为`0x760fb0 → 0x73dd36 → 0x99f70c`，后者调用Gamma载入、Baseband和Knee输出。`0x76110e`／`0x76111c`明确写入780C／D标签；Baseband输出函数为`0x995506`，Knee输出为`0x9a2286`。

#### 与现有移植的核对

当前六条Gamma记录按R5结构适配后完整复制，并非仅复制129个曲线点。核验六条转换后576字节与最终4.04逐字节一致，三个对应指针均为零，与FX2相同；零指针代表有效的原厂默认路径。

对FL2 ID47、FL3 ID48照片内部槽6，执行真实R5 Gamma尾部加载块，再执行真实Baseband／Knee输出函数，三个字段全部与保存RAW逐项相等。没有发现需要再移植一组独立短字段。

FL、FL2、FL3共用上述数值；ST的780C=4096、780D=14848、780E首项=17280，其余九项相同。ST Gamma三个指针非零，支持专用覆盖值的解释；**本轮没有重放ST指针目标的启动初始化**，不称ST来源也已完整回放。

### 780F共用84字节

原厂注册表`0xc07a48`将780F注册为276字节，入口指向`0x13d2e4`。其经`0x622658`处理矩阵，调用`0x624cae`打包。**这是位打包结构，不能把整个字段都当成连续int16颜色系数。**

| RAW字节范围（零基，右端不含） | 来源 | 当前处理 |
|---|---|---|
| `0,24)` | 16段色相分区坐标、模式／控制位 | 沿用R5公共block13及原厂代码 |
| `[24,216)` | group1的16槽×6系数，按列重排×4 | 已复制FL2／FL3供体系数 |
| `[216,248)` | 16个分区间隔换算系数，配对打包 | 原厂读取函数生成 |
| `[248,276)` | 三通道基准、分区控制字节、末尾控制值等，存在混合字节／位打包 | 沿用原厂配置和默认分支 |

具体来源：

- block13 `+0x100`保存16坐标`0,64,...,960`；`+0x120`为换算位移，值1。
- 原厂`0x12c344`按`(8192 << shift)/interval`生成16个间隔换算系数。本机均为256，RAW中对应重复的1024。
- 原厂`0x12c280`按控制模式读取分区字节及控制值；本次标准照片条件下ST／FL／FL2／FL3均为模式1，分区控制字节均为128。
- 三通道基准在本次路径由默认分支给出`1024,1024,1024`；特殊模式也可读block13 `+0x190..+0x195`，不能称该特殊读取为所有场景的来源。
- 公共参数读取及打包代码与R5原厂逐字节相同，部署没有改变block13 `[0,0x196)`。

R5／FX2整个block13头部存在20字节差异，详见JSON；本次实际涉及字段及输出匹配目标，不支持盲目复制整个供体头部。

#### 完整重建结果

| 保存RAW的外观记录 | 原厂函数生成完整276字节 | 差异字节数 |
|---|---|---|
| Standard | 完全相等 | 0 |
| FL | 完全相等 | 0 |
| FL2 | 完全相等 | 0 |
| FL3 | 完全相等 | 0 |

生成器不再借用RAW前24或后60字节；RAW只用于最后对照。输入为本机保存设置的公共配置及对应bank系数。

### 对现有添加流程的判断

六槽、CC1、block13目标bank／映射由设置区线刷；完整Gamma记录、内嵌CC1及选择路由等由SD包部署；共用配置和参数生成继续沿用R5原厂逻辑。CP内嵌四行CC1是作者主读取路径的同系数副本，不是额外一层调色。

当前block13仅复制供体`0x43e0..0x4fe0`的3072字节及对应4字节映射，不覆盖整个`0x7000`记录；CC1写四行各48字节及4字节映射。BK4校验和是有效性维护，不是颜色效果。六槽及AP look10／11→CP color19／20、profile54～57路由、范围／名称／元数据支持负责选中目标数据。

本轮没有发现共用字段导致流程不完善。先前缺少的是来源证据，现已补证；不需要因此增改公共头部、额外搬运短字段或缩减作者的矩阵复制范围。

## 五、同机型与跨机型色彩差异

### 同机型不同外观

进一步对照4.04 CP及T写后设置快照，并复用已保存的正常路径选择器证据。ST、FL、FL2、FL3在still和movie各自的CC1整行与block13整组都不同，八组间也未找到相同整行／整组。不是每个元素都不同：FL2与FL3照片CC1为24个int16中19个不同；视频为21个不同。每组block13为768字节，照片426字节不同，视频443字节不同。

CP内嵌的FL2／FL3四行系数与各自设置CC1行逐字节相同；FL2、FL3之间及照片／视频之间互不相同。它不是独立的第四套调色模型。

FL2／FL3六条576字节Gamma记录两两不同；每种外观still的内部槽0～5共用同一条，still槽6和movie槽6另用不同记录。六条记录的末尾u32结构字段都为2，不能把这一共同字段误认为整条曲线相同，且字段完整硬件含义尚未确定。ST、FL、FL2、FL3正常路由的对应Gamma记录也互不相同。

该比较没有逐一枚举其余八种外观，不声称全部十二种每对数据都不同。可重跑compare_look_banks.py，仅读取本地文件；完整源散列、逐对相等性及差异数量见look_bank_comparison.json。本次REA拒绝裸CP格式，沿用已有绑定源散列的布局／选择器证据作本地字节比较，没有启动相机或固件。

### R5与FX2的原有ST／FL

比较R5原厂4.00与FX2原厂1.01的同名外观；R5在T写后快照中的这几行CC1和block13已核对保持原厂。先把R5差分CC1还原成绝对系数，再与FX2比较，不把存储格式差异当作调色差异。此处为相同零调节输入下的普通路径，不包含两机实际标定与运行上下文。

| 外观／模式 | CC1有效24项中不同数量 | block13每组768字节中不同数量 | Gamma主曲线129个u32采样点 |
|---|---:|---:|---|
| ST照片 | 14 | 334 | 全部相同 |
| ST视频 | 20 | 318 | 全部相同 |
| FL照片 | 21 | 350 | 全部相同 |
| FL视频 | 23 | 332 | 全部相同 |

Gamma需要区分曲线与完整记录：将FX2的580字节记录按已验证的布局适配成576字节后，FL照片内部槽6和视频内部槽6记录完全一致；FL照片槽0～5共用记录仅+0x21c从R5的5变为FX2的3。ST照片槽0～5也是该单字段差异；ST照片槽6另外三处附属RAM地址字段不同，ST视频槽6一处附属RAM地址字段不同。引用RAM内容和完整效果未采集，不能把地址不同直接说成曲线形状或画面必然不同。

CP新增四行内嵌系数只服务FL2／FL3，不是给ST／FL又移植了四行，因此ST／FL跨机型比较的这一项不适用。本报告没有声称原固件所有代码段均不存在任何常量副本。

129个点为已验证固件消费函数复制的516字节范围，不可直接等同于ARW十字段表中的128元素标签。脚本compare_r5_fx2_st_fl.py与完整证据r5_fx2_st_fl_comparison.json保留原始绝对数值、曲线记录散列、逐字节差异和源文件身份。结果不证明跨机型最终像素相同。

### 数学差距量化

距离统一为norm(FX2-R5)/norm(R5)：CC1用24维绝对系数向量L2范数；block13按已验证的R5读取公式展开为3×3矩阵，采用Frobenius范数。矩阵的两机对角校准基准统一假设为1024，统计每个bank内3组×16槽共48张矩阵；这不是两台相机当前校准测量。

| 同名外观／模式 | CC1整体相对距离 | 矩阵相对距离中位数 | 矩阵相对距离最大值 |
|---|---:|---:|---:|
| ST照片 | 7.96% | 11.36% | 20.31% |
| ST视频 | 20.93% | 9.05% | 18.66% |
| FL照片 | 21.56% | 14.62% | 38.93% |
| FL视频 | 12.18% | 11.10% | 19.10% |

这不是逐项百分比取平均，而是整体差向量／原向量的范数比，避免接近零的单项使相对误差失真。矩阵中位数针对48个表项，不代表实际场景概率或真实插值权重。数据差距超过单纯取整噪声，但没有据此测出最终颜色差距。

统一对角基准时，所有展开矩阵的行和相同，差矩阵每行和为零，因此单独这一数学矩阵对相同中性输入的差为零；彩色输入则可能受不同通道混合影响。此结论不包括CC1、白平衡、传感器标定及其他处理阶段。

离线脚本measure_st_fl_distance.py和完整结果st_fl_numerical_distance.json保留逐项偏差、全部48张矩阵及统一单位输入立方体的代数探针。没有裁剪、Gamma、真实ISP或感知色差计算，不能把系数／矩阵距离直接称为画面百分比差异或DeltaE。

### R5／FX2的RAW对应关系

| RAW字段 | R5 ST对FX2 ST | R5 FL对FX2 FL | R5样本FL2／FL3对FX2同名外观 |
|---|---|---|---|
| 7842／7844／7845 | 不同 | 不同 | 相同 |
| 7800／780F | 不同 | 不同 | 相同 |
| 7806／780C／780D／780E | 相同 | 相同 | 相同 |
| 7770名称 | 全字节相同 | 全字节相同 | FL2全字节相同；FL3文本相同，NUL后尾字节不同 |

CC1差异经过第三节公式精确反映在RAW中。因此“新三机型的同名FL2／FL3相同”不能推为“所有机型同名外观全相同”。

### 跨代ST／FL的参数关系

对FX2、M5、R5、R6原始RAW的ST和FL进行比较，发现同名外观的颜色参数并不总相同。其中M5与R6在三组CC1对应字段上相同，但不能概括为二者全部ST数据一致。

| RAW字段 | ST／Standard跨机型关系 | FL跨机型关系 |
|---|---|---|
| 7842／7844／7845 | M5＝R6；FX2、R5各自不同 | M5＝R6；FX2、R5各自不同 |
| 7800／780F | 四款样片各不相同，包括M5与R6 | M5＝R5＝R6；FX2不同 |
| 7806／780C／780D／780E | 四款同名外观对应值相同 | 四款同名外观对应值相同 |
| 名称 | 相同 | 相同 |

这表明同样叫ST，颜色系数与矩阵仍可能发生变化；新一代机型也不是所有颜色数据都机械共用同一套。

### 对跨代色彩优化的推测

结合这些参数差异，可以提出一个研究假设：**除白平衡算法等环节外，索尼的部分跨代色彩优化，可能通过创意外观层的颜色系数与矩阵实现，并随RAW元数据交给Edit使用。**

它有参数变化和可替换显影的依据，但目前仍是“疑似”：传感器与机身标定、拍摄条件、其他私有显影参数也可能影响同名外观数据。不能把全部跨代色彩差异都归因于这十项，或断言已定位索尼唯一的色彩优化位置。

### R5使用R6 ST参数的视觉观察

IED项目已生成同一R5 RAW的A／B对照副本，将Standard组的十个目标字段赋为R6 ST数据。实际改变五项：7842、7844、7845、7800、780F；另五项原本已相同。其余104项外观字段、其他11种外观、RAW像素、白平衡、曝光、镜头和预览保持不变。

用户于2026-10-17此前总结时反馈：**在Edit重新显影后，采用R6 ST参数的版本，肤色部分比R5原ST更明亮，整体偏黄有所改善。** 该结果与“同名外观的颜色参数变化能够改变肤色和整体色彩”的假设相符，也说明至少在该对照中，无需改变原始RAW像素即可看到差异。

这里的“肤色更明亮”和“偏黄改善”最初为用户视觉观察。2026-10-17随后对两张ST导出做了独立量化：黄红分量确实减弱，但所选玩偶脸部的数值明度略降，不能把“视觉更清透”直接解释为提亮；详细结果见下节。不要用未更新的内嵌预览或Finder缩略图替代重新显影结果，也不要把这一结论直接套用于整套容器模板替换的“RAW功能解锁”工具——后者还可能继承其他私有字段。

### R5 ST与替换R6 ST参数的JPG量化

用户指定`samples/DSC00430_ST.JPG`和`DSC00430_ST替换为R6.JPG`。两张均为9504×6336、sRGB、`Edit 4.1.00.03062`导出，同一拍摄时间及曝光／白平衡记录（1/125秒、F2.8、ISO320、5300K）。Sony CreativeStyle／ColorMode仍为原拍FL标签，因此不以这些标签认证Edit重新显影时选择的ST；对照身份以用户确认和保存的参数替换实验为依据。

全分辨率RGB直方图交集均值为**98.948%**、BC分布亲和度均值为**99.985%**，其中R／G／B交集分别98.269%、99.451%、99.125%。亮度码值Y′交集99.299%。RGB全分辨率PSNR为45.17dB；平均绝对误差分别为0.984、0.556、0.705个8位码值。直方图高度相似不能排除局部色彩变化，BC也不是还原准确率。

统一缩至1584×1056后，平均ΔE00全图为**0.505**、主体矩形0.737、彩色主体**1.596**；灰色背景为0.401，主体颜色变化比背景集中。固定矩形均从R5参考图选择，不依据差异大小筛选；彩色主体的掩膜使用R5图中`C*ab>15且5<L*<95`的同一像素集合对照。缩图局部结果如下，差值方向均为R6参数导出减R5参数导出：

| 固定区域 | 平均ΔE00 | ΔL*（正=更亮） | Δa*（负=少红） | Δb*（负=少黄） | ΔC*ab（负=彩度降低） |
|---|---:|---:|---:|---:|---:|
| 高玩偶脸部三块皮肤色 | 1.285 | −0.685 | −1.376 | −1.115 | −1.734 |
| 矮玩偶脸部三块皮肤色 | 1.243 | −0.553 | −1.251 | −0.910 | −1.533 |
| 棕红头发 | 1.817 | −1.293 | −1.635 | −2.539 | −2.810 |
| 青色裙子 | 1.056 | +0.300 | +0.923 | +0.552 | −1.145 |
| 红衣区域（含部分背带） | 1.445 | −1.073 | −1.071 | −1.900 | −1.984 |
| 灰色背景 | 0.401 | +0.023 | +0.068 | +0.112 | −0.095 |

脸部测量另以原分辨率复核：高／矮玩偶分别采样38,076／50,144像素，平均ΔE00为1.365／1.362，平均ΔL*为−0.706／−0.556，Δa*为−1.402／−1.267，Δb*为−1.124／−0.910。与缩图结果方向一致，因此“脸部没有数值提亮”不是由缩图造成。玩偶脸部是涂装塑料，不代表真人皮肤；场景没有标准色卡，也不能据此评判哪套参数更准确。

**本组主要变化为暖色、红黄色的彩度减弱，灰背景基本保留；不是统一提高曝光，也不是整张图一致偏冷。** 例如脸部、头发减少黄红，而青裙的a*、b*向中性靠近并稍亮；变化具有区域／颜色选择性。仅凭JPG还不能把每项变化分配到7842／7844／7845、矩阵7800或780F各自的贡献，更不能把参数替换称作完整R6成像算法复制或原生R6机身实拍验证。

来源复核发现：原始430 ARW仍匹配实验记录的散列；当前R6参数副本比生成时增加1630字节，整文件散列已变化。只在内存重建最初预期副本，散列精确匹配原实验记录，再解析当前副本，确认全部十个ST负载仍匹配R6，各外观负载相对生成时均无变化，保存记录中的RAW像素区域散列全部一致；预览区域及其他私有元数据已有变化。本次未认证这些变化的写入者，也未恢复完整Edit历史，因此JPG测量是当前两张导出的输出差异，不能把所有残差无条件归因于唯一一个参数块。

证据：[直方图（本地证据：`r5_r6_st_comparison_20261017/histograms.png`，未公开）、脸部裁切对照（本地证据：`r5_r6_st_comparison_20261017/face_comparison.jpg`，未公开）、区域选择（本地证据：`r5_r6_st_comparison_20261017/ROI_selection.jpg`，未公开）、[完整指标](r5_r6_st_comparison_20261017/metrics.json)、原尺寸脸部复核（本地证据：`r5_r6_st_comparison_20261017/native_face_verification.json`，未公开）、RAW来源复核（本地证据：`r5_r6_st_comparison_20261017/raw_provenance.json`，未公开）。脚本为同目录`compare.py`、`verify_native_faces.py`、`verify_raw_provenance.py`，使用桌面内置Python及此前保存的色差函数。输入JPG／ARW均仅只读，没有相机操作。

## 六、画面对照与实机验收边界

用户于2026-10-17此前总结时补充实拍观察：**搬运FX2参数后的机内直出照片，与在Sony Edit中使用R6参数转换为对应FL2／FL3外观得到的图像，颜色表现相同。**

这为前述参数同源和数学换算提供了输出端的视觉印证。2026-10-17随后对用户指定的六张JPG进行了独立量化，结果如下；不将“颜色表现相同”写成逐像素完全相等或所有场景都相同。

至此证据顺序为：**RAW研究发现外观参数→三机型同名FL2／FL3核心数值一致→固件移植数据与RAW字段精确换算→用户反馈机内直出与Edit转换颜色一致。** 写后回读另行证明目标设置曾实际刷入；重启持久性和完整功能验收仍按各自日志记录，不从本次视觉结论反推所有项目均已验证。

### 430／431／432与Edit导出的直方图及色差实测

输入为`samples/`中的`DSC00430.JPG`、`DSC00431.JPG`、`DSC00432.JPG`，分别配对同编号`后期导出.JPG`，用户指定外观依次为FL／FL2／FL3。未使用另两张430的ST实验图。六文件的尺寸均为9504×6336，EXIF均声明sRGB，无内嵌ICC。机内图软件标记为`ILCE-7RM5 v4.04`，导出图为`Edit 4.1.00.03062`；保存的CreativeStyle／ColorMode均对应FL、FL2、FL3。每对曝光记录均为1/125秒、F2.8、ISO320、5300K、曝光补偿0，拍摄时间匹配；这些记录不能代替完整Edit调整历史认证。

全分辨率计算每通道256档归一化直方图及RGB逐像素误差。色差计算先以同样的LANCZOS算法缩为1584×1056，再按sRGB→XYZ D65→Lab D65计算CIEDE2000，参数均为1；实现对照四组公开Sharma参考值通过，误差小于0.0001。没有曝光修正、直方图匹配或几何变换。792×528的边缘位移诊断在横纵±3像素搜索范围内，三对均以零位移最优，相关系数0.9967～0.9976；这不等于证明亚像素完全对齐。

| 配对外观 | RGB直方图交集均值 | RGB分布亲和度BC均值 | 全图平均ΔE00 | 全图95百分位ΔE00 | ΔE00<2的采样点 | 彩色主体平均ΔE00 |
|---|---:|---:|---:|---:|---:|---:|
| 430／FL | 94.42% | 99.67% | 1.000 | 1.981 | 95.12% | 0.887 |
| 431／FL2 | 95.54% | 99.75% | 1.005 | 2.021 | 94.85% | 0.912 |
| 432／FL3 | 95.84% | 99.80% | 0.962 | 1.881 | 96.20% | 0.966 |

直方图交集为`Σmin(p,q)`，BC为`Σ√(pq)`，再乘100；均为归一化分布指标，不能解释为“准确还原率”或相同比例的像素完全一致。直方图忽略空间位置，因此另列对应位置的ΔE00。色差约1通常属于很小差别，但可见程度依赖显示、区域和观看条件；此处为缩图色差，不代表原尺寸每个细节像素的色差。

灰色背景占比较大，因此另做固定主体矩形和颜色掩膜复查。矩形范围为归一化坐标`x=0.32～0.70，y=0.24～0.99`，占全图28.50%；三组该区域平均ΔE00分别为1.039、1.040、1.035。彩色主体只使用矩形内机内图`C*ab>15且5<L*<95`的像素选择掩膜，两张配对图使用同一掩膜，不按差异大小筛选；分别覆盖全图4.91%、4.16%、4.63%，对应表中最后一列。局部统计仍未显示FL2／FL3独有的大幅色彩误差。

Edit相对机内图的全图平均ΔL*分别为−0.332、−0.258、−0.225，均稍暗；平均Δb*为−0.580、−0.592、−0.537，全图平均稍偏蓝／少黄。其幅度较小且三组方向接近，不能外推所有彩色区域均偏冷。全分辨率RGB平均绝对误差，合并三通道后分别约1.764、1.484、1.517个8位码值；PSNR为40.12、41.25、41.53dB，明确说明输出并非逐像素相同。残差可能涉及显影、降噪、锐化或JPEG编码，本次没有隔离其各自贡献。

**本组结论：FL2／FL3机内直出与对应Edit导出在整体分布及主体颜色上高度接近，差异与原生FL的机内／Edit差异处于相近量级；没有发现新增外观特有的明显色彩失配。** 这是单场景照片的输出端量化印证，不替代跨光源／肤色／饱和色／高动态场景、视频、重启后持久设置或全部原功能验收，也不由文件名及EXIF倒推出样片对应某次部署的运行状态。

复现脚本：[compare.py](r5_fl_edit_comparison_20261017/compare.py)。运行使用桌面内置Python（包含Pillow及NumPy）：

```sh
python3 -B analysis/r5_fl_edit_comparison_20261017/compare.py
```

原始输入未修改，无相机操作。六文件散列、完整直方图、全图及局部指标见[metrics.json](r5_fl_edit_comparison_20261017/metrics.json)，元数据见metadata.json（本地证据：`r5_fl_edit_comparison_20261017/metadata.json`，未公开）。另保存直方图叠加（本地证据：`r5_fl_edit_comparison_20261017/histograms.png`，未公开）、配对缩略图（本地证据：`r5_fl_edit_comparison_20261017/contact_sheet.jpg`，未公开）、主体矩形（本地证据：`r5_fl_edit_comparison_20261017/subject_region.jpg`，未公开）及逐对ΔE00热图（固定0～5，蓝→黄→红），后者不能按显示颜色当作原图色彩。

### 实机状态按时间区分

- 会话D在SD升级前写入30扇区、3710字节，完整回读通过，用户确认正常拍摄。
- 会话I在4.04后只读回查：六槽全00、CC1／block13等于原厂；eMMC和物理CP NOR完整匹配目标4.04，WBI3。该快照解释了当时选FL2／FL3却显示／记录ST的异常；丢失时点仍未确定。
- 会话T随后使用D原脚本重新部署30扇区、3711字节，六槽0A／0B、颜色字段、20MiB逻辑回读和40960个raw扇区解密核验通过；正常reboot后用户确认恢复拍摄。
- T之后U未进入fastboot，没有新数据或持久写入。I全00不是T后的当前值。用户后续视觉对照作为单独观察记录，不能替代重启后设置回查、全部场景／视频功能验收。

## 七、证据、复现与限制

### 原始证据入口

| 内容 | 脚本／结果 |
|---|---|
| CC1与RAW | compare_raw_and_cc1.py（本地证据：`r5_fl23_arw10_vs_firmware_20261016/compare_raw_and_cc1.py`，未公开）／raw_vs_cc1_correspondence.json（本地证据：`r5_fl23_arw10_vs_firmware_20261016/raw_vs_cc1_correspondence.json`，未公开） |
| 矩阵与Gamma | map_matrix_gamma.py（本地证据：`r5_fl23_arw10_vs_firmware_20261016/map_matrix_gamma.py`，未公开）／matrix_gamma_correspondence.json（本地证据：`r5_fl23_arw10_vs_firmware_20261016/matrix_gamma_correspondence.json`，未公开）／matrix_gamma_probes.json（本地证据：`r5_fl23_arw10_vs_firmware_20261016/matrix_gamma_probes.json`，未公开） |
| 同机型外观差异 | compare_look_banks.py（本地证据：`r5_fl23_arw10_vs_firmware_20261016/compare_look_banks.py`，未公开）／look_bank_comparison.json（本地证据：`r5_fl23_arw10_vs_firmware_20261016/look_bank_comparison.json`，未公开） |
| R5／FX2与数学距离 | compare_r5_fx2_st_fl.py（本地证据：`r5_fl23_arw10_vs_firmware_20261016/compare_r5_fx2_st_fl.py`，未公开）／r5_fx2_st_fl_comparison.json（本地证据：`r5_fl23_arw10_vs_firmware_20261016/r5_fx2_st_fl_comparison.json`，未公开）；measure_st_fl_distance.py（本地证据：`r5_fl23_arw10_vs_firmware_20261016/measure_st_fl_distance.py`，未公开）／st_fl_numerical_distance.json（本地证据：`r5_fl23_arw10_vs_firmware_20261016/st_fl_numerical_distance.json`，未公开） |
| 共用字段、原厂指令回放 | audit_common.py（本地证据：`r5_fl23_common_fields_20261017/audit_common.py`，未公开）／audit_results.json（本地证据：`r5_fl23_common_fields_20261017/audit_results.json`，未公开）／native_ranges.txt（本地证据：`r5_fl23_common_fields_20261017/native_ranges.txt`，未公开） |
| REA及代码摘录 | Knee／Gamma bundle（本地证据：`r5_fl23_common_fields_20261017/rea_knee_gamma_bundle.json`，未公开）／block13 bundle（本地证据：`r5_fl23_common_fields_20261017/rea_block13_bundle.json`，未公开）；同目录保留`make_excerpt.py`、ELF摘录及`excerpt_manifest*.json` |
| 实机设置与回读 | 会话D（本地证据：`r5_m4strict_personal_flash_20261015_D/README.md`，未公开）／会话I（本地证据：`r5_fl23_post404_readback_20261016_I_poweron/README.md`，未公开）／会话T（本地证据：`r5_fl23_post404_redeploy_20261016_T/README.md`，未公开）／会话U（本地证据：`r5_fl23_post404_persistence_20261016_U/README.md`，未公开） |
| 430／431／432机内与Edit量化 | [compare.py](r5_fl_edit_comparison_20261017/compare.py)／[metrics.json](r5_fl_edit_comparison_20261017/metrics.json)／直方图（本地证据：`r5_fl_edit_comparison_20261017/histograms.png`，未公开） |
| 430 R5 ST／R6 ST参数导出量化 | [compare.py](r5_r6_st_comparison_20261017/compare.py)／[metrics.json](r5_r6_st_comparison_20261017/metrics.json)／RAW复核（本地证据：`r5_r6_st_comparison_20261017/raw_provenance.json`，未公开） |

主要输入SHA-256：

| 输入 | SHA-256 |
|---|---|
| 最终4.04 CP，`build_r5_m4strict_4.04_20261015/patched/cpapp-b.bin` | `8e9e26bf2e4b93fa5142e961dcf21cb0f43f8871283814be2dcfb0a694cb5a32` |
| 原厂R5 CP | `3269bf62426339791fcfbe8529698cd4accbe6c3d2ea61cd7c368a90ab7ee7c8` |
| 原厂FX2 CP | `eba723db657117a36d9593dacf640840aca893c0d6ee5d728de9d1996b8c5e29` |
| 会话T写后设置logical | `f3c3d66e26b612dd7b5a16b66f1d923d21cc00946d0e21984d0e896d6136a34e` |

### 共用字段复现与REA记录

运行保存脚本：

```sh
.venv/bin/python -u analysis/r5_fl23_common_fields_20261017/audit_common.py
```

`audit_results.json`含源散列、六条Gamma整记录核验、原厂代码不变检查、CDE输出及四组完整780F。`native_ranges.txt`保存关键指令。`make_excerpt.py`生成不可刷写的ELF摘录，`excerpt_manifest*.json`绑定CP源散列及范围。

本机Unicorn在沙盒内映射内存以132退出；经批准在沙盒外运行保存脚本后全部通过。这是主机模拟环境限制，不是相机故障。

| REA分析 | Evidence ID |
|---|---|
| Knee RAW输出 | `ev_8d87da99d8bd370efbad7b370a99e01fcaf6b686f09ef938793e0290791bc2e6` |
| Baseband YGain | `ev_e8314aa347aae5923894553fe02030cbea6be6ea7785a3b48cb002e3cc496198` |
| Gamma RAW编排 | `ev_6a152ce4fc9578e14a70a3ad19e8635ddeb81d5fbd03b304d6f59d420534aa0e` |
| RAW780C／D写入 | `ev_fc84cb544499eb28696ad10df3dbb4e9bda5b393f6261a7a3a9dc80e3b33dae3` |
| 公共参数读取 | `ev_984fbe77b711e70d3ae753f721a5140f7283d873c455fa648d3218b5d31cbf39` |
| 780F完整打包 | `ev_7b4833c507d20c2383e056cc29c381b8e492cf220f7a827db70e755c79145ef1` |

完整记录保存在两个`rea_*_bundle.json`中。摘录缺少外部断言目标，部分伪代码显示`halt_baddata`或截断；结论同时核对原始ARM字节和独立Unicorn回放，不将摘录伪代码当完整源码。

### 验证边界

- 使用合成运行结构、分段真实指令回放，不是相机执行。Gamma尾部加载及CDE生成实际执行，但未模拟整段OS生命周期。
- 原有选择器测试边界早于公共头部函数；脚本独立调用真实头部读取及控制选择函数，未把A5哨兵当作相机数据。
- RAW打包上下文字段相对选择器输出偏移高`0x24`，脚本显式投影。中间完整服务传递及白平衡／矩阵处理未连续执行。因此这是原厂读取＋原厂打包的分段重放证明。
- 内存清零辅助函数按调用约定替代，原厂断言触发则失败。
- 保存R5 ARW的拍摄／编辑来源未独立认证，只用作数值对照。
- 会话T是最后成功写后回读；较早I的全00不是T后的已知状态。本轮没有采集新实机状态，重启保持及完整成像验收仍须单独报告。

### IED研究与实拍观察来源

- 独立RAW创意外观工具说明（本地证据：`local-ied-research/RAW创意外观解锁/使用说明.md`，未公开）。
- FX2／M5／R6外观参数对照（本地证据：`local-ied-research/研究记录/20261016_FX2_M5_R6外观参数对照/对照说明.md`，未公开）。
- FX2／M5／R5／R6的ST／FL对照（本地证据：`local-ied-research/研究记录/20261016_FX2_M5_R5_R6_ST_FL对照/对照说明.md`，未公开）。
- R5替换R6 ST十项的测试说明（本地证据：`local-ied-research/研究记录/20261016_R5替换R6_ST十项/测试说明.md`，未公开）与逐字段校验记录（本地证据：`local-ied-research/研究记录/20261016_R5替换R6_ST十项/替换与校验记录.json`，未公开）。

## 八、参考项目与致谢

感谢以下项目公开研究方法和工具。本项目的R5地址、结构适配与实机验收由本工作区单独核对；引用上游不表示上游作者验证或支持R5版本。

| 项目 | 本研究使用范围 |
|---|---|
| [Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/086df3b1e33dfa0206553ac2bb003535c58ddb80) | 当前FL2／FL3方法的直接依据，固定提交`086df3b1e33dfa0206553ac2bb003535c58ddb80`。参考AP／CP补丁、六槽个人设置、CC1／block13、Gamma以及SD与线刷分离的流程。R5不照搬M4分区号。 |
| [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE/tree/2328d18ce640e6c8cd9341efcf0043ce9042a135) | BootROM串行引导、RP2040桥接、fastboot与eMMC加解密的研究依据。该参考树未发现明确许可证，公开仓库不捆绑其源码、UF2或RAM载荷；历史本地构建身份另行核对。 |
| [DavidBuchanan314/fwtool.py，a7iv分支](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv)及[ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | Sony固件容器、文件系统、FDAT解包与格式研究基础。相关工具按其原许可取得。 |
| [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload/tree/1619f938663a36d41e72302a8cfee89a0f6acd1a) | 备用服务模式路线的资料研究；未用于本次R5部署，不作为已验证刷写步骤。原文为CC BY-SA 4.0，本文不转载其技术文档。 |
| [Capstone](https://github.com/capstone-engine/capstone)、[Unicorn](https://github.com/unicorn-engine/unicorn)、[Ghidra](https://github.com/NationalSecurityAgency/ghidra) | 指令审查、局部CPU回放与反编译分析。工具结果不能替代机身运行验收。 |

另感谢本地IED／RAW创意外观解锁项目提供十字段对照与Edit实验资料；当前没有核实其公开GitHub地址，因此不编造外部链接。Sony Imaging Edge Desktop为Sony官方软件，不属于本项目开源源码。

本研究公开的是主机脚本、补丁配方与研究说明；Sony原始或修改固件、供体完整色彩数据、机身备份、个人设置、签名私钥及第三方载荷不随源码发布。各工具保留原有许可证，致谢不替代再分发许可。
- 初始校验环境修改（本地证据：`../build_r5_partition1_verifykey_skip_20261014/README.md`，未公开）。
- 图像视觉反馈来源为用户2026-10-17消息；后续430／431／432配对量化及430两张ST导出量化已分别记录于第五、六部分。ST玩偶脸部黄红减弱但明度略降，与最初“更明亮”的主观描述分开报告。
