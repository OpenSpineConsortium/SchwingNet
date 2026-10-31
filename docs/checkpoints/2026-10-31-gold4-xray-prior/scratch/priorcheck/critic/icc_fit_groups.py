"""Critic's check: SD of ICC(1) over the 47 repeat units that fall in the prior's fit part (sizes from
data/splits/latent-prior-repeat-groups.json, the reserve and the held hash applied as gold3_prior.py does)."""
import hashlib, json
import numpy as np
g = json.load(open('/home/claude/SchwingNet/data/splits/latent-prior-repeat-groups.json'))
res = {p['person'] for p in json.load(open('/home/claude/SchwingNet/data/splits/latent-prior-test-reserve.json'))}
held = lambda u: int(hashlib.sha256(("gold3-prior:" + u).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < 0.2
sizes = [len(x['persons']) for x in g if not any(p in res for p in x['persons']) and not held(x['unit'])]
def icc1(groups):
    k = np.array([len(x) for x in groups]); N = k.sum(); G = len(groups)
    allv = np.concatenate(groups); gm = allv.mean()
    msb = sum(len(x) * (x.mean() - gm) ** 2 for x in groups) / (G - 1)
    msw = sum(((x - x.mean()) ** 2).sum() for x in groups) / (N - G)
    k0 = (N - (k ** 2).sum() / N) / (G - 1)
    return (msb - msw) / (msb + (k0 - 1) * msw)
rng = np.random.default_rng(7)
print("units", len(sizes), "studies", sum(sizes))
for true in (0.6, 0.7, 0.8, 0.9):
    est = []
    for _ in range(4000):
        u = rng.normal(0, np.sqrt(true), size=len(sizes))
        est.append(icc1([u[i] + rng.normal(0, np.sqrt(1 - true), size=s) for i, s in enumerate(sizes)]))
    est = np.array(est)
    print("true %.1f: mean %.3f sd %.3f, share below 0.75 %.3f" % (true, est.mean(), est.std(ddof=1), (est < 0.75).mean()))
