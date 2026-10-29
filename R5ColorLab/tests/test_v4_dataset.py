import io
import unittest
import zipfile
import numpy as np
import core,chart_target,v4_dataset,anchor_dataset

class V4Tests(unittest.TestCase):
    def test_default_and_tamper(self):
        a,audit=core.measured_inputs(v4_dataset.DATASET_ID)
        self.assertEqual(audit['dataset_id'],v4_dataset.DATASET_ID)
        self.assertEqual(a['input'].shape,(99372,9,3))
        self.assertTrue(anchor_dataset.validate(a)['passed'])
        a['sensor_codes'][0,0]+=1
        with self.assertRaises(ValueError):anchor_dataset.validate(a)

    def test_no_duplicate_leak_and_anchors(self):
        a,_=v4_dataset.load()
        _,g=np.unique(a['sensor_codes'],axis=0,return_inverse=True)
        sets=[set(g[a['split']==s]) for s in ('train','valid','test')]
        for i in range(3):
            for j in range(i):self.assertFalse(sets[i]&sets[j])
        self.assertEqual(np.sum(a['anchor_index']>=0),284)
        self.assertTrue(np.all(a['split'][a['anchor_index']>=0]=='train'))

    def test_actual_16bit_reference_sampling(self):
        import tifffile
        data=(v4_dataset.FOLDER/'reference-sRGB16.tiff').read_bytes()
        t,audit=chart_target.decode(data,v4_dataset.DATASET_ID)
        pixels=tifffile.imread(io.BytesIO(data))
        expected=pixels[16::32,16::32].reshape(-1,3)/65535
        np.testing.assert_allclose(t,expected,atol=2e-16,rtol=0)
        self.assertEqual(audit['schema'],v4_dataset.DATASET_ID)
        self.assertEqual(audit['bits_per_channel'],16)

    def test_download_exact_raf(self):
        with zipfile.ZipFile(io.BytesIO(chart_target.download(v4_dataset.DATASET_ID))) as z:
            m=v4_dataset.metadata()
            self.assertEqual(core.sha(z.read(m['raf_file'])),m['raf_sha256'])

if __name__=='__main__':unittest.main()
