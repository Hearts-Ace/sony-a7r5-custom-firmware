"""Copy the established local release machinery into the new 4.33 scope.

This records a mechanical baseline only; feature-specific gates and archive
replacement scope must be implemented before any package can be built.
"""
from pathlib import Path
import hashlib,json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'analysis/r5_custom_menu432_wheel_20261028'

def main():
    rows=[]
    for stem in ('package','release_gate','verify_delivery','run_offline','finalize'):
        source=OLD/(stem+'432.py');target=HERE/(stem+'433.py')
        text=source.read_text().replace('432','433').replace('4.32','4.33').replace('3204','3304')
        text=text.replace('build_r5_4.33_wheel_20261028','build_r5_4.33_color_fn_20261028')
        if stem=='verify_delivery':text=text.replace('h.versionMinor, h.model','h.versionMinor, h.model').replace('(4, 0x32, 0x11030080','(4, 0x33, 0x11030080')
        assert not target.exists(),target
        target.write_text(text)
        rows.append(dict(source=str(source.relative_to(ROOT)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                         target=str(target.relative_to(ROOT)),initial_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    (HERE/'release_tools_baseline.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(dict(prepared=len(rows))))

if __name__=='__main__':main()
