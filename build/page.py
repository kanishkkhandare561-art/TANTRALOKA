import sys, os, json, subprocess, io, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
sys.path.insert(0, os.path.dirname(__file__))
from lines import load, segment_lines, is_deva, superscripts, hspan
from seg import find_rule
IMG='/tmp/ep/x/OEBPS/images/p%03d.png'
S=2  # upscale

def tsv(img, lang, extra=()):
    buf=io.BytesIO(); img.save(buf,'PNG')
    r=subprocess.run(['tesseract','stdin','stdout','-l',lang,*(extra if '--psm' in extra else ('--psm','6',*extra)),'tsv'],input=buf.getvalue(),capture_output=True)
    out=[]
    for ln in r.stdout.decode('utf-8','replace').split('\n')[1:]:
        f=ln.split('\t')
        if len(f)<12 or f[0]!='5': continue
        txt=f[11]
        if not txt.strip(): continue
        out.append(dict(x=int(f[6]),y=int(f[7]),w=int(f[8]),h=int(f[9]),conf=float(f[10]),t=txt,blk=int(f[2]),par=int(f[3]),ln=int(f[4])))
    return out

def style(bw):
    """bw: bool array of a word at 2x. returns stroke width, italic score"""
    if bw.sum()<20: return None,None
    dt=ndi.distance_transform_edt(bw)
    sk=skeletonize(bw)
    sw=2*dt[sk].mean() if sk.any() else 0
    h,w=bw.shape
    def sharp(tan):
        ys=np.arange(h)[:,None]; 
        coords=np.nonzero(bw)
        xs=(coords[1]+ (coords[0]-h/2)*tan).astype(int); xs-=xs.min()
        pr=np.bincount(xs)
        return (pr.astype(float)**2).sum()
    s0=sharp(0.0); s1=sharp(0.21)
    return float(sw), float(s1/s0)

def process(n):
    p=IMG%n
    if not os.path.exists(p): p=p[:-3]+'jpg'
    g,d=load(p); H,W=d.shape
    r=find_rule(p)
    regs=[('m',0,(r[0]-3) if r else H)]
    if r: regs.append(('n',r[0]+6,H))
    L=[]
    for reg,a,b in regs:
        for t,bo in segment_lines(d,a,b):
            x0,x1=hspan(d,t,bo)
            dv=is_deva(d,t,bo)
            sups=[] if dv else superscripts(d,t,bo)
            L.append(dict(reg=reg,t=int(t),b=int(bo),x0=x0,x1=x1,deva=bool(dv),sups=[dict(t=s[0],b=s[1],x0=s[2],x1=s[3]) for s in sups],words=[]))
    # read superscript digits first
    allsup=[s for l in L for s in l['sups']]
    for s in allsup: s['n']=None
    if allsup:
        crops=[]
        for s in allsup:
            c=g[max(0,s['t']-2):s['b']+2, max(0,s['x0']-2):s['x1']+2]
            crops.append(Image.fromarray(c).resize((c.shape[1]*5,c.shape[0]*5),Image.LANCZOS))
        cw=max(c.size[0] for c in crops)+80; ch=max(c.size[1] for c in crops)+50
        sheet=Image.new('L',(cw,ch*len(crops)),255)
        for k,c in enumerate(crops): sheet.paste(c,(40,k*ch+25))
        res=tsv(sheet,'eng',('-c','tessedit_char_whitelist=0123456789'))
        for k,s in enumerate(allsup):
            txt=''.join(w['t'] for w in sorted([w for w in res if k*ch<=w['y']+w['h']/2<(k+1)*ch],key=lambda w:w['x']))
            s['n']=txt if txt.isdigit() else None
    for s in allsup:
        if s['n'] is None:
            c=g[max(0,s['t']-4):s['b']+4, max(0,s['x0']-4):s['x1']+4]
            im=Image.fromarray(c).resize((c.shape[1]*6,c.shape[0]*6),Image.LANCZOS)
            pad=Image.new('L',(im.size[0]+60,im.size[1]+60),255); pad.paste(im,(30,30))
            buf=io.BytesIO(); pad.save(buf,'PNG')
            rr=subprocess.run(['tesseract','stdin','stdout','-l','eng','--psm','8','-c','tessedit_char_whitelist=0123456789'],input=buf.getvalue(),capture_output=True)
            t=rr.stdout.decode().strip()
            s['n']=t if t.isdigit() else None
            s['n2']=True
    for l in L:
        for s in l['sups']:
            s['start']= s['x0']<=l['x0']+3
            s['ok']= bool(s['n']) and (len(s['n'])>=2 or (n<26 and (s['x1']-s['x0'])<=8) or (l['reg']=='n' and s['start']))
    big=Image.fromarray(g).resize((W*S,H*S),Image.LANCZOS)
    bigarr=np.array(big)
    lat=bigarr.copy(); dev=np.full_like(bigarr,255)
    for l in L:
        if l['deva']:
            dev[l['t']*S:l['b']*S]=bigarr[l['t']*S:l['b']*S]
            lat[l['t']*S:l['b']*S]=255
        for s in l['sups']:
            if s['ok']: lat[s['t']*S-1:s['b']*S+1, s['x0']*S-1:s['x1']*S+2]=255
    words=[(w,'lat') for w in tsv(Image.fromarray(lat),'Latin')]
    if any(l['deva'] for l in L):
        words+=[(w,'dev') for w in tsv(Image.fromarray(dev),'san')]
    binbig=bigarr<140
    for w,kind in words:
        cy=(w['y']+w['h']/2)/S
        best=None
        for i,l in enumerate(L):
            if l['deva']!=(kind=='dev'): continue
            ov=min(l['b'],(w['y']+w['h'])/S)-max(l['t'],w['y']/S)
            if best is None or ov>best[0]: best=(ov,i)
        if best is None: continue
        sw,it=style(binbig[w['y']:w['y']+w['h'], w['x']:w['x']+w['w']]) if kind=='lat' else (None,None)
        L[best[1]]['words'].append(dict(x0=w['x']//S,x1=(w['x']+w['w'])//S,t=w['t'],c=round(w['conf']),sw=sw,it=it))
    for l in L: l['words'].sort(key=lambda w:w['x0'])
    return dict(n=n,W=W,H=H,rule=r[0] if r else None,lines=L)

if __name__=='__main__':
    out=sys.argv[1]
    for n in map(int,sys.argv[2:]):
        fn=f'{out}/p{n:03d}.json'
        if os.path.exists(fn): continue
        res=process(n)
        json.dump(res,open(fn,'w'),ensure_ascii=False)
