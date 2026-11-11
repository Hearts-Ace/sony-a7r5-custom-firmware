"""在原 ext2 inode 上增长目标文件；支持 AP 的双重间接块，不改变分区长度。"""
import hashlib
import struct
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dat-tools'))
from a7r5dat.ext2_patch import Patch,require


class GrowingPatch(Patch):
    def pointer(self,inode_offset,pointers,index,group):
        n=self.bs//4
        if index<12:return inode_offset+40+index*4
        index-=12
        if index<n:root,indices=12,[index]
        else:
            index-=n
            if index<n*n:root,indices=13,[index//n,index%n]
            else:
                index-=n*n
                require(index<n*n*n,'文件超过 ext2 指针容量')
                root,indices=14,[index//(n*n),(index//n)%n,index%n]
        at=inode_offset+40+root*4
        for offset in indices:
            block=struct.unpack_from('<I',self.data,at)[0]
            if not block:
                block=self.allocate(group);struct.pack_into('<I',self.data,at,block)
                if at==inode_offset+40+root*4:pointers[root]=block
            require(0<block<self.fs.blocks_count,'间接块越界')
            at=block*self.bs+offset*4
        return at

    def replace(self,path,expected,target):
        inode=self.fs.walk(path);off=self.inode_offset(inode)
        mode,size,pointers=self.fs.inode(inode)
        blocks=self.fs.inode_blocks(inode);need=(len(target)+self.bs-1)//self.bs
        if need==len(blocks) or need<=12+self.bs//4:
            return super().replace(path,expected,target)
        require(path.startswith('/') and '..'not in path.split('/'),'目标路径异常')
        require(mode&0xf000==0x8000 and not struct.unpack_from('<I',self.data,off+32)[0]&0x80000,'文件类型不支持')
        require(self.fs.read_inode(inode)==expected and len(expected)==size,'目标前像不符')
        require(size<=len(target)<1<<32 and len(blocks)==(size+self.bs-1)//self.bs and all(blocks)
                and len(set(blocks))==len(blocks),'拒绝收缩/稀疏/重复块')
        require(not any(row['inode']==inode for row in self.changed_files),'重复 inode 目标')
        before_inode=bytes(self.data[off:off+self.fs.inode_size]);allocated_before=len(self.allocated)
        group=(inode-1)//self.fs.inodes_per_group
        while len(blocks)<need:
            at=self.pointer(off,pointers,len(blocks),group)
            require(struct.unpack_from('<I',self.data,at)[0]==0,'新增块指针已有占用')
            block=self.allocate(group);struct.pack_into('<I',self.data,at,block);blocks.append(block)
        for index,block in enumerate(blocks):
            content=target[index*self.bs:(index+1)*self.bs]
            self.data[block*self.bs:block*self.bs+len(content)]=content
        added=len(self.allocated)-allocated_before
        sectors=struct.unpack_from('<I',self.data,off+28)[0]
        struct.pack_into('<I',self.data,off+4,len(target));struct.pack_into('<I',self.data,off+28,sectors+added*(self.bs//512))
        require(self.fs.read_inode(inode)==target,'增长后内容回读失败')
        allowed=set(range(4,8))|set(range(28,32))|set(range(40,100))
        require(all(a==b for i,(a,b)in enumerate(zip(before_inode,self.data[off:off+self.fs.inode_size]))if i not in allowed),
                '非目标 inode 属性变化')
        self.changed_files.append(dict(path=path,inode=inode,before_bytes=size,after_bytes=len(target),new_allocated_blocks=added))


def files(fs):
    result={}
    def walk(inode,prefix):
        for child,name,kind in fs.dir_entries(inode):
            if name in ('.','..'):continue
            path=prefix+'/'+name
            mode,_,_=fs.inode(child)
            if mode&0xf000==0x4000:walk(child,path)
            elif mode&0xf000==0x8000:
                result[path]=(child,hashlib.sha256(fs.read_inode(child)).hexdigest())
    walk(2,'')
    return result


def non_regular_files(fs):
    """保留目录、链接和设备节点的完整身份；普通文件另由files检查。"""
    result={}
    def walk(inode,path):
        mode,size,_=fs.inode(inode)
        group,index=divmod(inode-1,fs.inodes_per_group)
        at=fs.inode_table(group)*fs.block_size+index*fs.inode_size
        record=bytes(fs.mm[at:at+fs.inode_size])
        if mode&0xf000!=0x8000:
            # 快速符号链接已包含在inode中，不能将内联目标当作块指针读取。
            content=fs.read_inode(inode) if mode&0xf000==0x4000 or (mode&0xf000==0xa000 and size>60) else b''
            result[path]=dict(inode=inode,mode=mode,
                inode_sha256=hashlib.sha256(record).hexdigest(),
                content_sha256=hashlib.sha256(content).hexdigest())
        if mode&0xf000==0x4000:
            for child,name,_ in fs.dir_entries(inode):
                if name not in ('.','..'):walk(child,path.rstrip('/')+'/'+name)
    walk(2,'/')
    return result


def verify_lut_layout(raw,required):
    """只核对包内挂载点，不访问或创建机内目录。"""
    from a7r5dat.ext2_patch import reader
    fs=reader(raw)
    try:inode=fs.walk('/data/lut')
    except KeyError:
        require(not required,'LUT功能依赖的/data/lut挂载目录缺失')
        return dict(passed=True,required=False,present=False,camera_io=False)
    mode,_,_=fs.inode(inode)
    parent=fs.walk('/data')
    require(mode==0o40755,'LUT挂载点不是原配方0755目录')
    require(list(fs.dir_entries(inode))==[(inode,'.',2),(parent,'..',2)],'LUT挂载目录内容异常')
    return dict(passed=True,required=bool(required),present=True,path='/data/lut',inode=inode,mode=mode,camera_io=False)


def patch_partition(raw,replacements):
    patch=GrowingPatch(raw);before=files(patch.fs);before_other=non_regular_files(patch.fs)
    for path,(expected,target)in replacements.items():patch.replace(path,expected,target)
    output,report=patch.finish();after=files(patch.fs)
    require(before.keys()==after.keys(),'分区目录集合改变')
    require(all(before[path]==after[path] for path in before if path not in replacements),'非目标文件改变')
    require(all(before[path][0]==after[path][0]for path in before),'inode 身份改变')
    require(non_regular_files(patch.fs)==before_other,'目录、符号链接或设备节点改变')
    report.update(passed=True,other_regular_files_preserved=len(before)-len(replacements),
        non_regular_entries_preserved=len(before_other),
        before_sha256=hashlib.sha256(raw).hexdigest(),sha256=hashlib.sha256(output).hexdigest())
    return output,report
