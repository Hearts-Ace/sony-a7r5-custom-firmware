"""Regression for reported428 failure: real name bridge and isolated inputs.

Names publication storage is seeded as an explicit data fixture. The compiled
name getters, private page, MID/ROW getters and resource-to-UTF8 bridge execute.
"""
from pathlib import Path
import hashlib, json, sys
HERE = Path(__file__).resolve().parent
CAND = HERE.parent
sys.path[:0] = [str(HERE), str(CAND)]
from replay_page425 import PageVM, RAM
from elftools.elf.elffile import ELFFile

audit = json.loads((CAND/'import/module_audit.json').read_text())
sections = {s['index']: s for s in audit['sections']
            if Path(s['object']).name == 'r5_filter_names423.o'}
with (CAND/'import/objects/r5_filter_names423.o').open('rb') as f:
    elf = ELFFile(f)
    locals_ = {s.name: int(sections[s['st_shndx']]['va'], 16)+s['st_value']
               for s in elf.get_section_by_name('.symtab').iter_symbols()
               if s.name in ('versions', 'names_header', 'version_count')}

rows = []
for bias in (0, 0x40000000):
    vm = PageVM(bias)
    for i in range(12):
        short = ('F%02d' % (i+1)).encode()
        full = ('自定义胶片 %02d / Full Filter Name' % (i+1)).encode()
        vm.u.mem_write(locals_['versions']+bias+i*88,
                       short.ljust(24, b'\0')+full.ljust(64, b'\0'))
    vm.w32(locals_['version_count']+bias, 1)
    vm.w64(locals_['names_header']+bias, (1 << 32) | 4095)
    c, p = vm.open()
    # Any private UI escape into the stock dispatcher or setters is a failure.
    def forbidden(a):
        raise AssertionError('custom input reached original Creative Look')
    for target in (0x1a6d8cc, 0x2207930, 0x220844c):
        vm.custom[target+bias] = forbidden
    observed = []
    def verify_name(number):
        rid = vm.d(vm.q(vm.pmap+11*16+8)+0x30)
        assert rid == 0x02ff4400+number
        assert bytes(vm.u.mem_read(vm.q(vm.pmap+11*16+8)+0x2c, 1)) == b'\1'
        expected = '自定义胶片 %02d / Full Filter Name' % number if number else '关闭'
        vm.events.clear()
        vm.call(vm.sy['r5_filter_menu_name_draw'], RAM+0x360000, rid)
        assert ('name_char', expected) in vm.events, (number, vm.events)
        # The focused short label must remain distinct from the full name.
        focused = []
        for index in (9, 16, 17, 18, 19, 20, 21):
            param = vm.q(vm.pmap+index*16+8)
            if bytes(vm.u.mem_read(param+0x2c, 1)) != b'\1':
                continue
            vm.events.clear()
            vm.call(vm.sy['r5_filter_menu_name_draw'], RAM+0x360000, vm.d(param+0x30))
            focused.extend(x[1] for x in vm.events if x[0] == 'name_char' and x[1].startswith('> '))
        assert focused == ['> '+('F%02d' % number if number else '关闭')], focused
        observed.append(dict(number=number, full=expected, short=focused[0]))
    verify_name(0)
    for number in range(1, 13):
        vm.event(0x2010005)  # Held Down, not just the initial key press.
        verify_name(number)
    for _ in range(5): vm.event(0x2010003)
    verify_name(12)
    for number in range(11, -1, -1):
        vm.event(0x2010002)
        verify_name(number)
    for _ in range(5): vm.event(0x2010000)
    verify_name(0)
    # A sparse published set skips absent slots in either direction.
    vm.mask = (1 << 1) | (1 << 8)
    for event, number in ((0x2010003, 2), (0x2010005, 9), (0x2010002, 2), (0x2010000, 0)):
        vm.event(event); verify_name(number)
    before = list(vm.calls)
    for event in (0x2010006, 0x2010008, 0x2010009, 0x201000b, 0x2030001, 0x2030002):
        vm.event(event)
        assert vm.d(vm.q(vm.pmap+11*16+8)+0x30) == 0x02ff4400
    for index in (3, 4, 5, 8, 10, 14, 15, 29, 30, 31, 32, 33):
        vm.touch(index)
    assert not any(x[0] == 'request' for x in vm.calls)
    assert set(i for i, t in vm.created) == {0, 1, 9, 11, 12, 13, *range(16, 29)}
    vm.w32(vm.menu_pid, 0x14c)  # Stale owned custom controller, stock MID.
    for event in (0x2010000, 0x2010003, 0x201000c, 0x2030001, 0x3010002): vm.event(event)
    assert not any(x[0] == 'request' for x in vm.calls)
    vm.w32(vm.menu_pid, 0x635)
    vm.event(0x201000f)
    for event in (0x2010000, 0x2010003, 0x201000c): vm.event(event)
    assert vm.calls.count(('pop', 0xd9)) == 1
    vm.cleanup()
    rows.append(dict(bias=hex(bias), names=observed, repeated_and_held_keys=True,
                     sparse_slots=True, adjustment_widgets_absent=True,
                     no_original_input_dispatch_or_setter=True,
                     no_update_entry_or_reload=True, stale_inputs_consumed=True))

# Preserve stock code and original native D9 styles. Only the independent635
# resolver branch in original .text can move with the appended private module.
with (CAND/'ap/appFw.so').open('rb') as a, (CAND.parent/'r5_custom_menu428_rollback425_20261024/ap/appFw.so').open('rb') as b:
    ea, eb = ELFFile(a), ELFFile(b)
    ta, tb = ea.get_section_by_name('.text'), eb.get_section_by_name('.text')
    assert ta.header == tb.header
    changed = [ta['sh_addr']+i for i, (x, y) in enumerate(zip(ta.data(), tb.data())) if x != y]
    build=json.loads((CAND/'ap/ap_build.json').read_text())
    allowed={at for row in build['patches'] for at in range(row['offset'],row['offset']+len(bytes.fromhex(row['after'])))}
    assert set(changed)<=allowed
    # Native text changes are only declared branch relocations into the new module.
    for row in build['patches']:
        if row['offset'] in changed:
            assert len(bytes.fromhex(row['after']))==4
    for va, count in ((0x405fc78, 34*52), (0x4060398, 34*52)):
        a.seek(va); b.seek(va); assert a.read(count) == b.read(count)

report = dict(passed=True, AP_sha256=hashlib.sha256((CAND/'ap/appFw.so').read_bytes()).hexdigest(),
              cases=rows, stock_text_exact428_except_declared_module_hooks=True,
              original_D9_styles_unchanged=True,
              limitations=['Publication data is a named fixture; compiled getters and UTF8 name bridge execute.',
                           'Graphics, model/worker IO and stock factory delegation services use the shared PageVM fixtures.',
                           'No physical LCD rasterization, GUI scheduling or camera acceptance.'])
(HERE/'name_input429_verified.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(dict(passed=True, cases=len(rows), AP_sha256=report['AP_sha256'])))
