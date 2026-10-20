"""Check a citing agent's result against its packet.
usage: python3 check_edits.py <packet.json> <result.json>
The result is {"edits":[{"unit_id","find","replace"}], "sources":[{"key",...}], ...}.
Prints every problem; exit 1 if any. Then prints each edited unit as it would read."""
import json, re, sys, difflib
MARK = re.compile(r'\[\[([^\[\]]*)\]\]')
KINDS = {'paper','preprint','book','repository','repository-file','documentation','web-page','blog-post','dataset','standard','terms','news','project-record'}
READS = {'opened','search','record'}
pk = json.load(open(sys.argv[1])); res = json.load(open(sys.argv[2]))
units = {u['id']: u for u in pk['units']}
problems = []
src = {}
for s in res.get('sources', []):
    k = s.get('key')
    if not k or not re.fullmatch(r's\d+', k): problems.append(f'source key {k!r} must be s1, s2, ...'); continue
    if k in src: problems.append(f'source key {k} defined twice')
    src[k] = s
    if s.get('kind') not in KINDS: problems.append(f'{k}: kind {s.get("kind")!r} not one of {sorted(KINDS)}')
    if s.get('read') not in READS: problems.append(f'{k}: read {s.get("read")!r} not one of {sorted(READS)}')
    if not s.get('title'): problems.append(f'{k}: no title')
    if s.get('kind') != 'project-record' and not (s.get('url') or '').startswith('http'): problems.append(f'{k}: no http url')
    if s.get('kind') == 'project-record' and not s.get('path'): problems.append(f'{k}: project-record needs path')
used = set()
spans = {}
for i, e in enumerate(res.get('edits', [])):
    uid, f, r = e.get('unit_id'), e.get('find', ''), e.get('replace', '')
    tag = f'edit {i} ({uid})'
    if uid not in units: problems.append(f'{tag}: no such unit in this packet'); continue
    u = units[uid]
    if 'never edit' in u['kind']: problems.append(f'{tag}: unit is {u["kind"]}')
    n = u['text'].count(f) if f else 0
    if n != 1: problems.append(f'{tag}: find occurs {n} times in the unit text (must be exactly once): {f!r}'); continue
    a = u['text'].index(f); b = a + len(f)
    for (a2, b2, j) in spans.get(uid, []):
        if a < b2 and a2 < b: problems.append(f'{tag}: overlaps edit {j} in the same unit')
    spans.setdefault(uid, []).append((a, b, i))
    for m in MARK.finditer(r):
        keys = [k.strip() for k in m.group(1).split(',')]
        for k in keys:
            if k not in src: problems.append(f'{tag}: marker names {k!r}, which is not in sources')
            used.add(k)
    stray = re.sub(MARK, '', r)
    if '[[' in stray or ']]' in stray: problems.append(f'{tag}: malformed marker in replace: {r!r}')
    if not MARK.search(r) and not e.get('removes_only'):
        problems.append(f'{tag}: replace has no [[s..]] marker (set "removes_only": true only if it just deletes a note mention)')
for k in src:
    if k not in used: problems.append(f'source {k} is defined but never cited')
for p in problems: print('PROBLEM:', p)
print(f'{len(problems)} problems; {len(res.get("edits", []))} edits; {len(src)} sources')
print()
for uid, lst in spans.items():
    t = units[uid]['text']
    for a, b, i in sorted(lst, reverse=True):
        t = t[:a] + res['edits'][i]['replace'] + t[b:]
    print(f'--- {uid} ({units[uid]["kind"]})')
    old = units[uid]['text'].split(); new = t.split()
    for d in difflib.ndiff(old, new):
        if d[0] in '+-': print('   ', d)
    print('   NOW:', t)
sys.exit(1 if problems else 0)
