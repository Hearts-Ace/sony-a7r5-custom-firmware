# R5 4.58 完整固件构建源码

本目录是当前唯一完整固件构建入口，`build.py`从散列匹配的原厂R5 4.00输入重建AP、CP、AVCAM、MPR、资源、四分区及完整DAT。所需4.55基础配方已包含于source中，是内部构建依赖，无需检出历史提交或使用旧生成件。

4.58保留自定义滤镜、异步快门声及音量恢复，加入1.618:1、2.39:1、5:4、1.85:1比例。JPG／HEIF及RAW组合共享预览按比例裁切，RAW Bayer、DefaultCrop和SonyCrop保持全幅。Fn纵横比沿用原厂菜单样式，只扩比例和图标；滤镜Fn显示左简称、右当前全称。两图像银行新增MENU／Fn统一23像素，回放1.85:1使用32，5:4回放复用原厂图标。

## 构建

按inputs.example.json配置原厂输入和自己的外部签名材料；输入大小及散列必须匹配inputs.lock.json。私钥权限0600。需要Python、clang、e2fsck和以下依赖，本地验证使用Apple clang 21。输出目录必须不存在，禁止python -O跳过断言。

```sh
python3 -m pip install -r firmware/r5/requirements.txt
python3 firmware/r5/build.py --inputs /path/to/inputs.json --output /path/to/new-output --stage all
```

`--stage components`只构建组件和分区；`--stage all`另行签名并核验完整DAT，输出package/NONINSTALLABLE.DAT，名称保留本地测试状态。可用`--e2fsck /path/to/e2fsck`指定工具。原厂输入、密钥、完整DAT和设备备份不包含于仓库。

声音转换器位于source/projects/firmware/development/shutter-sound-recovery455/host，现成音频仍见仓库sounds。六槽电脑端工具仍见tools/r5-slots，固件没有新增启动补槽。独立PPLUT分支未合入。

## 验证

冻结4.58源码ZIP已解压独立全量构建，精确复现四组件、70资源、四分区及754525608字节DAT；签名、CRC和完整明文检查通过。DAT SHA256：c37605b64aa04653d9cd57e63c7e223a4064e96d8480e0021137686bf61f7c8b。

公开副本仅修改说明及源锁、补充输入示例和许可入口，生产运行及构建代码与冻结源逐字一致，映射见../../publication/4.58/source_mapping.json。内部历史证据中的工作区路径是来源记录，不是构建依赖。未重跑历史被拒CPU测试，未变组件沿用已有证据；实体安装、启动、LCD及成片待验。
