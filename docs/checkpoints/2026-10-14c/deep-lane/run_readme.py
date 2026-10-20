"""Write validation/runs/2026-10-14/README.md from a deep run's deep.json.

    python3 run_readme.py <deep.json> <commit> <started line> [--write]
"""
import json
import sys
from pathlib import Path

REPO = Path("/home/user/symphony-protocol")


def n(x):
    return f"{int(round(x)):,}"


def main(argv):
    path, commit, started = argv[:3]
    d = json.loads(Path(path).read_text())
    by = {x["space"]: x for x in d["searches"]}
    assert not d["red"] and not d.get("errors"), (d["red"], d.get("errors"))
    g = d["gate"]
    states = [m["states"] for m in g["memory"]]
    chunks = d["soak"]["chunks"]
    c = d["conformance"]
    gd = d["guard"]
    rows = []
    for name in ("E-deep", "E-two", "E-faults"):
        x = by[name]
        rows.append((name, f"depth {x['depth']}, {n(x['states'])} states, {n(x['transitions'])} transitions, {n(x['seconds'])} s, {len(x['violations'])} violations"))
    rows.append(("Soak", f"{n(sum(k['walks'] for k in chunks))} walks of {n(sum(k['steps'] for k in chunks) // sum(k['walks'] for k in chunks))} steps, {n(sum(k['seconds'] for k in chunks))} s of walking, {sum(len(k['violations']) for k in chunks)} violations"))
    rows.append(("Gate in memory", f"four policies to depth {g['memory'][0]['depth']}, {n(min(states))} to {n(max(states))} states each, {sum(m['violation_count'] for m in g['memory'])} violations"))
    rows.append(("Gate over git", f"S05g {len(g['s05g']['timeline'])} acts with {len(g['s05g']['mismatches'])} mismatches; {g['git']['sequences']} sequences, {g['git']['merges']} merges, {g['git']['main_moved']} main moved, {g['git']['refusals']} refusals, {len(g['git']['violations'])} violations"))
    rows.append(("Git world", f"{len(d['git']['scenarios'])} scenarios and {len(d['git']['traces'])} traces, matching known.json"))
    rows.append(("Guard", f"{gd['recorded']} argument lists recorded again on {gd['git']}, {len(gd['differing'])} differing, {len(gd.get('missing', []))} missing"))
    rows.append(("Conformance", f"{sum(x['paths'] for x in c)} paths and {sum(x['counterexamples'] for x in c)} counterexamples in both worlds, {sum(len(x['disagreements']) for x in c)} disagreements, {n(sum(x['seconds'] for x in c))} s"))
    text = f"""# The run of record of the deep lane (2026-10-14)

`python3.12 scripts/validate.py deep --jobs 4 --out validation-out` on the cloud session's container (4 processors, git 2.43.0), at commit {commit} of the branch claude/validation-harness-step-6-mm6b8t, the pull request's final code: main merged in with build step 7, the review's fixes (0c17ac6, 72d86a0) and the runner's fixes after the third review round. It ran from {started} to its end, green, in {d['seconds']:,.1f} s: deep.json as the runner wrote it, its logs, and no trace files, since nothing was red. Its checkpoints are left out, as before: they are pickles of a few hundred megabytes that only a resume of that same run could read.

| Part | Measured |
| --- | --- |
""" + "".join(f"| {a} | {b} |\n" for a, b in rows) + """
This is the run the docs' measurements come from (validation/README.md, step 6; DESIGN.md, section 14, step 6, and the table of section 6.7). The two earlier runs beside it, 2026-10-14-partial and 2026-10-14-before-review, are kept for what they showed on the way: the soak's three leads, judged faults of the harness's model, and the lane's size and time before the review's fixes.
"""
    print(text)
    if "--write" in argv:
        folder = REPO / "validation/runs/2026-10-14"
        folder.mkdir(exist_ok=True)
        (folder / "README.md").write_text(text, encoding="ascii")
        print("written")


if __name__ == "__main__":
    main(sys.argv[1:])
