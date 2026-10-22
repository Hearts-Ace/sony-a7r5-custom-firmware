# sony-a7r5-custom-firmware

Sony ILCE-7RM5（A7R V / R5）自定义创意外观、FL2/FL3移植与RAW→S-Log3 LUT原生参数拟合研究。

**4.18用户已确认实机结果没问题。** 支持按原生1–12序号导入名称、CC1三端点、block13三端点和129点Gamma，保存到独立内部文件，无卡启动重载。额外补偿矩阵和网格未加入。拟合器的最终LUT还原色彩精度仍未通过，不能把固件验收当作拟合精度验收。

- [唯一研究总结：4.18方案、完整刷写、拟合、RAW换算及实拍证据](analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md)
- [4.18 AP/CP、Gamma、名称及参数编译源码](analysis/r5_native_overwrite418_20261021/)
- [PC拟合与数学参考源码](research/r5_custom_lut/scripts/)
- [公开范围与复现依赖](PUBLICATION.md)
- [源码来源与公开副本散列](SOURCE_MANIFEST.json)
- [致谢与许可](THIRD_PARTY_NOTICES.md)

## 4.20 固件源码候选

[4.20 实现、配置格式与验证说明](analysis/r5_native_grid420_20261022/README.md)：加入原厂运行路径的 5×9×9 网格，并修复 SD 配置完整替换。有效 BIN 覆盖整个自定义集合，未列外观清除覆盖；空 BIN 清空全部，无 BIN 或损坏文件保留旧配置。SD 根目录 `R5IMPORT.LOG` 记录导入、CP 传输及网格选择/建表/上传返回状态。

152 个 SD 导入场景及网格、颜色、持久化回归在本地通过，4.20 封装校验通过；**4.20 尚未实机验收，4.18 仍是最后已确认版本。** 本次仅公开固件源码、工具和离线结果，色彩拟合 Web 暂不提交，完整 DAT 不分发。

## 4.18 参数文件

```sh
python analysis/r5_native_overwrite418_20261021/import/native_overwrite_config.py pack native_config.json --output R5NATIVE.BIN
```

配置必须包含完整参数及原生序号；可用下述命令生成格式示例到新目录，再用上面的编译器打包：

```sh
python tools/example_native418_config.py --output native_config.json
```

示例为用于格式验证的中性开发参数，不是原厂ST、FL或合格S-Log3配方；不要把它当推荐拍摄效果。原厂参数与用户拟合数据须自行取得并核验。

## 发布边界

本仓库公开源码与研究文档，不分发完整DAT、Sony AP/CP、机身镜像、个人设置、私钥、Edit程序/运行时转储、原片或商业LUT。构建仍需明确基线、外部参考树和本机签名身份；不声称在干净环境完成固件重建，不是通用一键刷机工具。历史工具中的固定散列与身份校验不得删改绕过。

特别感谢 [Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware) 和 [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE)。自定义外观参考 [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research)，RAW目标链参考 [Raw Alchemy](https://github.com/shenmintao/Raw-Alchemy) 与 [Colour](https://github.com/colour-science/colour)。固定版本、具体贡献和许可见第三方说明。
