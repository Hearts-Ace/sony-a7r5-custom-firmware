# Adapted for R5FlashWorkbench, 2026-10-29. See THIRD_PARTY_NOTICES.md.
#!/usr/bin/env python3
"""只在开发机准备独立运行材料；不导入USB后端，不访问相机。"""
import argparse
import ast
import base64
import gzip
import hashlib
import importlib.util
import itertools
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
PREPARED = ROOT/'prepared'
ENGINE = PREPARED/'engine'
MARKER = 'd9a7216bc84f305e92a16bd4c7e038f5'
HASH_MARKER = '$6$rounds=10000$Q8j3k9w2s7m4n6p1$' + ''.join(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789./'[b % 64]
    for b in hashlib.shake_256(b'a7r5-desktop-template-not-a-password').digest(86))
CLANG = '/opt/homebrew/opt/llvm/bin/clang'
LLD = '/opt/homebrew/opt/lld/bin/ld.lld'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def copy_tree(source, destination):
    shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=False,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store', 'test', 'tests', '.git'))


def jit_values(run):
    prefix = '/tmp/jiritsu/a7r5-jit-' + run
    return dict(RUN_ID=run, STATE_PATH=prefix+'.state', STATE_NEW=prefix+'.state.new',
                OUTPUT_PATH=prefix+'.output', CLAIM_PATH=prefix+'.claim', TICKET_PATH=prefix+'.ticket',
                TICKET_BYTES='A7R5_LIBJIT '+run+'\n', LIBJIT_PATH='/tmp/jiritsu/libJit.so')


def ram_jit_values(run):
    control='/tmp_wbshd/a7r5-control-'+run
    values=jit_values(run)
    values.update({key:control+'/task'+suffix for key,suffix in (
        ('STATE_PATH','.state'),('STATE_NEW','.state.new'),('OUTPUT_PATH','.output'),('CLAIM_PATH','.claim'))})
    values.update(TICKET_PATH=control+'.ticket',CAPTURE_CONTROL_PARENT='/tmp_wbshd',CAPTURE_CONTROL_DIR=control)
    return values


def header(path, values):
    path.write_text(''.join('#define '+k+' '+json.dumps(v)+'\n' for k, v in values.items()))


def compile_configurable(command, *, run, password_hash=None, **kwargs):
    """将可变字符串放入单独编译的配置段，避免字符串合并和指令常量化。"""
    source = next(Path(v) for v in command if str(v).endswith('.c'))
    output = Path(command[command.index('-o')+1])
    include_args = []
    for index, value in enumerate(command):
        if value == '-I':include_args += ['-I', str(command[index+1])]
    text = subprocess.run([CLANG, '--target=aarch64-linux-gnu', '-E', '-P', *include_args, str(source)],
                          capture_output=True, text=True, check=True).stdout
    declarations, definitions = [], []
    strings = re.compile(r'"(?:\\.|[^"\\])*"(?:\s*"(?:\\.|[^"\\])*")*')
    lengths = {}
    def extract(match):
        pieces = re.findall(r'"(?:\\.|[^"\\])*"', match[0])
        if run not in match[0] and (password_hash is None or password_hash not in match[0]):return match[0]
        value = ''.join(ast.literal_eval(piece) for piece in pieces)
        name = 'desktop_config_'+str(len(declarations));size = len(value.encode())+1
        lengths[name] = size
        declarations.append(f'extern char {name}[{size}];')
        definitions.append(f'__attribute__((used,section(".a7r5_cfg"))) char {name}[{size}]='+json.dumps(value)+';')
        return name
    text = strings.sub(extract, text)
    # C局部数组仍保留原来的大小和sizeof语义，从外部配置段初始化。
    def initialize(match):
        variable, field = match[1], match[2]
        size = lengths[field]
        return f'char {variable}[{size}];__builtin_memcpy({variable},{field},{size});'
    text = re.sub(r'const\s+char\s+(\w+)\[\s*\]\s*=\s*(desktop_config_\d+)\s*;', initialize, text)
    body = output.parent/'desktop-body.c';config = output.parent/'desktop-config.c'
    body.write_text('\n'.join(declarations)+'\n'+text)
    config.write_text('\n'.join(definitions)+'\n')
    revised = [str(body) if str(v) == str(source) else str(v) for v in command]
    return subprocess.run([*revised, str(config), '-Wl,-O0', '-Wno-unused-but-set-variable'], **kwargs)


def compile_library(directory, source, run):
    output = directory/'libJit.so'
    command = [CLANG, '--target=aarch64-linux-gnu', '--ld-path='+LLD, '-nostdlib',
               '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fPIC', '-shared',
               '-fvisibility=hidden', '-O2', '-Wall', '-Wextra', '-Werror', '-Wl,-O0', '-Wl,--no-undefined',
               '-Wl,-z,max-page-size=65536', '-Wl,-init,_init', '-I', str(directory),
               '-I', str(ROOT/'sources/trust'), str(source), '-o', str(output)]
    compile_configurable(command, run=run, check=True, capture_output=True)
    return output.read_bytes()


def capture_shape(part_bytes=16384):
    if part_bytes not in (16384,262144):raise ValueError('未知捕获编译布局')
    count=(25100288+part_bytes-1)//part_bytes
    return dict(CAPTURE_PART_BYTES=part_bytes,CAPTURE_PART_COUNT=count,
        CAPTURE_SUMMARY=f' bytes=25100288 twice=1 chunks={count} chunk_bytes={part_bytes}\n')


def capture_library(directory, run, *, probe=False, part_bytes=16384):
    directory.mkdir()
    profile = json.loads((ROOT/'engine/profile.json').read_text())
    control='/tmp_wbshd/a7r5-control-'+run
    header(directory/'jit_config.h', ram_jit_values(run))
    header(directory/'capture_config.h', dict(CAPTURE_TARGET='/dev/cnflasha1',
        **capture_shape(part_bytes), CAPTURE_RAM_PARENT='/tmp_wbshd', CAPTURE_RAM_DIR='/tmp_wbshd/a7r5-capture-'+run,
        CAPTURE_PATH='/tmp_wbshd/a7r5-capture-'+run+'/partition.bin',
        CAPTURE_BEGIN='A7R5_CAPTURE_BEGIN '+run+'\n', CAPTURE_END='A7R5_CAPTURE_END '+run+'\n',
        PRELOAD_A=bytes.fromhex(profile['preload_baselines'][0][1]).decode(),
        PRELOAD_B=bytes.fromhex(profile['preload_baselines'][1][1]).decode()))
    if probe:
        header(directory/'work_probe_config.h',dict(PROBE_SOURCE='/dev/cnflasha6',
            PROBE_DATA_PATH=control+'/task.work-root',PROBE_BEGIN='A7R5_WORK_PROBE_BEGIN '+run+'\n',
            PROBE_END='A7R5_WORK_PROBE_END '+run+'\n'))
    source = (ROOT/'sources/trust/libjit-trust.c').read_text().replace(
        '#include "native_gate.c"', '#include "work_probe.c"' if probe else '#include "capture_gate.c"').replace(
        'A7R5_TRUST_PRODUCTION_V2', 'A7R5_WORK_PROBE_READONLY_V2_RAM_BOOTSTRAP' if probe else ('A7R5_CAPTURE_READONLY_V5_RAM_16K' if part_bytes==16384 else 'A7R5_CAPTURE_READONLY_V4_RAM_BOOTSTRAP'))
    (directory/'capture-wrapper.c').write_text(source)
    return compile_library(directory, directory/'capture-wrapper.c', run)


def capture_cleanup_library(directory, run):
    directory.mkdir()
    profile=json.loads((ROOT/'engine/profile.json').read_text())
    control='/tmp_wbshd/a7r5-cleanup-'+run
    values=ram_jit_values(run)
    values.update({key:control+'/task'+suffix for key,suffix in (
        ('STATE_PATH','.state'),('STATE_NEW','.state.new'),('OUTPUT_PATH','.output'),('CLAIM_PATH','.claim'))})
    values.update(TICKET_PATH=control+'.ticket',CAPTURE_CONTROL_DIR=control)
    header(directory/'jit_config.h',values)
    header(directory/'cleanup_config.h',dict(**capture_shape(),CLEANUP_PARENT='/tmp_wbshd',
        CLEANUP_DIRECTORY='a7r5-capture-'+run,SOURCE_CONTROL_DIRECTORY='a7r5-control-'+run,
        CAPTURE_BEGIN='A7R5_CAPTURE_BEGIN '+run+'\n',CAPTURE_END='A7R5_CAPTURE_END '+run+'\n',
        PRELOAD_A=bytes.fromhex(profile['preload_baselines'][0][1]).decode(),
        PRELOAD_B=bytes.fromhex(profile['preload_baselines'][1][1]).decode()))
    source=(ROOT/'sources/trust/libjit-trust.c').read_text().replace(
        '#include "native_gate.c"','#include "capture_cleanup.c"').replace(
        'A7R5_TRUST_PRODUCTION_V2','A7R5_CAPTURE_CLEANUP_V2_RAM_16K')
    (directory/'cleanup-wrapper.c').write_text(source)
    return compile_library(directory,directory/'cleanup-wrapper.c',run)


def trust_library(directory, run, preload, before, after, plan):
    rows = plan['rows']
    old = b''.join(before[r['offset']:r['offset']+512] for r in rows)
    new = b''.join(after[r['offset']:r['offset']+512] for r in rows)
    return trust_sector_library(directory,run,preload,sha(before),sha(after),old,new,plan)


def trust_sector_library(directory,run,preload,source_sha,target_sha,old,new,plan,*,force=False,precheck=False,sector_readback=True,planned_resource_budget=True):
    directory.mkdir()
    header(directory/'jit_config.h',dict(**ram_jit_values(run),TRUST_USER_CHECK_DIAGNOSTICS=1,TRUST_RESOURCE_CHECK_DIAGNOSTICS=1))
    if precheck:
        if not force:raise ValueError('只读检查必须使用独立诊断模板')
        with (directory/'jit_config.h').open('a') as stream:stream.write('#define TRUST_PRECHECK_ONLY 1\n')
    rows=plan['rows']
    ram = '/tmp_wbshd/a7r5-trust-'+run
    header(directory/'trust_config.h', dict(ORIGINAL_SHA=source_sha, CANDIDATE_SHA=target_sha, TRUST_FORCE_MODE=int(force),
        TRUST_FORCE_SECTOR_READBACK=int(force and sector_readback),
        TRUST_PLANNED_RESOURCE_BUDGET=int(force and sector_readback and planned_resource_budget),
        BEFORE_PATCH_SHA=sha(old), AFTER_PATCH_SHA=sha(new), RAM_DIR=ram,
        JOURNAL_PATH=ram+'/journal', READBACK_PATH=ram+'/partition.logical', EXPECTED_PRELOAD=preload,
        OUTPUT_BEGIN='A7R5_TRUST_BEGIN_'+run+'\n', OUTPUT_END='A7R5_TRUST_END_'+run+'\n', TARGET_PATH='/dev/cnflasha1'))
    if force:
        profile=json.loads((ROOT/'engine/profile.json').read_text())
        with (directory/'trust_config.h').open('a') as stream:
            for key,row in zip(('FORCE_PRELOAD_A','FORCE_PRELOAD_B'),profile['preload_baselines']):
                stream.write('#define '+key+' '+json.dumps(bytes.fromhex(row[1]).decode())+'\n')
    with (directory/'trust_config.h').open('a') as stream:
        stream.write('#define PARTITION_BYTES 25100288UL\n#define PATCH_COUNT 26U\n')
        if not precheck:
            stream.write('static const unsigned long PATCH_OFFSETS[]={'+','.join(str(r['offset'])+'UL' for r in rows)+'};\n')
            stream.write('static const unsigned char PATCH_CHECKSUM[]={'+','.join(str(int(r['phase']=='checksum')) for r in rows)+'};\n')
            for name, raw in [('BEFORE_SECTORS', old), ('AFTER_SECTORS', new)]:
                stream.write('static const unsigned char '+name+'[]={'+','.join(str(b) for b in raw)+'};\n')
    source=(ROOT/'sources/trust/libjit-trust.c').read_text().replace(
        'A7R5_TRUST_PRODUCTION_V2','A7R5_TRUST_PRECHECK_ONLY_V1' if precheck else
        ('A7R5_TRUST_FORCE_V3_RESOURCE_BUDGET' if sector_readback and planned_resource_budget else
         'A7R5_TRUST_FORCE_V2_SECTOR_READBACK' if sector_readback else 'A7R5_TRUST_FORCE_V1_RAM_16K') if force
        else 'A7R5_TRUST_PRODUCTION_V3_RAM_BOOTSTRAP')
    (directory/'trust-wrapper.c').write_text(source)
    return compile_library(directory,directory/'trust-wrapper.c',run)


def template_record(name, raw, alternate, run, *, hash_value=None):
    from elftools.elf.elffile import ELFFile
    import io
    elf = ELFFile(io.BytesIO(raw))
    assert elf['e_machine'] == 'EM_AARCH64' and elf['e_type'] == 'ET_DYN'
    ranges = [(s['sh_offset'], s['sh_offset']+s['sh_size']) for s in elf.iter_sections()
              if s.name == '.a7r5_cfg']
    fields = [(MARKER.encode(), run.encode())]
    if hash_value:
        fields.append((HASH_MARKER.encode(), hash_value.encode()))
    patched = raw
    counts = {}
    for old, new in fields:
        assert len(old) == len(new)
        positions = []
        start = 0
        while (at := raw.find(old, start)) >= 0:
            assert any(a <= at and at+len(old) <= b for a, b in ranges), (name, '模板字段位于非数据段')
            positions.append(at);start = at+len(old)
        # 部分SSH程序不使用密码哈希，允许相应字段不存在。
        counts['run' if old == MARKER.encode() else 'password_hash'] = len(positions)
        patched = patched.replace(old, new)
    assert patched == alternate, (name, '配置替换与独立编译结果不一致，禁止打包')
    assert counts['run'] > 0
    target = ENGINE/'templates'/name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return dict(sha256=sha(raw), bytes=len(raw), fields=counts, configuration_matches_compilation=True)

