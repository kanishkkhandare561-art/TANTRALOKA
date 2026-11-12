import json, glob, re, numpy as np, os
from PIL import Image
from page import tsv, IMG, S
back = kept = 0
for f in sorted(glob.glob('pages/p*.json')):
    P = json.load(open(f)); ch = False
    p = IMG % P['n']
    if not os.path.exists(p): p = p[:-3] + 'jpg'
    g = None
    for l in P['lines']:
        if not l.get('refixed'):
            continue
        if g is None: g = np.array(Image.open(p).convert('L'))
        crop = g[max(0, l['t'] - 3):l['b'] + 3]
        big = Image.fromarray(crop).resize((crop.shape[1] * S, crop.shape[0] * S), Image.LANCZOS)
        pad = Image.new('L', (big.size[0], big.size[1] + 40), 255); pad.paste(big, (0, 20))
        ws = tsv(pad, 'san', ('--psm', '7'))
        cs = np.mean([w['conf'] for w in ws]) if ws else 0
        cl = np.mean([w['c'] for w in l['words']]) if l['words'] else 0
        dv = sum(len(re.findall(r'[ऀ-ॿ]', w['t'])) for w in ws)
        tot = sum(len(w['t']) for w in ws) or 1
        if cs > cl and dv > 0.7 * tot:
            l['words'] = [dict(x0=w['x'] // S, x1=(w['x'] + w['w']) // S, t=w['t'], c=round(w['conf'])) for w in ws]
            l['deva'] = True; l['refixed'] = 'back'; back += 1; ch = True
        else:
            kept += 1
    if ch: json.dump(P, open(f, 'w'), ensure_ascii=False)
print('restored as Devanagari:', back, 'kept as Latin:', kept)
