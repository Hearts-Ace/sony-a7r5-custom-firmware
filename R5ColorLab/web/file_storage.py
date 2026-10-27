"""Independent APFS copy-on-write files; ordinary copies on other platforms."""
from pathlib import Path
import shutil
import sys


def copy_independent(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    if sys.platform == 'darwin':
        import ctypes
        import os
        library = ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True)
        clone = library.clonefile
        clone.argtypes = [ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
        clone.restype = ctypes.c_int
        if clone(os.fsencode(source),os.fsencode(destination),0) == 0:
            return 'apfs-independent-clone'
    shutil.copyfile(source,destination)
    return 'independent-copy'
