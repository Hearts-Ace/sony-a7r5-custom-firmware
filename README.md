# Sony A7R V / R5 自定义固件 4.65 候选

**[打开在线滤镜与声音资源库（Pages）](https://hearts-ace.github.io/sony-a7r5-custom-firmware/)**

[R5 滤镜](https://hearts-ace.github.io/sony-a7r5-custom-firmware/#filters) · [C2 滤镜](https://hearts-ace.github.io/sony-a7r5-custom-firmware/#c2) · [M4 滤镜](https://hearts-ace.github.io/sony-a7r5-custom-firmware/#m4) · [快门声音](https://hearts-ace.github.io/sony-a7r5-custom-firmware/#audio)

4.65 为当前唯一固件构建，基于官方 R5 4.00，保留自定义滤镜、FL2/FL3、声音、Fn、比例与裁切。滤镜切换按需读取 eMMC 中的一款，原厂颜色任务接管后再切换参数，旧任务归还引用后回收。

- [完整源码与唯一构建入口](firmware/r5/README.md)
- [4.65 验证摘要](publication/4.65/validation.json) · [4.65 源码锁](firmware/r5/sources.lock.json)
- [六槽回读与解放工具](tools/r5-slots/README.md)
- 在线资源库支持 R5 选择滤镜并下载整合 BIN，C2/M4 单滤镜下载，以及快门声试听、下载与转换。
- [当前单滤镜目录](filters/README.md)：按网页分类保存，每款只保留最新 BIN 与描述 JSON
- [声音安装与文件目录](sounds/README.md) · [全部声音 ZIP](sounds/R5-Sounds-4.55.zip)
- [常用十二款合并包](filter-bundles/常用十二款.bin) · [槽位说明](filter-bundles/常用十二款.json)

本项目以魔改线方案为主，不再提供macOS刷写工作台；六槽工具仅用于独立读取和限定设置修复，固件本身不自动补槽。

```sh
python3 -m pip install -r firmware/r5/requirements.txt
python3 firmware/r5/build.py --inputs /path/to/inputs.json --output /path/to/new-output --stage all
```

自行提供散列匹配的原厂 R5 4.00 输入、外部签名材料和工具链。签名、CRC、只读文件系统及全部解密明文核验通过。4.65 尚未实机验证，不能据此确认放大卡死或设置加载故障已解决。

公开范围为固件源码、设备工具、滤镜BIN、资源描述、R5S音频及校验摘要。色彩拟合方案、训练台、模拟算子、训练数据和相关研究源码不在本仓库发布。完整DAT/AP/CP、机身备份、签名材料及设备原始日志不发布。独立照片/PPLUT分支未合入。

来源和许可见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。


滤镜不再按发布日期分包。更新filters/内的BIN与同名描述JSON后，网页运行时自动读取；新增资源无需重新部署Pages。
