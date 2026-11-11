# R5 4.55：异步声音与重启恢复

从冻结声音4.54源码派生，本版处理连拍无法打断及普通关机再开后声音选择失效。用户最终要求只交付声音修复，六槽补写、网格修改及独立照片/PPLUT功能均未合入。原有滤镜功能、R5S资源格式、电脑转换器和十档音量保留。

## 实现

原厂同步Start的回复在播放完成时产生，阻塞共享worker，使下一曝光的Stop无法及时执行。现在使用R5原生异步Start队列；新曝光通过原厂Stop停止当前声音，完成清理及未决请求退休后只重播最新一拍。异步入队记录为PLAY_QUEUED，不把入队成功当成声音已经发出。Stop仍使用原厂同步RPC，其无限等待语义未改。

检测新电源会话后先暂停本地播放，核对原生未决请求、登记和DMM资源身份；确认退休后重新读取eMMC中的SEL、VOL和所选R5S载荷，重新安装播放资源并恢复有效菜单选择。普通重启恢复不扫描SD，也不因恢复流程改写持久化的选择和音量。有效CP租约保留并重新复制载荷；明确失效的旧句柄仅遗忘，不向未知资源发释放。新增诊断保留首个原生错误，区分导入与清理失败。

AP注入RX容量由64KiB扩为128KiB，RW移至0x8eb0000。AP文件增加65536字节，由严格ext2扩容器保留原块、分配空闲块并核对所有其他文件。CP与4.54逐字相同。旧源代码和历史记录中的4.46/4.54描述表示来源，当前身份以sources.lock.json、expected_outputs.json和本文件为准。

## 唯一构建入口

```sh
PYTHONPATH=vendor/audit-python .venv/bin/python -B projects/firmware/development/shutter-sound-recovery455/build.py \
  --inputs projects/firmware/inputs.local.json --output /path/to/new-directory --stage all
```

从源码ZIP解压后同样运行其中build.py；原始R5 4.00输入位置按inputs.example.json配置。签名材料留在本机，不随源码分发。目录含全部编译、封装源码及输入身份，不依赖旧版本脚本或产物。输出目录必须不存在，禁止使用python -O。默认构建必须复现冻结输出；--candidate仅供后续研究，输出标记NONINSTALLABLE，不作为本版交付。

## 验证与边界

实际AP/CP连续指令回放通过首次选择、异步Start、第二曝光Stop、真实完成回复与重播、异步拒绝回收，以及保留AP/CP内存时新会话从eMMC重装后再次播放。宿主运行时80项、后端23场景1336项、连拍16场景2331项检查通过。独立AP布局、ext2其他文件保持、完整DAT签名/CRC及全部明文检查通过。最终源码ZIP隔离完整重建结果由工作区analysis/r5_454_regressions_20261105/isolated-reproduction.json绑定，避免源码锁自引用。

这些是离线验证，OS、部分IPC/DMM与硬件完成仍有显式夹具，不等同于机身安装、扬声器、连拍节奏或WBI验收。播放中断电且完成回调丢失的跨会话情况仍会保守等待，尚无安全强制清零的证据。本版没有宣称所有断电场景都已解决。
