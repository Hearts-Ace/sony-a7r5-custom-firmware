# 快门声资源与安装

[在线试听、选择下载和 WAV 转换](https://hearts-ace.github.io/sony-a7r5-custom-firmware/#audio) · [全部 5 款 ZIP](R5-Sounds-4.55.zip)

## 声音目录

本目录是仓库声音文件的唯一来源。网页部署时从这里复制资源，按 [catalog.json](catalog.json) 加载；网页内不再另存一套音频。ZIP 文件名中的 4.55 是历史打包版本，不代表当前固件版本。

|声音|单个下载|
|---|---|
|Ciallo|[Ciallo.R5S](Ciallo.R5S)|
|YAOYAO|[YAOYAO.R5S](YAOYAO.R5S)|
|YEAH|[YEAH.R5S](YEAH.R5S)|
|mambo|[mambo.R5S](mambo.R5S)|
|wow|[wow.R5S](wow.R5S)|

## 放入相机

下载需要的 `.R5S`，放到 SD 卡根目录，完整取下电池再开机导入，然后在相机声音菜单选择。已导入 eMMC 的声音普通重启从机内恢复。中文文件名可直接使用，JSON 和文档无需放卡。机内不直接导入 WAV。

## 转换自己的声音

最简单的方式是在在线资源库选择 PCM WAV，然后下载转换后的 R5S。文件只在浏览器中处理，不上传服务器。输入不超过 2 秒、1 MiB，支持单/双声道、8–192 kHz、8/16/24/32-bit PCM；输出 24 kHz 单声道，包含十档音量。

也可运行仓库内工具：

```sh
python3 tools/r5-sound/prepare_sound.py convert "声音.WAV" -o "声音.R5S"
python3 tools/r5-sound/prepare_sound.py inspect "声音.R5S"
```

## 校验与历史

2026-11-17 本目录按用户要求精简为 Ciallo、YAOYAO、YEAH、mambo、wow。5 个 R5S 均重新执行严格格式、包头 CRC 和十段音量 SHA256 检查，全部通过；目录记录当前文件 SHA256。mambo、wow 分别保留完整的 0.696 秒和 1.392 秒音频。网页试听由 R5S 的 50% 音量段解码生成，不另发布原始 WAV。格式检查与试听不替代实体扬声器验收。

[历史转换来源与素材说明](CONVERSION_NOTES.md)仅用于追溯；同名 JSON 是格式检查回执，不是需要安装的文件。
