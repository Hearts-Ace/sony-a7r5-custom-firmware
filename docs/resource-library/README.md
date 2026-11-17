# R5 色彩资源库

静态滤镜库，按分类选取独立滤镜，加入资源栏、调整顺序，下载 `R5NATIVE.BIN`。最多 12 款，资源栏第 1–12 位即相机槽号。浏览器校验每个源 BIN 的 SHA256、CRC、机型和固件基线后，重编号并生成新 CRC。没有服务器上传或相机写入。

当前富士九款来自 2026-11-17 完成批次，RP、RN、P400 来自 2026-11-14 十二款交付。当前批次未实机验收。仅用于兼容 v4 自定义滤镜格式的 Sony A7R V 固件。

## 本地预览

在本目录运行 `python3 -m http.server 4192`，打开 http://127.0.0.1:4192/ 。不可直接双击 HTML（需要 fetch）。无构建依赖，部署目录为仓库根目录。

## 添加滤镜与分类

每个滤镜保留独立的 `data/filters/ID.bin`（单槽 v4 BIN）和对应 `.json`。向 `data/catalog.json` 增加条目，包含唯一 `id`、`name`、`type`、`category`、`series`、`version`、`bin`、`json`、`sha256`。页面自动加载全部目录项，分类自动生成。

`type` 为 `digital` 数码机型、`color-film` 彩色胶片、`bw-film` 黑白胶片。`category` 为富士数码、理光、佳能、徕卡、尼康、富士正片、富士负片、Kodak、Portra、Kodachrome、Classic BW、Niche BW 等系列。只添加已训练并校验的资源，不把待训练色卡列为可下载滤镜。不同版本使用不同唯一 ID，可在 `series` 标明源系列及版本。

只发布网页和完成的滤镜资源，不发布本机训练输入、逆向资料或原厂镜像。

## 快门声

音频区可试听、下载仓库里的 `.R5S`，或在浏览器内将本地 PCM WAV 转成 R5SNDF0/v1。沿用原转换器 Q24 FIR、24 kHz 单声道、F0 编码、十档音量和包校验规则；最多 2 秒、1 MiB，支持 8/16/24/32-bit PCM 与 8–192 kHz 采样率。转换不上传文件。当前 YAOYAO 输出与原 C 编码器逐字节相同。网页加载仓库 `sounds/catalog.json` 中全部 10 款声音，部署时从唯一的 `sounds/` 目录组装。转换结果未实机测试。

后续声音添加至仓库 `sounds/`，更新 `sounds/catalog.json`，无需向网页目录复制文件。

## 发布状态（2026-11-17）

网页：https://hearts-ace.github.io/sony-a7r5-custom-firmware/ 。源码在本仓库 `docs/resource-library/`，声音唯一来源在 `sounds/`。GitHub Actions 自动组装并发布。原 Gitee 仓库已设为私有下架。

## 验证

浏览器合并器生成 1、3、12 槽，原 Python 严格解码与逐项参数比较通过。声音在现有 YAOYAO、8 kHz 单声道、44.1 kHz 双声道、192 kHz 单声道上与原 C 编码器输出逐字节一致。

Taste Skill 的桌面 1440 和手机 390 截图已人工查看。`GATE: ERROR`：完整 gate 在沙箱内无法绑定检查端口，未获得完整一致性/布局检查报告，未重跑 gate。不宣称完整 gate 通过。色条仅作资源卡片装饰，不是滤镜画面效果预览。
