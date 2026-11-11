# 原生滚动夹具静态排查

范围：父 PT AP `470b36805d5c05f847e585100e63bd2517fe0a856e9b78b397826043ecdcde9e` 保持的原厂指令/relocation，以及 `verify_filter_fn.py`、`StyleReplay`、`UIReplay`。本任务只读固件，新增反汇编证据；未运行 CPU 模拟、被拒脚本或修改固件/测试源。以下是静态已证合同及父 agent 报告的故障，不是新的实机/运行通过回执。

## 两处确切夹具缺口

1. PC0、LR1832030 位于原 `1831fb0` 的 widget→UX manager 事件调用。widget+1c0 指向初始化时提供的 manager/context，读取其 VT+0 调用。该函数提交 `020f0001` 消息；消息 event+0、参数+4/+8、widget+1d0→消息+0c、其余参数+10/+14。`StyleReplay.begin()` 的共享 VT 只设置 +8/+20/+38，未设置 +0。因此第二次原生布局重建触发未定义 UX 服务。最小夹具修正是在这个已有 manager VT+0 提供明确事件提交端点，记录完整消息、返回0。不要覆盖 `1892414` 或写子树/输出。

2. libObj PC50137e3c、LR5017984c 是原 WidgetBase 注册撤销后的 Engine timer/observer registry 清理。`00179724` 中 179838→1768f4 将 Engine 指针加1b8，随后读取+5e8，即原 Engine+7a0，传 `00137e2c` 遍历。`UIReplay` 只将全局 Engine context 设置为60f00000零结构，Engine+7a0是0。因此原函数读registry+8失败。最小夹具修正可将60f007a0设置为另一个独立空服务 registry（如60f01000，至少0x40清零）；原注销逻辑继续执行并遍历空表。这是初始化既有明确 Engine 服务，不是填原Widget/滚动状态。更宽的替代是记录整179724注销并返回，但前者更窄且保留原函数。

证据：`scroll-boundary.asm`、`scroll-libObj.asm`、`scroll-engine.asm`。

## 为什么旧 child 仍是关闭/AS/CC/EBB

`1842aec(root,index)` 扫描 root+510 链表，通过每个 child 的 VT+180 返回值匹配**逻辑ID**，不是按可见槽序号找对象。

`1892068` 先调用 `1892048=(visibleRows−1)/2`。mode0五行时padding=2，缓存0/1为空，真正第0项“关闭”在逻辑ID2，filter12在逻辑ID14。实际text缓存地址 `owner+1de8+logicalID*9e8`；不能读+820断言名称。`1892c60` 也以owner+f10加padding找选中child，独立证明该合同。

只执行 `1892068` 会更新cache；它不改变rootcenter或child逻辑ID。root仍在center0时原子树0..5消费空空关闭ASCCEBB，不能由此判固件选择失败。

## 应恢复哪一段原生生命周期

原 type1c VT+148=`1891bcc` apply、VT+150=`18928a8` update。原正常链如下：

- 非动画且owner17c1=0：`18928a8→1892068`更新cache；
- 仅mode变化（`1891fb0`检查owner17c8与f0c）才调用`1892414`重构滚动root；
- 正常focus刷新使用`1892768→1844250(root,focus,1)`，随后`1843f94`调整可见子对象与逻辑ID；
- `1843f94→rootVT388=1845fb0`根据center、padding与范围创建、删除或复用原子节点；`rootVT398=1843310`提交原row更新callback；
- child callback `1892c44→18929b4`从真实root链查child，拷贝真实cache参数，执行原String consumer。

根测试连续12步只调用私有dispatch，而 `StyleReplay.begin` 将原viewVT+20/+50更新端点全部记录后返回；这会截断私有refresh后真正view/widget刷新。建议每次事件后执行原list apply/update并完成实际原row callbacks，观察实际childID和root+480动画状态。不要无条件每次重跑1892414，也不要手写rootcenter/focus/children。

如果root+480非0，原`18928a8`可因动画挂起而暂不处理新focus。应让明确Engine动画时钟服务触发原滚动tick。主动停止动画可执行原`1843678`（其自身清480并发原type3事件），但必须报告为“主动停止动画生命周期”夹具，不能声称自然Engine tick已测试。未完成正常tick全链时保留验证缺口。

## 子树与事件的实际原厂绑定

`1892414`原初始化root callback：

- root+1d8/+1e0 = owner / `1892c44`：row update；
- root+1e8/+1f0 = owner / `1892ef8`：touch/gesture；
- root+1f8/+200 = owner / `189303c`：interaction completion；
- root+228/+230 = owner / `1893358`：animation state。

`1893358`从真实消息+10/+18/+20取owner/事件/参数到`1893140`。可以记录已有原消息调度并调用这个真实handler；不要手写handler本应生成的原子树、选中背景和名称。

追加证据：`scroll-static.asm`、`scroll-static-extra.asm`、`scroll-root-ctor.asm`、`scroll-virtual-producers.asm`、`scroll-native-apply.asm`、`scroll-callbacks.asm`、`scroll-event-consumer.asm`。这些文件绑定保持的原厂指令，仅静态反汇编，不等价于执行。

## 精确的主动完成/即时布局建议

父 agent 明确需要可靠布局输出，不将它称为自然时钟动画通过。以下调用序列是静态推定、尚未在本子任务运行：

1. 正常调用list原VT+148/+150（1891bcc/18928a8）接受本轮真实project数据。
2. 若root+480非0，调用原1843678(root)，它自己清动画并发原type3消息；这一步只是停止动画，不会将center跳到desired。
3. 将S0设0.0，调用原1844250(root, owner+f10的实际focus, 0)。animate0通路来自原2414初始化，原函数自己完成center/geometry定位；使用已由原project写入的focus，不手写center或子节点。
4. 调用原1843f94(root)，让原VT388 producer依据新center/范围实际删除、复用、生成子节点与逻辑ID。
5. 对真实1842aec返回的child，调用原18929b4(owner, logicalID)，观察真正String输出。filter12的选中对象应是logicalID14。

此序列必须在回执列为“原厂动画主动停止＋原厂即时定位调用”，不称自动调度/自然动画已通过；不能单用1843678后循环native_update，因为后者会再次启动动画。正式固件实现未因此新增或改变任何hook。

## 后续指令预算排查

父 agent 后续报告原即时布局仍在2,000,000条上限停止：PC5012b388/LR50166610，先前PC50166390/LR50174cc4。新增 `scroll-loop-libObj.asm`、`scroll-loop-propagation.asm`确认：

- libObj174cc4为原 `ux::wgtsys::Widget::Widget()` 第一clip初始化；
- 166390为clip show字段setter；166610前调用13394c；
- 13394c仅将指针加8后调用12b384；12b384/12b110仅有界dirty flag操作，无这些地址内的自循环。

这些PC只说明在执行原Widget constructor/clip状态传播，不能凭InstructionLimit称Engine registry循环。原root388创建循环受start/end限制且每次逻辑ID递增；末端重绘可能一次创建约7个大型kind13内层item，每项具有嵌套String与大量原生控件。建议父验收只对该一次原1843f94调用提高有界指令预算（如10M），保留STOP返回检查，并记录root总数、center、范围、可见数、分配量和实际child数。若有界执行仍不返回，继续保留large滚动未知，不改固件使测试通过。本子任务未运行该建议。
