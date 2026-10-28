# 4.34 Fn 动态图标、激活和返回证据

最终 AP `../ap/appFw.so` 的 SHA256 为 `c61d151fd7da84896d675dd7be26a8319156598206556e6e5d50ea2da11406b3`。回放先校验 `../ap/ap_build.json`，每份回执再绑定实际 AP 和执行脚本散列。全程只处理本地固件，没有连接相机。

## 修正与真实资源来源

4.33 把 `0x021c6410` 当作图片是错误的：它是 Creative Look 的帮助文字。旧回放只证明这个编号能送到 sprite 参数，未验证资源类型和加载。旧回执保留为历史，不改写成成功结果。

4.34 保留 descriptor `+0x0c` 的帮助文字，恢复 `+0x60=0xffffffff`；仅在原生图片查询 `0x1bd63b4` 入口把 MID `0x635` 转为原厂 Creative Look MID `0x1e6`，重放原始比较后返回 `0x1bd63b8`。functionID `0x1f2` 与其归一化 MID `0x1e6` 不可混淆。私有标题、页面入口和滤镜选择继续使用 MID `0x635`。

真实图片通路为 `0x1bd642c → 0x1bd63b4 → 0x1bc50ec`：通过真实 getter `0x28ae4b0` 读取 Look 模型地址 `0x7f207e8`，选择原厂当前行，再从行取得图片。ST 为 `0x02000713`，PT 为 `0x02000719`，FL 为 `0x02002262`；FL2/FL3 分别为 `0x02004aaf/0x02004ac7`。完整数值与英文标签见外部 `look_mapping.json`。

原始行树之外还有独立的 5591 项 row-alias 树。本回放保留完整原始两树；省略 alias 会静默回落到默认行和 `0x02002290`，不能代表实际原厂图标。

## 最终回执

- `fn434_activation.json`：48 次真实 Fn Enter（拍照/视频各12槽 × 两PIE）、2 次私有关闭请求、4 次帮助文字投影。12 个命名 Look × 两PIE 共24例，均用**同一最终 AP、同一模型状态下原生 MID1e6 的输出**作为 oracle。
- 每个动态图标用例在同一 presenter 上只改变真实 Look 模型值，执行完整原生 `0x21706d0 → 0x21705a8` 刷新。12 槽交替使用私有 MID635 和原厂 MID1e6，共检查288组tile参数；真实 `0x183c85c → 0x183c138` 将同一图片和type6写到sprite资源参数。
- `fn434_stack_restore.json`：6 次 `C2 → D9 → C2` 原生push/pop。旧Fn presenter销毁、返回时重建；在同一VM中对原生pop安装的实际presenter指针继续运行原生标题、完整12槽刷新及sprite资源写入。

独立资源证据位于 `../../r5_icon434_evidence_20261028/`。原厂 `libObj.so` 的 bank选择、packed索引查找和type读取实际执行，12 Look × 两方向 × 两PIE共48条均找到image type6；Sony LZ77的主机解码得到70×35、5600字节像素。旧帮助编号在image bank中查无，在英文文字库中找到帮助正文。外部冻结manifest、脚本、原AP、libObj、6份image UXC、英文标签/帮助源、解码参考及预览均进入最终Fn散列绑定。

`evidence_contract.py` 统一检查激活/返回回执、动态oracle与资源证明，并逐字对比4.34与4.33的6段原生Look/图片helper，确保外部原厂证据对应本版保留的真实代码。`../fn/fn434_verified.json` 是总入口。

## 证据边界

OS锁/日志、容器构造、screen对象工厂、析构/方向/通知、view-map和sprite存储/提交为明确fixture。原生查找、真实PID地址、Enter成员表、入队、关闭、栈操作、图片查询、Fn刷新与sprite参数写入均实际执行。view参数到widget字段的标准绑定用字节复制表示。

本回放改变Look后明确调用原生刷新，没有执行observer/event-loop通知投递、GPU、LCD或相机图像解码硬件。LZ77是主机模型。12个命名Look通过；自定义记忆值10..15和AUTO16未建立独立场景，生产转发保留其原生逻辑，但本轮不称已覆盖。相机实际图标加载、时序、冷启动与拍摄验收仍独立。

用户明确取消普通主菜单左侧小logo追查，该项不属于本版验收。`0x1bd5630/0x20d34f8/0x20d1e54` 只记作帮助文字通路，不记作普通菜单图片消费者。`probe.py/probe2.py/xrefs.py` 仅为历史定位实验，不能作为生产结论或当前验收入口。
