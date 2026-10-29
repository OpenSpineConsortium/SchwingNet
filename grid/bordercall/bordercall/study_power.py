"""Power and size of the randomized reader study the white paper specifies, by simulation.

    python run.py study-power --outdir ../records/whitepaper-2026-10-26

The white paper of 2026-10-26 (docs/SCHWINGCHECK_LEVELCHECK.md) specifies a study in which
surgeons name the level of a marked vertebra on simulated radiographs, each case randomized within
reader and stratum to a registration aid (A) or to the exact rule (B), half each. The primary
comparison is over the standard and narrow-field strata, where the registration aid has a
correctly labelled CT to register; the transitional stratum and the stratum with no CT are
compared on their own. This simulates the plan's analyses to choose the number of readers and of
cases and to fix the critical values that keep the tests at their level.

The model. Correctness follows a logistic model with a reader intercept (SD 0.5 on the logit
scale) and a case intercept (SD 1.0), and, so that the aids' difference itself varies, a
reader-by-aid and a case-by-aid term: the logit difference between the aids for reader r on case c
is the mean difference plus v_r plus g_c, half added to B's logit and half taken from A's. Three
settings of their SDs are simulated: none (0, 0), moderate (0.25, 0.5) and large (0.25, 1.0); the
first simulation of the plan had neither term. Each aid's intercept is calibrated, by Gauss-Hermite
quadrature over the summed random effects, so that its accuracy over readers and cases is the
stated one. Every reader reads the same cases, as in the study, so cases are crossed with readers,
and each reader is allocated half of each stratum's cases to each aid.

The primary analysis. Each reader's difference d_r is the reader's accuracy on B minus that on A,
and the estimate is their mean. Readers are independent given the cases, so by the law of total
variance its variance is E[Var(d_r | cases)] / R, which the readers' sample variance estimates as
the t interval does, plus Var(delta_c) / C, where delta_c is case c's difference in accuracy
between the aids averaged over readers. The second term is the one a t interval over readers
leaves out, the cases being shared by every reader. It is estimated from each case's difference
between the readers who read it with B and those who read it with A: the variance of those
differences across cases, less the mean of their binomial sampling variances
p_B (1 - p_B) / (n_B - 1) + p_A (1 - p_A) / (n_A - 1), truncated at zero. The degrees of freedom are
Satterthwaite's over the three mean squares. Near the 95% accuracies the study expects, a
difference of proportions is skewed and its estimated variance falls as the estimate rises, so a
nominal t critical value lets too many null studies through even with a variance that is right on
average. The plan therefore fixes the critical value by simulation: for noninferiority, the
largest 97.5% quantile of (estimate - true difference) / standard error over the three interaction
settings at a true difference of minus the margin, at 95% against 90% and at 90% against 85%; for
superiority, the same at no difference, at 95% and at 90% on both aids. Noninferiority is claimed
when the estimate minus that critical value times the standard error lies above minus the margin,
and superiority when it lies above zero. The t interval over readers, the first plan's primary, is
recorded beside it with its nominal critical value, so its size under each setting is on record.

The tables. The grid gives, for readers by primary cases per reader (half in each of the two
primary strata), the nominal sizes, the calibrated critical values, and the power of
noninferiority when both aids are 95% accurate and of superiority at 90% against 95%, under each
interaction setting. The strata give one stratum's two-sided comparison, ten cases per reader,
five per aid, at 5% and at 1.25%, the level Holm's correction across four strata gives the first
stratum it tests, with critical values calibrated the same way at no difference. Every cell draws
from its own generator, seeded from SEED and the cell's indices, so a cell's numbers do not depend
on which other cells were run or in what order.

The three-arm design. The owner's revision of 2026-10-27 randomizes each case within reader and
stratum to one of three aids, registration alone (A), the exact rule alone (B) and the two together
(C), a third of each stratum's cases to each, in four strata, and makes C minus A over the whole
case mix the primary contrast. `run_three` simulates that design with the same model and the same
two analyses, so that its power, its size and its critical values carry a record:

    python run.py study-power-three --outdir ../records/whitepaper-2026-10-26

Each aid has its own reader-by-aid and case-by-aid terms, independent between aids, with SDs the
setting's divided by the square root of two, so that the logit difference between any two aids
varies exactly as the two-arm setting's does. A contrast uses only the cases each reader read with
its two aids, a third each; the third aid's cases do not enter it. Its estimate is still the mean of
the readers' differences, and since every case is equally likely to fall to each aid, the mean given
the cases is the average over all the cases of their differences, so the case term of the variance
is Var(delta_c) over the number of cases, as in two arms. delta_c is estimated from the readers who
read case c with each of the two aids; a case read with either by fewer than two readers, which can
happen with a third of twenty readers, is left out of that estimate rather than given an infinite
sampling variance. The accuracy of the aid outside a contrast changes nothing in it, so the nulls and
effects below name only the two aids compared, the third set equal to A.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

SEED = 20261026
READER_SD, CASE_SD, MARGIN = 0.5, 1.0, 0.05
POWER_REPS, SIZE_REPS, CHUNK = 10000, 20000, 1000
ALPHA = 0.05
HOLM_FIRST = 0.05 / 4
INTERACTIONS = (("none", 0.0, 0.0), ("moderate", 0.25, 0.5), ("large", 0.25, 1.0))
GRID_READERS, GRID_CASES = (20, 30, 40), (20, 24, 32, 40)
PRIMARY_STRATA = 2
NI_NULLS = ((0.95, 0.90), (0.90, 0.85))           # (A, B) at a true difference of minus the margin
SUPERIORITY_NULLS = ((0.95, 0.95), (0.90, 0.90))  # (A, B) at no difference
NI_POWER, SUPERIORITY_POWER = (0.95, 0.95), (0.90, 0.95)
STRATUM_READERS, STRATUM_CASES = (20, 30, 40), 10
STRATUM_NULLS = ((0.90, 0.90), (0.95, 0.95))
STRATUM_EFFECTS = ((0.80, 0.95), (0.85, 0.95))
GH_NODES = 81
PROCESSES = 4

ARMS = ("A", "B", "C")                            # registration alone, the exact rule alone, the two together
THREE_STRATA = 4
THREE_GRID = ((20, 48), (20, 60), (30, 48), (30, 60), (40, 48), (40, 60))
THREE_SUPERIORITY_POWER = ((0.90, 0.95), (0.85, 0.95))   # (A, C)
THREE_STRATUM_CASES = 12


def total_sd(reader_by_aid: float, case_by_aid: float) -> float:
    """SD of the summed random effects in one aid's logit."""
    return math.sqrt(READER_SD ** 2 + CASE_SD ** 2 + (reader_by_aid ** 2 + case_by_aid ** 2) / 4.0)


def marginal(b0: float, tau: float) -> float:
    """Accuracy over readers and cases of an aid with intercept b0, by Gauss-Hermite quadrature."""
    from scipy import special
    x, w = np.polynomial.hermite_e.hermegauss(GH_NODES)
    return float((w * special.expit(b0 + tau * x)).sum() / math.sqrt(2.0 * math.pi))


def calibrate(p: float, tau: float) -> float:
    from scipy import optimize
    return optimize.brentq(lambda b: marginal(b, tau) - p, -15.0, 20.0, xtol=1e-12)


def allocate(rng, reps: int, readers: int, cases: int, strata: int) -> np.ndarray:
    """True where a case goes to B: half of each stratum's cases for every reader."""
    per = cases // strata
    keys = rng.random((reps, readers, strata, per))
    ranks = keys.argsort(-1).argsort(-1)
    return (ranks < per // 2).reshape(reps, readers, cases)


def draw(rng, reps: int, readers: int, cases: int, p_a: float, p_b: float, interaction: Tuple[float, float],
         strata: int) -> Tuple[np.ndarray, np.ndarray]:
    """Simulated studies: whether each answer is right, and whether its case went to B, each
    (reps, readers, cases)."""
    from scipy import special
    ra, ca = interaction
    tau = total_sd(ra, ca)
    b_a, b_b = calibrate(p_a, tau), calibrate(p_b, tau)
    u = READER_SD * rng.standard_normal((reps, readers, 1))
    v = ra * rng.standard_normal((reps, readers, 1))
    c = CASE_SD * rng.standard_normal((reps, 1, cases))
    g = ca * rng.standard_normal((reps, 1, cases))
    on_b = allocate(rng, reps, readers, cases, strata)
    logit = np.where(on_b, b_b, b_a) + u + c + np.where(on_b, 0.5, -0.5) * (v + g)
    return rng.random((reps, readers, cases)) < special.expit(logit), on_b


def analyse(right: np.ndarray, on_b: np.ndarray) -> Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """For each simulated study: the estimate, its variance and degrees of freedom, under the
    primary analysis (readers and cases random) and the t interval over readers (cases fixed)."""
    _, r, c = right.shape
    y = right.astype(float)
    n_b = on_b.sum(2)
    d = (y * on_b).sum(2) / n_b - (y * ~on_b).sum(2) / (c - n_b)
    m = d.mean(1)
    v_readers = d.var(1, ddof=1) / r
    nb_c = on_b.sum(1)
    na_c = r - nb_c
    with np.errstate(divide="ignore", invalid="ignore"):
        p_b = (y * on_b).sum(1) / nb_c
        p_a = (y * ~on_b).sum(1) / na_c
        noise_c = p_b * (1 - p_b) / (nb_c - 1) + p_a * (1 - p_a) / (na_c - 1)
    s2 = np.nanvar(p_b - p_a, axis=1, ddof=1)
    noise = np.nanmean(noise_c, axis=1)
    keep = s2 > noise
    v_cases = np.where(keep, s2 - noise, 0.0) / c
    total = v_readers + v_cases
    df_noise = c * (r - 2)
    den = np.where(keep, v_readers ** 2 / (r - 1) + (s2 / c) ** 2 / (c - 1) + (noise / c) ** 2 / df_noise,
                   v_readers ** 2 / (r - 1))
    with np.errstate(divide="ignore", invalid="ignore"):
        df = np.where(den > 0, total ** 2 / den, float(r - 1))
    return {"random": (m, total, df), "t_interval": (m, v_readers, np.full(m.shape, float(r - 1)))}


def pivots(rng, reps: int, readers: int, cases: int, p_a: float, p_b: float, interaction, strata: int):
    """Every simulated study's estimate, standard error and degrees of freedom under both analyses,
    in chunks so that a large design never holds every study at once."""
    parts = {"random": [], "t_interval": []}
    done = 0
    while done < reps:
        n = min(CHUNK, reps - done)
        res = analyse(*draw(rng, n, readers, cases, p_a, p_b, interaction, strata))
        for k, (m, var, df) in res.items():
            parts[k].append(np.stack([m, np.sqrt(var), df]))
        done += n
    return {k: np.concatenate(v, axis=1) for k, v in parts.items()}


def t_crit(df: np.ndarray, alpha: float) -> np.ndarray:
    from scipy import stats
    return stats.t.ppf(1.0 - alpha / 2.0, df)


def pivot_quantile(m, se, truth: float, q: float, two_sided: bool) -> float:
    """The q quantile of (estimate - truth) / se, or of its absolute value; a study with no spread
    at all (se 0) counts as an infinite pivot in the direction of its error, or as none if exact."""
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(se > 0, (m - truth) / se, np.sign(m - truth) * np.inf)
    t = np.nan_to_num(t, nan=0.0)
    return float(np.quantile(np.abs(t) if two_sided else t, q))


def cell_rng(*key: int):
    return np.random.default_rng(np.random.SeedSequence([SEED, *key]))


def grid_cell(args) -> dict:
    """One design: nominal sizes, calibrated critical values, and power at both."""
    i, j, readers, cases, size_reps, power_reps = args
    row = {"readers": readers, "primary_cases": cases, "decisions": readers * cases, "size": {}, "power": {}}
    k_ni, k_sup = 0.0, 0.0
    for k, (iname, ra, ca) in enumerate(INTERACTIONS):
        for q, (p_a, p_b) in enumerate(NI_NULLS + SUPERIORITY_NULLS):
            is_ni = q < len(NI_NULLS)
            truth = (p_b - p_a)
            bound = -MARGIN if is_ni else 0.0
            piv = pivots(cell_rng(0, i, j, k, q), size_reps, readers, cases, p_a, p_b, (ra, ca), PRIMARY_STRATA)
            key = "%s_%g_%g_%s" % ("noninferiority" if is_ni else "superiority", p_a, p_b, iname)
            nominal = {}
            for a, (m, se, df) in piv.items():
                nominal[a] = float(np.mean(m - t_crit(df, ALPHA) * se > bound))
            m, se, _ = piv["random"]
            quant = pivot_quantile(m, se, truth, 1.0 - ALPHA / 2.0, two_sided=False)
            row["size"][key] = dict(nominal, pivot_975=quant)
            if is_ni:
                k_ni = max(k_ni, quant)
            else:
                k_sup = max(k_sup, quant)
    row["critical_noninferiority"], row["critical_superiority"] = k_ni, k_sup
    for k, (iname, ra, ca) in enumerate(INTERACTIONS):
        for q, (claim, (p_a, p_b), crit, bound) in enumerate((("noninferiority", NI_POWER, k_ni, -MARGIN),
                                                              ("superiority", SUPERIORITY_POWER, k_sup, 0.0))):
            piv = pivots(cell_rng(1, i, j, k, q), power_reps, readers, cases, p_a, p_b, (ra, ca), PRIMARY_STRATA)
            m, se, df = piv["random"]
            mt, set_, dft = piv["t_interval"]
            row["power"]["%s_%g_%g_%s" % (claim, p_a, p_b, iname)] = {
                "calibrated": float(np.mean(m - crit * se > bound)),
                "random_nominal": float(np.mean(m - t_crit(df, ALPHA) * se > bound)),
                "t_interval_nominal": float(np.mean(mt - t_crit(dft, ALPHA) * set_ > bound))}
    return row


def stratum_cell(args) -> dict:
    """One stratum's two-sided comparison at a number of readers: critical values calibrated at no
    difference, and power at each effect, at 5% and at Holm's first level."""
    i, readers, size_reps, power_reps = args
    row = {"readers": readers, "cases_in_stratum": STRATUM_CASES, "size": {}, "power": {}}
    crit = {ALPHA: 0.0, HOLM_FIRST: 0.0}
    for k, (iname, ra, ca) in enumerate(INTERACTIONS):
        for q, (p_a, p_b) in enumerate(STRATUM_NULLS):
            piv = pivots(cell_rng(2, i, k, q), size_reps, readers, STRATUM_CASES, p_a, p_b, (ra, ca), 1)
            entry = {}
            for a in (ALPHA, HOLM_FIRST):
                for name, (m, se, df) in piv.items():
                    entry["%s_nominal_at_%g" % (name, a)] = float(np.mean(np.abs(m) > t_crit(df, a) * se))
                m, se, _ = piv["random"]
                quant = pivot_quantile(m, se, 0.0, 1.0 - a, two_sided=True)
                entry["pivot_abs_at_%g" % a] = quant
                crit[a] = max(crit[a], quant)
            row["size"]["%g_%g_%s" % (p_a, p_b, iname)] = entry
    row["critical_at_5"], row["critical_at_holm_first"] = crit[ALPHA], crit[HOLM_FIRST]
    for k, (iname, ra, ca) in enumerate(INTERACTIONS):
        for q, (p_a, p_b) in enumerate(STRATUM_EFFECTS):
            piv = pivots(cell_rng(3, i, k, q), power_reps, readers, STRATUM_CASES, p_a, p_b, (ra, ca), 1)
            m, se, df = piv["random"]
            mt, set_, dft = piv["t_interval"]
            entry = {}
            for a, tag in ((ALPHA, "at_5"), (HOLM_FIRST, "at_holm_first")):
                entry["calibrated_" + tag] = float(np.mean(m > crit[a] * se))
                entry["t_interval_nominal_" + tag] = float(np.mean(mt > t_crit(dft, a) * set_))
            row["power"]["%g_%g_%s" % (p_a, p_b, iname)] = entry
    return row


def run(outdir: Optional[str] = None, power_reps: Optional[int] = None, size_reps: Optional[int] = None,
        processes: int = PROCESSES, readers: Sequence[int] = GRID_READERS, cases: Sequence[int] = GRID_CASES,
        stratum_readers: Sequence[int] = STRATUM_READERS) -> dict:
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    power_reps = power_reps or POWER_REPS
    size_reps = size_reps or SIZE_REPS
    grid_jobs = [(GRID_READERS.index(s), GRID_CASES.index(m), s, m, size_reps, power_reps)
                 for s in readers for m in cases]
    stratum_jobs = [(STRATUM_READERS.index(s), s, size_reps, power_reps) for s in stratum_readers]
    with ProcessPoolExecutor(max_workers=processes) as ex:
        grid = list(ex.map(grid_cell, grid_jobs))
        strata = list(ex.map(stratum_cell, stratum_jobs))
    for row in grid + strata:
        print(json.dumps(row, sort_keys=True))
    out = {"study": "power and size of the randomized reader study", "seed": SEED,
           "reader_sd_logit": READER_SD, "case_sd_logit": CASE_SD,
           "interactions": {n: {"reader_by_aid_sd_logit": ra, "case_by_aid_sd_logit": ca} for n, ra, ca in INTERACTIONS},
           "power_reps": power_reps, "size_reps": size_reps, "margin": MARGIN, "alpha": ALPHA,
           "holm_first_alpha": HOLM_FIRST, "primary_strata": PRIMARY_STRATA, "gh_nodes": GH_NODES,
           "ni_nulls": [list(p) for p in NI_NULLS], "superiority_nulls": [list(p) for p in SUPERIORITY_NULLS],
           "analyses": {"random": "law of total variance: readers' variance given the cases plus the variance of "
                                  "the cases' differences, Satterthwaite df; critical value calibrated",
                        "t_interval": "t interval over readers' differences, R - 1 df, nominal (cases fixed)"},
           "grid": grid, "strata": strata, "seconds": round(time.time() - t0, 1)}
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "study_power.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return out


def total_sd_arms(reader_by_aid: float, case_by_aid: float) -> float:
    """SD of the summed random effects in one aid's logit when each aid has its own interaction terms."""
    return math.sqrt(READER_SD ** 2 + CASE_SD ** 2 + (reader_by_aid ** 2 + case_by_aid ** 2) / 2.0)


def allocate_arms(rng, reps: int, readers: int, cases: int, strata: int, arms: int = 3) -> np.ndarray:
    """Each case's aid, 0 to arms - 1: an equal share of each stratum's cases to each aid, for every reader."""
    per = cases // strata
    if per * strata != cases or per % arms:
        raise ValueError("%d cases in %d strata do not split equally among %d aids" % (cases, strata, arms))
    keys = rng.random((reps, readers, strata, per))
    ranks = keys.argsort(-1).argsort(-1)
    return (ranks // (per // arms)).reshape(reps, readers, cases)


def draw_arms(rng, reps: int, readers: int, cases: int, accuracies: Sequence[float],
              interaction: Tuple[float, float], strata: int) -> Tuple[np.ndarray, np.ndarray]:
    """Simulated studies with one aid per entry of accuracies: whether each answer is right, and each
    case's aid, each (reps, readers, cases)."""
    from scipy import special
    ra, ca = interaction
    k = len(accuracies)
    tau = total_sd_arms(ra, ca)
    b = np.array([calibrate(p, tau) for p in accuracies])
    u = READER_SD * rng.standard_normal((reps, readers, 1))
    c = CASE_SD * rng.standard_normal((reps, 1, cases))
    v = ra / math.sqrt(2.0) * rng.standard_normal((reps, readers, 1, k))
    g = ca / math.sqrt(2.0) * rng.standard_normal((reps, 1, cases, k))
    arm = allocate_arms(rng, reps, readers, cases, strata, k)
    by_aid = np.take_along_axis(v + g, arm[..., None], -1)[..., 0]
    logit = b[arm] + u + c + by_aid
    return rng.random((reps, readers, cases)) < special.expit(logit), arm


def analyse_pair(right: np.ndarray, on_x: np.ndarray, on_y: np.ndarray):
    """The two analyses of `analyse` for the contrast y minus x, where each reader read only some cases
    with x and some with y and the rest with other aids, which do not enter."""
    _, r, c = right.shape
    y = right.astype(float)
    d = (y * on_y).sum(2) / on_y.sum(2) - (y * on_x).sum(2) / on_x.sum(2)
    m = d.mean(1)
    v_readers = d.var(1, ddof=1) / r
    ny_c, nx_c = on_y.sum(1), on_x.sum(1)
    valid = (ny_c >= 2) & (nx_c >= 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        p_y = np.where(valid, (y * on_y).sum(1) / ny_c, np.nan)
        p_x = np.where(valid, (y * on_x).sum(1) / nx_c, np.nan)
        noise_c = p_y * (1 - p_y) / (ny_c - 1) + p_x * (1 - p_x) / (nx_c - 1)
        s2 = np.nanvar(p_y - p_x, axis=1, ddof=1)
        noise = np.nanmean(noise_c, axis=1)
    n_valid = valid.sum(1)
    keep = (n_valid >= 2) & (s2 > noise)
    v_cases = np.where(keep, s2 - noise, 0.0) / c
    total = v_readers + v_cases
    df_noise = np.where(valid, ny_c + nx_c - 2, 0).sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        den = np.where(keep, v_readers ** 2 / (r - 1) + (s2 / c) ** 2 / (n_valid - 1) + (noise / c) ** 2 / df_noise,
                       v_readers ** 2 / (r - 1))
        df = np.where(den > 0, total ** 2 / den, float(r - 1))
    return {"random": (m, total, df), "t_interval": (m, v_readers, np.full(m.shape, float(r - 1)))}


def pivots_three(rng, reps: int, readers: int, cases: int, p_a: float, p_c: float, interaction, strata: int):
    """`pivots` for the contrast C minus A in the three-arm design, B as accurate as A."""
    parts = {"random": [], "t_interval": []}
    done = 0
    while done < reps:
        n = min(CHUNK, reps - done)
        right, arm = draw_arms(rng, n, readers, cases, (p_a, p_a, p_c), interaction, strata)
        for k, (m, var, df) in analyse_pair(right, arm == 0, arm == 2).items():
            parts[k].append(np.stack([m, np.sqrt(var), df]))
        done += n
    return {k: np.concatenate(v, axis=1) for k, v in parts.items()}


def three_grid_cell(args) -> dict:
    """One three-arm design: nominal sizes, calibrated critical values, and power at both, for C minus A."""
    i, readers, cases, size_reps, power_reps = args
    row = {"readers": readers, "cases": cases, "decisions": readers * cases,
           "contrast_cases_per_reader": 2 * cases // len(ARMS), "size": {}, "power": {}}
    k_ni, k_sup = 0.0, 0.0
    for k, (iname, ra, ca) in enumerate(INTERACTIONS):
        for q, (p_a, p_c) in enumerate(NI_NULLS + SUPERIORITY_NULLS):
            is_ni = q < len(NI_NULLS)
            bound = -MARGIN if is_ni else 0.0
            piv = pivots_three(cell_rng(10, i, k, q), size_reps, readers, cases, p_a, p_c, (ra, ca), THREE_STRATA)
            key = "%s_%g_%g_%s" % ("noninferiority" if is_ni else "superiority", p_a, p_c, iname)
            nominal = {a: float(np.mean(m - t_crit(df, ALPHA) * se > bound)) for a, (m, se, df) in piv.items()}
            m, se, _ = piv["random"]
            quant = pivot_quantile(m, se, p_c - p_a, 1.0 - ALPHA / 2.0, two_sided=False)
            row["size"][key] = dict(nominal, pivot_975=quant)
            if is_ni:
                k_ni = max(k_ni, quant)
            else:
                k_sup = max(k_sup, quant)
    row["critical_noninferiority"], row["critical_superiority"] = k_ni, k_sup
    claims = [("noninferiority", NI_POWER, k_ni, -MARGIN)]
    claims += [("superiority", p, k_sup, 0.0) for p in THREE_SUPERIORITY_POWER]
    for k, (iname, ra, ca) in enumerate(INTERACTIONS):
        for q, (claim, (p_a, p_c), crit, bound) in enumerate(claims):
            piv = pivots_three(cell_rng(11, i, k, q), power_reps, readers, cases, p_a, p_c, (ra, ca), THREE_STRATA)
            m, se, df = piv["random"]
            mt, set_, dft = piv["t_interval"]
            row["power"]["%s_%g_%g_%s" % (claim, p_a, p_c, iname)] = {
                "calibrated": float(np.mean(m - crit * se > bound)),
                "random_nominal": float(np.mean(m - t_crit(df, ALPHA) * se > bound)),
                "t_interval_nominal": float(np.mean(mt - t_crit(dft, ALPHA) * set_ > bound))}
    return row


def three_stratum_cell(args) -> dict:
    """One stratum of the three-arm design, a third of its cases to each aid: one two-sided contrast,
    critical values calibrated at no difference, and power at each effect, at 5% and at Holm's first level."""
    i, readers, size_reps, power_reps = args
    row = {"readers": readers, "cases_in_stratum": THREE_STRATUM_CASES,
           "cases_per_aid": THREE_STRATUM_CASES // len(ARMS), "size": {}, "power": {}}
    crit = {ALPHA: 0.0, HOLM_FIRST: 0.0}
    for k, (iname, ra, ca) in enumerate(INTERACTIONS):
        for q, (p_a, p_c) in enumerate(STRATUM_NULLS):
            piv = pivots_three(cell_rng(12, i, k, q), size_reps, readers, THREE_STRATUM_CASES, p_a, p_c, (ra, ca), 1)
            entry = {}
            for a in (ALPHA, HOLM_FIRST):
                for name, (m, se, df) in piv.items():
                    entry["%s_nominal_at_%g" % (name, a)] = float(np.mean(np.abs(m) > t_crit(df, a) * se))
                m, se, _ = piv["random"]
                quant = pivot_quantile(m, se, 0.0, 1.0 - a, two_sided=True)
                entry["pivot_abs_at_%g" % a] = quant
                crit[a] = max(crit[a], quant)
            row["size"]["%g_%g_%s" % (p_a, p_c, iname)] = entry
    row["critical_at_5"], row["critical_at_holm_first"] = crit[ALPHA], crit[HOLM_FIRST]
    for k, (iname, ra, ca) in enumerate(INTERACTIONS):
        for q, (p_a, p_c) in enumerate(STRATUM_EFFECTS):
            piv = pivots_three(cell_rng(13, i, k, q), power_reps, readers, THREE_STRATUM_CASES, p_a, p_c, (ra, ca), 1)
            m, se, df = piv["random"]
            mt, set_, dft = piv["t_interval"]
            entry = {}
            for a, tag in ((ALPHA, "at_5"), (HOLM_FIRST, "at_holm_first")):
                entry["calibrated_" + tag] = float(np.mean(m > crit[a] * se))
                entry["t_interval_nominal_" + tag] = float(np.mean(mt > t_crit(dft, a) * set_))
            row["power"]["%g_%g_%s" % (p_a, p_c, iname)] = entry
    return row


def run_three(outdir: Optional[str] = None, power_reps: Optional[int] = None, size_reps: Optional[int] = None,
              processes: int = PROCESSES, designs: Sequence[Tuple[int, int]] = THREE_GRID,
              stratum_readers: Sequence[int] = STRATUM_READERS) -> dict:
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    power_reps = power_reps or POWER_REPS
    size_reps = size_reps or SIZE_REPS
    grid_jobs = [(THREE_GRID.index(d), d[0], d[1], size_reps, power_reps) for d in designs]
    stratum_jobs = [(STRATUM_READERS.index(s), s, size_reps, power_reps) for s in stratum_readers]
    with ProcessPoolExecutor(max_workers=processes) as ex:
        grid = list(ex.map(three_grid_cell, grid_jobs))
        strata = list(ex.map(three_stratum_cell, stratum_jobs))
    for row in grid + strata:
        print(json.dumps(row, sort_keys=True))
    out = {"study": "power and size of the three-arm randomized reader study, contrast C minus A",
           "arms": {"A": "registration alone", "B": "the exact rule alone", "C": "registration with the exact rule"},
           "seed": SEED, "reader_sd_logit": READER_SD, "case_sd_logit": CASE_SD,
           "interactions": {n: {"reader_by_aid_sd_logit": ra, "case_by_aid_sd_logit": ca} for n, ra, ca in INTERACTIONS},
           "interaction_per_aid": "independent between aids, each SD the setting's over sqrt(2), so any two aids' "
                                  "logit difference varies as the setting says",
           "power_reps": power_reps, "size_reps": size_reps, "margin": MARGIN, "alpha": ALPHA,
           "holm_first_alpha": HOLM_FIRST, "strata": THREE_STRATA, "gh_nodes": GH_NODES,
           "ni_nulls_a_c": [list(p) for p in NI_NULLS], "superiority_nulls_a_c": [list(p) for p in SUPERIORITY_NULLS],
           "analyses": {"random": "law of total variance over the contrast's two aids: readers' variance given the "
                                  "cases plus the variance of the cases' differences over all cases, Satterthwaite "
                                  "df; critical value calibrated",
                        "t_interval": "t interval over readers' differences, R - 1 df, nominal (cases fixed)"},
           "grid": grid, "stratum": strata, "seconds": round(time.time() - t0, 1)}
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "study_power_three_arms.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return out
