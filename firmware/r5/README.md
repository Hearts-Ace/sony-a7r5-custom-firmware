# R5 4.59：清除确认弃用的私有代码

从aspect458-icons派生。最终滤镜Fn页面直接编译一次，移除旧页面代码／BSS及追加跳转阶段；删除旧type53 renderer及两处共享列表拦截，恢复原厂指令；删除AP GRID/E9日志观测链、CP E9回应及上传observer；删除无生产者的reload kind2分支和失败stub。

保留实际滤镜交易、ACK/E4、PT、文件原子持久化、电源会话及声音流程。wait_command和声音日志仍被当前功能使用，未判为弃用。传输固定ABI间的72字节空区保留，不再定义、访问或传输旧诊断结构；本轮不迁移bank布局。AVCAM／MPR／70资源与父4.58精确相同。安装版本升级为4.59。固件主体与已验证清理版4.58精确相同。

build.py是完整固件唯一入口，需要外置原厂输入及本机签名材料。示例：

```sh
python3 -B build.py --inputs /absolute/inputs.local.json --output /new/build-directory --stage all
```

expected_outputs.json绑定当前输出，sources.lock.json绑定所有交付源码和证据。evidence/是本轮新AP／CP的离线回执；历史证据只适用于原来的具体散列。原4.58源码／交付保留。

本轮横竖／大小池原生菜单输出、失败／延迟／退出、PT18组、CP启动64项／入口回退337项通过；完整源码独立构建和DAT核验见外部最终交付回执。OS、显示提交及worker完成等仍有显式夹具；自然动画调度、物理LCD、相机安装／启动／成片及耗时未验收。无相机／USB／SD／网络操作。
