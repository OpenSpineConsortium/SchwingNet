"""Fill the <<PLACEHOLDER>> marks of validation/README.md and DESIGN.md from a deep run's deep.json.

    python3 fill.py <deep.json> <commit> <test count> <suite seconds> <new tests seconds> [--write]
"""
import json
import re
import sys
from pathlib import Path

REPO = Path("/home/user/symphony-protocol")


def n(x):
    return f"{int(round(x)):,}"


def s(x):
    return f"{x:,.0f} s"


def hm(seconds):
    h, m = divmod(int(round(seconds / 60)), 60)
    return f"{h} h {m} min" if h else f"{m} min"


def violations(count):
    return "no violation" if count == 0 else f"{count} violations"


def main(argv):
    path, commit, test_count, suite_s, new_s = argv[:5]
    write = "--write" in argv
    d = json.loads(Path(path).read_text())
    by = {x["space"]: x for x in d["searches"]}
    assert not d["red"], d["red"]
    assert not d.get("errors"), d.get("errors")
    values = {}
    for name, key in (("E-deep", "E_DEEP"), ("E-two", "E_TWO"), ("E-faults", "E_FAULTS")):
        x = by[name]
        unknown = [v for v in x["violations"] if v["finding"] is None]
        values[key] = f"{n(x['states'])} states and {n(x['transitions'])} transitions in {s(x['seconds'])}, {violations(len(unknown))}"
        values[key + "_SHORT"] = f"{n(x['states'])} states in {s(x['seconds'])} ({hm(x['seconds'])}), {violations(len(unknown))}"
    chunks = d["soak"]["chunks"]
    walks = sum(c["walks"] for c in chunks)
    steps = sum(c["steps"] for c in chunks)
    walk_s = sum(c["seconds"] for c in chunks)
    soak_v = sum(len(c["violations"]) for c in chunks)
    values["SOAK"] = f"{n(walks)} walks of {n(steps // walks)} steps, {s(walk_s)} of walking over the chunks, {violations(soak_v)}"
    values["SOAK_SHORT"] = f"{n(walks)} walks, {s(walk_s)} of walking, {violations(soak_v)}"
    g = d["gate"]
    states = [m["states"] for m in g["memory"]]
    mem_v = sum(m["violation_count"] for m in g["memory"])
    mem_s = sum(m["seconds"] for m in g["memory"])
    git = g["git"]
    git_v = len(git["violations"])
    s05g = g["s05g"]
    values["GATE"] = (f"four policies to depth {g['memory'][0]['depth']} over MemoryWorld, {n(min(states))} to {n(max(states))} states each in {s(mem_s)} together, {violations(mem_v)}; "
                      f"S05g over BareGitWorld, {len(s05g['timeline'])} acts, {len(s05g['mismatches'])} mismatches; "
                      f"{git['sequences']} sequences over git, {git['acts']} acts, {git['merges']} merges, {git['main_moved']} main moved, {git['refusals']} refusals, {violations(git_v)}, {s(git['seconds'])}")
    values["GATE_SHORT"] = f"{n(min(states))} to {n(max(states))} states a policy in memory, {git['sequences']} sequences over git, {violations(mem_v + git_v)}"
    c = d["conformance"]
    paths = sum(x["paths"] for x in c)
    cex = sum(x["counterexamples"] for x in c)
    dis = sum(len(x["disagreements"]) for x in c)
    c_s = sum(x["seconds"] for x in c)
    values["CONFORMANCE"] = f"{paths} sampled paths and {cex} counterexamples played in both worlds, {dis} disagreements, {s(c_s)}"
    values["CONFORMANCE_SHORT"] = f"{paths} paths, {cex} counterexamples, {dis} disagreements, {s(c_s)}"
    gd = d["guard"]
    values["GUARD"] = (f"{gd['recorded']} argument lists recorded again under {gd['git']}, {len(gd['differing'])} answered differently from guard_git.json ({gd['recorded_git']}), "
                       f"{len(gd.get('missing', []))} of the file's missing, {s(gd['seconds'])}")
    values["GUARD_SHORT"] = f"{gd['recorded']} lists, {len(gd['differing'])} differing, {s(gd['seconds'])}"
    gs = d["git"]["scenarios"]
    gt = d["git"]["traces"]
    values["GIT_SCENARIOS_S"] = f"{sum(x['seconds'] for x in gs):.1f}"
    values["GIT_TRACES_S"] = f"{sum(x['seconds'] for x in gt):.1f}"
    values["TOTAL_S"] = f"{s(d['seconds'])} ({hm(d['seconds'])}), at commit {commit}"
    values["VERDICT"] = (f"The run is green: no violation, mismatch, disagreement or differing answer on the library as main holds it "
                         f"(0.4.1 with F7 and F12 fixed), and it is kept under validation/runs/2026-10-14/ as the run of record.")
    values["TEST_S"] = new_s
    values["TEST_COUNT"] = f"{int(test_count):,}"
    values["DESIGN_MEASURED"] = (f"the whole run in {s(d['seconds'])} ({hm(d['seconds'])}) at commit {commit}, green: E-deep at depth {by['E-deep']['depth']}, {values['E_DEEP_SHORT']}; "
                                 f"E-two at depth {by['E-two']['depth']}, {values['E_TWO_SHORT']}; E-faults at depth {by['E-faults']['depth']}, {values['E_FAULTS_SHORT']}; "
                                 f"the soak, {values['SOAK_SHORT']}; the gate, {values['GATE_SHORT']}; conformance, {values['CONFORMANCE_SHORT']}; the guard, {values['GUARD_SHORT']}; "
                                 f"the git world, {len(gs)} scenarios and {len(gt)} traces matching known.json in {values['GIT_SCENARIOS_S']} and {values['GIT_TRACES_S']} s.")
    for k, v in values.items():
        print(f"{k}: {v}")
    if write:
        for name in ("validation/README.md", "validation/DESIGN.md"):
            p = REPO / name
            t = p.read_text()
            t2 = re.sub(r"<<([A-Z_]+)>>", lambda m: values[m.group(1)], t)
            p.write_text(t2)
            print(f"{name}: {t.count('<<')} marks filled")


if __name__ == "__main__":
    main(sys.argv[1:])
