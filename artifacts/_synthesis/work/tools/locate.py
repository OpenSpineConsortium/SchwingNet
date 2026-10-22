import json, re, sys, os, unicodedata
base='/tmp/claude-0/-home-user/1b2f17bd-1fd4-5865-b98a-4797cc8ea3ad/scratchpad'
c=json.load(open(base+'/cands.json'))
textdir=base+'/text'
def resolve(aid):
    if not aid: return None
    p=os.path.join(textdir, aid+'.txt')
    if os.path.exists(p): return p
    repo,name=aid.split('/',1)
    for f in os.listdir(os.path.join(textdir,repo)):
        if f.startswith(name): return os.path.join(textdir,repo,f)
    return None
def norm(s):
    s=s.replace('\u00a0',' ').replace('\u202f',' ').replace('\u2009',' ')
    s=s.replace('\u2019',"'").replace('\u2018',"'").replace('\u201c','"').replace('\u201d','"')
    return re.sub(r'\s+',' ',s).strip()
def find(path, q):
    raw=open(path,encoding='utf-8').read()
    lines=raw.split('\n')
    out=[]
    frags=[f.strip(' .') for f in re.split(r'\.\.\.|\u2026',q) if f.strip(' .')]
    for fr in frags:
        nf=norm(fr).lower()
        hit=None
        for ln in lines:
            if nf in norm(ln).lower():
                hit=ln; break
        if hit is None:
            # try shorter prefix
            short=nf[:40]
            for ln in lines:
                if short in norm(ln).lower():
                    hit='[PREFIX] '+ln; break
        out.append((fr, hit))
    return out
sel=[int(x) for x in sys.argv[1:]] if len(sys.argv)>1 else range(1,81)
for n in sel:
    x=c[n-1]
    print('=====',n,x['topic'])
    for side in 'ab':
        aid=x['artifact_'+side]; q=x['quote_'+side]
        p=resolve(aid)
        if not p or not q:
            print(side,'NO TEXT/QUOTE',aid); continue
        for fr,hit in find(p,q):
            h=hit if hit is None else (hit if len(hit)<1500 else hit[:1500]+' [...]')
            print(side,'FRAG:',fr[:80]); print('   LINE:',h)
