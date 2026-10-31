"""The trimmed check's printed statistics in the population limit (n -> infinity, no sampling), for
the statistics critic's truths matched to the published ENHANCE.PET C3..L5 prior (review/limit_stats.py
builds the same truths; kron_sim.match_core and match_regional_mixed). C is the truth itself, K the
shrunk projection, as the job computes them from the sample correlation and the fit. The definitions
are SPEC.md's: far apart per plate pair with the two orders averaged, facing minus far over the 14
core discs and by the lower vertebra's group, refits over the subsets on the same spines. No row is
read; the only real numbers are the four published priors."""
import json
import sys
import numpy as np

PC = "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck"
sys.path.insert(0, PC)
import kron_sim as K  # noqa: E402

L, M = K.L, K.M
LEV = K.LEVELS
E, D, LW, LD, H = range(5)
PAIRS = [(i, j) for i in range(5) for j in range(i + 1, 5)]
NAMES = ["ed", "el", "eld", "eh", "dl", "dld", "dh", "lld", "lh", "ldh"]
PLATE = [k for k, (i, j) in enumerate(PAIRS) if j < 4]
REG = {"C3-C7": list(range(0, 5)), "T1": [5], "T2-T12": list(range(6, 17)), "L1-L4": list(range(17, 21)), "L5": [21]}
CORE = list(range(6, 21))                               # T2..L4
DISCS = [l for l in range(L - 1) if l in CORE and l + 1 in CORE]   # upper vertebra of each core disc
GROUPS = {"T2-T9": [l for l in DISCS if 7 <= l + 1 <= 13],        # lower vertebra T3..T9
          "T10-T12": [l for l in DISCS if 14 <= l + 1 <= 16],     # lower vertebra T10..T12
          "L1-L4": [l for l in DISCS if 17 <= l + 1 <= 20]}       # lower vertebra L1..L4
SUBSETS = {"T1..L5": (5, 21), "T2..L4": (6, 20), "T1..L4": (5, 20), "T2..L5": (6, 21), "C3..C7": (0, 4)}


def c(l, m):
    return l * M + m


def same(S, idx, i, j):
    return float(np.mean([S[c(l, i), c(l, j)] for l in idx]))


def lag1(S, adj, i, j):
    return float(np.mean([S[c(l, i), c(l + 1, j)] for l in adj]))


def far(S, A, B, i, j, lag=None):
    vals = []
    for a in A:
        for b in B:
            if lag is not None and b - a < lag:
                continue
            vals.append(0.5 * (S[c(a, i), c(b, j)] + S[c(a, j), c(b, i)]))
    return float(np.mean(vals))


def stats(S):
    out = {}
    out["six"] = float(np.mean([same(S, range(L), *PAIRS[k]) for k in PLATE]))
    for k in (1, 5):
        for r, idx in REG.items():
            out["same %s %s" % (NAMES[k], r)] = same(S, idx, *PAIRS[k])
        out["same %s all" % NAMES[k]] = same(S, range(L), *PAIRS[k])
    lags = [lag1(S, DISCS, m, m) for m in range(5)]
    out["lag core range"] = max(lags) - min(lags)
    out["facing-far w"] = lag1(S, DISCS, LW, E) - lag1(S, DISCS, E, LW)
    out["facing-far d"] = lag1(S, DISCS, LD, D) - lag1(S, DISCS, D, LD)
    for g, adj in GROUPS.items():
        out["facing-far w %s" % g] = lag1(S, adj, LW, E) - lag1(S, adj, E, LW)
        out["facing-far d %s" % g] = lag1(S, adj, LD, D) - lag1(S, adj, D, LD)
    out["far CxL"] = [far(S, REG["C3-C7"], REG["L1-L4"], *PAIRS[k]) for k in PLATE]
    out["far core lag6"] = [far(S, CORE, CORE, *PAIRS[k], lag=6) for k in PLATE]
    return out


def misfit(sig):
    rl, rm, _ = K.project(sig, L)
    Kd = np.kron(K.shrunk(rl, 0.05), K.shrunk(rm, 0.05))
    sc, sk = stats(sig), stats(Kd)
    out = {}
    for k in ("six", "lag core range", "facing-far w", "facing-far d") + tuple(k for k in sc if k.startswith("facing-far ") and k.count(" ") == 3):
        out[k] = round(sc[k] - sk[k], 3)
    for key in ("far CxL", "far core lag6"):
        d = [round(a - b, 3) for a, b in zip(sc[key], sk[key])]
        out[key + " by pair"] = d
        out[key + " mean"] = round(float(np.mean(d)), 3) if (min(d) > 0 or max(d) < 0) else None
    for k in sc:
        if k.startswith("same "):
            out["raw " + k] = round(sc[k], 3)
    out["drawn el"], out["drawn dld"] = round(sk["same el all"], 3), round(sk["same dld all"], 3)
    for name, (a, b) in SUBSETS.items():
        idx = list(range(a, b + 1))
        _, rms, _ = K.project(K.sub_levels(sig, idx), len(idx))
        out["refit %s width change" % name] = round(float(rms[E, LW] - rm[E, LW]), 3)
        out["refit %s depth change" % name] = round(float(rms[D, LD] - rm[D, LD]), 3)
    return out


def matched(parts, tl, tm):
    theta = sum(w for _, w in parts)
    delta = sum(w * K.delta_kind(k) for k, w in parts) / theta
    r = K.match_core(delta, theta, tl, tm)
    return r["sigma"] if r["ok"] else None


def main():
    obs = K.observed_targets()
    tl, tm = K.unshrink(obs["enhance_C3L5"].r_level), K.unshrink(obs["enhance_C3L5"].r_measure)
    tm1 = K.unshrink(obs["enhance_T1L5"].r_measure)
    cases = [("separable", None), ("noise 0.20", [("noise", 0.20)]), ("disc 0.163", [("disc", 0.163)]),
             ("size 0.20", [("size", 0.20)]), ("size 0.365", [("size", 0.365)]), ("size_wd 0.20", [("size_wd", 0.20)]),
             ("size_wd 0.15 + noise 0.10", [("size_wd", 0.15), ("noise", 0.10)]),
             ("noise 0.10 + disc 0.08", [("noise", 0.10), ("disc", 0.08)]),
             ("vertebra_wd 0.20", [("vertebra_wd", 0.20)]), ("cervical_widths 0.20", [("cervical_widths", 0.20)])]
    for name, parts in cases:
        sig = np.kron(tl, tm) if parts is None else matched(parts, tl, tm)
        print(json.dumps({"truth": name, "ok": sig is not None, **(misfit(sig) if sig is not None else {})}), flush=True)
    for kind, theta in (("size_wd", 0.35), ("size", 0.30)):
        r = K.match_regional_mixed(tl, tm, tm1, K.delta_kind(kind), theta)
        name = "regional+%s %.2f" % (kind, theta)
        print(json.dumps({"truth": name, "ok": r["ok"], **(misfit(r["sigma"]) if r["ok"] else {})}), flush=True)


if __name__ == "__main__":
    main()
