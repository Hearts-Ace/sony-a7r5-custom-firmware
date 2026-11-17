# Sony A7R V / R5 自定义固件 4.65 候选

4.65 为当前唯一固件构建，基于官方 R5 4.00，保留自定义滤镜、FL2/FL3、声音、Fn、比例与裁切。滤镜切换按需读取 eMMC 中的一款，原厂颜色任务接管后再切换参数，旧任务归还引用后回收。

- [完整源码与唯一构建入口](firmware/r5/README.md)
- [4.65 验证摘要](publication/4.65/validation.json) · [4.65 源码锁](firmware/r5/sources.lock.json)
- [六槽回读与解放工具](tools/r5-slots/README.md)
- [在线滤镜与声音资源库](https://hearts-ace.github.io/sony-a7r5-custom-firmware/)：选择滤镜、下载整合 BIN，试听/下载 5 款快门声，转换自己的 WAV
- [Canon 十二款单滤镜](filters/Canon_12_20261118/README.md)：AMD 正式训练已完成的 Canon 第一批
- [声音安装与文件目录](sounds/README.md) · [全部声音 ZIP](sounds/R5-Sounds-4.55.zip)
- [十二款滤镜BIN](filters/FUJ_12_v45/README.md)
- [NS／NN 新增单滤镜（PRO Neg. Std／NOSTALGIC Neg.）](filters/Fuji_NS_NN_20261117/README.md)
- [滤镜训练与网格工作台](https://github.com/Hearts-Ace/sony-r5-colorlab)

本项目以魔改线方案为主，不再提供macOS刷写工作台；六槽工具仅用于独立读取和限定设置修复，固件本身不自动补槽。

```sh
python3 -m pip install -r firmware/r5/requirements.txt
python3 firmware/r5/build.py --inputs /path/to/inputs.json --output /path/to/new-output --stage all
```

自行提供散列匹配的原厂 R5 4.00 输入、外部签名材料和工具链。签名、CRC、只读文件系统及全部解密明文核验通过。4.65 尚未实机验证，不能据此确认放大卡死或设置加载故障已解决。

公开范围为源码、脚本、滤镜BIN、R5S音频及校验摘要，完整DAT/AP/CP、机身备份、签名材料及设备原始日志不发布。独立照片/PPLUT分支未合入。旧版本文件及旧发布记录已移除，Git提交历史保留。

来源和许可见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
