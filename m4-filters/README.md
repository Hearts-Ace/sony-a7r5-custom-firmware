# M4 单滤镜

按分类保存，每款只保留最新文件及同名 `.meta.json` 页面描述。仅单款下载，不合并槽位。

适用 ILCE-7M4，camera-look v2。照片与预览使用同一组网格、矩阵、CC1；七条照片与一条预览 Gamma 完全复制。

由现有正式滤镜参数转封装，未经跨机型重新拟合或实机照片/预览验收。不沿用其他机型色差作为本机型指标。

## 转换规则

转换后处理工具为 `tools/m4-adapter/convert.py`。它规范化每款已转封装的 M4
`camera-look v2` payload，并把 572 字节 Gamma 记录复制到七条照片记录和一条
预览记录。Gamma 记录前 516 字节是 129 个 little-endian uint32；M4 可接受的
上限是 **130944**，超过的值统一截顶到 130944。记录偏移 544 的重复端点同步为
第 129 个值，然后重算 payload 的 `payload_sha256` 和同名 `.meta.json` 的下载
SHA-256。运行 `python3 tools/m4-adapter/convert.py` 后，再运行
`python3 tools/validate_model_filters.py` 校验长度、端点、上限、数量和散列。
