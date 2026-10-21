"""Verify changed parameter tables with original instructions in isolated RAM.

Includes measured contexts, nondefault Gamma with consistent inverse rebuild,
quantized block13 changes and direct CC1. No Edit launch or device operation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
from replay_edit_parameters import Replay, RUNTIME, RAW, CONTEXT, GAMMA, AXIS, VALUES, sha
from edit_parameter_context import ParameterContext, RuntimeColor, np, quantize_matrix_coefficients, main_inverse, secondary_inverse
from edit_native_model import expand_gamma

CONTRAST, INVERSE, DUMMY = 0x30300000,0x30310000,0x30350000


class ParameterReplay(Replay):
    def matrix_bytes(self,payload):
        self.matrix(payload)
        return bytes(self.uc.mem_read(RUNTIME+0x91bc0,1024*72))

    def gamma_bytes(self,axis,values,contrast):
        self.uc.mem_write(AXIS,np.asarray(axis,dtype='<i4').tobytes())
        self.uc.mem_write(VALUES,np.asarray(values,dtype='<i4').tobytes())
        self.uc.mem_write(CONTRAST,np.asarray(contrast,dtype='<i4').tobytes())
        self.call(0x1000c82d4,0,GAMMA,AXIS,VALUES,len(axis),CONTRAST)
        return bytes(self.uc.mem_read(GAMMA,0x20000))

    def inverse_bytes(self,gamma,initial_zero):
        self.uc.mem_write(GAMMA,gamma)
        initial = np.zeros(65536,dtype='<u2');initial[0] = initial_zero
        self.uc.mem_write(INVERSE,initial.tobytes())
        self.call(0x1000c2ff0,DUMMY,GAMMA,INVERSE)
        return bytes(self.uc.mem_read(INVERSE,0x20000))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists(): raise ValueError('New evidence output required')
    engine=ParameterReplay();rows=[]
    for i in range(3):
        m=RuntimeColor.from_capture(args.capture,i)
        p=ParameterContext(m,engine.matrix_bytes)
        rebuilt=p.build(matrix_payload=p.payload,cc1=p.cc1,gamma_y=p.gamma_y)
        row=dict(context=i,raw_roundtrip_bytes_equal=rebuilt.raw==m.raw,
            runtime_roundtrip_bytes_equal=rebuilt.runtime==m.runtime)
        plain=expand_gamma(p.axis,p.gamma_y)
        actual=np.frombuffer(m.runtime,dtype='<u2',count=65536,offset=0x18f6)
        row['without_contrast_max_code_error']=int(np.max(np.abs(plain.astype(np.int64)-actual.astype(np.int64))))
        gamma=engine.gamma_bytes(p.axis,p.gamma_y,p.contrast)
        row['gamma_instruction_bytes_equal']=gamma==actual.tobytes()
        row['inverse_instruction_bytes_equal']=engine.inverse_bytes(gamma,p.inverse_zero)==main_inverse(actual,p.inverse_zero).tobytes()
        rows.append(row)
    p=ParameterContext(RuntimeColor.from_capture(args.capture,2),engine.matrix_bytes)
    # A distinct curve changes both mapping and highlight suppression cutoff.
    changed_y=np.rint(p.gamma_y*.88).astype(np.int32)
    changed=p.build(gamma_y=changed_y)
    gamma=engine.gamma_bytes(p.axis,changed_y,p.contrast)
    rows.append(dict(case='nondefault_gamma',gamma_bytes_equal=gamma==changed.runtime[0x18f6:0x218f6],
        inverse_bytes_equal=engine.inverse_bytes(gamma,p.inverse_zero)==changed.runtime[0x69962:0x89962],
        before_suppression=p.base.chroma_controls(),after_suppression=changed.chroma_controls()))
    cfg=p.base.config
    coeff=np.array(struct.unpack_from('<96f',cfg,0x28)).reshape(6,16)
    rng=np.random.default_rng(20261019)
    quantization=[]
    for amplitude in [.002,.02,.08]:
        payload,q=quantize_matrix_coefficients(p.payload,coeff+rng.uniform(-amplitude,amplitude,(6,16)))
        model=p.build(matrix_payload=payload)
        actual_bytes=engine.matrix_bytes(payload)
        quantization.append(dict(amplitude=amplitude,packed_bytes=len(payload),
            builder_bytes_equal=model.runtime[0x91bc0:0xa3bc0]==actual_bytes,
            changed_payload_bytes=sum(a!=b for a,b in zip(payload,p.payload)),
            quantized_coefficients=q.tolist()))
    passed=all(all(v for k,v in r.items() if k.endswith('equal')) for r in rows+quantization)
    result=dict(schema='sony-edit-parameter-context-replay/1',all_passed=passed,
        report_sha256=sha((args.capture/'report.json').read_bytes()),measured_and_gamma=rows,
        changed_matrix=quantization,
        scripts={f.name:sha(f.read_bytes()) for f in [Path(__file__),Path(__file__).with_name('edit_parameter_context.py'),
            Path(__file__).with_name('edit_native_model.py'),Path(__file__).with_name('edit_color_pipeline.py')]},
        limitations=['Native code executes in synthetic RAM, not a camera or full Edit renderer.',
            'Direct CC1 mode 1, neutral contrast/highlight/shadow and identity calibration path only.',
            'Secondary Gamma retained; main Gamma and its inverse rebuilt together.',
            'Matrix instruction replay avoids float64 expansion rounding and signed-zero differences.'])
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(all_passed=passed,measured_and_gamma=rows),indent=2))
    if not passed: raise SystemExit(2)


if __name__=='__main__': main()
