"""Freeze small source inputs for 4.33 without touching historical builds."""
from pathlib import Path
import hashlib,json,shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'analysis/r5_custom_menu432_wheel_20261028'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    rows=[]
    directories=('import','menu_research','sync_tests','parent_evidence','style_evidence','wheel_evidence','crosscore','dependencies')
    names={'menu_parent423.py','replay_main_menu425.py','replay_title425.py','verify_inherited425.py'}
    special={'menu_hooks.json','native_extra425.json','native_list431.json','native_wheel432.json'}
    paths=[p for p in OLD.iterdir() if p.name in names]
    for directory in directories:
        paths += [p for p in (OLD/directory).iterdir() if p.is_file() and
                  (p.suffix in ('.py','.c','.h','.S') or p.name in special or directory=='dependencies')]
    for source in sorted(paths):
        relative=source.relative_to(OLD);target=HERE/relative
        assert not target.exists(),target
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        assert sha(target)==sha(source)
        rows.append(dict(source=str(source.relative_to(ROOT)),target=str(target.relative_to(ROOT)),sha256=sha(source)))
    (HERE/'baseline432_sources.json').write_text(json.dumps(dict(schema='r5-433-baseline432/1',rows=rows),indent=2)+'\n')
    print(json.dumps(dict(copied=len(rows),source=str(OLD),output=str(HERE))))

if __name__=='__main__':main()
