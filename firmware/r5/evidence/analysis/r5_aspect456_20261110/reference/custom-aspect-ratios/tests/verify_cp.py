#!/usr/bin/env python3
"""回放逐照片适配器及原厂复制／池操作；OS 信号量和参数库采用明确模型。"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm_const as A

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from native import Native

POOL, TASKS, STACK, WORK, STOP = 0x1112c54, 0x3000000, 0x4000000, 0x4010000, 0x4020000
STRIDE, GFW, SNAPSHOT, REQUEST = 0x6688, 0x157aa10, 0x163f3f0, 0x163f3c8


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class Replay:
    def __init__(self, raw, code, report):
        self.u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.u.mem_map(0x100000, 0x1b00000)
        self.u.mem_write(0x108000, raw)
        self.u.mem_write(report['RX'], code)
        self.u.mem_map(TASKS, 0x1000000)
        self.u.mem_map(STACK, 0x30000)
        self.u.reg_write(A.UC_ARM_REG_CPSR, 0x1f)
        self.symbols = report['symbols']
        self.size = (9504, 6336)
        self.fail_wait = False
        self.inject_snapshot_change = False
        self.native_calls = {}
        self.allocations = 0
        self.u.hook_add(UC_HOOK_CODE, self.hook)
        self.write(POOL + 4, 490)
        self.write(POOL + 0x10, TASKS)
        self.write(POOL + 0x14, STRIDE * 490)
        self.write(0x195e254, 1)

    def write(self, address, value):
        self.u.mem_write(address, struct.pack('<I', value))

    def word(self, address):
        return struct.unpack('<I', self.u.mem_read(address, 4))[0]

    def hook(self, u, pc, size, unused):
        if pc in (0x5f51bc, 0x5f53fc, 0x5f58b0, 0x4596f4, 0xae08c8):
            self.native_calls[hex(pc)] = self.native_calls.get(hex(pc), 0) + 1
        if pc == 0x5f51bc and self.inject_snapshot_change and u.reg_read(A.UC_ARM_REG_R0) == SNAPSHOT:
            self.inject_snapshot_change = False
            self.write(self.symbols['aspect_cp_sequence'], self.word(self.symbols['aspect_cp_sequence']) + 2)
            self.write(self.symbols['aspect_cp_selection'], 7)
        if pc not in (0x5c9034, 0x5c4e08, 0x5c5260, 0x5c4f58, 0x5c5340, 0xb0de92, 0x4e929c, 0x5ef69c):
            return
        result = 0
        if pc == 0x5ef69c:
            require(u.reg_read(A.UC_ARM_REG_R0) == 490, 'sidecar 分配量异常')
            self.allocations += 1
            result = WORK + 0x8000
        if pc in (0x5c4e08, 0x5c4f58):
            result = int(self.fail_wait)
        if pc == 0x4e929c:
            address = u.reg_read(A.UC_ARM_REG_R1)
            u.mem_write(address, struct.pack('<4H', *self.size, 0, 0))
            result = 1
        u.reg_write(A.UC_ARM_REG_R0, result)
        u.reg_write(A.UC_ARM_REG_PC, u.reg_read(A.UC_ARM_REG_LR))

    def call(self, name, *args, owner=None, fifth=0):
        for register, value in zip((A.UC_ARM_REG_R0, A.UC_ARM_REG_R1, A.UC_ARM_REG_R2, A.UC_ARM_REG_R3), args):
            self.u.reg_write(register, value)
        if owner is not None:
            self.u.reg_write(A.UC_ARM_REG_R4, owner)
        self.u.reg_write(A.UC_ARM_REG_SP, STACK + 0xff00)
        self.u.reg_write(A.UC_ARM_REG_LR, STOP | 1)
        self.write(STACK + 0xff00, fifth)
        self.u.emu_start(self.symbols[name], STOP, count=200000)
        require(self.u.reg_read(A.UC_ARM_REG_PC) == STOP, '模块函数未返回：' + name)
        require(self.u.reg_read(A.UC_ARM_REG_SP) == STACK + 0xff00, '模块函数未还原 SP：' + name)
        return self.u.reg_read(A.UC_ARM_REG_R0)

    def select(self, id):
        self.u.reg_write(A.UC_ARM_REG_R5, GFW)
        self.call('aspect_cp_receive_hook', 0, id + 1 if id else 2)

    def freeze(self, id, request):
        self.select(id)
        self.write(REQUEST, request)
        self.call('aspect_freeze_copy', SNAPSHOT, GFW, 0xdbc)

    def bind(self, index, request):
        task = TASKS + index * STRIDE
        self.write(task + 0x5ae8, request)
        self.call('aspect_capture_copy', task + 0x20, SNAPSHOT)
        return task


def verify(stock, module):
    native = Native(stock, 'CP')
    report = json.loads((module / 'build.json').read_text())
    code = (module / 'module.bin').read_bytes()
    require(hashlib.sha256(code).hexdigest() == report['code_sha256'], '模块摘要不符')
    for name, digest in report['sources'].items():
        require(hashlib.sha256((HERE / 'source' / name).read_bytes()).hexdigest() == digest, '源码已变化：' + name)
    r = Replay(native.raw, code, report)
    binding = crop_cases = formats = pool_cases = 0
    # 全部原生池索引可绑定；快照后的菜单切换不得改变其比例。
    for index in range(490):
        id = 4 + index % 4
        r.freeze(id, index + 1)
        r.select(4 + (index + 1) % 4)
        task = r.bind(index, index + 1)
        require(r.call('aspect_task_id', task) == id, '快照比例未绑定到照片')
        binding += 1
    # 不匹配编号、未完成发布和重叠的接收更新均不能继承上次比例。
    r.freeze(4, 1000)
    require(r.call('aspect_task_id', r.bind(0, 999)) == 0, '错误请求编号继承了比例')
    r.freeze(5, 1001)
    r.write(r.symbols['aspect_cp_sequence'], 1)
    r.call('aspect_freeze_copy', SNAPSHOT, GFW, 0xdbc)
    require(r.call('aspect_task_id', r.bind(0, 1001)) == 0, '未完成选择被发布')
    r.write(r.symbols['aspect_cp_sequence'], 0)
    r.freeze(6, 1002)
    r.inject_snapshot_change = True
    r.call('aspect_freeze_copy', SNAPSHOT, GFW, 0xdbc)
    require(r.call('aspect_task_id', r.bind(0, 1002)) == 0, '跨代快照被发布')
    for pointer in (TASKS - 1, TASKS + 1, TASKS + 490 * STRIDE):
        require(r.call('aspect_task_id', pointer) == 0, '非照片对象指针被接纳')
    expected_dimensions = ((9504, 5872), (9504, 3976), (7920, 6336), (9504, 5136))
    for id in range(4, 8):
        r.freeze(id, 2000 + id)
        task = r.bind(0, 2000 + id)
        for primary in (1, 2, 4):
            for secondary in (0, 1, 2, 4):
                r.write(task + 0x5980, primary)
                r.write(task + 0x5988, secondary)
                for offset, geometry in ((0x5f78, (9600, 6336, 9504, 6336, 0, 0)),
                                         (0x5fdc, (1664, 1080, 1616, 1080, 0, 0))):
                    original = struct.pack('<6H', *geometry)
                    r.u.mem_write(task + offset, original)
                    r.call('aspect_jpeg_request_copy', WORK, task + offset, 12, task)
                    result = bytes(r.u.mem_read(WORK, 12))
                    require(bytes(r.u.mem_read(task + offset, 12)) == original, '源任务几何被改写')
                    preview = primary in (1, 2) or secondary in (1, 2)
                    require((result != original) == preview, 'JPEG/RAW 预览格式隔离失败')
                    if offset == 0x5f78 and preview:
                        require(struct.unpack('<6H', result)[2:4] == expected_dimensions[id - 4], 'JPEG 裁切尺寸不符')
                    crop_cases += 1
                formats += 1
        # 原生尺寸查询主体执行，参数库读取按给定 WH 建模；RAW 的 WH 保持。
        for size in ((9504, 6336), (6240, 4160), (4752, 3168), (3168, 2112)):
            r.size = size
            for format in (1, 2, 4):
                r.write(task + 0x5980, format)
                result = r.call('aspect_notify_primary_hook', WORK, 2, 0, 0, owner=task, fifth=0x11223344)
                require(result == 1, '原生尺寸查询返回值丢失')
                actual = struct.unpack('<2H', r.u.mem_read(WORK, 4))
                require((actual == size) == (format == 2), 'RAW 尺寸或压缩尺寸隔离失败')
                formats += 1
        # JPEG THM 改请求副本，维持目标 canvas 和原有 flags。
        r.write(task + 0x5980, 1)
        r.write(task + 0x5988, 2)
        r.write(task + 0x3c, 0)
        r.u.mem_write(WORK, b'\xa5' * 0x200)
        r.u.mem_write(WORK + 0x70, struct.pack('<10H', 1664, 1080, 0, 0, 1616, 1080, 0, 0, 1616, 1080))
        r.u.mem_write(WORK + 0xf8, struct.pack('<10H', 256, 120, 0, 0, 160, 120, 0, 0, 160, 120))
        r.call('aspect_thumbnail_request_clear', WORK + 0x12c, 0x20, task)
        output = struct.unpack('<10H', r.u.mem_read(WORK + 0xf8, 20))
        require(output[:6] == (256, 120, 0, 0, 160, 120), '缩略图 canvas 或基础字段被更改')
        require(0 < output[8] <= 160 and 0 < output[9] <= 120, '缩略图适配越界')
        crop_cases += 1
        # 原生范围检查返回 true 不等于成功插回池，分别测试等待失败和成功。
        r.write(POOL, TASKS + STRIDE)
        r.write(POOL + 8, 489)
        r.fail_wait = True
        r.call('aspect_pool_release', POOL, task)
        require(r.call('aspect_task_id', task) == id, '释放失败时过早清除了比例')
        r.fail_wait = False
        r.call('aspect_pool_release', POOL, task)
        require(r.call('aspect_task_id', task) == 0 and r.word(POOL + 8) == 490, '真实释放后比例未退休')
        pool_cases += 2
    r.call('aspect_pool_reset', POOL)
    require(all(r.call('aspect_task_id', TASKS + i * STRIDE) == 0 for i in range(490)), '池重置后残留旧比例')
    return dict(schema='r5-aspect-cp-runtime-replay/1', passed=True, camera_io=False,
                code_sha256=report['code_sha256'], source_sha256=report['sources'],
                native_CP_sha256=hashlib.sha256(native.raw).hexdigest(),
                task_bindings=binding, crop_cases=crop_cases, format_cases=formats, pool_cases=pool_cases,
                native_calls_executed=r.native_calls, snapshot_race_rejected=True,
                native_functions=['memcpy', 'memmove', 'bzero', 'GFW to ImageParam mapping', 'pool range and linked-list release', 'still image size query'],
                sidecar_allocations=r.allocations,
                models=['OS context/wait/signal primitives', 'shared heap allocator returns retained 490B block',
                        'backup parameter reader supplies input WH', 'diagnostic logging'],
                limitations=['未执行完整 CP 任务调度、ISP、真实编码器或相机；并发边界使用显式注入，不是实际线程调度'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('输出已存在')
    receipt = verify(args.stock, args.module)
    with args.output.open('x') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(receipt, ensure_ascii=False))
