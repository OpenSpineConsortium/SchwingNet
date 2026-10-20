import json, re
GROUPS = {
 'spec-A': ('spec', ['1. Purpose and scope', '2. The systems']),
 'spec-B': ('spec', ['3. The taxonomy']),
 'spec-C': ('spec', ['4. Placement']),
 'spec-D': ('spec', ['5. Neighbors compared|', '5. Neighbors compared|5.1 Coordinators of coding agents']),
 'spec-E': ('spec', ['5. Neighbors compared|5.2 Research automation', '5. Neighbors compared|5.3 Verification of agent code and of protocols']),
 'spec-F': ('spec', ['6. Integration']),
 'spec-G': ('spec', ['7. The need']),
 'spec-H': ('spec', ['8. What is unique']),
 'spec-I': ('spec', ['9. GitHub Actions nativeness and free public minutes']),
 'spec-J': ('spec', ['10. Gaps, risks and open questions', '11. Research questions']),
 'man-A': ('manual', ['1. What this manual is for', '2. Before you start', '3. Running the deep research']),
 'man-B': ('manual', ['4. Checking a claim', '5. Placing any tool in the taxonomy']),
 'man-C': ('manual', ['6. Explaining the approach']),
 'man-D': ('manual', ['7. Combining Symphony and Beethoven with other software']),
 'man-E': ('manual', ['8. Keeping the spec current', '9. Glossary']),
}
def match(u, sel):
    if '|' in sel:
        s, sub = sel.split('|')
        return u['section'] == s and u['subsection'] == sub
    return u['section'] == sel
def describe(units):
    tables, rows, cells = {}, {}, {}
    out = []
    for u in units:
        ctx = u['ctx']
        t = [c for c in ctx if c.startswith('table:')]
        kind = 'paragraph'
        if u.get('heading'): kind = 'heading level %s' % u['heading']
        if 'code' in ctx: kind = 'code block (never edit)'
        if 'embed' in ctx: kind = 'embedded drawing (never edit)'
        if any(c.startswith('listItem:') for c in ctx): kind = 'list item'
        if any(c.startswith('blockquote') for c in ctx): kind = 'quote'
        if t:
            tid = t[-1].split(':')[1]
            r = [c for c in ctx if c.startswith('row:')][-1].split(':')[1]
            c = [c for c in ctx if c.startswith('cell:')][-1].split(':')[1]
            tables.setdefault(tid, len(tables) + 1)
            rows.setdefault(tid, [])
            if r not in rows[tid]: rows[tid].append(r)
            cells.setdefault(r, [])
            if c not in cells[r]: cells[r].append(c)
            kind = 'table %d, row %d, column %d%s' % (tables[tid], rows[tid].index(r), cells[r].index(c), ' (header row)' if rows[tid].index(r) == 0 else '')
        out.append((u, kind))
    return out
for g, (doc, sels) in GROUPS.items():
    units = json.load(open(f'refs/{doc}_units.json'))['units']
    mine = [u for u in units if any(match(u, s) for s in sels)]
    lines = [f'# Packet {g}: from the {"Symphony and Beethoven Taxonomy Spec" if doc=="spec" else "Symphony and Beethoven Taxonomy Manual"}, sections: ' + '; '.join(s.replace('|', ' / ') for s in sels), '']
    rec = []
    for u, kind in describe(mine):
        if not u['text'].strip(): continue
        lines.append(f'=== [unit {u["id"]}] {kind}')
        lines.append(u['text'])
        ls = [(u['text'][a:b], h) for a, b, h in u['spans'] if h != '**bold**']
        if ls:
            lines.append('    links in this unit: ' + '; '.join(f'"{t}" -> {h}' for t, h in ls))
        lines.append('')
        rec.append({'id': u['id'], 'kind': kind, 'text': u['text']})
    open(f'refs/packets/{g}.txt', 'w').write('\n'.join(lines))
    json.dump({'group': g, 'doc': doc, 'units': rec}, open(f'refs/packets/{g}.json', 'w'), indent=1)
    print(g, len(rec), sum(len(r['text']) for r in rec))
