"""备份专用读取策略：限制单次请求，并保留原生超时及已收部分，不隐式续读。"""
import ctypes


def file_read_limit(operation):
    size=getattr(operation,'usb_read_size',32768)
    if type(size) is not int or not 512<=size<=32768 or size%512:
        raise ValueError('文件USB读取粒度无效')
    return size


class StrictReadBackend:
    def __init__(self,backend):self.backend=backend

    def __getattr__(self,name):return getattr(self.backend,name)

    def bulk_read(self,handle,endpoint,interface,buffer,timeout):
        # PyUSB默认在TIMEOUT带部分数据时只返回长度；本任务要求任何原生异常立即停止。
        address,length=buffer.buffer_info();length*=buffer.itemsize
        transferred=ctypes.c_int()
        status=self.backend.lib.libusb_bulk_transfer(handle.handle,endpoint,
            ctypes.cast(address,ctypes.POINTER(ctypes.c_ubyte)),length,ctypes.byref(transferred),timeout)
        status=getattr(status,'value',status)
        count=transferred.value
        if not 0<=count<=length:raise OSError('libusb返回的接收长度越界')
        if status:
            from usb.backend.libusb1 import _check
            try:_check(status)
            except Exception as error:
                error.usb_partial_data=bytes(memoryview(buffer).cast('B')[:count])
                error.usb_requested_bytes=length
                error.usb_transferred_bytes=count
                raise
            raise OSError('libusb返回未知正状态')
        return count
