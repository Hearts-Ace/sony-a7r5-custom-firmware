"""Build new CP source tree from immutable455 sources, not binary stacking.
Produces NONINSTALLABLE component only. Native boot/MMU still gates delivery.
"""
from pathlib import Path
import shutil,json,hashlib,subprocess,sys,argparse
H=Path(__file__).resolve().parent;ROOT=H.parents[2];SRC=ROOT/'projects/firmware/development/shutter-sound-recovery455/src'
p=argparse.ArgumentParser();p.add_argument('--adapter',type=Path,default=H/'adapter-k');p.add_argument('--out',type=Path,default=H/'integrated-o');args=p.parse_args();OUT=args.out.resolve();ADAPTER=args.adapter.resolve();AR=json.loads((ADAPTER/'build.json').read_text());ASPECT_BYTES=AR['code_bytes'];TOTAL_BYTES=4096+ASPECT_BYTES;assert ASPECT_BYTES<4096
assert OUT.parent==H, 'output must remain directly under exclusive cp directory'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
OUT.mkdir(exist_ok=False)
for folder in ['cp','gamma','cp_include','lib','import'] :shutil.copytree(SRC/folder,OUT/folder)
(OUT/'inputs').mkdir();shutil.copyfile(H/'baseline404.bin',OUT/'inputs/cp_baseline.bin')
gates=OUT/'gamma/getter_build423';gates.mkdir();shutil.copyfile(H/'gamma_compact.bin',gates/'gates.bin')
g=json.loads((H/'gamma_compact.json').read_text());g['schema']='r5-native-gamma423-view-gates/1';g['patches']=[{'offset':r['offset'],'before':r['before'],'after':r['after'],'reason':'same native Gamma contract, shared all-register return'}for r in g['records']]
sys.path.insert(0,str(OUT/'lib'));from thumb_ops import BOUNDS
for at in BOUNDS:g['patches'].append({'offset':at,'before':'3328','after':'4b28','reason':'native Gamma bound75 retained'})
(gates/'gates.json').write_text(json.dumps(g,indent=2)+'\n')
for name in ['cp_stage413_probe.c','cp_transfer.c']:shutil.copyfile(H/'resident-crcshare-b'/name,OUT/'cp'/name)
shutil.copyfile(H/'aspect_resident.S',OUT/'cp/aspect_resident.S')
p=OUT/'cp/r5_sound_page.S';s=p.read_text();s=s.replace(' ldr r0,[r0,#0xe8]\n ldr r1,=0x1a3a63e\n cmp r0,r1\n bne .Lbad', ''' ldr r2,[r0,#0xe8]
 ldr r1,=0x1a3a63e
 cmp r2,r1
 bne .Lbad
 ldr r0,[r0,#0xec]
 ldr r1,=0x1a3b63e
 cmp r0,r1
 bne .Lbad''');p.write_text(s)
p=OUT/'cp/build_cp.py';s=p.read_text();s=s.replace('RX=0x1195260','RX=0x11951e0').replace('SOUND_BYTES=2240',f'SOUND_BYTES={TOTAL_BYTES}').replace("['r5_sound_page.S','r5_sound_guard_hooks.S','r5_sound_gain_guard.S']", "['r5_sound_page.S','r5_sound_guard_hooks.S','r5_sound_gain_guard.S','aspect_resident.S']")
s=s.replace("'r5ss_guard_expected_crc_inverse':0xdeadbeef", "'r5ss_guard_expected_crc_inverse':0xdeadbeef,'aspect_module_dispatch':0x1a3b001,'native_capture':0x4596f5,'native_dimensions':0x48b9d9,'native_pool_release':0xae08c9,'native_raw_exif':0xade83d")
s=s.replace("assert sound_sy['r5ss_cp_extended_consume']==SOUND|1 and len(sound_code)==SOUND_BYTES", "assert sound_sy['r5ss_cp_extended_consume']==SOUND|1 and len(sound_code)==2240")
s=s.replace(" link_audit={}\n", """ # Optional aspect code lives on the second immutable RX page. Padding is
 # included in CRC, preventing unverified indirect-table bytes.
 aspect_dir=Path(ADAPTER_PATH)
 aspect_report=json.loads((aspect_dir/'build.json').read_text())
 aspect=(aspect_dir/'adapter.bin').read_bytes()
 assert len(aspect)==ASPECT_CODE_BYTES
 assert 'aspect_state_reset' not in aspect_report['symbols']
 sound_code+=bytes(4096-len(sound_code))+aspect
 assert len(sound_code)==SOUND_BYTES
 link_audit={}
""")
s=s.replace("'r5ss_guard_expected_crc_inverse':(~zlib.crc32(sound_code))&0xffffffff", "'r5ss_guard_expected_crc_inverse':(~zlib.crc32(sound_code))&0xffffffff,'aspect_module_dispatch':int(aspect_report['symbols']['aspect_module_dispatch'],0),'native_capture':0x4596f5,'native_dimensions':0x48b9d9,'native_pool_release':0xae08c9,'native_raw_exif':0xade83d")
s=s.replace('assert resident_used<=7584,(resident_used,7584)', 'assert resident_used<=7712,(resident_used,7712)').replace('code+=bytes(7584-resident_used)', 'code+=bytes(7712-resident_used)')
s=s.replace("struct.pack('<III',0xe1a02000,0xe3a01a01,0xe3a0300f)", "struct.pack('<III',0xe1a02000,0xe3a01a02,0xe3a0300f)")
s=s.replace("struct.pack('<I',0x8a4000)", "struct.pack('<I',0x8a5000)").replace('mov16(3,0x9498)', 'mov16(3,0x9698)')
s=s.replace("'PTE':['0x01a3a63e']", "'PTE':['0x01a3a63e','0x01a3b63e']")
s=s.replace("report['BSS_extension_bytes']=0x8a4000-0x8a2448", "report['BSS_extension_bytes']=0x8a5000-0x8a2448")
s=s.replace("'descriptor_BSS_end':'0x1a3b000'", "'descriptor_BSS_end':'0x1a3c000'").replace("'native_BSS_clear_end':'0x1a39498'", "'native_BSS_clear_end':'0x1a39698'").replace("'resident_padding_bytes':7584-resident_used", "'resident_padding_bytes':7712-resident_used")
needle=" reverse=bytearray(candidate)"
insert=''' # The second immutable page extends BSS reservation exactly to the L1
 # descriptor VA1a3c000. Native +4fff would skip to physical1a40000,
 # breaking the resident TTBR identity contract. Round with +3fff instead;
 # L1 starts immediately after the reserved pages, L2/stacks stay unchanged.
 assert raw[0x1083ec-BASE:0x1083f0-BASE]==mov16(1,0x4fff)
 patch(0x1083ec-BASE,mov16(1,0x3fff),'Preserve identity L1/L2 placement after two-page RX reservation')
 # Every aspect callsite reaches resident code first, within signed BL range.
 aspect_hooks=aspect_report['hooks']
 assert len(aspect_hooks)==12 and 'heif' not in aspect_hooks
 assert not any('heif_packet' in name for name in aspect_report['symbols'])
 for name,row in aspect_hooks.items():
  at=int(row['VA'],0);expected=bytes.fromhex(row['source_bytes'])
  assert raw[at-BASE:at-BASE+len(expected)]==expected
  patch(at-BASE,bl(at,sy['aspect_resident_dispatch']), 'Aspect '+name+' through resident PTE+full CRC guard')
'''
assert needle in s;s=s.replace(needle,insert+needle)
s=s.replace("report['private_gain']=", "report['aspect']={'adapter_sha256':aspect_report['code_sha256'],'module_dispatch':aspect_report['symbols']['aspect_module_dispatch'],'resident_dispatch':hex(sy['aspect_resident_dispatch']),'RX':'0x1a3b000','state':'0x1a394a0','state_bytes':504,'pool_capacity_decimal':490,'pool_capacity_hex':'0x1ea','state_zeroed_by_native_clear':True,'guarded_hooks':12,'disabled_native_hooks':['heif'],'legacy_heif_helper':'removed from C, wrapper, module and resident dispatch; original native copy retained','fallback_invalidates_all_private_IDs':True,'Gamma_compact_bytes':348,'CRC_dedup':True}\n report['private_gain']=")
s=s.replace('ADAPTER_PATH',repr(str(ADAPTER))).replace('ASPECT_CODE_BYTES',str(ASPECT_BYTES))
p.write_text(s)
subprocess.run([sys.executable,'-B',str(p)],check=True)
r=json.loads((OUT/'cp/build.json').read_text());(OUT/'source-provenance.json').write_text(json.dumps({'original455':{str(p.relative_to(SRC)):sha(p)for folder in ['cp','gamma','cp_include','lib','import']for p in (SRC/folder).rglob('*')if p.is_file()},'new_sources':{str(p.relative_to(OUT)):sha(p)for p in OUT.rglob('*')if p.is_file() and p.suffix in ['.py','.c','.S','.h']},'no_DAT':True,'installable':False,'remaining':['run final-image boot/MMU, guard and native fallback/recovery replay for this exact output','HEIF paired AVCAM required; CP packet hook is disabled','complete AP/resource integration','camera JPEG/HEIF decode remains unvalidated; RAW modification is out of scope']} ,indent=2)+'\n')
print(json.dumps({'CP':r['candidate_sha256'],'resident':r['sound_page_guard'],'aspect':r['aspect']}))
