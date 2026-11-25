# 4.67 AP：准备参数与原厂颜色任务接管

冷启动继续从 SD 校验完整 R5NATIVE.BIN、原子保存整包到 eMMC，再释放临时整包。AP 常驻目录为 1284 B。普通切换仅读取所选记录；Off 不读参数文件。菜单、Fn、声音、比例、预览及回放的 62 个共享源文件保留。

`r5_filter_runtime.c` 重写提交状态，不保留 APPLY/CLEAR/STATUS 和失败重载旧滤镜。新 E7 magic 为 `0x46303536`：

- PREPARE=1：包含一款 2392 B compact；Off 是 slot/digest/payload 全零的 32 B 请求。准备不改变活动 owner，40 B 回执 `+36` 是非零 23 bit cookie。BUSY 或回执丢失仅重发相同请求，不重新读文件。已接管的同请求回状态6和原 cookie。
- 对已准备且确认 cookie 的请求，只执行一次原厂 E4。构造 hook 用 worker 静态 request+16 与确切对象指针匹配。执行 hook 复制该对象的 56 B，cookie 只写副本 selector 的原闲置高三字节。原对象、原色值和后八条 E4 调用均保持。序列化 hook 在原 BL `0x35614fc` 调用原 `0x3550354` 转换低位枚举，再携带 cookie。
- ACCEPT=4 是原厂 CP 接管后的独立通知，回执必须匹配 epoch、sequence、slot、digest、cookie。原厂 execute 返回与 ACCEPT 分别记账；两者都到达才持久化并发布 UI 成功。它们不是硬件显示完成的证明。
- 超时使用 ABORT=2 核对同一请求。状态0取消未接管准备，迟到任务不带 cookie；状态6和 cookie 证明已接管。ABORT 回执丢失时保留小 key，后续 worker 只重试控制请求。确认实际已接管但 E4 未完成、或保存 sidecar 失败时，显示实际活动选择和错误，不重载旧参数，不发送回滚 E4。重复选择已接管款仅重试保存。
- COLLECT=3 不带参数，切换、Off 和取消后由 AP worker 每秒轮询一次；回执 `+36` 为仍有旧 owner 引用的退役对象数。为0停止，丢回执继续。Off 后即使用户不再切换也执行收集。

`job.c`/`job.h` 仅处理任务副本与原厂颜色序列化；`r5_filter_store.c`、`r5_filter_file.c` 和 `r5_filter_boot.c` 保留整包导入/单条读取合同。单条读取实际共2581 B（128 B header、2452 B所选记录、末字节探测），临时 mount guard 65537 B立即归还。冷导入私有堆夹具峰95090 B、返回后全部释放，不等于整机内存峰。

AP 构建子步骤：`build_ap.py --stock-ap <原厂appFw.so> --output <新目录>`。从固定的原厂 AP 输入一次编译链接。输出 appFw.so 与 ap_build.json。首次候选 SHA256 `7cbe4534c6b61dbec09044411279dc358668b8ba42d1fefed219e4de47b15266`，97517568 B，RX65896 B，所有功能BSS62736 B；最终身份以交付回执为准。

验证：`tests/run_runtime.py` 在 ASan/UBSan 下运行15种模式×5种原厂Look共75例；覆盖独立 ACCEPT、丢回执/迟到、ABORT接受结果、暂停恢复、文件/保存失败、Off收集和禁止PT get/set。`tests/native_support/replay_filter_native.py` 在两个PIE加载地址执行最终二进制的原厂E4、402f序列化与补丁，采用显式原生入队、字段/传输/CP actor夹具。存储/启动14场景、比例690断言、Fn/UI原生图形库与ABI回放分别报告。

未执行完整机身调度、真实介质时延、硬件颜色消费者或 MF/AF 拍摄放大。CP照片/网格/Gamma引用传播和正式打包由集成任务独立验收；AP回放不证明现场卡死已修好。
