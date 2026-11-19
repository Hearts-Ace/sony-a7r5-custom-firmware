# R5 滤镜与声音资源库

[打开网页](https://hearts-ace.github.io/sony-a7r5-custom-firmware/)

色彩滤镜按分类浏览卡片，逐款加入资源栏并排序，下载最多十二槽的R5NATIVE.BIN。搜索框与当前分类标题共用一行。声音页支持试听、下载及本机WAV转R5S。

## 资源目录

滤镜唯一来源是仓库根目录[filters/](../../filters/README.md)。每个分类一个目录，每款一份同名BIN和描述JSON；不维护总目录文件，不在此目录复制滤镜，也不保留日期发布包。分类名直接来自文件夹名。说明、名称、简称、更新时间、散列和可选预览来自描述JSON。

资源工作流每天北京时间04:00扫描实际文件夹和文件，自动在resource-index分支生成仅含路径和源提交的directory.json；无需手动维护总catalog，不在每次提交时刷新。GitHub定时执行可能有延迟，需要立即更新时可在Actions手动运行。页面打开时从原始文件地址读取这个目录，再固定到同一提交读取描述和BIN，下载核验SHA256，不调用GitHub API。新增分类、新增滤镜或替换资源文件都不需要重新构建或部署Pages，目录刷新后重新打开页面即可加载。

常用十二款保留在仓库的[filter-bundles/](../../filter-bundles/)供直接取用，网页不加载该合并包；页面下载统一通过资源栏生成。

## 更新流程

将单槽BIN与同名描述JSON提交到main的filters/分类名/下；替换时同步更新sha256，内部菜单简称与描述保持一致。无需修改前端源码或总catalog。完整字段与预览说明见[资源维护说明](../../filters/README.md)。历史发布证据保留在Git历史和本地研究目录。

声音维持根目录sounds/管理及原有转换规则。本次调整只改变滤镜发现和发布方式。

## 误差说明

顶部“模拟到实机的误差”从resource-info/simulation-error.json读取，表示最新网格算子在指定NC色卡上的校验；说明中保留样本量及适用范围，不代表完整RAW流程或任意实拍。卡片读取每款描述JSON中的training_error；单位统一为ΔE00，详情展示平均/P95/最大及具体测试集。不同测试协议不能直接横向排名。

当前98款均有完整色差记录。每款保留其测试协议、样本数和算子身份，未将不同口径混为一个排名；复合验证目标值不会用作ΔE00。补齐training_error字段或更新顶部数据只需资源提交，不需要Pages部署。

## 开发

Node 22：npm ci；npm run build；npm run preview，打开http://127.0.0.1:4193/。页面预览也直接读取公开仓库当前资源。node --test tests/filter-catalog.test.mjs可验证自动发现、目录新增、描述错误及不加载仓库整包。

Pages只在网页源码或声音资源变化时构建。filters/及filter-bundles/更新不会触发Pages，每天的独立资源工作流负责验证文件并刷新目录，页面保持同一份构建产物。
