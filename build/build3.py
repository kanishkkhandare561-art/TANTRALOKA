"""Stage 3: blocks, verse alignment with the KSTS text, HTML, search index, site data."""
import json, re, html, collections, unicodedata as ud, difflib
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
from struct1 import fold

S2 = json.load(open('stage2.json'))
DEP = json.load(open('dep.json'))
pages = S2['pages']
notes = {int(k): v for k, v in S2['notes'].items()}
note_page = {int(k): v for k, v in S2['note_page'].items()}
esc = lambda s: html.escape(s, quote=True)
DEVA = re.compile(r'[ऀ-ॿ]')

# ------------------------------------------------------------------ KSTS verse word stream
LEX = DEP['lex']
stream = []          # dicts: d (deva), k (lex id), post (punct), unit, vn
for u in DEP['units']:
    for s in u['segs']:
        if s['t'] != 's':
            continue
        for x in s['w']:
            if isinstance(x, list):
                stream.append(dict(d=x[0], k=x[1], post='', unit=u['id'], vn=s['n']))
            elif x == '\n':
                if stream: stream[-1]['br'] = True
            elif stream:
                stream[-1]['post'] += (' ' if stream[-1]['post'] else '') + x
SD = ''
spans = []
CLEAN = lambda s: re.sub(r'[^ऀ-ॣ॰-ॿ]', '', s.replace('‌', '').replace('‍', ''))
for i, w in enumerate(stream):
    c = CLEAN(w['d'])
    spans.append((len(SD), len(SD) + len(c)))
    SD += c
# IAST stream for the book's transliterated verse lines
for w in stream:
    e = LEX[w['k']]
    w['iast'] = e['w'].replace('ṃ', 'ṁ')
SI = ''
ispans = []
for w in stream:
    c = re.sub(r'[^a-z]', '', fold(w['iast']))
    ispans.append((len(SI), len(SI) + len(c)))
    SI += c

def deva_clean(s):
    s = re.sub(r'[०-९0-9।॥|]', '', s)
    return CLEAN(s)

# ------------------------------------------------------------------ helpers: runs -> html
def runs_html(tk, refs=()):
    """tokens with b/i flags -> html; refs: list of (x, n) inserted after nearest token left of x"""
    ins = collections.defaultdict(list)
    for x, n in sorted(refs):
        idx = -1
        for k, t in enumerate(tk):
            if (t['x0'] + t['x1']) / 2 < x:
                idx = k
        ins[idx].append(n)
    out = []
    for n in ins.get(-1, []):
        out.append(('ref', n))
    for k, t in enumerate(tk):
        out.append(('tok', t))
        for n in ins.get(k, []):
            out.append(('ref', n))
    h = ''
    cur = (False, False)
    open_tags = ''
    def close():
        return ('</i>' if cur[1] else '') + ('</b>' if cur[0] else '')
    first = True
    for kind, v in out:
        if kind == 'ref':
            h += close(); cur = (False, False)
            h += f'<sup class="fn" data-n="{v}">{v}</sup>'
            continue
        st = (v['b'], v['i'])
        txt = v['t']
        if DEVA.search(txt):
            txt_html = deva_words(txt)
        else:
            txt_html = esc(txt)
        if st != cur:
            h += close()
            h += (' ' if not first else '')
            h += ('<b>' if st[0] else '') + ('<i>' if st[1] else '')
            cur = st
        else:
            h += (' ' if not first else '')
        h += txt_html
        first = False
    h += close()
    return h

# lookup for loose Devanagari words (outside aligned verses)
SURF = {}
for i, e in enumerate(LEX):
    SURF.setdefault(e.get('d') or '', i)
DEVSURF = {}
def deva_words(txt):
    parts = re.split(r'(\s+)', txt)
    o = ''
    for p in parts:
        if not p.strip():
            o += p; continue
        core = re.sub(r'[।॥|०-९\d.,;:()\[\]‘’“”\'"!?-]+$', '', p)
        rest = p[len(core):]
        if DEVA.search(core):
            o += f'<span class="w loose" lang="sa">{esc(core)}</span>{esc(rest)}'
        else:
            o += esc(p)
    return o

def plain(h):
    h = re.sub(r'<sup class="fn"[^>]*>\d+</sup>', '', h)
    return html.unescape(re.sub(r'<[^>]+>', '', h))

# ------------------------------------------------------------------ deva line alignment
pos = 0
ipos = 0
def align_deva(text):
    """returns list of stream indices for the book line, or None"""
    global pos
    b = deva_clean(text)
    if len(b) < 4:
        return None
    lo = pos
    hi = min(len(SD), pos + len(b) * 3 + 600)
    al = fuzz.partial_ratio_alignment(b, SD[lo:hi])
    if al is None or al.score < 72:
        # wider search (pages out of order / skipped verses)
        lo2 = max(0, pos - 300); hi2 = min(len(SD), pos + 6000)
        al2 = fuzz.partial_ratio_alignment(b, SD[lo2:hi2])
        if al2 is None or al2.score < 80:
            return None
        al, lo = al2, lo2
    s, e = lo + al.dest_start, lo + al.dest_end
    idx = [i for i, (a, z) in enumerate(spans) if a < e and z > s and (min(z, e) - max(a, s)) >= 0.5 * (z - a)]
    if not idx:
        return None
    pos = spans[idx[-1]][1]
    return idx

def align_iast(tk):
    """diacritic-only correction of a transliterated verse line against the KSTS IAST stream"""
    global ipos
    words = [t['t'] for t in tk]
    b = re.sub(r'[^a-z]', '', fold(' '.join(words)))
    if len(b) < 6:
        return
    lo = max(0, ipos - 200); hi = min(len(SI), ipos + len(b) * 3 + 1500)
    al = fuzz.partial_ratio_alignment(b, SI[lo:hi])
    if al is None or al.score < 75:
        return
    s, e = lo + al.dest_start, lo + al.dest_end
    ipos = e
    idx = [i for i, (a, z) in enumerate(ispans) if a < e and z > s]
    ref = ''.join(stream[i]['iast'] for i in idx)
    reff = fold(ref)
    # map folded letters of ref -> original chars
    refchars = [c for c in ud.normalize('NFC', ref) if re.match(r'[a-z]', fold(c))]
    refletters = ''.join(fold(c) for c in refchars)
    for t in tk:
        m = re.match(r'^([^\w]*)(.*?)([^\w]*)$', t['t'])
        pre, core, post = m.groups()
        cf = re.sub(r'[^a-z]', '', fold(core))
        if len(cf) < 2 or len(cf) != len([c for c in core if c.isalpha()]):
            continue
        k = refletters.find(cf)
        if k < 0:
            continue
        fixed = ''.join(refchars[k:k + len(cf)])
        if fold(fixed) == fold(core).lower():
            t['t'] = pre + fixed + post

# ------------------------------------------------------------------ TOC from the epub
navx = open('/tmp/ep/x/OEBPS/nav.xhtml', encoding='utf-8').read()
toc_src = navx.split('<nav epub:type="page-list"')[0]
TOC = []
depth = 0
for m in re.finditer(r'(<ol>|</ol>|<a href="p(\d+)\.xhtml">(.*?)</a>)', toc_src):
    if m.group(1) == '<ol>':
        depth += 1
    elif m.group(1) == '</ol>':
        depth -= 1
    else:
        TOC.append(dict(img=int(m.group(2)), title=html.unescape(m.group(3)), level=depth))

# ------------------------------------------------------------------ blocks
blocks = []
def new_block(kind, page, **kw):
    b = dict(kind=kind, page=page, lines=[], **kw)
    blocks.append(b)
    return b

def is_iast_verse(l, prevcat):
    tk = l['tk']
    if not tk or len(tk) > 12:
        return False
    letters = sum(len(t['t']) for t in tk)
    it = sum(len(t['t']) for t in tk if t['i'])
    bar = any(re.fullmatch(r'[|l1I\\]{1,2}|\|\|', t['t']) or t['t'].endswith('|') for t in tk)
    return it >= 0.6 * letters and (bar or prevcat in ('deva', 'iast'))

pitch = 25
prev = None
FIGS = {1: dict(src='scans/p001.jpg', cap='Cover'),
        4: dict(src='scans/fig-p004.png', cap='Swami Lakshmanjoo'),
        514: dict(table=open('extra/p514.html', encoding='utf-8').read(), cap='The End of the Twelve: a comparative table (transcribed from page 500)')}
for P in pages:
    n = P['n']
    main = [l for l in P['lines'] if l['reg'] == 'm' and not l.get('hdr')]
    # drop garbage read from pictures (low confidence, few letters)
    def junkline(l):
        if l['deva'] or not l['tk']:
            return False
        cs = [t['c'] for t in l['tk']]
        alnum = sum(c.isalnum() for t in l['tk'] for c in t['t'])
        return (sum(cs) / len(cs) < 45 and P['n'] < 15) or alnum < 0.4 * sum(len(t['t']) for t in l['tk'])
    if n == 4:
        main = [l for l in main if l['t'] < 320 or l['t'] > 1260]
    if n == 514:
        main = []
    main = [l for l in main if not junkline(l)]
    full = [l for l in main if not l['deva'] and l['x1'] - l['x0'] > 420]
    L = sorted(l['x0'] for l in full)[len(full) // 5] if full else 80
    R = sorted(l['x1'] for l in full)[len(full) // 2] if full else 820
    mid = (L + R) / 2
    blocks.append(dict(kind='page', page=n, label=P['label']))
    if n in FIGS:
        blocks.append(dict(kind='fig', page=n, lines=[None], **FIGS[n]))
    prevline = None
    for l in main:
        tk = l['tk']
        if l['deva']:
            cat = 'deva'
        elif is_iast_verse(l, prev['cat'] if prev else None):
            cat = 'iast'
        else:
            letters = sum(len(t['t']) for t in tk) or 1
            bold = sum(len(t['t']) for t in tk if t['b'])
            centered = l['x0'] > L + 30 and l['x1'] < R - 30 and abs((l['x0'] + l['x1']) / 2 - mid) < 22
            cat = 'center' if centered else 'text'
            l['bold'] = bold >= 0.6 * letters
        l['cat'] = cat
        gap = (l['t'] - prevline['b']) if prevline else 0
        newpar = True
        if prev and cat == prev['cat'] and cat in ('text',):
            indent = l['x0'] > L + 25
            prevshort = prev['line']['x1'] < R - 70
            if prevline is None:
                # first line on a new page: continuation if not indented and previous block ran to the margin
                newpar = indent or prevshort
            else:
                newpar = indent or prevshort or gap > 22
            if not newpar and prev['line'].get('bold') != l.get('bold') and abs(len(l['tk'])) > 3:
                newpar = False
        elif prev and cat == prev['cat'] and cat in ('deva', 'iast'):
            newpar = (gap > 22) if prevline else False
        elif prev and cat == 'center' and prev['cat'] == 'center' and prevline and gap < 14:
            newpar = False
        if newpar:
            kind = {'deva': 'deva', 'iast': 'iast', 'center': 'center', 'text': 'p'}[cat]
            b = new_block(kind, n)
        else:
            b = prev['block']
            if prevline is None:
                b['lines'].append(dict(pagebreak=n, label=P['label']))
        l['page'] = n
        b['lines'].append(l)
        prev = dict(cat=cat, block=b, line=l)
        prevline = l

# ------------------------------------------------------------------ text joining with hyphenation
WORDS = collections.Counter()
for P in pages:
    for l in P['lines']:
        for t in l['tk']:
            WORDS[fold(re.sub(r'[^\w-]', '', t['t']))] += 1

def join_lines(lines):
    """flatten lines into a single token list, with page-break markers and hyphen joins"""
    out = []
    refs = []
    for l in lines:
        if 'pagebreak' in l:
            out.append(dict(t='', pb=l['pagebreak'], label=l['label'], x0=0, x1=0, b=False, i=False))
            continue
        tk = [dict(t) for t in l['tk']]
        base = len(out)
        for x, nref in l.get('refs', []):
            # translate ref x position to global token index
            idx = -1
            for k, t in enumerate(tk):
                if (t['x0'] + t['x1']) / 2 < x:
                    idx = k
            refs.append((base + idx, nref))
        if out and tk:
            last = None
            for t in reversed(out):
                if 'pb' not in t:
                    last = t; break
            if last and last['t'].endswith('-') and len(last['t']) > 2 and tk[0]['t'][:1].islower():
                joined = last['t'][:-1] + tk[0]['t']
                core = fold(re.sub(r'[^\w-]', '', joined))
                hy = fold(re.sub(r'[^\w-]', '', last['t'] + tk[0]['t']))
                if WORDS[core] >= WORDS[hy] and not re.search(r'[A-Z]', tk[0]['t']):
                    last['t'] = joined
                else:
                    last['t'] = last['t'] + tk[0]['t']
                # refs on the merged token
                refs = [((r if r != base else base - 1), nn) if r == base else (r, nn) for r, nn in refs]
                tk = tk[1:]
                refs = [(r - 1 if r > base else r, nn) for r, nn in refs]
                base -= 0
                out.extend(tk)
                continue
        out.extend(tk)
    return out, refs

def tokens_html(tk, refs):
    ins = collections.defaultdict(list)
    for r, nref in refs:
        ins[r].append(nref)
    h = ''
    cur = (False, False)
    first = True
    def close():
        return ('</i>' if cur[1] else '') + ('</b>' if cur[0] else '')
    for nref in ins.get(-1, []):
        h += f'<sup class="fn" data-n="{nref}">{nref - 2000 if nref > 2000 else nref}</sup>'
    for k, t in enumerate(tk):
        if 'pb' in t:
            h += close(); cur = (False, False)
            h += f'<span class="pb" data-p="{t["pb"]}" data-l="{t["label"] or ""}"></span>'
            continue
        st = (t['b'], t['i'])
        txt = deva_words(t['t']) if DEVA.search(t['t']) else esc(t['t'])
        if st != cur:
            h += close() + ('' if first else ' ') + ('<b>' if st[0] else '') + ('<i>' if st[1] else '')
            cur = st
        else:
            h += '' if first else ' '
        h += txt
        first = False
        for nref in ins.get(k, []):
            h += f'<sup class="fn" data-n="{nref}">{nref - 2000 if nref > 2000 else nref}</sup>'
    h += close()
    h = h.replace('</b> <b>', ' ').replace('</i> <i>', ' ')
    return h

# ------------------------------------------------------------------ verse blocks
def word_span(i):
    w = stream[i]
    p = f' {esc(w["post"])}' if w['post'] else ''
    return f'<span class="w" data-k="{w["k"]}" lang="sa">{esc(w["d"])}</span>{p}'

def deva_block_html(b):
    rows = []
    units = []
    for l in b['lines']:
        if 'pagebreak' in l:
            rows.append(f'<span class="pb" data-p="{l["pagebreak"]}" data-l="{l["label"] or ""}"></span>')
            continue
        txt = ' '.join(t['t'] for t in l['tk'])
        idx = align_deva(txt)
        indent = ' class="ind"' if l['x0'] > 130 else ''
        if idx:
            for i in idx:
                if stream[i]['unit'] not in units:
                    units.append(stream[i]['unit'])
            rows.append(f'<span class="vl"{indent} data-src="ksts">' + ' '.join(word_span(i) for i in idx) + '</span>')
            l['aligned'] = True
        else:
            rows.append(f'<span class="vl"{indent} data-src="ocr">{deva_words(txt)}</span>')
    vns = []
    for u in units:
        vns.append(u)
    return ''.join(rows), units

def iast_block_html(b):
    rows = []
    for l in b['lines']:
        if 'pagebreak' in l:
            rows.append(f'<span class="pb" data-p="{l["pagebreak"]}" data-l="{l["label"] or ""}"></span>')
            continue
        tk = [dict(t) for t in l['tk']]
        align_iast(tk)
        for t in tk:
            t['i'] = False; t['b'] = False
        # tidy verse bars
        for t in tk:
            if re.fullmatch(r'[|lI1\\]{2}|\|l|l\||\\\\', t['t']):
                t['t'] = '||'
            elif re.fullmatch(r'[|lI\\]', t['t']):
                t['t'] = '|'
        indent = ' class="ind"' if l['x0'] > 130 else ''
        rows.append(f'<span class="vl"{indent}>' + tokens_html(tk, [(k, n) for x, n in l.get('refs', []) for k in [max([j for j, t in enumerate(tk) if (t['x0'] + t['x1']) / 2 < x] or [-1])]]) + '</span>')
    return ''.join(rows)

# ------------------------------------------------------------------ headings from TOC
def find_heading(entry):
    img = entry['img']
    t = fold(entry['title'])
    best = None
    for bi, b in enumerate(blocks):
        if b.get('page') != img or b['kind'] not in ('center', 'p'):
            continue
        txt = fold(' '.join(tt['t'] for l in b['lines'] if 'tk' in l for tt in l['tk']))
        if len(txt) > len(t) * 2.2 + 20:
            continue
        sc = fuzz.ratio(t, txt)
        sc2 = fuzz.partial_ratio(t, txt) if len(txt) > 8 else 0
        s = max(sc, sc2 - 8)
        if best is None or s > best[0]:
            best = (s, bi)
    return best

heading_at = {}
for e in TOC:
    if e['img'] < 15 and e['title'] not in ('Contents', 'Abbreviations', 'Acknowledgements'):
        continue
    f = find_heading(e)
    if f and f[0] >= 62:
        heading_at[f[1]] = e
        e['found'] = True
    else:
        e['found'] = False
print('headings found:', sum(bool(e.get('found')) for e in TOC), 'of', len(TOC))

# ------------------------------------------------------------------ render all blocks
out_blocks = []
bid = 0
for bi, b in enumerate(blocks):
    if b['kind'] == 'page':
        out_blocks.append(dict(t='pg', p=b['page'], l=b['label']))
        continue
    if not b['lines']:
        continue
    bid += 1
    if bi in heading_at:
        e = heading_at[bi]
        out_blocks.append(dict(t='h', lv=e['level'], id=f'b{bid}', p=b['page'], html=esc(e['title']), toc=TOC.index(e)))
        continue
    if b['kind'] == 'fig':
        out_blocks.append(dict(t='fig', id=f'b{bid}', p=b['page'], src=b.get('src'), table=b.get('table'), cap=b['cap']))
        continue
    if b['kind'] == 'deva':
        h, units = deva_block_html(b)
        out_blocks.append(dict(t='dv', id=f'b{bid}', p=b['page'], html=h, u=units))
    elif b['kind'] == 'iast':
        out_blocks.append(dict(t='ia', id=f'b{bid}', p=b['page'], html=iast_block_html(b)))
    else:
        tk, refs = join_lines(b['lines'])
        h = tokens_html(tk, refs)
        textlines = [l for l in b['lines'] if 'tk' in l]
        bold = sum(1 for l in textlines if l.get('bold')) >= max(1, 0.6 * len(textlines))
        kind = 'c' if b['kind'] == 'center' else ('vt' if bold else 'p')
        if kind == 'vt':
            h = h.replace('<b>', '').replace('</b>', '')
        indent = textlines[0]['x0'] > 130 if textlines else False
        out_blocks.append(dict(t=kind, id=f'b{bid}', p=b['page'], html=h, ni=(not indent)))

# headings not found: insert before first block of their page
for e in TOC:
    if e.get('found') or (e['img'] < 15 and e['title'] not in ('Chapter One: The Types of Liberating Knowledge (vijñānabhid)',)):
        continue
    for k, ob in enumerate(out_blocks):
        if ob['t'] == 'pg' and ob['p'] == e['img']:
            out_blocks.insert(k + 1, dict(t='h', lv=e['level'], id=f'h{TOC.index(e)}', p=e['img'], html=esc(e['title']), toc=TOC.index(e), ins=True))
            break

# ------------------------------------------------------------------ footnotes html
notes_html = {}
for n, lines in notes.items():
    if not lines:
        notes_html[n] = ''
        continue
    xs = sorted(l['x0'] for l in lines)
    L = xs[0]
    R = max(l['x1'] for l in lines)
    paras = [[]]
    for k, l in enumerate(lines):
        if k and (l['x0'] > L + 30):
            paras.append([])
        elif k and lines[k - 1]['x1'] < R - 90 and (sum(1 for t in l['tk'] if t['i']) >= 0.6 * max(1, len(l['tk'])) or l['deva'] or lines[k - 1]['deva']):
            paras[-1].append(dict(br=True))
        if k and l['page'] != lines[k - 1]['page']:
            paras[-1].append(dict(pagebreak=l['page'], label=pages[l['page'] - 1]['label']))
        paras[-1].append(l)
    hs = []
    for para in paras:
        segs = []
        cur = []
        for l in para:
            if l.get('br'):
                segs.append(cur); cur = []
            else:
                cur.append(l)
        segs.append(cur)
        ph = '<br>'.join(tokens_html(*join_lines(s)) for s in segs if s)
        hs.append(f'<p>{ph}</p>')
    notes_html[n] = ''.join(hs)

# ------------------------------------------------------------------ sections (for navigation)
sections = []
cur = dict(title='Front matter', toc=None, start=0)
sections.append(cur)
for k, ob in enumerate(out_blocks):
    if ob['t'] == 'h' and TOC[ob['toc']]['level'] >= 1 and ob['p'] >= 15:
        e = TOC[ob['toc']]
        cur = dict(title=e['title'], toc=ob['toc'], start=k, level=e['level'], img=e['img'])
        sections.append(cur)
for i, s in enumerate(sections):
    s['end'] = sections[i + 1]['start'] if i + 1 < len(sections) else len(out_blocks)
# chapter title / section with only a heading: merge forward
merged = []
for s in sections:
    if merged and merged[-1]['end'] - merged[-1]['start'] <= 3 and merged[-1]['toc'] is not None:
        merged[-1]['end'] = s['end']
        merged[-1].setdefault('sub', []).append(s['title'])
        continue
    merged.append(s)
sections = merged

json.dump(dict(blocks=out_blocks, notes=notes_html, note_page=note_page, sections=sections, toc=TOC,
               labels={P['n']: P['label'] for P in pages}), open('book.json', 'w'), ensure_ascii=False)
print('blocks', len(out_blocks), 'sections', len(sections), 'notes', len(notes_html))
c = collections.Counter(ob['t'] for ob in out_blocks)
print(c)
al = sum(1 for b in out_blocks if b['t'] == 'dv' and 'data-src="ksts"' in b['html'])
print('deva blocks aligned', al, 'of', c['dv'])
