#!/usr/bin/env python3
"""Build a relocatable macOS arm64 app. Offline; never enumerates USB."""
from pathlib import Path
import argparse, hashlib, json, os, plistlib, shutil, subprocess, tempfile, zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.2.1'
IGNORE=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store','.git','test','tests','SelfTest')
def copytree(source,target):shutil.copytree(source,target,ignore=IGNORE,symlinks=False)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def run(*args,**kwargs):return subprocess.run(list(map(str,args)),check=True,**kwargs)
def macho(path):
    with path.open('rb') as f:return f.read(4) in (b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python-runtime',required=True,type=Path)
    p.add_argument('--extra-site',required=True,type=Path)
    p.add_argument('--firmware',required=True,type=Path)
    p.add_argument('--public-key',required=True,type=Path)
    p.add_argument('--sony-public-key',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--native-binary',type=Path)
    a=p.parse_args();out=a.output.resolve()
    if out.exists():p.error('Output must be new')
    if sha(a.public_key)!='4cb3cf8cc7a847a5b6108863c2defa327ceb06280c1dda468cd57c3dd3cae859':p.error('Wrong public key')
    if sha(a.sony_public_key)!='8281413b5607446939613e07d020b2c7d8ee2371349099de56bc8288f7be0a43':p.error('Wrong original public key')
    out.mkdir(parents=True);app=out/'R5 刷写工作台.app';contents=app/'Contents';res=contents/'Resources';mac=contents/'MacOS'
    res.mkdir(parents=True);mac.mkdir()
    copytree(ROOT/'engine',res/'engine');engine=res/'engine'
    copytree(ROOT/'licenses',res/'licenses')
    for name in ('README.md','AI_GUIDE.md','AGENTS.md','THIRD_PARTY_NOTICES.md','REFERENCE.json'):
        shutil.copyfile(ROOT/name,res/name)
    (res/'firmware').mkdir();copytree(a.firmware,res/'firmware/r5')
    shutil.copyfile(a.public_key,engine/'public.pem')
    shutil.copyfile(a.sony_public_key,engine/'sony-public.pem')
    # Copy the standalone interpreter and stdlib, excluding unrelated workspace packages.
    runtime=res/'python';(runtime/'bin').mkdir(parents=True);(runtime/'lib').mkdir()
    shutil.copyfile(a.python_runtime/'bin/python3.12',runtime/'bin/python3.12');(runtime/'bin/python3.12').chmod(0o755)
    shutil.copyfile(a.python_runtime/'lib/libpython3.12.dylib',runtime/'lib/libpython3.12.dylib')
    shutil.copytree(a.python_runtime/'lib/python3.12',runtime/'lib/python3.12',
        ignore=shutil.ignore_patterns('site-packages','__pycache__','*.pyc','test','tests','tkinter','idlelib','ensurepip'))
    (runtime/'lib/python3.12/site-packages').mkdir()
    licenses=res/'licenses/python';licenses.mkdir()
    for name in ('LICENSE.txt','LICENSE','PYTHON_LICENSE'):
        if (a.python_runtime/name).exists():shutil.copyfile(a.python_runtime/name,licenses/name)
    (engine/'lib').mkdir(exist_ok=True)
    source_site=a.python_runtime/'lib/python3.12/site-packages'
    for pattern in ('numpy','numpy.libs','numpy-*.dist-info','cryptography','cryptography-*.dist-info','cffi','cffi-*.dist-info','_cffi_backend*.so'):
        for source in source_site.glob(pattern):
            target=runtime/'lib/python3.12/site-packages'/source.name
            if source.is_dir():copytree(source,target)
            else:shutil.copyfile(source,target)
    for pattern in ('Cryptodome','pycryptodomex-*.dist-info','capstone','capstone-*.dist-info','elftools','pyelftools-*.dist-info'):
        for source in a.extra_site.glob(pattern):copytree(source,runtime/'lib/python3.12/site-packages'/source.name)
    shutil.copyfile(a.extra_site/'libusb_package/libusb-1.0.dylib',engine/'lib/libusb-1.0.dylib')
    for name in ('LICENSE','COPYING','LICENSE.txt'):
        for source in a.extra_site.glob('libusb_package-*.dist-info/licenses/**/'+name):
            shutil.copyfile(source,res/'licenses'/('libusb-'+name))
    # Runtime dependencies must resolve inside the app or to Apple system libraries.
    native=[]
    for path in res.rglob('*'):
        if not path.is_file() or not macho(path):continue
        native.append(path)
        identities=run('/usr/bin/otool','-arch','arm64','-D',path,capture_output=True,text=True).stdout.splitlines()[1:]
        identity=identities[0].strip() if identities else None
        deps=run('/usr/bin/otool','-arch','arm64','-L',path,capture_output=True,text=True).stdout.splitlines()[1:]
        for row in deps:
            dependency=row.strip().split(' (',1)[0]
            if dependency.startswith(('/usr/lib/','/System/Library/','@')):continue
            # First dylib entry is its own install identity.
            if dependency==identity:continue
            raise ValueError('Nonrelocatable native dependency: '+str(path)+' -> '+dependency)
        if identity:run('/usr/bin/install_name_tool','-id','@loader_path/'+path.name,path,capture_output=True)
        run('/usr/bin/codesign','--force','--sign','-',path,capture_output=True)
    lock={str(p.relative_to(engine)):sha(p) for p in sorted(engine.rglob('*')) if p.is_file() and p.name!='resources.lock.json'}
    save(engine/'resources.lock.json',lock)
    info=dict(CFBundleName='R5 刷写工作台',CFBundleDisplayName='R5 刷写工作台',CFBundleExecutable='R5Workbench',
        CFBundleIdentifier='research.heartsace.r5flashworkbench',CFBundleVersion='3',CFBundleShortVersionString=VERSION,
        CFBundlePackageType='APPL',LSMinimumSystemVersion='14.0',NSHighResolutionCapable=True,
        NSHumanReadableCopyright='Personal noncommercial research; see bundled third-party notices.')
    (contents/'Info.plist').write_bytes(plistlib.dumps(info))
    if a.native_binary:shutil.copyfile(a.native_binary,mac/'R5Workbench');(mac/'R5Workbench').chmod(0o755)
    else:
        run('/usr/bin/xcrun','swiftc','-swift-version','5','-parse-as-library','-O','-target','arm64-apple-macosx14.0',
            '-module-cache-path',out/'swift-cache',ROOT/'native/Workbench.swift','-o',mac/'R5Workbench')
    launcher=mac/'r5wb'
    run('/usr/bin/xcrun','clang','-O2','-Wall','-Wextra','-Werror','-target','arm64-apple-macosx14.0',
        ROOT/'native/CLI.c','-o',launcher)
    run('/usr/bin/codesign','--force','--sign','-',launcher,capture_output=True)
    run('/usr/bin/codesign','--force','--sign','-',app,capture_output=True)
    run('/usr/bin/codesign','--verify','--deep','--strict',app,capture_output=True)
    # Relocation check: exercise isolated Python imports from a fresh application path.
    check=run(runtime/'bin/python3.12','-I','-B',engine/'bootstrap.py','selfcheck',capture_output=True,text=True,cwd='/private/tmp')
    result=json.loads(check.stdout);save(out/'offline-selfcheck.json',result)
    save(out/'build.json',dict(version=VERSION,firmware='4.36',platform='macOS-arm64',minimum_target='14.0',
        app=str(app),ad_hoc_signed=True,notarized=False,camera_IO=False,USB_enumerated=False,
        firmware_private_key_included=False,original_firmware_included=False,native_libraries=len(native),
        native_source_sha256=sha(ROOT/'native/Workbench.swift'),firmware_source_lock_sha256=sha(a.firmware/'sources.lock.json')))
    archive=out/('R5FlashWorkbench-macOS-arm64-'+VERSION+'.zip')
    run('/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',app,archive)
    (out/'SHA256SUMS').write_text(sha(archive)+'  '+archive.name+'\n')
    print('Built:',app,'\nZIP:',archive)

if __name__=='__main__':main()
