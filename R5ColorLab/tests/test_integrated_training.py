"""One-job native/PC pipeline contracts; the real numerical runs are separate."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import server


class IntegratedTrainingTests(unittest.TestCase):
    def test_ui_has_one_training_switch_and_no_separate_fitting_module(self):
        from html.parser import HTMLParser
        class Elements(HTMLParser):
            def __init__(self):super().__init__();self.ids=[]
            def handle_starttag(self,tag,attrs):
                value=dict(attrs).get('id')
                if value:self.ids.append(value)
        html=(server.STATIC/'index.html').read_text();elements=Elements();elements.feed(html)
        self.assertEqual(len(elements.ids),len(set(elements.ids)))
        self.assertLess(html.index('id="lut"'),html.index('id="pcTraining"'))
        self.assertLess(html.index('id="pcTraining"'),html.index('id="gamut"'))
        self.assertNotIn('pcFit',elements.ids)
        self.assertIn('resultMode',elements.ids)
        self.assertIn('nativeStages',elements.ids)

    def test_option_controls_solver_and_persisted_final_artifact(self):
        for enabled in [False, True]:
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);identifier='fixture'
                commands=[]
                class Process:
                    def __init__(self, cmd, **kwargs):commands.append(cmd)
                    def wait(self, **kwargs):return 0
                def finish(output,*args):return {'config':{},'heldout':{}}
                def pc(output):
                    (output/'pc_compensation.json').write_text('{"schema":"fixture"}')
                    return {'metrics':{'test':{'compensated':{'rmse':1}}}}
                def prepare(lut,gamut,output,dataset_id=None):
                    import chart_datasets
                    (output/'input_audit.json').write_text(json.dumps(dict(dataset_id=chart_datasets.get(dataset_id).DATASET_ID)))
                job={'id':identifier,'status':'queued'}
                with patch.object(server,'RUNS',root),patch.dict(server.JOBS,{identifier:job},clear=True), \
                     patch.object(server.core,'prepare_target',side_effect=prepare),patch.object(server.core,'finish_fit',side_effect=finish), \
                     patch.object(server.subprocess,'Popen',Process),patch('pc_compensation.generate',side_effect=pc) as generate:
                    server.work(identifier,dict(lut='fixture',gamut='S-Gamut3',evaluations=1,number=1,short_name='ST',full_name='ST',white_balance=enabled,pc_compensation=enabled,pc_options=dict(curve_mode='qaq-grid',grid_enabled=True,response=[[1,0,0],[0,1,0],[0,0,1]]),group_weights=dict(random=1,primaries=2,gray=3,colorchecker24=4),search_options=dict(starts=3,adaptive_rounds=1,perceptual_weight=.4,quantization_sweeps=2,parameter_smoothing=0,gamma_color_rounds=0)))
                    self.assertEqual(job['status'],'done',job.get('error'))
                    self.assertEqual('--pc-compensation' in commands[0],enabled)
                    self.assertEqual('--white-balance' in commands[0],enabled)
                    self.assertEqual(json.loads(commands[0][commands[0].index('--pc-options')+1]),dict(curve_mode='qaq-grid',grid_enabled=True,response=[[1,0,0],[0,1,0],[0,0,1]]))
                    self.assertEqual(json.loads(commands[0][commands[0].index('--group-weights')+1]),dict(random=1,primaries=2,gray=3,colorchecker24=4))
                    self.assertEqual(json.loads(commands[0][commands[0].index('--search-options')+1]),dict(starts=3,adaptive_rounds=1,perceptual_weight=.4,quantization_sweeps=2,parameter_smoothing=0,gamma_color_rounds=0,output_continuity=0,primary_tonal_weight=1.0,hue24_tonal_weight=1.0))
                    self.assertEqual(generate.call_count,int(enabled))
                    saved=json.loads((root/identifier/'job.json').read_text())
                    self.assertEqual(saved['result']['pc_compensation']['enabled'],enabled)
                    self.assertNotIn('process',saved)
                    self.assertIn('finished',saved)


if __name__=='__main__':unittest.main()
