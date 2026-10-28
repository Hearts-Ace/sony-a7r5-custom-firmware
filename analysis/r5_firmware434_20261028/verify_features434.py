"""Evidence identity/policy checks for the four requested 4.34 features.

These checks consume saved native-instruction replay receipts. They do not
rerun the updater, camera UI or ISP. Template bytes have a separate independent
verifier which does not import the template generator.
"""
from pathlib import Path
import hashlib,json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CP='8b38e753f34b1667d79b69079d911b9e6595f1ce1b873cb8e014437c6b4c494d'
FEATURE_RECEIPTS=('preservation/generated/templates_manifest.json',
                  'preservation/verification.json','color/color434_verified.json',
                  'color/integrated_templates_check.json')

def read(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(4<<20),b''):h.update(block)
    return h.hexdigest()
def bound(row):
    p=Path(row['path'])
    assert not p.is_absolute() and '..' not in p.parts
    assert sha(ROOT/p)==row['sha256'],str(p)

def verify_colour():
    q={name:read(HERE/name) for name in FEATURE_RECEIPTS}
    assert all(v['passed'] and v['camera_io'] is False for v in q.values())
    t=q[FEATURE_RECEIPTS[0]];m=q[FEATURE_RECEIPTS[1]];c=q[FEATURE_RECEIPTS[2]]
    assert t['schema']=='r5-sd-colour-preservation434/1'
    assert t['matrix_mode']=='dynamic' and t['count']==12
    assert (t['FL23_fields_each'],t['total_ranges_each'],t['total_field_bytes_each'])==(10,13,2746)
    assert not t['personalized_partition_embedded'] and not t['AP_hooks_added']
    assert t['backup_sum']['updated_template_CRC_rows']==12
    assert m['templates_manifest_sha256']==sha(HERE/FEATURE_RECEIPTS[0])
    assert m['template_count']==12 and m['native_core_cases']==len(m['native_runs'])==72
    for field in ('patched_templates_BK4_checksums_and_native_ranges_verified',
                  'all_full_dynamic_donor_banks_verified','idempotence_passed'):
        assert m[field],field
    assert len(m['negative_checks'])==4 and all(r['rejected'] for r in m['negative_checks'])
    assert len(m['kernels'])==2
    for row in [*m['kernels'].values(),m['native_harness']]:bound(row)
    colours={'0x02A40000','0x02A40001','0x02A4000D'}
    looks={'0x02CF0B69','0x02CF0B6F','0x02CF0B93','0x02CF0B95','0x02CF0B97','0x02CF0B99'}
    combos={(r['kernel'],r['mode'],r['property']) for r in m['native_runs']}
    assert combos=={(k,mode,p) for k in m['kernels'] for mode in (0,2,4,5) for p in colours|looks}
    for row in m['native_runs']:
        if row['property'] in colours:
            assert row['attributes']==8 and row['equals_template'] and not row['copied_old_value']
        elif row['mode']==5:
            assert row['attributes']==96 and row['equals_old'] and row['copied_old_value']
    assert c['CP_sha256']==CP and c['CP_exactly_4_32_unchanged']
    assert c['all3_properties_native_migration_attr8'] and c['R6_ST_photo_only']
    assert c['CP_changes_required'] is False
    for name,digest in c['sources'].items():bound(dict(path=name,sha256=digest))
    sources=read(HERE/'color/source_bindings.json')['rows']
    assert len(sources)>=20
    for row in sources:bound(row)
    assert {(r['property_id'],int(r['offset'],16),r['bytes']) for r in c['ranges']}=={
        ('0x02A40000',0x930,2),('0x02A40001',0x1250,48),('0x02A4000D',0x2a0,192)}
    awb=c['AWB']
    assert (awb['white']['old'],awb['white']['new'])==(88,97)
    assert (awb['ambience']['old'],awb['ambience']['new'])==(-24,-1)
    assert awb['companions_932_933']==[0,6]
    assert awb['cases']==len(awb['rows'])==336 and awb['native_helper_stubs'] is False
    assert awb['standard_branch_unchanged'] and awb['standard_all112_cases_unchanged']
    standard=[r for r in awb['rows'] if r['mode']==0]
    assert len(standard)==112 and all(r['before']==r['after'] for r in standard)
    assert any(r['changed'] for r in awb['rows'] if r['mode']==1)
    assert any(r['changed'] for r in awb['rows'] if r['mode']==2)
    assert c['cc1']['cases']==len(c['cc1']['rows'])==63
    matrix=c['matrix']
    assert matrix['cases']==len(matrix['rows'])==320 and matrix['native_helper_stubs'] is False
    assert matrix['ST_B_A2_preserved'] and matrix['ST_A1_all16_verified']
    integrated=q[FEATURE_RECEIPTS[3]]
    assert integrated['templates']==12 and integrated['AWB_bytes']=='61ff0006'
    assert integrated['only_awb_white_differs_from433']
    comparison=read(HERE/'preservation/compared_433_templates.json')
    assert comparison['passed'] and comparison['camera_io'] is False
    assert integrated['comparison_receipt_sha256']==sha(HERE/'preservation/compared_433_templates.json')
    return dict(passed=True,regional_templates=12,native_migration_core_cases=72,
                CC1_cases=63,matrix_cases=320,AWB_cases=336,standard_AWB_cases_unchanged=112,
                camera_io=False,device_acceptance_tested=False)

def verify_fn(ap):
    fn=read(HERE/'fn/fn434_verified.json')
    assert fn['passed'] and fn['AP_sha256']==ap
    required={'registration_candidate','native_registration_setter',
              'saved_slot_roundtrip','still_movie_activation',
              'fn_invocation_enters_private_page','fn_name_bridge',
              'native_return_path','original_creative_look_preserved',
              'fn_icon_reuses_creative_look'}
    assert required<=set(fn['checks'])
    for name in required:
        check=fn['checks'][name]
        assert check['passed'],name
        for field in ('evidence','native_executed','fixtures','limits'):assert field in check,(name,field)
        assert check['evidence'] and check['native_executed'],name
    for name in ('receipts','source_bindings'):
        assert fn[name],name
        assert len({r['path']for r in fn[name]})==len(fn[name])
        for row in fn[name]:bound(row)
    for receipt,script in (('fn434_candidates.json','replay_fn434.py'),
                           ('fn434_save_roundtrip.json','replay_fn_save434.py')):
        q=read(HERE/'fn'/receipt)
        assert q['passed'] and q['AP_sha256']==ap
        assert q['script_sha256']==sha(HERE/'fn'/script)
    candidates=read(HERE/'fn/fn434_candidates.json')
    assert (candidates['native_validity_cases'],candidates['native_build_cases'])==(156,20)
    saved=read(HERE/'fn/fn434_save_roundtrip.json')
    assert saved['native_registration_cases']==saved['native_shadow_roundtrips']==96
    assert saved['native_save_handler']=='0x21e45c8' and saved['native_first_screen_reader']=='0x216eb9c'
    assert {(row['bias'],case['kind'],case['slot'],case['default_target_present'])
            for row in saved['rows']for case in row['cases']}=={
                (bias,kind,slot,target)for bias in ('0x0','0x40000000')
                for kind in ('still','movie')for slot in range(12)for target in (False,True)}
    for row in saved['rows']:
        for case in row['cases']:
            assert case['function_id']==case['first_screen_reader_mid']=='0x635'
            assert case['other_slots_unchanged']
    for receipt,script in (('fn434_activation.json','replay_activation434.py'),
                           ('fn434_stack_restore.json','replay_stack434.py')):
        q=read(HERE/'fn_activation'/receipt)
        assert q['passed'] and q['AP_sha256']==ap
        assert q['script_sha256']==sha(HERE/'fn_activation'/script)
    import importlib.util
    contract_path=HERE/'fn_activation/evidence_contract.py'
    spec=importlib.util.spec_from_file_location('fn434_evidence_contract',contract_path)
    contract=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    act=read(HERE/'fn_activation/fn434_activation.json')
    stack=read(HERE/'fn_activation/fn434_stack_restore.json')
    activation_summary=contract.verify_activation(ap,act,stack)
    resource_evidence=contract.resource_bindings(act)
    assert fn['activation_summary']==activation_summary
    assert fn['icon_resources']=={k:v for k,v in resource_evidence.items()if k!='bindings'}
    ledger={r['path']:r['sha256']for r in fn['source_bindings']}
    for row in resource_evidence['bindings']:
        assert ledger[row['path']]==row['sha256']
    labels=read(HERE/'fn/fn434_registration_labels.json')
    assert labels['passed'] and labels['AP_sha256']==ap and labels['registration_label_cases']==4
    assert labels['script_sha256']==sha(HERE/'fn/replay_fn_labels434.py')
    return dict(passed=True,AP_sha256=ap,checks=sorted(required))

if __name__=='__main__':print(json.dumps(verify_colour()))
