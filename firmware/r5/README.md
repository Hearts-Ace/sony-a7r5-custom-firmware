# R5 4.55 完整固件构建源码

本目录含246个文件（245项源锁及锁文件），唯一入口build.py，从匹配散列的原厂R5 4.00输入重建AP、CP、分区和完整DAT，不依赖旧版本脚本、生成件或本地研究目录。

4.55修复4.54原生同步Start等播放完成、阻塞声音worker的问题，改为R5原生异步队列；新曝光通过原厂Stop停止当前声音，完成清理后重播最新一拍。异步拒绝在同一会话内由原未决请求和稳定空闲证据安全收尾。普通关机再开检测新会话后，核对原生资源并重新读取eMMC内的SEL、VOL和R5S载荷，重装播放资源，保留持久选择及音量。

声音格式、十档音量和4.36滤镜功能保留。六槽补写是独立电脑工具tools/r5-slots/，没有加入固件自动启动；网格和独立照片/PPLUT分支未改。CP与声音4.54逐字相同。新增恢复检查需要RX128KiB、RW起始0x8eb0000及AP文件增加65536B；严格ext2扩容保留其他文件和原块，并验证新分配、位图及空闲计数。

## 构建

按inputs.example.json配置外部原始输入，大小与散列必须匹配inputs.lock.json。签名材料自行保留，私钥权限0600；源码不包含原厂镜像或密钥。需要匹配工具链，本轮使用Apple clang 21及Python依赖，ext2工具使用macOS Homebrew e2fsprogs的/opt/homebrew/opt/e2fsprogs/sbin路径。

```sh
python3 -m pip install -r firmware/r5/requirements.txt
python3 firmware/r5/build.py --inputs /path/to/inputs.json --output /path/to/new-output --stage all
```

输出目录必须不存在，禁止用python -O跳过检查。默认构建逐项匹配expected_outputs.json；--stage components不产生DAT。--candidate仅用于后续研究，跳过冻结输出身份要求并将包标为NONINSTALLABLE。

电脑声音转换器位于host/，只需Python标准库和现有clang/gcc。现成音频包位于仓库sounds/；新增或替换声音时把R5S放SD根目录，完整取下电池再开机导入。已有eMMC音频的普通重启不再扫描SD。

```sh
python3 firmware/r5/host/prepare_sound.py convert "声音.WAV" -o "声音.R5S"
python3 firmware/r5/host/prepare_sound.py inspect "声音.R5S"
```

## 验证与边界

最终本地246文件源码ZIP已隔离执行stage all精确复现六主体及DAT。独立RSA/OpenSSL、篡改拒绝、CRC及全部751577088字节明文核对通过。实际AP/CP指令连续回放覆盖异步Start、新曝光Stop、原完成回包、重播、异步拒绝恢复及保留内存的新会话eMMC重载；宿主运行时80项、后端23场景1336项、连拍16场景2331项及最终菜单30项通过。

OS、部分传送/分配和硬件完成存在显式夹具；这些不等同于实体扬声器、连拍时序和WBI验收。播放中断电且完成回调丢失仍会保守等待，原同步Stop及DMM查询等待机制保留，未宣称所有断电场景自动恢复。

公开副本仅调整本README并重算源锁，其余244文件与已审本地源相同。映射和脱敏回执见../../publication/4.55/。FIELD_REPAIR、REPRODUCTION、source_provenance中的旧身份和工作区证据路径表示来源，不是旧构建依赖，也不表示未公开日志存在于仓库。公开副本仅检查映射、源锁和语法，复用同字节运行/构建源码已完成的隔离重建。

来源许可见THIRD_PARTY_NOTICES.md、LICENSE.Erlla及LICENSE.fwtool。本目录不包含DAT/AP/CP、原始镜像、设备备份、签名材料或原始设备日志。
