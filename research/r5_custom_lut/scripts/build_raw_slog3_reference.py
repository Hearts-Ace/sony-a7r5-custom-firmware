# SPDX-License-Identifier: AGPL-3.0-or-later
# RAW target-chain research based on Raw Alchemy v0.6.2; see THIRD_PARTY_NOTICES.md.
"""Build metadata-derived reference and synthetic target sets; no image fit."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/fit_eval_python312'))
sys.path.insert(0,str(ROOT/'upstream/colour-4ee3b72'))
import colour
from raw_slog3_reference import RawSLog3Reference,Cube,sensor_test_set,anchors

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('raw',type=Path,help='Read camera metadata only, never image colors')
    ap.add_argument('--sgamut3-lut',type=Path,required=True)
    ap.add_argument('--cine-lut',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(exist_ok=False)
    # Use the installed Raw Alchemy decoder build, without modifying its app.
    sys.path.append('/Applications/RawAlchemy.app/Contents/Resources')
    from rawpy import _rawpy
    raw=_rawpy.RawPy();raw.open_file(str(a.raw));raw.unpack()
    try:
        xyz=np.array(raw.rgb_xyz_matrix,dtype=float)
        wb=np.array(raw.camera_whitebalance,dtype=float);wb=wb[:3]/wb[1]
        black=list(raw.black_level_per_channel);white=raw.white_level
        camera_white=raw.camera_white_level_per_channel
    finally:raw.close()
    source=ROOT/'upstream/raw-alchemy-v0.6.2/src/raw_alchemy/colorspace_matrices.py'
    # Keep this isolated source import away from app/GPU initialization.
    import types
    package=types.ModuleType('raw_alchemy');package.config=types.SimpleNamespace(
        WORKING_SPACE_PROPHOTO='ProPhoto RGB',WORKING_SPACE_ACESCG='ACEScg',WORKING_SPACE='ProPhoto RGB')
    sys.modules['raw_alchemy']=package
    spec=importlib.util.spec_from_file_location('camera_matrix_source',source)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    cam=m.cam_to_prophoto_matrix(xyz)
    gamuts=['S-Gamut3','S-Gamut3.Cine']
    transforms={g:colour.matrix_RGB_to_RGB(colour.RGB_COLOURSPACES['ProPhoto RGB'],colour.RGB_COLOURSPACES[g]).tolist() for g in gamuts}
    profile=dict(schema='camera-RAW-SLog3-reference-profile/1',source_raw_sha256=sha(a.raw),
        normalized_sensor_domain='(camera code - channel black)/(RAW white_level - channel black), before WB',
        black_levels=black,white_level=white,camera_white_levels=camera_white,
        camera_wb_rgb=wb.tolist(),xyz_to_camera=xyz.tolist(),camera_to_working=cam.tolist(),
        working_to_log=transforms,working_space='ProPhoto RGB',exposure_ev=0,
        colour_commit='4ee3b72a2c6205c1d0cd964075621ec19290d571',colour_version=colour.__version__,
        camera_matrix_source_sha256=sha(source),metadata_decoder='installed Raw Alchemy rawpy/LibRaw',
        native_Edit_bridge_verified=False,
        limits=['LibRaw metadata branch; RawSpeed matrix selection has not been established for the earlier GUI export.',
            'Not a Sony camera S-Log3 calibration.',
            'Spatial decode, highlight reconstruction, lens correction and noise are outside uniform-patch reference.',
            'Neutral WB/exposure controls fixed; not automatic metering.',
            'No arbitrary Edit RGB normalization is authorized by this profile.'])
    (a.output/'camera_profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    arrays={}
    for i,(g,lut) in enumerate(zip(gamuts,[a.sgamut3_lut,a.cine_lut])):
        ref=RawSLog3Reference(profile,Cube(lut),g,mode='raw-alchemy-v0.6.2-fused')
        for split,seed,n in [('train',7101,8192),('valid',7102,4096),('test',7103,8192)]:
            sensor=sensor_test_set(seed,n,wb)
            arrays[f'{i}_{split}_sensor']=sensor
            arrays[f'{i}_{split}_target']=ref(sensor)
        anchor=anchors(wb);arrays[f'{i}_anchors_sensor']=anchor
        arrays[f'{i}_anchors_target']=ref(anchor)
    np.savez_compressed(a.output/'synthetic_reference.npz',**arrays)
    report=dict(schema='RAW-SLog3-LUT-mathematical-target/1',profile_sha256=sha(a.output/'camera_profile.json'),
        dataset_sha256=sha(a.output/'synthetic_reference.npz'),
        luts={g:dict(path=str(p.resolve()),sha256=sha(p)) for g,p in zip(gamuts,[a.sgamut3_lut,a.cine_lut])},
        samples_per_gamut=dict(train=8192,valid=4096,test=8192,anchors=len(anchor)),
        photo_pixels_used_for_fitting=False,compensation_enabled=False,
        native_Edit_bridge_verified=False,full_dual_pipeline_fitting_complete=False,
        native_input_admission='Do not feed sensor-normalized samples directly to Edit color_only.',
        next_required=['Recover/replay Edit black/WB input scaling and uniform-patch interpolation.',
            'Include/verify Vatr, SSCS and output stages before solving native parameters.',
            'Fit train, select on validation, report untouched test; photo validation comes last.'])
    (a.output/'reference_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
