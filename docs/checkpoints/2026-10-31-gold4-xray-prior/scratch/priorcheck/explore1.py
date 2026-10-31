import sys, time, json
sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck")
import numpy as np
import kron_sim as K

obs = K.observed_targets()
e = obs["enhance_C3L5"]
rl_u, rm_u = K.unshrink(e.r_level), K.unshrink(e.r_measure)
sig = np.kron(rl_u, rm_u)
# truth (a) as a Truth: lam = chol(sig), psi tiny
lam = K.chol_psd(sig)
ta = K.Truth("a_separable", lam, np.zeros(K.L*K.M))
print("diag check", np.abs(np.diag(ta.sigma())-1).max())
# population projection must return the matrices
t0=time.time(); prl, prm, used = K.project(sig, K.L); print("project steps", used, "time %.3f"%(time.time()-t0))
print("max |proj - truth| level %.2e measure %.2e" % (np.abs(prl-rl_u).max(), np.abs(prm-rm_u).max()))
# flip-flop convergence on a sample: how many steps does the copied loop use?
rng = np.random.default_rng(1)
v = ta.sample(rng, 693)
z,_,_ = K.standardise(v)
n, nl, nm = z.shape
sl, sm = np.eye(nl), np.eye(nm)
for i in range(300):
    im = np.linalg.inv(sm)
    sl_new = np.einsum("nlm,mk,njk->lj", z, im, z) / (n * nm)
    il = np.linalg.inv(sl_new)
    sm_new = np.einsum("nlm,lk,nkj->mj", z, il, z) / (n * nl)
    d = max(np.abs(sl_new - sl).max(), np.abs(sm_new - sm).max())
    sl, sm = sl_new, sm_new
    if d < 1e-9:
        print("sample flip-flop converged at step", i+1); break
t0=time.time(); rl, rm = K.grid_fit(v); print("fit time %.3f"%(time.time()-t0))
print("fitted R_measure:\n", rm.round(3))
print("published R_measure:\n", e.r_measure.round(3))
print("lag fitted", np.round(K.lag_profile(rl),3), "published", np.round(K.lag_profile(e.r_level),3))
