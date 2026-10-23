"""Gather every cluster sweep and every verifier's verdicts into one file, in the settled
clustering's order, so the rendered page is made from one record. A verdict is matched to
its candidate by position when the verifier returned one per candidate in order, else by
the pair of artifacts and the topic."""
import json
import sys


def key(c):
    return (c.get("artifact_a", ""), c.get("artifact_b", "") or "", (c.get("topic") or "").lower()[:40])


def attach(cands, verdicts):
    if verdicts and len(verdicts) == len(cands):
        return verdicts
    by = {}
    for v in verdicts or []:
        by.setdefault(key(v), v)
        by.setdefault((v.get("artifact_a", ""), v.get("artifact_b", "") or "", ""), v)
    out = []
    for c in cands:
        out.append(by.get(key(c)) or by.get((c.get("artifact_a", ""), c.get("artifact_b", "") or "", "")))
    return out


def load_sweeps(paths):
    found = {}
    for p in paths:
        for item in json.load(open(p)):
            if not item:
                continue
            name = item["cluster"]
            f = item.get("found") or {"candidates": item.get("candidates", [])}
            prev = found.get(name)
            if prev is None or (not prev["verdicts"] and item.get("verdicts")):
                found[name] = {"found": f, "verdicts": item.get("verdicts") or []}
    return found


def main(clustering, out, *sweeps_and_extra):
    sweeps = [p for p in sweeps_and_extra if not p.startswith("extra=")]
    extra = [p[6:] for p in sweeps_and_extra if p.startswith("extra=")]
    J = json.load(open(clustering))["judged"]
    found = load_sweeps(sweeps)
    numbers_extra = []
    for p in extra:
        d = json.load(open(p))
        for cv in d.get("clusters", []):
            if cv["cluster"] in found and not found[cv["cluster"]]["verdicts"]:
                found[cv["cluster"]]["verdicts"] = cv["verdicts"]
        numbers_extra += d.get("numbers", [])
    clusters = []
    for c in J["clusters"]:
        f = found.get(c["name"])
        if not f:
            clusters.append({"cluster": c["name"], "swept": False})
            continue
        cands = f["found"]["candidates"]
        clusters.append({"cluster": c["name"], "swept": True, "candidates": cands,
                         "verdicts": attach(cands, f["verdicts"]),
                         "canonical_check": f["found"].get("canonical_check", []),
                         "unsourced_summary": f["found"].get("unsourced_summary", ""),
                         "stale_summary": f["found"].get("stale_summary", ""),
                         "notes": f["found"].get("notes", "")})
    json.dump({"clusters": clusters, "numbers_extra": numbers_extra}, open(out, "w"), indent=1)
    for c in clusters:
        n = len(c.get("candidates", []))
        v = sum(1 for x in c.get("verdicts", []) if x)
        print(f"{c['cluster'][:50]:50} swept={c['swept']} candidates={n} verdicts={v}")
    print("extra number verdicts", len(numbers_extra))


if __name__ == "__main__":
    main(*sys.argv[1:])
