import copy, importlib.util, json, struct, tempfile, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('adapter',Path(__file__).with_name('convert.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
codec=m.codec
class Tests(unittest.TestCase):
 def test_transfer_and_hash(self):
  template=json.loads(Path(__file__).with_name('m4-template.json').read_text())
  self.assertEqual(m.digest(template),template['payload_sha256'])
  entry=dict(number=1, short_name='SYNTH', full_name='Synthetic M4 test', cc1_delta=[[0]*8,[0]*8,[0]*8], block13=[[[0]*6 for _ in range(16)] for _ in range(3)], gamma_native_129=[min(131071, i*1024) for i in range(129)], grid_5x9x9=codec.zero_grid())
  source=codec.pack(codec.config([entry]))
  with tempfile.TemporaryDirectory() as td:
   src=Path(td)/'source.bin'; src.write_bytes(source)
   e,d=m.convert(src,template)
   p=d['parameters']
   for branch in ['photo','live']:
    self.assertEqual(p[branch]['coefficients']['values'],e['cc1_delta']);self.assertEqual(p[branch]['matrices']['values'],e['block13']);self.assertEqual(p['grid'][branch],e['grid_5x9x9']['coefficients'])
    for r in p[branch]['gamma']['records']:
     points=list(struct.unpack('<129I',bytes(r[:516])));self.assertEqual(points,[min(v,m.M4_GAMMA_CAP) for v in e['gamma_native_129']]);self.assertLessEqual(max(points),m.M4_GAMMA_CAP);self.assertEqual(struct.unpack('<I',bytes(r[544:548]))[0],points[128])
   self.assertEqual(d['defaults'],template['defaults'])
   bad=copy.deepcopy(d);bad['parameters']['live']['gamma']['records'][0][540]^=1;bad['payload_sha256']=m.digest(bad)
   with self.assertRaisesRegex(ValueError,'identical'):m.validate(bad)
   bad=copy.deepcopy(d);bad['name']='modified'
   with self.assertRaisesRegex(ValueError,'hash'):m.validate(bad)
if __name__=='__main__':unittest.main()
