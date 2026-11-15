# 4.65 构建与封装

全部入口使用官方 R5 4.00 固定输入。本版仍保留 SD 整包导入 eMMC、平时切换只读一款，取景/拍摄各原厂任务引用决定旧参数保留多久。构建只写新的本地目录，不访问相机、SD 或网络。

- `stock_inputs.py` 核验官方输入并应用声明的基础配方；`ap/build_ap465.py` 与 `build_cp465.py` 直接编译本版接线。上一版本的自定义二进制不参与构建。
- `build_nonfilter.py` 从官方输入重建 AVCAM/MPR/70 项资源，并核验固定身份。`build_partitions.py` 集成四个分区，对其它文件与目录作范围检查并执行只读 e2fsck。
- `package_firmware.py` 验证原厂 TAR 的流式覆盖、只允许 nflasha3、nflasha5、nflasha8、nflasha15 和 part_image.sum 五个成员变化。官方工厂模板、backup.sum、更新器及其它普通成员保持原字节。

正式封装要求 `validation.lock.json` 和完整源锁。验证回执必须绑定四项精确组件散列，并为准备与设置锁、原厂 E4 cookie 接管、取景对象、待处理 Gamma、三路 AA、拍摄冻结/clone、持锁归还、Off 回收分别列明实际回放边界和证据。回执只见证已经执行的离线检查；重建只重新核对相同组件身份，不暗示重新执行相机 ARM 回放、硬件完成或机身验收通过。

安装包可明确标为 `unverified_candidate`：验证收据逐项列出尚未闭合的接线及原因，仍绑定 AP、CP、AVCAM、MPR 四项散列并执行完整来源、分区和签名校验。候选封包不代表机身验收或根因确认。

顶层 `../build.py --stage all` 重新跑主机测试、组件构建、范围审计，并在 `package/BODYDATA.DAT` 输出加密签名包；签名、篡改拒绝、CRC、全部块及全量明文分别核验。独立源 ZIP 重建可添加 `--reference-dat /absolute/path/BODYDATA.DAT`：实际重新生成加密和签名内容，逐字比对只读输入，再解密核验与第二次重建分区完全一致，不另写 DAT。首次封装的四分区共 710,777,216 B，DAT 为 754,525,608 B；不要同时保留两套大中间件。签名使用外部 0600 私钥，源码包不含本机路径或私钥。

`dependencies/baseline_recipes.json` 保留 FL2/FL3 及必要挂载布局，从官方 CP 派生时 Gamma 表迁至 0x107e968，路由迁至 0x107eefc。自定义参数接管不属于基础配方，直接由本版 CP 源链接。`cp_aux/` 保留声音和比例，`lib/`/`vendor/` 仅供主机构建。第三方来源约束见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，保留辅助源码身份见 `provenance.json`。
