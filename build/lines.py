import numpy as np
from PIL import Image
from scipy import ndimage as ndi

def load(path):
    g=np.array(Image.open(path).convert('L'))
    return g, g<140

def segment_lines(d, y0, y1, pitch=None):
    sub=d[y0:y1]; prof=sub.sum(axis=1).astype(float)
    if prof.max()==0: return []
    ink=prof>2
    bands=[];start=None
    for i,v in enumerate(ink):
        if v and start is None: start=i
        if not v and start is not None: bands.append([start,i]); start=None
    if start is not None: bands.append([start,len(ink)])
    hs=[b[1]-b[0] for b in bands if b[1]-b[0]>=8]
    if not hs: return []
    typ=pitch or pitch_of(d,y0,y1) or float(np.median(hs))
    typ=min(typ,float(np.median(hs))*1.2) if len(hs)>3 else typ
    out=[]
    for a,b in bands:
        if b-a>1.55*typ:
            # split at minima of smoothed profile
            sm=np.convolve(prof[a:b],np.ones(3)/3,mode='same')
            n=int(round((b-a)/typ))
            cuts=[]
            for k in range(1,n):
                c=int(a+k*(b-a)/n); lo=max(a+4,c-int(typ*0.35)); hi=min(b-4,c+int(typ*0.35))
                if hi<=lo: continue
                m=lo+int(np.argmin(sm[lo-a:hi-a])); cuts.append(m)
            prev=a
            for c in cuts: out.append([prev,c]); prev=c
            out.append([prev,b])
        else: out.append([a,b])
    # merge tiny bands
    changed=True
    while changed:
        changed=False
        for k,b in enumerate(out):
            if b[1]-b[0]<7 and len(out)>1:
                cand=[]
                if k>0: cand.append((b[0]-out[k-1][1],k-1))
                if k+1<len(out): cand.append((out[k+1][0]-b[1],k+1))
                gap,j=min(cand)
                if gap>12: continue
                lo=min(k,j); out[lo]=[min(b[0],out[j][0]),max(b[1],out[j][1])]; del out[max(k,j)]
                changed=True; break
    return [(a+y0,b+y0) for a,b in out if b-a>=5]

def hspan(d,top,bot):
    cols=np.where(d[top:bot].any(axis=0))[0]
    return (int(cols[0]),int(cols[-1])+1) if len(cols) else (0,0)

def is_deva(d, top, bot):
    x0,x1=hspan(d,top,bot)
    if x1-x0<40: return False
    frac=d[top:bot,x0:x1].mean(axis=1)
    srt=np.sort(frac)[::-1]
    am=int(frac.argmax())
    return srt[0]>0.45 and srt[0]>1.3*srt[2] and am<0.5*(bot-top)

def pitch_of(d,y0,y1):
    prof=d[y0:y1].sum(axis=1).astype(float)
    if len(prof)<80: return None
    p=prof-prof.mean()
    best=None
    for lag in range(16,40):
        c=(p[:-lag]*p[lag:]).sum()
        if best is None or c>best[0]: best=(c,lag)
    return best[1]

def body_band(d,top,bot):
    prof=d[top:bot].sum(axis=1).astype(float)
    thr=0.35*prof.max()
    rows=np.where(prof>thr)[0]
    return top+rows[0], top+rows[-1]+1

def superscripts(d, top, bot):
    xt,bl=body_band(d,top,bot); xh=max(4,bl-xt)
    t2=max(0,top-3)
    sub=d[t2:bot]
    lab,n=ndi.label(sub); objs=ndi.find_objects(lab)
    sup=[]
    for i,s in enumerate(objs):
        ys,xs=s; a=ys.start+t2; b=ys.stop+t2; hgt=b-a
        if b <= xt+0.6*xh and a < xt-0.12*xh and hgt>=0.5*xh and hgt<=1.25*xh and (lab[s]==i+1).sum()>=8 and (xs.stop-xs.start)<=1.2*xh:
            sup.append([a,b,xs.start,xs.stop])
    sup.sort(key=lambda c:c[2]); cl=[]
    for c in sup:
        if cl and c[2]-cl[-1][3]<=3:
            q=cl[-1]; cl[-1]=[min(q[0],c[0]),max(q[1],c[1]),q[2],max(q[3],c[3])]
        else: cl.append(c)
    return [tuple(int(v) for v in c) for c in cl]
