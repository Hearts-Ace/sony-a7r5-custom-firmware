# Adapted for R5FlashWorkbench, 2026-10-29. Do not infer installed firmware from an internal build string.
"""认证与会话退出；原固定读取和独立批准的转存流程分别设限。"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys
import time
import traceback

from .core import MODEL, NORMAL_PID, VID
from .preflight import PREFLIGHT_FILES, assess_preflight, wire_path
from .supplement import CONTROL_PATHS, SUPPLEMENT_FILES, assess_supplement, control_matches
from .usb_adapter import HEADER, LIBUSB, ReadOnlyDriver, claim_interface, same_port, validate_target
from .bulk_reader import StrictReadBackend, file_read_limit

FIXED_FILES = {
    "version.bin": "/version.txt",
    "device-info.xml": "/usr/share/pmbp/DeviceInfo.xml",
}
WIRE_PATHS = tuple(wire_path(p) for p in FIXED_FILES.values())
START = (1, 0x37FF, 0xD7AA)
STOP = (1, 0xC800, 0x2855)
READ = struct.pack("<HH", 0x1001, 0x11) + b"\0\xff\0"


def profile_files(profile):
    if profile == "stage1": return FIXED_FILES
    if profile == "preflight": return PREFLIGHT_FILES
    if profile == "supplement": return SUPPLEMENT_FILES
    raise ValueError("未知固定读取模式")


def plist_command(args):
    return plistlib.loads(subprocess.run(args, check=True, capture_output=True, timeout=15).stdout)


def camera_media(tree, location):
    """只接受型号、普通身份及 locationID 一致的 USB 子树。"""
    targets = []
    def visit(node):
        if (node.get("IOObjectClass") == "IOUSBHostDevice"
                and (node.get("idVendor"), node.get("idProduct"), node.get("locationID")) == (VID, NORMAL_PID, location)):
            if node.get("USB Product Name") != MODEL:
                raise ValueError("IORegistry 型号不匹配")
            targets.append(node)
        for child in node.get("IORegistryEntryChildren", []): visit(child)
    for root in tree: visit(root)
    if len(targets) != 1: raise ValueError("不能唯一定位相机卷所属的 USB 子树")
    media = []
    def collect(node):
        if "BSD Name" in node:
            name = node["BSD Name"]
            if not re.fullmatch(r"disk[0-9]+(?:s[0-9]+)?", name):
                raise ValueError("异常相机卷标识")
            media.append({"device": name, "whole": node.get("Whole", False), "bytes": node.get("Size")})
        for child in node.get("IORegistryEntryChildren", []): collect(child)
    collect(targets[0])
    return media


def unmount_camera(device, log):
    ports = tuple(device.port_numbers or ())
    if not 1 <= len(ports) <= 5 or any(not 1 <= p <= 15 for p in ports):
        raise ValueError("无法将 USB 物理端口映射到 Mac locationID")
    location = (device.bus << 24) | sum(p << (20 - 4 * i) for i, p in enumerate(ports))
    tree = plist_command(["ioreg", "-a", "-l", "-r", "-c", "IOUSBHostDevice"])
    media = camera_media(tree, location)
    if not any(m["whole"] for m in media): raise ValueError("未找到相机媒体，拒绝跳过挂载检查")
    for entry in media:
        info = plist_command(["diskutil", "info", "-plist", entry["device"]])
        entry["mount_point"] = info.get("MountPoint", "")
    log("camera_media_identified", location_id=hex(location), media=media)
    for entry in media:
        if entry["whole"]:
            result = subprocess.run(["diskutil", "unmountDisk", entry["device"]],
                                    check=True, capture_output=True, text=True, timeout=20)
            log("camera_disk_unmounted", device=entry["device"], message=result.stdout.strip())
    for entry in media:
        info = plist_command(["diskutil", "info", "-plist", entry["device"]])
        if info.get("MountPoint"): raise RuntimeError("相机卷仍挂载，停止服务切换")


class FixedReader:
    def __init__(self, driver, log, profile="stage1"):
        self.files = profile_files(profile)
        self.driver = ReadOnlyDriver(driver, tuple(wire_path(p) for p in self.files.values()))
        self.profile = profile
        self.strict = profile in ("preflight", "supplement")
        self.attempted_paths = set()
        self.requests_remaining = 2 * len(self.files) if self.strict else 12
        self.usable = True
        self.sequence = 1
        self.log = log

    def nonempty(self, size):
        for _ in range(5):
            data = self.driver.read(size)
            if data: return data
        raise ValueError("连续空 USB 包超过上限")

    def exchange(self, body, limit):
        if self.strict:
            if not self.usable or self.requests_remaining <= 0:
                raise PermissionError("预检通道已失败或请求数超限，拒绝继续发送")
            self.requests_remaining -= 1
            self.usable = False
        self.driver.write(HEADER.pack(len(body), 0x40, self.sequence, 0, 0, 0, 0) + body)
        raw = self.nonempty(HEADER.size)
        details = {"raw_hex": raw.hex(), "raw_bytes": len(raw), "expected_bytes": HEADER.size,
                   "expected_sequence": self.sequence, "response_limit": limit}
        if len(raw) != HEADER.size:
            self.log("fixed_read_response_header", **details, rejected_fields=["header_length"])
            raise ValueError("服务响应头校验失败（header_length）；不再发送文件请求")
        size, function, sequence, version, micon, offset, status = HEADER.unpack(raw)
        # 与参考一致：响应的三个元数据字段只记录，不要求复现请求中的零值。
        rejected = []
        if function != 0x40: rejected.append("function")
        if sequence != self.sequence: rejected.append("sequence")
        if size > limit: rejected.append("size")
        self.log("fixed_read_response_header", **details, size=size, function=function, sequence=sequence,
                 version=version, micon=micon, offset=offset, status=status, rejected_fields=rejected)
        if rejected:
            raise ValueError(f"服务响应头校验失败（{', '.join(rejected)}）；不再发送文件请求")
        content = bytearray()
        while len(content) < size:
            chunk = self.nonempty(size - len(content))
            if len(chunk) > size - len(content): raise ValueError("响应体超过声明长度")
            content.extend(chunk)
        if size and size % 512 == 0 and self.driver.read(512) != b"":
            raise ValueError("服务响应边界非空")
        self.sequence += 1
        if status or len(content) < 4: raise ValueError("服务响应状态异常或缺少结果码")
        result, = struct.unpack_from("<I", content)
        self.log("fixed_read_reply", sequence=sequence, result=f"0x{result:08x}", bytes=len(content) - 4)
        self.usable = True
        if result: raise FileResultError(result)
        return bytes(content[4:])

    def read(self, path):
        if path not in self.files.values(): raise PermissionError("不是本轮固定路径")
        if self.strict:
            if not self.usable: raise PermissionError("预检通道已失败，拒绝继续发送")
            if path in self.attempted_paths: raise PermissionError("预检固定路径不允许重发")
            if self.profile == "supplement" and path != tuple(self.files.values())[len(self.attempted_paths)]:
                raise PermissionError("补证必须按固定顺序先完成三个对照")
            self.attempted_paths.add(path)
        wire = wire_path(path)
        try:
            self.exchange(struct.pack("<HH", 0x1001, 0x0F) + b"\0" + wire + b"\0", 4)
            content = self.exchange(READ, 4 + 4096)
        except FileResultError:
            if self.profile == "supplement" and path in CONTROL_PATHS: self.usable = False
            raise
        if self.profile == "supplement" and path in CONTROL_PATHS and not control_matches(content):
            # 先允许上层保存原始内容，再报告对照失败；在此处已封锁后续发送。
            self.usable = False
        return content


class FileResultError(ValueError):
    def __init__(self, result):
        self.result = result
        super().__init__(f"文件服务返回 0x{result:08x}；不能据此认定文件不存在")


def run_session(output, transport="libusb", profile="stage1", *, _operation=None):
    """显式调用才枚举设备；固定读取保持原门禁，新转存流程由独立入口验证后注入。"""
    if transport != "libusb" or _operation is None: raise PermissionError("只允许本包固定补证操作")
    files = profile_files(profile)
    strict = profile in ("preflight", "supplement")
    if strict and transport != "libusb":
        raise ValueError("固定预检仅允许 libusb，不扩展原生后端的路径门禁")
    import usb.core
    import usb.util
    import usb.backend.libusb1
    from .environment import PMCA
    sys.path.insert(0, str(PMCA))
    from pmca.usb.sony import SonySenserAuthDevice

    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    report = {"model": MODEL, "transport": transport, "profile": profile, "firmware_version": None, "firmware_version_source": "body_version_not_observed_by_MSC_probe",
              "first_authentication_passed": False, "second_authentication_passed": False,
              "communication_verified": False, "ordinary_identity_restored": False, "files": [],
              "service_start_requested": False, "camera_protocol_requests": 0, "phase": "device_discovery",
              "service_stop_attempts": 0, "service_stop_result": "not_attempted",
              "camera_file_write_commands_sent": False, "debug_commands_sent": False,
              "preload_written": False, "card_formatted": False, "evidence_dir": str(output)}
    if _operation is not None: report["profile"] = "code85-fixed-read"
    def log(event, **fields):
        record = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
        with (output / "events.jsonl").open("a") as handle: handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, ensure_ascii=False), flush=True)

    source_paths = [Path(__file__), Path(__file__).with_name("usb_adapter.py"),
                    Path(__file__).with_name("preflight.py"),
                    Path(__file__).with_name("supplement.py"), Path(__file__).with_name("bulk_reader.py"),
                    PMCA / "pmca/usb/sony.py", PMCA / "pmca/usb/constants.py"]
    if transport == "native-host":
        source_paths += [Path(__file__).with_name(n) for n in ("native_host.py", "native_usb.m", "native_usb.dylib")]
    (output / "sources.json").write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                                   for p in source_paths}, indent=2) + "\n")
    # 保留底层IOKit错误；PyUSB的-99本身无法说明插件创建或接口打开失败的原因。
    os.environ.setdefault("LIBUSB_DEBUG", "3")
    backend = usb.backend.libusb1.get_backend(find_library=lambda _: str(LIBUSB))
    if backend is None: raise RuntimeError("libusb 后端不可用")
    read_limit=file_read_limit(_operation)
    report['file_usb_read_limit']=read_limit
    if getattr(_operation,'strict_usb_reads',False):
        backend=StrictReadBackend(backend)
        report['strict_usb_read_status']=True
    current = None
    claimed = False
    detached = False
    started = False
    port = None
    reader = None
    preflight_contents = {}
    deadline = time.monotonic() + 100

    def timeout():
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise TimeoutError("会话超过批准的时间上限")
        return max(1, min(8000, int(remaining * 1000)))

    def find(pid=None):
        devices = list(usb.core.find(find_all=True, idVendor=VID, backend=backend))
        matches = [d for d in devices if (pid is None or d.idProduct == pid)
                   and (port is None or (d.bus, tuple(d.port_numbers or ())) == port)]
        if len(matches) > 1: raise ValueError("多个 Sony 设备匹配，拒绝选择")
        return matches[0] if matches else None

    def wait_for(pid, seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            device = find(pid)
            if device is not None: return device
            time.sleep(0.25)
        return None

    class Driver:
        """认证阶段只接受三种认证包及两个服务控制请求。"""
        def __init__(self, device):
            self.device = device
            self.phase = "auth"
            interface = device.get_active_configuration()[(0, 0)]
            if _operation is None: raise PermissionError("本包只允许固定补证操作")
            _operation.interface_checked(device, interface)
            incoming = [e for e in interface if e.bmAttributes & 3 == 2 and e.bEndpointAddress & 0x80]
            outgoing = [e for e in interface if e.bmAttributes & 3 == 2 and not e.bEndpointAddress & 0x80]
            if not incoming or not outgoing: raise ValueError("接口缺少 bulk 端点")
            self.ep_in, self.ep_out = incoming[0].bEndpointAddress, outgoing[0].bEndpointAddress
        def reset(self): pass
        def getId(self): return self.device.idVendor, self.device.idProduct
        def write(self, data, ep=0):
            if ep: raise PermissionError("拒绝额外端点")
            if self.phase == "auth":
                if len(data) != 516: raise PermissionError("认证报文长度异常")
                command, salt = struct.unpack_from(">HH", data)
                if salt or (~command & 0xFFFF) not in (1, 3, 5): raise PermissionError("拒绝其他认证命令")
            if self.phase != "auth": _operation.guard_packet(data)
            report["camera_protocol_requests"] += 1
            # 写入失败或回执丢失也可能已经向设备发送命令，不能等成功后才登记。
            if self.phase == "fixed-read" and data[HEADER.size:HEADER.size+4] == struct.pack("<HH", 0x1001, 0x10):
                report["camera_file_write_commands_sent"] = True
            count = self.device.write(self.ep_out, data, timeout=timeout())
            if count != len(data): raise IOError("USB 短写；不重试请求")
            return count
        def read(self, length, ep=0, timeout=None):
            # 协议仍按32KiB逻辑块处理；备份可用更小的底层读取拼成同一逻辑块。
            limit = 32768 if self.phase == "fixed-read" else 4100
            if ep or not 1 <= length <= limit: raise PermissionError("读取超出本轮端点/长度限制")
            requested=min(length,read_limit) if self.phase=="fixed-read" else length
            return bytes(self.device.read(self.ep_in, requested, timeout=io_timeout()))
        def vendorRequestOut(self, request, value, index, data=b""):
            if (request, value, index) not in (START, STOP) or data: raise PermissionError("拒绝其他控制请求")
            try:
                report["camera_protocol_requests"] += 1
                self.device.ctrl_transfer(0x43, request, value, index, data, timeout=timeout())
                log("service_control_returned", operation="start" if value == START[1] else "stop")
            except usb.core.USBError as exc:
                # 参考实现容忍 stall；必须由后续认证或身份变化确认状态。
                log("service_control_usb_error", operation="start" if value == START[1] else "stop", message=str(exc))
                if getattr(exc, "backend_error_code", None) != -9: raise

    io_timeout = timeout

    class Auth(SonySenserAuthDevice):
        def _sendAuthPacket(self, command, data=b""):
            result, reply = super()._sendAuthPacket(command, data)
            log("authentication_reply", pid=f"{self.driver.getId()[1]:04x}", command=command, result=result,
                algorithm=("SHA-256" if result == 8 else "SHA-1") if command == 1 else None)
            return result, reply

    def release(surrender=False):
        nonlocal claimed, detached
        if current is None: return
        if getattr(current, "is_native_host", False):
            current.close(surrender=surrender)
            return
        if claimed:
            try: usb.util.release_interface(current, 0)
            except Exception as exc: log("release_interface_error", message=str(exc))
        if detached:
            try: current.attach_kernel_driver(0)
            except Exception as exc: log("reattach_driver_error", message=str(exc))
        usb.util.dispose_resources(current)
        claimed = detached = False

    def open_driver():
        nonlocal current, claimed, detached
        report["phase"] = "interface_claim"
        same_port(current, port)
        if transport == "native-host":
            from .native_host import NativeDevice
            from types import SimpleNamespace
            endpoints = [SimpleNamespace(bEndpointAddress=e.bEndpointAddress, bmAttributes=e.bmAttributes)
                         for e in current.get_active_configuration()[(0, 0)]]
            usb.util.dispose_resources(current)
            current = NativeDevice(current, endpoints)
            log("native_interface_opened", pid=f"{current.idProduct:04x}", physical_port=port)
            return Driver(current)
        driver = Driver(current)
        detached = claim_interface(current, usb.util, log, allow_settle=not started)
        claimed = True
        return driver

    try:
        current = find()
        if current is None: raise RuntimeError("未连接 Sony 相机")
        model = usb.util.get_string(current, current.iProduct)
        validate_target(current.idVendor, current.idProduct, model)
        port = (current.bus, tuple(current.port_numbers or ()))
        same_port(current, port)
        log("target_confirmed", product=model, pid=f"{current.idProduct:04x}", physical_port=port)
        report["phase"] = "host_unmount"
        unmount_camera(current, log)
        driver = open_driver()
        auth = Auth(driver)
        started = True
        report["service_start_requested"] = True
        report["phase"] = "service_start"
        auth.start()
        report["phase"] = "authentication"
        auth.authenticate()
        report["first_authentication_passed"] = True
        log("normal_authentication_passed")
        # 重枚举会移除普通设备，避免向已移除的设备执行重新绑定。
        detached = False
        release(surrender=True)
        current = wait_for(0x0336, 20)
        if current is None: raise RuntimeError("服务身份 054c:0336 未在同一物理端口出现")
        log("service_identity_seen", pid="0336", physical_port=port)
        driver = open_driver()
        auth = Auth(driver)
        report["phase"] = "service_start"
        auth.start()
        report["phase"] = "authentication"
        auth.authenticate()
        report["second_authentication_passed"] = True
        log("service_authentication_passed")
        driver.phase = "fixed-read"
        report["phase"] = "operation"
        if _operation is not None:
            _operation(driver, output, log, report)
        else:
            reader = FixedReader(driver, log, profile)
            for name, path in files.items():
                record = {"path": path}
                log("fixed_read_requested", path=path)
                try:
                    content = reader.read(path)
                except FileResultError as exc:
                    record.update(status="service_error", result=f"0x{exc.result:08x}")
                except Exception as exc:
                    if strict:
                        record.update(status="protocol_or_transport_error", error=f"{type(exc).__name__}: {exc}")
                        report["files"].append(record)
                        log("fixed_file_result", **record)
                    raise
                else:
                    (output / name).write_bytes(content)
                    if strict: preflight_contents[path] = content
                    record.update(status="read" if content else "empty", bytes=len(content),
                                  sha256=hashlib.sha256(content).hexdigest(), local_file=name)
                report["files"].append(record)
                log("fixed_file_result", **record)
                if profile == "supplement" and path in CONTROL_PATHS and not control_matches(preflight_contents.get(path)):
                    raise ValueError(f"补证对照未通过：{path}；停止后续文件请求")
            report["communication_verified"] = any(r["status"] == "read" for r in report["files"])
    except (Exception, KeyboardInterrupt) as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
        report["backend_error_code"] = getattr(exc, "backend_error_code", None)
        report["failure_phase"] = report["phase"]
        report["failure_traceback"] = traceback.format_exc()
        log("error", message=report["failure"], phase=report["failure_phase"],
            backend_error_code=report["backend_error_code"], traceback=report["failure_traceback"])
    finally:
        # 独立 5 秒退出上限；停止请求结果不等于正常模式已恢复。
        safe_exit = _operation is None or _operation.safe_to_stop
        if started and not safe_exit:
            report["recovery_required"] = True
            log("automatic_stop_withheld", reason="本次固定证据或前后预加载未全部确认；不自动退出服务")
            detached = False  # 不在未知任务状态下自动重新绑定内核驱动。
        if started and safe_exit:
            try:
                if current is None: current = find(0x0336)
                if current is None: raise RuntimeError("未找到可请求退出的服务设备")
                same_port(current, port)
                report["service_stop_attempts"] += 1
                report["service_stop_result"] = "attempting"
                log("stop_senser_attempted", attempt=report["service_stop_attempts"])
                report["camera_protocol_requests"] += 1
                current.ctrl_transfer(0x43, *STOP, b"", timeout=5000)
                report["service_stop_result"] = "returned"
                log("stop_senser_control_returned")
            except Exception as exc:
                code = getattr(exc, "backend_error_code", None)
                report["service_stop_backend_error_code"] = code
                report["service_stop_result"] = ("stalled" if code == -9 else "error") if report["service_stop_attempts"] else "withheld"
                report["service_stop_error"] = type(exc).__name__+": "+str(exc)
                log("stop_senser_exception", message=str(exc), backend_error_code=code)
        try: release()
        except Exception as exc: log("dispose_error", message=str(exc))
        # 退出后只由外层主机元数据观察器核对；不再libusb枚举。
        if strict:
            assess = assess_supplement if profile == "supplement" else assess_preflight
            report[profile] = assess(report["files"], preflight_contents)
            report["file_request_attempts"] = 0 if reader is None else 2 * len(files) - reader.requests_remaining
            log(f"{profile}_assessed", **report[profile], file_request_attempts=report["file_request_attempts"])
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        if os.geteuid() == 0:
            # 管理员进程只把本次新建的证据交还给工作区用户，便于其查看。
            owner = output.parent.stat()
            for artifact in output.iterdir():
                os.chown(artifact, owner.st_uid, owner.st_gid, follow_symlinks=False)
            os.chown(output, owner.st_uid, owner.st_gid, follow_symlinks=False)
    return report
