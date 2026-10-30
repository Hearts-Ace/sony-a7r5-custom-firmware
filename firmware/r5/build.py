#!/usr/bin/env python3
"""Only supported R5 4.36 build entry. Offline, no camera access."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys, tarfile

HERE=Path(__file__).resolve().parent
VERSION='4.36'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def apply_recipe(source,target,recipe):
    if sha(source)!=recipe['source_sha256']:raise ValueError('Unsupported source: '+str(source))
    shutil.copyfile(source,target)
    with target.open('r+b') as f:
        for row in recipe['patches']:
            before,after=bytes.fromhex(row['before']),bytes.fromhex(row['after'])
            assert len(before)==len(after)
            f.seek(row['offset']);assert f.read(len(before))==before
            f.seek(row['offset']);f.write(after)
    assert target.stat().st_size==recipe['bytes'] and sha(target)==recipe['target_sha256']

def integrate(source,target,component,name):
    from image_io import geometry
    before,offsets,unit,meta=geometry(source,name)
    payload=component.read_bytes();assert len(payload)==len(before)
    shutil.copyfile(source,target)
    with target.open('r+b') as f:
        for i,at in enumerate(offsets):
            block=payload[i*unit:(i+1)*unit];f.seek(at);f.write(block)
        f.flush();os.fsync(f.fileno())
    actual,o,u,m=geometry(target,name)
    assert actual==payload and (o,u,m)==(offsets,unit,meta)
    intervals=sorted((at,at+min(unit,len(payload)-i*unit)) for i,at in enumerate(offsets))
    with source.open('rb') as a,target.open('rb') as b:
        cursor=0
        for lo,hi in intervals:
            # Bounded reads even on unrelated large extents.
            left=lo-cursor
            while left:
                n=min(left,4<<20);assert a.read(n)==b.read(n);left-=n
            a.seek(hi);b.seek(hi);cursor=hi
        while True:
            x=a.read(4<<20);y=b.read(len(x));assert x==y
            if not x:break
    return dict(component_sha256=sha(component),partition_sha256=sha(target),
                original_partition_sha256=sha(source),all_other_bytes_unchanged=True)

def run(script,*args):
    subprocess.run([sys.executable,'-B',str(script),*map(str,args)],check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',required=True,type=Path,help='Private input path JSON; see inputs.example.json')
    p.add_argument('--output',required=True,type=Path,help='New empty output directory')
    p.add_argument('--stage',choices=('components','all'),default='all')
    a=p.parse_args()
    if not __debug__:p.error('Do not run with python -O: integrity assertions are required')
    out=a.output.resolve()
    if out.exists():p.error('Output must not exist; completed builds are immutable')
    if out==HERE or HERE.is_relative_to(out):p.error('Output cannot contain the source directory')
    config=json.loads(a.inputs.read_text());lock=json.loads((HERE/'inputs.lock.json').read_text())
    source_lock=json.loads((HERE/'sources.lock.json').read_text())
    for name,expected_digest in source_lock.items():
        assert sha(HERE/name)==expected_digest,('Source changed; update reviewed source lock',name)
    paths={key:Path(value).expanduser().resolve() for key,value in config.items()}
    for key,row in lock.items():
        source=paths[key]
        if not source.is_file() or source.stat().st_size!=row['bytes'] or sha(source)!=row['sha256']:
            raise ValueError('Wrong or unavailable original input: '+key)
    if a.stage=='all':
        private=paths['private_key']
        if private.stat().st_mode&0o777!=0o600:raise ValueError('Private key must have mode 0600')
    # All compilation happens in this new build tree, never in checked-in src.
    out.mkdir(parents=True)
    work=out/'work';shutil.copytree(HERE/'src',work)
    sys.path[:0]=[str(work/'lib'),str(work/'templates')]
    inputs=work/'inputs';inputs.mkdir()
    names={'original_dat':'original.DAT','original_fdat':'original.fdat',
           'updater':'updater.img','public_key':'public.pem','sony_public_key':'sony_public.pem'}
    if a.stage=='all':names['private_key']='private.pem'
    for key,name in names.items():(inputs/name).symlink_to(paths[key])
    recipes=json.loads((work/'dependencies/baseline_recipes.json').read_text())
    for key,src,dst in [('ap_baseline','stock_ap','ap_baseline.so'),
                        ('cp_baseline','stock_cp','cp_baseline.bin'),
                        ('nflasha15_layout','stock_nflasha15','nflasha15')]:
        apply_recipe(paths[src],inputs/dst,recipes[key])
    patched=out/'patched';patched.mkdir();evidence=out/'evidence';evidence.mkdir()
    apply_recipe(paths['stock_nflasha5'],patched/'nflasha5',recipes['nflasha5'])
    run(work/'import/build_ap_image.py','--output',patched)
    run(work/'gamma/getter_gates.py')
    run(work/'cp/build_cp.py')
    cp=work/'cp/cp423.NONINSTALLABLE.bin'
    shutil.copyfile(cp,patched/'cpapp-b.bin')
    partitions={
      'AP':integrate(inputs/'nflasha15',patched/'nflasha15',patched/'appFw.so','appFw.so'),
      'CP':integrate(paths['stock_nflasha8'],patched/'nflasha8',patched/'cpapp-b.bin','cpapp-b.bin')}
    from prepare_templates import build_templates
    replacements,templates=build_templates(paths['original_tar'],patched/'templates',expected_archive_sha256=lock['original_tar']['sha256'])
    save(evidence/'templates.json',templates)
    from image_io import update_sum,digest_stream
    from overlay import Overlay
    replacements.update({'0700_part_image/dev/'+name:patched/name for name in ('nflasha5','nflasha8','nflasha15')})
    with tarfile.open(paths['original_tar'],'r:') as t:
        members=t.getmembers();by={m.name:m for m in members};assert len(by)==len(members)
        name='0701_part_image_sum/part_image.sum'
        mapping={'dev/'+name:patched/name for name in ('nflasha5','nflasha8','nflasha15')}
        text,changes=update_sum(t.extractfile(name).read().decode('ascii'),mapping,{k:v.stat().st_size for k,v in mapping.items()})
        assert len(changes)==3
        sums=patched/'part_image.sum';sums.write_text(text);replacements[name]=sums
    ranges=[]
    for name,path in sorted(replacements.items(),key=lambda item:by[item[0]].offset_data):
        m=by[name];assert path.stat().st_size==m.size
        ranges.append((m.offset_data,m.offset_data+m.size,path))
    overlay=Overlay(paths['original_tar'],ranges)
    with overlay.open('rb') as f:archive_sha=digest_stream(f)
    facts=[]
    with tarfile.open(paths['original_tar'],'r:') as original,overlay.open('rb') as f,tarfile.open(fileobj=f,mode='r:') as result:
        assert [m.get_info() for m in original.getmembers()]==[m.get_info() for m in result.getmembers()]
        for m in members:
            if not m.isfile():continue
            before,after=digest_stream(original.extractfile(m)),digest_stream(result.extractfile(m))
            assert after==(sha(replacements[m.name]) if m.name in replacements else before)
            facts.append(dict(member=m.name,sha256=after,changed=before!=after))
    archive=dict(passed=True,output_sha256=archive_sha,changed_members=list(replacements),members=facts,
                 original_headers_padding_trailer_preserved=True)
    save(evidence/'archive_verification_436.json',archive)
    expected=json.loads((HERE/'expected_outputs.json').read_text())
    actual={'AP':sha(patched/'appFw.so'),'CP':sha(patched/'cpapp-b.bin'),
            'nflasha15':sha(patched/'nflasha15'),'nflasha8':sha(patched/'nflasha8'),
            'nflasha5':sha(patched/'nflasha5'),'archive':archive_sha}
    save(evidence/'computed_outputs.json',actual)
    for key,value in actual.items():
        assert value==expected[key],('Reproduction differs',key,value,expected[key])
    save(evidence/'components.json',dict(passed=True,version=VERSION,actual=actual,partitions=partitions,
         original_inputs=lock,source_sha256=sha(HERE/'sources.lock.json'),camera_io=False))
    if a.stage=='all':
        import package
        package.ROOT=work;package.OUT=out;package.TAR=overlay
        package.components=lambda:dict(upstream_commit='086df3b1e33dfa0206553ac2bb003535c58ddb80',
            components={n:dict(sha256=sha(patched/n)) for n in ('appFw.so','cpapp-b.bin','nflasha5')})
        original_digest=package.digest_file
        package.digest_file=lambda path:archive_sha if path is overlay else original_digest(path)
        package.build_package()
        assert sha(out/'BODYDATA.DAT')==expected['DAT'],'DAT differs from frozen 4.36'
        receipt=json.loads((out/'verification.json').read_text())
        receipt.update(exact_four_member_scope_verified=False,factory_defaults_and_backup_sum_unchanged=False,
            consolidated_source_build=True,source_input='original R5 4.00',
            custom_filter_Fn_automatically_assigned=False,AWB_white_priority=97,AWB_ambience=-1)
        save(out/'verification.json',receipt)
    # Record only public source identities; never store private key bytes.
    save(out/'build-result.json',dict(passed=True,version=VERSION,stage=a.stage,outputs=actual,
         DAT_sha256=sha(out/'BODYDATA.DAT') if a.stage=='all' else None,
         previous_version_scripts_required=False,previous_version_outputs_required=False,camera_io=False))
    print('R5 4.36 reproduced exactly:',out,flush=True)

if __name__=='__main__':main()
