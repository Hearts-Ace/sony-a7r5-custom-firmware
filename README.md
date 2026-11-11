# Sony A7R V / R5 自定义固件 4.58

4.58是当前唯一完整固件构建版本，包含自定义滤镜、异步快门声和新增拍摄比例1.618:1、2.39:1、5:4、1.85:1。JPG／HEIF及RAW组合共享预览按比例裁切，RAW原始像素保持全幅。原厂Fn纵横比样式保留，自定义滤镜Fn采用左简称、右当前全称。新增比例图标已统一并优化。

- [完整源码与唯一构建入口](firmware/r5/README.md)
- [4.58验证摘要](publication/4.58/validation.json) · [冻结源码映射](publication/4.58/source_mapping.json)
- [六槽回读与解放工具](tools/r5-slots/README.md)
- [音频包](sounds/README.md) · [下载声音ZIP](sounds/R5-Sounds-4.55.zip)
- [十二款滤镜BIN](filters/FUJ_12_v45/README.md)
- [滤镜训练与网格工作台](https://github.com/Hearts-Ace/sony-r5-colorlab)

本项目以魔改线方案为主，不再提供macOS刷写工作台。

```sh
python3 -m pip install -r firmware/r5/requirements.txt
python3 firmware/r5/build.py --inputs /path/to/inputs.json --output /path/to/new-output --stage all
```

所需基础配方均已包含，4.55只是内部重建依赖，历史提交无需检出。自行提供散列匹配的原厂R5 4.00输入、外部签名材料和工具链。源码ZIP独立全量重建、签名、CRC和完整明文核验通过，实体安装、启动、LCD及成片待验。

公开范围为源码、脚本、滤镜BIN、R5S音频及校验摘要，完整DAT/AP/CP、机身备份、签名材料及设备原始日志不发布。独立照片/PPLUT分支未合入。旧版本文件及旧发布记录已移除，Git提交历史保留。

来源和许可见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
