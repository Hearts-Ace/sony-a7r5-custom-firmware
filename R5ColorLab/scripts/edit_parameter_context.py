"""Rebuild measured Edit color contexts from quantized RAW look parameters.

Restricted to contexts whose native table builders exactly match the recovered
identity-calibration/no-extra-gamut path. Unknown settings fail closed. This
does not decode a RAW file or reproduce spatial processing.
"""
import struct
from edit_color_pipeline import RuntimeColor, static_table, np
from edit_native_model import decode_matrix16, expand_matrix16, expand_gamma


def main_inverse(gamma, initial_zero=0):
    """0x1000c2ff0: the search tests the NEXT table value, strictly < y."""
    g = np.asarray(gamma,dtype='<i2')
    if g.shape != (65536,) or np.any(np.diff(g[32768:].astype(np.int64)) < 0):
        raise ValueError('MainGamma must be signed and monotone on positive input')
    j = 32768+np.searchsorted(g[32769:],np.arange(32768),side='left')
    out = np.zeros(65536,dtype='<u2')
    # Native writes indices 1..65535 and leaves index zero untouched.
    out[0] = initial_zero
    out[32768:] = (j ^ 32768).astype('<u2')
    out[32768-np.arange(32768)] = ((-32768-j)&65535).astype('<u2')
    return out


def secondary_inverse(gamma):
    """0x1000c3068, first 16384 entries (the allocation is twice as large)."""
    g = np.asarray(gamma,dtype='<i2')
    if g.shape != (65536,) or np.any(np.diff(g[32768:].astype(np.int64)) < 0):
        raise ValueError('Secondary Gamma must be monotone')
    j = 32768+np.searchsorted(g[32769:],np.arange(16384),side='left')
    return (j ^ 32768).astype('<u2')


class ParameterContext:
    def __init__(self, measured, matrix_builder=None):
        self.base = measured
        self.matrix_builder = matrix_builder
        self.payload = measured.raw[0xae:0xae+276]
        cfg = decode_matrix16(self.payload)
        matrix = expand_matrix16(cfg).astype('<f4')
        # The 552-byte allocation has two trailing padding bytes. Native
        # decoding writes fields through +0x224 (uint16), leaving +0x226/227
        # untouched; fresh runtime captures need not have zero-filled padding.
        if cfg[:0x226] != measured.config[:0x226] or not np.array_equal(matrix,measured.matrix_table):
            raise ValueError('Captured matrix requires an unmodeled calibration/gamut builder')
        if struct.unpack_from('<i',measured.settings,0x1e8)[0] != 1:
            raise ValueError('This parameter editor currently requires measured CC1 mode 1')
        self.axis = np.frombuffer(measured.raw,dtype='<i4',count=128,offset=0x5d8).copy()
        self.gamma_y = np.frombuffer(measured.raw,dtype='<i4',count=128,offset=0x7d8).copy()
        self.cc1 = measured.coefficients().copy()
        # Identity user contrast/highlight/shadow: the native table still clips
        # the last interval at entry 1023, explaining a seven-code highlight gap.
        if any(struct.unpack_from('<i',measured.settings,i)[0] != 0 for i in [0x200,0x2b4,0x2b8]):
            raise ValueError('Nonneutral contrast/highlight/shadow builder not enabled here')
        self.contrast = static_table(0x100249e60+18*0x1004,1025,'<i4')
        gamma = expand_gamma(self.axis,self.gamma_y,self.contrast)
        actual = np.frombuffer(measured.runtime,dtype='<u2',count=65536,offset=0x18f6)
        if not np.array_equal(gamma,actual):
            raise ValueError('MainGamma builder/configuration not reproduced exactly')
        actual_inv = np.frombuffer(measured.runtime,dtype='<u2',count=65536,offset=0x69962)
        self.inverse_zero = int(actual_inv[0])
        inv = main_inverse(gamma,self.inverse_zero)
        if not np.array_equal(inv,actual_inv): raise ValueError('Main inverse builder mismatch')
        secondary = np.frombuffer(measured.runtime,dtype='<u2',count=65536,offset=0x218fc)
        actual_secondary_inv = np.frombuffer(measured.runtime,dtype='<u2',count=16384,offset=0x89962)
        if not np.array_equal(secondary_inverse(secondary),actual_secondary_inv):
            raise ValueError('Secondary inverse builder mismatch')

    def build(self, matrix_payload=None, cc1=None, gamma_y=None):
        runtime,raw = bytearray(self.base.runtime),bytearray(self.base.raw)
        if matrix_payload is not None:
            cfg = decode_matrix16(matrix_payload)
            raw[0xae:0xae+276] = matrix_payload
            runtime[0x91998:0x91bbe] = cfg[:0x226]
            if matrix_payload == self.payload:
                table = self.base.runtime[0x91bc0:0xa3bc0]
            elif self.matrix_builder is not None:
                table = self.matrix_builder(matrix_payload)
                if len(table) != 1024*18*4: raise ValueError('Incomplete native matrix builder result')
            else:
                table = expand_matrix16(cfg).astype('<f4').tobytes()
            runtime[0x91bc0:0xa3bc0] = table
        if cc1 is not None:
            a = np.asarray(cc1)
            if a.shape != (8,) or np.any(~np.isfinite(a)) or np.any(a != np.trunc(a)):
                raise ValueError('Eight integer CC1 values required')
            # Actual RGB→YCC decoder sign-extends low nine bits (first four),
            # while the gain shorts (last four) have no high-bit wrap allowance.
            if np.any(a[:4] < -1024) or np.any(a[:4] > 1023) or np.any(a[4:] < 0) or np.any(a[4:] > 2047):
                raise ValueError('CC1 outside supported native field ranges')
            if self.base.raw[0x1c]:
                struct.pack_into('<8h',raw,0xddc,*a.astype(int))
            else:
                # ST uses B + weighted deltas. Shift B by the effective
                # difference; leave the measured weights and deltas intact.
                old = np.array(struct.unpack_from('<8h',raw,0xdec),dtype=np.int64)
                shifted = old+a.astype(np.int64)-self.cc1
                if np.any(shifted < -32768) or np.any(shifted > 32767):
                    raise ValueError('Indirect CC1 base would overflow int16')
                struct.pack_into('<8h',raw,0xdec,*shifted)
        if gamma_y is not None:
            a = np.asarray(gamma_y)
            if (a.shape != (128,) or np.any(~np.isfinite(a)) or np.any(a != np.trunc(a))
                    or a[0] != 0 or np.any(np.diff(a) < 0) or np.any(a < 0) or np.any(a > 262143)):
                raise ValueError('Monotone zero-origin 18-bit Gamma ordinates required')
            struct.pack_into('<128i',raw,0x7d8,*a.astype(int))
            gamma = expand_gamma(self.axis,a,self.contrast)
            runtime[0x18f6:0x218f6] = gamma.tobytes()
            runtime[0x69962:0x89962] = main_inverse(gamma,self.inverse_zero).tobytes()
            # The captured secondary Gamma depends on its own RAW/settings,
            # not main Gamma. It and its inverse remain valid; main-dependent
            # suppression cutoffs are recomputed by RuntimeColor on every call.
        return RuntimeColor(runtime,raw,self.base.settings,area_controls=self.base.area_controls)


def quantize_matrix_coefficients(payload, coefficients):
    """Replace only 96 block13 coefficients, preserving all common fields.

    Signed packing is asymmetric: negative representable units are odd;
    positive units are integers. Return the decoded values actually written.
    """
    if len(payload) != 276: raise ValueError('Expected 276-byte block13 payload')
    a = np.asarray(coefficients,dtype=np.float64)
    if a.shape != (6,16) or not np.all(np.isfinite(a)) or np.any(np.abs(a) > 8191/1024):
        raise ValueError('Block13 coefficients outside representable range')
    units = np.where(a < 0,2*np.rint((np.abs(a)*1024-1)/2)+1,np.rint(a*1024))
    units = np.where(np.abs(a)*1024 < .5,0,units)
    units = np.clip(units,0,8191).astype(np.int64)
    code = np.where((a < 0)&(units != 0),0x8000|((0x3fff-units)<<2),units<<2)&65535
    out = bytearray(payload)
    for i,v in enumerate(code.reshape(-1)):
        at = 24+2*(i^1)
        old = struct.unpack_from('<H',out,at)[0]
        ignored = old & (7 if int(v)&0x8000 else 3)
        struct.pack_into('<H',out,at,int(v)|ignored)
    cfg = decode_matrix16(bytes(out))
    return bytes(out),np.array(struct.unpack_from('<96f',cfg,0x28)).reshape(6,16)
