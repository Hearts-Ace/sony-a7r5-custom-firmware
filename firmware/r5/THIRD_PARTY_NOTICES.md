# 第三方来源

声音格式检查、宿主SHA工具和Q24 FIR转换参考 [Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/0bfeee4f961610434588dc89c2cd3bc658816a3d/native/custom-sounds)，固定提交 `0bfeee4f961610434588dc89c2cd3bc658816a3d`。原始文件摘要与使用范围见 `sound_upstream.json`，许可保留于 `LICENSE.Erlla`；其 `THIRD_PARTY_NOTICES.md` 明确 `native/custom-sounds/` 为该项目原创适配代码。Q24系数采用无损四阶差分和nibble escape存储，恢复后的769项值及转换输出不变。4.40另参考其独立10档音量、默认50%、持久提交、GUI异步刷新和精确所有权内的原生增益7；R5使用单快门槽和既有原子文件接口。R5机内SHA复用原厂已有导入，原生地址、单声音播放、批量导入/持久化、所有权与退休判断另行适配，未照搬M4原生地址或双槽策略。

底层FL2/FL3参考仍固定 `086df3b1e33dfa0206553ac2bb003535c58ddb80`，声音参考提交不替换该基线身份。fwtool许可见 `LICENSE.fwtool`。Python与编译工具依赖保留各自许可，不包含其发行包。

这些许可不覆盖Sony原厂固件、原始镜像、机身设置、用户签名密钥或声音素材。本目录不附带原厂镜像、签名私钥或上游示例WAV。
