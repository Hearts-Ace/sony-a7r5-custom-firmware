"""Compile/link owned synchronous color consumers; no device or DAT.

Emits a patch recipe plus an independent CP address-space replay image. The
new RX page's loader/MMU/BSS integration is a separate mandatory build step.
"""
from pathlib import Path
import argparse, hashlib, json, struct, subprocess, sys
ROOT=Path(__file__).resolve().parents[3]
FW=ROOT/'research/r5_custom_lut/firmware'
sys.path[:0]=[str(ROOT/'vendor/audit-python'),str(ROOT/'tools')]
from link_thumb_regions import link
from audit_cp_reclaimed_rx import audit as audit_reclaimed
from build_r5_m4strict_cp import bw
RX=0x1a3b000; TRAMP=0x1196c00; BASE=0x108000
INPUT=ROOT/'research/r5_custom_lut/evidence/sd405_native_transport_v1/cp405-transfer-gate.NONINSTALLABLE.bin'
SHA='41bffc6bd0121eb9948f916c0496c35a6d355d5bebc928f639e32c5d8568f954'
def sha(b):return hashlib.sha256(b).hexdigest()
def branch(at,to,link=False):
    b=bytearray(bw(at,to)); h=struct.unpack_from('<H',b,2)[0]
    if link:struct.pack_into('<H',b,2,h|0x4000)
    return bytes(b)
def build(out,include_gamma=False,shared_gamma=False,isp_carrier=False,file_padding_code=False,preview=False):
    if shared_gamma and not include_gamma: raise ValueError('Shared Gamma requires Gamma consumers')
    if isp_carrier and not shared_gamma: raise ValueError('ISP identity needs audited shared-Gamma RX capacity')
    if preview and (not shared_gamma or isp_carrier): raise ValueError('Preview needs shared Gamma and replaces the rejected ISP carrier')
    out.mkdir(parents=True,exist_ok=False)
    objects=[];commands=[]
    sources=['r5_color_consumer.c','r5_color_q_carrier.c','r5_color_shadow.c','r5_color_copy.c','r5_color_q_gateways.S','r5_gamma_qualification.c','r5_gamma_identity.c','r5_color_seal_pending.S']
    if include_gamma:sources+=['r5_gamma_request.c','r5_gamma_request_shims.S']
    if shared_gamma:sources+=['r5_gamma_shared.S']
    if isp_carrier:sources+=['r5_isp_carrier.c','r5_isp_carrier.S','r5_isp_gateways.S']
    if preview:sources+=['r5_preview.c','r5_preview_stage.S','r5_preview_gateways.S','r5_preview_flip.S','r5_aa_snapshot.c','r5_aa_snapshot.S']
    # Compile from one captured source set, including headers. A concurrent
    # edit must never silently relabel an already built object as new source.
    compile_source=out/'compile_source';compile_source.mkdir()
    inputs=sources+[p.name for p in sorted(FW.glob('*.h'))]
    input_sha={name:sha((FW/name).read_bytes()) for name in inputs}
    for name in inputs:
        data=(FW/name).read_bytes()
        assert sha(data)==input_sha[name],('Source changed during capture',name)
        (compile_source/name).write_bytes(data)
    for source in sources:
        obj=out/(Path(source).stem+('_asm' if source in ('r5_isp_carrier.S','r5_aa_snapshot.S') else '')+'.o')
        command=['clang','--target=arm-none-eabi','-mthumb','-march=armv7-a','-mfloat-abi=soft',
            '-mhwdiv=thumb','-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector','-ffunction-sections',
            '-fstack-usage','-Wall','-Wextra','-Werror','-I',str(compile_source),'-c',str(compile_source/source),'-o',str(obj)]
        if preview:command[1:1]=['-DR5_PREVIEW','-DR5_PRODUCTION_CORE']
        subprocess.run(command,check=True);objects.append(obj);commands.append(command)
    if include_gamma and not shared_gamma:
        from build_gamma_owned_consumers import build as build_owned
        build_owned(out/'owned_native');objects.append(out/'owned_native/r5_gamma_owned.o')
    reclaim=audit_reclaimed(out/'reclaimed_rx_audit.json',seal_replaced=True)
    regions=[(RX,4096),(0x1196040,404),(0x11961dc,328),(0x1196b34,1228)]
    padding_audit=None
    if file_padding_code:
        from audit_cp_file_padding import audit as audit_padding
        padding_audit=audit_padding(out/'file_padding_audit')
        assert padding_audit['input_sha256']==SHA and padding_audit['start']=='0x1195080' and padding_audit['end_exclusive']=='0x1196000'
        assert padding_audit['bytes']==3968 and padding_audit['zero_span_in_stock_and_current']
        regions.append((0x1195080,3968))
    required=['r5_color_q_dispatch_gateway','r5_color_capture_copy','r5_color_source_copy','r5_color_source_complete','r5_color_snapshot_dispatch','r5_color_cc1','r5_color_block13','r5_gamma_owner','r5_gamma_q_initialize','r5_gamma_pool_ready']
    if include_gamma: required+=['r5_gamma_q_rebuild_alternate','r5_gamma_q_model_saved','r5_gamma_q_saved_rebuild']
    if shared_gamma: required+=['r5_gamma_shared']
    isp_names=['r5_isp_'+n for n in ('owner','stage_shim','build','black_set','baseband_set','gamma_set','prepare')]
    new_required=['r5_color_q_dispatch']
    if isp_carrier:
        required += [n+'_gateway' for n in isp_names]
        new_required += isp_names+['r5_isp_stage_before','r5_isp_stage_after','r5_isp_identity','r5_isp_custom_eligible']
    preview_names=['r5_preview_'+n for n in ('owner','stage_shim','build','gamma_set','publish','complete')]
    if preview:
        required += [n+'_gateway' for n in preview_names]+['r5_preview_flip_gateway']
    linked=link(objects,regions,branch,old_rx_required=required,new_rx_required=new_required);symbols=linked['symbols'];rels=linked['relocations']
    literal=symbols['r5_color_q_dispatch_destination'];dest=symbols['r5_color_q_dispatch']
    holder=[r for r in linked['regions'] if int(r['start'],16)<=literal<int(r['start'],16)+r['used']]
    assert len(holder)==1 and dest&1
    r=holder[0];raw=bytearray(r['data']);off=literal-int(r['start'],16)
    assert raw[off:off+4]==bytes(4)
    struct.pack_into('<I',raw,off,dest);r['data']=bytes(raw)
    if isp_carrier or preview:
        for name in (isp_names if isp_carrier else preview_names):
            literal=symbols[name+'_destination'];dest=symbols[name]
            holder=[r for r in linked['regions'] if int(r['start'],16)<=literal<int(r['start'],16)+r['used']]
            assert len(holder)==1 and dest&1
            r=holder[0];raw=bytearray(r['data']);off=literal-int(r['start'],16)
            assert raw[off:off+4]==bytes(4)
            struct.pack_into('<I',raw,off,dest);r['data']=bytes(raw)
    gamma_shared=None
    if shared_gamma:
        # Linker allocation changes the consume return PC. Bind the one actual
        # BL relocation, never an experiment address or guessed prolog size.
        calls=[r for r in rels if r['symbol']=='r5_gamma_native_wrapper_owned' and r['kind']==10]
        assert len(calls)==1+int(preview),calls
        gamma_shared=dict(patches=[])
        bindings=[('.text.r5_gamma_consume','r5_gamma_trusted_return','consume')]
        if preview:bindings += [('.text.r5_preview_gamma','r5_gamma_preview_trusted_return','preview')]
        for section,literal_name,label in bindings:
            owner=[s for s in linked['sections'] if s['section']==section]
            assert len(owner)==1,owner
            sites=[int(r['site'],16) for r in calls if int(owner[0]['site'],16)<=int(r['site'],16)<int(owner[0]['site'],16)+owner[0]['bytes']]
            assert len(sites)==1,sites
            site=sites[0];trusted=(site+4)|1;literal=symbols[literal_name]
            holder=[r for r in linked['regions'] if int(r['start'],16)<=literal<int(r['start'],16)+r['used']]
            assert len(holder)==1
            r=holder[0];raw=bytearray(r['data']);off=literal-int(r['start'],16)
            assert raw[off:off+4]==bytes(4)
            struct.pack_into('<I',raw,off,trusted);r['data']=bytes(raw)
            if label=='consume':gamma_shared.update(trusted_return_pc=hex(trusted),trusted_literal=hex(literal),consume_BL=hex(site))
            else:gamma_shared.update(preview_trusted_return_pc=hex(trusted),preview_trusted_literal=hex(literal),preview_BL=hex(site))
    image=INPUT.read_bytes();assert sha(image)==SHA
    patched=bytearray(image);patches=[]
    def patch(at,raw,kind,**kw):
        old=image[at-BASE:at-BASE+len(raw)];patched[at-BASE:at-BASE+len(raw)]=raw
        patches.append(dict(site=hex(at),original=old.hex(),replacement=raw.hex(),kind=kind,**kw))
    for region in linked['regions'][1:]:
        patch(int(region['start'],16),region['data'][:region['used']], 'reclaimed RX section payload')
    def target(at,name):
        dest=symbols[name]&~1
        assert -0x1000000<=dest-(at+4)<0x1000000,(hex(at),name,'Out-of-range hook: no unaudited trampoline space')
        return dest
    if shared_gamma:
        # Every replaced instruction is checked against the fixed 4.04 input.
        for at,name,old in [(0x413666,'load_413666','51f82210'),
                            (0x413d40,'load_413d40','50f82600'),
                            (0x413922,'load_413922','0d9d0beb8100'),
                            (0x4139cc,'load_4139cc','0d980146'),
                            (0x413e16,'wrapper_forward','fff711fc')]:
            assert image[at-BASE:at-BASE+len(bytes.fromhex(old))].hex()==old,(hex(at),image[at-BASE:at-BASE+len(bytes.fromhex(old))].hex())
            raw=branch(at,target(at,name),False)+(b'\x00\xbf' if len(bytes.fromhex(old))==6 else b'')
            patch(at,raw,'shared original Gamma detour',symbol=name)
            gamma_shared['patches'].append(dict(site=hex(at),original=old,replacement=raw.hex()))
    patch(0x11961d4,bytes.fromhex('dff800f0')+struct.pack('<I',symbols['r5_custom_bank_seal']),'replace original seal with global readiness gate')
    sites={0x1196848:('r5_color_seal_result','4ff00209'),0x898568:('r5_color_capture_copy','5cf528ee'),0x4baab6:('r5_color_source_copy','3af182eb'),
        0x4bab9c:('r5_color_source_complete','3af10eeb'),
        0x230be6:('r5_color_snapshot_dispatch','10f0a5f8'),0x231fde:('r5_color_cc1','ecf047f3'),
        0x2323aa:('r5_color_cc1','ecf061f1'),0x23299e:('r5_color_cc1','ebf067f6'),
        0x71b8bc:('r5_color_cc1','02f0d8fe'),0x244996:('r5_color_cc1','d9f06bf6'),
        0x71d6f8:('r5_color_block13','00f091fe'),
        0x717ecc:('r5_color_q_dispatch_gateway','26f0c5f9')}
    if include_gamma:
        # Later native capture reconstruction replaces the materialized
        # component outside our custom carrier. Invalidate stale Q identity.
        sites[0xaec5e4]=('r5_gamma_q_rebuild','2bf4b0fc')
        # Proven model/head writes retire the old request identity before native mutation.
        for at,name,old in [(0xadd846,'r5_gamma_q_model_copy','7bf555f7'),
                            (0x46e5f0,'r5_gamma_q_model_saved','6ef27af2'),
                            (0xaee598,'r5_gamma_q_head_clone','eff7c0fb'),
                            (0x46e614,'r5_gamma_q_saved_rebuild','aaf2d3fc')]:
            assert at not in sites
            sites[at]=(name,old)
        for at,old in [(0x46c1ec,'abf22efd'),(0xaec762,'2bf473fa'),(0xaec792,'2bf45bfa')]:
            sites[at]=('r5_gamma_q_rebuild_alternate',old)
        audit_path=ROOT/'research/r5_custom_lut/evidence/sd405_gamma_pool_audit_v3_20261020/audit.json'
        gamma_audit=json.loads(audit_path.read_text())
        for seam in gamma_audit['seams']:
            at=int(seam['site'],16);assert at not in sites
            sites[at]=(seam['symbol'],seam['original'])
    isp_hooks=[]
    if isp_carrier:
        for at,name,old in [(0x8848de,'owner','00f046fa'),(0x884e36,'stage_shim','8ef609f7'),
                            (0x8859ca,'build','bff710fd'),(0x8860fe,'build','bff776f9'),
                            (0x338fa6,'build','0cf122f2'),(0x886ac6,'build','bef792fc'),
                            (0x8454b4,'black_set','67f22bfb'),(0x845504,'baseband_set','67f205fb'),
                            (0x845700,'gamma_set','67f209fa'),(0x845aa8,'prepare','67f24af8')]:
            assert at not in sites
            symbol='r5_isp_'+name+'_gateway';sites[at]=(symbol,old)
            isp_hooks.append(dict(site=hex(at),original=old,symbol=symbol))
    preview_hooks=[]
    if preview:
        for at,name,old in [(0x8848de,'owner','00f046fa'),(0x884e36,'stage_shim','8ef609f7'),
                            (0x8859ca,'build','bff710fd'),(0x8860fe,'build','bff776f9'),
                            (0x338fa6,'build','0cf122f2'),(0x886ac6,'build','bef792fc'),
                            (0x845700,'gamma_set','67f209fa')]:
            assert at not in sites
            symbol='r5_preview_'+name+'_gateway';sites[at]=(symbol,old)
            preview_hooks.append(dict(site=hex(at),original=old,symbol=symbol))
        at=0x4be3a8;symbol='r5_preview_publish_gateway'
        old=image[at-BASE:at-BASE+4].hex()
        assert old==branch(at,0x7199d6,True).hex(),old
        sites[at]=(symbol,old);preview_hooks.append(dict(site=hex(at),original=old,symbol=symbol))
        at=0x4be3ae;symbol='r5_preview_complete_gateway';old=image[at-BASE:at-BASE+4].hex()
        assert old==branch(at,0xaacaa8,True).hex(),old
        sites[at]=(symbol,old);preview_hooks.append(dict(site=hex(at),original=old,symbol=symbol))
        for at,symbol,native in [(0xaacc36,'r5_aa_snapshot_table',0xaad068),(0xaacc4e,'r5_aa_snapshot_gamma_shim',0xaa69ea),(0xaacd94,'r5_aa_snapshot_mode2',0xaa6a9c)]:
            old=image[at-BASE:at-BASE+4].hex();assert old==branch(at,native,True).hex(),old
            sites[at]=(symbol,old);preview_hooks.append(dict(site=hex(at),original=old,symbol=symbol))
        at=0xaacd28;original=image[at-BASE:at-BASE+8]
        assert original.hex()=='0eb05df804bbf0bd',original.hex()
        patch(at,branch(at,target(at,'r5_aa_snapshot_release_shim'),False)+bytes.fromhex('00bf00bf'),'AA snapshot release epilogue',symbol='r5_aa_snapshot_release_shim')
        at=0xaa68cc
        # Exact 8-byte native load/eor/store sequence bound below from source.
        original=image[at-BASE:at-BASE+8]
        assert original.hex()=='0a5c82f001020a54',original.hex()
        patch(at,branch(at,target(at,'r5_preview_flip_gateway'),False)+bytes.fromhex('00bf00bf'),'atomic preview colour flip',symbol='r5_preview_flip_gateway')
    for at,(name,old) in sites.items():
        assert image[at-BASE:at-BASE+4].hex()==old
        raw=branch(at,target(at,name),True);patch(at,raw,'selected call',symbol=name)
    at=0x230bea;old=image[at-BASE:at-BASE+8];assert old.hex()=='204629460ef1ebf0'
    patched[at-BASE:at-BASE+8]=bytes.fromhex('00bf')*4
    patches.append(dict(site=hex(at),original=old.hex(),replacement='00bf'*4,
        kind='dispatch and argument moves relocated; retain dispatch return r0'))
    page=linked['regions'][0]['data'];(out/'color_page.bin').write_bytes(page)
    (out/'cp-callsite-replay.NONINSTALLABLE.bin').write_bytes(patched)
    undo=bytearray(patched)
    for p in patches:
        at=int(p['site'],16)-BASE;undo[at:at+len(bytes.fromhex(p['original']))]=bytes.fromhex(p['original'])
    assert bytes(undo)==image
    record=dict(schema='r5-color-consumer-candidate/1',camera_io=False,DAT_generated=False,installable=False,
        input=str(INPUT.relative_to(ROOT)),input_sha256=SHA,RX_start=hex(RX),RX_bytes=linked['code_bytes'],page_bytes=4096,include_gamma=include_gamma,
        executable_regions=[{k:v for k,v in r.items()if k!='data'}for r in linked['regions']],sections=linked['sections'],
        metadata_start='0x1a3af78',metadata_end_exclusive='0x1a3b000',metadata_bytes=136,
        carrier_bytes=64,carrier_lifetime='initial native snapshot records identity; Q single native construction commits private full-colour proposal; preview retains shared scratch through native AA flip and completion' if preview else 'initial native snapshot records identity; Q single native construction commits private full-colour proposal',
        source_sha256=input_sha['r5_color_consumer.c'],header_sha256=input_sha['r5_color_consumer.h'],
        stack_usage={p.name:p.read_text() for p in sorted(out.glob('*.su'))},
        compile_commands=commands,objects={p.name:sha(p.read_bytes()) for p in objects},page_sha256=sha(page),
        linked_sources={s:input_sha[s] for s in sources},compile_inputs=input_sha,
        candidate_sha256=sha(patched),symbols={k:hex(v)for k,v in symbols.items()},relocations=rels,patches=patches,
        production_test_api_stripped=preview,
        preview=dict(hooks=preview_hooks,metadata_start='0x1a3afec',metadata_bytes=8) if preview else None,
        gamma_shared=gamma_shared,fifth_argument_bytes=516 if include_gamma else None,
        file_padding_code=dict(start='0x1195080',end_exclusive='0x1196000',bytes=3968,
            input_sha256=SHA,audit_path=str(out/'file_padding_audit/audit.json'),
            audit_sha256=sha((out/'file_padding_audit/audit.json').read_bytes()),
            native_page_prefix_preserved=True,requires_loader_XN_clear=True,writable_executable_page=True) if padding_audit else None,
        isp_carrier=dict(metadata_start='0x1a3afec',metadata_bytes=8,qualification_gate='always rejects',hooks=isp_hooks) if isp_carrier else None,
        exact_reverse=True,native_profile_domain_preserved=True,
        not_patched=['CC1 metadata enumeration 0x244aaa','block13 metadata enumeration 0x24528c/0x2453d2',
            'native Gamma metadata enumeration','native scene/dispatch/profile selectors'],
        limits=['Address-space replay image requires independent RX copy/MMU/BSS integration.',
            'Original downstream hardware calls and asynchronous queues are not exercised by this builder.',
            'Numerical dispatch domains keep native gates; photo/preview/video labels and device functionality unverified.'])
    (out/'build.json').write_text(json.dumps(record,indent=2)+'\n');return record
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--include-gamma',action='store_true');p.add_argument('--shared-gamma',action='store_true');p.add_argument('--isp-carrier',action='store_true');p.add_argument('--file-padding-code',action='store_true');p.add_argument('--preview',action='store_true');a=p.parse_args()
    print(json.dumps(build(a.output,a.include_gamma,a.shared_gamma,a.isp_carrier,a.file_padding_code,a.preview)))
