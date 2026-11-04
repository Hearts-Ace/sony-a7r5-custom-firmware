# R5 4.48 完整固件构建源码

本目录为当前唯一构建入口，含244文件（243项源锁及锁文件自身），从匹配散列的原厂R5 4.00输入重建AP、CP、分区及完整DAT；不依赖旧版本脚本、旧生成件或本地研究目录。

4.48包含连拍声音打断、声音/音量菜单刷新、机外R5S转换与十档音量，以及4.36的滤镜、网格、静态C.Look图标、R6 ST、FL2/FL3参数保留和AWB（白色优先97/氛围−1）。下一次曝光通过原厂0329/operation2停止当前声音，原完成清理后从头播放最新一拍。4.48只将已审声音4.46的安装版本升号，全部运行代码及六主体输出保持。

## 构建

安装Python依赖，并准备clang及ELF链接器等工具链；构建器会使用现有工具链。原始输入的大小与SHA256见inputs.lock.json，路径示例见inputs.example.json。签名材料由使用者在本机外部提供，私钥权限须为0600。

```sh
python3 -m pip install -r firmware/r5/requirements.txt
python3 firmware/r5/build.py --inputs /path/to/inputs.json --output /path/to/new-output --stage all
```

输出目录必须不存在。构建先核源锁和全部原始输入，再从原厂输入编译与封装，逐项匹配expected_outputs.json。禁止使用python -O跳过校验。只编译组件可用--stage components；该模式不产生完整DAT。

本目录自带host/电脑端声音转换器。输入为不超过2秒/1MiB的整数PCM WAV，输出供相机冷启动导入的R5S；机内不进行WAV转换。

```sh
python3 firmware/r5/host/prepare_sound.py convert "声音.WAV" -o "声音.R5S"
python3 firmware/r5/host/prepare_sound.py inspect "声音.R5S"
```

## 身份与验证

本地最终源码ZIP已隔离执行唯一stage all，精确复现六主体和完整DAT。独立RSA/OpenSSL、篡改拒绝、外CRC及全部751577088B明文对照通过；相对4.46仅版本头和头CRC共5字节变化。功能回放以168份运行源和六主体身份复用4.46证据；物理扬声器、连拍时序、LCD及4.48安装/冷启动/WBI仍待机身确认。

公开副本只调整本README的入口路径和发布说明，重算源锁；其余运行、构建和封装文件与本地已审冻结源逐字相同。公开映射和脱敏回执见../../publication/4.48/。FIELD_REPAIR、REPRODUCTION及source_provenance中的旧版本/本地证据路径保留历史身份；它们不是旧版本构建依赖，未公开证据不伪装成仓库文件。

本仓库发布完整源码、脚本、数值配置和校验摘要；原厂镜像、DAT/AP/CP、签名密钥及设备原始日志由使用者自行保留。来源与许可见THIRD_PARTY_NOTICES.md、LICENSE.Erlla和LICENSE.fwtool。原厂恢复时使用自行保留的对应机型原版输入；本源码构建不是设备恢复工具。
