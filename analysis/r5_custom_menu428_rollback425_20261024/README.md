# 4.28：回退4.25并移除菜单更新操作

2026-10-24，按用户明确要求，以最终4.25 sync_exit为基线，删除自定义菜单内的更新按钮和对应操作逻辑，打包为4.28。没有带入4.26的MID/控件白名单改动，也没有带入4.27的虚表、静态对象池、首帧和所有权改动。原版资料与所有历史交付保持不变；未操作相机、SD或GitHub。

先从复制到新目录的冻结425源码重建：AP SHA256精确复现`11cd80055a7781eee61663dbc9ef0a8fff74fdeeeb9a6c3a59b8a7de379ac95c`，见`baseline425/reproduced.json`。再修改唯一生产源码`menu_research/r5_filter_page425.c`：

- 取消14文字和15触摸Widget构造，参数节点隐藏且文字资源清零。
- 删除更新文案、焦点状态、左右/边界切换到更新按钮、touch15响应、submit的reload分支和私有页对reload_request的链接依赖。
- 上下只在关闭及已有配置间移动；原更新触摸无操作，确认只提交当前滤镜选择。
- 保留425其余页面布局、入口、对象管理、方向回调、首次更新及同步选择/父值核对后退出。

自动导入、开机/媒体加载、worker实现、BIN v4和CP均保持425。底层worker仍有原内部reload实现，但自定义菜单无入口、调用引用或操作分支；未为删除菜单按钮改动自动加载或文件保存。CP逐字节继承423，422网格生命周期及CC1/block13/129点Gamma保持。

最终AP：`85c0f93da51276c89419b6fd7415bbe41589045fd7fe79a4bf81c3aa1d0987da`，97452032字节，RX61784/BSS112536；AP分区非payload字节保持，e2fsck只读通过。`rollback428_verified.json`确认精确基线复现、唯一生产源码变化、无426/427接入改动及page object无reload符号。`sync_inheritance428_verified.json`确认import源/代码/常量/BSS坐标精确继承最终425。

页面22项离线回放含旧更新触摸无提交、左右不触发刷新、上下边界无更新焦点、选择同步/失败/超时/父值异常和重进。主列表六组、标题16项、worker11项、原请求76项、wrapper10项和跨核28次选择绑定最终AP。162项历史SD回放通过精确闭包身份继承，未宣称当前AP执行全部162项。

此次是用户指定回退，因此425旧MID/布局ABI/动态对象行为一并保留；此前发现及实机记录不改写，不能把离线回退说成新实机验收。PageVM仍有构造、图形/heap/系统服务fixture，OOM直接gate测试不证明native manager OOM恢复。4.28实际LCD、冷启动及拍照未测试。

包版本4.28／BCD2804，交付目录`research/r5_custom_lut/build_r5_4.28_rollback425_20261024/`，最终实际DAT校验以`release_tests/delivery_verified.json`为准。复制脚本中425文件名和历史说明用于追踪基线；当前实现及证据边界以本说明为准。
