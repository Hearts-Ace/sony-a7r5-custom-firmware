# R5 4.67：参考 R5 修复双格式纵横比写入

4.67 是本仓库唯一构建版本。构建从官方 R5 4.00 的固定输入开始，基础配方和当前补丁均随源码提供。纵横比与双格式存储采用参考 R5 的 `audit-fixes-20261123` 方案，保留自定义滤镜、FL2/FL3、快门声音、Fn、取景与回放功能。

AVCAM `0x1f4088` 双槽构造、`0x1f4dbc/0x1f4dfc` GEN 单次绑定完全保持原厂。

CP 以原生 RAW mode/size getter 计算无损 M/S 显影后裁切标签及 EMB 声明；AVCAM 接受较大档位已裁切 JPEG，或在全幅源的局部 view 中居中裁切后缩至 RAW 目标；显影后同步 SonyCrop/EMB，消除先后执行顺序依赖；JPEG+HEIF 的 JPEG 主图 resize 同样消费裁切源。HEIF 仅在各格式局部 view 和原生 MC request 中传递 ROI，共享 YC 保持原样。MPR 使用参考 R5 私有 record 元数据方案。

RAW Bayer 和 DefaultCrop 保持原厂；SonyCrop 表达可撤销裁切，RAW 内嵌 JPEG 使用对应预览尺寸。原生物理卡映射、资源申请/归还、写入事务和完成通知保持。

菜单选择和照片快照发布按参考 R5 加入序号检查，拒绝复制途中跨代、未完成发布及请求号不匹配的绑定；回池必须同时核对原生链表头和可用数增加，不能仅凭原厂范围检查返回值清除比例。保留本项目既有 490B 静态 sidecar，两个序号使用已清零保留区 `0x1a39498..0x1a394a0`，不覆盖声音状态或从 `0x1a39698` 开始的滤镜 owner 状态。失败回退清理完整 `0x1a39498..0x1a39698`。

参考 ZIP SHA256：`cc79fcb6d320172978770135449da7f93a13c9e488d2b0847eea9b6facb9d698`。

从仓库根目录运行以下命令。使用 Python 3.9 或更新版本、Clang 和 e2fsck，并根据 [输入示例](inputs.example.json) 准备与 [输入锁](build_support/inputs.lock.json) 匹配的原厂资料和外部签名材料。构建输出须位于源码目录之外的新目录。

```sh
python3 -m pip install -r firmware/r5/requirements.txt
python3 -B firmware/r5/build.py --inputs /absolute/inputs.local.json --output /absolute/new-output --stage all
```

[构建与封装说明](build_support/README.md)包含 `--stage components` 和可选的 `--reference-dat` 用法。正常构建直接生成 `package/BODYDATA.DAT`。源码、输入和组件由各自的锁文件核验。

离线回放、封包核验及独立重建见 [4.67 验证摘要](../../publication/4.67/validation.json)。4.67 的物理双卡和整机连续拍摄仍待实机验收。
