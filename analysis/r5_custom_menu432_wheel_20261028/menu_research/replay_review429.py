"""427 independent reserved-pool/manager/factory/RW review. No device I/O."""
from pathlib import Path
import hashlib,json,io
from replay_lifecycle429 import LifecycleVM,RAM,CAND,HERE,X,R
from elftools.elf.elffile import ELFFile
rows=[]
for bias in [0,0x40000000]:
 vm=LifecycleVM(bias);vm.oom=1
 before=bytes(vm.u.mem_read(vm.parent,0x4000));c,p=vm.open()
 assert c and p and bytes(vm.u.mem_read(vm.parent,0x4000))==before
 assert not vm.allocations and not vm.frees
 rw=json.loads((CAND/'import/module_audit.json').read_text());lo=rw['rw']+bias;hi=lo+rw['bss_bytes']
 assert lo<=c<c+0x308<=hi and lo<=p<p+0x5a10<=hi and (c+0x308<=p or p+0x5a10<=c)
 assert c!=0x7546208+bias and p!=vm.parent
 d1c=vm.q(vm.q(c));d1p=vm.q(vm.q(p));d0c=vm.q(vm.q(c)+8);d0p=vm.q(vm.q(p)+8);counts=dict(vm.native_entries)
 for a,o in [(d1p,p),(d1c,c),(d0p,p),(d0c,c),(d1p,p),(d1c,c)]:vm.call(a,o)
 assert vm.native_entries[0x1cbfb80]-counts.get(0x1cbfb80,0)==1 and vm.native_entries[0x22083ec]-counts.get(0x22083ec,0)==1
 assert not vm.allocations and not vm.frees
 c2,p2=vm.open();assert(c2,p2)==(c,p);vm.cleanup()
 # Execute original native scene-manager factory wrappers. Product/UI services
 # remain explicit fixtures, but the factory lookup, argument remap and returned
 # custom object dereference are real native code.
 record=RAM+0x350000;vm.w32(record,0xd9)
 vm.w64(vm.manager+0x30,vm.context);vm.w64(vm.manager+0x38,vm.context)
 vm.custom[0x182ae14+bias]=lambda a:vm.ret(vm.view)
 vm.custom[0x36936bc+bias]=lambda a:vm.ret(0)
 vm.custom[0x36936fc+bias]=lambda a:vm.ret(0)
 cm=vm.native(0x1e979e4,vm.manager,0xd9,0)
 assert cm==c
 # Manager's exact factory-return instructions 1ec54fc..1ec550c. Stop only
 # after dereference and actual controller VT+20 callback complete.
 stop=0x1ec5510+bias
 vm.custom[stop]=lambda a:vm.u.emu_stop()
 vm.u.reg_write(X[0],cm);vm.u.reg_write(X[23],vm.manager+0x3b0);vm.u.reg_write(X[28],record)
 vm.u.reg_write(R.UC_ARM64_REG_SP,RAM+0x3f0000)
 vm.u.emu_start(0x1ec54fc+bias,stop,count=100000)
 assert vm.u.reg_read(R.UC_ARM64_REG_PC)==stop and vm.q(vm.manager+0x3b0)==c
 pm=vm.native(0x1e97948,vm.manager,0xd9,0);assert pm==p
 assert not vm.allocations and not vm.frees
 assert bytes(vm.u.mem_read(vm.parent,0x4000))==before
 vm.controller=cm;vm.presenter=pm;vm.cleanup()
 rows.append(dict(bias=hex(bias),mode='reserved_pool',OSAL_failure_injected=True,factories_return_nonzero_reserved_objects=True,controller=hex(c),presenter=hex(p),objects_inside_custom_RW_and_nonoverlapping=True,parent_bytes_preserved=True,native_controller_factory_wrapper_executed=True,native_manager_factory_return_dereference_executed=True,native_presenter_factory_wrapper_executed=True,native_constructor_and_destructor_executed=True,no_OSAL_allocation_or_free=True,destructor_variants_cleanup_once=True,reentry_reuses_reserved_objects=True))
 vm=LifecycleVM(bias);vm.w32(vm.menu_pid,0x14c)
 assert vm.call(vm.sy['r5_filter_controller425'],0,vm.manager,vm.context,0,0,0)==0x123456
 assert vm.call(vm.sy['r5_filter_presenter425'],0,vm.view,vm.context,0,0xd9,0)==0x123456
 assert not vm.allocations
 rows.append(dict(bias=hex(bias),mode='original_scene',original_factories_delegated_without_private_allocation=True,limits='Original factory targets in this case are explicit tracing fixtures; unchanged original factory path is separately inspected.'))
raw=(CAND/'ap/appFw.so').read_bytes();elf=ELFFile(io.BytesIO(raw));loads=[s for s in elf.iter_segments()if s['p_type']=='PT_LOAD']
for x,y in zip(loads,loads[1:]):assert (x['p_vaddr']+x['p_memsz']+65535)&-65536<=y['p_vaddr']
last=loads[-1];assert last['p_vaddr']==0x8ea0000 and last['p_filesz']==0 and last['p_memsz']<=196608
assert last['p_vaddr']+last['p_memsz']<0x9000000
report=dict(passed=True,AP_sha256=hashlib.sha256(raw).hexdigest(),cases=rows,RW_mapping=dict(base=hex(last['p_vaddr']),memsz=last['p_memsz'],end=hex(last['p_vaddr']+last['p_memsz']),filesz=last['p_filesz'],no_PT_LOAD_overlap=True,below_page_anchor=True,project_cap=196608),limits=['Static pool removes OSAL allocation failure from private factory construction. View/widget graphics arena allocation and actual physical RAM/loader acceptance remain separate checks.','Native1e979e4/1e97948 factory lookup/remap and exact manager1ec54fc..1ec550c return dereference/callback execute; product/UI view resolver, tracing mutex calls and context field getter remain fixtures. This is a bounded native chain, not the entire event scheduler.','Parent preservation compares the bounded captured parent fixture bytes; original factory pool sharing is established statically, not from a physical camera heap capture.','ELF final RW PT_LOAD p_memsz/geometry is checked; no camera kernel/loader mapping is executed.131072 was only a project cap, updated to196608 after checking no following PT_LOAD or anchor overlap.','All graphics/backend/context/model fixtures are inherited and documented in native_lifecycle429_verified.json.'])
(HERE/'review429_verified.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PASS review',len(rows),report['AP_sha256'])
