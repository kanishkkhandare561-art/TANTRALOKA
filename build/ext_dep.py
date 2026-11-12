import json
D='/home/claude/kanishkkhandare561-art/sanskrit-depository/data/tantraloka/'
glos=json.load(open(D+'glossary.json'))
LEX=[]; LEXI={}
def lexid(e):
    k=json.dumps(e,ensure_ascii=False,sort_keys=True)
    if k not in LEXI: LEXI[k]=len(LEX); LEX.append(e)
    return LEXI[k]
units=[]
for c in ['1.1','1.2','1.3','1.4','1.5','1.6']:
    ch=json.load(open(D+c+'.json'))
    for u in ch['units']:
        segs=[]
        for s in u['segs']:
            if s['t']=='g': segs.append({'t':'g','x':s['x']}); continue
            w=[]
            for x in s.get('w',[]):
                if isinstance(x,list): w.append([x[0],lexid(ch['lex'][x[1]])])
                else: w.append(x)
            o={'t':s['t'],'w':w}
            for k in ('l','n','i'):
                if k in s: o[k]=s[k]
            segs.append(o)
        units.append({'id':u['id'],'segs':segs})
used=set()
for e in LEX:
    for p in e.get('p',[]):
        used.add(p.get('l')); 
        if p.get('r'): used.add(p['r'])
G={k:v for k,v in glos.items() if k in used}
json.dump({'units':units,'lex':LEX,'glossary':G},open('dep.json','w'),ensure_ascii=False)
print(len(units), len(LEX), len(G), len(glos))
