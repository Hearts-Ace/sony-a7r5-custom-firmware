# R5 Color Lab · 4.34配套独立色彩工作台

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

下载原色卡得到`GFX100SII-v4-100MP-from-SONY-IED.RAF`：11648×8736、32×32色块，共99372块。该合成色卡使用Sony unity-WB设计，经IED方案转换为GFX100S II RAF；不是相机实拍。RAW散列`a8d5221521ecb2928596cadeecc43354481edd32be56551f126d7f9d1560637c`。

在显影软件中处理后导出同尺寸RGB TIFF（推荐16位）或JPG，保留方向和几何，不缩放或裁切；支持RGB ICC，转换后再取中心横向5点均值，避免中间RGB8量化。数值输入来自ITP/unity-WB→SSCS模拟，与Edit PT全部99372块×9探针逐值核对；不加入隐藏实采补偿。旧版白平衡错误色卡拒绝训练。RAW以gzip无损存储在源码包，下载时还原并核验原始SHA256；另附sRGB16参考色卡。

## 训练与导出

导入目标TIFF/JPG或cube，设置独立配置序号、简称/全称、权重和平滑，进行原生参数拟合。支持文件夹批量训练，简称使用实际文件名stem，全称独立保存；批次完成后合并BIN。最新12滤镜正式训练使用精度预算2000、12起点、8动态轮、压缩前Gamma/色彩交替3轮及量化3轮、参数平滑30、输出连续性30。详见[正式训练方案](TRAINING.md)。

自动压缩训练默认`fuji-target`：最终405节点整数网格直接拟合目标图，仅使用训练集优化；`pc-teacher`保留为显式可选研究目标。压缩后原生参数/网格交替以及灰阶微调关闭，压缩前交替保留。必要的3×5×9×9系数与原生参数一起写入BIN v4，旧BIN格式不兼容。导出前必须选择来源固定的原厂网格或完成网格拟合，服务端校验参数/目标/模型绑定。

R5实拍v2为默认响应`r5-paired-20261024-v2`，训练、压缩及RAW预览共用；覆盖42/256单元，留出RMSE3.696，未覆盖区域外推。QAQ研究提供原网格方法和历史代理参考，当前默认已替换为R5实拍参数。BIN只含整数网格系数，不把TPS/3×3响应写入固件。任意照片RAW前端与空间处理预览仍为近似，不声称完整恢复相机ISP。

运行`python3 launcher.py --check`核对数据与模型，`--test`运行回归。标定文件由`data_manifest.json`校验；合成capture报告仅脱敏本地路径，数值缓冲原样保留，manifest同时记录原报告与公开报告SHA256。`web/runs`、`web/batches`、上传/预览目录保存用户数据，不属于发布内容。

## 来源与许可

项目代码使用[GNU AGPL v3](LICENSE)。[致谢](ACKNOWLEDGEMENTS.md)、[数值来源](PROVENANCE.md)及`third_party/`记录QAQ MIT参考和其它第三方来源。Sony数值/合成色卡容器的来源不构成额外再许可。没有发布Sony完整应用、原机镜像、密钥或用户目标照片。离线拟合和格式校验通过不等于实际机内颜色验收。
