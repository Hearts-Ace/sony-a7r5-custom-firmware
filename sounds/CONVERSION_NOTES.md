# 历史转换记录

当前下载与安装以 [README.md](README.md) 为准。本文记录原批次，不代表最近一次检查状态；2026-11-17 按用户要求只保留 Ciallo、YAOYAO、YEAH，并新增 mambo、wow。

本轮新增音频来自用户提供的两个 Voicemod MP3。使用 FFmpeg 9.0.2 解码为 24 kHz、16-bit、单声道 PCM WAV，再由仓库 `tools/r5-sound/prepare_sound.py` 的原生整数 C 编码器生成十档 R5S。mambo 为 0.696 秒，wow 为 1.392 秒，均未裁切。源 MP3 不上传仓库。两份 R5S 的严格结构、包头 CRC、十段载荷 SHA256 和 F0 范围检查通过。

2026-11-04批次的原交付记录：8个文件使用4.54固件配套的机外转换器生成，24kHz、单声道、10档音量，当时逐个执行inspect通过。其中“你干嘛.mp3”原始约3.99秒，已取前2秒；其余保留完整可容纳内容。原始MP3、M4A、WAV未修改。

该批次文件原为 Ciallo、WOCAO、YYLX、ZBS、ZYJH、你干嘛、兔娘caliio、遥遥领先。2026-11-17 用户要求只保留 Ciallo，其他七份已从当前本地发布目录和 GitHub 删除；Git 历史仍可追溯。

原批次 SHA256SUMS 中“遥遥领先”使用旧文件名“遥遥领先-2.R5S”；该文件现已下架。

固件随包的YAOYAO约0.627秒、YEAH约1.115秒。YEAH由Erlla/sony-a7m4-custom-firmware固定声音参考提交0bfeee4f961610434588dc89c2cd3bc658816a3d的examples/custom-sounds/YEAH.WAV转换。YAOYAO和2026-11-04批次由用户提供并明确要求随音频包公开。源音频不随本包上传。

电脑转换器代码许可见firmware/r5/build_support/THIRD_PARTY_NOTICES.md，代码许可不改变声音素材本身的权利。R5S机外转换路线适用于当前4.55；机内不直接导入WAV。
