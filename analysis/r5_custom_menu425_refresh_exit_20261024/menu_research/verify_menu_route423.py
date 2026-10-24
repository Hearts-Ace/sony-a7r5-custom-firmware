"""Bind final AP menu opening, Enter and stack restoration evidence.

Compositional local CPU evidence with explicit model/OS/display boundaries.
Does not rebuild or change any firmware component.
"""
from pathlib import Path
import hashlib, json, struct
from read_menu import Image
ROOT = Path(__file__).resolve().parents[3]; OUT = Path(__file__).resolve().parent
AP = OUT.parent / 'ap/appFw.so'
im = Image(AP)
sha = hashlib.sha256(im.data).hexdigest()
assert sha == '4017b746b8720b0b3c0b1b8d79b00472548361b335048656b72c71be77202717'
audit = json.loads((OUT.parent / 'import/module_audit.json').read_text())
e = json.loads((OUT / 'ap_1005_enter423_replay.json').read_text())
p = json.loads((OUT / 'native_1005_push_pop423_replay.json').read_text())
assert e['passed'] and p['passed'] and e['sha256'] == p['sha256'] == sha
assert e['cases'] == 78 and e['callback_cases'] == 108 and p['cases'] == 6
assert len(e['native_main_open_cases']) == 2
assert all(x['from_screen'] == '0x2d7' and x['target_screen'] == '0x2ed' and x['queue_records'] == 1 for x in e['native_main_open_cases'])
assert all(x['push_count'] == x['pop_count'] == 1 and x['restored_screen'] == '0x2d7' and x['lower_stack_unchanged'] for x in p['rows'])

screens = []
for sid, factory, vt, typename in [(0x2d7, 0x1d69944, 0x58da118, '23scr7001_1004_controller'),
                                   (0x2ed, 0x1d6c180, 0x58da180, '23scr7001_1005_controller')]:
    entry = 0x506bf20 + sid * 0x60
    assert im.pointer(entry + 8) == factory
    ti = im.pointer(vt - 8)
    assert im.string(im.pointer(ti + 8)) == typename
    instructions = list(im.md.disasm(im.read(factory, 0x40), factory))
    assert any(i.mnemonic == 'mov' and i.op_str == f'w6, #{sid:#x}' for i in instructions)
    screens.append(dict(screen=hex(sid), screen_table_entry=hex(entry), factory=hex(factory),
                        actual_vtable=hex(vt), rtti=hex(ti), typename=typename,
                        presenter_index=struct.unpack('<I', im.read(entry + 0x18, 4))[0],
                        stack_enabled=im.read(entry + 0x1c, 1)[0]))
assert im.pointer(0x57d1440) == 0x21deab8
assert im.pointer(0x595e9e0) == 0x57d13a0
assert im.pointer(0x58d2fb8 + 0x18) == 0x1d15b50
assert im.pointer(0x58d2fb8 + 0x20) == 0x1d15798

spans = [(0x1d69944, 0x40), (0x1d6c180, 0x40), (0x21deab8, 0x130),
         (0x1bd5720, 0x30), (0x1bcf064, 0x6c), (0x21dd740, 0xd8),
         (0x1cdbb08, 0x34), (0x1d15b50, 0x210), (0x1ec657c, 0x90),
         (0x1ec5304, 0x23c), (0x1ec51f4, 0x3c),
         (0x1d15798, 0x64), (0x1ec557c, 0x34c)]
dis = '\n\n'.join(im.dis(start, size) for start, size in spans) + '\n'
(OUT / 'menu_route423_disassembly.txt').write_text(dis)
artifacts = ['replay_ap_1005_enter423.py', 'ap_1005_enter423_replay.json',
             'replay_native_1005_push_pop423.py', 'native_1005_push_pop423_replay.json',
             'verify_menu_route423.py', 'menu_route423_disassembly.txt']
report = dict(schema='r5-filter-menu-route423/1', passed=True,
              source=str(AP.relative_to(ROOT)), sha256=sha,
              module_audit_sha256=hashlib.sha256((OUT.parent / 'import/module_audit.json').read_bytes()).hexdigest(),
              screens=screens,
              opening=dict(native_controller='scr7001_1004_controller', from_screen='0x2d7',
                           native_handler='0x21deab8', handler_registration='0x57d1440',
                           menu_id='0x635', descriptor_screen_offset='0x20', target_screen='0x2ed',
                           native_manager='0x1d15b50', queue_records=1, queue_record_bytes=20, mode=0,
                           cases=2),
              selection=dict(native_controller='scr7001_1005_controller', native_handler='0x21e1b7c',
                             menu_action_offset='0x88', actual_compiled_callback=hex(audit['symbols']['r5_filter_menu_select']),
                             enter_cases=78, direct_callback_cases=108,
                             close_requests_per_enter=1, missing_config_submits=False,
                             off_always_selectable=True),
              restoration=dict(native_open='0x1ec5304', native_push='0x1ec51f4',
                               native_close='0x1ec557c', push_count=1, pop_count=1,
                               bytes_per_screen_group=12, returned_screen='0x2d7',
                               previous_main_presenter_preserved=True, lower_stack_unchanged=True, cases=6),
              artifacts={name:hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in artifacts},
              limits=['This combines three bounded local CPU stages: actual1004 Enter queues open; native open helper pushes the prior screen group; actual1005 Enter queues close, then native close helper pops the group. The Sony event loop joining these stages is not executed.',
                      'The actual preceding menu-row controller is1004/screen2d7. The1001/screen2d4 controller is a category layer and is not claimed to directly open the custom menu.',
                      'The AP actual initializer, descriptors/rows, reviewed virtual remaps, native tree lookups and compiled menu callback execute. Only custom r5_filter_request is stubbed; persistence and CP ACK are separate tests.',
                      'Model getters/category source, initial native registries/deques/objects, native validation/log/lock services, factories, object lifecycle notifications and orientation use explicit synthetic fixtures. The standard RELATIVE relocation application is not a complete Sony loader.',
                      'No physical display, native OS loop, camera, SD, ISP/JPEG or device heap/cache evidence. This is not an on-device navigation acceptance result.'])
(OUT / 'menu_route423_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:report[k] for k in ['passed', 'sha256', 'opening', 'selection', 'restoration']}, ensure_ascii=False))
