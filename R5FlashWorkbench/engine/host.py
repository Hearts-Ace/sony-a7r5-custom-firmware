# Adapted for R5FlashWorkbench, 2026-10-29. See THIRD_PARTY_NOTICES.md.
"""只在用户操作或恢复检查时观察主机元数据；不初始化USB后端。"""
from collections import Counter
import plistlib
import subprocess
import time


def physical_port(location):
    if type(location) is not int or not 0 < location <= 0xffffffff:
        raise ValueError('USB位置未知')
    ports = []
    ended = False
    for shift in (20, 16, 12, 8, 4):
        value = (location >> shift) & 15
        if value == 0:ended = True
        elif ended:raise ValueError('USB端口拓扑不连续')
        else:ports.append(value)
    if not ports or location & 15:
        raise ValueError('USB端口不能绑定到已知拓扑')
    return location >> 24, ports


def parse(tree, location=None):
    found = []
    def walk(node):
        if node.get('IOObjectClass') == 'IOUSBHostDevice' and node.get('idVendor') == 0x054c:
            found.append(node)
        for child in node.get('IORegistryEntryChildren', []):walk(child)
    for node in tree:walk(node)
    if not found:return dict(kind='absent', present=False)
    if len(found) != 1:raise ValueError('请只连接一台Sony相机')
    node = found[0];observed = node.get('locationID');pid = node.get('idProduct')
    physical_port(observed)
    if pid not in (0x0e0a, 0x0336, 0x096f):
        raise ValueError('当前USB模式未适配，请在相机上选择MSC')
    if location is not None and observed != location:
        raise ValueError('本次检查期间USB位置变化，请重新发起检查')
    result = dict(kind={0x0e0a:'ordinary', 0x0336:'service', 0x096f:'transition'}[pid], location_id=observed,
                  pid=pid, media=[], drivers=[], observed_product=node.get('USB Product Name'))
    if pid != 0x0e0a:return result
    if node.get('USB Product Name') != 'ILCE-7RM5':raise ValueError('仅支持A7R5（ILCE-7RM5）')
    result['model'] = 'ILCE-7RM5'
    def collect(item):
        kind = item.get('IOObjectClass', '')
        if 'MassStorage' in kind:result['drivers'].append(kind)
        if 'BSD Name' in item:
            size = item.get('Size')
            if type(size) is not int or size <= 0:raise ValueError('媒体容量元数据无效')
            result['media'].append([bool(item.get('Whole')), size])
        for child in item.get('IORegistryEntryChildren', []):collect(child)
    collect(node);result['media'].sort();result['drivers'] = sorted(set(result['drivers']))
    return result


def snapshot(out, label, timeout=5, location=None):
    raw = subprocess.run(['/usr/sbin/ioreg', '-a', '-l', '-r', '-c', 'IOUSBHostDevice'],
                         capture_output=True, check=True, timeout=timeout).stdout
    (out/(label+'.plist')).write_bytes(raw)
    return parse(plistlib.loads(raw), location)


def observe(baseline, take, seconds=45, interval=2, *, clock=time.monotonic, sleep=time.sleep):
    if not 0 < seconds <= 45 or not 0 < interval <= seconds:raise ValueError('观察范围无效')
    media = Counter(tuple(row) for row in baseline['media']);drivers = set(baseline['drivers'])
    if not media or not drivers:raise ValueError('缺少当前媒体基线')
    begin = clock();stable = 0;proof = dict(recovered=False, observations=[], camera_protocol_requests=0)
    for number in range(32):
        left = seconds-(clock()-begin)
        if left <= 0:break
        value = take('host-'+str(number), timeout=min(5, left))
        if value.get('location_id') not in (None, baseline['location_id']):raise ValueError('恢复位置不符')
        if value['kind'] == 'ordinary':
            now_media = Counter(tuple(row) for row in value['media']);now_drivers = set(value['drivers'])
            if now_media-media or now_drivers-drivers:raise ValueError('出现基线之外的媒体或驱动')
            stable = stable+1 if now_media == media and now_drivers == drivers else 0
        else:stable = 0
        proof['observations'].append(value)
        if stable >= 2:return dict(proof, recovered=True)
        sleep(min(interval, max(0, seconds-(clock()-begin))))
    return proof
