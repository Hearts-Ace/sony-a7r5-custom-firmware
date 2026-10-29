# R5 4.35：唯一固件构建入口

运行 `build.py`。不再逐版执行 4.05→4.35，不导入工作区 `tools/`、`analysis/`、`research/`、`history/` 中的脚本，也不读取任何旧版生成镜像、产物或历史验证回执。

本目录包含完整的当前 AP/CP C、汇编、专用链接器、参数模板合并和 DAT 封装实现。`src/` 下 Python 文件是构建内部模块，不是另外一套版本入口。C/汇编中的 411/423 等文件名、符号和协议常量保留原 ABI 含义，不要求存在对应旧版本目录。

## 构建

需要 Python 3.9+、支持 AArch64/ARM 裸机目标的 clang 和 OpenSSL。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp inputs.example.json inputs.local.json
# 编辑 inputs.local.json，填写自己提供的原始文件和签名材料路径。
.venv/bin/python build.py --inputs inputs.local.json --output /path/to/new-r5-4.35
```

本次在 macOS 工具链验证。编译器生成的机器码必须匹配 `expected_outputs.json`；不同 clang 版本如生成不同代码，构建会拒绝确认重现。已验证的编译器身份见 `REPRODUCTION.json`，不声称任意工具链均可逐字重建。

`--output` 必须不存在。所有复制、编译、派生镜像和签名输出仅写入该新目录，源码目录和输入文件不改写。不要使用 `python -O`。仅重建 AP/CP、参数模板和分区可用 `--stage components`，此时不读取私钥或生成 DAT。

## 输入与恢复

`inputs.example.json` 列出原始 R5 4.00 DAT、同一 DAT 解包所得 FDAT/TAR、原厂 updater、原始 AP/CP/三个分区，以及外部提供的公钥/私钥。原厂输入逐项按 `inputs.lock.json` 核对大小和 SHA256。私钥不随仓库分发、不打印、不写入回执；完整固件也不公开上传。完整签名构建仍需要原机信任的匹配签名身份。

`src/dependencies/baseline_recipes.json` 将已批准的底层 AP/CP/WBI 修改收为带原像、目标散列的补丁配方：AP 7处、CP 82处、WBI 1处；AP 分区扩容布局15处。扩容配方只保留文件系统布局，旧模块已剔除，新增空间置零后由当前源码编译结果完整覆盖。没有嵌入完整旧版本组件。

`src/dependencies/colour_fields.json` 是当前13段/2746字节的 FL2/FL3、R6 ST 与 AWB 参数。包含全部12地区模板的原像校验及 BK4/backup.sum 更新，不需要旧逆算脚本或另一机型的完整镜像。

`source_provenance.json` 仅记录合并来源，历史路径不是运行依赖。`sources.lock.json` 固定当前源码/数据；修改实现时须审查后更新该清单及目标输出身份，不能仅删除校验绕过失败。恢复当前版本需要本目录、匹配的原厂输入、签名材料及工具链；无需恢复历史目录。

## 4.35启动行为与验收边界

冷启动先扫描SD并完整校验R5NATIVE.BIN，再确定唯一一份待激活配置。有有效新BIN时先暂存、读回校验、原子替换内部旧文件，再向CP传输；无BIN或BIN损坏则加载内部原配置。零字节/有效空BIN沿用清空语义。相同配置跳过内部重复写入。不会先向CP发布旧配置再申请第二份bank。

恢复启动只加载内部已保存配置，不扫描SD、不做SD诊断写入或网格观察；内容相同的CP bank通过既有BEGIN协议复用。已撤下的私有重读入口保持拒绝，不会由迟到SD事件绕过此策略。恢复后更换SD的BIN需等下次冷启动才更新。

旧文件通过原子替换移除，不会先unlink活动文件；未通过验证或未成功写入的新BIN不会提前删除可恢复配置。冷启动避免创建旧CP bank，从源头避免那一份占用；不新增对渲染读者可能持有的bank进行free/清零的路径，也不扩大原厂heap。冷/恢复分类依据AP常驻工作线程的首次成功会话，首次会话之前的电源通知不会错误跳过冷启动扫描。

本地已执行当前AArch64加载/持久化与恢复路径回放、原厂有限heap下的AP/CP联动及打包校验。实际机身电源/WBI对首次会话的重建行为、当次菜单刷新与拍摄效果仍需实机验收；主机模拟和验签不等于机身通过。

4.34完整源码及冻结交付保留在Git历史/工作区4.34源码快照；不作为4.35构建输入。白色优先97、氛围−1、动态图标、Fn手动注册、R6 ST、FL23及参数模板保持原实现。本轮仅本地开发，无相机/SD写入。
