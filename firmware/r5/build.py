#!/usr/bin/env python3
"""Rebuild local R5 4.59 crop test components/partitions from frozen sources.

Source and original firmware inputs are never modified. No device or network
operation exists in this entry. --stage all additionally signs the local test
DAT using the operator's separately supplied private-key path.
"""
from pathlib import Path
import argparse,hashlib,importlib,json,os,shutil,subprocess,sys,tarfile,time

HERE=Path(__file__).resolve().parent
REL=Path('analysis/r5_aspect456_20261110')
BASE_REL=Path('projects/firmware/development/shutter-sound-recovery455')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def exact(path,row,label):
    assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],('Identity differs',label)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True,help='Private original input-path JSON; never included in source archive')
    p.add_argument('--output',type=Path,required=True,help='New build directory; compiled output lives here only')
    p.add_argument('--stage',choices=('components','all'),default='components')
    p.add_argument('--e2fsck',type=Path,help='Optional e2fsck executable for read-only ext2 validation')
    a=p.parse_args();assert __debug__,'Do not disable integrity assertions with -O'
    out=a.output.expanduser().resolve();config_path=a.inputs.expanduser().resolve()
    assert not out.exists(),'Output must be new'
    assert out!=HERE and not HERE.is_relative_to(out),'Output must not contain source tree'
    lock=json.loads((HERE/'sources.lock.json').read_text())
    assert lock and all(sha(HERE/name)==digest for name,digest in lock.items()),'Frozen source changed'
    expected=json.loads((HERE/'expected_outputs.json').read_text())
    config={k:str(Path(v).expanduser().resolve()) for k,v in json.loads(config_path.read_text()).items()}
    # Fail before the expensive baseline rebuild when a declared host tool or
    # Python package is missing. All resolved paths remain ordinary host tools.
    packages={name:importlib.import_module(name) for name in ('numpy','elftools','capstone','unicorn','Cryptodome','cryptography')}
    compiler=shutil.which('clang');assert compiler,'clang is required'
    checker=str(a.e2fsck.expanduser().resolve()) if a.e2fsck else (shutil.which('e2fsck') or '/opt/homebrew/opt/e2fsprogs/sbin/e2fsck')
    assert Path(checker).is_file(),'e2fsck is required; supply --e2fsck'
    # The original immutable 4.55 entry validates all input sizes/hashes before
    # using them. No private-key read is needed for the default component stage.
    out.mkdir(parents=True);runtime=out/'runtime';shutil.copytree(HERE/'source',runtime)
    for path,digest in lock.items():
        if path.startswith('source/'):
            assert sha(runtime/Path(path).relative_to('source'))==digest
    logs=out/'logs';logs.mkdir();commands=[]
    save(out/'host-environment.json',dict(python=sys.version,executable=sys.executable,
         compiler=compiler,compiler_version=subprocess.run([compiler,'--version'],capture_output=True,text=True,check=True).stdout,
         e2fsck=checker,packages={name:dict(path=str(module.__file__),version=getattr(module,'__version__',None))
                                for name,module in packages.items()}))
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
    # Canonicalize the caller's dependency search paths before cwd changes.
    # Third-party host packages are installed dependencies, not firmware inputs.
    if env.get('PYTHONPATH'):
        env['PYTHONPATH']=os.pathsep.join(str(Path(x or '.').resolve()) for x in env['PYTHONPATH'].split(os.pathsep))
    def run(label,script,*args,extra_env=None):
        command=[sys.executable,'-B',str(script),*map(str,args)]
        print(label,flush=True);started=time.monotonic()
        log=logs/(label+'.log')
        with log.open('w') as stream:
            r=subprocess.run(command,cwd=runtime,env={**env,**(extra_env or {})},stdout=stream,stderr=subprocess.STDOUT)
        row=dict(stage=label,command=command,exit_code=r.returncode,seconds=round(time.monotonic()-started,3),
                 log=str(log.relative_to(out)),log_sha256=sha(log))
        commands.append(row);save(out/'commands.json',commands)
        if r.returncode:
            print(log.read_text()[-6000:],file=sys.stderr)
            raise RuntimeError('Stage failed: '+label+'; see '+str(log))
    base=out/'base455';frozen455=runtime/BASE_REL
    run('01-baseline455',frozen455/'build.py','--inputs',config_path,'--output',base,'--stage','components')
    base_expected=json.loads((frozen455/'expected_outputs.json').read_text())
    for key,name in (('AP','appFw.so'),('CP','cpapp-b.bin'),('nflasha5','nflasha5'),('nflasha8','nflasha8'),('nflasha15','nflasha15')):
        assert sha(base/'patched'/name)==base_expected[key],('Baseline455 differs',key)
    release=runtime/'projects/firmware/releases/4.55-sound-recovery-20261105'
    release.mkdir(parents=True);shutil.copyfile(base/'patched/appFw.so',release/'appFw.so')
    crop=runtime/REL;cp=crop/'cp';ui=crop/'ui';review=crop/'reference-review'
    shutil.copyfile(base/'work/inputs/cp_baseline.bin',cp/'baseline404.bin')
    # Extract only the required originals into this fresh runtime. In particular
    # no old patched AP/CP/AVCAM/MPR or resource output is an input.
    full=crop/'full';sys.path.insert(0,str(full/'vendor'))
    from a7r5dat.ext2_patch import reader
    from a7r5dat.fat import FatImage
    fs=reader(Path(config['stock_nflasha15']).read_bytes())
    root_usr=runtime/'unpacked/r5/usr_complete';lib=root_usr/'lib';lib.mkdir(parents=True)
    (lib/'libmpr.so').write_bytes(fs.read_inode(fs.walk('/lib/libmpr.so')))
    resource_inputs=root_usr/'share/app';resource_inputs.mkdir(parents=True)
    resource_manifest=json.loads((crop/'resources/inputs.json').read_text())
    for row in resource_manifest['resource_files']:
        raw=fs.read_inode(fs.walk('/share/app/'+row['name']))
        assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
        (resource_inputs/row['name']).write_bytes(raw)
    del fs
    stock_parts=runtime/'unpacked/r5/firmware/0700_part_image/dev';stock_parts.mkdir(parents=True)
    with tarfile.open(config['original_tar'],'r:') as t:
        n3=t.extractfile('0700_part_image/dev/nflasha3').read()
    (stock_parts/'nflasha3').write_bytes(n3)
    camera=runtime/'unpacked/r5/system_main';camera.mkdir(parents=True)
    (camera/'av-cam.bin').write_bytes(FatImage(n3).read('/av-cam.bin'));del n3
    # Supply the original n3 next to n8 for the reviewed partition builder.
    (stock_parts/'nflasha8').symlink_to(Path(config['stock_nflasha8']))
    local_config={**config,'stock_nflasha8':str(stock_parts/'nflasha8')}
    generated_inputs=out/'inputs.runtime.json';save(generated_inputs,local_config)
    stock_cp=runtime/'unpacked/r5/cp_data';stock_cp.mkdir(parents=True)
    (stock_cp/'cpapp-b.bin').symlink_to(Path(config['stock_cp']))
    run('02-gamma',cp/'build_gamma_compact.py')
    adapter=cp/'adapter-build'
    run('03-cp-adapter',cp/'build_adapter.py','--dispatch','--out',adapter)
    integrated=cp/'integrated-build'
    run('04-cp-integrated',cp/'build_integrated.py','--adapter',adapter,'--out',integrated)
    module=ui/'module-build';contract=ui/'contract-build';ap=ui/'candidate-build'
    run('05-ap-module',ui/'compile_ui.py','--output',module)
    run('06-ap-contract',ui/'make_contract.py','--module',module,'--output',contract)
    run('07-ap-append',ui/'append_ui.py','--module',module,'--contract',contract/'integration.json','--output',ap)
    avcam=review/'avcam-build';mpr=review/'mpr-build';playback=review/'playback-build'
    run('08-avcam',review/'avcam_patch.py','--output',avcam)
    run('09-mpr',review/'mpr_patch.py','--output',mpr)
    run('10-ap-playback',review/'append_playback_segment.py','--base',ap/'appFw-NONINSTALLABLE.so',
        '--base-sha256',sha(ap/'appFw-NONINSTALLABLE.so'),'--output',playback)
    resource_output=crop/'resources/output-build'
    run('11-resources',crop/'resources/build_resources.py','--input-root',resource_inputs,'--output',resource_output)
    pt=runtime/'analysis/r5_filter_pt456_20261110/candidate-build'
    run('10c-ap-filter-pt',runtime/'analysis/r5_filter_pt456_20261110/build_pt.py',
        '--base',playback/'appFw-NONINSTALLABLE.so','--audit',base/'work/import/module_audit.json','--output',pt)
    outputs={'AP':pt/'appFw-NONINSTALLABLE.so','CP':integrated/'cp/cp423.NONINSTALLABLE.bin',
             'AVCAM':avcam/'av-cam.bin','MPR':mpr/'libmpr.so'}
    for key,path in outputs.items():exact(path,expected['components'][key],key)
    actual_resources=json.loads((resource_output/'manifest.json').read_text())
    assert {r['name']:r['output_sha256'] for r in actual_resources['files']}==expected['resources']
    partitions=out/'partitions-build'
    extra=['--e2fsck',checker]
    run('12-partitions',full/'build_partitions.py','--base',base,'--output',partitions,'--inputs',generated_inputs,
        '--ap',outputs['AP'],'--cp',outputs['CP'],'--avcam',outputs['AVCAM'],'--mpr',outputs['MPR'],
        '--resources',resource_output,*extra)
    for key,row in expected['partitions'].items():exact(partitions/'partitions'/key,row,key)
    package=None
    if a.stage=='all':
        package=out/'package'
        run('13-package',full/'package_candidate.py','--base',base,'--build',partitions,
            '--inputs',generated_inputs,'--output',package)
        if expected.get('DAT'):exact(package/'NONINSTALLABLE.DAT',expected['DAT'],'DAT')
        verification_path=package/'verification.json'
        verification=json.loads(verification_path.read_text())
        verification.update(source_freeze_and_rebuild_pending=False,
                            frozen_source_lock_sha256=sha(HERE/'sources.lock.json'),
                            all_components_and_partitions_rebuilt_from_frozen_sources=True,
                            device_acceptance_tested=False)
        save(verification_path,verification)
    report=dict(passed=True,status='LOCAL_TEST_BUILD_REPRODUCED_CAMERA_UNTESTED',version='4.59',stage=a.stage,
                source_lock_sha256=sha(HERE/'sources.lock.json'),expected_outputs_sha256=sha(HERE/'expected_outputs.json'),
                components={k:dict(path=str(v.relative_to(out)),bytes=v.stat().st_size,sha256=sha(v)) for k,v in outputs.items()},
                partitions={name:dict(path=str((partitions/'partitions'/name).relative_to(out)),**row) for name,row in expected['partitions'].items()},
                resources=len(actual_resources['files']),all_resource_bytes_exact=True,
                DAT=dict(path=str((package/'NONINSTALLABLE.DAT').relative_to(out)),sha256=sha(package/'NONINSTALLABLE.DAT')) if package else None,
                RAW=expected['RAW'],
                ratios=['809/500','239/100','5/4','37/20'],menu_order=[0,4,1,6,2,7,5,3],
                camera_io=False,device_tested=False,
                limitations=['Reproduction and offline CPU evidence do not establish camera startup, LCD, encoding or file acceptance'])
    save(out/'build-result.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
