# R5 滤镜与声音资源库

[打开网页](https://hearts-ace.github.io/sony-a7r5-custom-firmware/)

- **色彩滤镜**：按系列浏览卡片、查找滤镜、添加到资源栏。拖动或使用上下移按钮调整顺序，下载 `R5NATIVE.BIN`。最多 12 款，资源栏顺序对应相机槽位。
- **快门声音**：试听波形、下载现成的 R5S，或在浏览器里把本地 PCM WAV 转换为 R5S。WAV 最长 2 秒、最大 1 MiB；文件只在本机处理。

仅用于兼容 v4 自定义滤镜格式的 Sony A7R V 固件。本目录的滤镜尚未实机验收。

## 本地预览

使用 Node 22，在本目录运行：

```sh
npm ci
npm run build
npm run preview
```

打开 http://127.0.0.1:4193/ 。GitHub Actions 构建 `dist/` 并发布至 Pages。

## 添加滤镜和照片预览

将每款滤镜的单槽 BIN 和 JSON 放入 `data/filters/`，并更新 `data/catalog.json`。为每款资源填写唯一 `id`、`name`、`category`、`series`、`version`、`bin`、`json` 和 BIN 的 `sha256`。分类栏直接使用 `category`，例如“富士数码”“理光”或“Kodak”，不设上层分类。可保留 `type` 作为来源元数据。

准备好同一张基准照片的实际滤镜渲染后，可以将 sRGB WebP 或 JPEG 缩略图放入 `data/previews/`，并给对应目录项添加如 `"preview": "data/previews/NC.webp"` 的可选路径。构建会自动带上图片；没有图片的卡片仅显示名称与操作。

## 添加声音

在仓库根目录的 `sounds/` 放入新的 R5S 并更新 `sounds/catalog.json`。Pages 构建直接使用这份声音目录。试听从 R5S 提取 50% 音量档；转换沿用原工具的 24 kHz 单声道、F0 编码和十档音量规则。详情见[快门声音说明](../../sounds/README.md)。

## 页面设计与加载

暗房主题使用黑色、暖白与少量金色，滤镜卡片以 CSS 齿孔和帧号呈现。装饰不代表实拍预览；实际预览仍只读取目录中的 `preview`。系统字体、内联图标和 CSS 装饰无需外部 CDN。

声音工作台在第一次打开声音标签后加载，波形库在选择声音后加载。BIN、JSON、音频和转换内核按操作读取；转换继续在浏览器内完成。构建产物为静态文件，使用相对资源路径，兼容 GitHub Pages 的仓库子路径。
