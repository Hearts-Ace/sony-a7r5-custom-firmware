# R5 Color Lab · v4.5 色卡版（适配4.34固件）

使用当前Python环境在本地浏览器拟合CC1、block13、Gamma和5×9×9网格。无需原研究工作区、Edit或RawAlchemy安装；不执行相机刷写。

## 启动

推荐Python 3.12，在本目录安装依赖：

```sh
python3 -m pip install -r requirements.txt
python3 launcher.py
```

Windows使用`py -3`替代`python3`，或运行启动BAT；macOS可双击启动command。浏览器打开`http://127.0.0.1:4180`，仅监听本机。端口冲突可加`--port 4181`。关闭终端或Ctrl+C停止。

CPU为默认后端；Apple Silicon可安装`requirements-gpu.txt`并设置`R5_GPU_TRAINING=1`启用Metal/MPS。最终配置仍经过整数参数及CPU数值校验；本包不自动安装PyTorch。AMD专用包是独立工具，本包未验证AMD设备。

## 色卡与目标图

默认使用 **v4.5 · 5300K · 一亿像素** 色卡，完整有效11648×8736，共99,372个32×32色块。Web提供Sony ARW、标准Sony DNG及GFX100S II RAF下载；[三格式色卡包与独立训练台下载](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware/releases/tag/colorlab-v4.5)。三种RAW在源码包内以gzip无损存储，下载时恢复原始字节并核验SHA256。

Sony RGGB白平衡为2606:1024:1024:1789，Bayer码值已反向补偿，以保持原色卡的Sony PT颜色标准；DNG保留同一码值、电平和WB，RAF经IED方案转换，未另加增益。在各软件保留拍摄白平衡；富士显示的Kelvin可能不同，不要据显示值强改5300K。14位信号、16位DNG容器不等于16位有效传感器精度。

从v4.5重新导出同尺寸RGB TIFF（推荐16位）或JPG，保留方向，不缩放、裁切或做几何修正。Adobe RGB等RGB ICC目标使用64位浮点ICC转换，先逐采样点转为sRGB、再取中心横向5点均值，无RGB8中间量化；超出sRGB的值裁切到有效范围。训练、压缩及评估统一使用中心5点均值。

ITP/拍摄WB→SSCS的纯模拟输入已与新版Edit PT实采核对：全部99,372块×9探针RGB逐值一致。实采最终输出与TIFF编码逐值一致；完整PT颜色模拟99,371块一致，仅第59,361块（从0编号）G差11个原生码值，约0.17/255。实采仅作独立验证，不回填训练输入、不增加颜色补偿。任意照片的空间处理前端仍近似。

Web保留v4历史色卡选择，上传及任务按版本绑定；同尺寸旧目标不能直接切换为v4.5。仓库现有12款已完成滤镜仍对应v4输入，v4.5训练结果需单独验收。生成源码及依赖边界见[chart_sources/v4.5](chart_sources/v4.5/README.md)，验证摘要见[发布记录](../publication/colorlab-v4.5/edit-runtime-validation.json)。

## 训练与导出

导入目标TIFF/JPG或cube，设置独立配置序号、简称/全称、权重和平滑，进行原生参数拟合。支持文件夹批量训练，简称使用实际文件名stem，全称独立保存；批次完成后合并BIN。最新12滤镜正式训练使用精度预算2000、12起点、8动态轮、压缩前Gamma/色彩交替3轮及量化3轮、参数平滑30、输出连续性30。详见[正式训练方案](TRAINING.md)。

自动压缩训练默认`fuji-target`：最终405节点整数网格直接拟合目标图，仅使用训练集优化；`pc-teacher`保留为显式可选研究目标。压缩后原生参数/网格交替以及灰阶微调关闭，压缩前交替保留。必要的3×5×9×9系数与原生参数一起写入BIN v4，旧BIN格式不兼容。导出前必须选择来源固定的原厂网格或完成网格拟合，服务端校验参数/目标/模型绑定。

R5实拍v2为默认响应`r5-paired-20261024-v2`，训练、压缩及RAW预览共用；覆盖42/256单元，留出RMSE3.696，未覆盖区域外推。QAQ研究提供原网格方法和历史代理参考，当前默认已替换为R5实拍参数。BIN只含整数网格系数，不把TPS/3×3响应写入固件。任意照片RAW前端与空间处理预览仍为近似，不声称完整恢复相机ISP。

运行`python3 launcher.py --check`核对数据与模型，`--test`运行回归。标定文件由`data_manifest.json`校验；合成capture报告仅脱敏本地路径，数值缓冲原样保留，manifest同时记录原报告与公开报告SHA256。`web/runs`、`web/batches`、上传/预览目录保存用户数据，不属于发布内容。

## 来源与许可

项目代码使用[GNU AGPL v3](LICENSE)。[致谢](ACKNOWLEDGEMENTS.md)、[数值来源](PROVENANCE.md)及`third_party/`记录QAQ MIT参考和其它第三方来源。Sony数值/合成色卡容器的来源不构成额外再许可。没有发布Sony完整应用、原机镜像、密钥或用户目标照片。离线拟合和格式校验通过不等于实际机内颜色验收。
