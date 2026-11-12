import sys, numpy as np
from PIL import Image
def runs(row):
    r=np.diff(np.concatenate(([0],row.astype(np.int8),[0])))
    st=np.where(r==1)[0]; en=np.where(r==-1)[0]
    return st,en
def find_rule(path):
    im=np.array(Image.open(path).convert('L')); h,w=im.shape; d=im<140
    for y in range(int(h*0.2), h-30):
        band=d[y-2:y+3].any(axis=0)
        if band.sum()<140: continue
        st,en=runs(band); L=en-st; i=L.argmax()
        if L[i]<140: continue
        x0,x1=st[i],en[i]
        thick=d[y-2:y+3,x0:x1].sum(axis=0).max()
        above=d[y-10:y-3,x0:x1].mean(); below=d[y+4:y+10,x0:x1].mean()
        if above<0.04 and below<0.04 and thick<=6:
            return int(y),int(x0),int(x1),h,w
    return None
if __name__=='__main__':
    import json
    out={}
    for p in sys.argv[1:]:
        out[p]=find_rule(p)
    json.dump(out,sys.stdout)
