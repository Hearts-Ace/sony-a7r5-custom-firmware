"""Convert only the validated synthetic 100MP ARW with the IED RAF workflow.

The production IED sources are read-only. A single local builder adaptation
adds the full GFX crop size; strict custom preflight replaces camera-size limits.
"""
from pathlib import Path
import hashlib
import inspect
import io
import json
import os
import shutil
import struct
import sys
import tempfile

import numpy as np
import rawpy
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IED = Path('/Users/LOCAL_USER/Documents/ChatGPT/ied软件/索尼RAW转GFX无黑边/源码')
SOURCE = HERE/'SONY-v4.5-100MP-5300K.ARW'
SOURCE_SHA = '45455a7c46d7aa2454e73a67c32b01a29a13739d203e54ed24592a451fd48bd6'
DEST = HERE/'GFX100SII-v4.5-100MP-5300K.RAF'
sys.path.insert(0,str(IED))
import r5_to_gfx as app
import raw_storage
import raf
import metadata
from arw import parse, one, ints, subifd, maker, text_value


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(4*1024*1024),b''):
            digest.update(data)
    return digest.hexdigest()


def compact_thumbnail(data):
    # ARW stores its thumbnail outside JPEG EXIF; this custom ARW's 1600px
    # thumbnail exceeds the 64KiB APP1 limit when copied into the RAF preview.
    # Resize only this thumbnail. The full source preview scan stays unchanged.
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert('RGB')
        image.thumbnail((160,120),Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output,format='JPEG',quality=90)
    return output.getvalue()


def main():
    assert not DEST.exists(), 'Choose a new output; never overwrite'
    assert sha(SOURCE) == SOURCE_SHA
    assert shutil.disk_usage(HERE).free > 2*1024**3
    snapshot = HERE/'ied-original-source'
    snapshot.mkdir(exist_ok=True)
    input_hashes = {}
    for name in ['r5_to_gfx.py','sony_source.py','raw_storage.py','raf.py','arw.py',
                 'metadata.py','README.md','profile.json','gfx_profile.bin.z']:
        source = IED/name
        input_hashes[name] = sha(source)
        if not (snapshot/name).exists():
            shutil.copyfile(source,snapshot/name)
        assert sha(snapshot/name) == input_hashes[name]
    (HERE/'ied-source-sha256.json').write_text(json.dumps(input_hashes,indent=2)+'\n')
    # The app bundle normally supplies exiftool/. Use the same existing toolkit
    # via a local resource link, rather than the source-only fallback path.
    exiftool_dir = IED.parents[1]/'tools/Image-ExifTool-13.59'
    assert (exiftool_dir/'exiftool').is_file()
    if not (snapshot/'exiftool').exists():
        (snapshot/'exiftool').symlink_to(exiftool_dir,target_is_directory=True)
    assert (snapshot/'exiftool').resolve() == exiftool_dir.resolve()
    app.RESOURCE = snapshot
    # Preserve the IED packing, metadata, gain, lens neutralization and exposure
    # calibration. Extend only its bounded crop-size allowlist in a local copy.
    builder_source = inspect.getsource(raf.build)
    old = '((9504,6336),(7008,4672),(6224,4672),(6240,4160))'
    assert builder_source.count(old) == 1
    builder_source = builder_source.replace(old,'((9504,6336),(7008,4672),(6224,4672),(6240,4160),(11648,8736))')
    old_aspect = "aspect = (3,4) if (w,h)==(6224,4672) else (2,3)"
    assert builder_source.count(old_aspect) == 1
    builder_source = builder_source.replace(old_aspect,"aspect = (3,4) if (w,h) in ((6224,4672),(11648,8736)) else (2,3)")
    (HERE/'ied-build-100mp.py').write_text(builder_source)
    namespace = vars(raf).copy()
    exec(compile(builder_source,str(HERE/'ied-build-100mp.py'),'exec'),namespace)
    build = namespace['build']
    preview_source = inspect.getsource(app.preview)
    original_thumbnail = 'thumbnail=metadata.jpeg(a,chain[1][1])'
    assert preview_source.count(original_thumbnail) == 1
    preview_source = preview_source.replace(original_thumbnail,'thumbnail=compact_thumbnail(metadata.jpeg(a,chain[1][1]))')
    (HERE/'ied-preview-100mp.py').write_text(preview_source)
    preview_namespace = vars(app).copy()
    preview_namespace['compact_thumbnail'] = compact_thumbnail
    exec(compile(preview_source,str(HERE/'ied-preview-100mp.py'),'exec'),preview_namespace)
    make_preview = preview_namespace['preview']

    data = app.read_source(SOURCE)
    parsed = parse(data)
    sub = subifd(parsed)
    assert text_value(one(parsed['root'],0x10f)) == 'SONY'
    assert text_value(one(parsed['root'],0x110)) == 'ILCE-7RM5'
    assert ints(one(maker(parsed)[3],0xb001)) == [390]
    expected = {0xc61f:[32,20],0xc620:[11648,8736],0x74c7:[32,20],
                0x74c8:[11648,8736],0x102:[14],0x7310:[512]*4,
                0xc61d:[16383]}
    for tag, value in expected.items():
        assert ints(one(sub,tag)) == value, hex(tag)
    assert struct.unpack('<4h',one(sub,0x7313)['data']) == (2606,1024,1024,1789)
    assert one(sub,0x828e)['data'] == b'\0\1\1\2'
    assert ints(one(parsed['sr'],0x74c3)) == [32,20,11680,8756]
    assert ints(one(parsed['sr'],0x7922)) == [11648,8736]
    raw_storage.LAYOUTS['synthetic-100mp'] = ((11744,8776),(11776,9216),(11712,8776))
    raw_storage.validate_tiles(parsed,'synthetic-100mp')
    with rawpy.imread(io.BytesIO(data)) as source_raw:
        assert source_raw.raw_image.shape == (9216,11776)
        assert source_raw.raw_pattern.tolist() == [[0,1],[3,2]]
        assert source_raw.black_level_per_channel == [512]*4 and source_raw.white_level == 16383
        assert source_raw.camera_whitebalance == [2606.,1024.,1789.,1024.]
        # Outside the chart the generator repeats edge patches, followed by
        # zero tile padding. Keep the margins that fit the GFX storage canvas.
        mosaic = source_raw.raw_image
        assert not np.any(mosaic[8776:]) and not np.any(mosaic[:8776,11744:])
        pixels = mosaic[20:8756,32:11680].copy()
        transferred = mosaic[14:8768,24:11776].copy()
    assert pixels.shape == (8736,11648)
    print('Validated all 414 lossless Sony tiles and full 100MP source',flush=True)

    # GFX native metadata uses crop (8,7). Preserve the IED even Bayer placement
    # plus odd crop-top convention. The source array starts at (8,6), therefore
    # the on-disk recommendation is one row below it, as in IED's other cameras.
    # This avoids the former x=80 crop overflowing LibRaw's 11662px visible width.
    baseline_crop = (8,6,11648,8736)
    crop = raf.adobe_compatible_crop(baseline_crop)
    assert crop == (8,7,11648,8736)
    canvas = np.full(raf.CANVAS_WH[::-1],512,np.uint16)
    canvas[:,:transferred.shape[1]] = transferred
    assert np.array_equal(canvas[6:8742,8:11656],pixels)
    del transferred
    wb = [2606,1024,1789,1024]  # LibRaw/IED RGBG order
    donor = app.load_profile()
    with tempfile.TemporaryDirectory(prefix='.ied-100mp-',dir=HERE) as name:
        work = Path(name)
        (work/'source.ARW').write_bytes(data)
        info = app.tags(work/'source.ARW')
        jpeg = make_preview(parsed,donor,work,info,wb)
        image = build(donor,jpeg,canvas,wb,crop)
        temp = work/'verified.RAF'
        with temp.open('xb') as f:
            f.write(image);f.flush();os.fsync(f.fileno())
        digest = hashlib.sha256(image).hexdigest()
        assert sha(temp) == digest
        del image
        tags = app.tags(temp)
        assert tags['IFD0:Model'] == 'GFX100S II'
        assert tags['FujiIFD:BitsPerSample'] == 14
        assert tags['RAF:RawImageCropTopLeft'] == '7 8'
        assert tags['RAF:RawImageCroppedSize'] == '11648 8736'
        assert tags['RAF:RawImageAspectRatio'] == '4 3'
        assert tags['RAF:RawExposureBias'] == -0.49
        assert app.jpeg_info(raf.raf_parts(temp.read_bytes())['jpeg'])[0] == (11648,8736)
        with rawpy.imread(str(temp)) as raw:
            assert np.array_equal(raw.raw_image,canvas)
            assert np.array_equal(raw.raw_image[6:8742,8:11656],pixels)
            assert raw.raw_pattern.tolist() == [[0,1],[3,2]]
            assert raw.black_level_per_channel == [512]*4
            assert raw.camera_whitebalance[:3] == [2606,1024,1789]
            assert raw.white_level == 15872
            sizes = raw.sizes
            assert [sizes.crop_left_margin,sizes.crop_top_margin,sizes.crop_width,sizes.crop_height] == raf.libraw_recommended_crop(crop)
            assert 8+11648 <= sizes.width+sizes.left_margin
            sizes_text = str(sizes)
        app.publish_temp(temp,DEST,digest)
    print('RAF full Bayer array matches; no source sample scaling',flush=True)
    assert sha(DEST) == digest and sha(SOURCE) == SOURCE_SHA
    assert all(sha(IED/name) == value for name,value in input_hashes.items())
    result = dict(source=str(SOURCE),source_sha256=SOURCE_SHA,output=str(DEST),
        output_sha256=digest,output_bytes=DEST.stat().st_size,
        ied_source=str(IED),ied_version=app.VERSION,source_files_sha256=input_hashes,
        template_profile_sha256=hashlib.sha256(donor).hexdigest(),
        source_active_xywh=[32,20,11648,8736],source_active_pixels=11648*8736,
        output_canvas_wh=list(raf.CANVAS_WH),source_array_placement_xy=[8,6],
        source_storage_window_xywh=[24,14,11752,8754],
        baseline_crop_xywh=list(baseline_crop),on_disk_crop_xywh=list(crop),
        libraw_recommended_crop_xywh=raf.libraw_recommended_crop(crop),libraw_sizes=sizes_text,
        bits_per_sample=14,storage='uncompressed uint16 little-endian words with 14-bit samples',
        sample_gain=1,black_level=512,libraw_white_level=15872,WB_RGBG=wb,
        WB_RGGB=[wb[0],wb[1],wb[3],wb[2]],
        raw_exposure_bias=-0.49,private_0x9651=-0.72,
        entire_canvas_raw_exact=True,all_101756928_source_active_samples_exact=True,
        source_and_ied_files_unchanged=True,full_source_preview_preserved=True,
        patch_grid=[364,273],patch_size=32,patches=99372,
        crop_note='Same IED +1 odd-top convention. Native GFX crop is (8,7); LibRaw rounds it to (8,8) and reduces recommended height by one. Full 11648x8736 source samples remain stored in the RAW.',
        vendor_validation='Raw File Converter/SILKYPIX actual open pending',
        builder_adaptations=['Add 11648x8736 to crop allowlist','Select 4:3 aspect ratio for the 100MP crop'],
        preview_adaptation='Resize only EXIF thumbnail to <=160x120 to respect JPEG APP1 size; preserve full 11648x8736 source preview coding',
        training_data_changed=False)
    (HERE/'conversion.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'source_files_sha256'},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
