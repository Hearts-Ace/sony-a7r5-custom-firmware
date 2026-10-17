"""Read-only BK4 bank parser for local firmware research.

Format cross-check: ma1co/Sony-PMCA-RE, pmca/backup/__init__.py.
No property writes, checksum repair, camera I/O, or execution of extracted code.
Offsets in the format are relative to each bank, not to the containing file.
"""
from dataclasses import dataclass
import struct


class BK4Error(ValueError):
    """Malformed or unsupported BK4 data."""


@dataclass(frozen=True)
class Property:
    property_id: int
    attributes: int
    bank_offset: int
    relative_offset: int
    capacity: int
    data: bytes

    @property
    def file_offset(self):
        return self.bank_offset + self.relative_offset


class BK4Bank:
    HEADER_SIZE = 0x100
    ENTRY_SIZE = 6

    def __init__(self, data, offset=0):
        if offset < 0 or offset + self.HEADER_SIZE > len(data):
            raise BK4Error('Truncated bank header or invalid bank offset')
        if data[offset + 12:offset + 16] != b'BK4\0':
            raise BK4Error('Not a BK4 bank')
        ns, np, start, size, checksum = struct.unpack_from('<5I', data, offset + 0x10)
        table_end = self.HEADER_SIZE + self.ENTRY_SIZE * (ns + np)
        end = start + size
        if start < table_end or end > len(data) - offset:
            raise BK4Error('Invalid table/data extent')
        # Keep one immutable bank copy and calculate its checksum only once.
        self.data = bytes(data[offset:offset + end])
        calculated = sum(self.data[:0x20]) + sum(self.data[0x24:])
        if calculated != checksum:
            raise BK4Error('Wrong BK4 checksum')
        self.offset, self.size = offset, end
        self.num_subsystems, self.num_properties = ns, np
        self.data_offset, self.checksum = start, checksum
        self.property_table = self.HEADER_SIZE + ns * self.ENTRY_SIZE
        self.subsystems = []
        for index in range(ns):
            count, first = struct.unpack_from('<HI', self.data, self.HEADER_SIZE + index * 6)
            if first + count > np:
                raise BK4Error(f'Invalid subsystem extent at {index:#x}')
            self.subsystems.append((count, first))

    def _check_data(self, offset, size):
        if offset < self.data_offset or size < 0 or offset + size > self.size:
            raise BK4Error('Property points outside bank data')

    def property(self, property_id):
        if not isinstance(property_id, int) or not 0 <= property_id <= 0xffffffff:
            raise BK4Error('Invalid property id')
        subsystem, index = property_id >> 16, property_id & 0xffff
        if subsystem >= self.num_subsystems:
            raise KeyError(property_id)
        count, first = self.subsystems[subsystem]
        if index >= count:
            raise KeyError(property_id)
        attr, packed = struct.unpack_from('<HI', self.data, self.property_table + (first + index) * 6)
        if packed == 0xffffffff:
            raise KeyError(property_id)
        size, offset = packed >> 24, packed & 0xffffff
        capacity = size
        if size == 0xff:
            self._check_data(offset, 2)
            size = capacity = struct.unpack_from('<H', self.data, offset)[0]
            offset += 2
        elif size == 0:
            self._check_data(offset, 4)
            size, capacity = struct.unpack_from('<HH', self.data, offset)
            offset += 4
        if size > capacity:
            raise BK4Error('Property size exceeds capacity')
        self._check_data(offset, capacity)
        return Property(property_id, attr, self.offset, offset, capacity,
                        self.data[offset:offset + size])


def find_banks(data):
    """Discover non-overlapping, checksum-valid banks; ignore incidental magic.

    Caller must enforce its expected bank count/offsets. Invalid candidates are
    deliberately not accepted as banks. A valid first bank is required at zero.
    """
    banks = [BK4Bank(data)]
    cursor = banks[0].size
    while True:
        magic = data.find(b'BK4\0', cursor)
        if magic < 0:
            break
        offset = magic - 12
        if offset < cursor:
            cursor = magic + 4
            continue
        try:
            bank = BK4Bank(data, offset)
        except BK4Error:
            cursor = magic + 4
            continue
        banks.append(bank)
        cursor = offset + bank.size
    return banks
