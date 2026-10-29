"""The organization map, .github/symphony/organization.json: the check.

The map says how the organization's repositories depend on each other and
touch (a vendored library, a reusable workflow, a GitHub App, a runner,
data handed on) and which systems outside GitHub they reach; the control
panel's Organization tab draws it beside what it reads live from GitHub.
An edge to a node that is not there, a kind the file's own list does not
name or a repository that says no visibility would draw as a
gap or a blank, so this check holds the file together before a pull
request, from scripts/check.sh:

  python3 tools/organization_map.py check         the map holds together
  python3 tools/organization_map.py check PATH    another map file

One line per problem, "path: problem"; exit 1 when there is any, 0 with
the counts otherwise. Standard library only. docs/research/organization-map.md
says how the map was made and how to keep it.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / ".github" / "symphony" / "organization.json"
KEYS = ("about", "owner", "written", "edge_reads", "kinds", "groups", "nodes", "edges")
VISIBILITIES = ("public", "internal", "private")
SYSTEM = "system"


def problems_of(data):
    """Every way the map fails to hold together, in words, in reading order."""
    if not isinstance(data, dict):
        return ["the map is not a JSON object"]
    found = [f"the key {key} is missing" for key in KEYS if key not in data]
    if found:
        return found
    for key in ("kinds", "groups"):
        if not isinstance(data[key], dict) or not data[key]:
            found.append(f"{key} must be an object that names each one")
    for key in ("nodes", "edges"):
        if not isinstance(data[key], list):
            found.append(f"{key} must be a list")
    if found:
        return found
    names = set()
    for index, node in enumerate(data["nodes"]):
        found.extend(node_problems(node, index, names, data["groups"]))
    seen = set()
    for index, edge in enumerate(data["edges"]):
        found.extend(edge_problems(edge, index, names, data["kinds"], seen))
    return found


def node_problems(node, index, names, groups):
    """The problems of one node; names collects every name seen so far."""
    where = f"nodes[{index}]"
    if not isinstance(node, dict):
        return [f"{where} is not an object"]
    name = node.get("name")
    if not isinstance(name, str) or not name.strip():
        return [f"{where} has no name"]
    where = f"node {name}"
    found = []
    if name in names:
        found.append(f"{where} is named twice")
    names.add(name)
    if node.get("group") not in groups:
        found.append(f"{where} has a group the file does not list: {node.get('group')!r}")
    if node.get("kind") == SYSTEM:
        return found
    if node.get("visibility") not in VISIBILITIES:
        found.append(f"{where} must say public, internal or private, or be a system")
    if not isinstance(node.get("role"), str) or not node["role"].strip():
        found.append(f"{where} has no role")
    return found


def edge_problems(edge, index, names, kinds, seen):
    """The problems of one edge; seen collects every (from, to, kind) so far."""
    where = f"edges[{index}]"
    if not isinstance(edge, dict):
        return [f"{where} is not an object"]
    start, end, kind = edge.get("from"), edge.get("to"), edge.get("kind")
    where = f"edge {start} -> {end}"
    found = []
    for side in (start, end):
        if side not in names:
            found.append(f"{where} names a node that is not there: {side!r}")
    if start == end:
        found.append(f"{where} joins a node to itself")
    if kind not in kinds:
        found.append(f"{where} has a kind the file does not list: {kind!r}")
    if (start, end, kind) in seen:
        found.append(f"{where} is listed twice as {kind}")
    seen.add((start, end, kind))
    if not isinstance(edge.get("what"), str) or not edge["what"].strip():
        found.append(f"{where} does not say what passes")
    return found


def check(path):
    """Print each problem of the map at path; 1 when there is any, else 0."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"{path}: {error}")
        return 1
    found = problems_of(data)
    for problem in found:
        print(f"{path}: {problem}")
    if found:
        return 1
    print(f"{path}: {len(data['nodes'])} nodes and {len(data['edges'])} edges hold together")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] != "check" or len(argv) > 2:
        print("usage: python3 tools/organization_map.py check [PATH]")
        return 2
    return check(argv[1] if len(argv) == 2 else MAP)


if __name__ == "__main__":
    sys.exit(main())
