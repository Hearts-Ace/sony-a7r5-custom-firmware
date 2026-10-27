"""Compiled 4.31 projection -> original type1c row/scroll computation.

PageVM supplies explicit worker, page factory and UX fixtures. The private
compiled navigation/projection, original GUI-table initializer and original
type1c generation/configuration execute. This is not an LCD/renderer test.
"""
from pathlib import Path
import hashlib, json, struct, sys

HERE = Path(__file__).resolve().parent
CAND = HERE.parent
ROOT = CAND.parents[1]
sys.path[:0] = [str(ROOT/'vendor/audit-python'), str(CAND/'menu_research'), str(CAND)]
from replay_page425 import PageVM, RAM, X, R
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE

OWNER = 0x31000000
SHORT_RESOURCE = 0x02ff4300
SCROLL_FIXTURES = {
    0x18434d0, 0x1842e50, 0x16dbeb0, 0x1842a44, 0x1842a34,
    0x1842a2c, 0x1842ab0, 0x18430e8, 0x18438dc, 0x1843294,
    0x1842d28, 0x1842d5c, 0x18428e4, 0x1844250, 0x1842cc4, 0x1843f94,
}


def publication_offsets():
    audit = json.loads((CAND/'import/module_audit.json').read_text())
    sections = {s['index']: s for s in audit['sections']
                if Path(s['object']).name == 'r5_filter_names423.o'}
    with (CAND/'import/objects/r5_filter_names423.o').open('rb') as f:
        elf = ELFFile(f)
        return {s.name: int(sections[s['st_shndx']]['va'], 16)+s['st_value']
                for s in elf.get_section_by_name('.symtab').iter_symbols()
                if s.name in ('versions', 'names_header', 'version_count')}


def seed_names(vm, mask, offsets):
    # This is the explicitly named publication data fixture; getters execute.
    for i in range(12):
        short = ('F%02d' % (i+1)).encode()
        full = ('胶片 %02d / Full Filter Name' % (i+1)).encode()
        vm.u.mem_write(offsets['versions']+vm.bias+i*88,
                       short.ljust(24, b'\0')+full.ljust(64, b'\0'))
    vm.w32(offsets['version_count']+vm.bias, 1)
    vm.w64(offsets['names_header']+vm.bias, (1 << 32) | mask)


def rect(vm, index):
    at = vm.styles+index*52+40
    x, y, w, h = struct.unpack('<HHHH', vm.u.mem_read(at, 8))
    return [x, y, w, h]


def main():
    rows = []
    offsets = publication_offsets()
    candidate = CAND/'ap/appFw.so'
    candidate_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    original = ROOT/'assets/firmware/a8d5cd444bf0-appFw.so'
    for bias in (0, 0x40000000):
      for layout in (0, 1):
       for mask in (0xfff, (1 << 1) | (1 << 8), 0, 1 << 11):
        vm = PageVM(bias)
        vm.mask = mask
        seed_names(vm, mask, offsets)
        c, p = vm.open()
        if layout:
            vm.call(vm.q(vm.q(p)+0x40), p, layout)
        assert vm.d(vm.pmap+9*16) == 0x1c
        vm.u.mem_map(OWNER, 0x200000)
        vm.native(0x16f389c, 0)
        calls = []

        def hook(u, pc, size, arg):
            if pc-bias in SCROLL_FIXTURES:
                calls.append(dict(pc=hex(pc-bias), w1=u.reg_read(X[1]),
                    s0=struct.unpack('<f', struct.pack('<I', u.reg_read(R.UC_ARM64_REG_S0)))[0]))
                vm.ret(0)

        vm.u.hook_add(UC_HOOK_CODE, hook)
        available = [0]+[i for i in range(1, 13) if mask & (1 << (i-1))]
        # Read the rectangles compiled by the actual page, not copied constants.
        list_rect = rect(vm, 9)
        expected_list = [1, 51, 112, 330] if layout == 0 else [8, 64, 150, 330]
        assert list_rect == expected_list, (layout, list_rect)
        overlay_rects = [rect(vm, 22+i) for i in range(5)]
        assert overlay_rects == [[list_rect[0], list_rect[1]+i*66, list_rect[2], 66]
                                 for i in range(5)], overlay_rects
        assert all(vm.masks[22+i] == 0 for i in range(5))
        assert all(vm.masks[i] == 1 for i in (16, 17, 18, 19, 20, 21, 27, 28))

        def navigate(number):
            at = available.index(vm.selected)
            target = available.index(number)
            for _ in range(abs(target-at)):
                vm.event(0x2010005 if target > at else 0x2010002)
            assert vm.selected == number

        for at, number in enumerate(available):
            navigate(number)
            param = vm.q(vm.pmap+9*16+8)
            assert vm.d(param+0xd30) == len(available)
            assert vm.d(param+0xd34) == 0
            assert vm.d(param+0xd38) == at
            assert vm.d(param+0xd3c) == 0x635
            assert bytes(vm.u.mem_read(param+0xd40, 1)) == b'\1'
            assert bytes(vm.u.mem_read(param+0xd56, 1)) == b'\1'
            assert [vm.d(param+0x830+i*4) for i in range(len(available))] == [SHORT_RESOURCE+i for i in available]
            assert all(vm.d(param+0x30+i*4) == vm.d(param+0x430+i*4) == 0xffffffff
                       for i in range(len(available)))
            # The normal native create-screen rectangle fill is outside this
            # PageVM; copy its compiled style rectangle into the owner fixture.
            vm.u.mem_write(OWNER, bytes(0x100000))
            vm.u.mem_write(OWNER+0x1d8, bytes(vm.u.mem_read(param, 0xd68)))
            vm.w32(OWNER+0x1d8+0x20, list_rect[2])
            vm.w32(OWNER+0x1d8+0x24, list_rect[3])
            vm.native(0x1892068, OWNER)
            generated = []
            for logical in range(-2, len(available)):
                slot = OWNER+0x1de8+(logical+2)*0x9e8
                resource = vm.d(slot)
                active = bytes(vm.u.mem_read(slot+0x37c, 1))[0]
                disabled = bytes(vm.u.mem_read(slot+0x37d, 1))[0]
                expected = 0xffffffff if logical < 0 else SHORT_RESOURCE+available[logical]
                assert resource == expected
                assert active == int(logical == at)
                assert disabled == 0
                if logical >= 0:
                    assert [vm.d(slot+0x310+i*4) for i in range(4)] == [20, 0, 70, 60]
                    vm.events.clear()
                    vm.call(vm.sy['r5_filter_menu_name_draw'], RAM+0x360000, resource)
                    rendered = [e[1] for e in vm.events if e[0] == 'name_char']
                    expected_text = '关闭' if available[logical] == 0 else 'F%02d' % available[logical]
                    assert rendered == [expected_text], rendered
                    assert not rendered[0].startswith(('>', '*', ' '))
                generated.append(dict(logical=logical, resource=hex(resource), active=active))
            assert sum(r['active'] for r in generated) == 1
            calls.clear()
            vm.native(0x1892414, OWNER)
            stride = [r['s0'] for r in calls if r['pc'] == '0x18438dc']
            scroll_focus = [r['w1'] for r in calls if r['pc'] in ('0x1844250', '0x1842cc4')]
            assert stride == [66.0] and scroll_focus == [at, at], (stride, scroll_focus)
            visible = [available[k] if 0 <= k < len(available) else None
                       for k in range(at-2, at+3)]
            touch_results = []
            for row, target in enumerate(visible):
                navigate(number)
                overlay = vm.q(vm.pmap+(22+row)*16+8)
                assert bytes(vm.u.mem_read(overlay+0x2c, 1))[0] == int(target is not None)
                before = sum(x[0] == 'request' for x in vm.calls)
                vm.touch(22+row)
                assert vm.selected == (number if target is None else target)
                assert not any(x[0] == 'pop' for x in vm.calls)
                if target is None:
                    assert sum(x[0] == 'request' for x in vm.calls) == before
                touch_results.append(dict(row=row, target=target, selected=vm.selected))
            navigate(number)
            rows.append(dict(bias=hex(bias), layout=layout, mask=hex(mask),
                available=available, selected=number, absolute_focus=at, mode=0,
                generated_rows=generated, native_highlight_count=1,
                visible_configurations=visible, list_rect=list_rect,
                overlay_rects=overlay_rects, native_scroll_stride=stride[0],
                native_scroll_focus=scroll_focus, touch_results=touch_results,
                compiled_projection_executed=True, native_generation_executed=True,
                no_prefix_in_short_text=True, no_touch_exit=True))
        vm.cleanup()
    assert hashlib.sha256(candidate.read_bytes()).hexdigest() == candidate_digest
    report = dict(passed=True, version='4.31', AP_sha256=candidate_digest,
        original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
        cases=rows, compiled_projection=True, native_row_generation='0x1892068',
        native_gui_table_initializer='0x16f389c', native_scroll_configuration='0x1892414',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), camera_io=False,
        limitations=[
            'Publication data, page factories, worker completion, native name setter and low-level scroll setters are explicit fixtures.',
            'Compiled navigation/projection/name getters/resource bridge and original native row/scroll configuration execute; style rectangles are copied into the owner fixture because native create_screen is tested separately.',
            'Overlay66 rectangles and logical event mapping are verified. Actual GUI hit testing, native scroll placement, fonts, LCD and camera timing remain unobserved.',
        ])
    (HERE/'native_list431_verified.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=len(rows), AP_sha256=candidate_digest)))


if __name__ == '__main__':
    main()
