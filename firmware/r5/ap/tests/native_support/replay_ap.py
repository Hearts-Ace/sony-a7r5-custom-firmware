"""Register, POSIX fixture and call helpers for final AP ELF replay.
No module overlay or old firmware load path is present.
"""
import struct
from unicorn.arm64_const import *
X=[UC_ARM64_REG_X0+i for i in range(29)]+[UC_ARM64_REG_X29,UC_ARM64_REG_X30]
Q=[UC_ARM64_REG_Q0+i for i in range(32)]
STACK=0x12000000;STOP=0x13000000;FIX=0x10000000;SERV=0x11000000
def p32(x):return struct.pack('<I',x&0xffffffff)
def p64(x):return struct.pack('<Q',x)
class Replay:

    def hook(self, u, addr, size, _):
        if addr in self.callbacks:
            self.callbacks[addr]()

    def x(self, n):
        return self.u.reg_read(X[n])

    def putx(self, n, x):
        self.u.reg_write(X[n], x & 18446744073709551615)

    def ret(self, value=0):
        self.putx(0, value)
        self.u.reg_write(UC_ARM64_REG_PC, self.x(30))

    def cstr(self, p):
        b = bytearray()
        for i in range(1024):
            c = bytes(self.u.mem_read(p + i, 1))
            if c == b'\x00':
                return b.decode()
            b += c
        raise AssertionError('string limit')

    def setter(self):
        self.native = self.x(0)
        self.calls.append(('native_set', self.native))
        self.u.mem_write(133286944, p32(self.native))
        self.ret()

    def commit(self):
        self.calls.append(('native_commit', self.x(0)))
        self.ret()

    def send(self):
        self.calls.append(('send', bytes(self.u.mem_read(self.x(1), self.x(2))).hex()))
        self.ret(85)

    def dlsym(self):
        name = self.cstr(self.x(1))
        names = ['open', 'openat', 'read', 'write', 'close', 'fsync', 'renameat', 'unlinkat']
        if name not in names or self.fail == 'resolve':
            return self.ret(0)
        address = SERV + names.index(name) * 16
        self.callbacks[address] = lambda name=name: self.posix(name)
        self.ret(address)

    def posix(self, name):
        self.calls.append(('posix', name))
        if self.fail == name:
            return self.ret(-1)
        if name == 'open':
            assert self.cstr(self.x(0)) == '/setting'
            return self.ret(7)
        if name == 'openat':
            assert self.x(0) == 7
            n = self.cstr(self.x(1))
            flags = self.x(2)
            if flags & 64:
                self.files[n] = bytearray()
            if n not in self.files:
                return self.ret(-1)
            fd = self.nextfd
            self.nextfd += 1
            self.fds[fd] = [n, 0]
            return self.ret(fd)
        if name == 'read':
            (n, at) = self.fds[self.x(0)]
            raw = bytes(self.files[n][at:at + min(self.x(2), self.chunk)])
            self.u.mem_write(self.x(1), raw)
            self.fds[self.x(0)][1] += len(raw)
            return self.ret(len(raw))
        if name == 'write':
            (n, at) = self.fds[self.x(0)]
            raw = bytes(self.u.mem_read(self.x(1), min(self.x(2), self.chunk)))
            self.files[n][at:at + len(raw)] = raw
            self.fds[self.x(0)][1] += len(raw)
            return self.ret(len(raw))
        if name == 'renameat':
            a = self.cstr(self.x(1))
            b = self.cstr(self.x(3))
            self.files[b] = self.files.pop(a)
            return self.ret()
        if name == 'unlinkat':
            self.files.pop(self.cstr(self.x(1)), None)
            return self.ret()
        if name in ('close', 'fsync'):
            return self.ret()
        raise AssertionError(name)

    def call(self, name, *args):
        for (i, arg) in enumerate(args):
            self.putx(i, arg)
        self.u.reg_write(UC_ARM64_REG_SP, STACK + 126976)
        self.putx(29, 0)
        self.putx(30, STOP)
        self.u.emu_start(self.sy[name] if isinstance(name, str) else name, STOP, count=200000)
        assert self.u.reg_read(UC_ARM64_REG_PC) == STOP, (name, hex(self.u.reg_read(UC_ARM64_REG_PC)))
        return self.x(0) & 4294967295

    def token(self):
        return struct.unpack('<I', self.u.mem_read(self.sy['r5_aspect_selection'], 4))[0]
