#!/usr/bin/env python3
"""Offline source import. Never imports a USB backend or contacts a camera."""
from pathlib import Path
import argparse, ast, base64, hashlib, json, shutil

ROOT = Path(__file__).resolve().parents[1]
NOTICE = '# Adapted for R5FlashWorkbench, 2026-10-29. See THIRD_PARTY_NOTICES.md.\n'

def digest(raw): return hashlib.sha256(raw).hexdigest()
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', required=True, type=Path)
    p.add_argument('--original', required=True, type=Path)
    p.add_argument('--candidate', required=True, type=Path)
    a=p.parse_args(); ref=a.reference; desktop=ref/'a7r5-desktop'; engine=ROOT/'engine'
    engine.mkdir(parents=True, exist_ok=True)
    old,new=a.original.read_bytes(),a.candidate.read_bytes()
    source='d6cb0eb25e78dbfa09d29225485cc204b773d533d301af1ec54ea7bd2d1e1181'
    target='7d17697fb83a26bbcd53f49f7c791fea7cdd9e372ad6f4510d1f079e643a0b05'
    if len(old)!=25100288 or len(new)!=len(old) or digest(old)!=source or digest(new)!=target:
        raise ValueError('Unsupported offline trust image pair')
    rows=[];sectors=[]
    for at in range(0,len(old),512):
        x,y=old[at:at+512],new[at:at+512]
        if x==y:continue
        if not (82432<=at<9179648 or 15843840<=at<15844352):
            raise ValueError('Change outside initrd/checksum allocation')
        phase='checksum' if at>=15843840 else 'initrd'
        rows.append(dict(sector=at//512,offset=at,bytes=512,phase=phase,before_sha256=digest(x),after_sha256=digest(y)))
        sectors.append(dict(offset=at,before=base64.b64encode(x).decode(),after=base64.b64encode(y).decode()))
    plan=dict(schema='a7r5-kit-trust-plan-v1',device='/dev/cnflasha1',device_number='252:129',
        source_sha256=source,candidate_sha256=target,partition_bytes=len(old),logical_sector_size=512,
        changed_sectors=len(rows),logical_write_bytes=len(rows)*512,changed_bytes=sum(x!=y for x,y in zip(old,new)),
        rows=rows,automatic_retry=False,automatic_rollback=False,reboot=False)
    save(engine/'write-plan.json',plan);save(engine/'trust-sectors.json',dict(rows=sectors))
    files=['common.py','host.py','transport.py','policy.py','libjit_operation.py','capture_operation.py','trust_operation.py']
    origin={}
    for name in files:
        raw=(desktop/'engine'/name).read_bytes();origin[name]=digest(raw);text=raw.decode()
        if name=='common.py':text=text.replace('acf32d30dd883ed349738e66fb081e85e0d6a3c746f5e3ca169031e8d69ed731',source).replace('a3733332c2a1b336226bb9000e01665ce54bec970aefc3334b88863b80f40ceb',target)
        if name=='trust_operation.py':
            text=text.replace('258',str(len(rows))).replace('132096',str(len(rows)*512))
            text=text.replace("self.force=self.config.get('force_install',False)","self.force=self.config.get('force_install',False)\n        if self.force:raise ValueError('Force install is not supported by this workbench')")
        (engine/name).write_text(NOTICE+text)
    shutil.copytree(desktop/'engine/system_dump',engine/'system_dump',dirs_exist_ok=True)
    session=engine/'system_dump/session.py'
    session.write_text(NOTICE+session.read_text().replace('"firmware_version": "4.00", "firmware_version_source": "historical_user_report_only"',
        '"firmware_version": None, "firmware_version_source": "body_version_not_observed_by_MSC_probe"'))
    # Only reuse the standard backup/update preparation functions. No SSH/force UI or payload.
    text=(desktop/'engine/device.py').read_text();tree=ast.parse(text)
    selected=[]
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in ('package_base','prepare_capture','prepare_update'):
            part=ast.get_source_segment(text,node)
            if node.name=='prepare_capture':
                part=part.replace("template='work-probe.so' if probe else 'capture.so'","if probe:raise ValueError('Work probe is not included')\n    template='capture.so'")
                part=part.replace('(WorkProbeOperation if probe else CaptureOperation)(package)','CaptureOperation(package)')
            if node.name=='prepare_update':
                begin=part.index('    if force:\n');end=part.index('    if backup_manifest is None:')
                part=part[:begin]+"    if force:raise ValueError('Force install is not supported')\n"+part[end:]
                part=part.replace("value.update(","value.update(")
            selected.append(part)
    imports='''from pathlib import Path
import base64, shutil
from common import ROOT, SOURCE_SHA, TARGET_SHA, PARTITION_BYTES, config, digest, load, render_template, safe, save, sha, write_payload
from capture_operation import Operation as CaptureOperation
from trust_operation import Operation as TrustOperation
'''
    (engine/'preparation.py').write_text(NOTICE+imports+'\n\n'+'\n\n'.join(selected)+'\n')
    shutil.copyfile(desktop/'engine/profile.json',engine/'profile.json')
    vendor=ref/'a7r5-updater-trust/deploy/vendor/engine'
    shutil.copytree(vendor/'libs/usb',engine/'site/usb',dirs_exist_ok=True)
    shutil.copytree(vendor/'sources/workspaces/j/work/sony-pmca-re/pmca',engine/'vendor/pmca_source/pmca',dirs_exist_ok=True)
    shutil.copytree(desktop/'sources/trust',ROOT/'sources/trust',dirs_exist_ok=True)
    native=ROOT/'sources/trust/native_gate.c'
    native.write_text('/* Adapted for our signing identity and actual sector plan; 2026-10-29. */\n'+native.read_text().replace('258',str(len(rows))).replace('132096',str(len(rows)*512)))
    prepare=(desktop/'scripts/prepare.py').read_text().split('\ndef capture_payload():')[0]
    # Build-only import, with explicit portable compiler configuration supplied by our caller.
    prepare=prepare.replace('#define PATCH_COUNT 258U',f'#define PATCH_COUNT {len(rows)}U').replace('-Wno-unused-but-set-global','-Wno-unused-but-set-variable')
    (ROOT/'scripts/reference_compile.py').write_text(NOTICE+prepare)
    licenses=ROOT/'licenses';licenses.mkdir(exist_ok=True)
    for name in ('LICENSE','THIRD_PARTY_NOTICES.md','README.md'):
        shutil.copyfile(ref/name,licenses/('a7r5-rea-'+name))
    shutil.copyfile(ref/'a7r5-implementation-kit/engine/PMCA-LICENSE.txt',licenses/'PMCA-LICENSE.txt')
    for source_dir,label in [(ref/'a7r5-updater-trust/licenses','trust'),(ref/'a7r5-exec/licenses','exec')]:
        if source_dir.exists():shutil.copytree(source_dir,licenses/label,dirs_exist_ok=True)
    save(ROOT/'REFERENCE.json',dict(project='https://github.com/Liwenru88/a7r5-rea',commit='290c79e',
        adapted_original_files=origin,trust_plan=plan,reference_private_keys_included=False,
        reference_firmware_patches_included=False,camera_IO=False))
    print('Imported MSC transport; own trust plan:',len(rows),'sectors,',len(rows)*512,'bytes. No camera I/O.')

if __name__=='__main__':main()
