# M4固定转封装流程

照片与取景共用同一组网格、矩阵、CC1 和 Gamma Y 值，七条照片和一条取景 Gamma 分别保留其模板控制字。适用于新版可变 Gamma 末点规则，Y 值的 18 位上限为 262143，曲线须从零开始、单调非递减，末点须非零。

```
python3 tools/m4-adapter/convert.py INPUT.bin --output NEW_OUTPUT
python3 tools/m4-adapter/convert.py INPUT_DIRECTORY --output NEW_OUTPUT
python3 tools/m4-adapter/test_convert.py
```

递归目录输入须仅包含正式单滤镜BIN，保留分类；不要包含12槽合并包。输出目录必须不存在。默认模板为用户提供的CLASSIC CHROME.json，保留其默认微调值、格式编码和能力声明；需要更改模板可指定`--template`。输入BIN由本目录内的`custom_filter_v4.py`严格验证CRC、机型基线、保留字段及规范往返；该编解码器随公开工具提供，无需训练目录。流程无相机I/O。

每条 Gamma 记录长 572 字节。前 516 字节写入 R5 原始 129 个 uint32 Y 值，并在偏移 544 重复末点，其余字节来自对应的模板记录。

[M4 可变 Gamma 末点规则](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/b241457843392b1a73c6a1467eff648af4ba07d3/native/custom-lut/gamma-endpoints)

UUID按机型+简称确定性生成，逐款唯一；修订当前为1。`payload_sha256`按M4合同计算：`CAMLOOK2\0`加规定字段、排序键、紧凑UTF8 JSON。对用户原模板已验证该算法与原hash完全一致。输出JSON使用紧凑格式控制在128KiB机内读取限制内，不能加入任意空格而假定大小无影响。
