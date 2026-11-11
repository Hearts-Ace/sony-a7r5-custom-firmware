#!/usr/bin/env python3
"""Final-ELF native R5 model initialization and four visibility gates.
Adapted from supplied reference verify_guide_visibility.py, no device access.
"""
from pathlib import Path
import argparse, json, traceback
from replay_ui_support import (UIReplay, require, sha, WIDGET, COMMON, INIT,
                               VIEW, ARENA, FLAGS, SNAPSHOT, PRESENTER, PARAMETERS)
PRESENTER, PARAMETERS = 0x20060000, 0x20040000
PAGES = (
    dict(config=3, row=4, count=585, params=0x270, column=0x4ff14, exposure=0x3fa10,
         output_a=0x3f5f8, output_b=0x403f8, gate=0x2146224, chain=0x2148ee8,
         setter=0x2145858, merge=0x2148f54, init=0x214e500, map_init=0x16fe488,
         model_map=0x5973a60, lookup=0x2145024, update=0x1d9fa74),
    dict(config=4, row=3, count=442, params=0x1e0, column=0x478c0, exposure=0x37cc0,
         output_a=0x37980, output_b=0x38078, gate=0x2156e70, chain=0x2158560,
         setter=0x21565a8, merge=0x2158fc8, init=0x2157e68, map_init=0x16fe570,
         model_map=0x59448f0, lookup=0x2156554, update=0x1e1b240),
)


class ModelGuide(UIReplay):
    def hook(self, u, address, size, data):
        at = address - self.bias
        if at in (0x2e7d208, 0x2e7cee4):
            return self.returning()
        if at == 0x1bd5b40:
            # 仅两个显示选项的可用性查询；机型值、映射和四门结果不桩替换。
            return self.returning(0)
        if self.externals.get(address) == '__cxa_atexit':
            return self.returning()
        return super().hook(u, address, size, data)

    def register(self, page):
        self.invoke(0x182ad30, VIEW, 3, 0, ARENA, 0x400000, 0, 0, 0)
        self.u.mem_write(FLAGS, bytes([1]) * page['count'])
        created = self.invoke('r5_ui_before_create', VIEW, 0xca4, self.table,
                              page['count'], 0, FLAGS)
        require(created >> 31, '页面容量/创建保护拒绝目标Guide')
        self.write(VIEW + 0x3e90, page['count'])
        self.write(VIEW + 0x3ec8 + page['row'] * 8, WIDGET, '<Q')
        self.invoke('r5_ui_after_create', VIEW, FLAGS, created)
        self.slot = self.addr('r5_ui_guides') + ((page['config'] - 3) * 6 + 3) * 24
        require(self.read(self.slot, '<Q') == WIDGET + 0x1d8, 'Guide未按真实canvas登记')

    def setup(self, page, layout):
        self.construct_guide()
        self.table = layout['pages'][page['config']]['tables'][1]['VA'] + self.bias
        # 实际presenter vtable保留原生方向方法；其余行参数树为显式夹具。
        vtable = next(r['r_offset'] - 0x10 + self.bias
                      for r in self.ap_elf.get_section_by_name('.rela.dyn').iter_relocations()
                      if r['r_info_type'] == 1027 and r['r_addend'] == page['update'])
        self.write(PRESENTER, vtable, '<Q')
        self.write(PRESENTER + 0x10, self.table, '<Q')
        self.write(PRESENTER + page['params'], PARAMETERS, '<Q')
        for row in range(page['count']):
            kind = self.read(self.table + row * 52)
            parameter = WIDGET + 0x1d8 if row == page['row'] else 0x60300000 + row * 0x2000
            self.write(PARAMETERS + row * 16, kind)
            self.write(PARAMETERS + row * 16 + 8, parameter, '<Q')
        self.register(page)
        self.write(PRESENTER + (0x268 if page['config'] == 3 else 0x1d8), VIEW, '<Q')
        self.invoke(0x2904d14)
        self.invoke(0x17ffbc0)
        feature = self.invoke(0x17ffd3c)
        self.invoke(page['map_init'])
        self.invoke(page['init'], PRESENTER)
        self.column = self.read(PRESENTER + page['column'])
        require((self.read(self.bias + 0x7effa98), self.read(self.bias + 0x598e7a8),
                 feature, self.column) == (2, 23, 3, 16), '实际A7R5机型初始化或映射变化')
        self.register(page)
        return dict(product=2, internal=23, feature=feature, column=self.column)

    def produce(self, selected=4, mode=2, native_aspect=0):
        self.snapshot(native_aspect)
        self.write(SNAPSHOT + 0x24d8, mode)
        self.write(SNAPSHOT + 0x25c0, 0)
        self.write(self.addr('r5_aspect_selection'), 24 | selected)
        self.invoke('r5_ui_guide_produce', 0, WIDGET + 0x1d8, 0, SNAPSHOT)

    def merge(self, page):
        visible = self.invoke(page['chain'], PRESENTER, page['row'])
        # 第一页执行完整585行合并；第二页原生分成两动态门合并、机型批量拒绝、输出门。
        self.invoke(page['merge'], PRESENTER)
        if page['config'] == 4:
            self.invoke(0x21584a8, PRESENTER)
            if not self.invoke(0x2158510, PRESENTER, page['row']):
                self.invoke(page['setter'], PRESENTER, page['row'], 0)
        return visible


def verify(m):
    positives=[]; negatives=[]; guards=[]; unchanged=0
    for index,page in enumerate(PAGES):
        m.u.mem_write(m.addr('r5_ui_guides'),bytes(12*24))
        identity=m.setup(page,m.layout)
        for selected in range(4,8):
            for exposure in range(12):
                m.write(PRESENTER+page['exposure'],exposure)
                m.produce(selected)
                allowed=m.merge(page)
                m.invoke('r5_ui_guide_update',WIDGET)
                require(allowed==1 and m.u.mem_read(WIDGET+0x41,1)==b'\2',('Eligible R5 model gate did not show native Guide',index,selected,exposure,allowed,m.u.mem_read(WIDGET+0x41,1).hex(),m.read(m.slot+12),m.read(m.addr('r5_aspect_selection')),m.u.mem_read(WIDGET+0x1d8,0x60).hex()))
                children=[m.child(i) for i in range(8)]
                require(all(c['mode']==1 and c['rgba']=='000000ff' for c in children[:2]),'Actual child not opaque black')
                require(all(c['mode']==3 for c in children[2:]),'Unused Guide children visible')
                positives.append(dict(page=index,selected=selected,exposure=exposure,identity=identity))
        for case in ('native','cancel','no_registration','new_generation','stale_epoch','invalid_44',
                     'other_model','invalid_mode','invalid_aspect','movie','output_hidden'):
            m.register(page)
            m.write(PRESENTER+page['column'],m.column);m.write(PRESENTER+page['exposure'],0)
            m.write(PRESENTER+page['output_a'],0);m.write(PRESENTER+page['output_b'],0)
            m.produce()
            if case=='native':m.write(m.addr('r5_aspect_selection'),0x100)
            elif case=='cancel':m.produce(0)
            elif case=='no_registration':m.invoke('r5_ui_guide_unregister',WIDGET)
            elif case=='new_generation':m.register(page)
            elif case=='stale_epoch':m.write(m.addr('r5_aspect_selection'),0x108|4)
            elif case=='invalid_44':m.u.mem_write(WIDGET+0x21c,b'\0')
            elif case=='other_model':m.write(PRESENTER+page['column'],17)
            elif case=='invalid_mode':m.produce(mode=1)
            elif case=='invalid_aspect':m.produce(native_aspect=1)
            elif case=='movie':m.write(PRESENTER+page['exposure'],12)
            elif case=='output_hidden':
                m.write(PRESENTER+page['output_a'],1);m.write(PRESENTER+page['output_b'],1)
            allowed=m.merge(page);m.invoke('r5_ui_guide_update',WIDGET)
            require(allowed==0 and m.u.mem_read(WIDGET+0x41,1)==b'\3',('Native hidden boundary bypassed',index,case))
            negatives.append(dict(page=index,case=case))
        m.register(page);m.write(PRESENTER+page['column'],m.column)
        m.write(PRESENTER+page['exposure'],0);m.write(PRESENTER+page['output_a'],0);m.write(PRESENTER+page['output_b'],0)
        m.produce()
        for boundary in ('invalid_kind','null_parameter_table','wrong_config'):
            original_kind=m.read(PARAMETERS+page['row']*16)
            entry=bytes(m.u.mem_read(m.slot,24));wrong_slot=m.addr('r5_ui_guides')+((1-index)*6+3)*24
            wrong_entry=bytes(m.u.mem_read(wrong_slot,24))
            if boundary=='invalid_kind':m.write(PARAMETERS+page['row']*16,0)
            elif boundary=='null_parameter_table':m.write(PRESENTER+page['params'],0,'<Q')
            else:m.u.mem_write(wrong_slot,entry);m.u.mem_write(m.slot,bytes(24))
            require(m.invoke(page['gate'],PRESENTER,page['row'])==0,('Invalid gate input accepted',boundary))
            m.write(PARAMETERS+page['row']*16,original_kind);m.write(PRESENTER+page['params'],PARAMETERS,'<Q')
            m.u.mem_write(m.slot,entry);m.u.mem_write(wrong_slot,wrong_entry)
            guards.append(dict(page=index,boundary=boundary))
        for row in range(page['count']):
            if row==page['row']:continue
            before=m.invoke('r5_ui_original_guide_model_'+str(index),PRESENTER,row)
            after=m.invoke(page['gate'],PRESENTER,row)
            require(before==after,'Other row model gate changed')
            unchanged+=1
    return dict(positives=positives,negatives=negatives,guards=guards,unchanged_rows=unchanged)

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--module',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    require(not a.output.exists(),'Never overwrite evidence');cases=[]
    try:
        for bias in (0x4000000000,0x6000000000):
            m=ModelGuide(a.candidate,a.module,bias);r=verify(m);r['bias']=hex(bias);cases.append(r);del m
        result=dict(passed=True,cases=cases,AP_sha256=sha(a.candidate.read_bytes()),
                    module_sha256=sha((a.module/'module.json').read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),
                    actual_product_model_initialization=True,actual_four_gate_chains=True,
                    model_column_written_by_test_for_positive=False,actual_public_setters=True,
                    actual_shoot2_bulk_model_rejection=True,actual_native_Guide_child_output=True,
                    fixtures=['OS locks, libc memory/allocation, availability of two display options',
                              'Other widget rows get typed parameter buffers; actual target Guide is natively constructed',
                              'UX registration/engine counter and resource lookup models in replay_ui_support'],
                    limitations=['No complete GUI loop or device LCD, startup, IPC or encoding',
                                 'Second page replays original split dynamic, bulk and output visibility gates'])
    except Exception as e:result=dict(passed=False,error=repr(e),traceback=traceback.format_exc(),cases=cases)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','fixtures','limitations')}))
    require(result['passed'],'Visibility replay failed; retain failure receipt')
if __name__=='__main__':main()
