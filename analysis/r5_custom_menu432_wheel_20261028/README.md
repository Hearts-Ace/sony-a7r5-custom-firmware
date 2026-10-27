# R5 4.32：旋转控制轮与自定义滤镜菜单同步

用户确认4.31上下按键正常，但旋转控制轮仅切换滤镜、菜单高亮和名称不变。因此4.31控制轮交互未通过，原来的按键/触摸回放没有覆盖205旋转事件，不能代替实机验收。

本版基于冻结4.31，只修改生产源码menu_research/r5_filter_page425.c。原厂D9的205事件此前进入原生dispatcher而没有修改私有g.focus或重画；新页将2050000/4与“下一项”、2050001/5与“上一项”接入同一个submit(0)流程。每个原生事件固定一步，连续事件逐次处理；跳过未配置项并在关闭/最后一项停止，不从message猜测合并步数。2050002/3属于已移除的原厂参数调整，私有页吞掉整个205族，包含请求未完成、MID已变及关闭后的残留输入，防止误入原厂Look设置器。

原厂合同来自assets/firmware/a8d5cd444bf0-appFw.so（SHA256 a8d5cd444bf08a03a70aedc3cc32bdd857b89b468ac10bf8365d640e8d390d75），证据见wheel_evidence/README.md、native_wheel432.json和probe_native_wheel432.py。两PIE共36组原指令验证路由表、方向、固定一步及4/5重投；没有找到01/04表中205的原始别名，不伪造raw映射。

当前AP的menu_research/replay_wheel432.py核对26组：双PIE、两布局、全部/稀疏/空/末项配置、双向连续滚动、边界、与按键混用、确认及关闭残留、pending、失败、serial失效、MID变更和无关原生controller委托；同时回放冻结431的8组事件，确认它们漏回原生dispatcher且没有私有请求/投影更新。worker及绘制完成是明确fixture，预览提交不等于观察到实际ISP帧。原生列表生成/滚动76例、父级销毁重建6例/78值另行验证，180组SD、15项worker、7项诊断及跨核30选择/丢SEAL ACK恢复均重新绑定当前AP。

4.31原生列表与全称、移动应用保存留页/确认返回、父页原生重建和错误分类保留；4.30四个启动生产源码逐字保持。CP精确继承423（SHA256 8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d），4.22参数和网格生命周期保持。BIN v4、强制网格、原厂Gamma尾部保持，无更新按钮及右侧调整入口。

执行run_offline432.py可运行本地回归；Unicorn在macOS沙箱中SIGILL，需要已批准的同一窄runner在沙箱外执行。release_gate432.py门控当前回执，package432.py封装新包，verify_delivery432.py独立校验签名、CRC、篡改拒绝、AP/CP及全部明文字节。最终交付位于research/r5_custom_lut/build_r5_4.32_wheel_20261028/；仅release_tests/delivery_verified.json的passed=true表示独立交付核验完成。

本轮无相机、SD实物、fastboot、Web或GitHub操作。物理滚轮方向和速度、GUI事件队列、字体/透明度/触摸、冷启动和预览/JPG仍待用户实机验收。原始镜像和历史交付冻结，不修改首次采集资料。
