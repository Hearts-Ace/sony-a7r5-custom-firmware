#!/usr/bin/env python3
"""Stable AI/terminal interface. Stdout is one JSON result; progress goes to stderr."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'site'),str(ROOT/'vendor/pmca_source')]
sys.dont_write_bytecode=True
import argparse, contextlib, datetime, json, os, subprocess, uuid
import bootstrap
from common import save, load, safe

SCHEMA='r5-workbench-cli/1'

def describe():
    from card import filters
    return dict(schema=SCHEMA,version='0.2.1',firmware='4.36',bundled_filters=filters(),
        guide=str(ROOT.parent/'AI_GUIDE.md'),manifest=str(ROOT/'agent-manifest.json'),
        commands=load(ROOT/'agent-manifest.json')['commands'],
        output=dict(stdout='one JSON object',progress='stderr',success_exit=0,error_exit=1),
        natural_language='AI reads the user request and maps it to these fixed commands; no language-model service is embedded',
        startup_enumerates_USB=False,includes_filter_training_workbench=False)

def task(root,command,values):
    state=Path(os.environ.get('R5_WORKBENCH_STATE_DIR',Path.home()/'Library/Application Support/R5FlashWorkbench'))
    root=Path(root).expanduser().resolve() if root else state/'Tasks'
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    run=uuid.uuid4().hex;stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')
    job=root/(stamp+'_'+command+'_'+run[:6]);job.mkdir(mode=0o700)
    request=dict(values,run_id=run);save(job/'request.json',request)
    return job,request

def main(argv=None):
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks-root',help='Optional local task output directory')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('describe','status','selfcheck','usb-status'):sub.add_parser(name)
    p=sub.add_parser('verify');p.add_argument('--firmware',required=True)
    for name in ('plan','prepare'):
        p=sub.add_parser(name);p.add_argument('--destination',required=True);p.add_argument('--firmware')
    p=sub.add_parser('build');g=p.add_mutually_exclusive_group(required=True);g.add_argument('--original-dat');g.add_argument('--inputs')
    p.add_argument('--private-key');p.add_argument('--output',required=True)
    p=sub.add_parser('backup')
    p=sub.add_parser('install-trust');p.add_argument('--backup',required=True)
    p=sub.add_parser('recover');p.add_argument('--previous',required=True)
    p=sub.add_parser('result');p.add_argument('path')
    a=parser.parse_args(argv);job=None
    try:
        # Route ordinary progress away from the machine-readable result channel.
        with contextlib.redirect_stdout(sys.stderr):
            if a.command=='describe':result=describe()
            elif a.command=='result':result=load(Path(a.path).expanduser().resolve())
            elif a.command=='status':
                from card import filters
                state=Path(os.environ.get('R5_WORKBENCH_STATE_DIR',Path.home()/'Library/Application Support/R5FlashWorkbench'))
                root=Path(a.tasks_root).expanduser().resolve() if a.tasks_root else state/'Tasks'
                records=[]
                if root.is_dir():
                    for folder in sorted(root.iterdir(),reverse=True):
                        if folder.is_symlink() or not folder.is_dir():continue
                        resultpath=folder/'result.json'
                        records.append(dict(job=str(folder),result=str(resultpath) if resultpath.is_file() else None,
                            started=(folder/'RUNNING').exists(),finished=resultpath.is_file()))
                        if len(records)==20:break
                result=dict(ok=True,version='0.2.1',filters=filters(),tasks=records,camera_IO=False,USB_enumerated=False)
            else:
                values={}
                if a.command in ('prepare','plan'):values=dict(destination=a.destination,firmware=a.firmware)
                elif a.command=='verify':values=dict(firmware=a.firmware)
                elif a.command=='build':
                    if a.original_dat and not a.private_key:raise ValueError('--original-dat requires --private-key')
                    values=dict(original_dat=a.original_dat,private_key=a.private_key,inputs=a.inputs,destination=a.output)
                elif a.command in ('backup','install-trust','recover'):
                    values=dict(kind={'backup':'backup','install-trust':'update','recover':'recovery'}[a.command])
                    if a.command=='install-trust':values['backup_manifest']=str(Path(a.backup).expanduser().resolve())
                    if a.command=='recover':values['previous']=str(Path(a.previous).expanduser().resolve())
                job,request=task(a.tasks_root,a.command,values)
                if a.command in ('backup','install-trust','recover'):
                    # Explicit device command uses the same fixed GUI/admin entry; no sudo password is accepted.
                    if sys.platform!='darwin':raise ValueError('Device operations require macOS')
                    import shlex
                    command=shlex.join(['/usr/bin/env','-i','PATH=/usr/bin:/bin:/usr/sbin:/sbin',sys.executable,
                        '-I','-B',str(ROOT/'bootstrap.py'),'device',str(job/'request.json'),str(job)])
                    script='do shell script '+json.dumps(command,ensure_ascii=False)+' with administrator privileges'
                    process=subprocess.run(['/usr/bin/osascript','-e',script],capture_output=True,text=True)
                    if (job/'result.json').exists():result=load(job/'result.json')
                    else:raise RuntimeError(process.stderr.strip() or 'No device receipt; do not retry automatically')
                else:
                    action={'usb-status':'inspect'}.get(a.command,a.command)
                    class Tee:
                        def write(self,text):sys.stderr.write(text);return logfile.write(text)
                        def flush(self):sys.stderr.flush();logfile.flush()
                    with (job/'engine.log').open('x') as logfile,contextlib.redirect_stdout(Tee()):
                        result=bootstrap.execute(action,request,job)
                    save(job/'result.json',result)
        result=dict(result,schema=SCHEMA,job=str(job) if job else None)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return 1 if result.get('error') or result.get('ok') is False or result.get('task_complete') is False else 0
    except Exception as error:
        result=dict(ok=False,schema=SCHEMA,error=str(error),job=str(job) if job else None,automatic_retry=False)
        if job and not (job/'result.json').exists():save(job/'result.json',result)
        print(json.dumps(result,ensure_ascii=False),flush=True);return 1

if __name__=='__main__':sys.exit(main())
