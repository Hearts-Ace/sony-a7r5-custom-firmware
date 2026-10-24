# 4.25 选择提交与 SD 手动重读

本目录实现/验证属于新 4.25 分析树，冻结 4.23/4.24 源及原机资料未改。`import/r5_filter_runtime423.c` 保留历史文件名以复用构建入口，行为已是本次 4.25。

菜单请求序列化：接收一条选择或 SD 重读命令，等待 CP 精确身份 SELECT ACK、绑定本次私有请求构造的原厂 E4 对象执行返回、再一次新序号精确 SELECT ACK，然后持久保存选择、发布 AP selected 和成功状态。失败状态保持，UI 不应关闭；同一失败 alias 不后台暗中重试。失败后在可行时恢复上一选择，回滚也不被报告为成功。SD 更新由原 sole worker 执行，复用完整文件检查、原子机内存储发布、完整 CP 参数封存与名称生命周期；没有/损坏 SD 文件不作为清空成功，合法空文件仍明确清空。已选槽在新包中移除时选择关闭。

原 E4 的九条 native color dispatch 使用异步消息发送：`3561518/1c` 设 x5/x4=0，`35589f8` 跳过等待结果分支。E4 返回是原厂提交体完成。最终 ACK 证实 CP 串行接收器接受本次准确 bank/selected/sequence；与 native send 同目标资源 90030001，但未单独证明 OSAL FIFO、native 下游子任务或硬件完成。因此本实现的同步边界是“CP 选择状态与原厂参数提交均完成后再确认”，不能把它当 LCD 帧或 JPEG 已产生的证明。

原厂 `24b0780` 直接传 request+16 给 `32885e8` 构造，构造结束后才入队。固定 private request 由单 worker 同步调用；构造不能延迟到后续事务。执行回调同时检查对象地址、本次单调序号及调用前后的当前序号；超时后晚执行和执行过程中换序号不发布完成。

验证：
- `run_worker425.py`：实际 C worker 的 11 种 host 场景；native IO/时钟/传输和 E4 明示 fixture。
- `replay_exact_request425.py`：最终候选原厂 facade/factory/constructor/queue 链，两个 PIE 各38次。constructor 包装器入口只作身份观察后进入原生构造，完整 wrapper 身份逻辑由下项补充。
- `replay_refresh_wrapper425.py`：最终 AArch64 包装器两 PIE 10 次，含 exact/错构造请求/错执行对象/执行中代际变化/超时后晚回；native ctor/execute 为破坏 caller-saved 寄存器的 fixture。
- `collect_native_scope425.py`：绑定 4.24 未改原生段的静态 Capstone 证据，明确异步发送边界。

没有真实文件系统/相机/SD 写入；最终设备 scheduler、媒体拔插、Fsys 单次阻塞时长和硬件像素仍需实机验证。15 秒轮询预算不能限制原厂 Fsys 单次调用时长。

独立线程静态核对：`thread_ownership425_verified.json` 绑定最终 AP。原 UI manager 在 `1e97710` 以 ID3/入口 `1ec4d30` 创建线程；sequence manager 在 `31a9d64` 创建 IDs4..46，E4映射 index0 即 ID4/入口 `3256068→3255ea0`。队列循环在调用 command vtable+0x10 前释放 queue mutex，因此 UI handler sleep 不会因为共享线程而阻止 E4 execute。该证明不覆盖 UI caller 可能持有的其它高层 model 锁，需要页面事件通路单独核对。
