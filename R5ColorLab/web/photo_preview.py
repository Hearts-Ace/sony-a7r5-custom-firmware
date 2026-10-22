"""RAW photo comparison. Offline approximate front; existing fitted color subchain.

The LUT side uses LibRaw linear demosaic, not RawAlchemy's RCD decoder.
No image is admitted as training data. Historical collectors stay unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np  # Must precede historical imports with their audit path.
from PIL import Image, PngImagePlugin
import core
import white_balance
from edit_native_recipe import read
from raw_slog3_reference import RawSLog3Reference, Cube

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def approximate_front(camera_rgb, wb, reference_model):
    """Approximate photograph front, not the verified flatfield ITP branch.

    Reference-context green gain sets native units; this RAW supplies WB.
    Demosaic/Vatr/SSCS/lens/noise behavior of Edit is not reconstructed.
    """
    import struct
    from edit_raw_front import as_shot_wb
    gains = as_shot_wb(reference_model.raw, reference_model.settings).astype(float)
    scale = struct.unpack_from('<H', reference_model.raw, 0x40)[0]
    green_gain = scale/32768*gains[1]/16
    wb = np.asarray(wb, dtype=float)
    if wb.shape != (3,) or not np.isfinite(wb).all() or np.any(wb <= 0) or green_gain <= 0:
        raise ValueError('Invalid approximate frontend gains')
    native_wb = np.trunc(gains[1]*(wb/wb[1]))
    channel_gains = np.float32(scale)*np.float32(1/32768)*native_wb.astype(np.float32)*np.float32(1/16)
    return np.trunc(np.clip(np.asarray(camera_rgb,dtype=np.float32)*channel_gains, 0, 16383)).astype('<u2')


def quantize(rgb):
    return np.floor(np.clip(rgb, 0, 1)*255+.5).astype(np.uint8)


def raster(keys, rgb, bounds):
    y0, y1, x0, x1 = bounds
    image = np.zeros((y1-y0+1, x1-x0+1, 4), dtype=np.uint8)
    colors = quantize(rgb)
    for (y, x), color in zip(keys, colors):
        image[y-y0, x-x0, :3] = color
        image[y-y0, x-x0, 3] = 255
    return image


PREVIEW_LONG_EDGE = 3840

def preview_coordinates(sizes):
    """4K long edge, original aspect, common sensor samples for both paths."""
    width = min(sizes.crop_width-16, PREVIEW_LONG_EDGE)
    height = min(sizes.crop_height-16, round(width*sizes.crop_height/sizes.crop_width))
    xs = np.rint(np.linspace(sizes.crop_left_margin+8,
        sizes.crop_left_margin+sizes.crop_width-9, width)).astype(int)
    ys = np.rint(np.linspace(sizes.crop_top_margin+8,
        sizes.crop_top_margin+sizes.crop_height-9, height)).astype(int)
    return xs, ys


def apply_rows(rgb, transform, rows=8):
    """Bound temporary memory for high-resolution color transformations."""
    out = np.empty_like(rgb)
    for start in range(0, len(rgb), rows):
        out[start:start+rows] = transform(rgb[start:start+rows])
    return out


def render(source, job, output, pc=False, grid_key=None):
    output.mkdir(parents=True, exist_ok=True)
    pc=bool(pc or grid_key)
    pc_sha=digest(job/'pc_compensation.json') if pc else None
    grid_sha=None
    if grid_key:
        from grid_distillation import load_result
        _,_,grid_sha=load_result(job,grid_key)
    source_sha = digest(source)
    audit = json.loads((job/'input_audit.json').read_text())
    if digest(job/'input.cube') != audit['lut_sha256']:
        raise ValueError('任务 LUT 来源校验失败')
    from rawpy import _rawpy as rawpy
    raw = rawpy.RawPy()
    raw.open_file(str(source))
    raw.unpack()
    try:
        profile = json.loads(core.PROFILE.read_text())
        sizes = raw.sizes
        if ((sizes.raw_width, sizes.raw_height) != (9728, 6656) or
                (sizes.crop_left_margin, sizes.crop_top_margin,
                 sizes.crop_width, sizes.crop_height) != (32, 20, 9504, 6336) or
                not np.array_equal(raw.raw_pattern, [[0, 1], [3, 2]]) or
                not np.allclose(raw.rgb_xyz_matrix, profile['xyz_to_camera'], atol=1e-6)):
            raise ValueError('当前预览仅支持已验证几何与相机矩阵的全尺寸 R5 RGGB RAW')
        black = np.array(raw.black_level_per_channel)[[0, 1, 2]]
        white = raw.white_level
        if len(set(raw.black_level_per_channel)) != 1 or not np.all(white > black):
            raise ValueError('Unsupported RAW levels')
        wb = np.array(raw.camera_whitebalance[:3], dtype=float)
        if not np.isfinite(wb).all() or np.any(wb <= 0):
            raise ValueError('Invalid as-shot white balance')
        profile['camera_wb_rgb'] = (wb/wb[1]).tolist()
        # Unit-WB, black-subtracted camera-native RGB in original sensor units.
        camera = raw.postprocess(output_color=rawpy.ColorSpace.raw,
            user_wb=[1, 1, 1, 1], use_camera_wb=False, use_auto_wb=False,
            no_auto_bright=True, no_auto_scale=True, gamma=(1, 1),
            output_bps=16, user_flip=0, demosaic_algorithm=rawpy.DemosaicAlgorithm.LINEAR)
    finally:
        raw.close()
    recipe, model = read(job/'fit/recipe.json', core.CAPTURE, 4, None)
    # Both chains use the same decoded RAW and same regular preview grid.
    wb_shift=white_balance.from_recipe(recipe)
    wb_ratio=white_balance.photo_gains(model,wb,wb_shift)
    xs, ys = preview_coordinates(sizes)
    reference = RawSLog3Reference(profile, Cube(job/'input.cube'), audit['gamut'],
                                 mode='raw-alchemy-v0.6.2-fused')
    target = np.empty((len(ys), len(xs), 3), dtype=float)
    predicted = np.empty_like(target)
    for row, y in enumerate(ys):
        center = camera[y, xs].astype(float)
        target[row] = reference(center/(white-black))
        # Retain real adjacent sensor pixels; sampling density does not alter the neighborhood.
        neighborhoods = camera[y, xs[:, None]+np.arange(-4, 5)[None, :]]
        inputs = approximate_front(neighborhoods*wb_ratio, wb, model)
        predicted[row] = model.color_only(inputs)[:, 4]/16383
    del camera
    np.savez_compressed(output/'render_inputs.npz',native=predicted,target=target)
    if grid_key:
        from grid_distillation import apply,load_result
        predicted=apply_rows(predicted,lambda rgb:apply(job,rgb,grid_key))
        if grid_sha!=load_result(job,grid_key)[2]:raise ValueError('压缩参数在渲染期间发生变化')
    elif pc:
        from pc_compensation import apply
        predicted=apply_rows(predicted,lambda rgb:apply(job,rgb))
    if pc and pc_sha!=digest(job/'pc_compensation.json'):
        raise ValueError('PC 补偿参数在渲染期间发生变化，请重新生成预览')
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('Color interpretation', '8-bit output RGB displayed as sRGB; no extra gamma or black subtraction')
    for name, rgb in [('lut', target), ('model', predicted)]:
        Image.fromarray(quantize(rgb)).save(output/(name+'.png'), pnginfo=metadata)
    result = dict(schema='r5-RAW-photo-preview/2', source_sha256=source_sha,
        lut_sha256=digest(job/'input.cube'), recipe_sha256=digest(job/'fit/recipe.json'),
        gamut=audit['gamut'], samples=int(len(xs)*len(ys)),
        width=len(xs), height=len(ys), coverage=1.0,
        camera_wb=profile['camera_wb_rgb'], raw_unchanged=digest(source)==source_sha,
        edit_runtime_used=False, frontend_approximate=True, white_balance=recipe.get('white_balance'),
        grid_key=grid_key,grid_sha256=grid_sha,algorithm=('compressed' if grid_key else 'pc' if pc else 'native'),
        pc_compensation_enabled=pc,
        pc_compensation_sha256=pc_sha,
        lut_decoder='pip rawpy/LibRaw; linear bilinear demosaic, unit WB, no auto scale',
        lut_color='RawAlchemy v0.6.2 fused reference -> S-Log3 -> tetrahedral LUT',
        model_input='approximate RAW front: LibRaw camera RGB * reference green gain * as-shot WB; clipped/truncated native codes',
        model_color='selected fit recipe; measured ST context 4 color_only',
        step=None, sampling='rounded-uniform-sensor-coordinates', preview_long_edge=PREVIEW_LONG_EDGE, orientation='sensor landscape; EXIF rotation not applied',
        limits=['LUT demosaic is LibRaw bilinear, not RawAlchemy RCD: not a full app reproduction.',
                'Approximate model frontend omits Edit ITP/Vatr/SSCS, lens/noise processing and scene-dependent scaling.',
                'Reference-context green gain is retained; per-photo Edit native gain is not measured.',
                'Fitted color subchain has fixed reference context; full JPEG stages are not reproduced.',
                'Preview differences include approximate frontend error, not just fitting error.'])
    (output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result


def reuse(source,job,output,pc=False,grid_key=None):
    """Reapply the selected color function to the same decoded RAW samples."""
    from pc_compensation import apply as pc_apply
    from grid_distillation import apply as grid_apply,load_result
    value=json.loads((source/'result.json').read_text())
    if value['recipe_sha256']!=digest(job/'fit/recipe.json') or value['lut_sha256']!=digest(job/'input.cube'):
        raise ValueError('RAW缓存与当前任务不一致')
    with np.load(source/'render_inputs.npz',allow_pickle=False) as data:
        native=data['native'];target=data['target']
    output.mkdir(parents=True,exist_ok=True)
    pc=bool(pc or grid_key)
    pc_sha=digest(job/'pc_compensation.json') if pc else None
    grid_sha=load_result(job,grid_key)[2] if grid_key else None
    predicted=apply_rows(native,lambda rgb:grid_apply(job,rgb,grid_key)) if grid_key else apply_rows(native,lambda rgb:pc_apply(job,rgb)) if pc else native
    if pc and pc_sha!=digest(job/'pc_compensation.json'):raise ValueError('PC参数发生变化')
    if grid_key and grid_sha!=load_result(job,grid_key)[2]:raise ValueError('压缩参数发生变化')
    np.savez_compressed(output/'render_inputs.npz',native=native,target=target)
    for name,rgb in [('lut',target),('model',predicted)]:
        Image.fromarray(quantize(rgb)).save(output/(name+'.png'))
    value.update(pc_compensation_enabled=pc,pc_compensation_sha256=pc_sha,
                 grid_key=grid_key,grid_sha256=grid_sha,
                 algorithm='compressed' if grid_key else 'pc' if pc else 'native',
                 decoded_samples_reused=True,raw_rechecked_this_render=False)
    (output/'result.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('job', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--pc',action='store_true')
    parser.add_argument('--grid')
    parser.add_argument('--reuse',action='store_true')
    args = parser.parse_args()
    (reuse if args.reuse else render)(args.source, args.job, args.output,args.pc,args.grid)
