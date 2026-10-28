# 4.34 自定义滤镜 Fn 接入证据

最终验收入口为 `fn434_verified.json`；其 `AP_sha256` 与每个子回执必须对应同一个最终 AP。

## 实现

`patch_fn434.py` 在原厂 Fn 的 Color/Tone 组追加 functionID `0x635`。组头
`0x3e6f218` 的数量从 6 改为 7，原全零的 `0x3e6f3a4` 槽写入私人 ID，并逐字
复制 Creative Look 的拍照/视频/回放模式标志。原 6 项和顺序保持；私人项与创意外观
使用相同拍摄限制，回放模式不开放。这个候选表补丁改变 41 个字节，无新增代码或 BSS。

41 字节仅指候选表差分，逐字继承4.33。4.34修正4.33的图片资源类别错误：
`0x021c6410` 只保留为descriptor `+0x0c`帮助文字，`+0x60`恢复无静态图片sentinel。
新增20字节ASM对象，在原生图片查询 `0x1bd63b4` 仅将MID635转为原厂MID1e6，
继续执行原生当前Look选行/图片逻辑。其它22个对象逐字等于4.33；RX63480、BSS136384。
完整差分见 `../delta434_verified.json`，不改变默认Fn槽位。

本版只增加可注册项，不预先占用任何 Fn 槽位。用户需在“Fn 菜单设置 → 颜色/色调”
手动指定“自定义滤镜”。默认 Fn 槽位未改；地区模板仅修改已核对的颜色参数与 BK4
校验，不替换个人 Fn 设置。

注意：原厂 Creative Look 的 functionID 为 `0x1f2`，转换后的 MID 为 `0x1e6`；
自定义滤镜的 functionID/MID 均为 `0x635`。两者分别保留。

## 原生保存与读取

实际 Fn 指定入口为 `0x21e45c8`。当前目标 getter `0x28a86f8` 的 targetID
`0x38f..0x39a` 对应拍照 12 槽，`0x39b..0x3a6` 对应视频 12 槽。当前选项由
`0x28a8720` 读取，原生 switch 根据目标槽选择 setter，将 `0x635` 原值写入。

拍照模型 PID 为 `0x7ad..0x7b8`，视频 PID 为 `0x7b9..0x7c4`，它们与 BKID
`0x443..0x44e` / `0x44f..0x45a` 是不同编号体系，不可混用。当前数组的原生 getter
为 `0x28b1134` / `0x28b115c`，没有以固定假指针替换。

`replay_fn_save434.py` 执行完整指定入口、目标 switch、原生 setter 和提交 destructor。
随后执行每槽原生 backup-shadow save/restore helper，再通过首屏真实读取入口
`0x216eb9c` 重新取回 MID。24 槽 × 默认目标存在/不存在 × 两个 PIE 地址，共 96 组。
每组同时检查其它 23 槽不变，通知 PID 与目标槽相符。

## 回放边界

`fn434_candidates.json` 绑定最终 AP，执行通用候选 dispatcher、Fn builder、模式标志、
私人 descriptor 查找与 availability；其它原厂菜单的产品可用性和当前拍摄模式是环境
fixture。覆盖 26 模式 × 拍照/视频/回放 × 两 PIE，以及两 PIE 的 20 组候选列表构建。

`fn434_save_roundtrip.json` 中，锁、外部 observer/提交后端、更新服务和注册页 manager
动作是明确的 fixture。日志 copy 服务只复制声明的字节。原生 backup-shadow 指令往返
证明模型值不会在这一层截断；没有执行实体 eMMC 写入、相机重启或冷启动恢复。

Fn 首屏事件、页面进入、名称与图标、返回路径由独立的 `../fn_activation/` 证据接续，
最终总回执逐项列出真实执行地址、fixture 和剩余边界，不能用候选列表可见代替整个
Fn 功能验收。物理 LCD 字体/图标布局、相机事件时序、Fn 冷启动保持和拍摄仍待实机验收。

`fn434_registration_labels.json` 单独执行注册候选文字路径：真实 Fn builder →
`0x1bc69a0` 当前列标题解析 → 完整 `0x21e77c0` presenter → `0x185ba10` 子
`view_string` 参数 → `0x1885b38` 现有桥，最终 UTF-8 为“自定义滤镜”。覆盖拍照/
视频与两个 PIE。原厂其它项的动态标题为 fixture，私人项与 Creative Look 的标题
解析器实际执行；后者仍为原资源 `0x0200a2fd`。列表更新只回放指定标签传递窗口，
不把它当完整图形后端或物理字体测试。

独立激活回执覆盖 48 次实际 Enter 到 C2→D9 原生请求入队、2 次私人页关闭请求；
另 6 组执行真实 screen-stack push/pop 并保留下层页面。返回的 Fn presenter 构造
是 factory fixture，其实际返回指针随后在同一 VM 中执行原生 Fn 标题、tile、renderer
与 sprite 资源写入，标题保持“自定义滤镜”，sprite图片与同状态原厂Creative Look输出一致。事件队列的系统调度、真实对象构造及显示仍未执行。

整个目录只进行本地固件分析与离线指令回放，无相机、SD 实物或远端操作。

4.34动态图标证据覆盖12个命名Look×两PIE、同一presenter完整原生12槽刷新288组参数；
外部原厂资源证明覆盖两方向48条原生image type6记录和70×35像素主机解码。
总回执绑定外部冻结manifest及全部sources/artifacts，并对比保留原生helper身份。
帮助文字不是图标oracle；普通主菜单左侧小logo已按用户要求移出本版范围。
自定义记忆Look值10..15与AUTO16、observer投递、实际LCD加载仍不在离线通过范围。
