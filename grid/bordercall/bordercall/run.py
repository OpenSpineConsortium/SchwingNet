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
                           scale_sd=a.scale_sd)
    return 0


def cmd_panjabi_corpus(a) -> int:
    import junction
    measures = [m.strip() for m in a.measures.split(",") if m.strip()]
    junction.run_corpus(a.levels, a.phenotype, outdir=a.outdir, n_columns=a.n_columns,
                        margin=a.margin, seed=a.seed, measures=measures, rho=a.rho,
                        noise_mm=a.noise_mm, scale_sd=a.scale_sd)
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
