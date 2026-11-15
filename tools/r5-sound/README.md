# R5 4.41 快门声准备工具

把 WAV 在电脑上转换为 `.R5S`，再放到 SD 卡根目录。相机冷启动导入，菜单选择声音和独立音量。一个文件包含 10%–100% 十档音量；混音、FIR 重采样、缩放及 F0 编码全部在电脑执行。

需要 Python 3.9+。转换还需要已有的 clang 或 gcc；无需 pip、音频库或安装脚本。`inspect` 只需 Python。macOS 可使用 Command Line Tools 的 clang；Windows 可使用能正常编译 C 程序的 LLVM clang 或 MinGW gcc。

从固件源码根目录运行：

```sh
python3 host/prepare_sound.py convert "/path/to/YAOYAO.WAV" -o "/path/to/YAOYAO.R5S"
python3 host/prepare_sound.py inspect "/path/to/YAOYAO.R5S"
```

Windows 把 `python3` 换为 `python` 或 `py -3`，路径照常加引号。指定已有编译器：

```powershell
py -3 host/prepare_sound.py convert "C:\Sounds\YAOYAO.WAV" --cc "C:\LLVM\bin\clang.exe"
py -3 host/prepare_sound.py inspect "C:\Sounds\YAOYAO.R5S"
```

省略 `-o` 时输出到 WAV 同目录、同名 `.R5S`。默认拒绝覆盖已有文件；确需替换时加 `--force`。源 WAV 不改写。编译与临时可执行文件使用系统临时目录，退出后清除；不向源码目录写入编译产物。

仅接受整数 PCM RIFF/WAVE：不超过 1 MiB／2 秒，8–192 kHz，单／双声道，8／16／24／32 位。浮点 WAV、WAVE_EXTENSIBLE、压缩 WAV 和 MP3 不在支持范围内。文件内容由同一原 C parser 校验；不通过扩展名猜测编码。

命令成功向 stdout 输出 JSON，包含整包 `sha256`、`header_sha256`、来源 WAV SHA256、字节数、24 kHz 帧数、编译器身份及十档 payload SHA256，退出码为 0。失败向 stderr 输出 `{"passed": false, "error": "..."}`，退出码为 2，不交付输出包。

AI 可按这个流程直接执行：保留输入 WAV → `convert` 到新的 `.R5S` 路径 → `inspect` 同一路径 → 仅在两条命令退出码均为 0 且 `passed` 为 true 时交付／复制文件。不要安装第三方解码器或悄悄覆盖现有包。

## 文件格式与实现

`.R5S` 版本 1 使用 416 字节小端头和十个等长 F0 payload；采样率为 24000，帧数 1–48000，每档编码字节数为 `ceil(frames / 31) * 32`，最多 49568。头包含源 WAV SHA256、清零自身字段后计算的 header CRC32、十档 payload SHA256。保留字段必须为零。存盘不含运行时 64 字节 guard；相机在读取所选档位时补零。

机内目录条目的 `e.sha` 和内部 `R5SN` 文件名使用 **完整 416 字节头的 SHA256**，即 JSON 的 `header_sha256`／`catalog_identity.value`；该头已经承诺全部十档 payload 的哈希。这样机内选择声音时只读当前档，仍可核对该档身份。JSON 的 `sha256` 是整文件 SHA256，供电脑端传输／交付核验，不能代替机内目录身份。SD 上的人类可读文件名（如 `YAOYAO.R5S`）无需改成内部文件名。

`encoder/` 中五份 parser／转换器／Q24 kernel 文件从已冻结 `shutter-sound-menu441` 精确复制，身份见 `encoder/SOURCE.json`，该路径仅为来源说明。工具直接调用原 `csnd_pcm_f0_volume` 逐档生成，不用 Python 近似重写算法。`encode_main.c` 只负责标准输入／输出及参数封装；它不参与相机固件。

`inspect` 校验每个头字段、精确长度、header CRC32、十档 SHA256、F0 指数及末块补零。来源 WAV SHA256 是溯源身份，不证明磁盘上另一个 WAV 已核对；需要比较时以 JSON 值对照原文件散列。
