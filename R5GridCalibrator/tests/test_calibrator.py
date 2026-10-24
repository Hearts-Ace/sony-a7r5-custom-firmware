import base64,copy,hashlib,io,json,sys,tempfile,threading,time,unittest,urllib.request,urllib.error,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
import bin_v4,probe_sets,model,images,server

def fixture():
    e=dict(number=7,short_name='TEST',full_name='Source filter',cc1_delta=[[0]*8 for _ in range(3)],block13=[[[0]*6 for _ in range(16)] for _ in range(3)],gamma_native_129=[i*512 for i in range(129)],grid_5x9x9=bin_v4.zero_grid())
    e['grid_5x9x9']['coefficients'][0][2][3][4]=13
    return bin_v4.pack(bin_v4.config([e]))

def encoded(b):return base64.b64encode(b).decode()

def picture(colors,fmt='JPEG'):
    array=np.rint(np.clip(colors,0,1)*255).astype('uint8').reshape(48,64,3)
    array=np.repeat(np.repeat(array,16,0),16,1)
    out=io.BytesIO();Image.fromarray(array).save(out,format=fmt,quality=100,subsampling=0);return out.getvalue()

class ProbeTests(unittest.TestCase):
    def test_bundle_is_one_twelve_slot_bin_with_unchanged_parameters(self):
        source=fixture();packed,meta=probe_sets.build(source,7,12)
        cfg=bin_v4.unpack(packed);original=bin_v4.unpack(source)['entries'][0]
        self.assertEqual(len(cfg['entries']),12);self.assertEqual(len(packed),29552)
        for e in cfg['entries']:
            for key in ('cc1_delta','block13','gamma_native_129'):self.assertEqual(e[key],original[key])
        np.testing.assert_array_equal(probe_sets.grid(cfg['entries'][10]),probe_sets.grid(original))
        self.assertTrue(np.all(probe_sets.grid(cfg['entries'][0])==0))
        for axis in range(3):
            g=probe_sets.grid(cfg['entries'][1+axis*2]);self.assertTrue(np.all(g[:,axis]==12));self.assertEqual(np.count_nonzero(g),405)
        self.assertEqual([e['role'] for e in meta['entries']][-2:],['test','test'])
        archive=zipfile.ZipFile(io.BytesIO(probe_sets.archive(packed,meta)))
        self.assertEqual(archive.read('R5NATIVE.BIN'),packed)
        self.assertEqual(hashlib.sha256(packed).hexdigest(),meta['probe_bin_sha256'])
        with self.assertRaises(ValueError):probe_sets.build(source,1)
        corrupt=bytearray(source);corrupt[-1]^=1
        with self.assertRaises(ValueError):probe_sets.build(bytes(corrupt),7)

class FitTests(unittest.TestCase):
    def pairs(self):
        rng=np.random.default_rng(11);x=rng.uniform(.18,.78,(600,3));a=np.column_stack([model.BT,model.OFFSET])
        response=np.array([[.8,.1,-.1],[.2,1.3,.05],[-.15,.2,.7]])
        truth=dict(coordinate_affine=a.tolist(),smooth=False,response_weights=response.tolist())
        cfg=bin_v4.unpack(probe_sets.build(fixture(),7)[0]);pairs=[]
        for i in [1,2,3,4,5,6,7,8,9,11]:
            g=probe_sets.grid(cfg['entries'][i]);y=model.predict(x,g,truth)
            pairs.append(dict(x=x,y=y,grid=g,role='test' if i==11 else 'train',buckets=np.arange(len(x))%10))
        return pairs,truth
    def test_known_response_recovery_and_heldout_isolation(self):
        pairs,truth=self.pairs();fit=model.fit(pairs,refine=False)
        self.assertLess(fit['report']['test']['rmse'],.03)
        self.assertEqual(fit['report']['excitation_rank'],3)
        self.assertLess(fit['report']['test']['rmse'],fit['report']['legacy_identity_test']['rmse']*.01)
        changed=copy.deepcopy(pairs);changed[-1]['y']=np.zeros_like(changed[-1]['y'])
        poisoned=model.fit(changed,refine=False)
        np.testing.assert_array_equal(fit['response_weights'],poisoned['response_weights'])
        np.testing.assert_array_equal(fit['coordinate_affine'],poisoned['coordinate_affine'])
        self.assertGreater(poisoned['report']['test']['rmse'],50)
        np.testing.assert_array_equal(model.predict(pairs[0]['x'],np.zeros((405,3)),fit),pairs[0]['x'])
    def test_low_rank_and_absent_effect_are_reported(self):
        pairs,_=self.pairs();p=copy.deepcopy(pairs[:1]);p[0]['y']=p[0]['x'].copy()
        result=model.fit(p,refine=True)
        self.assertEqual(result['report']['excitation_rank'],1)
        self.assertGreaterEqual(len(result['report']['warnings']),3)
        self.assertIn('不可辨识',result['report']['coordinate_note'])
    def test_coordinate_refinement_runs_and_never_trains_on_test(self):
        pairs,_=self.pairs();options=dict(starts=2,alternations=2,max_nfev=10,samples_per_pair=80);result=model.fit(pairs,refine=True,options=options)
        changed=copy.deepcopy(pairs);changed[-1]['y']=np.zeros_like(changed[-1]['y'])
        other=model.fit(changed,refine=True,options=options)
        np.testing.assert_array_equal(result['coordinate_affine'],other['coordinate_affine'])
        self.assertEqual(len(result['report']['candidates']),10)
        runs=result['report']['optimization']['runs']
        self.assertEqual(len(runs),8)
        self.assertTrue(all(r['nfev']<=10 and r['residual_calls']>=r['nfev'] for r in runs))
        self.assertLess(result['report']['test']['rmse'],.05)

class ImageTests(unittest.TestCase):
    def test_mpo_primary_frame_is_accepted(self):
        from unittest.mock import patch
        picture=Image.new('RGB',(256,128),(70,100,140))
        picture.format='MPO';picture.info={}
        with patch.object(images.Image,'open',return_value=picture):
            array,bits,_=images.decode(b'fake-MPF-JPEG')
        self.assertEqual(array.shape,(128,256,3));self.assertEqual(bits,8)

    def test_camera_jpg_exif_orientation_and_embedded_icc(self):
        from PIL import ImageCms,ImageOps
        colors=np.zeros((160,240,3),dtype='uint8');colors[:,:120]=[80,120,180];colors[:,120:]=[180,90,60]
        im=Image.fromarray(colors);exif=Image.Exif();exif[274]=6
        icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        out=io.BytesIO();im.save(out,format='JPEG',quality=98,exif=exif,icc_profile=icc)
        arr,bits,policy=images.decode(out.getvalue())
        self.assertEqual(arr.shape,(240,160,3));self.assertIn('ICC-converted',policy)
        samples,audit=images.sample(out.getvalue(),out.getvalue())
        self.assertGreater(audit['blocks'],40)

    def test_tiff_16bit_and_jpg_dimensions(self):
        import tifffile
        x=np.random.default_rng(3).uniform(.15,.8,(3072,3));raw=picture(x);samples,audit=images.sample(raw,raw)
        self.assertGreater(audit['blocks'],1000);np.testing.assert_array_equal(samples['x'],samples['y'])
        image=np.full((128,128,3),34567,dtype='uint16');out=io.BytesIO();tifffile.imwrite(out,image,photometric='rgb')
        array,bits,profile=images.decode(out.getvalue());self.assertEqual(bits,16);self.assertEqual(int(array[0,0,0]),34567)
        bad=io.BytesIO();Image.new('RGB',(128,128)).save(bad,format='PNG')
        with self.assertRaises(ValueError):images.sample(raw,bad.getvalue())

class HTTPTests(unittest.TestCase):
    def test_full_generate_upload_fit_export_and_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=server.DATA;server.DATA=Path(tmp)
            for d in ('sets','captures','pairs','fits'):(server.DATA/d).mkdir()
            http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{http.server_port}'
            def req(path,data=None,origin=None):
                headers={'Content-Type':'application/json'}
                if origin:headers['Origin']=origin
                request=urllib.request.Request(base+path,data=json.dumps(data).encode() if data else None,headers=headers)
                try:
                    with urllib.request.urlopen(request,timeout=30) as r:
                        b=r.read();return json.loads(b) if r.headers['Content-Type'].startswith('application/json') else b
                except urllib.error.HTTPError as error:
                    error.msg=error.read().decode();raise
            try:
                raw=fixture();self.assertEqual(req('/api/bin',{'bin':encoded(raw)})['entries'][0]['number'],7)
                meta=req('/api/probes',{'bin':encoded(raw),'number':7,'amplitude':12})
                archive=zipfile.ZipFile(io.BytesIO(req('/api/probe-download/'+meta['id'])));cfg=bin_v4.unpack(archive.read('R5NATIVE.BIN'))
                x=np.random.default_rng(22).uniform(.2,.75,(3072,3));before=picture(x)
                cap=req('/api/capture',dict(set_id=meta['id'],name='Synthetic scene',base_look='ST',conditions='fixed',baseline=encoded(before),confirmed=True))
                truth=dict(coordinate_affine=np.column_stack([model.BT,model.OFFSET]).tolist(),smooth=False,response_weights=[[.8,.1,0],[.1,1.2,.05],[0,-.1,.7]])
                pairids=[]
                for n in (2,4,6,8,9,10,12):
                    y=model.predict(x,probe_sets.grid(cfg['entries'][n-1]),truth)
                    photo=req('/api/photo',dict(capture_id=cap['id'],number=n,image=encoded(picture(y))))
                    pairids.append(photo['id']);self.assertTrue(photo['baseline_bin_verified']);self.assertEqual(photo['probe_number'],n)
                with self.assertRaises(urllib.error.HTTPError):req('/api/photo',dict(capture_id=cap['id'],number=2,image=encoded(before)))
                drift=req('/api/photo',dict(capture_id=cap['id'],number=1,image=encoded(before)));self.assertEqual(drift['drift']['rmse'],0)
                self.assertEqual(len(req('/api/captures')[0]['uploaded']),7)
                jid=req('/api/fit',dict(pairs=pairids,refine=False))['id']
                for _ in range(100):
                    state=req('/api/status/'+jid)
                    if state['state']!='running':break
                    time.sleep(.1)
                self.assertEqual(state['state'],'done',state)
                self.assertLess(state['result']['report']['test']['rmse'],1)
                exported=zipfile.ZipFile(io.BytesIO(req('/api/export/'+jid)));self.assertIn('model.py',exported.namelist())
                with self.assertRaises(urllib.error.HTTPError):req('/api/bin',{'bin':encoded(raw)},'https://other.example')
                self.assertIn('网格'.encode(),req('/'))
            finally:http.shutdown();http.server_close();server.DATA=old

if __name__=='__main__':unittest.main()


class OptimizationTests(unittest.TestCase):
    def test_options_rejected(self):
        for options in [dict(max_nfev=0),dict(starts=True),dict(alternations=7),dict(unknown=1)]:
            with self.assertRaises(ValueError):model.optimization_options(options)
    def test_strata_keep_rare_colors_and_training_only(self):
        x=np.vstack([np.full((1000,3),.5),[[.9,.1,.1],[.1,.9,.1],[.1,.1,.9]],[[1,1,0]]])
        selected=model.stratified_indices(x,np.arange(1003),40)
        self.assertEqual(len(selected),40)
        self.assertTrue({1000,1001,1002}.issubset(set(selected)))
        self.assertNotIn(1003,selected)
        np.testing.assert_array_equal(selected,model.stratified_indices(x,np.arange(1003),40))
