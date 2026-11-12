"""Stage 1: per-page cleanup -> lines with styled tokens, header/page label, superscripts."""
import json, re, glob, statistics as st, unicodedata as ud

CHARFIX = str.maketrans({'ş':'ṣ','Ş':'Ṣ','ņ':'ṇ','Ņ':'Ṇ','ţ':'ṭ','Ţ':'Ṭ','ã':'ā','ä':'ā','ĩ':'ī','ũ':'ū','ç':'ś',
                         'ı':'i','Ș':'Ṣ','ș':'ṣ','ț':'ṭ','ł':'l','ń':'ṁ','ů':'ū','ĕ':'e','ǎ':'ā','Ã':'Ā','ō':'o','ē':'e'})
JUNK = re.compile(r'^[\W_]{1,3}$')

import os
def load(n):
    f=f'pages/p{n:03d}.json'
    if not os.path.exists(f): f=f'pages_old/p{n:03d}.json'
    return json.load(open(f))

def page_stats(P):
    sws=[w['sw'] for l in P['lines'] for w in l['words'] if w.get('sw') and len(w['t'])>=3]
    return (st.median(sws) if sws else 3.7)

def clean_word(t):
    t=ud.normalize('NFC',t)
    t=t.replace('āã','ā').replace('ãā','ā')
    t=t.translate(CHARFIX)
    t=re.sub(r'ā{2,}','ā',t)
    t=t.replace('$','Ś').replace('§','Ś')
    return t

def fold(s):
    s=ud.normalize('NFD',s)
    return ''.join(c for c in s if not ud.combining(c)).lower()

def tokens(line, msw):
    out=[]
    sups=[s for s in line['sups'] if s.get('ok')]
    for w in line['words']:
        t=w['t'] if line['deva'] else clean_word(w['t'])
        # drop junk tokens sitting where a superscript was masked
        if not line['deva'] and JUNK.match(t) and t not in ('—','–','-','&','(',')','|','||','||','/','“','”','‘','’','.',',',';',':'):
            near=any(s['x0']-12<=w['x1'] and w['x0']<=s['x1']+12 for s in line['sups'])
            if near or t in ('°','™','®','©','~','~-','*'): continue
        b = bool(w.get('sw')) and w['sw']>1.27*msw and len(t)>=1
        i = bool(w.get('it')) and w['it']>1.06
        out.append(dict(t=t,x0=w['x0'],x1=w['x1'],b=b,i=i,c=w.get('c',0)))
    return out
