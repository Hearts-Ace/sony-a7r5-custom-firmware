# 参考项目、致谢与许可

感谢[Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/086df3b1e33dfa0206553ac2bb003535c58ddb80)公开FL2／FL3方法。固定提交为086df3b1e33dfa0206553ac2bb003535c58ddb80；本项目直接参考其补丁配方、个人设置与颜色处理方法。其MIT声明见[附带原文](licenses/Erlla-MIT.txt)。上游作者未对本项目R5适配提供验收保证。本项目不继承上游针对其指定实验私钥的公开例外；R5私钥不公开。

[DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE)提供串行引导、RP2040、fastboot及eMMC研究基础；参考树未发现明确许可证，不复制其源码、载荷或UF2。公开的本地主机USB实现使用其协议研究结果，未捆绑上游载荷。

[DavidBuchanan314/fwtool.py — a7iv](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv)及[ma1co/fwtool.py](https://github.com/ma1co/fwtool.py)提供容器与解包基础。相关MIT声明见[ma1co原文](licenses/fwtool-MIT.txt)；工具本体作为外部依赖取得。

[YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload/tree/1619f938663a36d41e72302a8cfee89a0f6acd1a)仅为备用研究路线，未用于R5实际部署。原文CC BY-SA 4.0，不在此转载。

分析工具：[Capstone](https://github.com/capstone-engine/capstone)、[Unicorn](https://github.com/unicorn-engine/unicorn)、[Ghidra](https://github.com/NationalSecurityAgency/ghidra)。Python依赖由使用者单独安装，保留各发行包许可证；本仓库MIT不覆盖Python、cryptography/OpenSSL、PyCryptodome、NumPy、pySerial、pyelftools、Dissect或Pillow。外部fastboot、编译器与SDK遵循原条款。

Sony固件、颜色供体、校准／个人资料、Imaging Edge软件及工具输出的权利不因主机源码开源而改变。致谢不是第三方再分发许可。
