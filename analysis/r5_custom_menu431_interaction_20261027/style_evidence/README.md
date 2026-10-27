# 4.31 原生左列表与候选投影证据

本目录只读分析和离线回放，不操作相机、SD、Web 或网络。原厂 AP 来自统一资产 `assets/firmware/a8d5cd444bf0-appFw.so`，SHA256 为 `a8d5cd444bf08a03a70aedc3cc32bdd857b89b468ac10bf8365d640e8d390d75`。最终候选 AP 的 SHA256 为 `3c832336b73fc5d8b5a902faebd07249821888a17d3609831def42d4419ba941`。两类回执用途不同，不能用原厂回执替代候选绑定。

## 原厂列表契约

原 D9 style 表位于 `0x405fc78`、`0x4060398`，每条 52 字节，共 34 条。左列表是 style[9] 的单个 `type 0x1c` 原生控件；原横屏外框为 `(1,51,112,330)`。七个独立 String 加 `>`/`*` 前缀不能复用此控件的原生高亮和滚动行为。

`type1c` 参数数组及关键字段如下，相对参数首地址：

| 偏移 | 含义 |
| --- | --- |
| `+0x30` / `+0x430` | 两组图标资源，每组 256 项；纯文字行填 `0xffffffff` |
| `+0x830` | 256 项文字资源数组，候选使用短名称资源 |
| `+0xc30` | 每项禁用状态字节；可用项为 0 |
| `+0xd30` | 实际逻辑项数量，不含首尾空白位置 |
| `+0xd34` | 模式；0/2 为五行、1 为七行、3 为三行 |
| `+0xd38` | 实际列表绝对 focus 索引，不加空白偏移 |
| `+0xd3c` | 所属 MID，候选为 `0x635` |
| `+0xd40` | 1 启用原生选中高亮 |
| `+0xd44` | 原厂 D9 经 `0x28cc860` 取得的值 |
| `+0xd56` | 原厂 D9 设置为 1，候选保留 |

mode0 由原生 `0x1892048/0x1891fe0` 算出两个前导空白位置。画面五行对应 `focus-2 … focus+2`，边界越界保留空白，不把首尾项强制填满窗口。稀疏配置应先形成实际列表，然后以列表索引设置 focus；配置号不能直接当稀疏列表索引。

原生 `0x1892068` 读取 `owner+0x1d8` 的参数，生成从 `owner+0x1de8` 开始、步长 `0x9e8` 的行数据。行 `+0` 为文字资源，`+0x304/+0x308` 为图标，`+0x37c` 为高亮，`+0x37d` 为禁用状态。`0x16f389c` 初始化原生几何表；context0 的 mode0 纵向行内 rect 为 `[20,0,70,60]`。

`0x1892414` 配置 ScrollContainer，纵向步长经 `0x1892654/0x1892630` 从只读表 `0x376c340` 读取；context0 为 **66**，不是外框高度随意除以行数。候选横屏列表维持原厂 112×330；竖屏使用左侧 150×330。两个布局的五个独立触摸 overlay 均按 66 排列，并按相同五行窗口映射配置。

## View pool 与分配边界

原厂 `0x182ae14` 初始化六个 view，并将指针写到 `0x74c0470` 表；容量来自实际初始化指令的立即数，并不是该指针表中另存的容量数组：

| pool | 容量指令地址 | 容量 |
| --- | --- | ---: |
| 0 | `0x182ae94` | `0x600000`（6MiB） |
| 1 | `0x182aed4` | `0x400000`（4MiB） |
| 2 | `0x182af10` | `0x400000`（4MiB） |
| 3 | `0x182af54` | `0x40000`（256KiB） |
| 4 | `0x182af98` | `0x20000`（128KiB） |
| 5 | `0x182afd4` | `0x20000`（128KiB） |

构造器 `0x182ad30` 将 arena 指针写入 view `+0x3e98`、容量写入 `+0x3ea0`；allocator 使用 `+0x3ea4` 记录已用量。真实 `type1c` widget allocator `0x18204a0` 请求 `0x9ffd8` 字节，parameter-only allocator `0x1822adc` 请求 `0xd68` 字节；原生 create-screen 入口为 `0x182b41c`。因此不能按 String 的小内存需求推断原生列表一定适合全部池。候选仅在容量至少 `0xb0000` 时使用原生列表，小池保留文字回退。

常用菜单路径的 pool 选择由独立的 [父菜单回放](../parent_evidence/README.md) 绑定：`0x1e97948` 读取屏幕记录 `+0x10` 后调用 `0x182ae14(index)`。D9 与 2D7 的该字段均为 0，实际离线 factory 回放参数也均为 0，因此常用路径使用 6MiB 的 **pool0**。该字段与 presenter 层级字段 `+0x18` 不同，不能互相代替。这里没有取得机身实时内存遥测。

## 回执与实际覆盖

`probe_native_list431.py → native_list431.json`：48 例通过，两种加载偏移 × 四种 mode × 六种 focus。执行原厂 `0x16f389c`、`0x1892068`、模式 helper 和 `0x1892414`，核对资源、唯一选中项、行内几何、滚动配置和绝对 focus；报告还记录六个容量 MOV 指令的实际字节及解码值。`native_list_disassembly.txt` 保存对应指令摘录。这份报告绑定原厂 AP。

`replay_candidate_list431.py → native_list431_verified.json`：76 例通过，绑定上述最终 4.31 AP。两种加载偏移、横竖两布局、完整/稀疏/空/仅末槽四种 mask，遍历全部可用 focus。执行编译后的私有页面移动及投影，把参数复制到原生 owner 后执行原 `0x1892068/0x1892414`；核对列表数量、绝对 focus、唯一原生高亮、真实短名称 getter/资源桥接无前缀、330 高/66 行距、五行边界空白，以及 overlay 事件对应配置且保持在页内。

这些是 CPU 指令回放，不是完整 GUI 执行。名称发布存储、页面工厂、worker 完成结果和低层 scroll setter 为明确的 fixture；候选组合测试将已编译的 style 外框写入 owner，因为 native create-screen/allocator 在其它回执独立执行。实际 ScrollContainer 放置、字体栅格化、GUI 触摸命中、LCD 遮挡和机身时序没有在此观察。不得把本目录通过改写成实机菜单外观或交互已经验收。

固定运行入口：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=vendor/audit-python .venv/bin/python analysis/r5_custom_menu431_interaction_20261027/style_evidence/probe_native_list431.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=vendor/audit-python .venv/bin/python analysis/r5_custom_menu431_interaction_20261027/style_evidence/replay_candidate_list431.py
```

本机沙箱内 Unicorn 被 SIGILL 中断，最终回执来自获准的固定脚本沙箱外离线运行。AP 或源码改变后，应重新执行，不能仅替换回执散列。
