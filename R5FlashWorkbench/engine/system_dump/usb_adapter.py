"""Mac USB 适配基础；导入、检查依赖和离线测试不会枚举相机。"""

from pathlib import Path
import re
import struct
import sys
import time

from .core import MODEL, NORMAL_PID, VID

LIBUSB = Path(__file__).resolve().parents[1]/"lib/libusb-1.0.dylib"
HEADER = struct.Struct("<IHHBBBB")


def validate_target(vid, pid, model):
    if (vid, pid, model) != (VID, NORMAL_PID, MODEL):
        raise ValueError("必须从 ILCE-7RM5 的 054c:0e0a 普通身份开始，拒绝 A7C2 或未确认的服务设备")


def same_port(device, port):
    observed = (device.bus, tuple(device.port_numbers or ()))
    if not port[1] or observed != port:
        raise ValueError("设备物理端口不明或重枚举后端口改变")
    return True


def claim_interface(device, usb_util, log=None, *, allow_settle=False):
    """仅在服务启动前有界等待同一接口；不重置设备或重新选择设备。"""
    log = log or (lambda *args, **kwargs: None)
    detached = False
    port = (device.bus, tuple(device.port_numbers or ()))
    try:
        active = device.is_kernel_driver_active(0)
        log("kernel_driver_state", active=active)
        if active:
            log("kernel_driver_detach_requested")
            device.detach_kernel_driver(0)
            detached = True
            log("kernel_driver_detached")
    except NotImplementedError:
        # Darwin 后端可能不提供此查询，实际 claim 失败会直接向上传播。
        pass
    try:
        for attempt in range(1, 4):
            same_port(device, port)
            log("interface_claim_requested", attempt=attempt)
            try:
                usb_util.claim_interface(device, 0)
                break
            except Exception as exc:
                log("interface_claim_failed", attempt=attempt, error_type=type(exc).__name__,
                    message=str(exc), backend_error_code=getattr(exc, "backend_error_code", None),
                    errno=getattr(exc, "errno", None))
                # 只等待首次分离驱动后的插件就绪；服务已启动、其他错误和第三次失败均立即停止。
                if (not allow_settle or sys.platform != "darwin" or not detached
                        or getattr(exc, "backend_error_code", None) != -99 or attempt == 3):
                    raise
                log("interface_plugin_wait", attempt=attempt, delay_seconds=0.25)
                time.sleep(0.25)
        log("interface_claimed")
    except BaseException:
        if detached:
            try:
                same_port(device, port)
                log("kernel_driver_reattach_requested")
                device.attach_kernel_driver(0)
                log("kernel_driver_reattached")
            except Exception as cleanup_error:
                # 回收失败单独记录，保留最初接管异常及其调用栈。
                log("kernel_driver_reattach_failed", error_type=type(cleanup_error).__name__,
                    message=str(cleanup_error), backend_error_code=getattr(cleanup_error, "backend_error_code", None))
        raise
    return detached


class ReadOnlyDriver:
    """认证之后限制服务文件读取；禁止文件写、删除、DEBUG 及固件命令。"""

    def __init__(self, driver, allowed_paths=None):
        self.driver = driver
        self.selected = False
        self.allowed_paths = None if allowed_paths is None else frozenset(allowed_paths)

    def write(self, data, ep=0):
        if ep != 0 or len(data) < HEADER.size + 7:
            raise PermissionError("拒绝额外端点或过短报文")
        size, function, sequence, version, micon, offset, status = HEADER.unpack_from(data)
        body = data[HEADER.size:]
        if size != len(body) or function != 0x40 or any((version, micon, offset, status)):
            raise PermissionError("拒绝不符合只读服务协议的报文")
        group, command = struct.unpack_from("<HH", body)
        if group != 0x1001 or body[4] != 0:
            raise PermissionError("拒绝其他命令组或传输模式")
        if command == 0x0F:
            path = body[5:]
            if not re.fullmatch(rb"/tmp/jiritsu/[ -~]+\x00", path):
                raise PermissionError("路径必须是单个 Work 路径")
            if self.allowed_paths is not None and path[:-1] not in self.allowed_paths:
                raise PermissionError("拒绝读取本轮固定清单之外的路径")
            self.selected = False
            result = self.driver.write(data, ep)
            self.selected = True
            return result
        if command == 0x11 and body == struct.pack("<HH", 0x1001, 0x11) + b"\0\xff\0" and self.selected:
            self.selected = False
            return self.driver.write(data, ep)
        raise PermissionError("只读适配器拒绝此操作")

    def read(self, length, ep=0, timeout=None):
        if ep != 0: raise PermissionError("拒绝额外端点")
        return self.driver.read(length, ep=ep, timeout=timeout)

    def getId(self):
        return self.driver.getId()

    def reset(self):
        # 供已认证的 Senser 包装对象初始化使用，不透传物理重置。
        return None
