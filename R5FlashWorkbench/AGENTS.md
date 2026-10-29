# R5 刷写工作台 AI 入口

本目录是 macOS 刷写工作台，不是滤镜训练工作台。先阅读 `AI_GUIDE.md`；安装后的应用运行 `Contents/MacOS/r5wb describe` 获取实际路径、附带 BIN 身份和命令清单。

自然语言任务映射到固定 CLI。读取 stdout 单一 JSON，进度读取 stderr，使用 status/result 追踪回执。只导出最新附带 BIN 用 prepare --destination；组合导出加 --firmware。目标由用户描述确定；不同旧文件自动保留，同散列跳过。

设备命令遵循用户明确任务授权与系统管理员授权；未授权不要把本地导出扩展为相机写入。无完整成功回执不自动重试，不删设备锁，不将文件导出或 USB 信任安装称作机身升级成功。

开发继续使用 firmware/r5/build.py 唯一固件入口，保持 USB 协议及固定前像校验，保留原始镜像和签名材料。附带 filters/manifest.json 必须绑定已完成的正式合包；不附带训练服务、训练历史、私人照片或签名私钥。
