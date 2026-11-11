"""Offline evidence index; final icons decoded in approved preview, not runtime CPU testing."""
from pathlib import Path
import json
H=Path(__file__).resolve().parent
if __name__=='__main__':
 print(json.dumps(json.loads((H/'resource-scope.json').read_text()),ensure_ascii=False,indent=2))
