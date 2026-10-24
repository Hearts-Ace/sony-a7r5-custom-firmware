"""Run linked 4.25 boot/manual SD loader, decoder, persistence and native Fsys wrappers.

Kernel scheduling, clocks and lower Fsys are explicit fixtures. No device I/O.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'vendor/audit-python'), str(ROOT/'analysis/r5_custom_filter423_20261023/ap_design'),str(ROOT/'research/r5_custom_lut/scripts')]
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import arm64_const as R
from custom_filter_config423 import pack, MAXIMUM, SCHEMA, AP_SHA, CP_SHA
MAXIMUM=29552
MANUAL_SCENARIOS=('manual_valid','manual_missing','manual_bad','manual_zero','manual_removed_selected')
def fixture(slots=(1,)):
    return dict(schema=SCHEMA,model='ILCE-7RM5',baseline_ap_sha256=AP_SHA,baseline_cp_sha256=CP_SHA,entries=[dict(number=s,short_name='Cfg'+str(s),full_name='Custom filter '+str(s),cc1_delta=[[-189,-51,-448,-269,389,283,563,285],[0]*8,[0]*8],block13=[[[((i*6+k+g*19+s)%127)-63 for k in range(6)]for i in range(16)]for g in range(3)],gamma_native_129=[min(131071,i*1024)for i in range(129)],grid_5x9x9={'coefficients':[[[[0 for x in range(9)]for y in range(9)]for z in range(5)]for c in range(3)]})for s in slots])
def canonical_pack_fixture(payload):return payload
def canonical_pack(config):return pack(config)

RAM=0x20000000; SP=RAM+0x180000; STOP=RAM+0x1ff000; OBJ=RAM+0x1000
SCHED=0x32000000; CLOCK=SCHED+0x1000; SLEEP=SCHED+0x2000
GPRS=[getattr(R,'UC_ARM64_REG_X'+str(i))for i in range(29)]+[R.UC_ARM64_REG_FP,R.UC_ARM64_REG_LR]
QREGS=[getattr(R,'UC_ARM64_REG_Q'+str(i))for i in range(32)]
HANDLE=0x123456789
ERRNO=RAM+0x1f0000
RENAME=SCHED+0x3000;DUP=SCHED+0x3010
CURRENT_OFFSET=58996
EXTRA_OFFSET=88328
VALID_MOUNT=b'100 20 179:30 / /usr/data/lut rw,nosuid - vfat /dev/nflasha30 rw,uid=0\n'
def wire_set(payload):
    out=bytearray(29332)
    if not payload:return bytes(out)
    mask=struct.unpack_from('<I',payload,24)[0];struct.pack_into('<I',out,0,mask)
    for at in range(128,len(payload),2452):
        slot=struct.unpack_from('<I',payload,at)[0];lo=4+(slot-1)*2444
        out[lo:lo+2444]=payload[at+4:at+2448]
    return bytes(out)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--scenarios',nargs='+')
    p.add_argument('--verify-probe-boundary',action='store_true')
    args=p.parse_args()
    audit=json.loads((args.candidate/'import/module_audit.json').read_text());audit['diagnostics_bytes']=88368
    raw=(args.candidate/'ap/appFw.so').read_bytes()
    elf=ELFFile(io.BytesIO(raw)); results=[]
    scenarios=['valid_1','valid_16','valid_all','chunked','read_budget','missing_file',
        'retry_open','open_never','read_error','overreport','close_error','crc','model',
        'truncated','trailing','oversize','late_invalid_record','missing_clock',
        'missing_sleep','missing_sched','sched_fail','clock_error','clock_backwards',
        'clock_stuck','sleep_fail','not_ready','no_card','second_card','both_cards',
        'invalid_drive','failed_mount','late_events','late_read_timeout','late_close_timeout',
        'no_initial','no_completed','no_media']
    scenarios+=['merge_old','same_file','reload_no_card','reload_missing_sd','reload_invalid_sd','old_invalid','old_io','old_close','pending_stale','pending_only','write_fail','short_write','zero_write','over_write','file_sync','file_close','cleanup_fail','pending_read','pending_mismatch','pending_trailing','pending_close','rename_fail','rename_after_change','dir_sync','dir_close','release_close','dup_fail','missing_rename','missing_dup','mount_absent','mount_late','mount_readonly','mount_wrongid','mount_proc_error']
    scenarios+=['late_load','late_stage','clear_zero','clear_header','clear_corrupt_old']
    scenarios+=list(MANUAL_SCENARIOS)
    if args.scenarios:
        assert set(args.scenarios)<=set(scenarios)
        scenarios=args.scenarios
    for bias in (0,0x40000000):
        u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        for s in elf.iter_segments():
            if s['p_type']!='PT_LOAD':continue
            lo=(s['p_vaddr']+bias)&-4096
            hi=(s['p_vaddr']+bias+s['p_memsz']+4095)&-4096
            if hi>lo:u.mem_map(lo,hi-lo)
            if s['p_filesz']:u.mem_write(s['p_vaddr']+bias,s.data())
        u.mem_map(RAM,0x200000);u.mem_map(SCHED,0x4000)
        sy={k:v+bias for k,v in audit['symbols'].items()}
        diag=sy['r5_stage411_state']; state={}; end=[STOP]
        def ret(value=0):
            lr=u.reg_read(R.UC_ARM64_REG_LR)
            for i in range(1,19):u.reg_write(GPRS[i],0xdead0000+i)
            for reg in QREGS[:8]+QREGS[16:]:u.reg_write(reg,0xdeadbeef11223344)
            u.reg_write(R.UC_ARM64_REG_NZCV,0x50000000)
            u.reg_write(R.UC_ARM64_REG_FPCR,0x800000)
            u.reg_write(R.UC_ARM64_REG_FPSR,0x1f)
            u.reg_write(R.UC_ARM64_REG_X0,value&((1<<64)-1))
            u.reg_write(R.UC_ARM64_REG_PC,lr)
        log_boundaries={sy[n]for n in ('r5_log420_emit','r5_grid420_watch','r5_probe420_log','r5_transfer420_log')}
        def code(cpu,pc,n,_):
            state['instructions']+=1
            state['min_sp']=min(state['min_sp'],cpu.reg_read(R.UC_ARM64_REG_SP))
            if pc==end[0]:cpu.emu_stop();return
            if pc not in log_boundaries and pc not in native_pc and pc not in (RENAME,DUP,SCHED,CLOCK,SLEEP,sy['r5_stage413_transfer_run'],sy['r5_stage411_probe_run'],sy['r5_filter_service'],sy['r5_stage411_dlsym'],0x16da830+bias,0x16da0b0+bias,0x16dc070+bias):return
            av=[cpu.reg_read(r)for r in GPRS[:4]];fault=state['scenario']
            if pc in log_boundaries:
                if pc==sy['r5_log420_emit']:
                    state.setdefault('logs',[]).append(bytes(cpu.mem_read(av[1],48)).split(b'\0')[0].decode())
                ret(0);return
            if pc==sy['r5_filter_service']:
                state['isolated_selection_services']=state.get('isolated_selection_services',0)+1;ret(0);return
            if pc==sy['r5_stage413_transfer_run']:
                assert av[0]==diag+CURRENT_OFFSET
                assert not state['fds'] and state.get('probe_stubbed')
                current=bytes(cpu.mem_read(av[0],29332));mask=struct.unpack_from('<I',current)[0]
                canonical=canonical_pack(fixture(tuple(i+1 for i in range(12) if mask&(1<<i)))) if mask else b''
                assert current==wire_set(canonical),'upload used candidate rather than loaded/published set'
                state['upload_boundary_checked']=True
                # Model the separately tested complete CP data-ACK boundary only.
                # Actual names_publish/bank_ready are executed after this return.
                crc_input=struct.pack('<I',mask)
                for slot in range(12):
                    if mask&(1<<slot):
                        v=current[4+slot*2444:4+(slot+1)*2444]
                        compact=v[:24]+bytes(8)+v[88:1228]+struct.pack('<I',1)+v[1228:2443]+bytes(1)
                        assert len(compact)==2392
                        crc_input+=struct.pack('<I',slot+1)+compact
                transfer=sy['r5_stage413_transfer_state']
                cpu.mem_write(transfer+16,struct.pack('<I',1))
                cpu.mem_write(transfer+32,struct.pack('<QIII',av[0],0x42510001,mask,zlib.crc32(crc_input)))
                state.setdefault('published_masks',[]).append(mask)
                ret(0);return
            if pc==sy['r5_stage411_probe_run']:
                if args.verify_probe_boundary:
                    current=bytes(cpu.mem_read(diag+CURRENT_OFFSET,29332))
                    mask=struct.unpack_from('<I',current)[0]
                    expected_digest=0
                    if mask:
                        canonical=canonical_pack(fixture(tuple(i+1 for i in range(12) if mask&(1<<i))))
                        assert current==wire_set(canonical),'Unexpected current-set oracle'
                        expected_digest=struct.unpack_from('<I',canonical,112)[0]
                    assert av[:2]==[mask,expected_digest],(fault,'probe used wrong set/digest',av[:2],mask,expected_digest)
                    assert not state['fds'],'probe started before directory release'
                state['probe_stubbed']=True;ret(0);return
            if pc==sy['r5_stage411_dlsym']:
                assert av[0]==0
                name=bytes(cpu.mem_read(av[1],64)).split(b'\0')[0].decode()
                table={'sched_setscheduler':SCHED,'clock_gettime':CLOCK,'nanosleep':SLEEP,'renameat':RENAME,'dup':DUP}
                assert name in table
                missing={'missing_rename':'renameat','missing_dup':'dup','missing_sched':'sched_setscheduler','missing_clock':'clock_gettime','missing_sleep':'nanosleep'}
                ret(0 if missing.get(fault)==name else table[name]);return
            if pc in native_pc or pc in (RENAME,DUP):
                internal(cpu,pc);return
            if pc==SCHED:
                assert av[:2]==[0,0] and bytes(cpu.mem_read(av[2],4))==bytes(4)
                state['schedule']+=1;ret(-1 if fault=='sched_fail' else 0);return
            if pc==CLOCK:
                assert av[0]==1
                state['clocks']+=1
                if fault=='clock_error':ret(-1);return
                ms=state['time']
                # Keep moving backwards across each independent budget. A one-off
                # jump before the new SD budget is no longer an SD clock fault.
                if fault=='clock_backwards':ms=max(0,1000-state['clocks'])
                cpu.mem_write(av[1],struct.pack('<qq',ms//1000,(ms%1000)*1000000))
                ret(0);return
            if pc==SLEEP:
                assert struct.unpack('<qq',bytes(cpu.mem_read(av[0],16)))==(0,100000000) and av[1]==0
                state['sleeps']+=1
                if fault!='clock_stuck':state['time']+=100
                if fault=='late_events' and state['sleeps']==3:
                    # Separate callback execution is driven after this pause.
                    state['pause']=True;cpu.emu_stop();return
                ret(-1 if fault=='sleep_fail' else 0);return
            if pc==0x16da830+bias:
                path=bytes(cpu.mem_read(av[0],16)).split(b'\0')[0]
                assert path==(b'Z:/R5NATIVE.BIN' if fault=='second_card' else b'C:/R5NATIVE.BIN')
                assert av[2]==1
                state['opens']+=1
                if fault in ('missing_file','open_never','reload_missing_sd','manual_missing') or (fault=='retry_open' and state['opens']<3):
                    ret(0x80000001);return
                cpu.mem_write(av[1],struct.pack('<Q',HANDLE));ret(0);return
            if pc==0x16da0b0+bias:
                assert av[0]==HANDLE and 0<av[2]<=1024
                state['reads']+=1
                if fault=='read_error':ret(0x80000001);return
                if fault=='overreport':ret(av[2]+1);return
                chunk=1 if fault=='read_budget' else 127 if fault=='chunked' else 1024
                data=state['payload'][state['offset']:state['offset']+min(av[2],chunk)]
                if data:cpu.mem_write(av[1],data)
                state['offset']+=len(data)
                if fault=='late_read_timeout':state['time']+=16000
                ret(len(data));return
            if pc==0x16dc070+bias:
                assert av[0]==HANDLE;state['closes']+=1
                if fault=='late_close_timeout':state['time']+=16000
                ret(0x80000001 if fault=='close_error' else 0);return
        native_pc={sy[n]:n for n in ('r5_ap_posix_open','r5_ap_posix_openat','r5_ap_posix_read','r5_ap_posix_write','r5_ap_posix_close','r5_ap_posix_fsync','r5_ap_posix_unlinkat','r5_ap_posix_errno')}
        newfaults={'old_invalid','old_io','old_close','write_fail','short_write','zero_write','over_write','file_sync','file_close','cleanup_fail','pending_read','pending_mismatch','pending_trailing','pending_close','rename_fail','rename_after_change','dir_sync','dir_close','release_close','dup_fail','missing_rename','missing_dup','mount_absent','mount_late','mount_readonly','mount_wrongid','mount_proc_error','late_load','late_stage'}
        def string(at):return bytes(u.mem_read(at,128)).split(b'\0')[0]
        def internal(cpu,pc):
            if pc not in log_boundaries and pc not in native_pc and pc not in (RENAME,DUP,SCHED,CLOCK,SLEEP,sy['r5_stage413_transfer_run'],sy['r5_stage411_probe_run'],sy['r5_filter_service'],sy['r5_stage411_dlsym'],0x16da830+bias,0x16da0b0+bias,0x16dc070+bias):return
            av=[cpu.reg_read(r)for r in GPRS[:4]];fault=state['scenario'];files=state['files'];fds=state['fds'];label=native_pc.get(pc,'rename'if pc==RENAME else 'dup')
            state['internal_calls'].append((label,*av[:1]))
            def fail():cpu.mem_write(ERRNO,struct.pack('<i',5));ret(-1)
            def opened(name,data=None):
                fd=state['serial'];state['serial']+=1;fds[fd]=dict(name=name,data=data,offset=0);ret(fd)
            if label=='r5_ap_posix_errno':ret(ERRNO)
            elif label=='r5_ap_posix_open':
                path=string(av[0]);flags=av[1]
                if path==b'/usr/data/lut':
                    assert flags==0xc000;state['mount_open']+=1
                    if fault=='mount_absent'or fault=='mount_late'and state['mount_open']<3:fail()
                    else:assert 7 not in fds;fds[7]=dict(name='directory');ret(7)
                elif path==b'/proc/self/fdinfo/7':
                    assert flags==0x8000;opened('fdinfo',b'mnt_id:\t101\n'if fault=='mount_wrongid'else b'mnt_id:\t100\n')
                else:
                    assert path==b'/proc/self/mountinfo'and flags==0x8000
                    if fault=='mount_proc_error':fail()
                    else:opened('mountinfo',VALID_MOUNT.replace(b'lut rw,',b'lut ro,')if fault=='mount_readonly'else VALID_MOUNT)
            elif label=='r5_ap_posix_openat':
                assert av[0]==7 and 7 in fds;name=string(av[1]);assert name in (b'R5NATIVE.BIN',b'R5NATIVE.NEW',b'R5FILTER.BIN')
                if av[2]==0x80c1:
                    assert name==b'R5NATIVE.NEW'and av[3]==0o600
                    if name in files:cpu.mem_write(ERRNO,struct.pack('<i',17));ret(-1)
                    else:files[name]=b'';opened(name)
                else:
                    assert av[2:4]==[0x8000,0]
                    if name==b'R5NATIVE.BIN'and fault=='old_io':fail()
                    elif name not in files:cpu.mem_write(ERRNO,struct.pack('<i',2));ret(-1)
                    else:opened(name)
            elif label=='r5_ap_posix_read':
                h=fds[av[0]];name=h['name'];assert 0<av[2]<=1024
                if name==b'R5NATIVE.NEW'and fault=='pending_read':fail();return
                data=h['data']if h.get('data')is not None else files[name]
                if name==b'R5NATIVE.NEW':
                    if fault=='pending_mismatch':data=bytes([data[0]^1])+data[1:]
                    if fault=='pending_trailing':data+=b'X'
                part=data[h['offset']:h['offset']+min(av[2],127)];h['offset']+=len(part)
                if part:cpu.mem_write(av[1],part)
                ret(len(part))
            elif label=='r5_ap_posix_write':
                assert fds[av[0]]['name']==b'R5NATIVE.NEW';count=av[2];assert 0<count<=MAXIMUM
                state['internal_calls'].append(('write',count))
                if fault in ('write_fail','cleanup_fail'):fail()
                elif fault=='zero_write':ret(0)
                elif fault=='over_write':ret(count+1)
                else:
                    count=min(count,7 if fault=='short_write'else 4096);files[b'R5NATIVE.NEW']+=bytes(cpu.mem_read(av[1],count));ret(count)
            elif label=='r5_ap_posix_close':
                name=fds.pop(av[0])['name']
                if name==b'R5NATIVE.BIN'and fault=='late_load':state['time']+=16000
                if name==b'R5NATIVE.NEW'and fault=='late_stage':state['time']+=16000
                fail()if (name==b'R5NATIVE.BIN'and fault=='old_close'or name==b'R5NATIVE.NEW'and fault in ('file_close','pending_close')or name=='directory_dup'and fault=='dir_close'or name=='directory'and fault=='release_close')else ret(0)
            elif label=='r5_ap_posix_fsync':
                name=fds[av[0]]['name'];fail()if (name==b'R5NATIVE.NEW'and fault=='file_sync'or name=='directory_dup'and fault=='dir_sync')else ret(0)
            elif label=='r5_ap_posix_unlinkat':
                assert av[0]==7 and string(av[1])==b'R5NATIVE.NEW'and av[2]==0
                if fault=='cleanup_fail':fail()
                else:files.pop(b'R5NATIVE.NEW',None);ret(0)
            elif label=='rename':
                assert av[0]==av[2]==7 and string(av[1])==b'R5NATIVE.NEW'and string(av[3])==b'R5NATIVE.BIN'
                if fault=='rename_fail':fail()
                else:
                    files[b'R5NATIVE.BIN']=files.pop(b'R5NATIVE.NEW');fail()if fault=='rename_after_change'else ret(0)
            else:
                assert label=='dup'and av[0]==7
                if fault=='dup_fail':fail()
                else:opened('directory_dup')
        def write(cpu,access,address,size,value,_):
            assert (RAM+0x100000<=address<address+size<=SP or
                    audit['rw']+bias<=address<address+size<=audit['rw']+bias+audit['bss_bytes']), (hex(address),size)
        u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
        def invoke(pc,arg=0,event=None):
            end[0]=STOP if event is None else pc+4
            for i,r in enumerate(GPRS):u.reg_write(r,0x1234567800000000+i)
            for i,r in enumerate(QREGS):u.reg_write(r,0x1234567890abcdef1234000000000000+i)
            entry_sp=SP if event is None else SP-0x20000
            u.reg_write(R.UC_ARM64_REG_SP,entry_sp);u.reg_write(R.UC_ARM64_REG_LR,STOP)
            u.reg_write(R.UC_ARM64_REG_NZCV,0xa0000000)
            u.reg_write(R.UC_ARM64_REG_FPCR,0x400000);u.reg_write(R.UC_ARM64_REG_FPSR,0x8000000)
            if event is None:u.reg_write(R.UC_ARM64_REG_X0,arg)
            else:
                u.reg_write(R.UC_ARM64_REG_X19,OBJ)
                if event[0]=='initial':
                    u.reg_write(R.UC_ARM64_REG_X21,event[1]);u.reg_write(R.UC_ARM64_REG_X22,event[2])
                elif event[0]=='completed':u.reg_write(R.UC_ARM64_REG_X20,event[1])
                else:
                    frame=OBJ+0x8000;u.reg_write(R.UC_ARM64_REG_FP,frame)
                    u.reg_write(R.UC_ARM64_REG_X28,OBJ+0x100)
                    u.reg_write(R.UC_ARM64_REG_X22,0x100)
                    u.mem_write(OBJ+0x11c,struct.pack('<I',event[1]))
                    u.mem_write(frame+0x13d0,struct.pack('<IB',event[2],event[3]))
            before=[u.reg_read(r)for r in GPRS];qs=[u.reg_read(r)for r in QREGS]
            start=pc
            while True:
                state['pause']=False
                try:u.emu_start(start,end[0],count=10000000)
                except Exception as error:
                    raise RuntimeError((state['scenario'],hex(u.reg_read(R.UC_ARM64_REG_PC)),hex(u.reg_read(R.UC_ARM64_REG_LR)),{k:v for k,v in state.items()if k!='payload'})) from error
                if not state['pause']:break
                parent=u.context_save();saved=end[0]
                seed_ready();u.context_restore(parent);end[0]=saved;ret(0)
                start=u.reg_read(R.UC_ARM64_REG_PC)
            assert u.reg_read(R.UC_ARM64_REG_PC)==end[0], (state['scenario'],hex(u.reg_read(R.UC_ARM64_REG_PC)))
            assert u.reg_read(R.UC_ARM64_REG_SP)==entry_sp
            if event is not None:
                wanted=OBJ+0x430 if event[0]!='media' else OBJ+0x8100
                assert u.reg_read(R.UC_ARM64_REG_X0)==wanted
                assert [u.reg_read(r)for r in GPRS[1:]]==before[1:]
                assert [u.reg_read(r)for r in QREGS]==qs
                assert u.reg_read(R.UC_ARM64_REG_NZCV)==0xa0000000
                assert u.reg_read(R.UC_ARM64_REG_FPCR)==0x400000 and u.reg_read(R.UC_ARM64_REG_FPSR)==0x8000000
            else:
                assert [u.reg_read(r)for r in GPRS[19:30]]==before[19:30]
        sites={'initial':0x34dae68+bias,'completed':0x34e5140+bias,'media':0x33c3cd4+bias}
        def getter_address(name):
            pc=sy[name];a,b=struct.unpack('<II',bytes(u.mem_read(pc,8)))
            assert a&0x9f000000==0x90000000 and b&0xffc00000==0x91000000
            rd=a&31;assert b&31==rd and (b>>5)&31==rd
            delta=((a>>29)&3)|(((a>>5)&0x7ffff)<<2)
            if delta&(1<<20):delta-=1<<21
            return (pc&-4096)+(delta<<12)+((b>>10)&0xfff)
        def event(name,*values):invoke(sites[name],event=(name,*values))
        def invoke_value(pc,arg=0):
            invoke(pc,arg);return u.reg_read(R.UC_ARM64_REG_X0)&0xffffffff
        def seed_ready():
            fault=state['scenario']
            if fault=='second_card':statuses=(0,1)
            elif fault=='both_cards':statuses=(1,1)
            elif fault in ('no_card','reload_no_card','pending_only'):statuses=(0,0)
            else:statuses=(1,0)
            if fault!='no_initial':event('initial',*statuses)
            for slot,status in enumerate(statuses):
                if status:
                    if fault!='no_media':event('media',slot,1 if fault=='failed_mount' else 0,
                        ord('z') if fault=='invalid_drive' else ord('Z') if slot else ord('C'))
                    if fault!='no_completed':event('completed',slot)
        for scenario in scenarios:
            slots=(1,)if scenario=='valid_1'else tuple(range(1,13))if scenario=='valid_all'else(1,12)
            payload=canonical_pack(fixture(slots));expected_mask=sum(1<<(s-1)for s in slots)
            if scenario in ('crc','model','late_invalid_record'):
                data=bytearray(payload)
                if scenario=='crc':data[-1]^=128
                elif scenario=='model':data[32]^=1
                else:struct.pack_into('<I',data,128+2452+716+4,0x7fffffff)
                if scenario!='crc':struct.pack_into('<I',data,112,0);struct.pack_into('<I',data,112,zlib.crc32(data)&0xffffffff)
                payload=bytes(data)
            if scenario.startswith('clear_'):
                payload=b'' if scenario!='clear_header' else pack(fixture(()))
                if payload:
                    data=bytearray(payload);struct.pack_into('<II',data,20,0,0);struct.pack_into('<I',data,112,0);struct.pack_into('<I',data,112,zlib.crc32(data));payload=bytes(data)
            if scenario=='reload_invalid_sd':payload=payload[:-1]
            if scenario=='truncated':payload=payload[:-1]
            if scenario=='trailing':payload+=b'\0'
            if scenario=='oversize':payload=canonical_pack(fixture(tuple(range(1,13))))+b'\0'
            state.clear();state.update(scenario='valid_16' if scenario in MANUAL_SCENARIOS else scenario,payload=payload,offset=0,instructions=0,
                min_sp=SP,schedule=0,clocks=0,sleeps=0,time=1000,opens=0,reads=0,closes=0,pause=False)
            active=canonical_pack(fixture((2,5)))if scenario=='merge_old'else canonical_pack(fixture((1,12)))if scenario=='same_file'else canonical_pack(fixture((12,)))if scenario.startswith('reload_')or scenario in newfaults else None
            if scenario.startswith('clear_'):active=canonical_pack(fixture((2,5)))
            if scenario in ('old_invalid','clear_corrupt_old'):active=active[:-1]
            files={}if active is None else {b'R5NATIVE.BIN':active}
            if scenario in ('pending_stale','pending_only'):files[b'R5NATIVE.NEW']=b'stale-preserved'
            oldfiles=dict(files)
            state.update(files=files,fds={},serial=10,internal_calls=[],mount_open=0)
            u.mem_write(audit['rw']+bias,bytes(audit['bss_bytes']));invoke(sy['r5_session_cold']);invoke(sy['r5_session_prepare'])
            if scenario not in ('late_events','not_ready','clock_stuck','sleep_fail'):seed_ready()
            invoke(sy['r5_stage411_child'],diag)
            fields=struct.unpack('<10I',bytes(u.mem_read(diag+40,40)))
            result,attempts,selected,drive,used,reads,mask,terminal,closed,native=fields
            valid=scenario in MANUAL_SCENARIOS or scenario in ('valid_1','valid_16','valid_all','chunked','retry_open','second_card','both_cards','late_events','merge_old','same_file','short_write','mount_late','old_invalid','old_io','old_close','pending_stale','late_load','clear_zero','clear_header','clear_corrupt_old')
            absent=scenario in ('no_card','invalid_drive','failed_mount','reload_no_card','pending_only')
            invalid=scenario in ('crc','model','truncated','trailing','oversize','late_invalid_record','reload_invalid_sd')
            commit=scenario in ('write_fail','zero_write','over_write','file_sync','file_close','cleanup_fail','pending_read','pending_mismatch','pending_trailing','pending_close','rename_fail','rename_after_change','dir_sync','dir_close','dup_fail','late_stage')
            io_fault=scenario in ('release_close','missing_rename','missing_dup','mount_absent','mount_readonly','mount_wrongid','mount_proc_error')
            wanted=5 if commit else 3 if io_fault else 0 if valid else 1 if absent else 2 if invalid else 3
            assert result==wanted,(scenario,result,wanted,state['internal_calls'][-8:])
            assert terminal==1 and reads<=64 and state['opens']<=3 and state['closes']<=1 and attempts<=151
            assert state['closes']==(1 if state['reads'] else 0)
            parsed=bytes(u.mem_read(diag+108,29332));current=bytes(u.mem_read(diag+CURRENT_OFFSET,29332))
            extra=struct.unpack('<5i4I',bytes(u.mem_read(diag+EXTRA_OFFSET,36)))
            directory,load,stage,publish,release,loaded_mask,saved_mask,unchanged,mount_attempts=extra
            assert not state['fds'],(scenario,state['fds'])
            expected=bytearray(wire_set(payload))if valid or commit or scenario=='release_close' else bytearray(29332)
            if valid or commit or scenario=='release_close':
                assert parsed==expected,(scenario,'decoded/merged set mismatch')
            elif not io_fault:assert parsed==bytes(29332),(scenario,'invalid changed SD parsed state')
            saved=scenario in MANUAL_SCENARIOS or scenario in ('valid_1','valid_16','valid_all','chunked','retry_open','second_card','both_cards','late_events','merge_old','same_file','short_write','mount_late','release_close','dir_close','old_invalid','old_io','old_close','pending_stale','late_load','clear_zero','clear_header','clear_corrupt_old')
            changed=saved or scenario in ('rename_after_change','dir_sync')
            if changed:
                assert wire_set(files[b'R5NATIVE.BIN'])==expected,(scenario,'published wire differs')
            else:assert files.get(b'R5NATIVE.BIN')==oldfiles.get(b'R5NATIVE.BIN'),(scenario,'active unexpectedly modified')
            if saved:assert current==expected and saved_mask==struct.unpack_from('<I',expected)[0]
            elif scenario in ('rename_after_change','dir_sync'):
                # Publication was not acknowledged: preserve the preloaded
                # generation even if rename took effect on disk. A later
                # validated reload reconciles the file; do not claim success.
                assert current==wire_set(active)
            elif active is not None and scenario not in ('old_invalid','old_io','old_close','missing_rename','missing_dup','mount_absent','mount_readonly','mount_wrongid','mount_proc_error'):
                assert current==wire_set(active),(scenario,'loaded current lost')
            if scenario=='same_file':assert unchanged==0 and any(t[0]=='write'for t in state['internal_calls'])
            if scenario=='pending_only':assert files[b'R5NATIVE.NEW']==b'stale-preserved'
            if scenario=='late_stage':assert publish==-99 and files[b'R5NATIVE.NEW']==payload and saved_mask==0
            if scenario=='late_load':assert any(t[0]=='write'for t in state['internal_calls'])
            if scenario=='cleanup_fail':assert not any(t[0]=='write'for t in state['internal_calls'])
            if scenario in ('rename_after_change','dir_sync'):assert publish==4 and saved_mask==0
            # Fresh BSS / no-card second boot proves production child reloads bytes,
            # rather than relying on the previous worker's RAM snapshot.
            if saved or scenario in ('rename_after_change','dir_sync'):
                reload_expected=wire_set(files[b'R5NATIVE.BIN'])
                snapshot=dict(files);state['scenario']='reload_no_card';state['fds']={};state['serial']=10
                state['time']=1000;state['clocks']=0;state['opens']=state['reads']=state['closes']=0
                u.mem_write(audit['rw']+bias,bytes(audit['bss_bytes']));invoke(sy['r5_session_cold']);invoke(sy['r5_session_prepare']);seed_ready();invoke(sy['r5_stage411_child'],diag)
                assert bytes(u.mem_read(diag+CURRENT_OFFSET,29332))==reload_expected and state['files']==snapshot and not state['fds']
                state['scenario']=scenario
            manual_result=None
            if scenario in MANUAL_SCENARIOS:
                # Reset the RAM view only during a normal boot above. This call
                # retains bank/name/session/event state and exercises the actual
                # production manual wrapper and its entire child loader.
                state['scenario']=scenario;state['offset']=0
                state['opens']=state['reads']=state['closes']=0
                state['time']=1000;state['clocks']=0
                seed_ready() # The preceding no-card restart is a distinct boot test.
                before_files=dict(files)
                before_masks=list(state.get('published_masks',[]))
                before_mask=invoke_value(sy['r5_filter_available_mask'])
                # Fixture an already applied filter 12; its BSS location is
                # derived from the actual linked getter and read back through it.
                u.mem_write(getter_address('r5_filter_selected'),struct.pack('<I',12))
                assert invoke_value(sy['r5_filter_selected'])==12
                assert invoke_value(sy['r5_filter_request'],12)==0
                replacement=canonical_pack(fixture((1,))) if scenario=='manual_removed_selected' else canonical_pack(fixture((2,5)))
                if scenario=='manual_bad':replacement=replacement[:-1]
                if scenario=='manual_zero':replacement=b''
                state['payload']=replacement
                manual_result=invoke_value(sy['r5_stage425_reload'])
                valid_manual=scenario not in ('manual_missing','manual_bad')
                assert manual_result==(0 if valid_manual else 0xffffffff), (scenario,hex(manual_result),struct.unpack('<10I',bytes(u.mem_read(diag+40,40))),state.get('published_masks'))
                assert not state['fds'] and state['closes']==(1 if state['reads'] else 0)
                actual=bytes(u.mem_read(diag+CURRENT_OFFSET,29332))
                if valid_manual:
                    expected_new=wire_set(replacement)
                    assert actual==expected_new and wire_set(files[b'R5NATIVE.BIN'])==expected_new
                    new_mask=struct.unpack_from('<I',expected_new)[0]
                    assert invoke_value(sy['r5_filter_available_mask'])==new_mask
                    assert state['published_masks']==before_masks+[new_mask]
                    if scenario=='manual_removed_selected':
                        assert invoke_value(sy['r5_filter_request'],12)==0xffffffff
                        assert invoke_value(sy['r5_filter_request'],0)==0xffffffff # prior command stays pending
                else:
                    assert files==before_files and state['published_masks']==before_masks
                    assert invoke_value(sy['r5_filter_available_mask'])==before_mask
                reconciled=struct.unpack('<I',bytes(u.mem_read(getter_address('r5_filter_pending'),4)))[0]
                assert reconciled==(0 if valid_manual else 12), (scenario,reconciled)
                state['manual_evidence']={'returned':manual_result,'success':valid_manual,
                    'applied_selection_before_fixture':12,'desired_selection_after_reload':reconciled,
                    'actual_current_mask':struct.unpack_from('<I',actual)[0],
                    'published_mask':invoke_value(sy['r5_filter_available_mask']),
                    'open_calls':state['opens'],'read_calls':state['reads'],'close_calls':state['closes']}
            print(hex(bias),scenario,'PASS',flush=True)
            results.append(dict(bias=hex(bias),scenario=scenario,result=result,parsed_mask=mask,manual=state.get('manual_evidence'),
                fresh_BSS_restart_verified=saved,internal_diagnostics=extra,open_calls=state['opens'],read_calls=state['reads'],close_calls=state['closes'],
                poll_attempts=attempts,instructions=state['instructions'],observed_stack_span_with_isolated_events=SP-state['min_sp']))
    report=dict(schema='r5-411-readonly-sd-worker-replay/1',passed=True,camera_io=False,
        AP_sha256=hashlib.sha256(raw).hexdigest(),candidate_sha256=hashlib.sha256(raw).hexdigest(),cases=len(results),results=results,
        manual_reload_production_wrapper_executed=any(r['manual'] is not None for r in results),manual_scenarios=[s for s in MANUAL_SCENARIOS if s in scenarios],
        current_set_digest_boundary_checked=args.verify_probe_boundary,
        upload_uses_current_after_directory_release=True,
        original_Fsys_wrappers_executed=['0x3691104','0x3691138','0x3691124','0x3690da8'],
        full_decoded_set_compared_to_independent_wire_oracle=True,
        invalid_SD_preserves_internal=True,internal_file_transactions=True,fresh_BSS_no_card_restart_reloaded=any(x["fresh_BSS_restart_verified"]for x in results),
        limitations=['Lower Fsys, clock, sleep and sched_setscheduler are fixtures; CP probe and whole-bank transfer ACK are isolated boundaries, separately verified. Native decoder, storage transactions, manual wrapper, name/mask publication execute.',
            'Nested selection service is isolated here; selection/refresh completion is verified by the separate worker replay. This SD replay does not prove physical ISP application.',
            'No kernel/card/TLS/WBI, actual callback coverage, startup or thread-RAM observation.',
            'Bounded loops do not impose a timeout on synchronous native calls.'])
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k not in ('results',)}))

if __name__=='__main__':main()
