# R5 原厂 Fn 纵横比样式合同（只读）

本记录限定 `projects/firmware/releases/4.56-aspect-pt-20261110/appFw.so`，SHA256 `470b36805d5c05f847e585100e63bd2517fe0a856e9b78b397826043ecdcde9e`。结论来自该 AP 保持的原厂表、指令及 ELF RELATIVE relocation；不代表最终候选 LCD 验收。只新建证据，未修改冻结源码、菜单实现或原机资料。

用户边界：Fn 纵横比菜单只增加图标与新比例，保留原厂样式。自定义滤镜复用其样式，将左侧图像行换成简称，右侧显示当前全称。保留独立滤镜交易、PT 切换和声音路径。

## 原厂选择器与私有滤镜壳

原厂 select 表为 vertical `0x414ead8`、horizontal `0x414fef8`，各 98 项 × 52B，每项 13 个 uint32。word9 高16位为 widget index，复制到私有壳时须重映射；word10 为 packed x/y，word11 为 packed width/height。完整值见 `native-styles.json`。

横向 Fn 纵横比原厂控件如下，纵向坐标仍应读取原表，不另行设计：

|select index|type|内容|x,y,w,h|D9 建议目标|
|---|---|---|---|---|
|20|28 / 0x1c|原生滚动列表|1,51,112,330|9|
|21|2|当前全称/值|128,64,486,46|11|
|22|2|标题|128,8,450,46|12|
|16|0|左背景/分界 `02002cac`|0,0,114,426|8|
|6|0|底栏背景 `02000321`|0,420,640,60|4|
|7|24|原厂操作提示|148,434,484,40|5|
|23|2|帮助文字 `0200a000`|8,434,138,40|14|
|33|15|上箭头 `02000016`|39,28,34,18|30|
|32|15|下箭头 `02000010`|39,380,34,18|31|

原厂 generic selector constructor `0x1db5ee4` 使用约 `0xef00` 对象，98 个控件以及自身 view/map/MID/focus 字段。私有 D9 presenter 为 `0x5a10`，拥有既有滤镜生命周期与交易。因此直接切换整个 generic scene 会扩大改动；在私有 D9 内复制必要原厂样式片段更合适。不得改写共享 select 表以修自定义滤镜。

## Image、箭头与底栏实际消费

Image/type0 的资源在 parameter `+0x3c`，不是 `+0x30`。后者在 constructor 后为0；检查其为0不能判断图片已准备。原厂 Image apply/update 仍应消费 `+0x3c` 中的 `02000321` 或 `02002cac`。

箭头/type15 原厂 selector producer `0x21fb088..0x21fb100` 根据 active style20 写 parameter `+0x39=1,+0x3a=0`；其他样式反向。parameter `+0x2c` 控制实际显示，方向资源仍来自原始样式。只设 show 不能代替原厂方向/样式参数。

底栏/type24 constructor `0x183d888` 默认 parameter `+0x30=0xa7`，原厂 update `0x183e0d0` 对0xa7跳过四个内容组。故构造成功或 show1 不等于确定/取消已输出。原厂 selector `0x21fc0cc..0x21fc110` 在普通 Fn 上选择 scheme8（另一上下文 scheme4）。visibility producer `0x1b2af28 -> 0x1b2b0e8 -> 0x1b2b070` 写 selected layout parameter `+0x34=1`，show `+0x2c=1`。

scheme8 来自 relocation 解析后的原厂 tables：resources `0x375ed30`，modes `0x3760c50`，events `0x37601f0`，indices `0x375ec88`。实际组合为：

|组|mode|图片资源|event|width|
|---|---|---|---|---|
|0 确定|2|0200a28c|0201000c|72|
|1 取消|2|0200a2b0|0201000f|166|
|2 帮助|2|0200a26d|02030000|65|
|3|0|0|20000001|0|

`0x183e0d0 -> 0x183de24` 使用上述表并经 `0x183da84/0x183dc38/0x183dcec` 写真实 String/Image/touch 子控件，随后原生输出。应复用这条 producer，避免另外画提示。底栏位置与样式已经是原厂的一部分。

## native1c 左侧简称的原厂文字通路

parameter base = owner `+0x1d8`。原厂行数据为 imageA `+0x30`、imageB `+0x430`、text `+0x830`；因此首行 text 位于 owner `+0xa08`。行数/模式/焦点为 parameter `+0xd30/+0xd34/+0xd38`，即 owner `+0xf08/+0xf0c/+0xf10`。

`0x1892068` 从首行 text 选内层 item kind：将 text-1 与 `0xfffffffd` 作无符号比较，只有 text0或FFFFFFFF走 kind12 图像；普通有效正数 text token 走 kind13 String，mode3 时 kind19。此条件也决定各缓存行的 text 或 image 字段。私有简称 token 可沿原厂 String 行工作，不需增加新的文字 renderer。

可见模式由 `0x376c304` 四字节 `0f000f02` 跳表确定：mode0=5行、mode1=7行、mode2=5行、mode3=3行。不能把 mode1 当成5行。

`0x18928a8` 更新驱动嵌入 owner `+0x12a0` 的滚动根，`0x1892414` 配置/构造滚动布局，`0x18430e8/0x1843f94` 驱动缓存与异步状态。行回调 `0x1892c44 -> 0x18929b4` 通过 `0x1842aec(root,index)` 查 root `+0x510` 链表中的真实子对象，并 dynamic_cast 为 `23view_list_menu_cmn_item`（RTTI5789858），拷贝 `0x9e4` 的行参数，再调用子对象 VT+150 更新。

内层 item vtable address point `0x5789880`，VT+150=`0x1857084`。kind13 路径 `0x185721c -> 0x1856410` 更新内嵌 String owner `inner+0x14728`，将 inner `+0x820` 的文本资源写 String parameter `+0x30`，经 `0x1885688` 到真实文字绘制 `0x1885b38`。目标 AP 此处已有 detour `0x8e986f0`（原有 `r5_filter_menu_name_draw`），所以可复用已有简称资源处理。kind12 则走 `0x18561b0` 图像路径。

## 验证边界

仅执行静态反汇编和读取目标字节，未执行相机/USB/SD/网络操作，未运行已拒绝 `revalidate_h.py`。原生列表 update 被调用但无 name_char，不足以证明简称缺失或输出通过：真实 child cache 可能尚未由原厂异步滚动生命周期建立。应检查 `0x1842aec` 返回的原生子对象、实际 kind13 和 String 资源消费。不得手造 child tree 作为原厂输出验收。

负责实现的父 agent 将单独记录最终候选身份、实际输出/焦点/取消/异步验证与封装构建。本文不将构造成功、gfx提交或旧包回执写成实体 LCD 通过。
