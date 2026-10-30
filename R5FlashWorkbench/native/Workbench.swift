import SwiftUI
import AppKit

enum Page: String, CaseIterable, Identifiable {
    case overview = "工作台", camera = "USB 维护", firmware = "固件", ai = "AI 助手", history = "任务记录"
    var id: String { rawValue }
    var symbol: String {
        switch self { case .overview: return "square.grid.2x2"; case .camera: return "cable.connector"; case .firmware: return "shippingbox"; case .ai: return "sparkles"; case .history: return "clock.arrow.circlepath" }
    }
}

@MainActor final class Workbench: ObservableObject {
    @Published var page: Page = .overview
    @Published var busy = false
    @Published var deviceBusy = false
    @Published var status = "就绪 · 尚未连接相机"
    @Published var log = "点击「离线自检」检查应用。启动时不扫描 USB。"
    @Published var firmware = UserDefaults.standard.string(forKey: "r5.lastFirmware") ?? "" {
        didSet { UserDefaults.standard.set(firmware, forKey: "r5.lastFirmware") }
    }
    @Published var inputs = ""
    @Published var originalDAT = ""
    @Published var signingKey = ""
    @Published var backup = ""
    @Published var previous = ""
    @Published var tasks: [URL] = []
    @Published var activeJob: URL?
    @Published var lastResult: [String: Any] = [:]
    private var timer: Timer?
    let resources = Bundle.main.resourceURL!
    let taskRoot: URL
    var filterInfo: [String: Any] {
        guard let data = try? Data(contentsOf: resources.appendingPathComponent("engine/filters/manifest.json")),
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
        return value
    }
    var filterNames: String {
        (filterInfo["filters"] as? [[String: Any]] ?? []).compactMap { $0["short_name"] as? String }.joined(separator: " · ")
    }
    var cli: String { Bundle.main.bundleURL.appendingPathComponent("Contents/MacOS/r5wb").path }
    init() {
        taskRoot = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("R5FlashWorkbench/Tasks", isDirectory: true)
        try? FileManager.default.createDirectory(at: taskRoot, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        reloadTasks()
    }
    func reloadTasks() {
        tasks = ((try? FileManager.default.contentsOfDirectory(at: taskRoot, includingPropertiesForKeys: [.isDirectoryKey])) ?? [])
            .filter { (try? $0.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true }.sorted { $0.lastPathComponent > $1.lastPathComponent }
    }
    func choose(_ title: String, directory: Bool = false) -> String? {
        let p = NSOpenPanel(); p.title = title; p.canChooseFiles = !directory; p.canChooseDirectories = directory; p.allowsMultipleSelection = false
        return p.runModal() == .OK ? p.url?.path : nil
    }
    func reveal(_ path: String) { NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)]) }
    func notice(_ title: String, _ text: String) {
        let a = NSAlert(); a.messageText = title; a.informativeText = text; a.addButton(withTitle: "好"); a.runModal()
    }
    func confirm(_ title: String, _ text: String) -> Bool {
        let a = NSAlert(); a.messageText = title; a.informativeText = text; a.alertStyle = .warning
        a.addButton(withTitle: "继续"); a.addButton(withTitle: "取消"); return a.runModal() == .alertFirstButtonReturn
    }
    nonisolated static func shellQuote(_ s: String) -> String { "'" + s.replacingOccurrences(of: "'", with: "'\\''") + "'" }
    nonisolated static func appleString(_ s: String) -> String {
        "\"" + s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"").replacingOccurrences(of: "\n", with: "\\n") + "\""
    }
    func run(_ action: String, values: [String: Any] = [:], privileged: Bool = false) {
        guard !busy else { return }
        let run = UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
        let stamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
        let job = taskRoot.appendingPathComponent(stamp + "_" + action + "_" + String(run.prefix(6)), isDirectory: true)
        var request = values; request["run_id"] = run
        do {
            try FileManager.default.createDirectory(at: job, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
            let data = try JSONSerialization.data(withJSONObject: request, options: [.prettyPrinted, .sortedKeys])
            let path = job.appendingPathComponent("request.json"); try data.write(to: path, options: .withoutOverwriting)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: path.path)
        } catch { notice("无法创建任务", error.localizedDescription); return }
        busy = true; deviceBusy = privileged; activeJob = job; lastResult = [:]
        status = privileged ? "等待管理员授权，随后执行 USB 事务" : "正在执行本地任务"
        log = "任务：\(job.lastPathComponent)\n"
        let python = resources.appendingPathComponent("python/bin/python3.12").path
        let script = resources.appendingPathComponent("engine/bootstrap.py").path
        let arguments = ["-I", "-B", script, action, job.appendingPathComponent("request.json").path, job.path]
        if privileged {
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    guard let self else { return }
                    if let s = try? String(contentsOf: job.appendingPathComponent("engine.log"), encoding: .utf8) { self.log = s }
                }
            }
        }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let process = Process(); let pipe = Pipe(); process.standardOutput = pipe; process.standardError = pipe
            process.environment = ["PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8", "HOME": FileManager.default.homeDirectoryForCurrentUser.path]
            if privileged {
                let command = (["/usr/bin/env", "-i", "PATH=/usr/bin:/bin:/usr/sbin:/sbin", python] + arguments).map(Workbench.shellQuote).joined(separator: " ")
                process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
                process.arguments = ["-e", "do shell script " + Workbench.appleString(command) + " with administrator privileges"]
            } else { process.executableURL = URL(fileURLWithPath: python); process.arguments = arguments }
            var text = ""; var exitCode: Int32 = -1
            do {
                try process.run()
                // Drain stdout while the process runs; never block on a full pipe.
                while true {
                    let data = pipe.fileHandleForReading.availableData
                    if data.isEmpty { break }
                    let chunk = String(decoding: data, as: UTF8.self); text += chunk
                    let currentLog = String(text.suffix(200000))
                    if !privileged { DispatchQueue.main.async { self?.log = currentLog } }
                }
                process.waitUntilExit(); exitCode = process.terminationStatus
            } catch { text = error.localizedDescription }
            if !privileged { try? text.write(to: job.appendingPathComponent("engine.log"), atomically: true, encoding: .utf8) }
            let data = try? Data(contentsOf: job.appendingPathComponent("result.json"))
            let result = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } ?? [:]
            DispatchQueue.main.async { self?.finished(action: action, job: job, text: text, exitCode: exitCode, result: result, privileged: privileged) }
        }
    }
    func finished(action: String, job: URL, text: String, exitCode: Int32, result: [String: Any], privileged: Bool) {
        timer?.invalidate(); timer = nil; busy = false; deviceBusy = false; lastResult = result
        if let full = try? String(contentsOf: job.appendingPathComponent("engine.log"), encoding: .utf8) { log = full }
        if !text.isEmpty && privileged { log += "\n" + text }
        if let error = result["error"] as? String { status = "任务未完成：" + error }
        else if exitCode != 0 || result.isEmpty { status = "未收到完整成功回执，请查看任务日志" }
        else if action == "device" {
            let recovered = result["USB_recovered"] as? Bool == true
            let complete = result["task_complete"] as? Bool == true || result["ok"] as? Bool == true
            status = complete && recovered ? "USB 事务完成 · 请在机身确认画面" : "请查看事务与 USB 恢复状态"
            previous = job.appendingPathComponent("result.json").path
            if result["kind"] as? String == "backup", result["backup_complete"] as? Bool == true {
                backup = previous
                let trust = result["trust_state"] as? String ?? "unsupported"
                status += trust == "installed" ? " · 已匹配我们的签名公钥" : (trust == "original" ? " · 原厂信任前像" : " · 未适配前像")
            }
        } else if action == "prepare" {
            let files = result["files"] as? [[String: Any]] ?? []
            status = files.count > 1 ? "固件与 12 款滤镜已准备好 · 弹出存储卡后在机身启动更新" : "12 款滤镜已导出 · 可按已有固件的滤镜加载流程使用"
        } else if action == "inspect" {
            status = result["kind"] as? String == "ordinary" ? "已识别 ILCE-7RM5 · MSC" : "当前未识别到普通 MSC 相机"
        } else { status = "本地任务完成" }
        if action == "build", let path = result["file"] as? String { firmware = path }
        reloadTasks()
    }
    func backupCamera() {
        guard confirm("备份更新器分区", "使用普通 USB 连接并在相机选择 MSC。将短暂进入服务会话，读取两次完整更新器分区并保存在本机。保持供电和连接。") else { return }
        run("device", values: ["kind": "backup"], privileged: true)
    }
    func installTrust() {
        guard !backup.isEmpty else { notice("需要备份记录", "先执行备份，或选择本工作台生成的 result.json。"); return }
        guard confirm("安装我们固件的更新公钥", "只接受已完成的真实原厂备份；机内再次核对完整前像后写入 26 扇区，并进行完整回读。本操作准备信任环境，固件升级随后在机身通过存储卡完成。") else { return }
        run("device", values: ["kind": "update", "backup_manifest": backup], privileged: true)
    }
    func buildFirmware(advanced: Bool = false) {
        if advanced && inputs.isEmpty { notice("请选择输入配置", "选择按 firmware/r5/inputs.example.json 填写的外部路径配置。"); return }
        if !advanced && (originalDAT.isEmpty || signingKey.isEmpty) { notice("请选择原始 DAT 和外部签名私钥", "需要原厂 R5 4.00 DAT，以及与我们公钥匹配的私钥（权限 0600）。原始 DAT 保持只读。"); return }
        guard let parent = choose("选择构建输出的父目录", directory: true) else { return }
        let output = URL(fileURLWithPath: parent).appendingPathComponent("R5_4.36_" + UUID().uuidString.prefix(8)).path
        if advanced { run("build", values: ["inputs": inputs, "destination": output]) }
        else { run("build", values: ["original_dat": originalDAT, "private_key": signingKey, "destination": output]) }
    }
    func exportFirmware() {
        prepareCard(withFirmware: true)
    }
    func prepareCard(withFirmware: Bool) {
        if withFirmware && (firmware.isEmpty || !FileManager.default.fileExists(atPath: firmware)) {
            guard let selected = choose("选择我们的 4.36 BODYDATA.DAT") else { return }; firmware = selected
        }
        guard let destination = choose("选择存储卡根目录或目标文件夹", directory: true) else { return }
        var values: [String: Any] = ["destination": destination]
        if withFirmware { values["firmware"] = firmware }
        run("prepare", values: values)
    }
    func copyAIInstructions() {
        let text = "请使用这台 Mac 上的 R5 刷写工作台处理我接下来的要求。先执行：\n" + Workbench.shellQuote(cli) + " describe\n再读取其返回的 AI_GUIDE.md。按我的自然语言描述选择固定命令；附带最新已完成的 R5NATIVE.BIN，无滤镜训练工作台。CLI 的 stdout 为 JSON，进度在 stderr，操作回执可用 status/result 读取。存储卡导出不表示相机已经升级完成。\n我的要求："
        NSPasteboard.general.clearContents(); NSPasteboard.general.setString(text, forType: .string)
        status = "已复制给 AI 的说明，粘贴后补充你的要求即可"
    }
}

struct Card<Content: View>: View {
    let title: String; let subtitle: String; @ViewBuilder var content: () -> Content
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 5) { Text(title).font(.headline); Text(subtitle).font(.subheadline).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
            content()
        }.padding(22).frame(maxWidth: .infinity, alignment: .leading).background(.background, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(.quaternary, lineWidth: 1))
    }
}

struct FileChoice: View {
    let title: String; let path: String; let choose: () -> Void
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "doc").foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 4) { Text(title).font(.subheadline.weight(.medium)); Text(path.isEmpty ? "尚未选择" : path).font(.caption).foregroundStyle(.secondary).lineLimit(2).textSelection(.enabled) }
            Spacer(); Button("选择…", action: choose)
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var model: Workbench
    var body: some View {
        NavigationSplitView {
            VStack(alignment: .leading, spacing: 24) {
                HStack(spacing: 12) {
                    Image(systemName: "camera.aperture").font(.system(size: 30, weight: .light)).foregroundStyle(.orange)
                    VStack(alignment: .leading, spacing: 3) { Text("R5 工作台").font(.headline); Text("ILCE-7RM5 · macOS").font(.caption).foregroundStyle(.secondary) }
                }.padding(.top, 16).padding(.horizontal, 16)
                List(Page.allCases, selection: $model.page) { page in Label(page.rawValue, systemImage: page.symbol).tag(page) }.listStyle(.sidebar)
                VStack(alignment: .leading, spacing: 6) { Text("固件 4.36 · 附带 12 款 BIN").font(.caption.weight(.semibold)); Text("普通 USB／MSC").font(.caption2).foregroundStyle(.secondary); Text("本地研究版 0.2.1").font(.caption2).foregroundStyle(.secondary) }.padding(18)
            }.navigationSplitViewColumnWidth(min: 200, ideal: 220, max: 260)
        } detail: {
            VStack(spacing: 0) {
                HStack(alignment: .center) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(model.page.rawValue).font(.largeTitle.weight(.semibold))
                        Text("Sony A7R V · 保留任务日志与完整回读证据").foregroundStyle(.secondary)
                    }
                    Spacer()
                    if model.busy { ProgressView().controlSize(.small) }
                    Text(model.busy ? "执行中" : "就绪").font(.caption.weight(.medium)).padding(.horizontal, 12).padding(.vertical, 7).background(model.busy ? Color.orange.opacity(0.12) : Color.green.opacity(0.10), in: Capsule())
                }.padding(28)
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        switch model.page {
                        case .overview: overview
                        case .camera: camera
                        case .firmware: firmware
                        case .ai: ai
                        case .history: history
                        }
                    }.padding(.horizontal, 28).padding(.bottom, 28).disabled(model.busy)
                }
                Divider()
                HStack(alignment: .top, spacing: 9) {
                    Image(systemName: model.busy ? "hourglass" : "info.circle").foregroundStyle(.secondary)
                    Text(model.status).font(.caption).textSelection(.enabled); Spacer()
                    if let job = model.activeJob { Button("打开记录") { model.reveal(job.path) }.controlSize(.small) }
                }.padding(15).frame(maxWidth: .infinity, alignment: .leading)
            }.background(Color(nsColor: .windowBackgroundColor))
        }.frame(minWidth: 1000, minHeight: 720)
    }
    var overview: some View {
        VStack(spacing: 18) {
            Card(title: "准备存储卡", subtitle: "已附带最新完成的 12 款 R5NATIVE.BIN。选好目标目录即可导出，旧文件会先保留。") {
                Text(model.filterNames).font(.caption).foregroundStyle(.secondary)
                HStack {
                    Button("导出最新滤镜…") { model.prepareCard(withFirmware: false) }.buttonStyle(.borderedProminent)
                    Button("固件＋滤镜一起准备…") { model.prepareCard(withFirmware: true) }
                    Button("交给 AI 处理") { model.copyAIInstructions(); model.page = .ai }
                }
            }
            Card(title: "先备份，再准备升级", subtitle: "普通 USB 负责备份和更新信任；BODYDATA.DAT 通过存储卡在机身升级。") {
                HStack(spacing: 18) {
                    step("1", "USB 备份", "保存完整更新器分区")
                    Image(systemName: "chevron.right").foregroundStyle(.tertiary)
                    step("2", "匹配签名公钥", "已安装时无需重复写入")
                    Image(systemName: "chevron.right").foregroundStyle(.tertiary)
                    step("3", "存储卡升级", "导出并在机身启动更新")
                }
                HStack { Button("离线自检") { model.run("selfcheck") }.buttonStyle(.borderedProminent); Button("查看 USB 状态") { model.run("inspect") }; Spacer(); Button("使用说明") { NSWorkspace.shared.open(model.resources.appendingPathComponent("README.md")) } }
            }
            Card(title: "继续使用我们的 4.36", subtitle: "固定 C.Look 图标、Fn 手动注册、R6 ST、FL2／FL3 参数保留、自定义滤镜，以及白色优先 97／氛围 −1。") {
                Text("固件生成仅调用统一 build.py；不包含参考项目的功能补丁或签名私钥。已有 4.36 文件可直接校验、导出。").font(.subheadline).foregroundStyle(.secondary)
                HStack { Button("USB 维护") { model.page = .camera }; Button("固件与导出") { model.page = .firmware } }
            }
            Card(title: "验收状态", subtitle: "离线构建和回执验证，与相机实际升级、启动和拍摄分别记录。") {
                Label("本应用尚未完成实机 USB 与卡刷验收", systemImage: "wrench.and.screwdriver").font(.subheadline)
                Text("启动和离线自检不扫描相机。设备操作需在 USB 维护页点击，并由 macOS 请求管理员授权。").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
    func step(_ number: String, _ title: String, _ subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 8) { Text(number).font(.title3.monospacedDigit()).foregroundStyle(.orange); Text(title).font(.subheadline.weight(.semibold)); Text(subtitle).font(.caption).foregroundStyle(.secondary) }.frame(maxWidth: .infinity, alignment: .leading)
    }
    var camera: some View {
        VStack(spacing: 18) {
            Card(title: "普通 USB／MSC", subtitle: "使用普通数据线连接一台 ILCE-7RM5，在机身选择 MSC。仅适配指定 R5 前像；未识别的版本或分区状态会停止操作。") {
                HStack { Button("查看 USB 状态") { model.run("inspect") }; Button("备份更新器分区…") { model.backupCamera() }.buttonStyle(.borderedProminent) }
                Text("备份为更新器分区（约 25 MB），不替代首次保留的整机备份。工作台不操作个人设置分区。").font(.caption).foregroundStyle(.secondary)
            }
            Card(title: "安装匹配公钥", subtitle: "只使用我们 4.36 的公钥。真实备份和当前机内完整前像都必须匹配，才允许写入 26 个扇区。") {
                FileChoice(title: "本工作台的备份回执 result.json", path: model.backup) { if let p = model.choose("选择备份 result.json") { model.backup = p } }
                Button("安装更新信任…") { model.installTrust() }
                Text("备份显示「已匹配我们的签名公钥」时，直接进入固件导出，无需再次安装。").font(.caption).foregroundStyle(.secondary)
            }
            Card(title: "USB 恢复观察", subtitle: "仅检查上一事务的普通 MSC 身份、端口、媒体和驱动。不重发写入或 STOP。") {
                FileChoice(title: "上一设备事务 result.json", path: model.previous) { if let p = model.choose("选择设备事务 result.json") { model.previous = p } }
                Button("观察恢复状态…") { model.run("device", values: ["kind": "recovery", "previous": model.previous], privileged: true) }.disabled(model.previous.isEmpty)
            }
        }
    }
    var firmware: some View {
        VStack(spacing: 18) {
            Card(title: "固件与附带滤镜", subtitle: "选择我们的 4.36 DAT 后，一次准备好固件和最新 BIN；内容相同会跳过，不同旧文件会先备份。") {
                FileChoice(title: "BODYDATA.DAT", path: model.firmware) { if let p = model.choose("选择我们的 4.36 BODYDATA.DAT") { model.firmware = p } }
                HStack { Button("校验文件") { model.run("verify", values: ["firmware": model.firmware]) }.disabled(model.firmware.isEmpty); Button("准备固件＋滤镜…") { model.exportFirmware() }.buttonStyle(.borderedProminent) }
                Text("导出完成后，按相机菜单进入机身固件更新。工作台不会通过 USB 直接写 AP／CP。").font(.caption).foregroundStyle(.secondary)
            }
            Card(title: "从原厂 DAT 生成 4.36", subtitle: "自动提取并核对原厂 R5 4.00 输入，再调用唯一 build.py。需要 Apple Command Line Tools 和足够的构建空间。") {
                FileChoice(title: "原厂 R5 4.00 BODYDATA.DAT", path: model.originalDAT) { if let p = model.choose("选择原厂 R5 4.00 DAT") { model.originalDAT = p } }
                FileChoice(title: "外部签名私钥 · 与我们的公钥匹配", path: model.signingKey) { if let p = model.choose("选择外部签名私钥 PEM") { model.signingKey = p } }
                Button("生成完整固件…") { model.buildFirmware() }.buttonStyle(.borderedProminent)
                Text("原厂 DAT 保持只读；私钥不会复制进应用或输入目录，权限须为 0600。构建过程保存逐项核验与结果。").font(.caption).foregroundStyle(.secondary)
            }
            DisclosureGroup("高级：已有原始输入") {
                FileChoice(title: "外部输入路径配置 JSON", path: model.inputs) { if let p = model.choose("选择私有输入路径 JSON") { model.inputs = p } }
                HStack { Button("用已有输入构建…") { model.buildFirmware(advanced: true) }; Button("查看输入模板") { model.reveal(model.resources.appendingPathComponent("firmware/r5/inputs.example.json").path) } }
                Text("签名私钥由用户外部提供，应用内不携带。构建结果、源码散列及封包核验写入新目录。").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
    var ai: some View {
        VStack(spacing: 18) {
            Card(title: "把要求直接告诉 AI", subtitle: "复制一次工作台说明，粘贴给能操作本机文件与终端的 AI，再写你要做的事。") {
                Button("复制给 AI 的说明") { model.copyAIInstructions() }.buttonStyle(.borderedProminent)
                Text("例如：把附带的最新 BIN 放到桌面的相机文件夹；把这份 4.36 固件和滤镜一起准备到存储卡；检查上一次操作有没有完成。").font(.subheadline).foregroundStyle(.secondary)
                Text("AI 会调用同一套刷写工具并读取回执。工作台不内置模型，也不需要 API Key。").font(.caption).foregroundStyle(.secondary)
            }
            Card(title: "AI 可以直接调用", subtitle: "固定命令、JSON 结果和独立任务日志，可直接发现功能并处理文件。") {
                Text(Workbench.shellQuote(model.cli) + " describe").font(.caption.monospaced()).textSelection(.enabled)
                HStack {
                    Button("打开 AI 使用说明") { NSWorkspace.shared.open(model.resources.appendingPathComponent("AI_GUIDE.md")) }
                    Button("显示命令入口") { model.reveal(model.cli) }
                }
            }
        }
    }
    var history: some View {
        VStack(spacing: 18) {
            Card(title: "任务与回执", subtitle: "每次操作保存独立目录；保留失败现场，不自动重试。") {
                HStack { Button("打开任务文件夹") { model.reveal(model.taskRoot.path) }; Button("刷新") { model.reloadTasks() }; Spacer(); Text("\(model.tasks.count) 个任务").font(.caption).foregroundStyle(.secondary) }
                ForEach(model.tasks.prefix(12), id: \.path) { job in
                    HStack { Image(systemName: "folder").foregroundStyle(.secondary); Text(job.lastPathComponent).font(.caption.monospaced()); Spacer(); Button("查看") { model.activeJob = job; model.log = (try? String(contentsOf: job.appendingPathComponent("engine.log"), encoding: .utf8)) ?? "没有引擎日志" }; Button("打开") { model.reveal(job.path) } }
                }
            }
            Card(title: "引擎日志", subtitle: model.activeJob?.path ?? "尚无任务") {
                ScrollView([.horizontal, .vertical]) { Text(model.log).font(.system(size: 11, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }.frame(minHeight: 230, maxHeight: 400)
            }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    weak var model: Workbench?
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if model?.deviceBusy == true {
            let alert = NSAlert(); alert.messageText = "USB 事务进行中"; alert.informativeText = "请等待事务回执后退出。强行结束界面不会停止机内任务。"; alert.runModal(); return .terminateCancel
        }
        if model?.busy == true { return .terminateCancel }
        return .terminateNow
    }
}

@main struct R5WorkbenchApp: App {
    @StateObject private var model = Workbench()
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    var body: some Scene {
        WindowGroup("R5 刷写工作台") { ContentView().environmentObject(model).onAppear { delegate.model = model } }.defaultSize(width: 1120, height: 820)
            .commands { CommandGroup(replacing: .newItem) {} }
    }
}
