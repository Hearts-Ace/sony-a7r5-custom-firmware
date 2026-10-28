"""Bounded read-only AP/libObj ownership and native widget detach evidence."""
from read_menu import *


def ranges(im, windows):
    return [dict(name=name, va=hex(address), bytes=size,
                 sha256=hashlib.sha256(im.read(address, size)).hexdigest(),
                 disassembly=im.dis(address, size))
            for name, address, size in windows]


def main():
    ap = Image(ROOT/'build_r5_m4strict_4.04_20261015/patched/appFw.so')
    lib = Image(ROOT/'unpacked/r5/usr_complete/lib/libObj.so')
    ap_ranges = ranges(ap, [
        ('view string param constructor', 0x1884c7c, 0x54),
        ('view string constructor', 0x1884cd0, 0xb0),
        ('view string destructor', 0x18855f8, 0x8c),
        ('view string param rectangle getter', 0x18847c4, 0x44),
        ('native list primary param initializer', 0x18292a8, 0xb8),
        ('native list primary row filling', 0x185dd2c, 0x178),
        ('view string resource or char selection', 0x1885b20, 0x24),
        ('view string raw char branch', 0x1885d3c, 0x20),
    ])
    lib_ranges = ranges(lib, [
        ('Widget::setParent', 0x174eb4, 0x58),
        ('WidgetD2Ev', 0x1757ac, 0x40),
        ('WidgetBase destructor', 0x176794, 0x78),
        ('graphics branch destructor', 0x1662b8, 0x14),
        ('graphics branch base destructor', 0x1634b4, 0x14),
        ('graphics tree destructor', 0x10886c, 0x64),
        ('widget node destructor', 0x17a204, 0x14),
        ('widget node tree destructor', 0x17a188, 0x54),
        ('node base destructor', 0x133bd4, 0x48),
        ('node parent accessor', 0x133858, 0xc),
        ('node set parent', 0x133b44, 0x90),
        ('node remove child', 0x1339cc, 0x98),
        ('list unlink links', 0x12b23c, 0x64),
    ])
    data = dict(
        schema='r5-custom-filter423-renderer-lifetime-static/1',
        camera_io=False, firmware_modified=False,
        ap=dict(path=str(ap.path.relative_to(ROOT)), sha256=hashlib.sha256(ap.data).hexdigest()),
        library=dict(path=str(lib.path.relative_to(ROOT)), sha256=hashlib.sha256(lib.data).hexdigest()),
        conclusions=dict(
            param_copy=dict(begin='object+0x1d8', bytes='0x650', end_exclusive='object+0x828',
                            first_owning_gfx_object='object+0x830',
                            native_destructor_frees=['object+a20 optional graphics pointer', 'object+a48 optional graphics pointer'],
                            native_destructor_ignores_param_range=True,
                            scope='No owning graphics object or owning-destructor state is copied. Parameters contain inline values and borrowed text/attribute data; string param+38 char pointer is reset to zero for private resource names.',
                            recommendation='Keep size exactly650 and never copy through830. Prefer fresh native param initialization if future filters add nontrivial rich-text data.'),
            detach=dict(
                entry='AP18855f8 -> PLT16dbba0 -> libObj WidgetD2Ev1757ac',
                chain=['1757ac WidgetD2Ev', '176794 WidgetBase destructor',
                       '17a204 object+8 node destructor', '17a188 tree destructor',
                       '133bd4 node base destructor', '133858 nonnull parent check',
                       '133b44(this,0) set parent', '1339cc(parent,this) removes child',
                       '12b23c unlinks intrusive neighbors'],
                conclusion='Native string destruction removes the node from the parent before the backing extra block is freed. No additional manual detach is indicated by this path.',
                ordering='Destroy extra strings in reverse construction order before owner native destructor and free only after all native destructors return.'),
            construction_context=dict(fields=['owner+1b8 u64', 'owner+1c0 u64', 'owner+1c8 u64', 'owner+1d0 u32 -> context+20', 'owner+1d4 u32 -> context+28'],
                                      matches_native_string_constructor=True),
        ),
        limitations=['Static code and symbol binding evidence only; no device execution',
                     'This does not establish rendered column geometry, z-order or label truncation',
                     'Nested parameter data should be reconsidered if later UI changes introduce rich-text attribute ownership'],
        ap_ranges=ap_ranges, library_ranges=lib_ranges)
    (OUT/'renderer_lifetime423_evidence.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    (OUT/'renderer_lifetime423_disassembly.txt').write_text('\n\n'.join(
        f'## {prefix} {r["name"]} {r["va"]} bytes={r["bytes"]}\n{r["disassembly"]}'
        for prefix, rr in [('AP', ap_ranges), ('libObj', lib_ranges)] for r in rr)+'\n')
    print(json.dumps({k:v for k,v in data.items() if k not in ('ap_ranges','library_ranges')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
