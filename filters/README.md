# 当前正式滤镜

本目录只保留各款当前正式参数，按网页分类组织。每款一对同名文件：`简称.bin`和`简称.json`。JSON是描述信息，BIN内部的short_name必须与描述一致；单款槽号固定为1。

网页运行时读取GitHub当前main提交的文件树，分类来自目录名，名称、简称、说明及SHA256来自同名描述JSON。不维护总catalog，不按发布批次建目录，不向页面构建目录复制滤镜。新增分类直接新建目录。

更新一款：替换BIN，更新同名描述中的sha256和updated；新增一款：在分类目录提交BIN与描述；删除一款：同时删除二者。提交到main后在网页点击“刷新资源”即可看到，无需重新部署Pages。BIN和描述在一次页面加载中固定读取同一个提交，下载会核验SHA256。GitHub公开API受访问频率限制，受限时页面明确提示稍后刷新。

描述示例：

```json
{"schema":"r5-filter-description/1","id":"NC","name":"CLASSIC Neg.","short_name":"NC","series":"Fujifilm Film Simulation","description":"","updated":"2026-11-19","sha256":"填写BIN的64位SHA256","camera_tested":false,"order":4}
```

id稳定且全库唯一，用于保留用户资源栏；更名文件或菜单简称无需修改id。order可选，数字较小者优先。preview可选，填写仓库内filters/下存在的图片路径。

[常用十二款合并包](../filter-bundles/常用十二款.bin)单独维护，只保留当前包；相机可用包最多十二槽，网页支持从全部单款自由组合。相机协议v4保持不变。未实机验收，训练模型误差不等于实拍误差。
