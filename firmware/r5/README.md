# R5 4.34：唯一固件构建入口

运行 `build.py`。不再逐版执行 4.05→4.34，不导入工作区 `tools/`、`analysis/`、`research/`、`history/` 中的脚本，也不读取任何旧版生成镜像、产物或历史验证回执。

本目录包含完整的当前 AP/CP C、汇编、专用链接器、参数模板合并和 DAT 封装实现。`src/` 下 Python 文件是构建内部模块，不是另外一套版本入口。C/汇编中的 411/423 等文件名、符号和协议常量保留原 ABI 含义，不要求存在对应旧版本目录。

## 构建

需要 Python 3.9+、支持 AArch64/ARM 裸机目标的 clang 和 OpenSSL。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp inputs.example.json inputs.local.json
# 编辑 inputs.local.json，填写自己提供的原始文件和签名材料路径。
.venv/bin/python build.py --inputs inputs.local.json --output /path/to/new-r5-4.34
```

本次在 macOS 工具链验证。编译器生成的机器码必须匹配 `expected_outputs.json`；不同 clang 版本如生成不同代码，构建会拒绝确认重现。已验证的编译器身份见 `REPRODUCTION.json`，不声称任意工具链均可逐字重建。

`--output` 必须不存在。所有复制、编译、派生镜像和签名输出仅写入该新目录，源码目录和输入文件不改写。不要使用 `python -O`。仅重建 AP/CP、参数模板和分区可用 `--stage components`，此时不读取私钥或生成 DAT。

## 输入与恢复

`inputs.example.json` 列出原始 R5 4.00 DAT、同一 DAT 解包所得 FDAT/TAR、原厂 updater、原始 AP/CP/三个分区，以及外部提供的公钥/私钥。原厂输入逐项按 `inputs.lock.json` 核对大小和 SHA256。私钥不随仓库分发、不打印、不写入回执；完整固件也不公开上传。完整签名构建仍需要原机信任的匹配签名身份。

`src/dependencies/baseline_recipes.json` 将已批准的底层 AP/CP/WBI 修改收为带原像、目标散列的补丁配方：AP 7处、CP 82处、WBI 1处；AP 分区扩容布局15处。扩容配方只保留文件系统布局，旧模块已剔除，新增空间置零后由当前源码编译结果完整覆盖。没有嵌入完整旧版本组件。

`src/dependencies/colour_fields.json` 是当前13段/2746字节的 FL2/FL3、R6 ST 与 AWB 参数。包含全部12地区模板的原像校验及 BK4/backup.sum 更新，不需要旧逆算脚本或另一机型的完整镜像。

`source_provenance.json` 仅记录合并来源，历史路径不是运行依赖。`sources.lock.json` 固定当前源码/数据；修改实现时须审查后更新该清单及目标输出身份，不能仅删除校验绕过失败。恢复当前版本需要本目录、匹配的原厂输入、签名材料及工具链；无需恢复历史目录。

## 本次复现

统一入口从上述原厂输入重编 AP、CP、12个模板、分区及完整 DAT，全部匹配已交付4.34。DAT：754525608字节，SHA256 `1aeccd8f7fd6c1672b8fcd60ee1389c9b85a40a8aef51d6a720d898ecf9a1da9`。签名、篡改拒绝、容器CRC及751577088明文字节独立解密核对通过。

这是构建整理，固件版本和行为不变：白色优先97、氛围−1、动态图标、Fn手动注册、R6 ST、FL23及现有菜单/网格生命周期。未操作相机，既有实机验收边界不变。历史源码/证据在 Git 历史和本地恢复归档保留，不是当前构建入口。
