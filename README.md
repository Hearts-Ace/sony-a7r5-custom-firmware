# Sony A7R V / R5 自定义滤镜与声音 4.48

4.48支持下一次拍摄打断当前快门声：沿原厂停止命令及完成清理后，从头播放最新一拍，快速连拍只保留最新待处理触发。包含声音/音量菜单刷新、机外R5S转换与十档音量；保留4.36滤镜/网格、固定C.Look图标、Fn手动注册、R6 ST、FL2/FL3参数保留，以及白色优先97/氛围−1。4.48仅将已审声音4.46安装版本升号，全部运行代码及六主体保持。

- [完整固件源码与唯一构建入口](firmware/r5/README.md)
- [最新十二款滤镜BIN](filters/FUJ_12_v45/README.md)
- [滤镜工作台、训练方案及网格算子](https://github.com/Hearts-Ace/sony-r5-colorlab)
- [macOS刷写台0.2.1完整源码](R5FlashWorkbench/README.md)（该独立应用仍以4.36为目标）
- [4.48发布校验摘要](publication/4.48/validation.json) · [完整源码映射](publication/4.48/source_mapping.json)

## 完整脚本

```sh
python3 -m pip install -r firmware/r5/requirements.txt
python3 firmware/r5/build.py --inputs /path/to/inputs.json --output /path/to/new-output --stage all
```

自行提供inputs.lock.json要求的原厂R5 4.00输入、外部签名材料和匹配工具链；不依赖历史版本脚本、历史生成件或研究目录。输出目录必须不存在。电脑声音转换器同时包含在firmware/r5/host/。

## 验证与发布

最终本地244文件源码ZIP隔离完整重建、RSA/OpenSSL验签、篡改拒绝、CRC和全部明文核对通过。168份运行源及六主体与声音4.46全等，相关宿主与原指令回放按身份复用；4.48实体安装、扬声器/连拍时序、LCD与启动/WBI待机身验收。

本仓库沿用源码发布方式，公开完整源码、打包脚本、滤镜BIN和脱敏校验摘要。完整DAT/AP/CP、原机备份、签名密钥、私人照片和原始设备日志不随仓库分发；本地DAT身份为754525608B，SHA256 `5f4e2dc9789d5018ed35a84f7986d069a980ab01d0356bfbac653076cbdae25c`。独立照片/LUT研究不包含在本声音版本。

色彩训练与网格标定维护于[sony-r5-colorlab](https://github.com/Hearts-Ace/sony-r5-colorlab)，本仓库保留可直接导入的最新BIN。参考项目、致谢与许可见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；历史提交和发布回执保留各自版本身份。
