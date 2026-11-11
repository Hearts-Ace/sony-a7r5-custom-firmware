# 比例图标修正：最终采用 SOURCE_MINIMAL_E

基线是4.56 PT AP `470b36805d5c05f847e585100e63bd2517fe0a856e9b78b397826043ecdcde9e`。用户实拍显示主菜单新比例左侧错误3:2，Fn左侧文字覆盖。冻结source及历史原始证据未改。

## 已确认原因和最小修正

主菜单选项 producer `22df69c` 经 `1bd5810→1bd1ae8`读取row+0x0c写模型+0x288。新row从3:2复制，旧初始化仅更新Fn +0x20/+0x24，没有更新+0x0c。因此主菜单保留3:2图。

Fn producer `1bc36f8` 经 `1bd5840/1bd5870→1bd18e8/1bd19e8`读取图像后写+0x30/+0x430，图像存在时文字+0x830为FFFFFFFF。私有parent=33，原厂尺寸图类别`1bc785c`排除>32，故私有row走原厂+0x20/+0x24，已有八个Fn图像资源可直接消费。旧post-hook却清空所有图像并写文字，导致实机文字列表。

最终只在新私有row设置+0x0c为02001e80..83，并完全撤`r5_aspect_list_hook`、其extern、汇编trampoline、native continuation binding及两合同中的1bc36f8 detour。Fn原厂query/producer/style/layout/input/lifecycle保持。native0..3在私有写入之前continue，其128字节copy不变。RAW/JPG/HEIF裁切、版本、PT、滤镜交易和声音未在该修正中改动。

原厂MENU图像画布76×40。现有回放图47×32，其中原厂48b0实际显示1.91:1，不能用作5:4字形。因此新建四个MENU专用76×40资源，stride80；完整复用已确认Fn70×60中间40行像素，x平移3/y平移-10。无字体重绘或图像缩放，Fn图像/回放图像保持。02001e80..83在两原厂bank空且在原7844项索引范围，未扩大索引。

## 接入文件

将`HANDOFF.json`的八项复制到root新生产source的对应`analysis/r5_aspect456_20261110/`位置：ap/menu C、wire S、compile_module.py、ap/integration.json、cancel/candidate-f/contract.json、resources/build_resources.py、reference_style.py、inputs.json。后三份state/persist/header仅为独立编译复制，逐字不变，不必替换。不得采用初期append build-a/build-b或ratio_icons.S；它们不是最终方案。

重新运行生产构建入口，资源总数仍70文件（68文字＋2图像），每图像bank增加4个新记录，旧14个新增比例/像素图及全部原记录像素保留；两图像bank的descriptor-relative偏移额外+80。新图资源02001e80..83由row+0x0c消费。生产detour数量减少1，没有新增hook。

## 已完成验证和缺口

`static-e.json`通过：menu修改精确等于指定改动，native源copy路径保持、state/persist/header逐字不变；wire仅删除独用trampoline，compile仅删除对应binding，两contract其它字段精确；独立ARM编译rx3012B（旧3140B），rw_file0、BSS1116B保持，无list符号/relocation；70资源独立重建，68文字与先前资源逐字相同，旧所有图像payload保持，八个MENU图像的独立host解压6400字节/两块4096+2304准确，像素与Fn源切片逐值相同。

`menu-icons-e.png`为两面板host像素预览：原厂3:2及四新图，用于检查完整字形；不是相机LCD。

本次窄范围Unicorn `verify_icons.py`沙箱SIGILL，沙箱外被自动审批内容过滤限制拒绝，未绕过。见EXECUTION_BLOCK.md。没有新ARM runtime field-for-field执行，不称CPU菜单回放通过。SOURCE_MINIMAL_E采用源/目标消费者字节和资源证据，最终AP/loader/签名及设备LCD由父agent整合后分别报告。不得把历史资源selector回放或静态证据当作本次完整设备验收。
