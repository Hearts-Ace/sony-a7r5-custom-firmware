2026-10-29：默认改为v4.5 5300K数据集，权威元数据为web/data/chart/sony100mp_5300k_v45/manifest.json。旧v4 unity-WB仅保留版本绑定兼容；下文旧默认描述按历史读取。新pairs数值未改，派生上下文报告及实采验证摘要只脱敏本地路径，原始/公开散列映射见publication/colorlab-v4.5/source_mapping.json。

2026-10-28：当前默认、色卡及算法以README.md和web/data/chart/sony100mp_unity_center5/manifest.json为准；下文早期默认值及3700点色卡描述仅作历史来源。

# 数据与算法来源

- 相机：Sony ILCE-7RM5；12外观数值表由已固定原厂R5与既有FX2 FL2/FL3适配抽取；固定上游086df3b1e33dfa0206553ac2bb003535c58ddb80。data/presets.json仅数值，无固件代码。
- 模型：既有验证ST context4，data/model/capture保留原始报告及引用缓冲；配方绑定报告、runtime/raw/settings散列。
- 训练：合成RAW完整传感器独立解码一致，新3700点frontend仅用用户最后一次导出的context2。原始报告、buffer、chart数值、manifest均保留；不附合成RAW本体，避免夹带过期原片缩略图。dataset_id=balanced-chart-20261022-manual-context2。
- 静态数值表：从散列c250f466835c5380d244de33a6824e9930fe3f250ce9b1d948d5e379cc4c8133的Edit arm64常量区抽取5张必要表（地址、类型、数量和每表散列见data/static_tables.json），不携带程序执行代码。
- LUT目标：复用RawAlchemy v0.6.2色彩/S-Log3参考数值链；照片解码改为pip rawpy/LibRaw，与原先打包版LibRaw版本可能不同，不宣称像素等价。
- 标准24色：BabelColor Average D50，经相机profile转换的既有284锚点尾24项；色度和来源散列保留在chart/manifest.json。
- 包中数据来自本地研究；不包含首次完整镜像、私人照片、签名密钥、Sony完整固件或Edit可执行文件。数据及代码路径以项目相对路径加载。

数据散列见data_manifest.json。原工作区新旧数据绑定策略有区别：独立包只接受新色卡，不携带旧任务兼容数据。

网格响应新增 QAQ 公开参数 `calibration/a7c2-2.01.virtual.npz` @ c8328ad5；原文件保存在data/qaq，来源/许可证同目录。应用户要求直接作A7C2→R5代理，不宣称完成R5标定。

## 公开发布与许可

项目代码按 GNU AGPL v3 发布（见 LICENSE），以保留 RawAlchemy 参考实现的许可要求；QAQ 来源的代码和参数同时保留其 MIT 许可证，见 third_party 与 data/qaq/LICENSE。第三方及原生数值资料的权利不因本项目发布而改变。详细致谢见 ACKNOWLEDGEMENTS.md。

公开采集报告仅脱敏本机用户名与临时路径，测量和缓冲未修改；原始与公开散列映射见 publication_manifest.json。

2026-10-23：新增 web/data/stock_grids423.json，仅包含 R5 4.00 CN2 属性 02a40004/05 的1215字节数值系数及来源散列／偏移；原厂 CP 建表器33组验证见工作区 analysis/web_stock_grid423_20261023/verification.json。目录不携带固件代码；未证实的外观专属映射不标注。两项均与4.23自定义格式在全部强度档逐字一致；02a40006不满足完整等价，排除。
