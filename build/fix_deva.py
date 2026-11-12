import json, glob, re, io, subprocess, numpy as np
from PIL import Image
from page import tsv, style, IMG, S
import os
fixed = 0
for f in sorted(glob.glob('pages/p*.json')):
    P = json.load(open(f))
    bad = []
    for l in P['lines']:
        if not l['deva']:
            continue
        txt = ''.join(w['t'] for w in l['words'])
        dv = len(re.findall(r'[ऀ-ॿ]', txt))
        lat = len(re.findall(r'[A-Za-z0-9{}\[\]()€$^&;:"\'.,]', txt))
        if dv < 0.75 * max(1, len(txt)) or lat >= 3:
            bad.append(l)
    if not bad:
        continue
    p = IMG % P['n']
    if not os.path.exists(p): p = p[:-3] + 'jpg'
    g = np.array(Image.open(p).convert('L'))
    for l in bad:
        crop = g[max(0, l['t'] - 3):l['b'] + 3]
        big = Image.fromarray(crop).resize((crop.shape[1] * S, crop.shape[0] * S), Image.LANCZOS)
        pad = Image.new('L', (big.size[0], big.size[1] + 40), 255); pad.paste(big, (0, 20))
        ws = tsv(pad, 'Latin', ('--psm', '7'))
        arr = np.array(pad) < 140
        nw = []
        for w in ws:
            sw, it = style(arr[w['y']:w['y'] + w['h'], w['x']:w['x'] + w['w']])
            nw.append(dict(x0=w['x'] // S, x1=(w['x'] + w['w']) // S, t=w['t'], c=round(w['conf']), sw=sw, it=it))
        # keep as Devanagari if Latin reading is worse
        lt = ''.join(w['t'] for w in nw)
        if sum(c.isalpha() for c in lt) < 0.5 * max(1, len(lt)):
            continue
        l['words'] = nw; l['deva'] = False; l['refixed'] = True
        fixed += 1
    json.dump(P, open(f, 'w'), ensure_ascii=False)
print('re-read lines:', fixed)
