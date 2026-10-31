import sys
sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck")
import numpy as np
import kron_sim as K
L, M = K.L, K.M
def factor_truth(a2, b2, c2, g=0.4, phi=0.6, hp_a=0.0, hp_c=0.0, disc=0.0):
    ku = K.ar_kernel(L, phi, g)
    a = [np.sqrt(a2)]*4 + [np.sqrt(hp_a)]
    b = [np.sqrt(b2)]*5
    c = [np.sqrt(c2)]*4 + [np.sqrt(hp_c)]
    cols = [K.comp_global(a), K.comp_measure_fields(b, ku), K.comp_vertebra(c)]
    psi = np.zeros(L*M)
    for l in range(L):
        for m in range(M):
            tot = (a[m]**2 + b[m]**2 + c[m]**2)
            psi[K.cell(l,m)] = max(1 - tot - (disc if m < 4 else 0), 0.0)
    if disc:
        cols.append(K.comp_disc(np.sqrt(disc), np.sqrt(disc)))
    return K.scaled("f", cols, psi)
print("a2 b2 c2 disc | true S(wd4) widths | lag1 lag5 | crossboth lag1 | disc | fitted Rm wd4 widths | Rl lag1 lag5 | KLgap gain_vs_assumed")
for a2, b2, c2, disc in [(0.15,0.45,0.0,0),(0.15,0.45,0.1,0),(0.15,0.45,0.2,0),(0.15,0.45,0.3,0),(0.15,0.45,0.4,0),
                         (0.0,0.6,0.4,0),(0.3,0.3,0.3,0),(0.15,0.45,0.2,0.15),(0.15,0.45,0.0,0.3),(0.15,0.45,0.2,0.2)]:
    t = factor_truth(a2,b2,c2,disc=disc)
    s = t.sigma()
    ts = K.truth_stats(s)
    rl, rm = K.projected_prior(s)
    ps = K.prior_stats(rl, rm)
    gap = K.population_kl_gap(s, rl, rm); gain = K.population_gain_over_assumed(s, rl, rm)
    print("%.2f %.2f %.2f %.2f | %.3f %.3f | %.3f %.3f | %.3f | %.3f | %.3f %.3f | %.3f %.3f | %.2f %.2f" % (
        a2,b2,c2,disc, ts["same_level_wd4_mean"], ts["same_level_widths"], ts["lag_same_measure_wd4"][0], ts["lag_same_measure_wd4"][4],
        ts["lag1_cross_wd4_not_facing"], ts["disc_widths"], ps["R_measure_wd4_mean"], ps["R_measure_widths"], ps["R_level_lag"][0], ps["R_level_lag"][4], gap, gain))
