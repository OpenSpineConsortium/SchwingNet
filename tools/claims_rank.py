"""Rank what to run next by how much SchwingNet's claims rest on it.

Source: issue #216, 2026-10-24, the owner's ask for a ranked list of experiments by their "critical
weight bearing" on the claims of novelty, functionality and integrity. Chapter 33 of the textbook
(docs/textbook/33-what-to-run-next-by-the-weight-of-the-claims.md) explains the register and the
ranking; this module is the arithmetic.

The register is docs/textbook/claims.json. Each claim has a kind (novelty, functionality,
integrity), a statement, the evidence it stands on with a grade for each link, its own grade (the
weakest link) and its stakes, the things that fall if it fails (the patent, the talk, a
manuscript, the grant, the operating-room study). Each item is an experiment or an open question:
what it is, which claims it bears on, the grade it could bring each claim to and whether it could
refute it, what it costs, whether it waits on the owner's word and which items it waits on.

The weight of an item, with every constant named below so a person can change it:

    criticality(claim) = sum of STAKE_WEIGHTS over the claim's stakes
    move(item, claim)  = max(GRADE_RANK[to] - GRADE_RANK[claim's grade],
                             REFUTE_STEP if the item could refute the claim else 0)
    own(item)          = sum over the claims it bears on of
                         KIND_WEIGHTS[kind] x criticality(claim) x move(item, claim)
    weight(item)       = own(item) + UNLOCK_SHARE x sum of weight(j) over the open items j
                         that list this item in depends_on
    cost_factor(item)  = 1 + SESSION_HOUR x session hours + WORK_DAY x days of work
                           + CPU_HOUR x CPU-hours + GPU_HOUR x GPU-hours
                           + READER_HOUR x readers' hours + PER_DOLLAR x dollars
                           + UNKNOWN_COST[kind] for each kind of cost the record does not size
                           + EXTERNAL_PARTY when an outside party must act
    score(item)        = weight(item) / cost_factor(item)

A range [low, high] counts at its midpoint. The grade ladder is Unverified 0, Inferred 1, Reported
2, Measured 3; a refutation counts REFUTE_STEP, since finding a claim false before it is made is
worth a step of grade. The ranking knows nothing of dates, of the probability that an item
succeeds or of how much a result would move a number; chapter 33 says what that leaves out.

    python3 tools/claims_rank.py table      # the ranked items, as a Markdown table
    python3 tools/claims_rank.py claims     # the claims by kind, as a Markdown table
    python3 tools/claims_rank.py next       # the top ready item with and without the owner's word, as JSON
    python3 tools/claims_rank.py check      # the register holds together

Every command takes --file to read another register. Standard library only.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "textbook" / "claims.json"

GRADE_RANK = {"Unverified": 0, "Inferred": 1, "Reported": 2, "Measured": 3}
KINDS = ("novelty", "functionality", "integrity")

# What falls if a claim fails, and how much it weighs. The patent is filed once and cannot be
# taken back; the talk is public on 2 November; a manuscript can be corrected before submission.
STAKE_WEIGHTS = {
    "patent": 5,
    "talk": 4,
    "paper-1": 3,
    "paper-2": 3,
    "or-study": 3,
    "paper-film": 2,
    "grant": 2,
}

# The owner named the three kinds together; they weigh the same until the owner says otherwise.
KIND_WEIGHTS = {"novelty": 1.0, "functionality": 1.0, "integrity": 1.0}

REFUTE_STEP = 1
UNLOCK_SHARE = 0.5

SESSION_HOUR = 0.05
WORK_DAY = 0.5
CPU_HOUR = 0.01
GPU_HOUR = 0.25
READER_HOUR = 0.1
PER_DOLLAR = 0.0005
UNKNOWN_COST = {"grid": 2.0, "reads": 2.0, "external": 0.0}
EXTERNAL_PARTY = 3.0

COST_RATES = {
    "session_hours": SESSION_HOUR,
    "work_days": WORK_DAY,
    "cpu_hours": CPU_HOUR,
    "gpu_hours": GPU_HOUR,
    "reader_hours": READER_HOUR,
    "dollars": PER_DOLLAR,
}


def load(path=REGISTER):
    """The register as a dictionary."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def amount(value):
    """A cost figure or the midpoint of a [low, high] range."""
    if isinstance(value, list):
        return (value[0] + value[1]) / 2
    return value


def criticality(claim):
    """How much falls if the claim fails: the summed weights of its stakes."""
    return sum(STAKE_WEIGHTS[stake] for stake in claim["stakes"])


def move(bearing, claim):
    """How far an item could move a claim: steps of grade, or a refutation."""
    rise = GRADE_RANK[bearing["to"]] - GRADE_RANK[claim["grade"]]
    refute = REFUTE_STEP if bearing.get("could_refute") else 0
    return max(rise, refute, 0)


def own_weight(item, claims):
    """The weight an item carries through the claims it bears on directly."""
    total = 0.0
    for bearing in item["bears_on"]:
        claim = claims[bearing["claim"]]
        total += KIND_WEIGHTS[claim["kind"]] * criticality(claim) * move(bearing, claim)
    return total


def is_external(cost):
    """Whether an outside party must act for the item to run."""
    return bool(cost.get("external")) or "external" in cost.get("unknown", [])


def cost_factor(item):
    """One plus the item's costs, each at its named rate."""
    cost = item["cost"]
    factor = 1.0
    for field, rate in COST_RATES.items():
        if field in cost:
            factor += rate * amount(cost[field])
    for kind in cost.get("unknown", []):
        factor += UNKNOWN_COST[kind]
    if is_external(cost):
        factor += EXTERNAL_PARTY
    return factor


def open_items(register):
    """The items not yet done."""
    return [item for item in register["items"] if item.get("status", "open") != "done"]


def dependents(items):
    """For each item id, the open items that wait on it."""
    waiting = {item["id"]: [] for item in items}
    for item in items:
        for needed in item["depends_on"]:
            if needed in waiting:
                waiting[needed].append(item["id"])
    return waiting


def weights(register):
    """The weight of every open item, its own plus a share of what it unlocks."""
    claims = {claim["id"]: claim for claim in register["claims"]}
    items = {item["id"]: item for item in open_items(register)}
    waiting = dependents(list(items.values()))
    memo = {}

    def weight(item_id):
        if item_id not in memo:
            unlocked = sum(weight(other) for other in waiting[item_id])
            memo[item_id] = own_weight(items[item_id], claims) + UNLOCK_SHARE * unlocked
        return memo[item_id]

    return {item_id: weight(item_id) for item_id in items}


def is_ready(item, register):
    """Whether everything the item waits on is done."""
    done = {other["id"] for other in register["items"] if other.get("status") == "done"}
    return all(needed in done for needed in item["depends_on"])


def ranked(register):
    """The open items with their weight, cost factor and score, best first."""
    weight_of = weights(register)
    rows = []
    for item in open_items(register):
        factor = cost_factor(item)
        rows.append({
            "item": item,
            "weight": weight_of[item["id"]],
            "cost_factor": factor,
            "score": weight_of[item["id"]] / factor,
            "ready": is_ready(item, register),
        })
    rows.sort(key=lambda row: (-round(row["score"], 9), row["item"]["id"]))
    return rows


def bearing_text(item, claims):
    """The claims an item bears on, each with the grade it could reach."""
    parts = []
    for bearing in item["bears_on"]:
        claim = claims[bearing["claim"]]
        rises = GRADE_RANK[bearing["to"]] > GRADE_RANK[claim["grade"]]
        step = f"{claim['grade']} to {bearing['to']}" if rises else "no rise"
        if bearing.get("could_refute"):
            step = step + ", or refute" if rises else "could refute"
        parts.append(f"{bearing['claim']} ({step})")
    return "; ".join(parts) if parts else "none directly"


def table(register):
    """The ranked items as a Markdown table."""
    claims = {claim["id"]: claim for claim in register["claims"]}
    lines = [
        "| Rank | Item | What | Bears on | Weight | Cost factor | Score | Owner's word | Ready |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rank, row in enumerate(ranked(register), 1):
        item = row["item"]
        lines.append(
            f"| {rank} | {item['id']} | {item['title']} | {bearing_text(item, claims)} | "
            f"{row['weight']:.1f} | {row['cost_factor']:.2f} | {row['score']:.1f} | "
            f"{'yes' if item['needs_owner_word'] else 'no'} | "
            f"{'yes' if row['ready'] else 'after ' + ', '.join(item['depends_on'])} |"
        )
    return "\n".join(lines)


def claims_table(register):
    """The claims, grouped by kind, as a Markdown table."""
    lines = [
        "| Claim | Kind | Statement | Grade | Stakes | Criticality | Action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for kind in KINDS:
        for claim in register["claims"]:
            if claim["kind"] == kind:
                statement = claim["statement"].replace("|", "\\|")
                lines.append(
                    f"| {claim['id']} | {kind} | {statement} | {claim['grade']} | "
                    f"{', '.join(claim['stakes'])} | {criticality(claim)} | {claim.get('action', 'carry')} |"
                )
    return "\n".join(lines)


def summary(row, register):
    """One ranked item as the JSON the Claude integration reads."""
    item = row["item"]
    claims = {claim["id"]: claim for claim in register["claims"]}
    return {
        "id": item["id"],
        "title": item["title"],
        "what": item["what"],
        "score": round(row["score"], 2),
        "weight": round(row["weight"], 2),
        "cost_factor": round(row["cost_factor"], 2),
        "needs_owner_word": item["needs_owner_word"],
        "owner_word_reason": item.get("owner_word_reason"),
        "bears_on": [
            {"claim": b["claim"], "from": claims[b["claim"]]["grade"], "to": b["to"],
             "could_refute": bool(b.get("could_refute"))}
            for b in item["bears_on"]
        ],
        "issue": item.get("issue"),
        "cost": item["cost"],
    }


def next_items(register):
    """The top ready item that needs no word of the owner's, and the top that does."""
    rows = [row for row in ranked(register) if row["ready"]]
    free = next((row for row in rows if not row["item"]["needs_owner_word"]), None)
    asked = next((row for row in rows if row["item"]["needs_owner_word"]), None)
    return {
        "without_owner_word": summary(free, register) if free else None,
        "with_owner_word": summary(asked, register) if asked else None,
    }


def problems(register):
    """Every way the register fails to hold together."""
    found = []
    found += claim_problems(register)
    found += item_problems(register)
    found += cycle_problems(register)
    return found


def evidence_problems(claim):
    """A claim's evidence: graded, sourced, and its grade the weakest link."""
    found = []
    evidence = claim.get("evidence") or []
    if not evidence:
        return [f"claim {claim['id']}: no evidence"]
    for link in evidence:
        if link.get("grade") not in GRADE_RANK:
            found.append(f"claim {claim['id']}: evidence grade {link.get('grade')!r} is not one of the four")
        source = link.get("source", "")
        if source.startswith(("docs/", "artifacts/")) and not (ROOT / source.split("#")[0]).exists():
            found.append(f"claim {claim['id']}: evidence source {source} does not exist")
    grades = [link["grade"] for link in evidence if link.get("grade") in GRADE_RANK]
    if grades and claim.get("grade") in GRADE_RANK:
        weakest = min(grades, key=GRADE_RANK.get)
        if weakest != claim["grade"]:
            found.append(f"claim {claim['id']}: grade {claim['grade']} is not its weakest link, {weakest}")
    return found


def claim_problems(register):
    """Ids, kinds, grades, stakes and evidence of every claim."""
    found = []
    seen = set()
    for claim in register.get("claims", []):
        cid = claim.get("id")
        if cid in seen:
            found.append(f"claim {cid}: id used twice")
        seen.add(cid)
        if claim.get("kind") not in KINDS:
            found.append(f"claim {cid}: kind {claim.get('kind')!r} is not one of {', '.join(KINDS)}")
        if claim.get("grade") not in GRADE_RANK:
            found.append(f"claim {cid}: grade {claim.get('grade')!r} is not one of the four")
        if claim.get("kind") == "novelty" and claim.get("grade") == "Measured":
            found.append(f"claim {cid}: a novelty claim cannot be Measured")
        if not claim.get("stakes"):
            found.append(f"claim {cid}: no stakes")
        for stake in claim.get("stakes", []):
            if stake not in STAKE_WEIGHTS or stake not in register.get("stakes", {}):
                found.append(f"claim {cid}: stake {stake!r} has no weight or no description")
        found += evidence_problems(claim)
    return found


def cost_problems(item):
    """An item's cost: known fields, figures that are numbers, ranges low to high."""
    found = []
    cost = item.get("cost")
    if not isinstance(cost, dict) or not cost.get("basis"):
        return [f"item {item.get('id')}: a cost with no basis"]
    for field in COST_RATES:
        value = cost.get(field)
        if value is None:
            continue
        pair = value if isinstance(value, list) else [value, value]
        if len(pair) != 2 or not all(isinstance(v, (int, float)) and v >= 0 for v in pair) or pair[0] > pair[1]:
            found.append(f"item {item['id']}: cost {field} {value!r} is not a figure or a low-to-high range")
    for kind in cost.get("unknown", []):
        if kind not in UNKNOWN_COST:
            found.append(f"item {item['id']}: unknown cost kind {kind!r}")
    return found


def item_problems(register):
    """Ids, references to claims and items, grades and costs of every item."""
    found = []
    claims = {claim.get("id"): claim for claim in register.get("claims", [])}
    ids = [item.get("id") for item in register.get("items", [])]
    for item in register.get("items", []):
        iid = item.get("id")
        if ids.count(iid) > 1:
            found.append(f"item {iid}: id used twice")
        if not isinstance(item.get("needs_owner_word"), bool):
            found.append(f"item {iid}: needs_owner_word must be true or false")
        for bearing in item.get("bears_on", []):
            claim = claims.get(bearing.get("claim"))
            if claim is None:
                found.append(f"item {iid}: bears on {bearing.get('claim')!r}, which is no claim")
                continue
            if bearing.get("to") not in GRADE_RANK:
                found.append(f"item {iid}: grade {bearing.get('to')!r} for {claim['id']} is not one of the four")
            elif claim["kind"] == "novelty" and bearing["to"] == "Measured":
                found.append(f"item {iid}: a novelty claim ({claim['id']}) cannot become Measured")
        for needed in item.get("depends_on", []):
            if needed not in ids:
                found.append(f"item {iid}: depends on {needed!r}, which is no item")
        found += cost_problems(item)
    return found


def cycle_problems(register):
    """Items that wait on each other in a circle, which nothing could start."""
    graph = {item.get("id"): list(item.get("depends_on", [])) for item in register.get("items", [])}
    state = {}
    found = []

    def visit(node, path):
        if state.get(node) == "done" or node not in graph:
            return
        if state.get(node) == "open":
            found.append("items wait on each other in a circle: " + " -> ".join(path + [node]))
            return
        state[node] = "open"
        for needed in graph[node]:
            visit(needed, path + [node])
        state[node] = "done"

    for node in graph:
        visit(node, [])
    return found


def main(argv=None):
    """Run one command over the register."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["table", "claims", "next", "check"])
    parser.add_argument("--file", default=str(REGISTER), help="the register to read")
    args = parser.parse_args(argv)
    register = load(args.file)
    found = problems(register)
    if args.command == "check" or found:
        for problem in found:
            print(problem)
        if found:
            print(f"{len(found)} problems in {args.file}")
            return 1
        print(f"claims register ok: {len(register['claims'])} claims, {len(register['items'])} items")
        return 0
    if args.command == "table":
        print(table(register))
    elif args.command == "claims":
        print(claims_table(register))
    else:
        print(json.dumps(next_items(register), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
