"""Verify fitted native tables with original Edit instructions and PC reload."""
from pathlib import Path
import argparse,json,hashlib,struct
from edit_parameter_context import ParameterContext,RuntimeColor,np
from replay_edit_parameter_context import ParameterReplay
from edit_native_recipe import read,render

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('recipe',type=Path);ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 if a.output.exists():raise ValueError('New output required')
 r=json.load(open(a.recipe));i=r['source']['context'];p=r['parameters'];engine=ParameterReplay();ctx=ParameterContext(RuntimeColor.from_capture(a.capture,i),engine.matrix_bytes)
 payload=bytes.fromhex(p['matrix_780f_hex']);native=engine.matrix_bytes(payload);approx=ctx.build(matrix_payload=payload).runtime[0x91bc0:0xa3bc0]
 # Also quantify the float64 expansion used only during optimization.
 relaxed=ParameterContext(ctx.base).build(matrix_payload=payload).runtime[0x91bc0:0xa3bc0]
 d=np.frombuffer(native,dtype='<f4')-np.frombuffer(relaxed,dtype='<f4')
 gamma=engine.gamma_bytes(ctx.axis,p['gamma_7806_y'],ctx.contrast);model=ctx.build(matrix_payload=payload,cc1=p['cc1_direct_raw'],gamma_y=p['gamma_7806_y'])
 _,reload=read(a.recipe,a.capture,i,engine.matrix_bytes);rng=np.random.default_rng(2911);x=rng.integers(0,16384,(128,9,3),dtype=np.uint16)
 result=dict(schema='full-chain-recipe-native-instruction-verification/1',recipe_sha256=hashlib.sha256(a.recipe.read_bytes()).hexdigest(),matrix_native_builder_bytes_equal=native==approx,
 gamma_native_bytes_equal=gamma==model.runtime[0x18f6:0x218f6],inverse_native_bytes_equal=engine.inverse_bytes(gamma,ctx.inverse_zero)==model.runtime[0x69962:0x89962],
 strict_PC_reader_render_equal=np.array_equal(render(reload,x),model.color_only(x)),matrix_relaxation_max_float_error=float(np.max(np.abs(d))),
 gamma_flat_intervals=int(np.sum(np.diff(p['gamma_7806_y'])==0)),additional_compensation_enabled=False)
 result['passed']=all(result[k] for k in ['matrix_native_builder_bytes_equal','gamma_native_bytes_equal','inverse_native_bytes_equal','strict_PC_reader_render_equal'])
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 if not result['passed']:raise SystemExit(2)
if __name__=='__main__':main()
