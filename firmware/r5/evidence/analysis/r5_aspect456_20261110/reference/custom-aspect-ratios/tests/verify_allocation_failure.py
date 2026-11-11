#!/usr/bin/env python3
"""CP实际接收/ACK和AP冻结/返回的配对回放；传输与OS服务显式建模。"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import struct
import sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from unicorn import arm_const as C
from unicorn import arm64_const as A
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from native import Native
from verify_ap_menu import Machine, require
from verify_cp import Replay, WORK, GFW, SNAPSHOT, REQUEST, STACK, STOP
PARAMETER, AP_STOP = 0x20010000, 0x40000000
DIMENSIONS = {0: (9504, 6336), 4: (9504, 5872), 5: (9504, 3976),
              6: (7920, 6336), 7: (9504, 5136)}


class Capture(Replay):
    def __init__(self, raw, patch, fault=0, heap=True, ready=True):
        report = patch['module']
        at = patch['source_VA'] - 0x108000
        code = raw[at:at + report['code_bytes']]
        require(hashlib.sha256(code).hexdigest() == report['code_sha256'], 'CP载荷不符')
        self.fault, self.acks = fault, []
        self.gate = patch['gate_VA']
        self.postprocess_calls = []
        super().__init__(raw, code, report)
        self.write(self.symbols['aspect_cp_ready'], int(ready))
        self.write(0x195e254, int(heap))
        self.write(GFW + 0xcc, 2)
        self.request_number = 0
        self.raw_preview_crop = True

    def hook(self, u, pc, size, unused):
        if pc == 0x5ef69c and self.fault:
            self.allocations += 1
            if self.fault > 0:
                self.fault -= 1
            u.reg_write(C.UC_ARM_REG_R0, 0)
            u.reg_write(C.UC_ARM_REG_PC, u.reg_read(C.UC_ARM_REG_LR))
            return
        if pc in (0x33d004, 0x33d14c, 0xadee8e):
            self.postprocess_calls.append(hex(pc))
            u.reg_write(C.UC_ARM_REG_R0, 0)
            u.reg_write(C.UC_ARM_REG_PC, u.reg_read(C.UC_ARM_REG_LR))
            return
        if pc == 0x898210:
            address = u.reg_read(C.UC_ARM_REG_R0)
            length = u.reg_read(C.UC_ARM_REG_R1)
            require(length == 12, 'ACK长度变化')
            self.acks.append(bytes(u.mem_read(address, length)))
            u.reg_write(C.UC_ARM_REG_R0, 0)
            u.reg_write(C.UC_ARM_REG_PC, u.reg_read(C.UC_ARM_REG_LR))
            return
        return super().hook(u, pc, size, unused)

    def exchange(self, packet):
        require(len(packet) == 24, 'AP包长度变化')
        pointer = WORK + 0x6000
        self.write(pointer - 12, 0x12345678)
        self.u.mem_write(pointer, packet)
        self.u.reg_write(C.UC_ARM_REG_R0, pointer)
        self.u.reg_write(C.UC_ARM_REG_SP, STACK + 0xff00)
        self.u.reg_write(C.UC_ARM_REG_LR, STOP | 1)
        before = len(self.acks)
        self.u.emu_start(0x33f305, STOP, count=300000)
        require(self.u.reg_read(C.UC_ARM_REG_PC) == STOP and
                self.u.reg_read(C.UC_ARM_REG_SP) == STACK + 0xff00, 'CP接收未正常返回')
        require(len(self.acks) == before + 1, '没有唯一原生ACK')
        ack = self.acks[-1]
        require(ack[0] == 1 and ack[2:8] == packet[2:8], 'ACK身份字段改变')
        return struct.unpack_from('<I', ack, 8)[0]

    def resident(self, site, *arguments, owner=None, fifth=0):
        for reg, value in zip((C.UC_ARM_REG_R0, C.UC_ARM_REG_R1,
                               C.UC_ARM_REG_R2, C.UC_ARM_REG_R3), arguments):
            self.u.reg_write(reg, value)
        if owner is not None:
            self.u.reg_write(C.UC_ARM_REG_R4, owner)
        self.u.reg_write(C.UC_ARM_REG_SP, STACK + 0xff00)
        self.u.reg_write(C.UC_ARM_REG_LR, (site + 4) | 1)
        self.write(STACK + 0xff00, fifth)
        # 从真实调用指令进入；未安装hook的原生复制也须执行实际callee。
        self.u.emu_start(site | 1, site + 4, count=300000)
        require(self.u.reg_read(C.UC_ARM_REG_PC) == site + 4 and
                self.u.reg_read(C.UC_ARM_REG_SP) == STACK + 0xff00, '常驻门未正常返回')
        return self.u.reg_read(C.UC_ARM_REG_R0)

    def photo(self, expected_id, slot=0):
        self.request_number += 1
        self.write(REQUEST, self.request_number)
        self.resident(0xadf128, SNAPSHOT, GFW, 0xdbc)
        task = 0x3000000 + slot * 0x6688
        self.write(task + 0x5ae8, self.request_number)
        self.resident(0xadd846, task + 0x20, SNAPSHOT)
        actual_id = self.call('aspect_task_id', task)
        require(actual_id == expected_id, '照片编号与已接受选择不一致')
        original = struct.pack('<6H', 9600, 6336, 9504, 6336, 0, 0)
        self.write(task + 0x5980, 1)
        self.write(task + 0x5988, 4)
        self.u.mem_write(task + 0x5f78, original)
        self.resident(0x473562, WORK, task + 0x5f78, 12, owner=task)
        jpeg_geometry = bytes(self.u.mem_read(WORK, 12))
        jpeg = struct.unpack('<6H', self.u.mem_read(WORK, 12))[2:4]
        require(jpeg == DIMENSIONS[expected_id], 'JPEG输出与已接受选择不一致')
        require(bytes(self.u.mem_read(task + 0x5f78, 12)) == original, 'JPEG源几何改写')
        packet = bytearray(b'\xa5' * 0x25c)
        for i in range(3):
            struct.pack_into('<6H', packet, 0xcc + i * 0x20, 9600, 6336, 9504, 6336, 0, 0)
        self.u.mem_write(task + 0x5b3c, bytes(packet))
        self.resident(0xae78ae, WORK, task + 0x5b3c, 0x25c, owner=task)
        require(bytes(self.u.mem_read(WORK, 0x25c)) == packet, 'RAW/HEIF共享YC包被提前裁切')
        require(bytes(self.u.mem_read(task + 0x5b3c, 0x25c)) == packet, '共享YC源包改写')
        self.size = (9504, 6336)
        self.resident(0xae77d8, WORK, 2, 0, 0, owner=task, fifth=0x11223344)
        notified = struct.unpack('<2H', self.u.mem_read(WORK, 4))
        require(notified == DIMENSIONS[expected_id], '尺寸通知与照片不一致')
        self.resident(0xae7822, WORK, 2, 0, 0, owner=task, fifth=0x11223344)
        heif_target = struct.unpack('<2H', self.u.mem_read(WORK, 4))
        require(heif_target == DIMENSIONS[expected_id], 'HEIF目标通知与已接受选择不一致')
        self.write(task + 0x5980, 2)
        self.write(task + 0x5988, 0)
        self.resident(0x473562, WORK, task + 0x5f78, 12, owner=task)
        # 此调用构造RAW内嵌JPEG的局部请求，须与JPEG采用相同的已接受裁切；
        # 共享源及RAW传感器通知仍保持原幅。
        raw_preview_geometry = bytes(self.u.mem_read(WORK, 12))
        expected_preview = jpeg_geometry if self.raw_preview_crop else original
        require(raw_preview_geometry == expected_preview, 'RAW预览与本次验收约定不一致')
        require(bytes(self.u.mem_read(task + 0x5f78, 12)) == original, 'RAW共享源几何改写')
        self.resident(0xae77d8, WORK, 2, 0, 0, owner=task, fifth=0x11223344)
        require(struct.unpack('<2H', self.u.mem_read(WORK, 4)) == (9504, 6336), 'RAW尺寸裁切')
        return dict(id=actual_id, jpeg=jpeg, HEIF_target=heif_target,
                    shared_YC_preserved=True, notification=notified,
                    RAW_preview=struct.unpack('<6H', raw_preview_geometry)[2:4],
                    RAW_sensor_notification_preserved=True)


class Application(Machine):
    def __init__(self, raw, report, stock_ap, bias=0):
        self.paused = None
        self.active_send = None
        self.waits = 0
        self.mutexes = set()
        self.publish_schedule = []
        self.mode, self.send_return = 'pause', 0
        self.error_calls = []
        decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        self.native_callees = {int(i.op_str[1:], 16) for i in
            decoder.disasm(stock_ap[0x3565f34:0x3566d00], 0x3565f34) if i.mnemonic == 'bl'}
        super().__init__(raw, report, bias)

    def addr(self, name):
        # 共用模型的新hook也用于回放旧4.12；缺少新helper时只禁用该断点。
        if name == 'aspect_selection_begin' and name not in self.symbols:
            return -1
        return super().addr(name)

    def hook(self, u, address, size, data):
        pc = address - self.bias
        if self.publish_schedule:
            next_publish = self.publish_schedule[0]
            boundary = (next_publish['at'] == 'lock' and pc == 0x16dc820 or
                        next_publish['at'] == 'begin' and self.mutexes and
                        address == self.addr('aspect_selection_begin'))
            if boundary:
                self.publish_schedule.pop(0)
                self.paused = dict(kind='publish', context=u.context_save(), pc=address,
                                   selected=next_publish['selected'], token=self.token(),
                                   at=next_publish['at'])
                u.emu_stop()
                return
        if address == self.addr('aspect_ap_send_hook'):
            self.active_send = dict(frame=u.reg_read(A.UC_ARM64_REG_X29),
                pointer=u.reg_read(A.UC_ARM64_REG_X1), length=u.reg_read(A.UC_ARM64_REG_X2))
        if pc == 0x355882c:
            if self.mode == 'finish':
                return self.returning(self.send_return)
            pointer, length = (u.reg_read(A.UC_ARM64_REG_X1 + i) for i in range(2))
            self.paused = dict(kind='send', context=u.context_save(), packet=bytes(u.mem_read(pointer, length)),
                frame=u.reg_read(A.UC_ARM64_REG_X29), token=self.token())
            u.emu_stop()
            return
        if pc == 0x16dc820:
            mutex = u.reg_read(A.UC_ARM64_REG_X0)
            if mutex in self.mutexes:
                self.waits += 1
                self.paused = dict(kind='wait', lock=mutex, context=u.context_save(),
                    pc=address, token=self.token())
                u.emu_stop()
                return
            self.mutexes.add(mutex)
            return self.returning(0)
        if pc == 0x16dc620:
            mutex = u.reg_read(A.UC_ARM64_REG_X0)
            require(mutex in self.mutexes, '未持有参数锁即解锁')
            self.mutexes.remove(mutex)
            return self.returning(0)
        if pc == 0x16d95f0:
            destination, fill, length = (u.reg_read(A.UC_ARM64_REG_X0 + i) for i in range(3))
            require(length <= 4096, '原memset越界')
            u.mem_write(destination, bytes([fill & 255]) * length)
            return self.returning(destination)
        if pc in (0x1c448dc, 0x1c61d14, 0x1c93d88):
            return super().hook(u, address, size, data)
        if pc in self.native_callees:
            self.error_calls.append(hex(pc))
            return self.returning()
        return super().hook(u, address, size, data)

    def resume_wait(self, call):
        require(call['kind'] == 'wait', '不是等待中的参数提交')
        require(call['lock'] not in self.mutexes, '前一请求未释放闸门即唤醒')
        self.u.context_restore(call['context'])
        self.mode, self.paused = 'pause', None
        self.u.emu_start(call['pc'], AP_STOP, count=500000)
        require(self.paused is not None and self.paused['kind'] == 'send', '唤醒后没有继续原生发送')
        return self.paused

    def publish_and_resume(self, call):
        require(call['kind'] == 'publish', '不是菜单发布调度边界')
        self.query('aspect_set', call['selected'])
        published = self.token()
        self.u.context_restore(call['context'])
        self.mode, self.paused = 'pause', None
        self.u.emu_start(call['pc'], AP_STOP, count=500000)
        require(self.paused is not None, '菜单发布后没有继续参数请求')
        return self.paused, published

    def query(self, name, *args):
        # 处于native_send断点外执行；独立栈避免覆盖仍在等待ACK的原生帧。
        context = self.u.context_save()
        for i, value in enumerate(args):
            self.u.reg_write(A.UC_ARM64_REG_X0 + i, value)
        self.u.reg_write(A.UC_ARM64_REG_SP, 0x3000f000)
        self.u.reg_write(A.UC_ARM64_REG_LR, AP_STOP)
        self.u.emu_start(self.addr(name), AP_STOP, count=500000)
        require(self.u.reg_read(A.UC_ARM64_REG_PC) == AP_STOP, '独立AP查询未返回')
        value = self.u.reg_read(A.UC_ARM64_REG_X0)
        self.u.context_restore(context)
        return value

    def begin(self, selected, *, select=True, stack=0x3001f000):
        if select:
            self.query('aspect_set', selected)
        self.write(PARAMETER, 0x12345678)
        self.write(PARAMETER + 8, self.native)
        self.write(PARAMETER + 0x54, 0)
        self.paused = None
        self.mode = 'pause'
        self.u.reg_write(A.UC_ARM64_REG_X0, PARAMETER)
        self.u.reg_write(A.UC_ARM64_REG_X1, PARAMETER + 0x1000)
        self.u.reg_write(A.UC_ARM64_REG_SP, stack)
        self.u.reg_write(A.UC_ARM64_REG_LR, AP_STOP)
        self.u.emu_start(0x3565f34 + self.bias, AP_STOP, count=500000)
        require(self.paused is not None and self.paused['kind'] in ('send', 'wait', 'publish'),
                '没有停在实际发送或等待边界')
        return self.paused

    def finish(self, call, status, native_return=0):
        require(call['kind'] == 'send', '等待请求尚不能交付ACK')
        self.u.context_restore(call['context'])
        self.write(call['frame'] + 0x228, status)
        self.mode, self.send_return = 'finish', native_return
        self.u.emu_start(0x355882c + self.bias, AP_STOP, count=500000)
        require(self.u.reg_read(A.UC_ARM64_REG_PC) == AP_STOP, 'AP原返回路径未完成')
        result = self.u.reg_read(A.UC_ARM64_REG_X0)
        self.mode = 'pause'
        return result

    def send(self, capture, selected, select=True):
        call = self.begin(selected, select=select)
        status = capture.exchange(call['packet'])
        result = self.finish(call, status)
        return result, status


def queue_checks(ap_raw, ap_report, cp_raw, cp_report, stock_ap):
    rows = []
    for bias in (0, 0x10000000):
        for scenario in ('two_success', 'failure_then_queued_old', 'failure_then_new',
                         'same_id_new_epoch', 'cancel_after_failure'):
            capture = Capture(cp_raw, cp_report, fault=0 if scenario == 'two_success' else 1)
            app = Application(ap_raw, ap_report, stock_ap, bias)
            first = app.begin(4)
            require(first['kind'] == 'send', '首条正常消息未进入发送')
            next_id = 5 if scenario == 'failure_then_new' else 0 if scenario == 'cancel_after_failure' else 4
            explicit = scenario in ('failure_then_new', 'same_id_new_epoch', 'cancel_after_failure')
            waiting = app.begin(next_id, select=explicit, stack=0x30018000)
            require(waiting['kind'] == 'wait', '第二参数消息未正常排队')
            require(app.query('aspect_get') == 0, '排队期间意外显示未接受裁切')
            first_status = capture.exchange(first['packet'])
            require(first_status == (0xf000 if scenario == 'two_success' else 0xf001), '首条资源结果不符')
            app.finish(first, first_status)
            after_first = app.query('aspect_get')
            if scenario != 'two_success':
                require(after_first == 0, '拒绝或新选择未完成时显示私有裁切')
            second = app.resume_wait(waiting)
            wire = second['packet'][8]
            expected_id = 0 if scenario in ('failure_then_queued_old', 'cancel_after_failure') else next_id
            require(wire == (expected_id + 1 if expected_id else 2), '排队旧代私有请求重新启用裁切')
            second_status = capture.exchange(second['packet'])
            require(second_status == 0xf000, '后续实际发送没有正常接收')
            app.finish(second, second_status)
            final_status = app.read(second['frame'] + 0x228)
            require(final_status == 0xf000, '取锁后重新冻结的请求未正常完成')
            require(app.query('aspect_get') == expected_id and
                    capture.word(capture.symbols['aspect_cp_selection']) == expected_id,
                    '排队完成后AP和CP选择不一致')
            photo = capture.photo(expected_id)
            expected_allocations = 2 if scenario in ('failure_then_new', 'same_id_new_epoch') else 1
            require(capture.allocations == expected_allocations, '排队旧代再次申请资源或新代不能重试')
            rows.append(dict(bias=bias, scenario=scenario, first_ACK=first_status,
                queued_wire=wire, CP_second_ACK=second_status, AP_second_status=final_status,
                AP_after_first=after_first, final_id=expected_id, photo=photo,
                modeled_pthread_wait=app.waits, allocator_calls=capture.allocations))
            del app, capture
            gc.collect()
    return rows


def publish_checks(ap_raw, ap_report, cp_raw, cp_report, stock_ap):
    rows = []
    for bias in (0, 0x10000000):
        for selected in (4, 6, 0):
            for fault in (0, 1):
                app = Application(ap_raw, ap_report, stock_ap, bias)
                capture = Capture(cp_raw, cp_report, fault=fault)
                app.publish_schedule = [dict(at='lock', selected=5),
                                        dict(at='begin', selected=selected)]
                before_lock = app.begin(4)
                require(before_lock['kind'] == 'publish' and before_lock['at'] == 'lock',
                        '没有到达首个菜单发布边界')
                before_begin, middle = app.publish_and_resume(before_lock)
                require(before_begin['kind'] == 'publish' and before_begin['at'] == 'begin',
                        '没有到达锁后登记边界')
                call, latest = app.publish_and_resume(before_begin)
                require(call['kind'] == 'send', '菜单重选后没有执行真实发送')
                require(not app.publish_schedule, '未完成菜单发布调度')
                require(app.query('aspect_get') == 0, '重选但未准入的比例被显示为接受')
                frozen = app.read(call['frame'] + 0x74)
                require(frozen == (latest if selected else 0), '读取与登记之间改选后冻结旧epoch')
                wire = call['packet'][8]
                require(wire == (selected + 1 if selected else 2), '菜单重选未进入实际参数包')
                ack = capture.exchange(call['packet'])
                rejected = bool(selected and fault)
                require(ack == (0xf001 if rejected else 0xf000), '菜单重选后的CP准入不符')
                app.finish(call, ack)
                expected_id = 0 if rejected else selected
                require(app.query('aspect_get') == expected_id and
                        capture.word(capture.symbols['aspect_cp_selection']) == expected_id,
                        '菜单重选完成后AP和CP选择不一致')
                require(not app.mutexes, '菜单重选完成后参数锁未释放')
                photo = capture.photo(expected_id)
                rows.append(dict(bias=bias, selected=selected, fault=fault,
                    initial=before_lock['token'], intermediate=middle, latest=latest,
                    frozen=frozen, wire=wire, ACK=ack, final_id=expected_id, photo=photo))
                del app, capture
                gc.collect()
    return rows


def preview_checks(stock, raw, report):
    import io
    from elftools.elf.elffile import ELFFile
    from verify_guide_visibility import ModelGuide, PAGES, WIDGET
    from verify_guide_native import LIBRARIES, PALETTE_SHA, reader
    fs = reader((stock / 'archive/0700_part_image/dev/nflasha15').read_bytes())
    libraries = {path: fs.read_inode(fs.walk(path)) for path in LIBRARIES}
    for path, (_, digest) in LIBRARIES.items():
        require(hashlib.sha256(libraries[path]).hexdigest() == digest, '原生显示库身份不符')
    palette = fs.read_inode(fs.walk('/share/app/color_cmn.uxc'))
    require(hashlib.sha256(palette).hexdigest() == PALETTE_SHA, '颜色银行身份不符')
    layout = json.loads((HERE / 'evidence/preview-filter-fix-20261106/ui-layout.json').read_text())
    rows = []
    for bias in (0, 0x10000000):
        for index, page in enumerate(PAGES):
            m = ModelGuide(raw, report, libraries, palette, bias)
            m.ap_elf = ELFFile(io.BytesIO(raw))
            m.setup(page, layout)
            for selected in range(4, 8):
                for status in (0xf000, 0xf001):
                    m.produce(selected)
                    token = m.read(m.addr('aspect_ap_selection'))
                    require(m.merge(page) == 1, '基线裁切Guide不可见')
                    m.invoke('aspect_guide_update', WIDGET)
                    require(m.u.mem_read(WIDGET + 0x41, 1) == b'\2', '基线Guide父节点未显示')
                    tracked = m.invoke('aspect_selection_begin', token)
                    require(tracked == 1 and m.invoke('aspect_selection_id', token) == 0,
                            '等待ACK仍公开私有裁切')
                    # 不重新运行producer，已有遮罩应被正常公共显示合并撤销。
                    require(m.merge(page) == 0, '等待ACK时机型门仍放行旧Guide')
                    m.invoke('aspect_guide_update', WIDGET)
                    require(m.u.mem_read(WIDGET + 0x41, 1) == b'\3', '等待ACK遗留旧Guide')
                    m.invoke('aspect_selection_end', token, status, tracked)
                    accepted = status == 0xf000
                    public = m.invoke('aspect_selection_id', m.read(m.addr('aspect_ap_selection')))
                    require(public == (selected if accepted else 0), 'ACK后公开选择不符')
                    allowed = m.merge(page)
                    m.invoke('aspect_guide_update', WIDGET)
                    require(allowed == int(accepted) and m.u.mem_read(WIDGET + 0x41, 1) ==
                            (b'\2' if accepted else b'\3'), 'ACK后旧Guide显示状态不符')
                    rows.append(dict(bias=bias, page=index, selected=selected, ACK=status,
                                     no_producer_between_ACK_and_visibility_merge=True,
                                     visible_after_ACK=accepted))
            del m
            gc.collect()
    return rows


def verify(stock, ap_path, ap_report, cp_path, cp_report, expect):
    stock_ap = Native(stock, 'AP').raw
    Native(stock, 'CP')
    ap_raw, cp_raw = ap_path.read_bytes(), cp_path.read_bytes()
    require(hashlib.sha256(ap_raw).hexdigest() == ap_report['sha256'], 'AP与收据不符')
    require(hashlib.sha256(cp_raw).hexdigest() == cp_report['output_sha256'], 'CP与收据不符')
    rows = []
    for bias in (0, 0x10000000):
        for selected in range(4, 8):
            for scenario in ('success', 'fail_once_then_recover', 'always_fail', 'heap_not_ready',
                             'accepted_then_allocator_unavailable', 'module_not_ready'):
                rejected = scenario in ('fail_once_then_recover', 'always_fail', 'heap_not_ready', 'module_not_ready')
                capture = Capture(cp_raw, cp_report,
                    fault=1 if scenario == 'fail_once_then_recover' else -1 if scenario == 'always_fail' else 0,
                    heap=scenario != 'heap_not_ready', ready=scenario != 'module_not_ready')
                # legacy只复现旧分配失败，不给旧组件追加4.17的预览需求。
                capture.raw_preview_crop = expect == 'fixed'
                app = Application(ap_raw, ap_report, stock_ap, bias)
                call = app.begin(selected)
                if expect == 'fixed':
                    require(app.query('aspect_get') == 0 and
                            app.query('aspect_selection_id', app.token()) == 0,
                            'ACK前仍显示已接受的私有裁切')
                    require(app.read(call['frame'] + 0x74) == call['token'], '未冻结完整epoch')
                    capture.photo(0)
                ack = capture.exchange(call['packet'])
                admitted_allocations = capture.allocations
                if expect == 'fixed':
                    require(app.query('aspect_get') == 0, '收到CP ACK但尚未交付时意外发布私有比例')
                    if rejected:
                        capture.photo(0)
                app.finish(call, ack)
                if expect == 'legacy':
                    require(ack == 0xf000 and app.query('aspect_get') == selected, '旧版未复现接受私有选择')
                    effective = 0 if rejected else selected
                else:
                    require(ack == (0xf001 if rejected else 0xf000), 'ACK不符合准入结果')
                    require(app.query('aspect_get') == (0 if rejected else selected), 'AP未按ACK回退')
                    effective = 0 if rejected else selected
                if scenario == 'accepted_then_allocator_unavailable':
                    capture.photo(selected)
                    capture.fault = -1
                    capture.write(0x195e254, 0)
                photos = [capture.photo(effective, i) for i in range(3)]
                if expect == 'fixed':
                    require(capture.allocations == admitted_allocations, '冻结或照片格式链再次分配裁切状态')
                    if rejected:
                        require(not (app.token() & 15), '回退残留私有token')
                    before = capture.allocations
                    _, native_ack = app.send(capture, 0)
                    require(native_ack == 0xf000 and app.query('aspect_get') == 0, '原厂比例受失败标志污染')
                    require(capture.allocations == before, '原厂比例触发分配')
                    capture.photo(0)
                    if scenario in ('fail_once_then_recover', 'always_fail', 'heap_not_ready'):
                        capture.fault = 0
                        capture.write(0x195e254, 1)
                        _, recovered = app.send(capture, selected)
                        require(recovered == 0xf000 and app.query('aspect_get') == selected, '明确重选未恢复')
                        capture.photo(selected)
                rows.append(dict(bias=bias, selected=selected, scenario=scenario, ack=ack,
                    AP_id=app.query('aspect_get'), photos=photos, allocation_calls=capture.allocations,
                    selected_cleared_before_photos=expect == 'fixed' and rejected))
                del app, capture
                gc.collect()
    queue_rows = queue_checks(ap_raw, ap_report, cp_raw, cp_report, stock_ap) if expect == 'fixed' else []
    publish_rows = publish_checks(ap_raw, ap_report, cp_raw, cp_report, stock_ap) if expect == 'fixed' else []
    preview_rows = preview_checks(stock, ap_raw, ap_report) if expect == 'fixed' else []
    return dict(passed=True, expect=expect, camera_io=False, device_tested=False,
                AP_sha256=ap_report['sha256'], CP_sha256=cp_report['output_sha256'],
                paired_cases=len(rows), photos=sum(len(r['photos']) for r in rows),
                queue_cases=len(queue_rows), queued_submissions=queue_rows,
                publish_cases=len(publish_rows), published_submissions=publish_rows,
                preview_cases=len(preview_rows), preview_visibility=preview_rows,
                actual_CP_receiver_and_ACK_frame=True, actual_CP_resident_dispatch=True,
                actual_AP_native_serializer_and_send_return=True, real_IPC=False,
                models=['CP ACK status populates original AP response slot; no real IPC',
                        'CP three post-receive scheduling/parameter services return0; packet parsing/ACK construction execute',
                        'heap-ready/allocator faults, pthread mutex waits/returns and input WH lookup',
                        'AP diagnostics return0; memset performs exact buffer writes'],
                limitations=['没有完整GUI、真实低内存、IPC、调度/ISP/编码器或实机验证',
                             'Guide仅执行原生公共显示合并/父子绘制模型；Fn完整GUI未执行'], rows=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stock', 'ap', 'ap-report', 'cp', 'cp-report', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--expect', choices=('legacy', 'fixed'), default='fixed')
    args = parser.parse_args()
    require(not args.output.exists(), '输出已存在')
    result = verify(args.stock, args.ap, json.loads(args.ap_report.read_text()),
                    args.cp, json.loads(args.cp_report.read_text()), args.expect)
    result['test_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('passed', 'expect', 'paired_cases', 'photos')}))
