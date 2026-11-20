# M4固定转封装流程

按用户与M4作者确认的复制策略：同一套系数、矩阵、网格用于photo/live；7条照片Gamma和1条live Gamma全部使用同一条完整572字节记录。不做跨机型重拟合，不单独缩放预览曲线。M4 Gamma最高值为130944：源129点逐点执行 `min(value, 130944)`，保持单调性，并把记录偏移544的重复末点同步为第129点。

```
python3 tools/m4-adapter/convert.py INPUT.bin --output NEW_OUTPUT
python3 tools/m4-adapter/convert.py INPUT_DIRECTORY --output NEW_OUTPUT
python3 tools/m4-adapter/test_convert.py
```

递归目录输入须仅包含正式单滤镜BIN，保留分类；不要包含12槽合并包。输出目录必须不存在。默认模板为用户提供的CLASSIC CHROME.json，保留其默认微调值、格式编码和能力声明；需要更改模板可指定`--template`。输入BIN由本目录内的`custom_filter_v4.py`严格验证CRC、机型基线、保留字段及规范往返；该编解码器随公开工具提供，无需训练目录。流程无相机I/O。

网格3x5x9x9、矩阵3x16x6和CC1 3x8逐值复制到两个分支。129个Gamma uint32点覆盖模板photo[0]记录前516字节；模板+544处的重复端点同步为截顶后的第129点，其余附带字节使用photo[0]。所得整条记录逐字复制8份，包括相同标志值；不保留旧live或照片槽6的差异。这是用户指定复制策略，尚未经M4原生解析器或机内验收。

UUID按机型+简称确定性生成，逐款唯一；修订当前为1。`payload_sha256`按M4合同计算：`CAMLOOK2\0`加规定字段、排序键、紧凑UTF8 JSON。对用户原模板已验证该算法与原hash完全一致。输出JSON使用紧凑格式控制在128KiB机内读取限制内，不能加入任意空格而假定大小无影响。

当前交付：`exports/m4-filters-20261120`及`exports/M4-filters-20261120.zip`，146款，全部来自当前已发布单BIN。未复制旧模板的滤镜名称/UUID/参数/内容hash，默认微调值仍沿用模板。各款provenance只记源BIN散列、复制策略及未实机验收，不继承R5指标作为M4色差。

验证：全部129点Gamma与源一致，8条记录逐字相同，photo/live矩阵/CC1/网格一致，payload hash/唯一UUID/文件大小及ZIP CRC通过。`manifest.json`和`validation.json`是交付审计，不要当作滤镜导入。未上传GitHub/Pages。
