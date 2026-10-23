"""The figures the synthesis has settled, and every text checked against them.

A concept is a figure and the words that say what it is a figure of. Two kinds are kept in
work/out/concepts.json. A dataset count comes from a record under data/sources/: its name
gives the aliases a text calls the set by (work/aliases.json replaces them where the name
gives none or the wrong ones), and each count is a figure with the noun that counts it. A
settled figure comes from a number verdict of the contradictions record that put two values
on one quantity: its anchors are the rarer words its two quotes share, with the quantity's
words that either quote carries, and each value is current, superseded or open by the
verdict. updated-later makes current the side whose figure the ruling's hint carries, else
the later page by the inventory's dates; same-number-restated makes both current; a
confirmed contradiction, cannot-tell or an updated-later whose later side neither says
leaves both open. A settled figure is used only when its own two quotes pass the rule it is
checked by, so one whose evidence the rule does not recognise is listed and not used.

Every artifact's text, every research note under docs/research/ and each dataset record's
own words are then read passage by passage. In a passage that names a dataset, each figure
goes to the nearest name within 160 characters: equal to one of that set's counts it agrees,
the same figure written with fewer digits it is rounded, and within a tenth of a count (a
thirtieth for a size) whose noun follows it, it differs. A dataset record's own words are
checked against its own counts the same way. A passage that carries at least two of a settled
figure's anchors, half of their weight by rarity, and one of its values written the same way
or rounded agrees, is superseded or is open as that value is; a passage in the figure's own
two artifacts is its evidence and is not checked. Nothing here judges: a check is a script's
match, for a person or a skeptic to read.
"""
import collections
import glob
import hashlib
import json
import math
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

sys.path.insert(0, os.path.dirname(__file__))
import verify_quotes as vq  # noqa: E402
from render_contradictions2 import number_key, number_verdicts  # noqa: E402
from render_inventory import cell, to_ascii  # noqa: E402

STOP = set("""a an the and or of in on at to for from by with without as is are was were be been being it its
this that these those which who whom whose what when where why how not no nor but if then than so such into onto over
under about above below between per each every all any some one two three four five six seven eight nine ten more
most less least other another same own only also both either neither can could may might must shall should will would
do does did done has have had having there here their them they we our us you your he she his her me my vs via etc
eg ie""".split())
WORD = re.compile(r"[a-z][a-z0-9]*")
NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?!\w)")
PERCENT_AFTER = re.compile(r"\s?(?:%|per ?cent)|\s?[-\u2013\u2014]\s?\d+(?:\.\d+)?\s?%")
# A word is an anchor when it is in fewer than about three texts in ten (an inverse document
# frequency of 1.2), so a passage is matched by what is particular to a quantity.
RARE = 1.2
NEAR = 160
SIZE_KEYS = ("gb", "mb", "tb", "bytes")
NOUNS = {
    "films": {"films", "radiographs", "xrays", "rays", "images", "laterals"},
    "radiographs": {"radiographs", "films", "xrays", "rays", "images"},
    "xrays": {"xrays", "rays", "radiographs", "films", "images"},
    "images": {"images", "films", "radiographs", "frames", "jpg", "jpgs", "png", "pngs"},
    "frames": {"frames", "images"},
    "people": {"people", "persons", "subjects", "patients", "participants", "individuals"},
    "persons": {"people", "persons", "subjects", "patients", "participants", "individuals"},
    "subjects": {"people", "persons", "subjects", "patients", "participants", "individuals", "cases"},
    "patients": {"people", "persons", "subjects", "patients", "participants", "individuals", "cases"},
    "cases": {"cases", "patients", "subjects"},
    "studies": {"studies", "exams", "examinations"},
    "series": {"series"}, "volumes": {"volumes", "cts", "scans"}, "scans": {"scans", "volumes", "cts"},
    "cts": {"cts", "ct", "scans", "volumes"}, "videos": {"videos", "clips"}, "clips": {"clips", "videos"},
    "sequences": {"sequences"}, "recordings": {"recordings"}, "specimens": {"specimens", "cadavers", "pelves"},
    "hospitals": {"hospitals", "sites", "centres", "centers"}, "sites": {"sites", "hospitals", "centres", "centers"},
    "centres": {"centres", "centers", "sites"}, "projections": {"projections", "frames"}, "panels": {"panels"},
    "renders": {"renders", "drrs"}, "sweeps": {"sweeps"}, "men": {"men"}, "women": {"women"},
    "landmarks": {"landmarks"}, "devices": {"devices"}, "classes": {"classes"},
    "gb": {"gb"}, "mb": {"mb"}, "tb": {"tb"}, "bytes": {"bytes"},
}
DISTINCT = re.compile(r"^(?=.*[A-Za-z])(?:.*[A-Z].*[A-Z]|.*\d)")
GENERIC = {"CT", "CTS", "MRI", "AP", "PET", "FDG", "AWS", "IDC", "TIB", "NLM", "CDC", "NIH", "II", "OK", "CBCT", "DRR", "XR",
           "AI", "RSNA", "MICCAI", "IEEE", "ACCV", "ETH", "CC", "BY"}
FIRST_WORDS_TOO_PLAIN = {"the", "real", "public", "synthetic", "veterinary", "coronary", "open", "international"}
OUTCOMES = ("agrees", "rounded", "superseded", "open", "differs")


def words(s):
    return [w for w in WORD.findall((s or "").lower()) if w not in STOP and len(w) > 1]


def plain(s):
    """A name or a passage as lower-case words and digits, so BUU-LSPINE and BUU LSpine meet."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def figures_in(text):
    """Each figure of two digits or more in a text, as (value, is_percent, start, end, as
    written); a figure in a word, such as case134, is no figure, and the low end of a range of
    percents, as 96 in 96-98%, is a percent."""
    out = []
    for m in NUMBER.finditer(text or ""):
        whole, frac = m.group(1), m.group(2) or ""
        if len((whole + frac).replace(",", "").replace(".", "")) < 2:
            continue
        pct = bool(PERCENT_AFTER.match(text[m.end():m.end() + 14]))
        out.append((Decimal(whole.replace(",", "") + frac), pct, m.start(), m.end(), m.group(0)))
    return out


def same(a, b):
    """Equal, or equal once the more precise of the two is rounded to the other's decimals, so
    98.22 % is the 98.2 % a page gives of the same result."""
    if a == b:
        return True
    ea, eb = a.as_tuple().exponent, b.as_tuple().exponent
    if ea == eb:
        return False
    coarse, fine = (a, b) if ea > eb else (b, a)
    return fine.quantize(Decimal(1).scaleb(coarse.as_tuple().exponent), rounding=ROUND_HALF_UP) == coarse


def written_shorter(short, full):
    """Whether short is full written with fewer figures, within two parts in a hundred: 3,600
    for 3,603, 87 for 86.834, but not 20 for 24."""
    if short == full or not full or abs(short - full) / abs(full) > Decimal("0.02"):
        return False
    exp = short.as_tuple().exponent
    if exp < 0:
        return full.quantize(Decimal(1).scaleb(exp), rounding=ROUND_HALF_UP) == short
    digits = str(short)
    step = Decimal(10) ** (len(digits) - len(digits.rstrip("0")))
    return (full / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step == short


def rounded(a, b):
    return written_shorter(a, b) or written_shorter(b, a)


def passages(text):
    """The lines of a text, a long line cut into pieces of about 600 characters at a sentence's
    end, each with its line number."""
    for n, line in enumerate((text or "").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        start = 0
        while start < len(line):
            end = min(len(line), start + 600)
            if end < len(line):
                cut = line.rfind(". ", start + 200, end)
                end = cut + 1 if cut > 0 else end
            yield n, line[start:end].strip()
            start = end


def sources(text_dir, root):
    """Every text the concepts are checked against, by id: each artifact's extracted text
    (repo/folder), each research note (notes:docs/research/...) and each dataset record's own
    words (registry:<id>)."""
    out = {aid: open(f"{text_dir}/{aid}.txt", encoding="utf-8").read() for aid in vq.artifact_ids(text_dir)}
    for path in sorted(glob.glob(os.path.join(root, "docs", "research", "**", "*.md"), recursive=True)):
        out["notes:" + os.path.relpath(path, root).replace(os.sep, "/")] = open(path, encoding="utf-8", errors="replace").read()
    for path in sorted(glob.glob(os.path.join(root, "data", "sources", "*.json"))):
        rec = json.load(open(path, encoding="utf-8"))
        out["registry:" + rec["id"]] = "\n".join(str(rec.get(k) or "") for k in ("what", "status"))
    return out


def rarity(texts):
    """Each word's inverse document frequency over the texts, the weight it carries as an
    anchor."""
    df = collections.Counter()
    for t in texts.values():
        df.update(set(words(t)))
    n = len(texts)
    return {w: math.log((n + 1) / (c + 1)) for w, c in df.items()}


# Dataset counts.

def name_aliases(name):
    """The names a dataset record's name gives for its set: each run of words that holds a
    distinctive one (two capitals, or letters and digits, and not a common abbreviation),
    each name in backticks, and each identifier in parentheses; else its first two words,
    when the first is a proper name."""
    found = set(re.findall(r"`([^`]+)`", name))
    bare = re.sub(r"\(.*?\)|`[^`]*`", " ", name)
    for part in re.split(r"\s+/\s+|\s+and\s+|,|:|;", bare):
        run = []
        for token in part.split():
            core = token.strip("'\".;")
            if DISTINCT.match(core) and core.upper() not in GENERIC:
                run.append(core)
            elif run and (core[:1].isupper() or core.isdigit()):
                run.append(core)
            elif run:
                break
        if run:
            found.add(" ".join(run))
    for inner in re.findall(r"\(([^)]*)\)", name):
        found.update(w.strip(";,") for w in inner.split() if re.search(r"\d", w) and re.search(r"[a-z]", w, re.I) and len(w) >= 6)
    if not found:
        first = re.sub(r"\(.*", "", name).split()
        if len(first) >= 2 and first[0][:1].isupper() and first[0].lower().strip(":") not in FIRST_WORDS_TOO_PLAIN:
            found.add(" ".join(first[:2]))
    return sorted({plain(a) for a in found if len(plain(a)) >= 4})


def noun_of(key):
    for part in reversed(key.lower().split("_")):
        if part in NOUNS:
            return part
    return None


def dataset_concepts(root, overrides):
    """One concept per numeric count of each dataset record whose key names what it counts."""
    out = []
    for path in sorted(glob.glob(os.path.join(root, "data", "sources", "*.json"))):
        rec = json.load(open(path, encoding="utf-8"))
        aliases = overrides.get(rec["id"], name_aliases(rec["name"]))
        for key, value in (rec.get("counts") or {}).items():
            noun = noun_of(key)
            if noun and isinstance(value, (int, float)) and not isinstance(value, bool) and value:
                out.append({"id": f"dataset:{rec['id']}:{key}", "dataset": rec["id"], "name": rec["name"], "key": key,
                            "value": str(value), "noun": noun, "aliases": [plain(a) for a in aliases]})
    return out


def alias_patterns(by_alias):
    """Each alias as a pattern that finds it between any separators, BUU-LSPINE as BUU LSpine."""
    return [(re.compile(r"(?<![a-z0-9])" + r"[^a-z0-9]+".join(map(re.escape, alias.split())) + r"(?![a-z0-9])"), datasets)
            for alias, datasets in by_alias.items()]


def alias_spans(passage, patterns):
    """Where each dataset alias stands in a passage, as (start, end, dataset)."""
    low = passage.lower()
    spans = []
    for pattern, datasets in patterns:
        for m in pattern.finditer(low):
            spans.extend((m.start(), m.end(), d) for d in datasets)
    return spans


def nearest(spans, start, end):
    """The sets whose alias stands nearest the figure, within NEAR characters: more than one
    where an alias names several, or aliases of several stand as near, sorted, so a run gives
    the same checks whatever order Python's hash seed gives a set."""
    best, names = None, set()
    for s, e, d in spans:
        gap = start - e if start >= e else (s - end if s >= end else 0)
        if gap > NEAR:
            continue
        if best is None or gap < best:
            best, names = gap, {d}
        elif gap == best:
            names.add(d)
    return sorted(names)


def noun_after(passage, end):
    return set(plain(passage[end:end + 40]).split()[:4])


def count_outcome(value, pct, after, counts):
    """How one figure stands to the counts of the set it is near: agrees with any count it
    equals; rounded where it is one written shorter and its noun follows; differs where it is
    within a tenth of one (a thirtieth for a size) and its noun follows; else nothing."""
    if pct:
        return None, None
    equal = [c for c in counts if same(value, Decimal(c["value"]))]
    if equal:
        return "agrees", equal
    named = [c for c in counts if after & NOUNS[c["noun"]]]
    for c in named:
        if rounded(value, Decimal(c["value"])):
            return "rounded", [c]
    for c in named:
        full = Decimal(c["value"])
        share = Decimal("0.0333") if c["noun"] in SIZE_KEYS else Decimal("0.10")
        if abs(value - full) / full <= share:
            return "differs", [c]
    return None, None


def check_datasets(texts, concepts):
    by_dataset = collections.defaultdict(list)
    by_alias = collections.defaultdict(set)
    for c in concepts:
        by_dataset[c["dataset"]].append(c)
        for a in c["aliases"]:
            by_alias[a].add(c["dataset"])
    patterns = alias_patterns(by_alias)
    checks = []
    for sid, text in texts.items():
        own = sid.split(":", 1)[1] if sid.startswith("registry:") else None
        for line, passage in passages(text):
            spans = [] if own else alias_spans(passage, patterns)
            if not own and not spans:
                continue
            for value, pct, start, end, written in figures_in(passage):
                counts = [c for d in ([own] if own else nearest(spans, start, end)) for c in by_dataset.get(d, [])]
                if not counts:
                    continue
                outcome, hit = count_outcome(value, pct, noun_after(passage, end), counts)
                for c in hit or []:
                    checks.append(check(c["id"], "dataset", sid, line, outcome, written, passage))
    return checks


# Settled figures.

def values_of(text):
    return [(v, pct) for v, pct, _s, _e, _w in figures_in(text)]


def carried_side(hint, value_a, value_b):
    """The side whose figure the ruling's hint names alone, a or b, else None."""
    named = {f for f, _p in values_of(hint)}
    a = any(any(same(f, v) for f in named) for v, _p in values_of(value_a))
    b = any(any(same(f, v) for f in named) for v, _p in values_of(value_b))
    return "a" if a and not b else "b" if b and not a else None


def later_side(date_a, date_b):
    """The side whose inventory date is plainly later, a or b, else None (a month and a day
    in that month say nothing of their order)."""
    if not date_a or not date_b or date_a == date_b or date_a.startswith(date_b) or date_b.startswith(date_a):
        return None
    return "a" if date_a > date_b else "b"


def statuses(verdict, v, dates, x):
    if verdict == "same-number-restated":
        return "current", "current"
    if verdict == "updated-later":
        side = carried_side(v.get("resolution_hint"), v.get("value_a") or x["value_a"], v.get("value_b") or x["value_b"]) \
            or later_side(dates.get(x["artifact_a"]), dates.get(x["artifact_b"]))
        if side:
            return ("current", "superseded") if side == "a" else ("superseded", "current")
    return "open", "open"


def anchors_of(quote_a, quote_b, quantity, weight):
    a, b = set(words(quote_a)), set(words(quote_b))
    pool = (a & b) | ((a | b) & set(words(quantity)))
    return sorted((w for w in pool if weight.get(w, 0) >= RARE), key=lambda w: (-weight[w], w))[:8]


def anchored(anchors, have, weight):
    """Whether a passage's words carry at least two of the anchors and half of their weight."""
    if len(anchors) < 2:
        return False
    hits = [w for w in anchors if w in have]
    return len(hits) >= 2 and sum(weight[w] for w in hits) >= 0.5 * sum(weight[w] for w in anchors)


def value_status(concept, passage):
    """The status of the concept's value the passage gives, the current one first, with the
    figure as the passage writes it; None when it gives none of them."""
    found = []
    for f, pct, _s, _e, written in figures_in(passage):
        for v in concept["values"]:
            if v["percent"] == pct and same(f, Decimal(v["figure"])):
                found.append((v["status"], written))
    for status in ("current", "superseded", "open"):
        for s, written in found:
            if s == status:
                return status, written
    return None, None


def figure_concepts(M, N, inventory, weight):
    """One concept for each number verdict that put two values on one quantity, with whether
    its own quotes pass the rule it is checked by."""
    dates = {f"{r['repo']}/{r['folder']}": r.get("date") or "" for r in inventory["artifacts"]}
    verdicts = number_verdicts(N, M.get("numbers_extra", []))
    out = []
    for i, x in enumerate(N["candidates"]):
        v = verdicts.get(number_key(x))
        if not v or v["verdict"] not in ("confirmed-contradiction", "updated-later", "cannot-tell", "same-number-restated"):
            continue
        qa, qb = v.get("quote_a") or x["quote_a"], v.get("quote_b") or x["quote_b"]
        sa, sb = statuses(v["verdict"], v, dates, x)
        values = [{"figure": str(f), "percent": p, "status": s, "side": side}
                  for side, text, s in (("a", v.get("value_a") or x["value_a"], sa), ("b", v.get("value_b") or x["value_b"], sb))
                  for f, p in values_of(text)]
        concept = {"id": f"figure:{i}", "row": i, "quantity": x["quantity"], "verdict": v["verdict"],
                   "artifacts": [x["artifact_a"], x["artifact_b"]], "quotes": [qa, qb],
                   "anchors": anchors_of(qa, qb, x["quantity"], weight), "values": values}
        concept["unused"] = why_unused(concept, weight)
        out.append(concept)
    return out


def why_unused(concept, weight):
    if len(concept["anchors"]) < 2:
        return "its two quotes share fewer than two rarer words"
    if not concept["values"]:
        return "its values give no figure of two digits or more"
    for side, quote in zip("ab", concept["quotes"]):
        if not anchored(concept["anchors"], set(words(quote)), weight):
            return f"its quote from side {side} carries too few of its anchors"
        mine = [v for v in concept["values"] if v["side"] == side]
        if mine and value_status({"values": mine}, quote)[0] is None:
            return f"its quote from side {side} does not give that side's figure"
    return None


def check_figures(texts, concepts, weight):
    checks = []
    used = [c for c in concepts if not c["unused"]]
    for sid, text in texts.items():
        for line, passage in passages(text):
            have = set(words(passage))
            for c in used:
                if sid in c["artifacts"] or not anchored(c["anchors"], have, weight):
                    continue
                status, written = value_status(c, passage)
                if status:
                    outcome = "agrees" if status == "current" else status
                    checks.append(check(c["id"], "figure", sid, line, outcome, written, passage))
    return checks


def check(concept, kind, source, line, outcome, written, passage):
    key = hashlib.sha1(f"{concept}|{source}|{vq.norm(passage)}|{outcome}|{written}".encode("utf-8")).hexdigest()[:16]
    return {"key": key, "concept": concept, "kind": kind, "source": source, "line": line, "outcome": outcome,
            "value": written, "text": to_ascii(passage)[:300]}


def build(root, text_dir, inventory, M, N, overrides, date):
    texts = sources(text_dir, root)
    weight = rarity(texts)
    datasets = dataset_concepts(root, overrides)
    figures = figure_concepts(M, N, inventory, weight)
    checks = check_datasets(texts, datasets) + check_figures(texts, figures, weight)
    unique = {c["key"]: c for c in checks}
    return {"date": date, "texts": len(texts), "datasets": datasets, "figures": figures,
            "checks": sorted(unique.values(), key=lambda c: (c["concept"], c["source"], c["line"], c["key"]))}


# The page.

def where_link(source, up="../"):
    if source.startswith("notes:"):
        path = source.split(":", 1)[1]
        return f"[{path}](../../{path})"
    if source.startswith("registry:"):
        return f"[data/sources/{source.split(':', 1)[1]}.json](../../data/sources/{source.split(':', 1)[1]}.json)"
    repo, folder = source.split("/", 1)
    if repo == "SchwingNet":
        return f"[{folder}]({up}{folder}/)"
    return f"[{folder}](https://github.com/OpenSpineConsortium/symphony-template/tree/main/artifacts/{folder}/)"


def page(ledger, baseline_date):
    """concepts.md: the dataset counts and settled figures, and where each text stands."""
    checks = ledger["checks"]
    tally = collections.Counter(c["outcome"] for c in checks)
    by_concept = collections.defaultdict(list)
    for c in checks:
        by_concept[c["concept"]].append(c)
    figures = ledger["figures"]
    used = [f for f in figures if not f["unused"]]
    out = ["# Concepts the synthesis has settled, and where every text stands\n",
           to_ascii(__doc__.strip().split("\n\n")[0].replace("\n", " ")) + "\n",
           to_ascii(__doc__.strip().split("\n\n")[1].replace("\n", " ")) + "\n",
           f"Rendered on {ledger['date']} from {ledger['texts']} texts by work/tools/synth.py concepts, which"
           " .github/workflows/synthesis.yml runs on every push that changes an artifact, a research note or a"
           " dataset record; the issue labelled synthesis lists what each run found that the stamp of"
           f" {baseline_date} had not seen. Edit the records and render again rather than editing this file.\n",
           "## Summary\n",
           f"- Dataset counts: {len(ledger['datasets'])}, from {len({d['dataset'] for d in ledger['datasets']})} records under data/sources/.",
           f"- Settled figures: {len(figures)}, {len(used)} used and {len(figures) - len(used)} not used (listed at the end).",
           "- Checks: " + ", ".join(f"{tally[o]} {o}" for o in OUTCOMES) + ".\n"]
    out += dataset_section(ledger, by_concept)
    out += figure_section(used, by_concept)
    out.append("## Settled figures not used\n")
    out.append("| Row | Quantity | Verdict | Why not |\n|---|---|---|---|")
    for f in figures:
        if f["unused"]:
            out.append(f"| {f['row']} | {cell(to_ascii(f['quantity']))} | {f['verdict']} | {f['unused']} |")
    return "\n".join(out) + "\n"


def dataset_section(ledger, by_concept):
    out = ["## Dataset counts\n",
           "Each record's counts with the lines that give one of them otherwise; the lines that agree are counted, not listed.\n"]
    by_dataset = collections.defaultdict(list)
    for d in ledger["datasets"]:
        by_dataset[d["dataset"]].append(d)
    for dataset, counts in sorted(by_dataset.items()):
        hits = [c for d in counts for c in by_concept.get(d["id"], [])]
        if not hits:
            continue
        agree = sum(1 for c in hits if c["outcome"] == "agrees")
        out.append(f"### {cell(to_ascii(counts[0]['name']))} ({dataset})\n")
        out.append("Called " + ", ".join(f"'{a}'" for a in counts[0]["aliases"]) + "; counts "
                   + ", ".join(f"{d['key']} {d['value']}" for d in counts) + f"; {agree} lines agree.\n")
        listed = [c for c in hits if c["outcome"] != "agrees"]
        if listed:
            out.append("| Count | Outcome | Gives | Where | Line | Passage |\n|---|---|---|---|---|---|")
            for c in listed:
                key = c["concept"].rsplit(":", 1)[1]
                out.append(f"| {key} | {c['outcome']} | {cell(c['value'])} | {where_link(c['source'])} | {c['line']} | {cell(c['text'][:200])} |")
            out.append("")
    return out


def figure_section(used, by_concept):
    out = ["## Settled figures\n",
           "Each number verdict's figures with their status, and the other texts that give one of them.\n"]
    for f in used:
        hits = by_concept.get(f["id"], [])
        vals = "; ".join(f"{v['figure']}{'%' if v['percent'] else ''} ({v['status']}, side {v['side']})" for v in f["values"])
        out.append(f"### Row {f['row']}: {cell(to_ascii(f['quantity']))}\n")
        out.append(f"{f['verdict']}; {vals}; anchors " + ", ".join(f["anchors"]) + "; read from "
                   + " and ".join(where_link(a) for a in f["artifacts"]) + ".\n")
        if hits:
            out.append("| Outcome | Gives | Where | Line | Passage |\n|---|---|---|---|---|")
            for c in hits:
                out.append(f"| {c['outcome']} | {cell(c['value'])} | {where_link(c['source'])} | {c['line']} | {cell(c['text'][:200])} |")
            out.append("")
    return out


def load_overrides(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.get("aliases", {}).items()}
