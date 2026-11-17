# 富士 NS／NN 单滤镜（2026-11-17）

| 简称 | 滤镜 | 单滤镜 BIN | 可编辑 JSON | 平均 ΔE00 | P95 | 最大 |
|---|---|---|---|---:|---:|---:|
| NS | PRO Neg. Std | [NS.bin](NS.bin) | [NS.json](NS.json) | 1.061797 | 2.660850 | 7.569077 |
| NN | NOSTALGIC Neg. | [NN.bin](NN.bin) | [NN.json](NN.json) | 1.090621 | 2.694877 | 7.964185 |

每份 BIN 仅含槽1，v4格式、2580字节。单独使用时将下载文件改名为 `R5NATIVE.BIN`，按兼容固件的导入流程加载。也可通过[在线资源库](https://hearts-ace.github.io/sony-a7r5-custom-firmware/)加入资源栏，与其他滤镜合并下载，最多12款。

两款均为5300K正式训练结果，使用正负非对称感知网格算子。未加去毛刺，未加入20%轨迹权重调整。逐款全量CPU回放、目标重算、Gamma及原生参数限制、数据隔离和严格编解码通过。误差为每款63111点函数独立测试，不同于v4.5 TIFF色卡测试口径；尚未实机验收。

[metrics.json](metrics.json) 提供完整测试指标，[export-audit.json](export-audit.json) 与 [SHA256SUMS](SHA256SUMS) 提供参数导出及文件散列。仅单槽编号统一为1，训练参数保持。原十二款整合包继续保留。本目录只发布最终参数及验收摘要。
