# R5 Color Lab · 独立色彩拟合工作台

本地浏览器拟合 Sony A7R V（ILCE-7RM5）外观颜色参数。默认关闭实验白平衡训练、开启 PC 色彩补偿。包含全部代码、12 种外观参数、新分层色卡传感器数值及实采训练输入、颜色模型必要表、v2/v3 BIN 编译器。无需原“固件”工作区、Codex、Edit 或 RawAlchemy 安装。

## 启动

先安装 **Python 3.11–3.13（推荐 3.12）**，安装 Windows Python 时勾选 Python Launcher / PATH。

解压后先在项目目录自行安装依赖（也可以使用自己管理的虚拟环境）：

```sh
python3 -m pip install -r requirements.txt
```

Windows 使用 `py -3 -m pip install -r requirements.txt`。依赖安装完成后：

- macOS：解压到普通可写文件夹，双击 `启动R5色彩工作台.command`；或在终端运行 `python3 launcher.py`。
- Windows：双击 `启动R5色彩工作台.bat`；或运行 `py -3 launcher.py`。
- Linux：运行 `./start.sh` 或 `python3 launcher.py`。

启动器使用当前 Python 环境，不自动创建虚拟环境或安装依赖。浏览器自动打开 http://127.0.0.1:4180。关闭终端或按 Ctrl+C 停止。端口占用时运行 `python3 launcher.py --port 4181`。仅绑定本地回环，不提供公网访问。

不包含 Python 安装程序、虚拟环境或预编译运行库，依赖由使用者自行准备。macOS 下载文件若被系统阻止，可直接在终端运行 Python 启动命令。不要从 ZIP 内直接运行。

## 使用

选择外观，导入 `.cube` LUT，调整组权重、平滑、优化预算，点击开始拟合。新任务使用 2026-10-22 最后一次手动 ST 导出采集的3700点分层色卡；保留284锚点（正色、256级灰阶、标准24色）及64个矩阵方向代表色。训练、验证、独立测试划分固定。LUT目标固定。

“压缩训练”将完整PC明暗、染色与颜色补偿蒸馏成5×9×9网格。完成后点击“将本任务原生参数＋5×9×9网格加入导出集”，可以与其他外观合包。

- v2 BIN：4.18原生参数；不包含PC补偿。
- v3 BIN：需要4.20网格固件，包含每外观启用标志及1215个有符号7位系数；SD导入完整替换，未列外观清除自定义参数。
- 实验白平衡：默认关闭；启用后仅作用于PC模型，WB不在BIN中。
- 第129点Gamma：可自定义导出末点，保持曲线单调；当前RAW模型只有前128点，末点不改变模型预览。
- RAW预览：使用pip rawpy/LibRaw解码，同一RAW分别走LUT和拟合颜色函数，长边3840；可导入Edit实际导出的JPG作第三栏对照。支持已验证全尺寸R5 RGGB几何，压缩/RAW类型以LibRaw支持为准。
- 验证RAW导出：写ST参数的副本，不含PC补偿/网格，原片不改写。

`web/runs/`保存本项目生成的任务、日志和预览；分享包不包含原工作区私人照片、任务历史、固件包、整份Edit程序、相机完整镜像或签名私钥。不要将原工作区历史任务直接复制到这里：独立包只保留新色卡来源，老色卡任务请在原工作区查看。

## 给开发者

```
web/         HTTP服务、UI、训练/压缩、照片预览
scripts/     NumPy颜色模型、LUT参考链、原生参数/RAW编解码
compilers/   v2/v3 BIN编译器，无刷写或固件签名能力
data/        来源固定的参数、静态表、相机profile、新色卡数值与实采缓冲
tests/       独立回归与数值验证
launcher.py  使用当前Python环境的本地启动器
self_check.py  数据散列、来源、解码与测试入口
```

运行 `python3 launcher.py --check` 检查所有必要数据、模型和LibRaw加载；`python3 launcher.py --test`运行回归。编辑依赖请同步修改 `requirements.txt`，并自行重新安装。只修改算法代码不需要重建数据清单；修改标定/数据必须重新说明来源并更新`data_manifest.json`。

模型从实采post-SSCS输入开始，不能声称完整复现Edit JPEG、相机ISP或RawAlchemy解码器。RAW前端为近似，网格坐标/响应未完成机内标定。离线误差和BIN格式通过不等于机内颜色验收。本项目保留这些边界用于继续研究，不附机身刷写工具。

## 致谢与来源

感谢 [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) 的网格、矩阵／响应参数与拟合研究。本项目内置其 A7C2 实测参数作为 R5 代理；参考提交、许可证和适用范围详见 [致谢](ACKNOWLEDGEMENTS.md)。

Sony原生表、Edit实采运行时/数值常量、RawAlchemy v0.6.2颜色参考链与本地研究适配见 [PROVENANCE.md](PROVENANCE.md)。第三方依赖由pip安装，各自遵循其许可证。本包不额外授予Sony或其他第三方材料的再许可。公开分发范围和报告路径脱敏说明见 [PUBLICATION.md](PUBLICATION.md)。

合成色卡RAW本体不随包分发（包含过期内嵌缩略图且训练运行不需要它）。保留色块传感器值、完整3700点实采、来源RAW散列和已完成全像素解码校验回执，启动时检查分发数据的独立散列。照片预览请上传自己的R5原片。

## 2026-10-22 网格响应更新

新任务的直接网格及压缩后5×9×9网格使用固定 QAQ c8328ad5 的 A7C2 2.01 实测参数代理，运算为实测逆坐标、三线性偏移、非线性TPS前向响应，并用零网格预测锚定原生输出。取消新任务固定3×3矩阵输入；训练、量化微调、指标及RAW预览共用此函数。完整PC明暗/灰阶染色教师仍保留，压缩学生改为新模型；没有移植QAQ的17项原生控制来替换现有完整原生参数训练。

这是应用户要求采用的跨机型代理，不是R5网格实测。参数来源、散列及有限ISO/WB范围见data/qaq/PROVENANCE.md。模型在PC使用，BIN仍只写原生参数和1215字节网格，不把TPS或固定3×3响应写入固件。本轮未改固件。两个Web运行目录历史任务已按用户要求清空。

## 许可

项目代码采用 [GNU AGPL v3](LICENSE)，第三方材料保留各自许可；QAQ 参考材料的 MIT 许可证见 `third_party/` 与 `data/qaq/LICENSE`。数据及原生材料的来源和权利边界见 [PROVENANCE.md](PROVENANCE.md)。
