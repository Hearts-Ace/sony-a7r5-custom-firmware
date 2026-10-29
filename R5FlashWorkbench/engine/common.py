# Adapted for R5FlashWorkbench, 2026-10-29. See THIRD_PARTY_NOTICES.md.
"""独立运行路径、受限文件和回执；不查询设备。"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parent
SOURCE_SHA = 'd6cb0eb25e78dbfa09d29225485cc204b773d533d301af1ec54ea7bd2d1e1181'
TARGET_SHA = '7d17697fb83a26bbcd53f49f7c791fea7cdd9e372ad6f4510d1f079e643a0b05'
PARTITION_BYTES = 25100288


def safe(path, *, file=False):
    path = Path(path).absolute()
    if '..' in path.parts or path.is_relative_to('/dev') or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('请选择普通本机路径，不接受设备或符号链接')
    if file and not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('输入必须是普通文件')
    return path


def sha(path):
    with safe(path, file=True).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(safe(path, file=True).read_text())


def save(path, value):
    path = safe(path)
    raw = (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def progress(message):
    print(json.dumps(dict(progress=message), ensure_ascii=False), flush=True)


def render_template(name, run, password_hash=None):
    if not re.fullmatch('[0-9a-f]{32}', run):
        raise ValueError('本次会话号无效')
    manifest = load(ROOT/'templates.json')
    record = manifest['files'].get(name)
    if record is None:
        raise ValueError('未知预编译载荷')
    raw = safe(ROOT/'templates'/name, file=True).read_bytes()
    if len(raw) != record['bytes'] or digest(raw) != record['sha256']:
        raise ValueError('预编译载荷身份变化')
    marker = manifest['run_marker'].encode()
    if raw.count(marker) != record['fields']['run']:
        raise ValueError('会话字段数量变化')
    raw = raw.replace(marker, run.encode())
    hash_marker = manifest['hash_marker'].encode()
    expected = record['fields'].get('password_hash', 0)
    if expected:
        if not isinstance(password_hash, str) or not re.fullmatch(r'\$6\$rounds=10000\$[A-Za-z0-9./]{16}\$[A-Za-z0-9./]{86}', password_hash):
            raise ValueError('密码哈希格式不符')
        if raw.count(hash_marker) != expected or len(password_hash) != len(hash_marker):
            raise ValueError('密码字段数量或长度变化')
        raw = raw.replace(hash_marker, password_hash.encode())
    return raw


def write_payload(path, raw):
    path = safe(path)
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600);stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return path


def config(run, baseline):
    if not re.fullmatch('[0-9a-f]{32}', run):raise ValueError('会话号无效')
    profile = load(ROOT/'profile.json')
    # 接口格式仍固定；总线及端口绑定本次普通身份，不继承开发机历史位置。
    from host import physical_port
    bus, ports = physical_port(baseline['location_id'])
    for row in profile['interfaces'].values():
        row['bus'], row['ports'] = bus, ports
    profile.update(run_id=run, host_baseline=baseline, task_seconds=60, observe_seconds=60)
    return profile
