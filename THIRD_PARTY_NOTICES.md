# 参考项目、致谢与许可

感谢[Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/086df3b1e33dfa0206553ac2bb003535c58ddb80)公开FL2／FL3方法。固定提交为086df3b1e33dfa0206553ac2bb003535c58ddb80；本项目直接参考其补丁配方、个人设置与颜色处理方法。其MIT声明见[附带原文](licenses/Erlla-MIT.txt)。上游作者未对本项目R5适配提供验收保证。本项目不继承上游针对其指定实验私钥的公开例外；R5私钥不公开。

[DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE)提供串行引导、RP2040、fastboot及eMMC研究基础；参考树未发现明确许可证，不复制其源码、载荷或UF2。公开的本地主机USB实现使用其协议研究结果，未捆绑上游载荷。

[DavidBuchanan314/fwtool.py — a7iv](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv)及[ma1co/fwtool.py](https://github.com/ma1co/fwtool.py)提供容器与解包基础。相关MIT声明见[ma1co原文](licenses/fwtool-MIT.txt)；工具本体作为外部依赖取得。

[YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload/tree/1619f938663a36d41e72302a8cfee89a0f6acd1a)仅为备用研究路线，未用于R5实际部署。原文CC BY-SA 4.0，不在此转载。

分析工具：[Capstone](https://github.com/capstone-engine/capstone)、[Unicorn](https://github.com/unicorn-engine/unicorn)、[Ghidra](https://github.com/NationalSecurityAgency/ghidra)。Python依赖由使用者单独安装，保留各发行包许可证；本仓库MIT不覆盖Python、cryptography/OpenSSL、PyCryptodome、NumPy、pySerial、pyelftools、Dissect或Pillow。外部fastboot、编译器与SDK遵循原条款。

Sony固件、颜色供体、校准／个人资料、Imaging Edge软件及工具输出的权利不因主机源码开源而改变。致谢不是第三方再分发许可。


## 4.18自定义外观与色彩拟合新增来源

[QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research/tree/008a12f2b8d79f04ffa405d5d4ce2546b2a3db42)，固定提交008a12f2b8d79f04ffa405d5d4ce2546b2a3db42（feature/lut-device-import），用于自定义外观、导入与消费者路线参考。R5的原生1–12映射、独立保存、三端点及Gamma路由按本机结构适配；不表示上游验收本实现。上游MIT原文见licenses/a7c2-fl23-MIT.txt。

[shenmintao/Raw-Alchemy](https://github.com/shenmintao/Raw-Alchemy/tree/v0.6.2) 0.6.2提供RAW→工作空间→S-Log3与LUT参考及实际导出对照。其许可为AGPL-3.0，原文见licenses/Raw-Alchemy-AGPL-3.0.txt。公开的raw_slog3_reference.py、build_raw_slog3_reference.py、build_full_chain_pairs.py按AGPL-3.0-or-later发布，源文件声明优先于根MIT；不捆绑应用程序、ONNX、源码树或用户LUT。相关算法核对脚本需自行取得上游源码，并遵守上游许可。

[Colour](https://github.com/colour-science/colour/tree/4ee3b72a2c6205c1d0cd964075621ec19290d571)提供色域矩阵与S-Log3独立数值核对，固定提交4ee3b72a2c6205c1d0cd964075621ec19290d571；BSD-3-Clause原文见licenses/Colour-BSD-3-Clause.txt。NumPy、SciPy、rawpy/LibRaw作为外部依赖单独安装，遵循各自许可。Sony Imaging Edge仅用于本地渲染研究，不随源码分发。


## R5ColorLab 实测响应与矩阵参数致谢

感谢 [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research/tree/c8328ad5ee485efec4f6aa51314f6062d79533e1) 的原生5×9×9网格、矩阵／响应参数及实测联合拟合研究。R5ColorLab内置该提交的calibration/a7c2-2.01.virtual.npz（SHA256 7e183f46f7acd739a12b7c2989e0ce245628a1f0d72d4f673f48945f4493b0af），仅作A7C2→R5代理，不表示完成R5网格标定。来源、MIT许可证及贡献范围见R5ColorLab/ACKNOWLEDGEMENTS.md和data/qaq。

R5ColorLab代码采用其目录内AGPL v3许可证，保留RawAlchemy来源声明；第三方资料保留其各自权利，不由根MIT再许可。


## 2026-10-23 / 4.24 发布更新

按用户明确授权，4.24完整BODYDATA.DAT作为候选Release附件发布，Web分享包与源码同步；旧“仅源码、不发布DAT”描述仅代表以前的发布范围。原机完整镜像、备份、签名私钥和私人照片仍排除。4.21–4.24新增源码为脱敏研究/构建配方，未移除固定输入校验，不宣称公开仓库可独立重建完整固件。

菜单适配参考用户提供的A7M4离线方法；参考ZIP及其代码不重新分发。QAQ A7C2实测代理固定c8328ad5，属于跨机型模型，保留上游署名与许可；R5实测标定尚未完成。


## R5GridCalibrator与实拍模型

独立反推工作台沿用本项目GNU AGPL v3，许可见R5GridCalibrator/LICENSE。R5实拍模型由用户探针照片拟合，不包含原始照片。富士名称用于描述模拟目标，非富士官方产品；本次不分发目标图片。4.28沿用4.25菜单基线，未重新分发用户提供的M4参考ZIP。


## 2026-10-28 / 4.32

4.32继续采用固定Erlla M4菜单方法和QAQ网格研究；默认响应由用户R5探针实拍拟合。合成100MP RAF按Sony设计/IED转换方案生成，未打包完整第三方软件或用户目标图。滤镜名称用于描述模拟目标，非品牌官方产品。


## 2026-10-28 / 4.34

本次仅公开固件源码、构建／打包脚本与脱敏数值回执，不分发完整DAT、AP／CP、Backup镜像或密钥。4.33帮助文字误作图片的结论由4.34动态取图证据纠正。训练代码更新为连续性30／平滑30正式方案，附12项新配置／设置；旧公开滤镜目录与4.32 Release由本版替代，历史源码提交保留。算法许可与原有第三方署名不变。上游核心固定086df3b；颜色模板保留仅参考指定sd-colour-preservation文档／方法，不改变动态B／A1／A2策略。


2026-10-29固件源合并：既有固件C/汇编、链接器和打包代码收拢到firmware/r5/src，来源散列见source_provenance.json。fwtool.py保留其LICENSE.fwtool；其余原有许可及署名继续适用。baseline_recipes.json为既有原厂补丁的原像/目标配方，colour_fields.json为已公开同一功能的数值片段；不包含完整原厂镜像或签名私钥。


## macOS R5 Flash Workbench

R5FlashWorkbench is adapted from Liwenru88/a7r5-rea snapshot 290c79e; its original portions are for personal noncommercial research. See R5FlashWorkbench/THIRD_PARTY_NOTICES.md and licenses within that directory. This scope is not relicensed under the repository root license.
