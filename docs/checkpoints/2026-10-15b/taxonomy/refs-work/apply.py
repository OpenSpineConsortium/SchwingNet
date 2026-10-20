"""Merge the checked citation results of one document's groups, number the
sources by first citation, and write the update ops and the reference list.
usage: python3 apply.py spec|manual"""
import json, re, sys, os, collections
R = os.path.dirname(os.path.abspath(__file__))
DOC = sys.argv[1]
GROUPS = [g for g in ['spec-A','spec-B','spec-C','spec-D','spec-E','spec-F','spec-G','spec-H','spec-I','spec-J'] if DOC == 'spec'] or \
         ['man-A','man-B','man-C','man-D','man-E']
MARK = re.compile(r'\[\[([^\[\]]*)\]\]')
units = json.load(open(f'{R}/{DOC}_units.json'))['units']
order = {u['id']: i for i, u in enumerate(units)}
text_of = {u['id']: u['text'] for u in units}

def norm(url):
    u = url.strip()
    u = re.sub(r'#.*$', '', u)
    u = re.sub(r'^http://', 'https://', u)
    u = re.sub(r'^https://www\.', 'https://', u)
    m = re.match(r'https://arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})(v\d+)?(\.pdf)?$', u)
    if m: return 'arxiv:' + m.group(1)
    u = re.sub(r'\.git$', '', u).rstrip('/')
    return u.lower() if 'github.com' in u and '/blob/' not in u and '/tree/' not in u else u

def gkey(s):
    if s.get('kind') == 'project-record' or not s.get('url'):
        return 'path:' + (s.get('path') or s.get('title'))
    return norm(s['url'])

def score(s):
    return sum(bool(s.get(f)) for f in ['authors','title','container','date','version','public_url']) + (2 if s.get('read') == 'opened' else 0)

records = {}          # gkey -> record
conflicts = []
edits_by_unit = collections.defaultdict(list)
uncited = []
for g in GROUPS:
    p = f'{R}/out/{g}-check.json'
    if not os.path.exists(p): p = f'{R}/out/{g}-cite.json'
    res = json.load(open(p))
    local = {}
    for s in res['sources']:
        k = gkey(s)
        local[s['key']] = k
        if k in records:
            old = records[k]
            if old.get('read') != s.get('read'): conflicts.append((k, g, old.get('read'), s.get('read')))
            if score(s) > score(old): records[k] = s
        else:
            records[k] = s
    for e in res['edits']:
        rep = MARK.sub(lambda m: '[[' + ','.join(local[x.strip()] for x in m.group(1).split(',')) + ']]', e['replace'])
        edits_by_unit[e['unit_id']].append({'find': e['find'], 'replace': rep, 'group': g})
    for u in res.get('uncited', []): uncited.append((g, u))

# apply edits per unit, in doc order; number on first appearance
numbers = {}
new_text = {}
spans = {}
for uid in sorted(edits_by_unit, key=lambda x: order[x]):
    t = text_of[uid]
    placed = []
    for e in edits_by_unit[uid]:
        a = t.find(e['find'])
        assert a >= 0 and t.count(e['find']) == 1, (uid, e['find'])
        placed.append((a, a + len(e['find']), e['replace']))
    placed.sort()
    for (a1, b1, _), (a2, b2, _) in zip(placed, placed[1:]):
        assert b1 <= a2, ('overlap', uid)
    out, pos = [], 0
    for a, b, r in placed:
        out.append(t[pos:a]); out.append(r); pos = b
    out.append(t[pos:])
    nt = ''.join(out)
    for m in MARK.finditer(nt):
        for k in m.group(1).split(','):
            if k not in numbers: numbers[k] = len(numbers) + 1
    new_text[uid] = nt
    spans[uid] = (placed[0][0], placed[-1][1])

def render_marker(m):
    ns = sorted(set(numbers[k] for k in m.group(1).split(',')))
    parts, i = [], 0
    while i < len(ns):
        j = i
        while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1: j += 1
        parts.append(f'{ns[i]}-{ns[j]}' if j - i >= 2 else ', '.join(str(n) for n in ns[i:j + 1]))
        i = j + 1
    return '[' + ', '.join(parts) + ']'

def finalize(s):
    s = MARK.sub(render_marker, s)
    return s

# ops: one per unit, the span covering its edits, made unique in the doc
alltexts = [u['text'] for u in units]
def count_in_doc(f):
    return sum(t.count(f) for t in alltexts)
ops, preview = [], []
for uid in sorted(new_text, key=lambda x: order[x]):
    t = text_of[uid]; a, b = spans[uid]
    nt = finalize(new_text[uid])
    # map the covering span in the new text: prefix t[:a] and suffix t[b:] are unchanged
    rep = nt[a:len(nt) - (len(t) - b)]
    while count_in_doc(t[a:b]) > 1 and (a > 0 or b < len(t)):
        a2 = t.rfind(' ', 0, a - 1) + 1 if a > 0 else 0
        b2 = t.find(' ', b + 1) if b < len(t) else len(t)
        b2 = len(t) if b2 < 0 else b2
        a, b = a2, b2
        rep = nt[a:len(nt) - (len(t) - b)]
    op = {'op': 'replace', 'target': {'kind': 'find', 'text': t[a:b]}, 'with': {'from': {'kind': 'inline', 'content': rep}, 'as': 'text'}}
    n = count_in_doc(t[a:b])
    if n > 1:
        before = sum(x.count(t[a:b]) for x in alltexts[:order[uid]]) + t[:a].count(t[a:b])
        op['target']['nth'] = before + 1  # ops are sent in reverse doc order, so earlier occurrences are untouched
    ops.append(op)
    preview.append({'unit': uid, 'old': t, 'new': nt})

# reference list
def esc(s):
    return re.sub(r'([\\`*_\[\]<>])', r'\\\1', s)
def fmt_authors(a):
    if not a: return ''
    if len(a) > 6: a = a[:3] + ['et al']
    return ', '.join(a)
def entry(s):
    parts = []
    au = fmt_authors(s.get('authors') or [])
    if au: parts.append(esc(au.rstrip('.')) + '.')
    title = (s.get('title') or '').strip()
    parts.append(esc(title) + ('' if title[-1:] in '.?!' else '.'))
    cont, date = (s.get('container') or '').strip(), (s.get('date') or '').strip()
    if cont or date:
        parts.append(esc('; '.join(x for x in [cont, date] if x)) + '.')
    v = (s.get('version') or '').strip()
    if v:
        if re.fullmatch(r'[0-9a-f]{7,40}', v): parts.append(f'Commit {v}.')
        elif re.fullmatch(r'\d{4}\.\d{4,5}(v\d+)?', v): parts.append(f'arXiv:{v}.')
        else: parts.append(esc(v if v[:1].isupper() or v.startswith('v') or v.startswith('arXiv') else 'Version ' + v) + '.')
    if s.get('url'):
        parts.append(f'[{esc(s["url"])}]({s["url"]})')
    if s.get('public_url') and norm(s['public_url']) != norm(s.get('url', '')):
        parts.append(f'Public page: [{esc(s["public_url"])}]({s["public_url"]})')
    if s.get('read') == 'search':
        parts.append('Not opened by the research session; reported from a search summary or secondary source.')
    if s.get('kind') == 'project-record':
        parts.append('Unpublished project record, ' + esc(s.get('path', '').replace('/mnt/project-files/', '')) + '.')
    return ' '.join(parts)
refs = sorted(numbers, key=numbers.get)
md = '\n'.join(f'{numbers[k]}. {entry(records[k])}' for k in refs)
json.dump({'ops': ops, 'preview': preview, 'refs': [{'n': numbers[k], 'key': k, 'rec': records[k], 'entry': entry(records[k])} for k in refs],
           'uncited': uncited, 'conflicts': conflicts}, open(f'{R}/{DOC}_apply.json', 'w'), indent=1)
open(f'{R}/{DOC}_refs.md', 'w').write(md)
print(f'{DOC}: {len(ops)} ops, {len(refs)} references, {len(uncited)} uncited, {len(conflicts)} read conflicts, unused records {len(records) - len(refs)}')
