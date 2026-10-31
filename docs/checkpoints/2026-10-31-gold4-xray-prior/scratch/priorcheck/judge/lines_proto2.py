"""Scratch prototype, second cut: the check's report lines in the widths the gate shows (each line,
with the report's "- " before it, at most 196 characters for the longest population name)."""
from __future__ import annotations

import math
import time

import numpy as np

import check_proto as P
from lines_proto import average_ranks, icc1
from schwingcheck import correlation as CORR

SHORT = {0: "e", 1: "d", 2: "l", 3: "ld", 4: "h"}
ORDER = " ".join(SHORT[i] + SHORT[j] for i, j in P.PAIRS)
REGIONS = ("C3-C7", "T1", "T2-T12", "L1-L4", "L5")
ADJ = ("C3-C7", "C7-T2", "T2-T12", "T12-L4", "L4-L5")
GAP_REGIONS = ("C3-C7", "T2-T12", "L1-L4")


def f2(x):
    return "n/a" if not np.isfinite(x) else "%.2f" % x


def judged(m, null):
    mu, sd = null
    z = (m - mu) / sd if sd > 0 else float("nan")
    return "%+.3f against %+.3f sd %.3f (z %+.1f)" % (m, mu, sd, z)


def normal_scores(values):
    n = values.shape[0]
    out = np.empty_like(values, dtype=float)
    nd = P.statistics.NormalDist()
    for idx in np.ndindex(values.shape[1:]):
        r = average_ranks(values[(slice(None),) + idx])
        out[(slice(None),) + idx] = [nd.inv_cdf((x - 0.375) / (n + 0.25)) for x in r]
    return out


def gap(S, C, reg):
    return max(abs(P.same_level(S, reg[r], i, j) - P.same_level(C, reg[r], i, j))
               for r in GAP_REGIONS if r in reg for k, (i, j) in enumerate(P.PAIRS) if k in P.PLATE)


def report(head, levels, fit, held, fit_units, facts, repeat, B=200, seed=20261031):
    t0 = time.time()
    out = []
    say = lambda text: out.append("%s: %s" % (head, text))
    M = len(P.MEASURES)
    whole = np.isfinite(fit).all(axis=(1, 2))
    wf, units = fit[whole], [u for u, w in zip(fit_units, whole) if w]
    wh = held[np.isfinite(held).all(axis=(1, 2))]
    z, _, _ = CORR.standardise(wf)
    n = len(z)
    reg = P.level_regions(levels)
    slices = np.array([facts[i]["slice_mm"] for i in np.flatnonzero(whole)])
    # S0
    say("rows code stamp %s; %d whole spines fitted, %d held; slice spacing median %.1f mm, %.0f%% at most 1.5 mm, %.0f%% above 2.5 mm"
        % (facts[0]["code"], n, len(wh), np.median(slices), 100 * np.mean(slices <= 1.5), 100 * np.mean(slices > 2.5)))
    say("measures e endplate, d endplate_depth, l endplate_lower, ld endplate_lower_depth, h h_post; pairs in the order %s" % ORDER)
    miss = np.isnan(fit).mean(axis=(0, 1))
    worst = max(reg, key=lambda r: np.isnan(fit[:, reg[r], :]).mean())
    say("missing cells of the fit part, %s; most in %s (%.1f%%)"
        % (", ".join("%s %.1f%%" % (SHORT[m], 100 * x) for m, x in enumerate(miss)), worst, 100 * np.isnan(fit[:, reg[worst], :]).mean()))
    obs = P.observed(z, levels)
    nl = P.null(obs["rl"], obs["rm"], n, levels, B=B, seed=seed)
    raw, drawn, mis = obs["raw"], obs["drawn"], obs["misfit"]
    zc, _, _ = CORR.standardise(normal_scores(wf))
    Cc = P.sample_corr(zc)
    # S1
    for k, (i, j) in enumerate(P.PAIRS):
        regions = " ".join("%s %s" % (r, f2(raw["same %d %s" % (k, r)])) for r in REGIONS if ("same %d %s" % (k, r)) in raw)
        ranks = np.mean([Cc[P.cell(l, i), P.cell(l, j)] for l in range(len(levels))])
        say("same level %s%s: %s all %s ranks %s; drawn %s; misfit %s"
            % (SHORT[i], SHORT[j], regions, f2(raw["same %d all" % k]), f2(ranks), f2(drawn["same %d all" % k]),
               judged(mis["same %d all" % k], nl["same %d all" % k])))
    say("same level, the six end-plate pairs: raw %s, drawn %s, misfit %s"
        % (f2(raw["same plate all"]), f2(drawn["same plate all"]), judged(mis["same plate all"], nl["same plate all"])))
    # S2
    for m in range(M):
        say("one level apart, %s: %s" % (P.MEASURES[m], " ".join(
            "%s %s" % (r, f2(raw["lag1 %d %s" % (m, r)])) for r in ADJ if ("lag1 %d %s" % (m, r)) in raw)))
    say("one level apart as drawn, every measure: %s" % " ".join(
        "%s %s" % (r, f2(drawn["lag1 0 %s" % r])) for r in ADJ if ("lag1 0 %s" % r) in drawn))
    say("one level apart, T2 to L4, range of the five measures: %s" % judged(mis["lag1 range core"], nl["lag1 range core"]))
    for name, key in (("widths", "widths"), ("depths", "depths")):
        say("across a disc, T2 to L4, %s: facing %s far %s, facing minus far %s"
            % (name, f2(raw["facing " + key]), f2(raw["far " + key]), judged(mis["facing minus far " + key], nl["facing minus far " + key])))
    # S3
    say("contrasts one level apart, T2 to L4: size %s, width difference %s, depth difference %s; size minus differences %s"
        % (f2(raw["contrast size"]), f2(raw["contrast width difference"]), f2(raw["contrast depth difference"]),
           judged(mis["contrast size minus differences"], nl["contrast size minus differences"])))
    # S4
    if "long cross C x L" in raw:
        say("far apart, C3-C7 with L1-L4: two measures %s drawn %s, misfit %s; one measure %s drawn %s"
            % (f2(raw["long cross C x L"]), f2(drawn["long cross C x L"]), judged(mis["long cross C x L"], nl["long cross C x L"]),
               f2(raw["long same C x L"]), f2(drawn["long same C x L"])))
    say("far apart, T2 to L4, six or more levels: two measures %s drawn %s, misfit %s"
        % (f2(raw["long cross core lag6"]), f2(drawn["long cross core lag6"]), judged(mis["long cross core lag6"], nl["long cross core lag6"])))
    # S5
    say("refit over C3..L5, unshrunk: %s" % " ".join(f2(obs["rm"][i, j]) for i, j in P.PAIRS))
    for name, r in obs["refits"].items():
        say("refit over %s, unshrunk: %s" % (name, " ".join(f2(x) for x in r)))
        say("refit over %s, change from C3..L5: width pair %s; mean absolute %s"
            % (name, judged(mis["refit %s width pair" % name], nl["refit %s width pair" % name]),
               judged(mis["refit %s mean abs" % name], nl["refit %s mean abs" % name])))
    # S6
    big = np.abs(z) > 4
    worst = max(reg, key=lambda r: big[:, reg[r], :].mean())
    say("values beyond 4 SD of their cell, %s; most in %s (%.2f%%); a Gaussian gives 0.006%%"
        % (", ".join("%s %.2f%%" % (SHORT[i], 100 * big[:, :, i].mean()) for i in range(M)), worst, 100 * big[:, reg[worst], :].mean()))
    _, rmc = CORR.flip_flop(zc)
    say("normal-scores refit, unshrunk: %s" % " ".join(f2(rmc[i, j]) for i, j in P.PAIRS))
    # S7
    cv = P.cv_scores(wf, units)
    say("fivefold by unit, gain over the prior in nats a spine: person effect plus Kronecker %+.2f (SE %.2f); blend at weight %.2f %+.2f (SE %.2f)"
        % (cv["person"][0], cv["person"][1], cv["w"], cv["blend"][0], cv["blend"][1]))
    if len(wh) >= 2:
        ho = P.held_scores(wf, wh, cv["w"])
        say("held out %d whole spines, gain in nats a spine: person effect plus Kronecker %+.2f (SE %.2f); blend %+.2f (SE %.2f)"
            % (len(wh), ho["person"][0], ho["person"][1], ho["blend"][0], ho["blend"][1]))
    a, Bm, CL, CMm, pc = P.person_effect(z)
    pd = (1 - P.SHRINK) * CORR.to_correlation(pc) + P.SHRINK * np.eye(len(pc))
    share = np.array([[a[l] ** 2 * Bm[m, m] / pc[P.cell(l, m), P.cell(l, m)] for m in range(M)] for l in range(len(levels))])
    bcorr = CORR.to_correlation(Bm)
    say("person effect, share of a cell's variance: %s" % " ".join("%s %s" % (r, f2(share[reg[r], :].mean())) for r in REGIONS if r in reg))
    say("person effect, its own measure correlation: %s" % " ".join(f2(bcorr[i, j]) for i, j in P.PAIRS))
    C = P.sample_corr(z)
    K = obs["drawn_matrix"] if "drawn_matrix" in obs else np.kron(CORR.shrunk(obs["rl"], P.SHRINK), CORR.shrunk(obs["rm"], P.SHRINK))
    blend = cv["w"] * K + (1 - cv["w"]) * C
    there = [r for r in GAP_REGIONS if r in reg]
    say("width pair over %s: raw %s; prior %s; person effect %s"
        % (" ".join(there), " ".join(f2(P.same_level(C, reg[r], 0, 2)) for r in there),
           " ".join(f2(P.same_level(K, reg[r], 0, 2)) for r in there), " ".join(f2(P.same_level(pd, reg[r], 0, 2)) for r in there)))
    say("six end-plate pairs, largest gap from raw over %s: prior %s, person effect %s, blend %s"
        % (" ".join(there), f2(gap(K, C, reg)), f2(gap(pd, C, reg)), f2(gap(blend, C, reg))))
    # S9 mechanisms
    if "C3-C7" in reg:
        fl, un = [], []
        for s, spine in enumerate(np.flatnonzero(whole)):
            for l in reg["C3-C7"]:
                (fl if l in facts[spine]["foramina"] else un).append((z[s, l, 0], z[s, l, 2]))
        def r_of(pairs):
            if len(pairs) < 10:
                return "n/a"
            x = np.array(pairs)
            return "%s (%d)" % (f2(np.corrcoef(x[:, 0], x[:, 1])[0, 1]), len(x))
        share_fl = len(fl) / max(1, len(fl) + len(un))
        say("neck body cut fell back on %.0f%% of C3-C7 vertebrae; width pair r %s where it fell back, %s where a foramen closed"
            % (100 * share_fl, r_of(fl), r_of(un)))
    pm = z.mean(axis=1)
    rs = [np.corrcoef(slices, pm[:, m])[0, 1] for m in range(M)]
    thick = slices > 2.5
    main = thick if thick.mean() >= 0.5 else ~thick
    if main.sum() >= 60:
        zs, _, _ = CORR.standardise(wf[main])
        _, rms = CORR.flip_flop(zs)
        sub = "refit on the %d spines %s 2.5 mm, el %s dld %s" % (main.sum(), "above" if thick.mean() >= 0.5 else "at most", f2(rms[0, 2]), f2(rms[1, 3]))
    else:
        sub = "no slice class holds 60 spines"
    say("slice spacing against each spine's mean z, %s; %s" % (", ".join("%s %+.2f" % (SHORT[m], r) for m, r in enumerate(rs)), sub))
    # S8 repeat scans
    if repeat:
        byunit = {}
        for u, v in repeat:
            byunit.setdefault(u, []).append(v)
        multi = {u: vs for u, vs in byunit.items() if len(vs) >= 2}
        iccs = np.full((len(levels), M), np.nan)
        for l in range(len(levels)):
            for m in range(M):
                iccs[l, m] = icc1([[v[l, m] for v in vs if np.isfinite(v[l, m])] for vs in multi.values()])
        there = [r for r in REGIONS if r in reg]
        row = lambda m: "%s %s" % (SHORT[m], " ".join(f2(np.nanmean(iccs[reg[r], m])) for r in there))
        say("repeat scans, %d units of %d studies, ICC over %s: %s; %s"
            % (len(multi), sum(len(v) for v in multi.values()), " ".join(there), row(0), row(1)))
        say("repeat scans, ICC over %s: %s; %s; %s" % (" ".join(there), row(2), row(3), row(4)))
        core = [l for r in ("T2-T12", "L1-L4") for l in reg.get(r, [])]
        def both(i, j):
            vals = [C[P.cell(l, i), P.cell(l, j)] for l in core]
            cor = [C[P.cell(l, i), P.cell(l, j)] / math.sqrt(max(iccs[l, i], 0.1) * max(iccs[l, j], 0.1))
                   for l in core if np.isfinite(iccs[l, i] * iccs[l, j])]
            return "%s%s %s %s" % (SHORT[i], SHORT[j], f2(np.mean(vals)), f2(np.mean(cor)) if cor else "n/a")
        say("same level in T2 to L4, raw then corrected for repeat-scan agreement: %s"
            % ", ".join(both(i, j) for i, j in ((0, 2), (1, 3), (0, 1), (2, 3), (1, 4), (3, 4))))
    say("done in %.0f s, %d draws from the fitted Kronecker for each null" % (time.time() - t0, B))
    return out
