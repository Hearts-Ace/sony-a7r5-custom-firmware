# 4.33 SD升级颜色参数保留

本项沿用原厂R5更新器的BK4迁移，只在打包时补全全部通用默认模板。没有新增AP运行时写回、Backup专用同步、finalizer、设置分区镜像或设备操作。

## 上游与R5根因

用户指定的[上游文档](https://github.com/Erlla/sony-a7m4-custom-firmware/blob/main/methods/03-fl2-fl3/sd-colour-preservation.md)锁定提交`d4649e21f72e9074031c0c95c9ec2dc23ecb6807`。文档与2026-10-19参考存档相同；最新`sd_templates.py`相对存档仅把配方名`cp-v7-recipe.json`改为`cp-recipe.json`。新获取文件及来源散列见[upstream_manifest.json](upstream_manifest.json)。上游文本用于查证技术方法，不作为新的用户指令。

R5 4.32打包链继承严格4.04的`firmware.tar`。直接检查该冻结归档发现：其中**全部12份GL地区BK4模板都精确等于R5原厂4.00**，FL2/FL3颜色bank和四字节映射均未补入。R5不是M4的LS/LS_GLEE 32份模板，不能照搬其文件集数量。

原始R5 `backup.ko`的迁移核对表明：AWB、CC1、block13属性都是`attrs=0x8`，在已审查的mode0/2/4/5下均采用新模板内容；六个LOOK槽的`attrs=0x60`在mode5下才保留旧值。这解释了已启用菜单经过支持的保留迁移后，LOOK可仍为0A/0B、颜色属性却被空模板覆盖的机制。实际某次升级选择的UUD/Backup模式仍需实机日志确认。

## 本次合并

每份原厂模板合并13个范围，共2746字节允许范围，另更新受影响BK4段校验和；实际每份改变1976个字节。

| 范围 | 处理 |
|---|---|
| CC1 `+0x1236`、block13 `+0x1CC` | 映射为22、24、23、25 |
| CC1 bank22–25 | FX2绝对值转R5差分；每bank前48字节，尾16字节保留 |
| block13 bank22–25 | 保持4.32/固定086df3b的动态B/A1/A2；各576字节有效组，尾192字节保留 |
| CC1 ST照片bank0 `+0x1250` | R6 ST可逆算的48字节 |
| block13 ST照片A1 `+0x2A0` | R6 ST可逆算的192字节；R5 B/A2及尾部保留 |
| AWB `+0x930..+0x931` | 白色优先112／氛围-1；配套`+932/+933`保持0／6 |

FL2/FL3十处共2504字节是上游保留机制的目标范围；ST/AWB另外三处共242字节来自本次明确需求。矩阵保持动态端点，**没有采用上游默认fixed-a1重复三组的调色变更**。每份最终模板中四个完整768字节FL2/FL3 bank也已独立核对等于既有FX2动态供体，包括未改的尾部。

全部12份模板长度、BK4索引/属性、LOOK六槽默认、其余校准与默认数据保持。`backup.sum`的12个模板CRC32全部更新，文件长度、行顺序及其它列保持。MainDest、TAR头部和几何不由本项修改。

## 产物与集成接口

- [prepare_templates.py](prepare_templates.py)：`build_templates(source_tar, output_dir, extra_updates=None, *, expected_archive_sha256=None)`返回`(member -> Path, manifest)`。默认读取同级`color/color433.py`的精确ST/AWB数据。
- [generated/templates_manifest.json](generated/templates_manifest.json)：12模板、12个CRC条目与13个包成员替换文件；`replacement_files`每项含成员名、文件路径、源/目标SHA256、字节数、原TAR数据偏移。供主构建将本项与AP/CP分区及`part_image.sum`一起加入同尺寸overlay。
- [verify_templates.py](verify_templates.py)／[verification.json](verification.json)：验证脚本与实际执行回执。

复现只写新的输出目录：

```sh
.venv/bin/python -B analysis/r5_firmware433_20261028/preservation/prepare_templates.py \
  --source-tar build_r5_m4strict_4.04_20261015/patched/firmware.tar \
  --expected-sha256 36c899f32fd37e643b252d1825d28392ec7545a0bed30634d16f12192c975c6a \
  --output analysis/r5_firmware433_20261028/preservation/new-output
```

## 已通过的验证与边界

全部12份真实模板通过固定源身份、源CRC、BK4双段校验、精确范围及尾部保留、动态供体完整bank和重复合并幂等性核验。四个失败场景（坏校验、已重算校验但未知ST前像、已重算校验但无关字段变化、重叠范围）均被拒绝。另一工作单元对最终12模板的ST/AWB数据也完成独立只读核对。

执行两个原始R5 ARM64迁移核心共72个案例：原始update-initrd及原厂应用rootfs，各含三颜色属性×四模式和六LOOK槽×四模式。AWB/CC1/block13均从目标模板产生；mode5保留旧0A/0B槽，其他模式遵循原厂默认行为。原始核心文件与入口绑定在回执中。沙盒内Unicorn以132退出后，同一脚本在获准的沙盒外离线执行通过。

该回放对属性/头查找和memcpy服务使用模型，未执行完整更新器、VFS或设备硬件；原始模板解析与校验另有独立格式验证。此方法支持已启用LOOK在已审查mode5路径下的颜色保留，不宣称恢复出厂、首次全原厂安装或任意更新状态自动启用FL2/FL3。当前个人设置不以历史镜像覆盖；实际升级后的BACKUP.BIN/BAK、活动属性、物理NOR/eMMC与拍摄效果仍属于后续实机验收。
