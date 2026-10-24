# 4.25 私有 D9 透明菜单与同步退出

本目录是新 4.25 源码和离线回执；没有修改冻结的 4.23/4.24、首次镜像或实机证据。基线的当前实机状态以根 README 与 DEVELOPMENT_RECORD 及原始日志为准。

## M4 方案与 R5 绑定

参考用户提供包内 `files/0802.c` 的 D9 自定义页面：克隆运行时已重定位 vtable，使用原生样式和 view 工厂，Background2 不构造 Widget，而不是把 mask0 误写成透明。mask0 会构造真正 Widget；保留 Live View 原生壳。字符串复用原生 type2/view_string，与现有私有资源名绘制 hook 一致。M4 曾直接改变样式项类型与位置，本版也仅使用原生类型。

R5 D9 controller/presenter factory 原槽分别 0x5071088/0x5071080，原函数 0x1d2e488/0x1e1e1a4；新页面只针对 MID0x635。主父页是 SID0x2d7，实际 factory0x1d90c7c 由新窄 wrapper 捕获真实构造结果，不猜测 pool 槽位。私有 controller 0x308、presenter 0x5a10 分别由 OSAL 分配；base destructor 与自有一次释放分开。stock MID 原工厂继续执行。横竖重排使用真正 presenter vtable addresspoint+0x30。

## 交互和父值提交

左侧关闭/可用配置简写最多7项滚动；右侧全称；顶部更新滤镜。键盘和原生触摸都进入同一提交入口。先绘制同步状态，再向常驻 worker 提交命令；UI 每10ms yielding，最长20秒，严格匹配 command sequence。成功选择必须先完成原生父页 update，再验证其真实值字段，才提交一次 pop。失败留页，更新滤镜必须由 worker 完成全部SD配置加载及当前配置同步应用，然后与普通选择共用同一父页值验证/单次退出路径。

20秒仍在处理时保留 pending sequence，不允许返回或重复提交；下一私有 UI 事件检查同一命令。完成后的处理仍执行同一父值验证/返回流程；生命周期系统事件继续交给原 dispatcher。这是有界等待后的显式再次查询，不声称有未实现的 UI 定时通知。

父页实际值生产链：`1d90de8 -> 1bc4190 -> 1bc3f64 -> 1bd55fc -> 1bc8eb8 -> 1bc50ec -> descriptor+78 -> r5_filter_menu_selected`。生产器将显示 MID 写到 0x74dc6e8，数量 0x74dc830；type5B param+0x80+4*index 是对应显示值资源。新代码在 update 返回后验证当前 MID0x635 对应值严格为 `SHORT_RESOURCE + committed selected`，且类型、数量一致；校验失败不关闭页面。不是把 void paint 返回当作成功。

## 最终回放

`page425_replay.json`：最终 AP SHA256 `11cd80055a7781eee61663dbc9ef0a8fff74fdeeeb9a6c3a59b8a7de379ac95c`，2个PIE地址 ×13种场景，共26项全部通过。源码 `r5_filter_page425.c` SHA256 `e79de3b286c4d2cbb5fc014db103b0ea368a1ff546385a856088949a11637a0c`。

场景包括成功、worker失败、SD更新完成后退出、更新失败留页、更新父值校验失败留页、更新超时锁定及后续完成、选择超时锁定及后续完成、触摸选择、故意破坏父值后留页、横竖重新构造/同类重排、OOM、退出析构后二次进入、stock工厂回退。成功执行上述真实父值生产链及实际编译 getter；选择父值字段为02ff4301、更新父值字段为02ff4300后才pop，均只pop一次。超时2000次yield后Menu/confirm不再次request、不pop；原sequence成功后更新父值并pop。分配/释放逐对象相等且地址不重复释放。

执行：`PYTHONPATH=vendor/audit-python .venv/bin/python analysis/r5_custom_menu425_refresh_exit_20261024/menu_research/replay_page425.py`。本机 Unicorn 需要非 sandbox 执行（sandbox 会SIGILL）；没有相机、SD、块设备访问。

## 证据边界

这是普通文件/Capstone/Unicorn证据，不冒称 REA MCP。UI图形系统、实际 Widget 构造、controller ctor、OSAL allocator、profile/display/model服务和worker IO是明确fixture；真实原生parent update/helper/descriptor getter/value字段执行。没有完整 Sony GUI 事件循环、字体栅格、LCD透明度、设备heap/cache/stack、真实SD延迟或ISP/JPG实测验收。页面 busy 状态调用了 paint，但实际液晶刷新时序仍需实机。跨线程 E4 执行与持久化/回滚由 import 的独立证据覆盖，不能以本页回放替代。
