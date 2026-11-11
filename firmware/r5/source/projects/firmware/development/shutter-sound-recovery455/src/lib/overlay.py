import io

class OverlayStream(io.RawIOBase):
 def __init__(self,source,rows):self.f=source.open('rb');self.rows=rows;self.position=0;self.length=source.stat().st_size
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.position
 def seek(self,n,whence=0):
  self.position=n if whence==0 else self.position+n if whence==1 else self.length+n
  if self.position<0:raise ValueError('Negative offset')
  return self.position
 def read(self,n=-1):
  n=max(0,self.length-self.position)if n<0 else min(n,max(0,self.length-self.position));start=self.position;self.f.seek(start);result=bytearray(self.f.read(n));end=start+len(result)
  for lo,hi,path in self.rows:
   if lo<end and hi>start:
    a,b=max(start,lo),min(end,hi)
    with path.open('rb')as f:f.seek(a-lo);replacement=f.read(b-a)
    assert len(replacement)==b-a;result[a-start:b-start]=replacement
  self.position=end;return bytes(result)
 def close(self):self.f.close();super().close()

class Overlay:
 def __init__(self,source,rows):self.source,self.rows=source,rows
 def open(self,mode):assert mode=='rb';return OverlayStream(self.source,self.rows)
 def stat(self):return self.source.stat()
