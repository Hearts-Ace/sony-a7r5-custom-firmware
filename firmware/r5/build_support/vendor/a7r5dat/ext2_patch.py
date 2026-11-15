"""冻结的ext2局部替换器；保留inode，允许小资源增长。"""
import struct
from .ext2read import Ext2

def require(value, message):
    if not value:
        raise ValueError(message)


def reader(raw):
    require(len(raw) >= 2048 and raw[1080:1082] == b'\x53\xef', '不是 ext2')
    e = Ext2.__new__(Ext2)
    e.mm = raw
    e.inodes_count, e.blocks_count = struct.unpack_from('<II', raw, 1024)
    log_size = struct.unpack_from('<I', raw, 1048)[0]
    require(log_size <= 2, '不支持的块大小')
    e.block_size = 1024 << log_size
    e.blocks_per_group = struct.unpack_from('<I', raw, 1056)[0]
    e.inodes_per_group = struct.unpack_from('<I', raw, 1064)[0]
    e.inode_size = struct.unpack_from('<H', raw, 1112)[0]
    require(0 < e.blocks_per_group <= e.block_size*8 and e.inodes_per_group > 0, '块组几何无效')
    e.bgd_off = max(e.block_size, 2048)
    return e


class Patch:
    def __init__(self, raw):
        self.source = raw
        self.data = bytearray(raw)
        self.fs = reader(self.data)
        self.bs = self.fs.block_size
        self.first = struct.unpack_from('<I', raw, 1044)[0]
        compat, incompat, ro = struct.unpack_from('<3I', raw, 1116)
        require(self.bs in (1024, 2048, 4096) and self.fs.blocks_count*self.bs == len(raw), '文件系统几何不支持')
        require(incompat == 2 and ro & ~3 == 0 and not compat & 4, '拒绝日志、extents 或未知特性')
        require(self.fs.inode_size in (128, 256) and self.first == int(self.bs == 1024), 'inode 或首块几何不支持')
        self.groups = (self.fs.blocks_count-self.first+self.fs.blocks_per_group-1)//self.fs.blocks_per_group
        self.allocated = []
        self.changed_files = []
        self._validate_free()

    def _validate_free(self):
        total = 0
        for group in range(self.groups):
            d = self.fs.bgd_off+group*32
            bitmap = struct.unpack_from('<I', self.data, d)[0]
            require(0 < bitmap < self.fs.blocks_count, '位图块越界')
            valid = min(self.fs.blocks_per_group, self.fs.blocks_count-self.first-group*self.fs.blocks_per_group)
            bits = int.from_bytes(self.data[bitmap*self.bs:(bitmap+1)*self.bs], 'little')
            count = valid-bin(bits & ((1 << valid)-1)).count('1')
            require(count == struct.unpack_from('<H', self.data, d+12)[0], '组空闲计数与位图不一致')
            total += count
        require(total == struct.unpack_from('<I', self.data, 1036)[0], '超级块空闲计数不一致')

    def inode_offset(self, inode):
        require(1 <= inode <= self.fs.inodes_count, 'inode 越界')
        group, index = divmod(inode-1, self.fs.inodes_per_group)
        return self.fs.inode_table(group)*self.bs+index*self.fs.inode_size

    def allocate(self, preferred):
        for step in range(self.groups):
            group = (preferred+step) % self.groups
            d = self.fs.bgd_off+group*32
            free = struct.unpack_from('<H', self.data, d+12)[0]
            if not free:
                continue
            bitmap = struct.unpack_from('<I', self.data, d)[0]*self.bs
            valid = min(self.fs.blocks_per_group, self.fs.blocks_count-self.first-group*self.fs.blocks_per_group)
            for index in range(valid):
                byte, mask = bitmap+index//8, 1 << (index % 8)
                if self.data[byte] & mask:
                    continue
                block = self.first+group*self.fs.blocks_per_group+index
                require(block not in self.allocated and block > 0, '块分配重复或越界')
                self.data[byte] |= mask
                struct.pack_into('<H', self.data, d+12, free-1)
                super_free = struct.unpack_from('<I', self.data, 1036)[0]
                require(super_free > 0, '超级块空闲计数下溢')
                struct.pack_into('<I', self.data, 1036, super_free-1)
                self.data[block*self.bs:(block+1)*self.bs] = bytes(self.bs)
                self.allocated.append(block)
                return block
        raise ValueError('空闲块不足')

    def replace(self, path, expected, target):
        require(path.startswith('/') and '..' not in path.split('/'), '目标路径异常')
        inode = self.fs.walk(path)
        off = self.inode_offset(inode)
        mode, size, pointers = self.fs.inode(inode)
        require(mode & 0xf000 == 0x8000 and not struct.unpack_from('<I', self.data, off+32)[0] & 0x80000,
                '目标不是普通块映射文件')
        require(self.fs.read_inode(inode) == expected and len(expected) == size, '目标内容前像不符')
        require(len(target) >= size and len(target) < 1 << 32, '拒绝收缩或超大文件')
        require(not any(row['inode'] == inode for row in self.changed_files), '重复 inode 目标')
        blocks = self.fs.inode_blocks(inode)
        require(len(blocks) == (size+self.bs-1)//self.bs and all(blocks) and len(set(blocks)) == len(blocks),
                '目标稀疏、块重复或映射不完整')
        need = (len(target)+self.bs-1)//self.bs
        # 现有大 AP 可以有双/三级间接块；本工具只允许小资源文件增长。
        require(need == len(blocks) or need <= 12+self.bs//4, '拒绝双/三级间接块增长')
        before_inode = bytes(self.data[off:off+self.fs.inode_size])
        allocated_before = len(self.allocated)
        group = (inode-1)//self.fs.inodes_per_group
        while len(blocks) < need:
            index = len(blocks)
            if index >= 12 and not pointers[12]:
                pointers[12] = self.allocate(group)
                struct.pack_into('<I', self.data, off+40+12*4, pointers[12])
            pointer_at = off+40+index*4 if index < 12 else pointers[12]*self.bs+(index-12)*4
            require(struct.unpack_from('<I', self.data, pointer_at)[0] == 0, '新增块指针已有占用')
            block = self.allocate(group)
            struct.pack_into('<I', self.data, pointer_at, block)
            blocks.append(block)
        for index, block in enumerate(blocks):
            data = target[index*self.bs:(index+1)*self.bs]
            self.data[block*self.bs:block*self.bs+len(data)] = data
        struct.pack_into('<I', self.data, off+4, len(target))
        added = len(self.allocated)-allocated_before
        sectors = struct.unpack_from('<I', self.data, off+28)[0]
        struct.pack_into('<I', self.data, off+28, sectors+added*(self.bs//512))
        require(self.fs.read_inode(inode) == target, '替换后内容回读不符')
        # mode/uid/gid、时间、链接数、标志、扩展属性等保持原状。
        allowed = set(range(4, 8)) | set(range(28, 32)) | set(range(40, 100))
        after_inode = self.data[off:off+self.fs.inode_size]
        require(all(a == b for i, (a, b) in enumerate(zip(before_inode, after_inode)) if i not in allowed),
                '非目标 inode 属性变化')
        self.changed_files.append({'path': path, 'inode': inode, 'before_bytes': size,
            'after_bytes': len(target), 'new_allocated_blocks': added})

    def finish(self):
        self._validate_free()
        return bytes(self.data), {'changed_files': self.changed_files, 'new_blocks': self.allocated,
            'filesystem_size_unchanged': len(self.data) == len(self.source),
            'inode_identity_and_unrelated_attributes_preserved': True}
