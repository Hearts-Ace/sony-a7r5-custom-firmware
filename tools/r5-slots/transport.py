"""Read-only transport helpers and independent raw verification."""
import datetime
import json
import re
import subprocess
from pathlib import Path
from filesystem import require
from sparse import SIZE, START_SECTOR
HOST=None
XTS_REFERENCE=None

def save(path, obj):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
    tmp.chmod(0o600)
    tmp.replace(path)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def execute(run, label, args, host=None):
    host = host or HOST/'read_fastboot_usb_all'
    log = run/(label+'.log')
    with log.open('x') as f:
        try:
            proc = subprocess.run([str(host), *map(str,args)],stdout=f,stderr=subprocess.STDOUT,text=True,timeout=60)
        finally:
            f.flush()
            print(log.read_text(),flush=True)
    output = log.read_text()
    require(proc.returncode == 0, label+' failed: '+str(proc.returncode))
    return output


def reboot(run, label='reboot'):
    out = execute(run,label,['reboot'],HOST/'read_fastboot_usb')
    require('COMMAND reboot\nREPLY OKAY' in out, 'No normal reboot acknowledgment')


def raw_verify(raw, logical):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    code = XTS_REFERENCE.read_text()
    arr = re.search(r'part_key\[64\]\s*=\s*\{(.*?)\}',code,re.S).group(1)
    key = bytes(int(v,16) for v in re.findall(r'0x([0-9a-fA-F]{2})',arr))
    require(len(key)==64 and len(raw)==len(logical)==SIZE, 'Invalid raw/XTS inputs')
    algo = algorithms.AES(key)
    for i in range(SIZE//512):
        dec = Cipher(algo,modes.XTS((START_SECTOR+i).to_bytes(16,'little'))).decryptor()
        require(dec.update(raw[i*512:(i+1)*512])+dec.finalize()==logical[i*512:(i+1)*512],
                'Independent AES-XTS mismatch at sector '+str(i))
