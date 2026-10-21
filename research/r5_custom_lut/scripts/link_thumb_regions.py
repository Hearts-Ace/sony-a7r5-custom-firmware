"""Small deterministic freestanding Thumb section linker for audited regions.

Only executable .text sections and branch relocations are accepted. Allocation
never spills across the caller's explicit regions and static ELF symbols are
resolved per object, rather than relying on section or function names.
"""
from pathlib import Path
import struct
from elftools.elf.elffile import ELFFile

def read_objects(objects):
    sections=[];symbols=[];relocations=[]
    for oi,obj in enumerate(objects):
        with Path(obj).open('rb') as f:
            e=ELFFile(f);sy=e.get_section_by_name('.symtab');indices={}
            for si,s in enumerate(e.iter_sections()):
                if s['sh_flags']&4 and s['sh_size']:
                    assert s.name.startswith('.text.'),(obj,s.name)
                    indices[si]=len(sections)
                    sections.append(dict(object=oi,name=s.name,data=s.data(),size=s['sh_size']))
                elif s['sh_flags']&2 and s['sh_size']:
                    assert s.name.startswith(('.ARM.exidx','.ARM.extab')),(obj,s.name,'unhandled allocated data')
            for si,sym in enumerate(sy.iter_symbols()):
                if sym['st_shndx'] in indices:
                    symbols.append(dict(object=oi,index=si,name=sym.name,section=indices[sym['st_shndx']],
                                        offset=sym['st_value'],global_symbol=sym['st_info']['bind']=='STB_GLOBAL'))
            for rs in e.iter_sections():
                if rs['sh_type']!='SHT_REL' or rs['sh_info'] not in indices:continue
                for r in rs.iter_relocations():
                    relocations.append(dict(object=oi,index=r['r_info_sym'],name=sy.get_symbol(r['r_info_sym']).name,
                        section=indices[rs['sh_info']],offset=r['r_offset'],kind=r['r_info_type']))
    return sections,symbols,relocations

def allocate(sections,regions,old_rx_required=(),new_rx_required=()):
    # First fit by the smallest remaining legal region, largest sections first.
    # Backtracking is bounded by the explicitly small number of RX regions.
    required={'.text.'+name for name in old_rx_required}
    new_required={'.text.'+name for name in new_rx_required}
    assert not required & new_required
    # Reject impossible layouts before exponential placement backtracking.
    # The search may rearrange sections but cannot create executable bytes.
    sizes=[(s['size']+3)&~3 for s in sections]
    assert sum(sizes)<=sum(size for _,size in regions), (
        'Audited executable space exhausted; no implicit region expansion',
        sum(sizes),sum(size for _,size in regions))
    for names,allowed in ((required,lambda a:a<0x1a00000),
                          (new_required,lambda a:a>=0x1a00000)):
        need=sum(size for size,s in zip(sizes,sections) if s['name'] in names)
        assert need<=sum(size for a,size in regions if allowed(a)), (
            'Required executable region exhausted',need)
    order=sorted(range(len(sections)),key=lambda i:(sections[i]['name']not in required,-((sections[i]['size']+3)&~3),i))
    used=[0]*len(regions);positions={};failed=set()
    def place(n):
        if n==len(order):return True
        key=(n,tuple(used))
        if key in failed:return False
        i=order[n];size=(sections[i]['size']+3)&~3
        candidates=sorted(range(len(regions)),key=lambda r:(regions[r][1]-used[r],r))
        seen=set()
        for r in candidates:
            if sections[i]['name']in required and regions[r][0]>=0x1a00000:continue
            if sections[i]['name']in new_required and regions[r][0]<0x1a00000:continue
            remaining=regions[r][1]-used[r]
            if remaining<size or remaining in seen:continue
            seen.add(remaining);positions[i]=(r,regions[r][0]+used[r]);used[r]+=size
            if place(n+1):return True
            used[r]-=size;positions.pop(i)
        failed.add(key);return False
    assert place(0),'Audited executable space exhausted; no implicit region expansion'
    return positions,used

def link(objects,regions,branch,old_rx_required=(),new_rx_required=()):
    sections,syms,rels=read_objects(objects);positions,used=allocate(sections,regions,old_rx_required,new_rx_required)
    local={};global_symbols={}
    for s in syms:
        value=positions[s['section']][1]+s['offset'];local[s['object'],s['index']]=value
        if s['global_symbol']:
            assert s['name'] not in global_symbols,s['name'];global_symbols[s['name']]=value
    result=[bytearray(size) for _,size in regions];recipes=[]
    for i,s in enumerate(sections):
        r,at=positions[i];offset=at-regions[r][0];result[r][offset:offset+s['size']]=s['data']
        recipes.append(dict(object=str(objects[s['object']]),section=s['name'],site=hex(at),bytes=s['size'],region=r))
    resolved=[]
    for r in rels:
        region,section_at=positions[r['section']];at=section_at+r['offset'];offset=at-regions[region][0]
        target=local.get((r['object'],r['index']),global_symbols.get(r['name']))
        assert target is not None,(r,target)
        if r['kind']==2:
            assert r['name'] in ('r5_color_copy','r5_color_word','r5_color_equal'),('unapproved ABS32 helper',r)
            assert result[region][offset:offset+4]==bytes(4),('ABS32 addend must be zero',r)
            assert target&1 and any(a<=(target&~1)<a+used[i] for i,(a,_) in enumerate(regions)),('ABS32 target outside used RX',r,target)
            struct.pack_into('<I',result[region],offset,target)
        else:
            assert r['kind'] in (10,30),(r,target)
            assert result[region][offset:offset+4] in (bytes.fromhex('fff7feff'),bytes.fromhex('fff7febf'))
            assert -0x1000000 <= (target&~1)-(at+4) < 0x1000000,(hex(at),hex(target),'Thumb branch out of range')
            result[region][offset:offset+4]=branch(at,target&~1,r['kind']==10)
        resolved.append(dict(site=hex(at),kind=r['kind'],symbol=r['name'],target=hex(target)))
    return dict(regions=[dict(start=hex(a),capacity=size,used=used[i],data=bytes(result[i]))for i,(a,size)in enumerate(regions)],
                symbols=global_symbols,relocations=resolved,sections=recipes,code_bytes=sum(s['size']for s in sections))
