# 4.33 Fn 激活、两路图标和返回离线证据

冻结 AP：`../ap/appFw.so`，SHA256 `65bd99095f626f990890156c0e536d56394c75313452caa451322e1148c1faec`。本目录只写研究脚本和回执，没有修改生产 AP/C、冻结颜色输出或历史证据，没有连接相机。

## 最终通过

- `fn433_activation.json`：48 例真实 Fn Enter（still/movie 各 12 槽 × 两 PIE），8 个图标 getter/普通菜单及通用列表 producer，2 例私有 controller 的真实关闭请求。实际 Fn 标题、tile 参数、tile renderer 和 sprite 资源写入在两 PIE 通过。
- `fn433_stack_restore.json`：6 例 C2 → D9 → C2 原生屏幕栈 push/pop（两 PIE × 三种下层），重建 Fn controller/presenter。每例在**同一个模拟器**里对原生 pop 安装的 presenter 指针继续执行 Fn 标题、tile producer、tile renderer 和 sprite writer：标题“自定义滤镜”，图标 `0x021c6410`，启用资源绘制。

`probe.py`、`probe2.py` 和 `xrefs.py` 是定位工具；正式结论以上述两个最终 AP 回执为准。

## 真实通路

Fn 首屏是 `scr0135_0001_controller`，SID `0xc2`。工厂表 `0x50707e8 → 0x1d2ba30`，wrapper 向 ctor `0x1d2b894` 传入 `w6=0xc2`；ctor 安装 vtable `0x58d6eb8` 并写 `controller+0x178`。

保存后的槽位由原生 `0x216eb9c` 根据拍照/视频模式和 `5aa/5ab` 哨兵读取，返回 MID `0x635`。真实事件 `0x0201000c` 经 `0x1a5de30` 的原厂成员表进入 `0x216f2d8`，读取真实 PID `0x3b2`，完成两次 ID 归一化、descriptor screen 查找后调用 router。实际入队记录为 `(0xc2, 0xd9, 0xc2, 0, 1, 0)`；PID `0x3b2=635`、ROW PID `0x3b7=1607` 保持。

普通菜单图标由 `0x1bd5630 → 0x1bcef8c` 从 descriptor `+0x0c` 读取；`0x20d34f8` 与通用列表 producer `0x20d1e54` 都真实产出 `title=0x02ff4230 / icon=0x021c6410`。原厂 Creative Look descriptor `0x5858b08 +0x0c` 为相同资源。名称桥仍输出“自定义滤镜”。

Fn 图标 `0x1bd642c` 未命中特定行图标时，经 `0x1bd57e0 → 0x1bcefdc` 读取 descriptor `+0x60`。真实 Fn tile producer `0x21705a8` 输出 type `6`、resource `0x021c6410`；实际 renderer `0x183c85c → 0x183c138` 将资源写入 sprite 参数 `+0x3c`，`+0x4c=1`。这是 sprite 图形资源路径，不经过文字资源的 `name_id`。

Fn 上方标题由 `0x2170734 → 0x1bd54d8` 写入 type2 view 参数 `+0x30`，资源 `0x02ff4230` 经已有 `0x1885b38` 桥输出 UTF-8“自定义滤镜”。注册候选列表文字另见 `../fn/fn433_registration_labels.json`。

私有 controller 通过真实 D9 工厂槽进入保留对象构建门，私有返回事件 `0x0201000f` 执行真实 `r5_filter_parent_refresh425 → 0x1bd55fc → 0x1bc8eb8` 解析已提交简称，再经 manager `+0x20 → 0x1d15798` 写关闭请求。原生下层 `0x1ec5304 / 0x1ec557c` push/pop 回放确认：**Fn C2 和 D9 都占 presenter 层0，进入时旧 Fn presenter 被销毁，返回时重建 C2 presenter**。不能套用主菜单 2D7 保留旧 presenter 的结论；生产私有页没有持有或解引用旧 Fn presenter。

## Fixture 与证据边界

- 完整原厂 menu/row key-value 对和实际初始化的私有 descriptor 用平衡树构造；分配/树构造本身没有执行，原生查找、归一化和对应 producer/handler 实际执行。
- OS 锁、日志、screen validation、通知外发，以及 memcpy/memset 为明确 fixture；当前 Fn PID 存储、读槽、事件成员映射、screen getter、实际路由队列和关闭请求执行原生指令。
- 首屏激活前把真实读槽输出写入真实 PID3B2 存储；首屏焦点移动/物理按键传输不在本回放中。Fn 注册/影子恢复由独立 `../fn/` 回执覆盖。
- 私有 controller 执行真实编译后的工厂和 dispatch，原厂 ctor `0x1d2e2f0` body 是初始化对象 fixture；当前滤镜服务固定为0（“关闭”）。真实简称查找、父值判断和关闭请求没有桩替换。完整 worker/提交/失败留页由主代理既有回归覆盖。
- 屏幕栈回放执行真实 push、close、iterator、pop；controller/presenter 工厂、析构、方向和 open/close 通知是对象/OS fixture。当前 SID 的外层 caller 更新及事件循环没有执行。pop 从真实栈恢复 C2 并安装工厂返回的 presenter 后，标题/tile 重新投影在同一 VM、该相同指针上执行。
- 标题回放隔离 `21704ac/21706d0` 两个独立 tile refresh，随后直接执行真实 `21705a8` tile producer。view map 和参数对象为 fixture，标准 view 参数到 widget 字段绑定用明确字节复制表示。实际 tile renderer 和 sprite 参数写入执行原生指令；sprite 存储/提交、相邻 value/highlight 子控件为 fixture。
- 文本桥验证到 `name_char` 的实际 UTF-8 参数；图标验证到 sprite 资源写入。没有执行字体光栅化、GPU、LCD、真实 UI 事件循环、eMMC 提交、冷启动或拍摄，不能据此称实机已验收。

`frozen_manifest.json` 绑定本目录正式脚本/回执和直接导入、生产 AP/C 依赖。完成后目录冻结，后续生产改动必须重跑对应回执，不能只改散列。
