"""bordercall: name a vertebral border from the shape of the bone, on any corpus.

Run the commands in this order on a corpus you have not measured before.

    python run.py scheme    --labels LABELS                 # 1. is the identifier map right?
    python run.py selftest  --levels KNOWN.csv              # 2. does this copy still work?
    python run.py measure   --labels LABELS --out levels.csv
    python run.py phenotype --labels LABELS --out phenotype.csv
    python run.py border    --levels levels.csv --above T12 --below L1
    python run.py breakout  --levels levels.csv --phenotype phenotype.csv
    python run.py plot      --levels levels.csv --phenotype phenotype.csv

    python run.py all --labels LABELS --outdir out/         # 3-7 in one go
    python run.py panjabi                                    # both junctions from Panjabi's tables alone
    python run.py panjabi-corpus --levels levels.csv --phenotype phenotype.csv
    python run.py disagree --levels levels.csv --phenotype phenotype.csv --above T12 --below L1
    python run.py synth-corpus --out out/synth         # a made-up corpus to run the rest on
    python run.py panjabi-figures --json out/panjabi/panjabi_junction.json --outdir figures/junction
    python run.py neighbour --outdir out/neighbour          # name a vertebra from its neighbours alone
    python run.py neighbour-enumerate --arm flank --shard 0 --of 1 --out out/neighbour/shard0.json
    python run.py neighbour-more --outdir out/neighbour     # the field with the target in it, continued
    python run.py neighbour-figures --json out/neighbour/neighbour.json --outdir figures/neighbour
    python run.py identify --outdir out/identify               # which vertebrae a normal spine identifies best
    python run.py identify-figures --json out/identify/identify.json --outdir figures/identify
    python run.py exact --outdir out/exact                     # the generator's own Bayes rule, by enumeration
    python run.py exact-figures --json out/exact/exact.json --outdir figures/exact
    python run.py exact-supplement --outdir out/exact          # the checks the second review asked for
    python run.py exact-slide-figures --json out/exact/exact.json --outdir figures/exact-slides
    python run.py second-opinion --outdir out/whitepaper       # the exact rule beside a registration's answer
    python run.py study-power --outdir out/whitepaper          # readers and cases for the white paper's study
    python run.py study-power-three --outdir out/whitepaper    # the same for the three-arm design, C minus A
    python run.py whitepaper-checks --outdir out/whitepaper    # within-one best rule; anomalous by the count from C2

`scheme` and `selftest` are not optional. The first catches a corpus numbered differently
from this package's assumption, which produces finite, plausible, wrong numbers and raises
nothing. The second catches a copy of the code whose model has drifted from the published
one. Both take seconds; skipping them costs a re-run of everything downstream.

See README.md for the full walk-through and HANDOFF.md for the traps.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import phenotype as PH            # noqa: E402
import scheme as S                # noqa: E402
from border import Border, Corpus, out_of_fold  # noqa: E402

KNOWN = {"auc_adjacent": 0.988, "auc_whole": 0.998, "junction": 0.951}
TOL = 0.004
DEFAULT_REFERENCE = os.path.join(HERE, "reference", "panjabi_full_spine.csv")
# the fixture selftest checks against, shipped so the repo can verify itself anywhere
DEFAULT_FIXTURE = os.path.join(os.path.dirname(HERE), "testdata",
                               "ctspinopelvic1k_level_gradients.csv")


def cmd_scheme(a) -> int:
    return S.check(a.labels, n=a.n)


def cmd_measure(a) -> int:
    cmd = [sys.executable, os.path.join(HERE, "measure_levels.py"),
           "--labels", a.labels, "--out", a.out]
    if a.jobs:
        cmd += ["--jobs", str(a.jobs)]
    print("running: " + " ".join(cmd))
    return subprocess.call(cmd)


def cmd_phenotype(a) -> int:
    PH.run(a.labels, a.out, jobs=a.jobs)
    return 0


def cmd_border(a) -> int:
    c = Corpus.from_csv(a.levels, case_key=a.case_key)
    print("levels found: %s" % ", ".join(c.levels))
    print(Border(a.above, a.below).evaluate(c, folds=a.folds, seed=a.seed).report())
    return 0


def _accuracy_by_class(levels_csv, phenotype_csv, above, below, case_key="case",
                       folds=5, seed=0):
    """{class: (n, correct)} plus the per-case offsets, for the breakout and the plots."""
    c = Corpus.from_csv(levels_csv, case_key=case_key)
    b = Border(above, below)
    upper, _ = b.split(c.levels)
    X, groups, lv, _ = c.features()
    y = __import__("numpy").array([1 if l in upper else 0 for l in lv], int)
    s = out_of_fold(X, y, groups, folds=folds, seed=seed)
    order = {l: i for i, l in enumerate(c.levels)}
    per_case = defaultdict(dict)
    for g, l, p in zip(groups, lv, s >= 0.5):
        per_case[g][l] = bool(p)
    phen = PH.load(phenotype_csv)
    acc, offs = defaultdict(lambda: [0, 0]), defaultdict(lambda: defaultdict(int))
    for g, d in per_case.items():
        if above not in d or below not in d:
            continue
        # a case the file has no class for is unknown, never typical: the grid writes every
        # countable case with its phenotype empty where the ribs were not read
        k = phen.get(g, {}).get("phenotype") or "unknown"
        present = sorted(d, key=lambda l: order[l])
        seq = [d[l] for l in present]
        n = sum(seq)
        acc[k][0] += 1
        if seq[:n] != [True] * n or any(seq[n:]):
            offs[k]["ragged"] += 1
            continue
        o = n - sum(1 for l in present if l in upper)
        offs[k][o] += 1
        acc[k][1] += int(o == 0)
    return {k: tuple(v) for k, v in acc.items()}, offs, phen


def cmd_breakout(a) -> int:
    acc, offs, phen = _accuracy_by_class(a.levels, a.phenotype, a.above, a.below,
                                         a.case_key, a.folds, a.seed)
    print("border %s/%s, broken out by phenotype\n" % (a.above, a.below))
    print("  %-30s %7s %9s %10s" % ("class", "cases", "correct", "accuracy"))
    tot_n = tot_k = 0
    for k in PH.CLASS_ORDER + ["unknown"]:
        if k not in acc:
            continue
        n, ok = acc[k]
        tot_n += n
        tot_k += ok
        print("  %-30s %7d %9d %9.1f%%" % (PH.PRETTY.get(k, "No rib reading"), n, ok,
                                           100.0 * ok / n if n else float("nan")))
    if tot_n:
        print("  %-30s %7d %9d %9.1f%%" % ("ALL", tot_n, tot_k, 100.0 * tot_k / tot_n))
    print("\n  offsets, per class (0 = the border is where the labels put it)")
    for k in PH.CLASS_ORDER + ["unknown"]:
        if k in offs:
            d = ", ".join("%s:%d" % (x, offs[k][x])
                          for x in sorted(offs[k], key=lambda z: (isinstance(z, str), z)))
            print("    %-30s %s" % (PH.PRETTY.get(k, "No rib reading"), d))
    print("\n  A corpus average over classes of very different size hides the result.")
    print("  Read the per-class rows, and read a class of fewer than ~20 cases as")
    print("  'no failures seen' rather than as an accuracy.")
    return 0


def cmd_plot(a) -> int:
    import plots
    c = Corpus.from_csv(a.levels, case_key=a.case_key)
    ref = None if a.no_reference else (a.reference or DEFAULT_REFERENCE)
    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.join(a.outdir, "levels_%s" % a.measure)
    plots.plot_levels(c, a.measure, base, reference=ref, scale=a.scale,
                      withhold=not a.no_withhold)
    if a.phenotype:
        acc, _, phen = _accuracy_by_class(a.levels, a.phenotype, a.above, a.below,
                                          a.case_key, a.folds, a.seed)
        plots.plot_classes(c, a.measure, os.path.join(a.outdir, "classes_%s" % a.measure),
                           phen, reference=ref, accuracy=acc,
                           violin_min=a.violin_min, scale=a.scale,
                           withhold=not a.no_withhold)
    return 0


def cmd_sweep(a) -> int:
    import sweep
    return sweep.run(a.levels, a.phenotype, case_key=a.case_key, folds=a.folds,
                     seed=a.seed, min_class=a.min_class,
                     countable_only=not a.allow_uncountable)


def cmd_panjabi(a) -> int:
    import junction
    measures = [m.strip() for m in a.measures.split(",") if m.strip()]
    junction.run_synthetic(outdir=a.outdir, n_columns=a.n_columns, n_eval=a.n_eval,
                           measures=measures, within=a.within, profile=a.profile,
                           margin=a.margin, seed=a.seed, rho=a.rho, noise_mm=a.noise_mm,
                           scale_sd=a.scale_sd, r_between=a.r_between)
    return 0


def cmd_panjabi_corpus(a) -> int:
    import junction
    measures = [m.strip() for m in a.measures.split(",") if m.strip()]
    junction.run_corpus(a.levels, a.phenotype, outdir=a.outdir, n_columns=a.n_columns,
                        margin=a.margin, seed=a.seed, measures=measures, rho=a.rho,
                        noise_mm=a.noise_mm, scale_sd=a.scale_sd, r_between=a.r_between)
    return 0


def cmd_disagree(a) -> int:
    import disagree
    disagree.run(a.levels, a.phenotype, above=a.above, below=a.below, folds=a.folds,
                 seed=a.seed, case_key=a.case_key)
    return 0


def cmd_panjabi_figures(a) -> int:
    import junction_figures
    junction_figures.run(a.json, a.outdir)
    return 0


def cmd_synth_corpus(a) -> int:
    import synth_corpus
    synth_corpus.write(a.out, n=a.n, seed=a.seed)
    return 0


def cmd_covariance(a) -> int:
    """The between-measure covariance: what the literature does and does not supply.

    The generator draws each measure's departure from its published mean independently.
    Real vertebrae do not work that way -- a wide body tends to come with a deep one -- so
    independence hands the classifier more information than it would really have, and every
    accuracy at r = 0 is an upper bound. No published source gives the within-patient value
    (see the report), so it is swept rather than assumed, and the sweep's job is to show
    whether the conclusion survives the whole range.
    """
    import covariance as CV

    if a.from_json:
        CV.report_from_record(a.from_json)
        return 0

    grid = None
    if a.r_grid:
        grid = [float(x) for x in a.r_grid.replace(",", " ").split()]

    CV.report()
    if a.sweep:
        print("\n")
        CV.measure_set_sweep(r_grid=grid, out_json=a.out,
                             n_columns=a.n_columns, n_eval=a.n_eval)
    else:
        print("\nRe-run with --sweep to measure whether the conclusion depends on it,")
        print("or --from-json RECORD.json to re-report a sweep already recorded.")
    return 0


def cmd_enumerate(a) -> int:
    """Every subset, every r. Exhaustive is the right method at these counts, not a fallback.

    7.24 s per evaluation, measured, so the whole ground set of 7 measures is 127 subsets and
    about 3 hours of single-core work -- cheaper than reasoning about which subsets to try, and
    exact. HANDOFF.md has the Slurm array job and the crossover where this stops being true.
    """
    import covariance as CV

    if a.gather:
        CV.gather_shards(a.gather, out_json=a.out)
        return 0

    measures = ([x for x in a.measures.replace(",", " ").split()] if a.measures else None)
    grid = ([float(x) for x in a.r_grid.replace(",", " ").split()] if a.r_grid else None)
    CV.enumerate_subsets(measures=measures, min_k=a.min_k, r_grid=grid,
                         shard=a.shard, n_shards=a.n_shards,
                         n_columns=a.n_columns, n_eval=a.n_eval, out_json=a.out)
    return 0


def cmd_neighbour(a) -> int:
    import neighbour as NB
    grid = [float(x) for x in a.r_grid.split(",")] if a.r_grid else None
    NB.run(outdir=a.outdir, n_fit=a.n_fit, n_select=a.n_select, n_score=a.n_score,
           r_grid=grid, quick=a.quick)
    return 0


def cmd_neighbour_enumerate(a) -> int:
    import neighbour as NB
    if a.gather:
        NB.gather_subsets(a.gather, out_json=a.out)
        return 0
    NB.enumerate_subsets(arm=a.arm, shard=a.shard, n_shards=a.n_shards, n_fit=a.n_fit,
                         n_select=a.n_select, n_score=a.n_score, out_json=a.out, quick=a.quick)
    return 0


def cmd_neighbour_more(a) -> int:
    import neighbour_more as NM
    grid = [float(x) for x in a.r_grid.split(",")] if a.r_grid else None
    NM.run(outdir=a.outdir, n_fit=a.n_fit, n_select=a.n_select, n_score=a.n_score,
           r_grid=grid, quick=a.quick)
    return 0


def cmd_neighbour_figures(a) -> int:
    import neighbour_figures as NF
    NF.run(a.json, a.outdir, enumerate_json=a.enumerate_json, more_json=a.more_json)
    return 0


def cmd_identify(a) -> int:
    import identify as ID
    ID.run(outdir=a.outdir, n_fit=a.n_fit, n_select=a.n_select, n_score=a.n_score, quick=a.quick)
    return 0


def cmd_identify_figures(a) -> int:
    import identify_figures as IF
    IF.run(a.json, a.outdir)
    return 0


def cmd_exact(a) -> int:
    import exact as E
    if a.quick:
        E.run(a.outdir, n_score=60, widths=(1, 3, 9), n_worlds=2, identify_json=a.identify_json,
              processes=a.processes, quick=True, robust_columns=20)
    else:
        E.run(a.outdir, identify_json=a.identify_json, processes=a.processes)
    return 0


def cmd_exact_figures(a) -> int:
    import exact_figures as EF
    EF.run(a.json, a.outdir)
    return 0


def cmd_exact_slide_figures(a) -> int:
    import exact_slide_figures as XS
    XS.run(a.json, a.outdir, a.venue)
    return 0


def cmd_exact_supplement(a) -> int:
    import exact_supplement as ES
    if a.quick:
        ES.run(a.outdir, record_json=a.record_json, processes=a.processes, n_score=40, n_worlds=2, quick=True)
    else:
        ES.run(a.outdir, record_json=a.record_json, processes=a.processes)
    return 0


def cmd_second_opinion(a) -> int:
    import second_opinion as SO
    SO.run(a.outdir, record_json=a.record_json)
    return 0


def cmd_study_power(a) -> int:
    import study_power as SP
    SP.run(a.outdir, power_reps=a.power_reps, size_reps=a.size_reps)
    return 0


def cmd_study_power_three(a) -> int:
    import study_power as SP
    SP.run_three(a.outdir, power_reps=a.power_reps, size_reps=a.size_reps)
    return 0


def cmd_whitepaper_checks(a) -> int:
    import whitepaper_checks as WC
    WC.run(a.outdir, record_json=a.record_json, supplement_json=a.supplement_json)
    return 0


def cmd_selftest(a) -> int:
    c = Corpus.from_csv(a.levels)
    print("levels found: %s" % ", ".join(c.levels))
    r = Border("T12", "L1").evaluate(c)
    print(r.report())
    bad = []
    for key, want, got in (("auc_adjacent", KNOWN["auc_adjacent"], r.auc_adjacent),
                           ("auc_whole", KNOWN["auc_whole"], r.auc_whole),
                           ("junction", KNOWN["junction"], r.junction_accuracy)):
        d = abs(got - want)
        print("  %s %-13s want %.3f  got %.4f  (%+.4f)"
              % ("ok " if d <= TOL else "OFF", key, want, got, got - want))
        if d > TOL:
            bad.append(key)
    if bad:
        print("\nSELFTEST FAILED on %s. The model or the features have changed; do not"
              % ", ".join(bad))
        print("trust results from this copy until the difference is explained.")
        return 1
    print("\nselftest passed: this copy reproduces the published CTSpinoPelvic1K numbers.")
    return 0


def cmd_all(a) -> int:
    os.makedirs(a.outdir, exist_ok=True)
    lv = os.path.join(a.outdir, "levels.csv")
    ph = os.path.join(a.outdir, "phenotype.csv")
    if S.check(a.labels, n=3):
        print("\nstopping: fix scheme.py first.")
        return 1
    rc = cmd_measure(argparse.Namespace(labels=a.labels, out=lv, jobs=a.jobs))
    if rc:
        return rc
    PH.run(a.labels, ph, jobs=a.jobs)
    cmd_border(argparse.Namespace(levels=lv, above=a.above, below=a.below, folds=5,
                                  seed=0, case_key="case"))
    cmd_breakout(argparse.Namespace(levels=lv, phenotype=ph, above=a.above, below=a.below,
                                    folds=5, seed=0, case_key="case"))
    for m in a.measures.split(","):
        cmd_plot(argparse.Namespace(levels=lv, phenotype=ph, measure=m.strip(),
                                    outdir=a.outdir, reference=a.reference,
                                    no_reference=a.no_reference, above=a.above,
                                    below=a.below, folds=5, seed=0, case_key="case",
                                    violin_min=40, scale=1.0, no_withhold=False))
    print("\neverything in %s" % a.outdir)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scheme", help="check the identifier map against the volumes")
    p.add_argument("--labels", required=True)
    p.add_argument("--n", type=int, default=3)
    p.set_defaults(fn=cmd_scheme)

    p = sub.add_parser("measure", help="label volumes -> wide per-level table")
    p.add_argument("--labels", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--jobs", type=int, default=0)
    p.set_defaults(fn=cmd_measure)

    p = sub.add_parser("phenotype", help="label volumes -> per-case phenotype")
    p.add_argument("--labels", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--jobs", type=int, default=0)
    p.set_defaults(fn=cmd_phenotype)

    p = sub.add_parser("border", help="can the shape name this border?")
    p.add_argument("--levels", required=True)
    p.add_argument("--above", default="T12")
    p.add_argument("--below", default="L1")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--case_key", default="case")
    p.set_defaults(fn=cmd_border)

    p = sub.add_parser("breakout", help="the border, per phenotype")
    p.add_argument("--levels", required=True)
    p.add_argument("--phenotype", required=True)
    p.add_argument("--above", default="T12")
    p.add_argument("--below", default="L1")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--case_key", default="case")
    p.set_defaults(fn=cmd_breakout)

    p = sub.add_parser("plot", help="conference figures, PDF and PNG")
    p.add_argument("--levels", required=True)
    p.add_argument("--phenotype", default=None)
    p.add_argument("--measure", default="endplate",
                   choices=["endplate", "h_ant", "h_post", "canal_w", "tp_span"])
    p.add_argument("--outdir", default="figures")
    p.add_argument("--reference", default=None)
    p.add_argument("--no-reference", action="store_true")
    p.add_argument("--above", default="T12")
    p.add_argument("--below", default="L1")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--case_key", default="case")
    p.add_argument("--violin-min", type=int, default=40)
    p.add_argument("--scale", type=float, default=1.0,
                   help="font scale; 1.3 for a poster")
    p.add_argument("--no-withhold", action="store_true",
                   help="draw the last lumbar level for end-plate and pedicle width, "
                        "which the body cut contaminates there")
    p.set_defaults(fn=cmd_plot)

    p = sub.add_parser("sweep", help="which border is most robust in anomalous spines?")
    p.add_argument("--levels", required=True)
    p.add_argument("--phenotype", required=True)
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--case_key", default="case")
    p.add_argument("--min-class", type=int, default=10,
                   help="an anomalous class under this many cases is not ranked")
    p.add_argument("--allow-uncountable", action="store_true",
                   help="score records with no C2; their ground truth is not a count")
    p.set_defaults(fn=cmd_sweep)

    def synth_args(p):
        p.add_argument("--n-columns", type=int, default=2000, dest="n_columns",
                       help="synthetic columns the local rule is fitted on")
        p.add_argument("--margin", type=float, default=0.0,
                       help="abstain when the best cut beats the runner-up by less (log-likelihood)")
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--rho", type=float, default=0.5, help="share of a measure's spread a column keeps across levels")
        p.add_argument("--noise-mm", type=float, default=1.0, dest="noise_mm", help="measurement noise, mm")
        p.add_argument("--scale-sd", type=float, default=0.07, dest="scale_sd", help="patient size spread, log")
        p.add_argument("--r-between", type=float, default=0.0, dest="r_between",
                       help="correlation between the measures' patient offsets. 0.0 is "
                            "the OPTIMISTIC end, not a neutral default: nothing published "
                            "supplies the real value, so sweep it (run.py covariance)")
        p.add_argument("--outdir", default=None, help="write the tables as JSON here")

    p = sub.add_parser("panjabi", help="name both junctions from Panjabi's tables on synthetic columns")
    p.add_argument("--measures", default=",".join(["endplate", "h_post", "canal_w"]),
                   help="of endplate, h_post, canal_w, canal_ap, pedicle; a CT mask gives the first three or four")
    p.add_argument("--n-eval", type=int, default=500, dest="n_eval", help="windows scored per phenotype")
    p.add_argument("--within", action="store_true", help="local rule: add the within-vertebra ratios")
    p.add_argument("--profile", action="store_true", help="local rule: add the level over its window median")
    synth_args(p)
    p.set_defaults(fn=cmd_panjabi)

    p = sub.add_parser("panjabi-corpus", help="the Panjabi models on a measured corpus counted from C2, both junctions")
    p.add_argument("--levels", required=True, help="measure's levels.csv")
    p.add_argument("--phenotype", required=True, help="phenotype.csv with countable per case")
    p.add_argument("--measures", default=",".join(["endplate", "h_post", "canal_w", "canal_ap"]),
                   help="of endplate, h_post, canal_w, canal_ap; a measure the table lacks is dropped")
    synth_args(p)
    p.set_defaults(fn=cmd_panjabi_corpus)

    p = sub.add_parser("disagree", help="where the shape disagrees with the name: the count, the ribs, the circular arm")
    p.add_argument("--levels", required=True)
    p.add_argument("--phenotype", required=True, help="phenotype.csv with countable, phenotype and the rib-bearing names")
    p.add_argument("--above", default="T12")
    p.add_argument("--below", default="L1")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--case_key", default="case")
    p.set_defaults(fn=cmd_disagree)

    p = sub.add_parser("panjabi-figures", help="the junction predictor's figures from a panjabi run's JSON")
    p.add_argument("--json", required=True, help="panjabi_junction.json")
    p.add_argument("--outdir", default="figures/junction")
    p.set_defaults(fn=cmd_panjabi_figures)

    p = sub.add_parser("synth-corpus", help="a made-up corpus in the grid job's layout, to run every command on")
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(fn=cmd_synth_corpus)

    p = sub.add_parser("covariance",
                       help="can the literature supply the between-measure covariance, and "
                            "does the answer change what we conclude?")
    p.add_argument("--sweep", action="store_true",
                   help="also run the 7-against-3 measure-set sweep over the whole r grid "
                        "(a few minutes; synthetic columns only, no corpus is read)")
    p.add_argument("--out", default=None, help="write the sweep's JSON here")
    p.add_argument("--from-json", default=None, dest="from_json",
                   help="re-report the partial identification from a recorded sweep "
                        "instead of running one; costs nothing and is reproducible")
    p.add_argument("--r-grid", default=None, dest="r_grid",
                   help="comma-separated r values to sweep, e.g. "
                        "0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9. A finer grid narrows the "
                        "L*h/2 term the command reports, but refining is NOT a reliable "
                        "check on its own -- see the note in covariance.py")
    p.add_argument("--n-columns", type=int, default=600, dest="n_columns")
    p.add_argument("--n-eval", type=int, default=400, dest="n_eval")
    p.set_defaults(fn=cmd_covariance)

    p = sub.add_parser("enumerate",
                       help="score EVERY subset of the measures at every r: the exact answer, "
                            "and the ground truth any budget-allocation procedure must be "
                            "tested against")
    p.add_argument("--measures", default=None,
                   help="comma-separated ground set; defaults to the 7 SPINEPS-measurable")
    p.add_argument("--min-k", type=int, default=1, dest="min_k")
    p.add_argument("--r-grid", default=None, dest="r_grid")
    p.add_argument("--shard", type=int, default=0,
                   help="this task's index, for a Slurm array job")
    p.add_argument("--of", type=int, default=1, dest="n_shards",
                   help="how many shards in total")
    p.add_argument("--n-columns", type=int, default=600, dest="n_columns")
    p.add_argument("--n-eval", type=int, default=400, dest="n_eval")
    p.add_argument("--out", default=None, help="write this shard's JSON here")
    p.add_argument("--gather", nargs="+", default=None,
                   help="instead of scoring, merge these shard JSONs and rank the subsets")
    p.set_defaults(fn=cmd_enumerate)

    p = sub.add_parser("neighbour",
                       help="name a vertebra from its neighbours alone, on synthetic columns: "
                            "solutions A to F, three projection regimes, six phenotypes, the "
                            "r sweep and the latency (docs/NEIGHBOUR_IDENTITY_STUDY.md)")
    p.add_argument("--outdir", default=None, help="write neighbour.json and models.json here")
    p.add_argument("--n-fit", type=int, default=300, dest="n_fit", help="typical columns fitted on")
    p.add_argument("--n-select", type=int, default=150, dest="n_select", help="columns per phenotype thresholds are chosen on")
    p.add_argument("--n-score", type=int, default=200, dest="n_score", help="columns per phenotype scored")
    p.add_argument("--r-grid", default=None, dest="r_grid", help="comma-separated r values for the sweep")
    p.add_argument("--quick", action="store_true", help="a small run to check the command")
    p.set_defaults(fn=cmd_neighbour)

    p = sub.add_parser("neighbour-enumerate",
                       help="solution D: every subset of the seven measures on one arm, chosen on "
                            "one seed and scored on another; shard with --shard/--of, then --gather")
    p.add_argument("--arm", default="flank", choices=list(["below1", "above1", "flank", "flank2", "with_target"]))
    p.add_argument("--shard", type=int, default=0)
    p.add_argument("--of", type=int, default=1, dest="n_shards")
    p.add_argument("--n-fit", type=int, default=300, dest="n_fit")
    p.add_argument("--n-select", type=int, default=150, dest="n_select")
    p.add_argument("--n-score", type=int, default=200, dest="n_score")
    p.add_argument("--out", default=None, help="this shard's JSON, or the gathered JSON")
    p.add_argument("--gather", nargs="+", default=None, help="merge these shard JSONs and rank")
    p.add_argument("--quick", action="store_true")
    p.set_defaults(fn=cmd_neighbour_enumerate)

    p = sub.add_parser("neighbour-more",
                       help="the series continued: the field decoded with the target in it, a nonlinear "
                            "classifier, the size of the fit; writes neighbour_more.json")
    p.add_argument("--outdir", default=None, help="write neighbour_more.json here")
    p.add_argument("--n-fit", type=int, default=300, dest="n_fit", help="typical columns fitted on")
    p.add_argument("--n-select", type=int, default=150, dest="n_select", help="columns per phenotype the width is chosen on")
    p.add_argument("--n-score", type=int, default=200, dest="n_score", help="columns per phenotype scored")
    p.add_argument("--r-grid", default=None, dest="r_grid", help="comma-separated r values for the sweep")
    p.add_argument("--quick", action="store_true", help="a small run to check the command")
    p.set_defaults(fn=cmd_neighbour_more)

    p = sub.add_parser("neighbour-figures", help="the neighbour study's figures from its recorded JSON")
    p.add_argument("--json", required=True, help="neighbour.json")
    p.add_argument("--more-json", default=None, dest="more_json", help="neighbour_more.json, for the field figure")
    p.add_argument("--enumerate-json", default=None, dest="enumerate_json", help="the gathered enumeration JSON")
    p.add_argument("--outdir", default="figures/neighbour")
    p.set_defaults(fn=cmd_neighbour_figures)

    p = sub.add_parser("identify",
                       help="which vertebrae of a normal spine can be identified best, and by what: "
                            "Kunkel 2010's frame, the closed-form isolation of every level, the classifier "
                            "level by level at every width, abstention, the size, the unidentified r; "
                            "typical columns only; writes identify.json")
    p.add_argument("--outdir", default=None, help="write identify.json here")
    p.add_argument("--n-fit", type=int, default=1000, dest="n_fit", help="typical columns fitted on")
    p.add_argument("--n-select", type=int, default=500, dest="n_select", help="typical columns the confidence thresholds are chosen on")
    p.add_argument("--n-score", type=int, default=1000, dest="n_score", help="typical columns scored")
    p.add_argument("--quick", action="store_true", help="a small run to check the command")
    p.set_defaults(fn=cmd_identify)

    p = sub.add_parser("identify-figures", help="the identifiability study's figures from its recorded JSON")
    p.add_argument("--json", required=True, help="identify.json")
    p.add_argument("--outdir", default="figures/identify")
    p.set_defaults(fn=cmd_identify_figures)

    p = sub.add_parser("exact",
                       help="name a run of 1 to 22 consecutive vertebrae with the generator's own Bayes rule, "
                            "every place enumerated: the ceiling for any formula or network, the selective "
                            "guarantee, the coarse claims (which border a body is below), all 127 measure "
                            "subsets, and what survives a wrong table or generator; writes exact.json")
    p.add_argument("--outdir", default=None, help="write exact.json here")
    p.add_argument("--identify-json", default=os.path.join(HERE, "..", "records", "identify-2026-10-26", "identify.json"),
                   dest="identify_json", help="the identifiability study's record, for its fitted classifiers")
    p.add_argument("--processes", type=int, default=4, help="processes to run the widths and worlds in")
    p.add_argument("--quick", action="store_true", help="a small run to check the command")
    p.set_defaults(fn=cmd_exact)

    p = sub.add_parser("exact-figures", help="the exact study's figures from its recorded JSON")
    p.add_argument("--json", required=True, help="exact.json")
    p.add_argument("--outdir", default="figures/exact")
    p.set_defaults(fn=cmd_exact_figures)

    p = sub.add_parser("exact-slide-figures",
                       help="the panels of the five exact-identification slides, each at its slide size, from "
                            "the recorded JSON")
    p.add_argument("--json", required=True, help="exact.json")
    p.add_argument("--outdir", default="figures/exact-slides",
                   help="the NeurIPS set goes here, the CNS set into its cns/ folder")
    p.add_argument("--venue", choices=("both", "neurips", "cns"), default="both")
    p.set_defaults(fn=cmd_exact_slide_figures)

    p = sub.add_parser("exact-supplement",
                       help="the checks the exact study's second review asked for: the region claim near the "
                            "regional borders, the quadrature on every scoring column, the exact rule on the "
                            "classifier's fields and on columns of another length; writes supplement.json")
    p.add_argument("--outdir", default=None, help="write supplement.json here")
    p.add_argument("--record-json", default=os.path.join(HERE, "..", "records", "exact-2026-10-26", "exact.json"),
                   dest="record_json", help="the exact study's record, to check the region counts against")
    p.add_argument("--processes", type=int, default=4, help="processes to run the worlds and chunks in")
    p.add_argument("--quick", action="store_true", help="a small run to check the command")
    p.set_defaults(fn=cmd_exact_supplement)

    p = sub.add_parser("second-opinion",
                       help="what the exact rule says about an answer one level off, on the exact study's own "
                            "scoring columns, for the white paper's comparison with registration; writes "
                            "second_opinion.json")
    p.add_argument("--outdir", default=None, help="write second_opinion.json here")
    p.add_argument("--record-json", default=os.path.join(HERE, "..", "records", "exact-2026-10-26", "exact.json"),
                   dest="record_json", help="the exact study's record, whose columns and exact shares it must match")
    p.set_defaults(fn=cmd_second_opinion)

    p = sub.add_parser("study-power",
                       help="power of the white paper's randomized reader study by simulation, over readers, "
                            "cases and strata; writes study_power.json")
    p.add_argument("--outdir", default=None, help="write study_power.json here")
    p.add_argument("--power-reps", type=int, default=None, dest="power_reps",
                   help="simulated studies per power cell (default the module's)")
    p.add_argument("--size-reps", type=int, default=None, dest="size_reps",
                   help="simulated studies per size cell (default the module's)")
    p.set_defaults(fn=cmd_study_power)

    p = sub.add_parser("study-power-three",
                       help="power and size of the three-arm design (registration, the exact rule, both), for "
                            "the contrast of both against registration; writes study_power_three_arms.json")
    p.add_argument("--outdir", default=None, help="write study_power_three_arms.json here")
    p.add_argument("--power-reps", type=int, default=None, dest="power_reps",
                   help="simulated studies per power cell (default the module's)")
    p.add_argument("--size-reps", type=int, default=None, dest="size_reps",
                   help="simulated studies per size cell (default the module's)")
    p.set_defaults(fn=cmd_study_power_three)

    p = sub.add_parser("whitepaper-checks",
                       help="the within-one Bayes rule on the exact study's scoring columns, and the anomalous "
                            "columns judged by the count from C2 as well as by their own names; writes checks.json")
    p.add_argument("--outdir", default=None, help="write checks.json here")
    p.add_argument("--record-json", default=os.path.join(HERE, "..", "records", "exact-2026-10-26", "exact.json"),
                   dest="record_json", help="the exact study's record, whose shares it must match")
    p.add_argument("--supplement-json",
                   default=os.path.join(HERE, "..", "records", "exact-2026-10-26", "supplement.json"),
                   dest="supplement_json", help="the supplement, whose own-name anomalous counts it must match")
    p.set_defaults(fn=cmd_whitepaper_checks)

    p = sub.add_parser("selftest", help="reproduce the known CTSpinoPelvic1K answers")
    p.add_argument("--levels", default=DEFAULT_FIXTURE,
                   help="defaults to the bundled fixture")
    p.set_defaults(fn=cmd_selftest)

    p = sub.add_parser("all", help="measure, phenotype, border, breakout, plots")
    p.add_argument("--labels", required=True)
    p.add_argument("--outdir", default="out")
    p.add_argument("--above", default="T12")
    p.add_argument("--below", default="L1")
    p.add_argument("--jobs", type=int, default=0)
    p.add_argument("--measures", default="endplate,canal_w")
    p.add_argument("--reference", default=None)
    p.add_argument("--no-reference", action="store_true")
    p.set_defaults(fn=cmd_all)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
