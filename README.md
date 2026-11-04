# Sony A7R V / R5 自定义滤镜与声音 4.55

4.55把快门声改为原生异步播放，使下一次曝光能停止当前声音并重播最新一拍；普通关机再开后从eMMC重载已保存的声音、选择及音量。保留十档音量、R5S机外转换和4.36滤镜功能。完整源码、六槽回读/解放工具及10份现成音频包均已提供。

- [完整固件源码与唯一构建入口](firmware/r5/README.md)
- [六槽回读与解放工具](tools/r5-slots/README.md)
- [音频包及使用说明](sounds/README.md) · [下载声音ZIP](sounds/R5-Sounds-4.55.zip)
- [最新十二款滤镜BIN](filters/FUJ_12_v45/README.md)
- [滤镜训练与网格工作台](https://github.com/Hearts-Ace/sony-r5-colorlab)
- [macOS刷写台0.2.1源码](R5FlashWorkbench/README.md)（独立应用仍以4.36为目标）
- [4.55验证摘要](publication/4.55/validation.json) · [完整源码映射](publication/4.55/source_mapping.json)

```sh
python3 -m pip install -r firmware/r5/requirements.txt
python3 firmware/r5/build.py --inputs /path/to/inputs.json --output /path/to/new-output --stage all
```

自行提供inputs.lock.json匹配的原厂R5 4.00输入、外部签名材料和工具链。源码共246文件，可独立编译封装；最终本地源码ZIP隔离重建、完整包独立验签/CRC/全部明文检查通过。实际AP/CP指令回放覆盖连拍Stop/重播、异步拒绝及保留内存的暖恢复，实体扬声器/时序/WBI仍待验。播放中断电且完成回调丢失仍保守等待。

独立槽位工具只把本机新读BACKUP.BIN/BAK的六个LOOK值00补为0A/0B，保留颜色、其他设置与UPDATER；固件没有加入启动自动补槽。对应本机原入口已完成6扇区/15字节写入及完整20MiB logical/raw回读，公开适配仅离线验证，详见工具说明。

本仓库发布源码、脚本、滤镜BIN、R5S音频包与脱敏校验摘要。完整DAT/AP/CP、机身备份、签名材料、私人照片及设备原始日志不发布。4.55本地DAT为754525608字节，SHA256 `e6376d3836cb1fdfc65c7cfaf314044af96bde3442fc2a699c0841a4d2c6feef`。独立照片/PPLUT分支未合入。

参考项目、来源和许可见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。历史提交/回执保留各自身份，旧路径不是当前构建入口。
