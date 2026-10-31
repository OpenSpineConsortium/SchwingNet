"""Scratch prototype of the check's report lines (not a repository file): the line templates the
grid job would print, run on synthetic populations to measure the line budget and the run time."""
from __future__ import annotations

import math
import time

import numpy as np

import check_proto as P
from schwingcheck import correlation as CORR

SHORT = {0: "e", 1: "d", 2: "l", 3: "ld", 4: "h"}
ORDER = " ".join(SHORT[i] + SHORT[j] for i, j in P.PAIRS)
REGIONS = ("C3-C7", "T1", "T2-T12", "L1-L4", "L5")
ADJ = ("C3-C7", "C7-T2", "T2-T12", "T12-L4", "L4-L5")


def f2(x):
    return "%.2f" % x


def sgn(x):
    return "%+.3f" % x


def judged(m, null):
    mu, sd = null
    return "%s against %s sd %.3f" % (sgn(m), sgn(mu), sd)


def average_ranks(col):
    order = np.argsort(col, kind="mergesort")
    ranks = np.empty(len(col))
    sorted_ = col[order]
    i = 0
    while i < len(col):
        j = i
        while j + 1 < len(col) and sorted_[j + 1] - sorted_[i] <= 1e-9:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def normal_scores(values):
    n = values.shape[0]
    out = np.empty_like(values, dtype=float)
    nd = P.statistics.NormalDist()
    for idx in np.ndindex(values.shape[1:]):
        r = average_ranks(values[(slice(None),) + idx])
        out[(slice(None),) + idx] = [nd.inv_cdf((x - 0.375) / (n + 0.25)) for x in r]
    return out


def icc1(groups):
    """One-way random-effects ICC(1) over groups of values (each with 2 or more); nan when fewer than 2 groups."""
    groups = [np.asarray(g, float) for g in groups if len(g) >= 2]
    g = len(groups)
    if g < 2:
        return float("nan")
    N = sum(len(x) for x in groups)
    grand = np.concatenate(groups).mean()
    ssb = sum(len(x) * (x.mean() - grand) ** 2 for x in groups)
    ssw = sum(((x - x.mean()) ** 2).sum() for x in groups)
    msb, msw = ssb / (g - 1), ssw / (N - g)
    k0 = (N - sum(len(x) ** 2 for x in groups) / N) / (g - 1)
    return float((msb - msw) / (msb + (k0 - 1) * msw))


def report(head, levels, fit, held, fit_units, held_units, facts, repeat, B=200, seed=20261031):
    """head 'enhance_pet C3..L5 check'; fit/held (n, L, M) with NaN; units per spine; facts per fit spine
    (slice_mm, foramina set of level indices); repeat: list of (unit, values (L, M)) for the ICC."""
    t0 = time.time()
    out = []
    M = len(P.MEASURES)
    whole = np.isfinite(fit).all(axis=(1, 2))
    wf, units = fit[whole], [u for u, w in zip(fit_units, whole) if w]
    hwhole = np.isfinite(held).all(axis=(1, 2))
    wh = held[hwhole]
    z, mean, sd = CORR.standardise(wf)
    n = len(z)
    reg = P.level_regions(levels)
    slices = np.array([facts[i]["slice_mm"] for i in np.flatnonzero(whole)])
    out.append("%s: rows code stamp %s; %d whole spines fitted, %d held; slice spacing median %.1f mm, %.0f%% at most 1.5, %.0f%% above 2.5"
               % (head, facts[0]["code"], n, len(wh), np.median(slices), 100 * np.mean(slices <= 1.5), 100 * np.mean(slices > 2.5)))
    miss = np.isnan(fit).mean(axis=(0, 1))
    worst = max(reg, key=lambda r: np.isnan(fit[:, reg[r], :]).mean())
    out.append("%s: missing cells of the fit part, %s; most in %s (%.1f%%)"
               % (head, ", ".join("%s %.1f%%" % (m, 100 * x) for m, x in zip(P.MEASURES, miss)), worst,
                  100 * np.isnan(fit[:, reg[worst], :]).mean()))
    obs = P.observed(z, levels)
    nl = P.null(obs["rl"], obs["rm"], n, levels, B=B, seed=seed)
    raw, drawn, mis = obs["raw"], obs["drawn"], obs["misfit"]
    zc, _, _ = CORR.standardise(normal_scores(wf))
    Cc = P.sample_corr(zc)
    out.append("%s: pairs are named e endplate, d endplate_depth, l endplate_lower, ld endplate_lower_depth, h h_post, in the order %s" % (head, ORDER))
    for k, (i, j) in enumerate(P.PAIRS):
        regions = " ".join("%s %s" % (r, f2(raw["same %d %s" % (k, r)])) for r in REGIONS if ("same %d %s" % (k, r)) in raw)
        ranks = np.mean([Cc[P.cell(l, i), P.cell(l, j)] for l in range(len(levels))])
        out.append("%s: same level %s%s: %s all %s ranks %s; drawn %s; misfit %s"
                   % (head, SHORT[i], SHORT[j], regions, f2(raw["same %d all" % k]), f2(ranks), f2(drawn["same %d all" % k]),
                      judged(mis["same %d all" % k], nl["same %d all" % k])))
    out.append("%s: same level, the six end-plate pairs: raw %s, drawn %s, misfit %s"
               % (head, f2(raw["same plate all"]), f2(drawn["same plate all"]), judged(mis["same plate all"], nl["same plate all"])))
    for m in range(M):
        out.append("%s: one level apart, %s: %s" % (head, P.MEASURES[m], " ".join(
            "%s %s" % (r, f2(raw["lag1 %d %s" % (m, r)])) for r in ADJ if ("lag1 %d %s" % (m, r)) in raw)))
    out.append("%s: one level apart as drawn, every measure: %s" % (head, " ".join(
        "%s %s" % (r, f2(drawn["lag1 0 %s" % r])) for r in ADJ if ("lag1 0 %s" % r) in drawn)))
    out.append("%s: across a disc, T2 to L4: widths facing %s far %s, %s; depths facing %s far %s, %s"
               % (head, f2(raw["facing widths"]), f2(raw["far widths"]), judged(mis["facing minus far widths"], nl["facing minus far widths"]),
                  f2(raw["facing depths"]), f2(raw["far depths"]), judged(mis["facing minus far depths"], nl["facing minus far depths"])))
    out.append("%s: one level apart, T2 to L4, contrasts: size %s, width difference %s, depth difference %s; size minus differences %s; range of the five measures %s"
               % (head, f2(raw["contrast size"]), f2(raw["contrast width difference"]), f2(raw["contrast depth difference"]),
                  judged(mis["contrast size minus differences"], nl["contrast size minus differences"]),
                  judged(mis["lag1 range core"], nl["lag1 range core"])))
    out.append("%s: far apart, C3-C7 with L1-L4: two measures %s drawn %s, misfit %s; one measure %s drawn %s"
               % (head, f2(raw["long cross C x L"]), f2(drawn["long cross C x L"]), judged(mis["long cross C x L"], nl["long cross C x L"]),
                  f2(raw["long same C x L"]), f2(drawn["long same C x L"])))
    out.append("%s: far apart, T2 to L4 six or more levels apart: two measures %s drawn %s, misfit %s"
               % (head, f2(raw["long cross core lag6"]), f2(drawn["long cross core lag6"]), judged(mis["long cross core lag6"], nl["long cross core lag6"])))
    full = np.array([obs["rm"][i, j] for i, j in P.PAIRS])
    out.append("%s: refit r_measure unshrunk over %s on these spines: %s" % (head, "C3..L5", " ".join(f2(x) for x in full)))
    for name, r in obs["refits"].items():
        out.append("%s: refit r_measure unshrunk over %s on these spines: %s; width pair change %s; mean absolute change %s"
                   % (head, name, " ".join(f2(x) for x in r), judged(mis["refit %s width pair" % name], nl["refit %s width pair" % name]),
                      judged(mis["refit %s mean abs" % name], nl["refit %s mean abs" % name])))
    big = np.abs(z) > 4
    worst = max(reg, key=lambda r: big[:, reg[r], :].mean())
    out.append("%s: values beyond 4 SD of their cell, %s; most in %s (%.2f%%); a Gaussian gives 0.006%%"
               % (head, ", ".join("%s %.2f%%" % (m, 100 * big[:, :, i].mean()) for i, m in enumerate(P.MEASURES)), worst, 100 * big[:, reg[worst], :].mean()))
    _, rmc = CORR.flip_flop(zc)
    out.append("%s: normal-scores refit r_measure unshrunk: %s" % (head, " ".join(f2(rmc[i, j]) for i, j in P.PAIRS)))
    cv = P.cv_scores(wf, units)
    ho = P.held_scores(wf, wh, cv["w"]) if len(wh) >= 2 else None
    out.append("%s: fivefold by unit on the fit part, gain over the prior in nats a spine: person effect plus Kronecker %+.2f (SE %.2f); blend at weight %.2f %+.2f (SE %.2f)"
               % (head, cv["person"][0], cv["person"][1], cv["w"], cv["blend"][0], cv["blend"][1]))
    if ho:
        out.append("%s: held out %d whole spines, gain over the prior in nats a spine: person effect plus Kronecker %+.2f (SE %.2f); blend %+.2f (SE %.2f)"
                   % (head, len(wh), ho["person"][0], ho["person"][1], ho["blend"][0], ho["blend"][1]))
    a, Bm, CL, CMm, pc = P.person_effect(z)
    pd = (1 - P.SHRINK) * CORR.to_correlation(pc) + P.SHRINK * np.eye(len(pc))
    share = np.array([[a[l] ** 2 * Bm[m, m] / pc[P.cell(l, m), P.cell(l, m)] for m in range(M)] for l in range(len(levels))])
    bcorr = CORR.to_correlation(Bm)
    implied = {r: P.same_level(pd, reg[r], 0, 2) for r in ("C3-C7", "T2-T12", "L1-L4")}
    out.append("%s: person effect: share of a cell's variance %s; its measure correlation %s; it draws the width pair at %s"
               % (head, " ".join("%s %s" % (r, f2(share[reg[r], :].mean())) for r in REGIONS if r in reg),
                  " ".join(f2(bcorr[i, j]) for i, j in P.PAIRS), " ".join("%s %s" % (r, f2(v)) for r, v in implied.items())))
    # the neck cut, where the levels hold the neck
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
        out.append("%s: neck body cut fell back on %.0f%% of C3-C7 vertebrae; width pair r %s where it fell back, %s where a foramen closed"
                   % (head, 100 * share_fl, r_of(fl), r_of(un)))
    pm = z.mean(axis=1)
    rs = [np.corrcoef(slices, pm[:, m])[0, 1] for m in range(M)]
    main = slices > 2.5 if np.mean(slices > 2.5) >= 0.5 else slices <= 2.5
    if main.sum() >= 60:
        zs, _, _ = CORR.standardise(wf[main])
        _, rms = CORR.flip_flop(zs)
        sub = "refit on the %d spines of the commoner class: widths %s depths %s" % (main.sum(), f2(rms[0, 2]), f2(rms[1, 3]))
    else:
        sub = "no slice class holds 60 spines"
    out.append("%s: slice spacing against each spine's mean z, %s; %s" % (head, ", ".join("%s %+.2f" % (m, r) for m, r in zip(P.MEASURES, rs)), sub))
    # repeat scans
    if repeat:
        byunit = {}
        for u, v in repeat:
            byunit.setdefault(u, []).append(v)
        multi = {u: vs for u, vs in byunit.items() if len(vs) >= 2}
        iccs = np.full((len(levels), M), np.nan)
        for l in range(len(levels)):
            for m in range(M):
                groups = [[v[l, m] for v in vs if np.isfinite(v[l, m])] for vs in multi.values()]
                iccs[l, m] = icc1(groups)
        out.append("%s: repeat scans, %d units of %d studies: ICC by region %s" % (head, len(multi), sum(len(v) for v in multi.values()),
                   "; ".join("%s %s" % (m, " ".join(f2(np.nanmean(iccs[reg[r], i])) for r in REGIONS if r in reg)) for i, m in enumerate(P.MEASURES[:3]))))
        out.append("%s: repeat scans, ICC by region %s" % (head, "; ".join("%s %s" % (m, " ".join(f2(np.nanmean(iccs[reg[r], i])) for r in REGIONS if r in reg)) for i, m in enumerate(P.MEASURES) if i >= 3)))
        core = [l for r in ("T2-T12", "L1-L4") for l in reg.get(r, [])]
        C = P.sample_corr(z)
        def corrected(i, j):
            vals = [C[P.cell(l, i), P.cell(l, j)] / math.sqrt(max(iccs[l, i], 0.1) * max(iccs[l, j], 0.1)) for l in core if np.isfinite(iccs[l, i] * iccs[l, j])]
            return f2(np.mean(vals)) if vals else "n/a"
        out.append("%s: same level corrected for repeat-scan agreement, T2 to L4: widths %s, depths %s, upper width and depth %s, lower width and depth %s, h_post with the depths %s"
                   % (head, corrected(0, 2), corrected(1, 3), corrected(0, 1), corrected(2, 3), corrected(4, 1)))
    out.append("%s: done in %.0f s, %d bootstrap draws from the fitted Kronecker" % (head, time.time() - t0, B))
    return out
