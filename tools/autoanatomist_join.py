#!/usr/bin/env python3
"""The auto-anatomist screen's join: every trial's entry read and checked, the decision against the
null, two plots and a short summary (docs/research/autoanatomist-screen/README.md).

    python3 tools/autoanatomist_join.py --plan PLAN.json --out STUDY_FOLDER

Reads STUDY_FOLDER/trials/<trial>/entry.json for every trial of the plan
(schwingnet.autoanatomist_screen.trials), refuses an entry that does not hold
(entry_problems) by counting its trial as failed, with the reason the trial left in why.txt where
it wrote no entry, decides each arm against the null (decide) and
writes STUDY_FOLDER/join/DECISION.json first, then curves.png, finals.png and SUMMARY.md, plots
first with a line on how to read each. A failed trial is shown failed, never dropped: its arm, and
every arm when the null is the one that failed, is undecided. Exit 0 when every trial wrote an entry
that holds, 3 when some did not (the decision and the plots are written all the same), 2 when the
plan itself does not hold.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# As in tools/realism.py: this folder leaves the path, and the package and the pinned beethoven-qa
# its contracts come from join it.
sys.path[0] = str(ROOT / "src")
if str(ROOT / "vendor" / "beethoven-qa" / "src") not in sys.path:
    sys.path.insert(1, str(ROOT / "vendor" / "beethoven-qa" / "src"))

from schwingnet.autoanatomist_screen import (  # noqa: E402
    decide,
    entry_problems,
    plan_of,
    plan_problems,
    trials,
)

CURVES_NOTE = (
    "Each line is one trial: its mean surface distance on the validation CTs at each reading, every "
    "few epochs, read from the CT alone. Lower is better. Dashed lines are the null, which never "
    "anneals."
)
FINALS_NOTE = (
    "Each dot is one seed's distance after the last epoch. An arm beats the null when every one of its "
    "dots sits left of every one of the null's."
)


def why_none(folder):
    """The first line of the reason a trial left where it wrote no entry, or a plain word."""
    try:
        line = (folder / "why.txt").read_text(encoding="utf-8").strip().splitlines()[0]
    except (OSError, IndexError):
        return "wrote no entry"
    return f"wrote no entry ({line[:200]})"


def read_entries(plan, out):
    """Each trial's entry where it wrote one that holds, and what kept the others out."""
    entries, failed = {}, {}
    for trial in trials(plan):
        path = out / "trials" / trial.id / "entry.json"
        if not path.is_file():
            failed[trial.id] = why_none(path.parent)
            continue
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            failed[trial.id] = f"its entry is not JSON ({error.__class__.__name__})"
            continue
        found = entry_problems(entry, trial, plan)
        if found:
            failed[trial.id] = found[0]
        else:
            entries[trial.id] = entry
    return entries, failed


def arm_colours(plan):
    """One colour an arm, from the default cycle, in the arms' sorted order."""
    cycle = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
    return {arm: cycle[at % len(cycle)] for at, arm in enumerate(sorted(plan.arms))}


def plot_curves(plan, entries, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colours = arm_colours(plan)
    from matplotlib.ticker import MaxNLocator

    figure, axes = plt.subplots(figsize=(8.0, 4.2))
    for trial in trials(plan):
        entry = entries.get(trial.id)
        if entry is None:
            continue
        points = [(e["epoch"], e[plan.measure]) for e in entry["epochs"] if e[plan.measure] is not None]
        if points:
            style = "--" if trial.arm == plan.null else "-"
            axes.plot(*zip(*points), style, color=colours[trial.arm], label=trial.id, linewidth=1.4)
    axes.set_xlabel("epoch")
    axes.set_ylabel(f"validation {plan.measure} (lower is better)")
    axes.set_title(f"{plan.screen}: every trial's curve")
    axes.xaxis.set_major_locator(MaxNLocator(integer=True))
    axes.legend(fontsize=7, frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def plot_finals(plan, decision, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colours = arm_colours(plan)
    order = [plan.null] + sorted(set(plan.arms) - {plan.null})
    finals = {plan.null: decision["null_finals"], **{arm: d["finals"] for arm, d in decision["arms"].items()}}
    figure, axes = plt.subplots(figsize=(7.0, 0.6 + 0.55 * len(order)))
    labels = []
    for row, arm in enumerate(order):
        values = [v for v in finals[arm] if v is not None]
        axes.scatter(values, [row] * len(values), color=colours[arm], s=36, zorder=3)
        missing = len(finals[arm]) - len(values)
        labels.append(f"{arm} ({missing} failed)" if missing else arm)
    known = [v for v in decision["null_finals"] if v is not None]
    if known:
        axes.axvspan(min(known), max(known), color="#d9d9d9", zorder=1, linewidth=0)
    axes.set_yticks(range(len(order)), labels=labels)
    axes.set_xlabel(f"final validation {plan.measure} (lower is better)")
    axes.set_title(f"{plan.screen}: each seed's last epoch, the null's span shaded")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def verdict_word(value):
    return {True: "beats the null", False: "does not beat the null", None: "undecided"}[value]


def summary_text(plan, decision, failed):
    lines = [f"# {plan.screen}", "", plan.purpose, "", "![every trial's curve](curves.png)", "", CURVES_NOTE, "",
             "![each seed's last epoch](finals.png)", "", FINALS_NOTE, "", decision["rule"] + ".", ""]
    for arm, d in sorted(decision["arms"].items()):
        lines.append(f"- {arm} {verdict_word(d['beats_null'])}: {d['why']}.")
    for trial, why in sorted(failed.items()):
        lines.append(f"- {trial} failed: {why}.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    top.add_argument("--plan", required=True, help="the screen's plan file")
    top.add_argument("--out", required=True, help="the study's folder, which holds trials/")
    args = top.parse_args(argv)
    record = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    found = plan_problems(record)
    if found:
        print(f"autoanatomist_join: the plan does not hold: {found[0]}")
        return 2
    plan, out = plan_of(record), Path(args.out)
    entries, failed = read_entries(plan, out)
    decision = decide(plan, entries)
    decision["failed"] = failed
    join = out / "join"
    join.mkdir(parents=True, exist_ok=True)
    (join / "DECISION.json").write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    plot_curves(plan, entries, join / "curves.png")
    plot_finals(plan, decision, join / "finals.png")
    (join / "SUMMARY.md").write_text(summary_text(plan, decision, failed), encoding="utf-8")
    for arm, d in sorted(decision["arms"].items()):
        print(f"autoanatomist_join: {arm} {verdict_word(d['beats_null'])}")
    for trial, why in sorted(failed.items()):
        print(f"autoanatomist_join: {trial} failed: {why}")
    return 3 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
