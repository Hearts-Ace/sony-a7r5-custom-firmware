import unittest,json,struct,copy,sys
from pathlib import Path
import numpy as np
import core,anchor_dataset,sector16,tonal_sampling
from edit_parameter_context import RuntimeColor

class PortableTests(unittest.TestCase):
    def test_new_data_binding_and_balanced_test_split(self):
        with np.load(anchor_dataset.PAIRS)as p:a=dict(p)
        self.assertEqual(anchor_dataset.validate(a)['frontend_context'],2)
        model=RuntimeColor.from_capture(core.CAPTURE,4)
        ids,_=sector16.select(a,model)
        self.assertEqual((ids>=0).sum(),64)
        b=tonal_sampling.classify(model.color_only(a['input'])[:,4]/16383)
        np.testing.assert_array_equal(np.bincount(b[a['split']=='test'],minlength=3),[249,245,246])
        a['input']=a['input'].copy();a['input'][0,4,0]+=1
        with self.assertRaises(ValueError):anchor_dataset.validate(a)
    def test_defaults_and_v3_grid_export(self):
        html=(core.HERE/'static/index.html').read_text()
        self.assertIn('id="wbTraining" type="checkbox">',html)
        self.assertIn('id="pcTraining" type="checkbox" checked>',html)
        entries,_=core.presets();self.assertEqual(len(entries),12)
        cfg=core.config(entries[:1]);cfg['schema']='r5-native-overwrite-config/3';cfg['compensation_grid_enabled']=True
        grid=np.zeros((3,5,9,9),dtype=int);grid[0,0,0,0]=-64;grid[2,4,8,8]=63
        cfg['entries'][0]['grid_5x9x9']=dict(enabled=True,coefficients=grid.tolist())
        blob,_,fw,v=core.compile_config(cfg)
        self.assertEqual((len(blob),fw,v),(2528,'4.20',3))
        self.assertEqual(struct.unpack_from('<I',blob,128+1176)[0],1)
        self.assertEqual(blob[128+1180:128+2395],grid.astype('i1').tobytes())
    def test_no_external_symbolic_links_or_machine_paths(self):
        root=core.ROOT
        for directory in ['web','scripts','compilers','data']:
            for p in (root/directory).rglob('*'):
                self.assertFalse(p.is_symlink(),str(p))
                if p.suffix=='.py':
                    source=p.read_text()
                    self.assertNotIn('/Users/',source)
                    self.assertNotIn('/Applications/',source)
