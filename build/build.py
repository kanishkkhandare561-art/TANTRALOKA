"""Stage 2: whole-book structure from per-page OCR JSON.

Produces book.json: {pages:[...], blocks:[...], notes:{n: html}, toc:[...]}
"""
import json, re, os, math, html, unicodedata as ud, collections
from rapidfuzz import fuzz
from wordfreq import zipf_frequency
from struct1 import load, page_stats, tokens, fold

NPAGES = 514
DEP = json.load(open('dep.json'))
esc = lambda s: html.escape(s, quote=False)

# ------------------------------------------------------------------ lexicon (IAST restoration)
MGLYPH = re.compile(r'(rı|ri|rh|rm|rn|rň|ṁm|ħ|rń|ń)')

def anus(s):
    return s.replace('ṃ', 'ṁ')

LEXC = collections.Counter()
for e in DEP['lex']:
    LEXC[anus(e['w'])] += 2
    for p in e.get('p', []):
        LEXC[anus(p.get('u', ''))] += 1
        LEXC[anus(p.get('l', ''))] += 1
for k in DEP['glossary']:
    LEXC[anus(k)] += 1

def build_fold_map(counter):
    fm = collections.defaultdict(collections.Counter)
    for w, c in counter.items():
        if len(w) >= 2:
            fm[fold(w)][w] += c
    return fm

ENG_CACHE = {}
def eng(w):
    k = w.lower()
    if k not in ENG_CACHE:
        ENG_CACHE[k] = zipf_frequency(k, 'en')
    return ENG_CACHE[k]

DIAC = set('āīūṛṝḷśṣṇṭḍṅñṁṃḥĀĪŪṚŚṢṆṬḌṄÑṀḤ')

def consistent(base, cand):
    """cand may add diacritics where base has plain letters, never contradict base diacritics"""
    if len(base) != len(cand):
        return False
    for a, b in zip(base, cand):
        if a == b:
            continue
        if a in DIAC or fold(a) != fold(b):
            return False
    return True

def restore(word, italic, FM, NAMES):
    """word: core token without surrounding punctuation"""
    if not word or not re.search(r'[A-Za-zĀ-ſḀ-ỿ]', word):
        return word
    w = word.replace('&', 'ā') if re.match(r'^&[a-z]', word) else word
    has_d = any(c in DIAC for c in w)
    plain = re.sub(r'[^A-Za-z]', '', fold(w))
    if not italic and not has_d:
        # roman text: only proper names / clearly non-English words
        if w[:1].isupper():
            cands = NAMES.get(fold(w))
            if cands and (eng(w) < 3.3 or w in ('Siva', 'Sakti', 'Rama', 'Krsna')):
                best = cands.most_common(1)[0][0]
                if len(best) == len(w):
                    return best
        if eng(w) >= 2.5 or len(plain) < 4:
            return w
    bases = {w}
    occ = [m for m in MGLYPH.finditer(w)]
    if occ and len(occ) <= 3:
        for mask in range(1, 2 ** len(occ)):
            s = w; off = 0
            for k, m in enumerate(occ):
                if mask >> k & 1:
                    a, b = m.start() + off, m.end() + off
                    s = s[:a] + 'ṁ' + s[b:]; off += 1 - (m.end() - m.start())
            bases.add(s)
    best = None
    for b in bases:
        lw = b[0].lower() + b[1:] if b[:1].isupper() else b
        for cand, c in FM.get(fold(lw), {}).items():
            if consistent(lw, cand):
                score = math.log(c + 1) + (0.5 if b == w else 0) + sum(1 for x, y in zip(lw, cand) if x == y and x in DIAC) * 0.3
                if best is None or score > best[0]:
                    out = cand
                    if b[:1].isupper():
                        out = cand[0].upper() + cand[1:]
                    best = (score, out)
    if best:
        return best[1]
    if w in LEXC:
        return w
    # a lone anusvara glyph at word end
    for b in bases:
        if b != w and b.endswith('ṁ') and italic:
            return b
    return w

TOKSPLIT = re.compile(r'^([^\wĀ-ſḀ-ỿ&]*)(.*?)([^\wĀ-ſḀ-ỿ]*)$')

def fix_token(t, italic, FM, NAMES):
    m = TOKSPLIT.match(t)
    pre, core, post = m.groups()
    # inner punctuation (hyphens, slashes) -> restore each piece
    pieces = re.split(r'([-/])', core)
    pieces = [p if p in '-/' else restore(p, italic, FM, NAMES) for p in pieces]
    return pre + ''.join(pieces) + post

# ------------------------------------------------------------------ load pages
pages = []
for n in range(1, NPAGES + 1):
    P = load(n)
    msw = page_stats(P)
    for l in P['lines']:
        l['tk'] = [] if l['deva'] else tokens(l, msw)
        if l['deva']:
            l['tk'] = [dict(t=w['t'], x0=w['x0'], x1=w['x1'], b=False, i=False, c=w.get('c', 0)) for w in l['words']]
        # smooth styles of short tokens
        tk = l['tk']
        for k, t in enumerate(tk):
            letters = sum(ch.isalpha() for ch in t['t'])
            pb = tk[k - 1]['b'] if k else None
            nb = tk[k + 1]['b'] if k + 1 < len(tk) else None
            pi = tk[k - 1]['i'] if k else None
            ni = tk[k + 1]['i'] if k + 1 < len(tk) else None
            if letters < 3:
                t['b'] = bool((pb if pb is not None else nb) and (nb if nb is not None else pb))
                t['i'] = bool((pi if pi is not None else ni) and (ni if ni is not None else pi)) and letters > 0
            elif pb and nb and not t['b']:
                t['b'] = True
    pages.append(P)

# corpus-derived lexicon: OCR tokens that already carry diacritics
CORP = collections.Counter()
for P in pages:
    for l in P['lines']:
        if l['deva']:
            continue
        for t in l['tk']:
            core = TOKSPLIT.match(t['t']).group(2)
            if any(c in DIAC for c in core) and core.isalpha():
                CORP[core] += 1
for w, c in list(CORP.items()):
    if c >= 2:
        LEXC[w[0].lower() + w[1:]] += 3 * c
FM = build_fold_map(LEXC)
NAMES = collections.defaultdict(collections.Counter)
for w, c in CORP.items():
    if w[:1].isupper() and c >= 3:
        NAMES[fold(w)][w] += c

NUMLIKE = re.compile(r'[\(\[]?[\dlIO]+[a-d]*(?:[-–/][\dlIO]+[a-d]*)*[\)\],.;:]*')
for P in pages:
    for l in P['lines']:
        if l['deva']:
            continue
        for t in l['tk']:
            if NUMLIKE.fullmatch(t['t']) and re.search(r'\d', t['t']):
                t['t'] = re.sub(r'[lI]', '1', t['t']).replace('O', '0')
                continue
            t['t'] = fix_token(t['t'], t['i'], FM, NAMES)

# ------------------------------------------------------------------ page labels and headers
HDR = re.compile(r'^(?:(\d{1,3})\s+(?:CHAPTER ONE|APPENDIX.*)|(?:TANTR\S*LOKA|CHAPTER ONE|APPENDIX.*?)\s+(\d{1,3}))$', re.I)
ROMAN = re.compile(r'^[ivxlIVXL1]{1,5}$')
for P in pages:
    P['label'] = None
    main = [l for l in P['lines'] if l['reg'] == 'm']
    if not main:
        continue
    first = main[0]
    txt = ' '.join(t['t'] for t in first['tk']).strip()
    m = HDR.match(txt.replace('—', ' ').strip())
    if m:
        P['label'] = m.group(1) or m.group(2)
        first['hdr'] = True
    elif ('CHAPTER ONE' in txt.upper() or 'TANTR' in txt.upper()) and len(txt) < 40 and first['t'] < 110 and P['n'] > 15:
        num = re.findall(r'\d+', txt)
        P['label'] = num[0] if num else None
        first['hdr'] = True
    # lone page numbers (front matter) at the very top or bottom
    for l in (main[0], main[-1]):
        tx = ' '.join(t['t'] for t in l['tk']).strip()
        if not l.get('hdr') and (ROMAN.match(tx) or re.match(r'^\d{1,3}$', tx)) and (l['t'] < 110 or l['b'] > P['H'] - 120):
            l['hdr'] = True
            P['label'] = P['label'] or tx

# fill missing labels from neighbours (printed numbering = image - 14 from p.15 on)
for P in pages:
    if P['n'] >= 15:
        exp = str(P['n'] - 14)
        if P['label'] != exp:
            P['label'] = exp
    else:
        P['label'] = None

# ------------------------------------------------------------------ footnotes
def ltext(l):
    return ' '.join(t['t'] for t in l['tk'])

notes = collections.OrderedDict()   # n -> list of line dicts (with page)
note_page = {}
page_note_starts = collections.defaultdict(list)
JUNKSTART = re.compile(r'[^\w(‘“\[—–]{1,3}')
recs = []   # (page, line, cand, read, strength)
for P in pages:
    nl = [l for l in P['lines'] if l['reg'] == 'n' and not l.get('hdr')]
    if not nl:
        continue
    L = min(l['x0'] for l in nl)
    R = sorted(l['x1'] for l in nl)[len(nl) // 2]
    prevl = None
    for l in nl:
        tk = l['tk']
        cand = False; read = None; strong = False
        cont = False
        prevl_prev = prevl
        if prevl is not None and prevl['tk']:
            last = prevl['tk'][-1]['t']
            cont = prevl['x1'] >= R - 12 and not re.search(r'[.:;!?)\]’”]$', last)
        prevl = l
        ss = [s for s in l['sups'] if s['x0'] <= L + 14 and not any(t['x1'] < s['x0'] - 2 and re.search(r'[A-Za-z]{2}', t['t']) for t in tk)]
        if ss:
            s0 = ss[0]
            if s0.get('n'):
                cand = True; read = s0['n']; strong = True
            elif tk and tk[0]['x0'] >= s0['x1'] - 1:
                cand = True
        if not cand and tk and l['x0'] <= L + 8 and len(tk) > 1:
            f = tk[0]['t']
            if re.fullmatch(r'\d{1,4}', f):
                cand = True; read = f
            elif len(f) <= 3 and re.search(r'[^A-Za-zĀ-ſḀ-ỿ]', f) and not re.match(r'^[(‘“\[—–]', f) and not re.fullmatch(r'[A-Za-z][.,;:]', f):
                cand = True
                m = re.search(r'\d+', f)
                if m and len(m.group(0)) >= 2: read = m.group(0)
            elif re.fullmatch(r'\d{1,4}[A-Z]\w*', f):
                cand = True; read = re.match(r'\d+', f).group(0)
        if cand and cont and not (read and len(read) >= 3):
            cand = False
        weak = False
        if not cand and prevl_prev is not None and tk and l['x0'] <= L + 8 and prevl_prev['x1'] < R - 45:
            it = sum(len(t['t']) for t in tk if t['i']); tot = sum(len(t['t']) for t in tk) or 1
            if it < 0.5 * tot and re.match(r'^[A-ZĀ-ſḀ-ỿ“‘(]', tk[0]['t']) and not l['deva'] and not prevl_prev['deva']:
                cand = True; weak = True
        if cand and not (read and len(read) >= 2) and tk and re.match(r'^[-‘\']?[a-z]', tk[0]['t']) and len(tk[0]['t']) > 1:
            cand = False
        recs.append(dict(P=P, l=l, cand=cand, read=read, strong=strong, weak=weak if cand else False))

PMR = {}
for P in pages:
    rd = sorted(int(x['n']) for l in P['lines'] if l['reg'] == 'm' and not l['deva'] for x in l['sups'] if x.get('n') and len(x['n']) >= 2)
    if rd:
        med = rd[len(rd) // 2]
        rd = [x for x in rd if abs(x - med) <= 12]
        PMR[P['n']] = (rd[0], rd[-1])

def sc_start(r, num):
    read = r['read']
    s = str(num)
    rng = PMR.get(r['P']['n'])
    return sc_read(r, num)

def sc_read(r, num):
    read = r['read']
    s = str(num)
    if read is None:
        return 0.0 if r.get('weak') else 0.2
    if read == s:
        return 4
    if len(read) >= 2 and (s.endswith(read) or s.startswith(read)):
        return 1.5
    if len(read) >= 2:
        return -4
    if num < 10:
        return 2 if read == s else -1
    return 0.3 if (s.endswith(read) or s.startswith(read)) else -0.6

states = {0: (0.0, None)}
hist = []
cidx = [i for i, r in enumerate(recs) if r['cand'] and r['P']['n'] < 499]
for i in cidx:
    r = recs[i]
    new = {}
    for num, (score, _) in states.items():
        skip = score - (2.5 if (r['strong'] and r['read'] and len(r['read']) >= 2) else (0.05 if r.get('weak') else 0.35))
        if num not in new or skip > new[num][0]:
            new[num] = (skip, (num, 'skip'))
        opts = [(1, 0), (2, -3)]
        rd = r['read']
        if rd and rd.isdigit() and len(rd) >= len(str(num + 1)) and num + 2 < int(rd) <= num + 40:
            opts.append((int(rd) - num, -2.5 - 0.3 * (int(rd) - num - 2)))
        for jump, cost in opts:
            nn = num + jump
            v = score + cost + sc_start(r, nn)
            if nn not in new or v > new[nn][0]:
                new[nn] = (v, (num, 'start'))
    best = sorted(new.items(), key=lambda kv: -kv[1][0])[:250]
    states = dict(best)
    hist.append(states)
# backtrack
num = max(states, key=lambda k: states[k][0])
assign = {}
for step in range(len(cidx) - 1, -1, -1):
    sc, (prev, act) = hist[step][num]
    if act == 'start':
        assign[cidx[step]] = num
    num = prev
an = 2000
for i, r in enumerate(recs):
    if r['P']['n'] >= 499 and r['cand'] and not r.get('weak'):
        an += 1
        assign[i] = an
open_note = None
for i, r in enumerate(recs):
    P, l = r['P'], r['l']
    if P['n'] >= 499 and open_note is not None and open_note < 2000 and i not in assign:
        continue
    if i in assign:
        tk = l['tk']
        while len(tk) > 1 and (re.fullmatch(r'\d{1,4}', tk[0]['t']) or JUNKSTART.fullmatch(tk[0]['t']) or (len(tk[0]['t']) <= 3 and re.search(r'[^A-Za-zĀ-ſḀ-ỿ]', tk[0]['t']) and not re.match(r'^[(‘“\[—–]', tk[0]['t']))):
            tk.pop(0)
        if tk and re.fullmatch(r'\d{1,4}[A-Z]\w*', tk[0]['t']):
            tk[0]['t'] = re.sub(r'^\d+', '', tk[0]['t'])
        open_note = assign[i]
        notes[open_note] = []
        note_page[open_note] = P['n']
        page_note_starts[P['n']].append(open_note)
    if open_note is None:
        continue
    l['page'] = P['n']
    notes[open_note].append(l)
cur = max(k for k in notes if k < 2000) if notes else 0
# split notes that swallowed missing successors
split_count = 0
for k in sorted(list(notes)):
    m = 0
    while (k + m + 1) not in notes and k + m + 1 < cur:
        m += 1
    if not m:
        continue
    lines = notes[k]
    if len(lines) < 2:
        continue
    Lx = min(l['x0'] for l in lines)
    Rx = sorted(l['x1'] for l in lines)[len(lines) // 2]
    sc = []
    for j in range(1, len(lines)):
        l, pl = lines[j], lines[j - 1]
        tk = l['tk']
        if not tk or l['deva']:
            continue
        v = 0.0
        if pl['x1'] < Rx - 45: v += 2
        f = tk[0]['t']
        if re.fullmatch(r'\d{1,4}', f) or (len(f) <= 3 and re.search(r'[^A-Za-zĀ-ſḀ-ỿ]', f) and not re.match(r'^[(‘“\[—–]', f)):
            v += 2
        if re.match(r'^[A-ZĀ-ſḀ-ỿ]', f): v += 0.5
        it = sum(len(t['t']) for t in tk if t['i']); tot = sum(len(t['t']) for t in tk) or 1
        if it > 0.5 * tot: v -= 2
        if l['x0'] > Lx + 25: v -= 3
        if l.get('page') != pl.get('page') and pl['x1'] >= Rx - 45: v -= 2
        if any(s.get('n') for s in l['sups'] if s['x0'] <= Lx + 14): v += 1.5
        sc.append((v, j))
    picks = sorted([j for v, j in sorted(sc, reverse=True)[:m] if v >= 2])
    if not picks:
        continue
    bounds = [0] + picks + [len(lines)]
    for q in range(len(picks) + 1):
        seg = lines[bounds[q]:bounds[q + 1]]
        num = k + q
        if q:
            tk = seg[0]['tk']
            while len(tk) > 1 and (re.fullmatch(r'\d{1,4}', tk[0]['t']) or (len(tk[0]['t']) <= 3 and re.search(r'[^A-Za-zĀ-ſḀ-ỿ]', tk[0]['t']) and not re.match(r'^[(‘“\[—–]', tk[0]['t']))):
                tk.pop(0)
            note_page[num] = seg[0]['page']
            page_note_starts[seg[0]['page']].append(num)
            page_note_starts[seg[0]['page']].sort()
            split_count += 1
        notes[num] = seg
notes = collections.OrderedDict(sorted(notes.items()))
print('split merged notes:', split_count)
print('footnotes:', len(notes), 'last', cur)
missing = [k for k in range(1, cur + 1) if k not in notes]
print('gaps in numbering:', len(missing), missing[:40])

# ------------------------------------------------------------------ main-text references
def match_score(e, read, width):
    s = str(e - 2000 if e > 2000 else e)
    if read == s:
        return 5
    if read and len(read) >= 2 and (s.endswith(read) or s.startswith(read)):
        return 3
    if read and len(read) >= 2 and fuzz.ratio(read, s) >= 66:
        return 2
    if read is None:
        return 1 if width >= 4 * len(s) else 0.3
    if len(read) == 1 and len(s) == 1:
        return 0.5
    return -3

ref_stats = collections.Counter()
for P in pages:
    exp = page_note_starts.get(P['n'], [])
    cands = []
    hs = [s['b'] - s['t'] for l in P['lines'] for s in l['sups'] if s.get('n') and len(s['n']) >= 2]
    hmed = sorted(hs)[len(hs) // 2] if hs else 10
    for li, l in enumerate(P['lines']):
        if l['reg'] != 'm' or l['deva'] or l.get('hdr'):
            continue
        merged = []
        for s in sorted(l['sups'], key=lambda s: s['x0']):
            if merged and s['x0'] - merged[-1]['x1'] <= 6 and abs(s['t'] - merged[-1]['t']) <= 3:
                m = merged[-1]
                m['x1'] = s['x1']; m['b'] = max(m['b'], s['b'])
                m['n'] = (m['n'] + s['n']) if (m.get('n') and s.get('n')) else (m.get('n') or s.get('n'))
                m['ok'] = m.get('ok') or s.get('ok')
                continue
            merged.append(dict(s))
        l['sups'] = merged
        for s in merged:
            if s['b'] - s['t'] > 1.3 * hmed + 1:
                continue
            cands.append((li, s))
    if not exp:
        continue
    # DP alignment: expected (in order) to candidates (in order)
    E, C = len(exp), len(cands)
    NEG = -1e9
    dp = [[NEG] * (C + 1) for _ in range(E + 1)]
    bt = [[None] * (C + 1) for _ in range(E + 1)]
    for j in range(C + 1):
        dp[0][j] = 0
    for i in range(1, E + 1):
        dp[i][0] = dp[i - 1][0]; bt[i][0] = ('skipE',)
        for j in range(1, C + 1):
            best = (dp[i][j - 1], ('skipC',))
            if dp[i - 1][j] > best[0]:
                best = (dp[i - 1][j], ('skipE',))
            sc = match_score(exp[i - 1], cands[j - 1][1].get('n'), cands[j - 1][1]['x1'] - cands[j - 1][1]['x0'])
            if sc >= 0.9 and dp[i - 1][j - 1] + sc > best[0]:
                best = (dp[i - 1][j - 1] + sc, ('match',))
            dp[i][j], bt[i][j] = best
    i, j = E, C
    assigned = {}
    while i > 0:
        mv = bt[i][j] if j > 0 else ('skipE',)
        if mv[0] == 'match':
            assigned[exp[i - 1]] = cands[j - 1]; i -= 1; j -= 1
        elif mv[0] == 'skipC':
            j -= 1
        else:
            i -= 1
    # pair leftovers inside the gaps between confident matches
    order = {id(c[1]): j for j, c in enumerate(cands)}
    anchors = sorted([(exp.index(e), order[id(c[1])]) for e, c in assigned.items()])
    bounds = [(-1, -1)] + anchors + [(len(exp), len(cands))]
    for (e0, c0), (e1, c1) in zip(bounds, bounds[1:]):
        le = [exp[k] for k in range(e0 + 1, e1) if exp[k] not in assigned]
        lc = [cands[k] for k in range(c0 + 1, c1)]
        lc = [c for c in lc if c[1]['x1'] - c[1]['x0'] >= 3 * len(str(le[0])) ] if le else []
        if le and len(le) == len(lc):
            for e, c in zip(le, lc):
                assigned[e] = c
    JUNKTAIL = re.compile(r'[!?"”“\'’°*^~|¹²³⁰-⁹\d»«®©™]+$')
    for e, (li, sp) in assigned.items():
        if sp.get('ok'):
            continue
        l = P['lines'][li]
        for t in l['tk']:
            if t['x0'] <= sp['x0'] + 2 and t['x1'] >= sp['x0'] - 2:
                m = JUNKTAIL.search(t['t'])
                if m and m.start() > 0:
                    core = t['t'][:m.start()]
                    tail = m.group(0)
                    keep = tail[0] if tail[0] in '?!”’' and not core.endswith(('.', ')', ',', '’', '”')) else ''
                    t['t'] = core + keep
                t['x1'] = min(t['x1'], sp['x0'])
                break
    for e in exp:
        if e in assigned:
            li, s = assigned[e]
            P['lines'][li].setdefault('refs', []).append((s['x0'], e))
            ref_stats['sup'] += 1
        else:
            # fallback: digits glued to a word in the text
            done = False
            for l in P['lines']:
                if l['reg'] != 'm' or l['deva']:
                    continue
                for t in l['tk']:
                    m = re.search(r'([^\d])' + str(e) + r'$', t['t'])
                    if m:
                        t['t'] = t['t'][:-len(str(e))]
                        l.setdefault('refs', []).append((t['x1'], e)); done = True; break
                if done:
                    break
            ref_stats['text' if done else 'unplaced'] += 1
            if not done:
                P.setdefault('unplaced', []).append(e)
print('refs:', dict(ref_stats))

json.dump({'pages': pages, 'notes': {k: v for k, v in notes.items()}, 'note_page': note_page},
          open('stage2.json', 'w'), ensure_ascii=False)
