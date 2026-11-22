# M4 单滤镜

按分类保存，每款只保留最新文件及同名 `.meta.json` 页面描述。仅单款下载，不合并槽位。

适用 ILCE-7M4，camera-look v2。照片与预览使用同一组网格、矩阵、CC1；七条照片与一条取景 Gamma 共用 129 个 Y 值，分别保留各自的 M4 模板控制字。

由现有正式滤镜参数转封装，未经跨机型重新拟合或实机照片/预览验收。不沿用其他机型色差作为本机型指标。

## Gamma

此批使用支持可变 Gamma 末点的 M4 固件。18 位上限为 **262143**。以 R5 的 129 个 Y 值逐点写入，并将每条记录偏移 `0x220` 的值同步为末点。本批源曲线最高值为 **131071**。格式仍为 camera-look v2。

[M4 可变 Gamma 末点源码与兼容性说明](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/b241457843392b1a73c6a1467eff648af4ba07d3/native/custom-lut/gamma-endpoints)
