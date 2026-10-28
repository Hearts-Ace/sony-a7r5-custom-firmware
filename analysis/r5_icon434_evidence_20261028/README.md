# 原厂 Creative Look 动态图标证据（4.34 接入参考）

4.33 使用的 `021C6410` 是帮助文字资源，不能交给图片控件。本目录对冻结 4.33 AP 中未修改的原厂图标逻辑取证；4.34 最终 AP 的私有菜单转发、激活、返回和刷新另由 `r5_firmware434_20261028/fn_activation/` 验证。

## 已执行的原厂逻辑

`1BD642C(MID) → 1BD63B4(self,MID) → 1BD62AC → 1BC50EC` 读取 Creative Look 描述符的选中值回调 `1C05F18`。该回调通过原生 `28AE4B0` 取得 PID `690` 的模型存储 `7F207E8`，按 `3F4A280` 中 19 行的 `+34` 值匹配选中行。随后 `1BD6384 → 1BD5840 → 1BD18E8` 得到行图片资源；Fn 的 `2170374` 对这 12 种外观均返回图片类型 6。

`replay_stock_icons.py` 直接执行上述 A64 指令，在同一 VM 中修改真实模型存储并查询各状态，两个 PIE 地址共 24 例。当前 Look getter、选中行解析、图片选择和返回资源均没有 stub。`stock_icons.json` 保存数值、选中行、真实资源和执行轨迹。

必须加载两张不同的原厂表：行注册表 `5030590..5046300`（5591 项），以及行 alias 表 `3E52E40/AEB8`（5591 项，启动构造 `16FBF5C..16FBF84`，GOT `592F4C8`）。旧 VM 遗漏后者时会默默解析到默认行 `15D8`，结果不能作为原厂动态图标证据。

## 真实资源核验

`verify_image_resources.py` 把上述真实返回值交给原厂 R5 `libObj.so` 的 `123840`，执行真实 13-bit bank/index 分解，再执行 `122930 → 122870` packed-index reader；`118858` 对每条记录确认原生类型 6。文件加载和 bank cache 是明确的内存文件 fixture，每条资源的索引、记录地址及资源 ID 均由原指令计算。

12 种外观 × 23/32 两套图片 × 两个 PIE 地址，共 **48 条**图片记录通过。每条记录均为 70×35，Sony LZ77 完整解码为 5600 字节（80 像素对齐，16-bit 像素）。`image_resources.json` 保存实际文件/记录/payload/解码数据的散列和偏移；`look_mapping.json` 的名称来自原行标题资源及英文 UXC，未按数值猜测名称。

| 原厂 Look 值 | 英文简称 | 实际图片 ID |
|---:|---|---|
|0|ST|02000713|
|1|PT|02000719|
|2|NT|02000715|
|3|VV|02000714|
|4|VV2|02002261|
|5|FL|02002262|
|17|FL2|02004AAF|
|18|FL3|02004AC7|
|6|IN|02002263|
|7|SH|02002260|
|8|BW|0200071E|
|9|SE|0200071F|

`021C6410` 的真实图片查询请求 bank `E3`，图片库无该 bank，原生选择返回空。它实际在 `string_english_f.uxc` 的 `0x9C70` 位置存储为 `1E1C6410`，内容为 “Selects your desired image processing.\nEnables customized image expressions by applying further detailed settings.”。

原始图片解码预览与完整Sony图片库仅作为本地证据保留，不包含在公开源码中。

预览前两行是 23 版、后两行是 32 版；每两行依次为 ST、PT、NT、VV、VV2、FL、FL2、FL3、IN、SH、BW、SE。PNG 使用软件 LZ77 和 RGBA4444 解释，不能代表相机 `/dev/ldec`、字体或物理 LCD 已执行。

## 最小接法与边界

只在 `1BD63B4` 的图片查询入口拦截 `W1==635`，改为 `1E6`，然后重放原 `CMP W1,#CA4`（字节 `3f903271`）并跳转 `1BD63B8`，使原函数继续处理。`X0=self`、LR/SP 和 callee-saved 寄存器保持。非 635 请求仍走原流程；不更改私有 selected getter、滤镜选中值、标题、页面或 Fn 槽。Fn type 对当前 12 种状态均为 6，无需把私有选中行替换成 Creative Look 行。

普通 `1BD5630 → 1BCEF8C → descriptor+C` 是帮助文字查询，旧 `20D34F8/20D1E54` 回放不构成图片证明。用户已要求不再追查主菜单左侧小 logo，本目录不对该 UI 消费者作结论。

模型字段、启动后的原表容器和 OS 锁/通知服务使用继承回放环境；当前机身状态、完整 Linux/GUI 生命周期、订阅事件、hardware decoder、冷启动及实机画面不在本目录的验证范围内。最终新 AP 须另验证私有/原厂查询在相同模型状态下逐项一致。

所有内容只写本新目录，冻结 4.33、原始备份、相机、SD 实物和远端均未改。`frozen_manifest.json` 绑定本目录产物和全部直接源文件。复现使用 `PYTHONPATH=vendor/audit-python .venv/bin/python -B`，依次运行两个回放脚本，再运行 `finalize_evidence.py`；Unicorn 在本机须在允许本地原指令回放的执行环境中运行。
