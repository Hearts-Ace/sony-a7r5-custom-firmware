# R5 刷写工作台：AI 操作指南

这是外部本地 AI 使用的固定工具接口。用户用自然语言描述目标，AI 根据本说明调用命令。应用没有内置语言模型，不需要 API Key；随包只有最新已完成的滤镜 BIN，不包含滤镜训练工作台。

先执行应用内 `Contents/MacOS/r5wb describe`。返回实际指南路径、命令清单、附带 BIN 的版本、散列和 12 项名称。应用可能被移动或重命名，始终使用当前应用绝对路径，并按 shell 规则引用含空格的路径。

## 常用任务

以下 `CLI` 表示用户实际安装的应用内入口，例如：

```sh
CLI='/Applications/R5 刷写工作台.app/Contents/MacOS/r5wb'
"$CLI" describe
"$CLI" status
"$CLI" plan --destination '/Volumes/相机卡'
"$CLI" prepare --destination '/Volumes/相机卡'
"$CLI" prepare --firmware '/path/to/BODYDATA.DAT' --destination '/Volumes/相机卡'
"$CLI" result '/path/to/task/result.json'
```

- “把最新滤镜放到这个文件夹”：执行 `prepare --destination PATH`，只复制附带的 `R5NATIVE.BIN`。
- “把固件和滤镜准备到卡里”：执行 `prepare --firmware DAT --destination PATH`。固件必须精确匹配我们的冻结 4.35 DAT。
- “先看看会改什么”：执行 `plan`，只校验并输出计划，不复制或替换目标文件。
- “上次完成了吗”：执行 `status`，再根据任务路径执行 `result`。有需要才查对应 `engine.log`。
- “校验这份固件”：执行 `verify --firmware DAT`。
- “重新构建固件”：执行 `build --original-dat DAT --private-key PEM --output NEW_DIRECTORY`；已有统一输入配置则用 `build --inputs JSON --output NEW_DIRECTORY`。外部私钥需权限 0600，禁止输出其内容。

目标必须是已存在的目录。根据用户提供的路径定位存储卡；目标不明确时询问路径。不要把相机 MSC 卷默认当作用户指定的存储卡。导出会完整读回；同散列文件跳过，不同旧文件保存在目标 `.R5Workbench-backups/<本次编号>/`。多文件操作会逐项完成，失败时检查 `prepared-*.json`，不要假定全组自动回滚。

每次正常命令的 stdout 只有一个 JSON 对象，进度在 stderr。退出码 0 为完成，1 为失败或未完成，2 为参数错误。正常操作返回 `job`，其目录包含 request、result 和日志。长时间构建应持续消费 stderr；不要仅因静默就自动重试。

全局 `--tasks-root PATH` 放在子命令前，可指定回执位置。`R5_WORKBENCH_STATE_DIR` 可隔离本地任务与导出锁目录；默认 `~/Library/Application Support/R5FlashWorkbench/`。这些配置不改变设备事务锁。

## 普通 USB／MSC

`describe`、`status`、`selfcheck`、`plan`、`prepare`、`verify`、`build` 不联系相机。`usb-status` 显式观察主机 USB 元数据，不发送相机协议命令。

只有用户明确要求 USB 备份或准备更新信任时才运行以下设备命令；会显示 macOS 管理员授权。用户已明确授权的动作无需再次泛化确认，操作系统授权由用户完成。

```sh
"$CLI" backup
"$CLI" install-trust --backup '/path/to/completed-backup/result.json'
"$CLI" recover --previous '/path/to/previous/result.json'
```

备份仅覆盖完整更新器分区。安装信任仅接受真实完成且原厂前像正确的备份，机内再次核对后写入我们的公钥及必要校验。未知前像拒绝；已有我们的公钥可跳过。不使用历史整分区覆盖机身，不提供强制入口。失败保留回执和锁，不自动重复 USB 写入、STOP、删除锁或尝试 fastboot。

`prepare` 成功仅表示文件已准备；普通 USB 信任安装成功仅表示更新信任已准备。固件升级由用户在机身通过存储卡完成，不能据此报告升级、启动或拍摄验收成功。最新滤镜身份以 `describe` 的完成批次为准，未完成训练不随包发布。
