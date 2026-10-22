# 致谢

感谢 [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) 开放 Sony 原生网格与滤镜拟合研究。

本项目的 **5×9×9 网格格式、矩阵／响应参数和实测非线性响应拟合思路**参考该项目。当前内置参数来自固定提交 [`c8328ad5`](https://github.com/QAQLeonard/a7c2-fl23-research/tree/c8328ad5ee485efec4f6aa51314f6062d79533e1) 的 [`calibration/a7c2-2.01.virtual.npz`](https://github.com/QAQLeonard/a7c2-fl23-research/blob/c8328ad5ee485efec4f6aa51314f6062d79533e1/calibration/a7c2-2.01.virtual.npz)。参数来源、SHA256 和许可证保存在 [data/qaq](data/qaq/PROVENANCE.md)。早期网格算法的测试参考代码保存在 `tests/fixtures/qaq_native.py`；对应许可证保存在 `third_party/`。

这些参数采集自 A7C2，目前按用户选择作为 R5 的代理模型。**尚未完成 R5 网格响应标定，不代表与 R5 机内实际输出一致。** 本项目独立实现 Web 工作流和 R5 适配，不属于上游官方工具。

另感谢 RawAlchemy 的颜色处理参考实现；相关来源说明见 [PROVENANCE.md](PROVENANCE.md)，许可证保存在 `third_party/RAW_ALCHEMY_LICENSE`。其他原生数值表、训练数据和参考方法也在来源说明中列出。
