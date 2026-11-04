# R5 声音包

共10份现成R5S，可下载单个文件或[R5-Sounds-4.55.zip](R5-Sounds-4.55.zip)。均来自此前转换交付，本次补齐8份时直接复制，没有重新转换或校验音频。

| 文件 | 转换批次 |
| --- | --- |
| [YAOYAO.R5S](YAOYAO.R5S) | 固件随包 |
| [YEAH.R5S](YEAH.R5S) | 固件随包 |
| [Ciallo.R5S](Ciallo.R5S) | 2026-11-04 |
| [WOCAO.R5S](WOCAO.R5S) | 2026-11-04 |
| [YYLX.R5S](YYLX.R5S) | 2026-11-04 |
| [ZBS.R5S](ZBS.R5S) | 2026-11-04 |
| [ZYJH.R5S](ZYJH.R5S) | 2026-11-04 |
| [你干嘛.R5S](你干嘛.R5S) | 2026-11-04，取前2秒 |
| [兔娘caliio.R5S](兔娘caliio.R5S) | 2026-11-04 |
| [遥遥领先.R5S](遥遥领先.R5S) | 2026-11-04 |

新增或替换声音时，把需要的.R5S放到SD卡根目录，完整取下电池再开机导入，再在相机声音菜单选择。已经导入eMMC的声音普通重启从机内恢复。中文文件名可以直接使用；JSON及说明文档不需要放卡。

转换自己的音频使用仓库firmware/r5/host/prepare_sound.py：

```sh
python3 firmware/r5/host/prepare_sound.py convert "声音.WAV" -o "声音.R5S"
python3 firmware/r5/host/prepare_sound.py inspect "声音.R5S"
```

转换来源及历史记录见[CONVERSION_NOTES.md](CONVERSION_NOTES.md)。YAOYAO/YEAH同名JSON保留此前格式检查信息；新增8份未重新检查。本次没有新增实体扬声器或普通重启测试。
