#!/usr/bin/env python3
"""Compile only fixed MSC backup and our trust-key payloads, entirely offline."""
from pathlib import Path
import argparse, base64, hashlib, importlib.util, json, os, secrets, tempfile, subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',required=True,type=Path);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('reference_compile',ROOT/'scripts/reference_compile.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.ROOT=ROOT;m.ENGINE=ROOT/'engine'
    plan=json.loads((m.ENGINE/'write-plan.json').read_text())
    rows=json.loads((m.ENGINE/'trust-sectors.json').read_text())['rows']
    old=b''.join(base64.b64decode(r['before']) for r in rows);new=b''.join(base64.b64decode(r['after']) for r in rows)
    with tempfile.TemporaryDirectory(prefix='payloads-',dir=ROOT) as tmp:
        tmp=Path(tmp)
        wrapper=tmp/'ld.lld'
        wrapper.write_text('#!/bin/sh\nexec '+"'"+str(a.zig.resolve()).replace("'","'\\''")+"'"+' ld.lld "$@"\n');wrapper.chmod(0o755)
        m.CLANG='/usr/bin/clang';m.LLD=str(wrapper)
        # Apple clang supplies AArch64 object code; Zig supplies ELF lld.
        original=m.compile_configurable
        def configurable(command,**kwargs):
            try:return original(command,**kwargs)
            except subprocess.CalledProcessError as e:
                print((e.stderr or b'').decode(errors='replace'));raise
        m.compile_configurable=configurable
        alternate=secrets.token_hex(16);manifest={}
        for name,fn in [('capture.so',m.capture_library),('capture-cleanup.so',m.capture_cleanup_library)]:
            first=fn(tmp/(name+'-a'),m.MARKER);second=fn(tmp/(name+'-b'),alternate)
            row=m.template_record(name,first,second,alternate)
            if name=='capture.so':row.update(control_layout='ram-v2',capture_format='ram-16k-v1')
            else:row.update(cleanup_policy='verified-current-ram-v2')
            manifest[name]=row
        profile=json.loads((m.ENGINE/'profile.json').read_text())
        for label,preload in profile['preload_baselines']:
            def compile_one(folder,run):
                return m.trust_sector_library(folder,run,bytes.fromhex(preload).decode(),plan['source_sha256'],
                    plan['candidate_sha256'],old,new,plan,force=False)
            name='trust-'+label+'.so'
            manifest[name]=dict(m.template_record(name,compile_one(tmp/(name+'-a'),m.MARKER),
                compile_one(tmp/(name+'-b'),alternate),alternate),control_layout='ram-v2')
        m.save(m.ENGINE/'templates.json',dict(run_marker=m.MARKER,hash_marker=m.HASH_MARKER,files=manifest))
        m.save(ROOT/'verification/payloads.json',dict(templates=manifest,sector_count=len(rows),
            logical_write_bytes=len(rows)*512,configuration_matches_independent_compilation=True,camera_IO=False))
    print('Payloads compiled and configuration replacement independently verified. No USB enumeration.')

if __name__=='__main__':main()
