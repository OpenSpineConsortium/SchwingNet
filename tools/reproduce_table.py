"""The reproduction page of the dataset registry.

For each record under data/sources/, docs/research/datasets-reproduce.md gives the manifest records of
data/reproduce/sources.json (spinesurg-ct-nnunet's data platform, copied with its fetch code) that hold the
source: how and when it was acquired, the links it came from, the command that fetches it again, the checks
that prove a copy, where it sits on the grid, and its licence and access; then the 144 sources of the anomaly
harvest; then what no script reproduces and the manual step each needs. data/reproduce/map.json says which
manifest records belong to which registry record. Standard library only, so the check runs wherever the
repository is checked out.

    python3 tools/reproduce_table.py render   # write the page
    python3 tools/reproduce_table.py check    # the page matches its inputs, the map is complete, the copies are intact
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "sources"
KIT = ROOT / "data" / "reproduce"
PAGE = ROOT / "docs" / "research" / "datasets-reproduce.md"
HARVEST = "family:B"

GROUPS = ["fluoro", "video", "projections", "films", "ct", "future"]
GROUP_TITLES = {
    "fluoro": "Real intraoperative fluoroscopy, stills (the target domain)",
    "video": "Video and cine (consecutive frames)",
    "projections": "Real projections with a registered CT (the COBRA kind)",
    "films": "Plain films (lateral or AP radiographs)",
    "ct": "CT collections and their renders (3D truth, synthetic 2D)",
    "future": "Future directions",
}
REACHES = ["held", "get", "gated", "embargoed", "none", "excluded"]
REACH_WORDS = {"held": "HAVE", "get": "GET", "gated": "GATED", "embargoed": "EMBARGOED", "none": "NONE", "excluded": "EXCLUDED"}

# The page is ASCII (the writing rule for docs/); each character the manifest uses beyond ASCII is spelt here,
# and one that is not fails the run rather than slipping through as a question mark.
SPELT = {
    "\u00a7": "sec. ", "\u2026": "...", "\u00f6": "o", "\u00fc": "u", "\u00e9": "e", "\u00e8": "e", "\u00e1": "a",
    "\u00ed": "i", "\u00f3": "o", "\u010d": "c", "\u017e": "z", "\u2260": "!=", "\u2013": "-", "\u2014": "--",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u00d7": "x", "\u2192": "->", "\u00b0": " deg",
}


def plain(text):
    """The text in ASCII, or a failure naming the character that has no spelling."""
    text = str(text)
    for char, spelling in SPELT.items():
        text = text.replace(char, spelling)
    for char in text:
        if ord(char) > 127:
            raise SystemExit(f"tools/reproduce_table.py: U+{ord(char):04X} has no ASCII spelling in {text[:80]!r}")
    return text


def one_line(text):
    return " ".join(plain(text).split())


def code(text):
    return "`" + one_line(text).replace("`", "'") + "`"


def cell(text):
    return one_line(text).replace("|", "/")


def number(value):
    return f"{value:,}" if isinstance(value, int) else str(value)


def load_registry():
    return [json.loads(p.read_text(encoding="ascii")) for p in sorted(REGISTRY.glob("*.json"))]


def load_manifest():
    data = json.loads((KIT / "sources.json").read_text(encoding="utf-8"))
    return data["meta"], {s["id"]: s for s in data["sources"]}


def load_map():
    mapping = json.loads((KIT / "map.json").read_text(encoding="ascii"))
    mapping.pop("_about", None)
    return mapping


def problems(registry, manifest, mapping):
    """What stops the page from being trusted: a registry record the map forgets, a map entry naming nothing
    that exists, or a copied file whose bytes are not the ones SHA256SUMS records."""
    found = []
    ids = {r["id"] for r in registry}
    for rid in sorted(ids - set(mapping)):
        found.append(f"data/reproduce/map.json: registry record {rid} has no entry")
    for rid in sorted(set(mapping) - ids):
        found.append(f"data/reproduce/map.json: {rid} is not a registry record")
    for rid, entry in mapping.items():
        for pid in entry.get("platform", []):
            if pid != HARVEST and pid not in manifest:
                found.append(f"data/reproduce/map.json: {rid} names an unknown manifest record {pid}")
        if not entry.get("basis"):
            found.append(f"data/reproduce/map.json: {rid} gives no basis")
    for line in (KIT / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        digest, _, name = line.partition("  ")
        path = KIT / name.strip()
        if not path.exists():
            found.append(f"data/reproduce/SHA256SUMS names {name.strip()}, which is not there")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            found.append(f"data/reproduce/{name.strip()}: SHA-256 {actual} is not the recorded {digest}")
    return found


# ------------------------------------------------------------------------------------------- one manifest record

def acquired(source):
    a = source.get("acquired") or {}
    method, date = one_line(a.get("method") or ""), one_line(a.get("date") or "")
    if method and date:
        return f"{method} ({date})"
    return method or date or "not recorded"


def origin(source):
    links = source.get("doi_or_url") or []
    return "; ".join(one_line(link) for link in links) or "none recorded"


def fetch(source):
    r = source.get("reacquire") or {}
    commands = r.get("command") or []
    if commands:
        return " then ".join(code(c) for c in commands)
    steps = r.get("gated_steps") or []
    if steps:
        return "manual: " + " ".join(one_line(s) for s in steps)
    return "no command recorded"


def checks(source):
    parts = []
    for check in (source.get("reacquire") or {}).get("verify") or []:
        kind = check.get("type", "?")
        rest = ", ".join(f"{k} {one_line(v)}" for k, v in check.items() if k != "type")
        parts.append(code(f"{kind}: {rest}" if rest else kind))
    return "; ".join(parts) or "none recorded"


def place(source):
    layout = source.get("layout") or {}
    return code(layout["path"]) if layout.get("path") else "none recorded"


def manifest_lines(source):
    r = source.get("reacquire") or {}
    return [
        f"  - {code(source['id'])}: {one_line(source.get('name') or '')}; kind {source.get('kind', '?')}, "
        f"family {source.get('family', '?')}; route {code(r.get('route') or 'none')}, mode {r.get('mode') or 'none'}; "
        f"status {source.get('status', '?')}.",
        f"    - acquired: {acquired(source)}",
        f"    - origin: {origin(source)}",
        f"    - fetch: {fetch(source)}",
        f"    - checks: {checks(source)}",
        f"    - on the grid: {place(source)}",
        f"    - licence: {one_line(source.get('licence') or 'not recorded')}; access: {one_line(source.get('access') or 'not recorded')}",
    ]


# ------------------------------------------------------------------------------------------- one registry record

def counts(record):
    return ", ".join(f"{k.replace('_', ' ')} {number(v)}" for k, v in record.get("counts", {}).items()) or "none"


def section(record, mapping, manifest, harvest_size):
    entry = mapping[record["id"]]
    basis = one_line(entry["basis"])
    lines = [
        f"### {one_line(record['name'])} ({code(record['id'])}, {REACH_WORDS[record['reach']]})",
        "",
        f"- Registry: link {record.get('link') or 'none recorded'}; grid path "
        f"{code(record['grid_path']) if record.get('grid_path') else 'none'}; counts {counts(record)}.",
    ]
    platform = entry.get("platform", [])
    if platform == [HARVEST]:
        lines.append(f"- Manifest records: the {harvest_size} sources of family B ({basis}); the table below lists them.")
    elif not platform:
        lines.append(f"- Manifest records: none. {basis}.")
        steps = " ".join(one_line(s) for s in record.get("how_to_get", []))
        lines.append(f"- The registry's steps: {steps or 'none recorded'}")
    else:
        lines.append(f"- Manifest records ({basis}):")
        for pid in platform:
            lines += manifest_lines(manifest[pid])
    return lines + [""]


def harvest_table(manifest):
    rows = sorted((s for s in manifest.values() if s.get("family") == "B"), key=lambda s: s["id"])
    modes = {}
    for s in rows:
        mode = (s.get("reacquire") or {}).get("mode") or "none"
        modes[mode] = modes.get(mode, 0) + 1
    lines = [
        "## Family B: the anomaly harvest's sources",
        "",
        f"{len(rows)} manifest records, by mode: " + ", ".join(f"{m} {n}" for m, n in sorted(modes.items())) + ". "
        "Mode run and submit are fetched by reacquire.py (run inside a job, submit as its own job); manual needs a person's "
        "step, given in each record's gated_steps and printed by the dry run.",
        "",
        "| Manifest record | Name | Kind | Route / mode | Status | On the grid | Origin |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in rows:
        r = s.get("reacquire") or {}
        first = (s.get("doi_or_url") or ["none recorded"])[0]
        layout = s.get("layout") or {}
        lines.append("| " + " | ".join([
            cell(s["id"]), cell(s.get("name") or ""), cell(s.get("kind") or ""),
            cell(f"{r.get('route') or 'none'} / {r.get('mode') or 'none'}"), cell(s.get("status") or ""),
            cell(layout.get("path") or "none recorded"), cell(first),
        ]) + " |")
    return lines + [""], len(rows)


def manual_section(registry, mapping, manifest):
    lines = ["## What no script reproduces, and the step each needs", "",
             "Registry records with no manifest record:", ""]
    for record in registry:
        entry = mapping[record["id"]]
        if not entry.get("platform"):
            steps = " ".join(one_line(s) for s in record.get("how_to_get", [])) or "none recorded"
            lines.append(f"- {code(record['id'])}: {one_line(entry['basis'])}. Steps: {steps}")
    lines += ["", "Manifest records behind the registry whose mode is manual (a person's step, then the checks):", ""]
    seen = set()
    for record in registry:
        for pid in mapping[record["id"]].get("platform", []):
            if pid == HARVEST or pid in seen:
                continue
            seen.add(pid)
            r = manifest[pid].get("reacquire") or {}
            if (r.get("mode") or "manual") == "manual":
                steps = " ".join(one_line(s) for s in r.get("gated_steps") or []) or "no step recorded"
                lines.append(f"- {code(pid)}: {steps}")
    return lines + [""]


def render(registry, manifest, mapping, meta):
    harvest_lines, harvest_size = harvest_table(manifest)
    with_records = [r for r in registry if mapping[r["id"]].get("platform") and mapping[r["id"]]["platform"] != [HARVEST]]
    without = [r for r in registry if not mapping[r["id"]].get("platform")]
    named = {pid for r in with_records for pid in mapping[r["id"]]["platform"]}
    roots = meta.get("roots", {})
    lines = [
        "# How each source of the registry is obtained again: the manifest, the links, the code and the checks",
        "",
        "Generated by tools/reproduce_table.py from data/sources/ (the registry), data/reproduce/map.json and",
        "data/reproduce/sources.json; do not edit by hand, change an input and render it again",
        "(`python3 tools/reproduce_table.py render`), and the check fails when they differ. The manifest and the fetch",
        "code under data/reproduce/ are byte-for-byte copies of spinesurg-ct-nnunet's data_platform at the commit",
        "data/reproduce/README.md names, with their SHA-256 in data/reproduce/SHA256SUMS, which the check verifies.",
        "",
        "A manifest record is one entry of that manifest: what the source is, how and when it was acquired, the links it",
        "came from (origin), the command that fetches it again (fetch; the variables ${DEST}, ${RS}, ${HOME}, ${REPO} and",
        "${DP} are the ones reacquire.py resolves, and its dry run prints them resolved), the checks that prove a copy, its",
        "place on the grid, and its licence and access. \"not recorded\" means the manifest is silent, and \"none\" that the",
        "registry record holds no such field.",
        "",
        f"{len(registry)} registry records: {len(with_records)} are held by {len(named)} manifest records between them, "
        f"one is the anomaly harvest with its {harvest_size} records of family B, and {len(without)} have no manifest "
        f"record and say why. The manifest was generated {meta.get('generated', '?')}; its roots are HOME "
        f"{code(roots.get('HOME', '?'))} and CEPH {code(roots.get('CEPH', '?'))}.",
        "",
        "## How to run it",
        "",
        "- Dry run, any machine, standard library: `python3 data/reproduce/reacquire/reacquire.py --grid <id> [<id> ...]`",
        "  prints, per source, the commands with the variables resolved to the grid's roots, the checks, and the manual",
        "  steps; `--list` prints every id with its route and mode; `--all --modes run submit` covers everything unattended.",
        "- On the grid, the same bytes run from the source repository, because the rebuild routes call its tools:",
        "  `cd ~/spinesurg-ct-nnunet/data_platform/reacquire && mkdir -p logs && sbatch -D \"$PWD\"",
        "  --export=ALL,IDS=\"<id>\",MODE=--run reacquire.sbatch`; `MODE=--verify` runs only the checks. The script refuses",
        "  to run work on the login node.",
        "- data/reproduce/README.md records what was checked on which date.",
        "",
    ]
    order = {g: i for i, g in enumerate(GROUPS)}
    reach_order = {r: i for i, r in enumerate(REACHES)}
    ordered = sorted(registry, key=lambda r: (order[r["group"]], reach_order[r["reach"]], r["name"].lower()))
    for n, group in enumerate(GROUPS, 1):
        lines += [f"## {n}. {GROUP_TITLES[group]}", ""]
        for record in ordered:
            if record["group"] == group:
                lines += section(record, mapping, manifest, harvest_size)
    lines += harvest_lines
    lines += manual_section(registry, mapping, manifest)
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv):
    command = argv[1] if len(argv) > 1 else "check"
    registry, (meta, manifest), mapping = load_registry(), load_manifest(), load_map()
    found = problems(registry, manifest, mapping)
    if found:
        print("\n".join(found))
        return 1
    page = render(registry, manifest, mapping, meta)
    if command == "render":
        PAGE.write_bytes(page.encode("ascii"))
        print(f"{PAGE.relative_to(ROOT).as_posix()}: {len(registry)} registry records rendered")
        return 0
    if PAGE.exists() and PAGE.read_bytes() == page.encode("ascii"):
        print(f"{PAGE.relative_to(ROOT).as_posix()}: matches the registry, the map and the manifest; the copies are intact")
        return 0
    print(f"{PAGE.relative_to(ROOT).as_posix()}: out of date with its inputs; run python3 tools/reproduce_table.py render")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
