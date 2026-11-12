"""Write the site's data files (plain JS so the site also opens from disk)."""
import json, html, os, re, sys
OUT = sys.argv[1]
os.makedirs(OUT + '/data', exist_ok=True)
esc = lambda s: html.escape(s, quote=True)
book = json.load(open('book.json'))
dep = json.load(open('dep.json'))

def js(name, var, obj):
    with open(f'{OUT}/data/{name}', 'w', encoding='utf-8') as f:
        f.write(f'window.{var}=')
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')
    print(name, os.path.getsize(f'{OUT}/data/{name}') // 1024, 'KB')

# ---- Viveka (Sanskrit commentary, KSTS) per unit
def words(ws):
    o = []
    for x in ws:
        if isinstance(x, list):
            o.append(f'<span class="w" data-k="{x[1]}" lang="sa">{esc(x[0])}</span>')
        elif x == '\n':
            o.append('<br>')
        else:
            o.append(esc(x))
    s = ' '.join(o)
    s = s.replace(' <br> ', '<br>')
    s = re.sub(r'“ ', '“', s); s = re.sub(r' ”', '”', s)
    s = re.sub(r' ([,;:.?!)])', r'\1', s); s = re.sub(r'\( ', '(', s)
    return s

viv = {}
unit_verses = {}
for u in dep['units']:
    h = []
    fn = []
    vs = []
    for s in u['segs']:
        t = s['t']
        if t == 'g':
            h.append(f'<span class="kp">KSTS {esc(s["x"])}</span>')
        elif t == 's':
            vs.append(s['n'])
            h.append(f'<div class="kv root"><span class="vn">{esc(s["n"])}</span>{words(s["w"])}</div>')
        elif t == 'v':
            h.append(f'<div class="kv">{words(s["w"])}</div>')
        elif t in ('h', 'c'):
            h.append(f'<p class="kh">{words(s["w"])}</p>')
        elif t == 'b' and s.get('l') == 'notes':
            fn.append(f'<li>{words(s["w"])}</li>')
        else:
            h.append(f'<p>{words(s["w"])}</p>')
    if fn:
        h.append(f'<details class="kn"><summary>Editor’s notes in the KSTS print ({len(fn)})</summary><ol>{"".join(fn)}</ol></details>')
    viv[u['id']] = ''.join(h)
    unit_verses[u['id']] = vs

js('viveka.js', 'TL_VIVEKA', viv)
# ---- lexicon + glossary (word popups)
js('lex.js', 'TL_LEX', {'lex': dep['lex'], 'glossary': dep['glossary']})
# ---- book text + notes
blocks = book['blocks']
for b in blocks:
    if b.get('t') == 'dv':
        b['v'] = [v for u in b.get('u', []) for v in unit_verses.get(u, [])]
js('book.js', 'TL_BOOK', {'blocks': blocks, 'sections': book['sections'], 'toc': book['toc'],
                          'labels': book['labels'], 'unitVerses': unit_verses})
js('notes.js', 'TL_NOTES', {'html': book['notes'], 'page': book['note_page']})

# ---- plain text edition (text/...txt)
import html as H
def plain(h):
    h = re.sub(r'<sup class="fn" data-n="(\d+)">\d+</sup>', r'[\1]', h)
    h = re.sub(r'<span class="pb" data-p="(\d+)" data-l="([^"]*)"></span>', lambda m: f' [p. {m.group(2) or "image " + m.group(1)}] ', h)
    h = re.sub(r'<br>|</span><span class="vl', '\n<span class="vl', h)
    h = re.sub(r'</p>', '\n', h)
    return H.unescape(re.sub(r'<[^>]+>', '', h)).strip()
out = ['Tantrāloka: The Light On and Of the Tantras — Volume One, Chapter One',
       'Abhinavagupta, with Jayaratha’s Viveka, translated by Mark S. G. Dyczkowski (2023)',
       'PRIVATE STUDY COPY — © the translator / publisher. Not for redistribution.',
       'Read by OCR from the page images of the e-book; not proofread. Footnote numbers appear as [n].', '']
noteset = book['notes']
allref = set(int(r) for b in blocks for r in re.findall(r'data-n="(\d+)"', b.get('html', '') or ''))
for si, s in enumerate(book['sections']):
    secpages = set(b['p'] for b in blocks[s['start']:s['end']] if b.get('t') == 'pg')
    out.append('\n' + '=' * 70 + '\n' + s['title'] + '\n' + '=' * 70 + '\n')
    refs = []
    for b in blocks[s['start']:s['end']]:
        t = b.get('t')
        if t == 'pg':
            out.append(f"\n[p. {b['l'] or 'image ' + str(b['p'])}]\n"); continue
        if t == 'fig':
            out.append(f"[Figure: {b['cap']}]\n"); continue
        txt = plain(b.get('html', ''))
        refs += re.findall(r'data-n="(\d+)"', b.get('html', ''))
        if t == 'h':
            out.append('\n## ' + txt + '\n')
        else:
            out.append(txt + '\n')
    extra = [int(n) for n, pg in book['note_page'].items() if int(n) not in allref and pg in secpages]
    if refs or extra:
        out.append('\n--- Footnotes ---\n')
        for n in sorted(set(int(r) for r in refs) | set(extra)):
            out.append(f'{n}. ' + plain(noteset.get(str(n), noteset.get(n, ''))).replace('\n', '\n    ') + '\n')
os.makedirs(OUT + '/text', exist_ok=True)
open(OUT + '/text/Tantraloka-Vol1-Ch1-Dyczkowski.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('text', os.path.getsize(OUT + '/text/Tantraloka-Vol1-Ch1-Dyczkowski.txt') // 1024, 'KB')
