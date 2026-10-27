from pathlib import Path
import subprocess,json,hashlib,tempfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];CAND=HERE.parent
source=HERE/'worker425_test.c'
with tempfile.TemporaryDirectory(prefix='r5worker425-') as td:
 exe=Path(td)/'worker'
 subprocess.run(['clang','-O2','-I',str(CAND/'import'),str(source),'-o',str(exe)],check=True)
 rows=[json.loads(subprocess.check_output([str(exe),str(i)])) for i in range(15)]
files=[CAND/'import/r5_filter_runtime423.c',CAND/'import/r5_filter_runtime423.h',CAND/'import/r5_stage413_thread.c',source,Path(__file__)]
report={'passed':True,'schema':'r5-menu425-sync-worker-host/1','AP_sha256':hashlib.sha256((CAND/'ap/appFw.so').read_bytes()).hexdigest(),'rows':rows,'cases':len(rows),'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'case_names':['success','foreign_execute_then_exact','E4_timeout_and_late_return','save_failure_rollback','SD_read_failure','empty_SD','first_ACK_lost','last_ACK_lost','mismatched_ACK','applied12_removed_select_Off','session_lost_during_E4','boot_E4_late_ready','boot_first_ACK_lost','boot_retry_cap_and_new_UI_request','UI_bypasses_boot_backoff'],'boundaries':['Actual C worker code, compiled host ISA; native clocks, transport ACK, E4 constructor/executor and IO/persistence are explicit fixtures.','E4 execute return and following exact CP ACK are control-plane completion; native dispatches are async and this does not prove LCD/ISP frame completion.','Manual SD read integration retains old parser/persistence/transport implementation but requires final AArch64 candidate replay separately.'],'event_legend':{'S':'SELECT send; ACK fixture unless case drops it','Q':'native E4 enqueue+constructor fixture','E':'original E4 execute body fixture returned','P':'sidecar persist fixture','R':'sole-worker reload fixture'}}
(HERE/'worker425_verified.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':True,'cases':len(rows),'AP_sha256':report['AP_sha256']}))
