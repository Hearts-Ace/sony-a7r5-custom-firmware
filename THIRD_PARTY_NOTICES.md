# 参考项目、致谢与许可

当前版本为 R5 4.36；macOS 刷写工作台源码为 0.2.1。色彩训练与标定已独立至 [sony-r5-colorlab](https://github.com/Hearts-Ace/sony-r5-colorlab)。

- [Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/086df3b1e33dfa0206553ac2bb003535c58ddb80)：参考 FL2／FL3 解锁、菜单适配及颜色参数保留方法。[MIT 许可](licenses/Erlla-MIT.txt)。
- [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research)：参考自定义滤镜导入、原生网格及颜色参数处理思路。[MIT 许可](licenses/a7c2-fl23-MIT.txt)。
- [Liwenru88/a7r5-rea](https://github.com/Liwenru88/a7r5-rea)：刷写台参考其普通 USB／MSC 备份与信任安装流程，采用快照 `290c79e`。本项目使用自己的固件实现和签名身份；该部分保留个人非商业研究限制，详见 [刷写台来源与许可](R5FlashWorkbench/THIRD_PARTY_NOTICES.md)。
- [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) 与 [DavidBuchanan314/fwtool.py](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv)：固件容器解析与封装参考。派生代码保留 [fwtool MIT 许可](firmware/r5/LICENSE.fwtool)。
- [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE)：引导与存储协议研究参考；不捆绑其未明确许可的代码或载荷。

本仓库原创代码按根目录 [MIT 许可](LICENSE) 发布；刷写台和第三方代码遵循各自声明，根许可不覆盖它们。固件源码来源及固定身份见 [来源记录](firmware/r5/source_provenance.json)。

Capstone、Unicorn、Ghidra、Python 及相关依赖分别遵循其许可证；刷写台随包保留 Python、PyUSB、Sony-PMCA-RE、libusb 等组件的署名与许可。Sony 固件、Imaging Edge、原始镜像、签名材料及第三方数值资料的权利不因本项目开源而改变。滤镜名称仅说明模拟目标，不代表品牌官方产品或上游认可。
