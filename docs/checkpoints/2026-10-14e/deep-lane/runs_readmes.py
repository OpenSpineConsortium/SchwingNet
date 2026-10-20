"""Keep the final code's run beside the run of record and say in each run's README which code it measured.

    python3 runs_readmes.py <final out folder> <final commit> [--write]
"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path("/home/claude/symphony-protocol")
RUNS = REPO / "validation" / "runs"


def n(x):
    return f"{int(round(x)):,}"


def swap(text, old, new):
    assert text.count(old) == 1, old[:80]
    return text.replace(old, new)


def final_readme(d, commit, started):
    g = d["gate"]
    states = [m["states"] for m in g["memory"]]
    chunks = d["soak"]["chunks"]
    c = d["conformance"]
    gd = d["guard"]
    rows = [
        ("Soak", f"{n(sum(k['walks'] for k in chunks))} walks of {n(sum(k['steps'] for k in chunks) // sum(k['walks'] for k in chunks))} steps, {n(sum(k['seconds'] for k in chunks))} s of walking, {sum(len(k['violations']) for k in chunks)} violations"),
        ("Gate in memory", f"four policies to depth {g['memory'][0]['depth']}, {n(min(states))} to {n(max(states))} states each, {sum(m['violation_count'] for m in g['memory'])} violations"),
        ("Gate over git", f"S05g {len(g['s05g']['timeline'])} acts with {len(g['s05g']['mismatches'])} mismatches; {g['git']['sequences']} sequences, {g['git']['merges']} merges, {g['git']['main_moved']} main moved, {g['git']['refusals']} refusals, {len(g['git']['violations'])} violations"),
        ("Git world", f"{len(d['git']['scenarios'])} scenarios and {len(d['git']['traces'])} traces, matching known.json"),
        ("Guard", f"{gd['recorded']} argument lists recorded again on {gd['git']}, {len(gd['differing'])} differing, {len(gd.get('missing', []))} missing"),
        ("Conformance", f"{sum(x['paths'] for x in c)} paths and {sum(x['counterexamples'] for x in c)} counterexamples in both worlds, {sum(len(x['disagreements']) for x in c)} disagreements, {n(sum(x['seconds'] for x in c))} s"),
    ]
    return (f"""# The deep lane's parts but the searches, at the final code (2026-10-14)

`python3.12 scripts/validate.py deep --only soak,gate,git,guard,conformance --jobs 3 --out validation-out` on the cloud session's container (4 processors, git 2.43.0), at commit {commit} of the branch claude/validation-harness-step-6-mm6b8t, the pull request's final code: the run of record's code (acc83fb) with main's F15, F16 and F17 (#28 to #31) merged in (0a99040), the review of that merge answered (b388b0c) and the second review, of those answers, answered too. It ran from {started} to its end, green, in {d['seconds']:,.1f} s: deep.json as the runner wrote it, its logs, and no trace files, since nothing was red.

| Part | Measured |
| --- | --- |
""" + "".join(f"| {a} | {b} |\n" for a, b in rows) + """
The run of record beside it, validation/runs/2026-10-14/, ran every part at acc83fb, before main's F15, F16 and F17 came in, and so measured the library without them; this run measures every part but the four searches on the library with them. The searches take hours, and validate.yml's weekly deep job runs them on main. The git world plays seventeen traces here, F15's, F16's and F17's among them, where the run of record played fourteen.
""")


def main(argv):
    out, commit = Path(argv[0]), argv[1]
    d = json.loads((out / "deep.json").read_text())
    assert d["finished"] and not d["red"] and not d.get("errors") and not d["searches"], (d["red"], d.get("errors"))
    started = (out / "started.txt").read_text().split()[1]
    assert (out / "started.txt").read_text().split()[3] == commit, "the run was not made at that commit"
    when = started[11:16] + " UTC"
    text = final_readme(d, commit, when)
    record = (RUNS / "2026-10-14" / "README.md").read_text()
    # The run of record's README already says acc83fb was the code when the run began (the checkpoint of 2026-10-14e).
    record = swap(record, "\nThis is the run the docs' measurements come from",
                  "\nIt measured the library as main held it at c2de8b1: 0.4.1 with F4, F7, F9, F12, F13 and F14 fixed. Main merged "
                  "F15, F16 and F17 (#28 to #31) while it ran, and the pull request took them in afterwards (0a99040), so this run "
                  "did not measure them; validation/runs/2026-10-14-merged/ holds every part but the four searches run again at "
                  f"the final code, {commit}, green.\n\nThis is the run the docs' measurements come from")
    record = swap(record, "the lane's size and time before the review's fixes.",
                  "the lane's size and time before the review's fixes; the one after it, 2026-10-14-merged, for the final code.")
    before = (RUNS / "2026-10-14-before-review" / "README.md").read_text()
    before = swap(before, "so the run of record is the one at the pull request's final head, under validation/runs/2026-10-14/ once it is made.",
                  "so the run of record is validation/runs/2026-10-14/, made at the pull request's code before main's F15, F16 and "
                  "F17 came in, with validation/runs/2026-10-14-merged/ beside it for the final code.")
    print(text)
    if "--write" in argv:
        target = RUNS / "2026-10-14-merged"
        target.mkdir(exist_ok=True)
        for name in ("deep.json", "run.log", "progress.log", "started.txt"):
            shutil.copyfile(out / name, target / name)
        (target / "README.md").write_text(text, encoding="ascii")
        (RUNS / "2026-10-14" / "README.md").write_text(record, encoding="ascii")
        (RUNS / "2026-10-14-before-review" / "README.md").write_text(before, encoding="ascii")
        print("written")


if __name__ == "__main__":
    main(sys.argv[1:])
