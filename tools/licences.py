"""The licence of every dataset, as classes a recipe can choose by, and the record of each run.

Source: the thread "Training data licence provenance", 2026-10-23, the owner's ask of that day:
before training, every run must say which datasets went into it under which licence, so that a
network meant for commercial use is built only from data whose terms allow it, a network that
needs non-commercial data is known as one, and the recipes that are possible can be seen before
anything runs.

The facts are in data/licences.json, one entry per dataset: every record under data/sources/ by
its id, and every registry source under data/registry/ that has no record of its own, with an
alias where a registry source is a record under another name. An entry copies the record's
licence line word for word, so a line that changes is caught, and gives it a class, from the most
permissive to the least:

    open            commercial use and derivatives allowed, at most attribution (CC BY, CC0, PD, MIT)
    share-alike     commercial use allowed, derivatives under the same licence (CC BY-SA)
    non-commercial  no commercial use (CC BY-NC, BY-NC-SA, In Copyright non-commercial)
    agreement       the terms of a signed agreement: a DUA, a credentialed licence, a request form,
                    competition rules, research-only; never commercial
    no-derivatives  no adapted material may be shared (any ND); a trained network may count as one
    unknown         not recorded, to confirm, or read two ways with no restriction named

The rule below proposes a class from the line's words, taking the strictest reading any phrase of
it gives; an entry the rule proposed says "reviewed": "rule", and the owner's own reading says
"owner YYYY-MM-DD". Only the owner's reading may give a class more permissive than the rule's.
Whether a trained network is a derivative under share-alike or no-derivatives terms, and whether
an agreement allows any use beyond the project's, are questions for counsel: the classes say what
the words say, never what a court would.

A recipe, data/recipes/<name>.json, names the classes it takes. A catalog is cut to a recipe by
`derive`, which keeps only the recipe's sources and writes the recipe and its parent's sha256 into
the copy, and every run writes PROVENANCE.json and PROVENANCE.md beside RUN.json (tools/flow.py):
each source, its licence and class, its frames and persons in each part, the recipes it fits, and
the run's own class, the strictest among the sources it trained or selected on. Standard library
only; it never opens a frame.

    python3 tools/licences.py check
    python3 tools/licences.py propose [--write]
    python3 tools/licences.py render
    python3 tools/licences.py recipes [--catalog CATALOG]
    python3 tools/licences.py derive --catalog CATALOG --recipe NAME --out NEW.sqlite
    python3 tools/licences.py provenance --catalog CATALOG --out RUN_DIR [--recipe NAME]
"""

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data" / "licences.json"
RECIPES = ROOT / "data" / "recipes"
RECORDS = ROOT / "data" / "sources"
REGISTRY = ROOT / "data" / "registry"
PAGE = ROOT / "data" / "LICENCES.md"

CLASSES = ("open", "share-alike", "non-commercial", "agreement", "no-derivatives", "unknown")
COMMERCIAL = {"open": "yes", "share-alike": "yes", "unknown": "unknown"}
DERIVATIVES = {"no-derivatives": "no", "agreement": "unknown", "unknown": "unknown"}
TRAINING_PARTS = ("train", "validation")
REVIEWED = re.compile(r"^(rule|owner \d{4}-\d{2}-\d{2})$")
NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Each restriction counts wherever the line names it, notes included, since a note that says the
# labels are non-commercial binds as much as the line's first words do.
NO_DERIVATIVES = re.compile(r"(?i)\bND\b|no ?derivatives")
NON_COMMERCIAL = re.compile(r"(?i)\bNC\b|non[- ]?commercial")
AGREEMENT = re.compile(
    r"(?i)(?<!no )agreement|\bDUA\b|credentialed|restricted health data|research[- ]use|research[- ]only"
    r"|competition rules|by request|request form|on request|reasonable request|by registration|registration"
    r"|subscription|in copyright|licence form|license form"
)
# Doubt counts only where no restriction does: a line that is non-commercial by any reading is
# non-commercial, while one that is open by one reading and unread by another is unknown.
DOUBT = re.compile(r"(?i)not recorded|unknown|to confirm|by one reading|varies|mixed|unlicensed|inherits|project's own|none stated|unstated|unread")
# An open licence counts only in the line's own words, outside its notes in parentheses, as the
# census reads it (spine-datasets tools/census.py): a note may speak of another record's licence.
# "Open access" and a bare "open" say the files can be read, not what may be done with them.
SHARE_ALIKE = re.compile(r"(?i)BY-SA|ShareAlike|share-alike")
OPEN = re.compile(
    r"(?i)CC[- ]?BY\b|CC0|public domain|\bPDDL\b|\bMIT\b|Creative Commons Attribution(?! ?-? ?Non)"
    r"|\bODC-?By\b"
)
RESTRICTIONS = ((NO_DERIVATIVES, "no-derivatives"), (AGREEMENT, "agreement"), (NON_COMMERCIAL, "non-commercial"))


class LicenceError(Exception):
    """A file or a run the licence rules refuse, with the reason a person reads."""


def classify(text):
    """The class the rule reads in a licence line: the strictest restriction it names, else
    unknown where it doubts, else what its own words open."""
    text = text if isinstance(text, str) else ""
    named = [found for pattern, found in RESTRICTIONS if pattern.search(text)]
    if named:
        return strictest(named)
    if DOUBT.search(text):
        return "unknown"
    words = re.sub(r"\([^)]*\)", " ", text)
    if SHARE_ALIKE.search(words):
        return "share-alike"
    return "open" if OPEN.search(words) else "unknown"


def strictest(classes):
    """The least permissive of some classes; unknown for none, since nothing read is no licence."""
    return max(classes, key=CLASSES.index, default="unknown")


def terms_of(licence_class):
    """Whether a class allows commercial use and derivatives, in yes, no or unknown."""
    return {
        "commercial": COMMERCIAL.get(licence_class, "no"),
        "derivatives": DERIVATIVES.get(licence_class, "yes"),
    }


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LicenceError(f"{path}: {error}") from error


def licence_lines():
    """Every dataset's licence line, by the key data/licences.json gives it: each record under
    data/sources/ by its id, its licence line; and each registry source, under its alias where it
    has one, by its access line, which wins over the record's, since it is what was read when the
    source entered the catalog a run trains from."""
    facts = read_json(FACTS) if FACTS.is_file() else {"aliases": {}}
    lines = {path.stem: str(read_json(path).get("licence") or "") for path in sorted(RECORDS.glob("*.json"))}
    for path in sorted(REGISTRY.glob("*.json")):
        lines[facts.get("aliases", {}).get(path.stem, path.stem)] = str(read_json(path).get("access") or "")
    return dict(sorted(lines.items()))


def proposal(text):
    licence_class = classify(text)
    return {"licence": text, "class": licence_class, **terms_of(licence_class), "reviewed": "rule", "note": ""}


def proposed_facts(facts, lines):
    """The facts with every missing entry proposed by the rule, and every entry whose line changed
    proposed again; an entry whose line still stands is kept as it is, the owner's reading above all."""
    sources = dict(facts.get("sources", {}))
    changed = []
    for key, text in lines.items():
        entry = sources.get(key)
        if entry is None or entry.get("licence") != text:
            changed.append(key)
            sources[key] = proposal(text)
    return {"aliases": facts.get("aliases", {}), "sources": dict(sorted(sources.items()))}, changed


def entry_problems(key, entry, text):
    """What one entry gets wrong against its record's line and the rules."""
    if text is None:
        return [f"{key}: no record under data/sources/ and no registry source has this name"]
    found = []
    if entry.get("licence") != text:
        found.append(f"{key}: the licence line changed since it was classified; run propose --write and review it")
    if entry.get("class") not in CLASSES:
        found.append(f"{key}: class {entry.get('class')!r} is none of {', '.join(CLASSES)}")
        return found
    if not REVIEWED.match(str(entry.get("reviewed", ""))):
        found.append(f"{key}: reviewed is 'rule' or 'owner YYYY-MM-DD'")
    if {k: entry.get(k) for k in ("commercial", "derivatives")} != terms_of(entry["class"]):
        found.append(f"{key}: commercial and derivatives must be {terms_of(entry['class'])} for class {entry['class']}")
    loosened = CLASSES.index(entry["class"]) < CLASSES.index(classify(text))
    if loosened and not str(entry.get("reviewed", "")).startswith("owner"):
        found.append(f"{key}: class {entry['class']} is more permissive than the rule's {classify(text)}; only the owner's reading may say so")
    return found


def problems(facts, lines, recipes):
    """Everything data/licences.json and data/recipes/ get wrong; empty when they hold."""
    sources = facts.get("sources", {})
    found = [f"{key}: no entry in data/licences.json; run propose --write" for key in lines if key not in sources]
    for key, entry in sources.items():
        found += entry_problems(key, entry, lines.get(key))
    for alias, target in facts.get("aliases", {}).items():
        if not (REGISTRY / f"{alias}.json").is_file() or target not in sources:
            found.append(f"aliases: {alias} -> {target} needs a registry source and an entry")
    for name, recipe in recipes.items():
        found += recipe_problems(name, recipe)
    return found


def recipe_problems(name, recipe):
    found = []
    if recipe.get("name") != name or not NAME.match(name):
        found.append(f"recipe {name}: its name is its file's name, lower case with hyphens")
    allow = recipe.get("allow")
    if not isinstance(allow, list) or not allow or any(c not in CLASSES for c in allow):
        found.append(f"recipe {name}: allow lists classes among {', '.join(CLASSES)}")
    elif "unknown" in allow:
        found.append(f"recipe {name}: no recipe takes unknown; classify the source first")
    if not isinstance(recipe.get("reviewed_only"), bool) or not str(recipe.get("why", "")).strip():
        found.append(f"recipe {name}: reviewed_only is true or false, and why says what the recipe is for")
    return found


def load_recipes():
    return {path.stem: read_json(path) for path in sorted(RECIPES.glob("*.json"))}


def entry_for(facts, source):
    """The entry a catalog source is read by, through its alias where it has one."""
    key = facts.get("aliases", {}).get(source, source)
    return key, facts.get("sources", {}).get(key)


def fits(entry, recipe):
    if entry is None or entry["class"] not in recipe["allow"]:
        return False
    return not recipe["reviewed_only"] or str(entry.get("reviewed", "")).startswith("owner")


def recipe_named(name, recipes):
    if name not in recipes:
        raise LicenceError(f"no recipe {name}; the recipes are {', '.join(recipes) or 'none'} under data/recipes/")
    return recipes[name]


def connect(catalog, write=False):
    if not Path(catalog).is_file():
        raise LicenceError(f"{catalog}: no catalog there")
    return sqlite3.connect(catalog if write else f"file:{catalog}?mode=ro", uri=not write)


def counts_by_source(catalog):
    """Frames and persons of each source in each part, and the recipe the catalog was cut by."""
    db = connect(catalog)
    try:
        rows = db.execute(
            "SELECT source, part, COUNT(DISTINCT sha256), COUNT(DISTINCT person) FROM item GROUP BY source, part"
        ).fetchall()
        sources = [row[0] for row in db.execute("SELECT source FROM source")]
        recipe = cut_recipe(db)
    finally:
        db.close()
    counts = {source: {"frames": {}, "persons": {}} for source in sources}
    for source, part, frames, persons in rows:
        counts.setdefault(source, {"frames": {}, "persons": {}})
        counts[source]["frames"][part] = frames
        counts[source]["persons"][part] = persons
    return dict(sorted(counts.items())), recipe


def cut_recipe(db):
    """The recipe a derived catalog records, or None for a catalog no recipe cut."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'recipe'").fetchone():
        return None
    name, allow, parent = db.execute("SELECT name, allow, parent_catalog_sha256 FROM recipe").fetchone()
    return {"name": name, "allow": json.loads(allow), "parent_catalog_sha256": parent}


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_row(source, counts, facts, recipes):
    key, entry = entry_for(facts, source)
    entry = entry or {"licence": "", "class": "unknown", "reviewed": "none"}
    return {
        "source": source, "inventory": key, "licence": entry["licence"], "class": entry["class"],
        **terms_of(entry["class"]), "reviewed": entry.get("reviewed", "none"),
        "frames": counts["frames"], "persons": counts["persons"],
        "recipes": [name for name, recipe in recipes.items() if fits(facts["sources"].get(key), recipe)],
    }


def trained_on(row):
    return any(row["frames"].get(part) for part in TRAINING_PARTS)


def provenance(catalog, facts, recipes):
    """The run's licence record: every source of the catalog, and the run's class and recipes,
    judged by the sources it trained or selected on; a test-only source is listed, not counted."""
    counts, cut = counts_by_source(catalog)
    rows = [source_row(source, value, facts, recipes) for source, value in counts.items()]
    used = [row for row in rows if trained_on(row)]
    run_class = strictest([row["class"] for row in used])
    return {
        "catalog_sha256": sha256_of(catalog),
        "recipe": cut,
        "sources": rows,
        "run_class": run_class,
        "commercial_use": terms_of(run_class)["commercial"],
        "fits_recipes": [name for name in recipes if used and all(name in row["recipes"] for row in used)],
        "unclassified": [row["source"] for row in rows if row["reviewed"] == "none"],
        "caveat": "classes read the licence's words; whether a trained network is a derivative is for counsel",
    }


def provenance_page(record):
    """PROVENANCE.md: the record as a person reads it."""
    recipe = record["recipe"]
    lines = [
        "# Training data provenance",
        "",
        f"- Catalog sha256: {record['catalog_sha256']}",
        f"- Cut by recipe: {recipe['name'] + ' (' + ', '.join(recipe['allow']) + '), from catalog ' + recipe['parent_catalog_sha256'][:12] if recipe else 'none, the whole catalog'}",
        f"- The run's class: {record['run_class']}; commercial use: {record['commercial_use']}",
        f"- Recipes the run fits: {', '.join(record['fits_recipes']) or 'none'}",
        f"- Sources with no licence entry: {', '.join(record['unclassified']) or 'none'}",
        "",
        "| Source | Class | Commercial | Reviewed | Train frames | Validation frames | Test frames | Licence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in record["sources"]:
        frames = [str(row["frames"].get(part, 0)) for part in ("train", "validation", "test")]
        lines.append(f"| {row['source']} | {row['class']} | {row['commercial']} | {row['reviewed']} | " + " | ".join(frames) + f" | {cell(row['licence'])} |")
    return "\n".join([*lines, "", record["caveat"].capitalize() + ".", ""])


def cell(text):
    return " ".join(str(text).split()).replace("|", "/")


def run_provenance(catalog, recipe_name=None):
    """The record of a run about to start, refused for a catalog with a source that has no licence
    entry, or with a source the recipe the run names does not take."""
    facts, recipes = read_json(FACTS), load_recipes()
    record = provenance(catalog, facts, recipes)
    if record["unclassified"]:
        raise LicenceError(f"sources with no licence entry in data/licences.json: {', '.join(record['unclassified'])}")
    if recipe_name:
        recipe_named(recipe_name, recipes)
        outside = [row["source"] for row in record["sources"] if trained_on(row) and recipe_name not in row["recipes"]]
        if outside:
            raise LicenceError(f"recipe {recipe_name} does not take {', '.join(outside)}; cut the catalog with derive first")
    return record


def write_provenance(out, record):
    """PROVENANCE.json and PROVENANCE.md in a run's folder."""
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / "PROVENANCE.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    (Path(out) / "PROVENANCE.md").write_text(provenance_page(record), encoding="utf-8")


def derive(catalog, recipe_name, out):
    """A copy of the catalog holding only the sources the recipe takes, with the recipe recorded."""
    facts, recipes = read_json(FACTS), load_recipes()
    recipe = recipe_named(recipe_name, recipes)
    if Path(out).exists():
        raise LicenceError(f"{out} exists; a derived catalog is written once")
    parent = sha256_of(catalog)
    shutil.copyfile(catalog, out)
    db = connect(out, write=True)
    try:
        sources = [row[0] for row in db.execute("SELECT source FROM source UNION SELECT source FROM item")]
        dropped = sorted(s for s in sources if not fits(entry_for(facts, s)[1], recipe))
        drop_sources(db, dropped)
        db.execute("CREATE TABLE recipe (name TEXT, allow TEXT, parent_catalog_sha256 TEXT, kept TEXT, dropped TEXT)")
        kept = sorted(set(sources) - set(dropped))
        db.execute("INSERT INTO recipe VALUES (?, ?, ?, ?, ?)", (recipe_name, json.dumps(recipe["allow"]), parent, json.dumps(kept), json.dumps(dropped)))
        db.commit()
        db.execute("VACUUM")
    finally:
        db.close()
    return kept, dropped


def drop_sources(db, dropped):
    marks = ", ".join("?" for _ in dropped)
    if not dropped:
        return
    db.execute(f"DELETE FROM label WHERE shard IN (SELECT name FROM shard WHERE source IN ({marks}))", dropped)
    db.execute(f"DELETE FROM item WHERE source IN ({marks})", dropped)
    db.execute("DELETE FROM embedding WHERE item NOT IN (SELECT sha256 FROM item)")
    for table in ("person", "shard", "source"):
        db.execute(f"DELETE FROM {table} WHERE source IN ({marks})", dropped)


def mark(entry, recipe):
    """yes where the recipe takes the source now, after review where only the owner's reading of
    its class stands in the way, and a dash where its class is not one the recipe takes."""
    if fits(entry, recipe):
        return "yes"
    return "after review" if entry and entry["class"] in recipe["allow"] else "-"


def render(facts, recipes):
    """data/LICENCES.md: every dataset by class, and which recipe takes which trainable source."""
    sources = facts["sources"]
    trainable = sorted(path.stem for path in REGISTRY.glob("*.json"))
    lines = [
        "# Dataset licences and training recipes",
        "",
        "Written by `python3 tools/licences.py render` from data/licences.json and data/recipes/; do not edit by hand.",
        "A class reads the licence's words (tools/licences.py); whether a trained network is a derivative is for counsel.",
        "",
        "## Classes",
        "",
        "| Class | Datasets | Owner-reviewed |",
        "|---|---|---|",
    ]
    for licence_class in CLASSES:
        members = [k for k, e in sources.items() if e["class"] == licence_class]
        reviewed = sum(1 for k in members if sources[k]["reviewed"].startswith("owner"))
        lines.append(f"| {licence_class} | {len(members)} | {reviewed} |")
    lines += ["", "## Recipes over the trainable sources (data/registry/)", "",
              "yes: the recipe takes the source now; after review: its class fits, and the recipe takes it once the owner confirms the class; -: never under this licence.", "", "| Source | Class | Reviewed | " + " | ".join(recipes) + " |", "|---|---|---|" + "---|" * len(recipes)]
    for source in trainable:
        key, entry = entry_for(facts, source)
        marks = [mark(entry, recipe) for recipe in recipes.values()]
        lines.append(f"| {source} | {entry['class'] if entry else 'none'} | {entry['reviewed'] if entry else 'none'} | " + " | ".join(marks) + " |")
    lines += ["", "## Every dataset", "", "| Dataset | Class | Commercial | Reviewed | Licence |", "|---|---|---|---|---|"]
    for key, entry in sources.items():
        lines.append(f"| {key} | {entry['class']} | {entry['commercial']} | {entry['reviewed']} | {cell(entry['licence'])} |")
    return "\n".join(lines) + "\n"


def command_check(_args):
    facts = read_json(FACTS)
    found = problems(facts, licence_lines(), load_recipes())
    if not found and (not PAGE.is_file() or PAGE.read_text(encoding="utf-8") != render(facts, load_recipes())):
        found.append(f"{PAGE.relative_to(ROOT)} differs from what the facts render; run render")
    for line in found:
        print(f"licences: {line}", file=sys.stderr)
    return 1 if found else 0


def command_propose(args):
    facts = read_json(FACTS) if FACTS.is_file() else {"aliases": {}, "sources": {}}
    updated, changed = proposed_facts(facts, licence_lines())
    for key in changed:
        print(f"{key}: {updated['sources'][key]['class']} ({cell(updated['sources'][key]['licence'])[:90]})")
    if args.write:
        FACTS.write_text(json.dumps(updated, indent=1) + "\n", encoding="utf-8")
    return 0


def command_render(_args):
    PAGE.write_text(render(read_json(FACTS), load_recipes()), encoding="utf-8")
    return 0


def command_recipes(args):
    facts, recipes = read_json(FACTS), load_recipes()
    counts = counts_by_source(args.catalog)[0] if args.catalog else {path.stem: None for path in sorted(REGISTRY.glob("*.json"))}
    for name, recipe in recipes.items():
        taken = [s for s in counts if fits(entry_for(facts, s)[1], recipe)]
        frames = sum(sum(counts[s]["frames"].values()) for s in taken) if args.catalog else None
        print(json.dumps({"recipe": name, "allow": recipe["allow"], "sources": taken, "left_out": [s for s in counts if s not in taken], "frames": frames}))
    return 0


def command_derive(args):
    kept, dropped = derive(args.catalog, args.recipe, args.out)
    print(json.dumps({"catalog": args.out, "recipe": args.recipe, "kept": kept, "dropped": dropped}))
    return 0


def command_provenance(args):
    record = run_provenance(args.catalog, args.recipe)
    write_provenance(args.out, record)
    print(json.dumps({"run_class": record["run_class"], "commercial_use": record["commercial_use"], "fits_recipes": record["fits_recipes"]}))
    return 0


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("propose").add_argument("--write", action="store_true")
    sub.add_parser("render")
    sub.add_parser("recipes").add_argument("--catalog")
    derive_p = sub.add_parser("derive")
    provenance_p = sub.add_parser("provenance")
    for p in (derive_p, provenance_p):
        p.add_argument("--catalog", required=True)
        p.add_argument("--out", required=True)
    derive_p.add_argument("--recipe", required=True)
    provenance_p.add_argument("--recipe")
    return parser.parse_args(argv)


COMMANDS = {"check": command_check, "propose": command_propose, "render": command_render, "recipes": command_recipes, "derive": command_derive, "provenance": command_provenance}


def main(argv=None):
    args = parse(argv)
    try:
        return COMMANDS[args.command](args)
    except LicenceError as error:
        print(f"licences: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
