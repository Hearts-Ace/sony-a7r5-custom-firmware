"""Run unchanged UI/Fn/cancel replays against an explicit final ELF and module.
Writes a separate source/ELF binding for each original receipt; no code overlays.
"""
from pathlib import Path
import argparse,hashlib,json,runpy,sys
H=Path(__file__).resolve().parent;P=H.parent
p=argparse.ArgumentParser();p.add_argument('--case',choices=['ui','visibility','fn','cancel','lifecycle','lazy'],required=True);p.add_argument('--ap',type=Path,required=True);p.add_argument('--module',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
ap=a.ap.resolve();build=a.module.resolve();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
receipt=out/(a.case+'.json');binding=out/(a.case+'-binding.json');assert not receipt.exists() and not binding.exists()
sha=lambda q:hashlib.sha256(Path(q).read_bytes()).hexdigest();original_ap=sha(ap);original_module=sha(build/'module.json');original_rx=sha(build/'rx.bin')
scripts={'ui':P/'ui/replay_ui.py','visibility':P/'ui/replay_visibility.py','fn':P/'ui/replay_fn_native.py','cancel':P/'ui/replay_ordered_cancel.py','lifecycle':P/'cancel/replay_lifecycle.py','lazy':P/'cancel/replay_lazy_capture.py'};script=scripts[a.case]
sys.path[:0]=[str(P/'ui'),str(P/'cancel')]
if a.case in ('lifecycle','lazy'):
 view=out/('view-'+a.case);(view/'ap').mkdir(parents=True,exist_ok=False)
 (view/'ap/appFw-NONINSTALLABLE.so').symlink_to(ap);(view/'module').symlink_to(build,target_is_directory=True)
 sys.argv=[str(script),str(receipt),str(view)]
else:sys.argv=[str(script),'--candidate',str(ap),'--module',str(build),'--output',str(receipt)]
argv=list(sys.argv);before_script=sha(script);runpy.run_path(str(script),run_name='__main__')
r=json.loads(receipt.read_text());assert r['passed'];assert r.get('AP_sha256',original_ap)==original_ap;assert sha(ap)==original_ap and sha(build/'module.json')==original_module and sha(build/'rx.bin')==original_rx and sha(script)==before_script
sources={str(script):sha(script),str(Path(__file__).resolve()):sha(__file__)}
for m in sys.modules.values():
 q=getattr(m,'__file__',None)
 if q and str(Path(q).resolve()).startswith(str(P)) and str(q).endswith('.py'):sources[str(Path(q).resolve())]=sha(q)
result=dict(passed=True,case=a.case,AP=str(ap),AP_sha256=original_ap,module=str(build),module_manifest_sha256=original_module,module_rx_sha256=original_rx,invocation=argv,receipt=str(receipt),receipt_sha256=sha(receipt),source_hashes=sources,no_runtime_production_overlay=True,device_tested=False,legacy_lifecycle_AP_binding='Exact read-only symlink view and explicit FinalAP import inputs' if a.case=='lifecycle' else None)
binding.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(binding=str(binding),passed=True,AP_sha256=original_ap)))
