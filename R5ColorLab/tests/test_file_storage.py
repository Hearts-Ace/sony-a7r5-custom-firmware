import tempfile,unittest
from pathlib import Path
from file_storage import copy_independent
class IndependentStorageTests(unittest.TestCase):
 def test_copy_never_aliases_original_and_refuses_overwrite(self):
  with tempfile.TemporaryDirectory() as root:
   source=Path(root)/'source';dest=Path(root)/'dest'
   source.write_bytes(b'original pixels')
   copy_independent(source,dest)
   self.assertEqual(dest.read_bytes(),source.read_bytes())
   self.assertNotEqual(source.stat().st_ino,dest.stat().st_ino)
   dest.write_bytes(b'changed copy')
   self.assertEqual(source.read_bytes(),b'original pixels')
   with self.assertRaises(FileExistsError):copy_independent(source,dest)
if __name__=='__main__':unittest.main()
