# 最新十二款 FUJ/v4.5 滤镜

使用无专家共享C1算子及原生参数约束完成的正式批次 `c29ff1d3ef314d718ab370cf6ed2bfb6`，替换此前旧批次BIN。顺序为AS / CC / EBB / ET / NC / NH / PV / RA / VN / 正片 / 负片 / Portra400。

下载[R5NATIVE.BIN](R5NATIVE.BIN)放存储卡根目录，按支持BIN v4的固件冷启动导入流程加载整套配置；恢复启动不扫描存储卡。兼容本项目4.48声音版，滤镜独立于声音资源。

[完整可编辑参数、训练设置、网格来源及数值/重编回执](https://github.com/Hearts-Ace/sony-r5-colorlab/tree/main/filters/FUJ_12_v45_shared_c1_20261104)在独立滤镜工作台仓库维护；[当前共享C1算子和训练方法](https://github.com/Hearts-Ace/sony-r5-colorlab/blob/main/R5ColorLab/TRAINING.md)同步提供。

公共源码从12份完成结果逐项重导并重编合包逐字一致，第二套codec严格回环通过。本次没有重新训练；色卡模型预测误差不代替实机加载或跨场景成像验收。

BIN为v4，29552B，SHA256：`2e9c60c1f7858940e366aa1b0f2c0c089347445c9c286c0c938a40a35610caee`。
