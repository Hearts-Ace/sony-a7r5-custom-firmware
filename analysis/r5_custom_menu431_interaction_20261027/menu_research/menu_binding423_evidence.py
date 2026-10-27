"""Source-bound 1005 descriptor, row selection and vtable evidence.

Reads original/4.04 AP files only.  This is static evidence, not a UI or camera
test.  In particular all vtable offsets use the +0x10 C++ address point.
"""
from read_menu import *


def u32(im, address):
    return struct.unpack('<I', im.read(address, 4))[0]


def main():
    im = Image(ROOT/'build_r5_m4strict_4.04_20261015/patched/appFw.so')
    stock = Image(ROOT/'unpacked/r5/usr_complete/lib/appFw.so')
    windows = [
        ('1005 factory', 0x1d6bfec, 0x1d4),
        ('1005 presenter constructor and factory', 0x1d90370, 0x1c8),
        ('1005 Enter', 0x21e1b7c, 0x1b0),
        ('row screen public wrapper', 0x1bd5750, 0x30),
        ('row screen and callback', 0x1bc990c, 0x44),
        ('row registry normalized access', 0x1bd9f98, 0x64),
        ('selection commit public wrapper', 0x1bd9410, 0x30),
        ('selection commit dispatch', 0x1bd9348, 0xc8),
        ('row owner primary map', 0x1bdb0b0, 0x180),
        ('separate adjacent alias map', 0x1bd960c, 0x60),
        ('menu normalizer public wrapper', 0x1bd851c, 0x30),
        ('native menu PID callback gate', 0x1bd645c, 0x98),
        ('native descriptor options callbacks', 0x1bc84e0, 0x98),
        ('view string ctor', 0x1884cd0, 0xa0),
        ('view string params', 0x18847c4, 0xc),
        ('view string update', 0x1885688, 0x500),
    ]
    ranges = []
    for name, address, size in windows:
        raw = im.read(address, size)
        same = raw == stock.read(address, size)
        assert same, (name, hex(address))
        ranges.append(dict(name=name, va=hex(address), bytes=size,
                           file_offset=hex(im.offset(address)),
                           sha256=hashlib.sha256(raw).hexdigest(),
                           unchanged_original=same,
                           disassembly=im.dis(address, size)))
    got, base = 0x591f9a8, im.pointer(0x591f9a8)
    address_point = base + 0x10
    entries = []
    for off, expected, use in [
        (0x328, 0x1bdb0b0, '1005 row to owner menu in 1bd9348'),
        (0x330, 0x1bd960c, 'adjacent map, not the 1005 commit virtual call'),
        (0x790, 0x1bd9f98, 'normalized row lookup from 1bc990c'),
        (0x798, 0x1bd9ffc, 'adjacent direct row lookup'),
    ]:
        slot = address_point + off
        actual = im.pointer(slot)
        assert actual == expected, (hex(slot), hex(actual), hex(expected))
        entries.append(dict(virtual_offset=hex(off), slot=hex(slot),
                            function=hex(actual), use=use))
    screen_table = im.pointer(0x5915668)
    screens = []
    for screen_id, expected in [(0xd4, 0x1d2db50), (0x2ed, 0x1d6c180), (0x2ee, 0x1d6c354)]:
        entry = screen_table + screen_id * 0x60
        factory = im.pointer(entry+8)
        assert factory == expected
        screens.append(dict(id=hex(screen_id), entry=hex(entry), factory=hex(factory),
                            presenter_factory=hex(im.pointer(entry))))
    counts = {}
    for pair in range(0x502a980, 0x5030590, 16):
        descriptor = im.pointer(pair+8)
        if not descriptor:
            continue
        screen, rowcount = u32(im, descriptor+0x20), u32(im, descriptor+0x54)
        has_setter = bool(im.pointer(descriptor+0x80))
        key = (screen, bool(rowcount), has_setter)
        counts[key] = counts.get(key, 0)+1
    data = dict(
        schema='r5-custom-filter423-native-menu-binding/1',
        source=str(im.path.relative_to(ROOT)),
        source_sha256=hashlib.sha256(im.data).hexdigest(),
        stock_sha256=hashlib.sha256(stock.data).hexdigest(),
        camera_io=False, firmware_modified=False,
        scope='Static AP facts; native 1005 replay is a separate artifact; no actual menu render or device test',
        screen_table=dict(got='0x5915668', base=hex(screen_table), stride='0x60', screens=screens),
        presenter_binding=dict(screen='0x2ed', table_entry='0x507d800',
                               presenter_factory='0x1d90504', presenter_ctor='0x1d90370',
                               presenter_vtable_got='0x593f8b0',
                               presenter_vtable_address_point=hex(im.pointer(0x593f8b0)+0x10),
                               param_getter='0x21e2640', param_fill='0x21e2690',
                               update='0x21e2904', list_update='0x185f370',
                               correction='21e2690 is the 2ed/1005 presenter path. A previous assignment to 1006 based on code adjacency was incorrect.'),
        inventory=[dict(screen=hex(k[0]), has_rows=k[1], has_setter=k[2], count=v)
                   for k, v in sorted(counts.items()) if k[0] in (0xd4, 0x2ed, 0x2ee)],
        utility_vtable=dict(got=hex(got), relocation_addend=hex(base),
                            address_point=hex(address_point), entries=entries,
                            correction='All virtual offsets are relative to addend+0x10. The previous +0x328-to-1bd960c claim was wrong; existing parent wrapper covers the actual +0x328 call.'),
        descriptor_contract=dict(menu='0x635', rows=['0x1600','0x160c'],
                                 screen20='0x2ed', screen24='0x4cf',
                                 null_pid='0x39fc', selected_callback='+0x78',
                                 alternate_setter='+0x80', enter_setter='+0x88',
                                 enter_flag_byte90=0, enter_argument='row ID'),
        row_contract=dict(next_screen_offset='0x18', next_screen='0x4cf',
                          screen_callback_offset='0x72', null_callback_index='0x55',
                          owner='independent native map 1bdb0b0, narrow wrapper for private rows',
                          primary_text_resource_offset='0x8',
                          left_icon_image_offset='0xc',
                          warning='row+0xc is an image/icon; passing a string ID there does not create a text column'),
        commit_path=['21e1b7c Enter', '21e0140 -> 28a87e8 selected row',
                     '1bd5750 -> 1bc990c -> virtual+790 -> normalized row lookup',
                     'row+18 returns 4cf with null callback index55',
                     '21e03e0 -> router close_screen queues one screen close',
                     '1bd9410 -> 1bd9348 -> virtual+328 -> r5_filter_row_parent',
                     '1bd851c -> r5_filter_menu_normalize -> registry635',
                     'descriptor byte90==0 -> descriptor+88(rowID)',
                     'r5_filter_menu_select requests asynchronous apply and performs no extra pop'],
        limitations=['UI rendering and navigation after native screen-manager dispatch still need integration validation',
                     'Host Unicorn fixtures do not establish camera behavior',
                     'Screen 2ee/1006 has no native row-list descriptors in this inventory'],
        ranges=ranges)
    (OUT/'menu_binding423_evidence.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    (OUT/'menu_binding423_disassembly.txt').write_text('\n\n'.join(
        f'## {r["name"]} {r["va"]} bytes={r["bytes"]}\n{r["disassembly"]}' for r in ranges)+'\n')
    print(json.dumps({k:v for k,v in data.items() if k != 'ranges'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
