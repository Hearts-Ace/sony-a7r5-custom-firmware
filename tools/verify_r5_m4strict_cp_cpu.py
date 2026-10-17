"""Offline ARM helper states for the strict M4-to-R5 CP verifier only.

No device transport, no executable target processes, no previous build inputs.
"""
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *
BASE = 0x108000
PROP = 0x16b0f14
SCRATCH = 0x3000000
STOP = SCRATCH + 0x8000
SP = SCRATCH + 0xf000

def new_cpu(code, prop=None):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    u.mem_map(0x100000, 0x1f00000)
    u.mem_write(BASE, code)
    u.mem_map(SCRATCH, 0x10000)
    u.reg_write(UC_ARM_REG_SP, SP)
    u.reg_write(UC_ARM_REG_LR, STOP | 1)
    if prop:
        u.mem_write(PROP, prop)
    return u


def w32(u, at, value):
    u.mem_write(at, struct.pack('<I', value))


def lookup(code, entry, profile, mode, adjustment, prop):
    u = new_cpu(code, prop)
    dst = SCRATCH + 0x4000
    u.mem_write(dst, b'\xa5' * 64)
    u.reg_write(UC_ARM_REG_R0, dst)
    u.reg_write(UC_ARM_REG_R1, profile)
    u.reg_write(UC_ARM_REG_R2, SCRATCH + 0x1000 if entry == 0x616670 else mode)
    u.reg_write(UC_ARM_REG_R3, SCRATCH + 0x1000)
    w32(u, SCRATCH + 0x1000, SCRATCH + 0x2000)
    calls = []

    def hook(cpu, at, size, data):
        off = at - BASE
        if off == 0x61674e:
            calls.append('adjustment_helper')
            cpu.mem_write(cpu.reg_read(UC_ARM_REG_R0), struct.pack('<8h', *adjustment))
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
        elif off == 0x61a396:
            calls.append('diagnostic_helper')
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    u.hook_add(UC_HOOK_CODE, hook)
    u.emu_start((BASE + entry) | 1, STOP, count=5000)
    assert u.reg_read(UC_ARM_REG_PC) == STOP, 'lookup did not return'
    return bytes(u.mem_read(dst, 64)), calls


def full_selector(code, color, mode, scene=0, variant=0, prop=None):
    u = new_cpu(code, prop)
    indirect, state, context, output_struct, dst = [SCRATCH + x for x in (0x1000, 0x2000, 0x3000, 0x3800, 0x4000)]
    w32(u, indirect, state)
    w32(u, indirect + 4, context)
    w32(u, output_struct + 8, dst)
    u.reg_write(UC_ARM_REG_R0, indirect)
    u.reg_write(UC_ARM_REG_R1, output_struct)
    u.mem_write(dst, b'\xa5' * 0x200)
    for off, val in [(0x18,2 if mode=='still' else 0),(0x2e,color),(0x17,scene),(0x34,variant%4),
                     (0x52,(variant>>1)&1),(0xa0,(variant>>2)&1),(0x25,(variant>>3)&1)]:
        u.mem_write(state+off,bytes([val]))
    u.mem_write(context+3,bytes([variant%3]))
    u.mem_write(context+4,bytes([13 if variant&8 else 0]))
    u.mem_write(0x16afd14+0x14,bytes([0x30 if variant&8 else 0]))
    w32(u,state+0x17c,11)
    w32(u,state+0x180,3)
    calls=[]
    def hook(cpu,at,size,data):
        off=at-BASE
        if off in (0x62efd2,0x62c792,0xa05e92):
            calls.append(hex(off))
            cpu.reg_write(UC_ARM_REG_R0, 1 if variant&16 and off!=0xa05e92 else 0)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        elif off==0x12bc10:cpu.emu_stop()
    u.hook_add(UC_HOOK_CODE,hook)
    u.emu_start((BASE+0x12afe0)|1,BASE+0x12bc10,count=10000)
    assert u.reg_read(UC_ARM_REG_PC)==BASE+0x12bc10, (mode,color,scene,variant,hex(u.reg_read(UC_ARM_REG_PC)-BASE))
    return bytes(u.mem_read(dst,0x200)),calls

