# 参考项目、致谢与许可

当前版本为 R5 4.58。色彩训练与标定已独立至 [sony-r5-colorlab](https://github.com/Hearts-Ace/sony-r5-colorlab)。

- [Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/086df3b1e33dfa0206553ac2bb003535c58ddb80)：参考 FL2／FL3、菜单、颜色参数保留及快门声实现；声音参考固定提交 `0bfeee4f961610434588dc89c2cd3bc658816a3d`，详见 [声音来源](firmware/r5/THIRD_PARTY_NOTICES.md)。[MIT 许可](licenses/Erlla-MIT.txt)。
- [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research)：参考自定义滤镜导入、原生网格及颜色参数处理思路。[MIT 许可](licenses/a7c2-fl23-MIT.txt)。
- [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) 与 [DavidBuchanan314/fwtool.py](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv)：固件容器解析与封装参考。派生代码保留 [fwtool MIT 许可](firmware/r5/LICENSE.fwtool)。
- [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE)：引导与存储协议研究参考；不捆绑其未明确许可的代码或载荷。

本仓库原创代码按根目录 [MIT 许可](LICENSE) 发布；第三方代码遵循各自声明，根许可不覆盖它们。固件源码来源及固定身份见 [来源记录](firmware/r5/source_provenance.json)。

Capstone、Unicorn、Ghidra、Python 及相关依赖分别遵循其许可证。Sony 固件、Imaging Edge、原始镜像、签名材料及第三方数值资料的权利不因本项目开源而改变。滤镜名称仅说明模拟目标，不代表品牌官方产品或上游认可。

本次随包R5S声音的来源与范围见[sounds/README.md](sounds/README.md)。六槽工具复用本项目已公开USB主机代码，引导载荷及外部存储协议资料由使用者自备，不在仓库中分发。
