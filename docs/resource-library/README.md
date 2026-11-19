# R5 滤镜与声音资源库

[打开网页](https://hearts-ace.github.io/sony-a7r5-custom-firmware/)

色彩滤镜按分类浏览卡片，加入资源栏并排序，下载最多十二槽的R5NATIVE.BIN。也可直接下载常用十二款合并包。声音页支持试听、下载及本机WAV转R5S。

## 资源目录

滤镜唯一来源是仓库根目录[filters/](../../filters/README.md)。每个分类一个目录，每款一份同名BIN和描述JSON；不维护总目录文件，不在此目录复制滤镜，也不保留日期发布包。分类名直接来自文件夹名。说明、名称、简称、更新时间、散列和可选预览来自描述JSON。

页面运行时通过GitHub公开文件树自动发现这些文件，并固定到同一提交读取描述和BIN，下载核验SHA256。点击“刷新资源”可读取最新提交。新增分类、新增滤镜或替换资源文件都不需要重新构建或部署Pages。GitHub公开API每次刷新仅两次请求，描述与BIN从原始文件地址读取；API受限时页面会明确报错，稍后重试。

常用十二款放在[filter-bundles/](../../filter-bundles/)，只保留当前合并包和说明JSON，单款目录包含其全部成员。

## 更新流程

将单槽BIN与同名描述JSON提交到main的filters/分类名/下；替换时同步更新sha256，内部菜单简称与描述保持一致。无需修改前端源码或总catalog。完整字段与预览说明见[资源维护说明](../../filters/README.md)。历史发布证据保留在Git历史和本地研究目录。

声音维持根目录sounds/管理及原有转换规则。本次调整只改变滤镜发现和发布方式。

## 误差说明

顶部“模拟到实机的误差”从resource-info/simulation-error.json读取，表示最新网格算子在指定NC色卡上的校验；说明中保留样本量及适用范围，不代表完整RAW流程或任意实拍。卡片读取每款描述JSON中的training_error；单位统一为ΔE00，详情展示平均/P95/最大及具体测试集。不同测试协议不能直接横向排名。

现有14款有完整色差记录，其余84款等待AMD最终指标文件，明确显示待补；复合验证目标值不会用作ΔE00。补齐training_error字段或更新顶部数据同样只需资源提交，不需要Pages部署。

## 开发

Node 22：npm ci；npm run build；npm run preview，打开http://127.0.0.1:4193/。页面预览也直接读取公开仓库当前资源。node --test tests/filter-catalog.test.mjs可验证自动发现、目录新增、描述错误及合并包读取。

Pages只在网页源码或声音资源变化时构建。filters/及filter-bundles/更新不会触发Pages，独立资源检查工作流负责验证文件，页面保持同一份构建产物。
