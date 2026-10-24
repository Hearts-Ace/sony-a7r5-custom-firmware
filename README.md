# Sony A7R V / R5 自定义滤镜 4.28

按用户要求回退到4.25菜单基线，删除更新按钮及对应触摸、焦点与手动刷新操作。保留自动导入、选择同步应用保存及父级选中值校验后退出，未带入4.26/4.27菜单改动。创意外观决定原厂基底，自定义滤镜独立选择，原厂名称不变。

- [4.28固件与独立工具下载](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware/releases/tag/v4.28)
- [反推网格工作台：探针生成、照片文件夹训练](R5GridCalibrator/README.md)
- [色彩工作台：默认R5实拍v2响应，训练/压缩/预览共用](R5ColorLab/README.md)
- [富士九款模拟滤镜：BIN、可编辑JSON与报告](filters/FUJ_grid_v2/README.md)
- [实拍网格模型及来源](R5ColorLab/web/data/r5/PROVENANCE.md)
- [唯一研究总结：菜单、参数和网格生命周期](analysis/R5_FL2_FL3固件色彩与RAW参数研究总结.md)
- [固件交付校验](publication/4.28/firmware_delivery_verified.json)

只支持BIN v4；CC1、block13、129点Gamma与5×9×9网格共同发布，保留4.22网格生命周期。富士模拟滤镜包括ASTIA、CLASSIC CHROME、ETERNA BLEACH BYPASS、ETERNA、CLASSIC Neg.、PRO Neg. Hi、PROVIA、REALA ACE、Velvia；不是富士官方滤镜。BIN会完整替换自定义配置集合。

固件754525608字节，SHA256 `dd64c0d26cf71d3b595dcf20cf11d39abdff8f78eadd7241a833182d28e03816`；滤镜BIN22196字节，SHA256 `5700b9dd8c1390ac851528f01be1776034d6b8fb66287cfffb3600351af38a93`。

R5实拍v2模型覆盖42/256，留出RMSE3.696；未覆盖颜色属于外推，不等于完整恢复原厂ISP。固件整包签名/CRC/完整解密已通过，4.28实机菜单、冷启动及照片颜色待验收。4.25其余入口/布局/对象行为随回退保留。

公开源码缺少Sony原机镜像、签名输入与部分本地依赖，不是干净克隆即可重建完整固件的一键工具。首次镜像、密钥、私人照片和训练运行目录不发布。第三方来源见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
