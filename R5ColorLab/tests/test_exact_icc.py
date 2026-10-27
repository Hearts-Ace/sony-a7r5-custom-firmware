"""Saturated boundaries against independent ICC D50 matrix/TRC mathematics."""
from pathlib import Path
import unittest
import numpy as np
from PIL import ImageCms
from exact_icc import ExactRGBTransform,to_srgb
from icc_reference import independent_convert


class ICCTests(unittest.TestCase):
    def test_adobe_rgb_edges_and_mean_before_quantization(self):
        source=(Path(__file__).parent/'testdata/AdobeRGB1998.icc').read_bytes()
        destination=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        x=np.linspace(0,65535,19,dtype=np.uint16)
        rgb=np.stack(np.meshgrid(x,x,x,indexing='ij'),axis=-1).reshape(-1,3)
        expected,_=independent_convert(rgb,source,destination)
        with ExactRGBTransform(source,destination) as transform:actual=transform.convert(rgb)
        self.assertLessEqual(int(np.abs(actual.astype(int)-expected.astype(int)).max()),1)
        # Nonlinear transform must precede the center-five mean. Deliberately
        # different probes expose both wrong averaging order and RGB8 loss.
        probes=np.array([[[100,200,300],[50000,0,65000],[65535,30000,1],[10000,50000,20000],[32000,32000,32001]]],dtype=np.uint16)
        colors,audit=to_srgb(probes/65535,source)
        with ExactRGBTransform(source,destination) as transform:
            separate=transform.convert_float(probes/65535)
            wrong=transform.convert_float((probes/65535).mean(1))
        np.testing.assert_array_equal(colors,separate)
        self.assertGreater(float(np.abs(colors.mean(1)-wrong).max()),.001)
        self.assertFalse(audit['intermediate_quantization'])


if __name__=='__main__':unittest.main()
