"""The plan and the moves of a drive the organizer has read: a session's
projects checked against the catalog, and the moves they ask for, written
for the owner to read and made one call at a time only once approved.

The drive is read through Microsoft Graph under the owner's own Microsoft
sign-in, the control panel's Connect OneDrive: drive-organize.yml's step
catalog walks it (tools/drive_organize.py) and leaves catalog.json, with
each item's parent and the folders Microsoft 365's apps keep, on a private
repository's branch drive-catalog. The walk through the Microsoft 365
connector that this tool once kept is retired (2026-10-20): no drive is
read here.

  python3 tools/drive_connector.py check --plan PLAN.json --catalog DIR/catalog.json
  python3 tools/drive_connector.py moves --plan PLAN.json --catalog DIR/catalog.json --out DIR
  python3 tools/drive_connector.py approve --moves DIR/moves.json
  python3 tools/drive_connector.py next --moves DIR/moves.json
  python3 tools/drive_connector.py done --moves DIR/moves.json --op N [--id NEW_ID]
  python3 tools/drive_connector.py undo --moves DIR/moves.json

The plan is the organizer's own JSON (drive_organize.schema), so its
projects open as proposed epics through the workflow's step open. moves
writes moves.json and MOVES.md: one folder "Symphony projects" at the
drive's top, one folder per project inside it, and each of a project's
folders and files moved into its project's folder. next prints the one call
to make, with every id filled in, and refuses until approve has been run,
which the session runs only on the owner's own word; done records what the
call gave. undo turns the moves that were made into a plan that moves each
item back to the folder it came from, under its own name, and deletes
nothing: an empty project folder is the owner's to delete.

A catalog and a plan name a person's files: keep them in the session's
scratchpad, never in a commit, and push them only to a private
repository's branch drive-catalog. Standard library only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import drive_organize  # noqa: E402

HOME = "Symphony projects"
MANAGED = drive_organize.MANAGED
MAX_OPS = 600


class ConnectorError(Exception):
    """A step that cannot go on, said in one line."""


# The plan

def lookup_of(made):
    return {entry["path"]: entry for entry in made["folders"] + made["files"]}


def check(plan, made):
    """What of the session's plan the catalog does not hold, project by
    project, so the session corrects its paths before anything opens."""
    lookup, report = lookup_of(made), []
    for project in plan.get("projects", []):
        slug = str(project.get("slug", ""))
        paths = list(project.get("folders", [])) + list(project.get("files", []))
        unknown = [p for p in paths if str(p).strip().strip("/") not in lookup]
        problems = []
        if not drive_organize.SLUG.fullmatch(slug):
            problems.append("the slug is not lowercase letters, digits and dashes")
        if not project.get("tasks"):
            problems.append("no tasks")
        if project.get("domain") not in drive_organize.DOMAINS:
            problems.append("a domain outside the list")
        repo = project.get("repository")
        if repo and not isinstance(repo, dict):
            problems.append("repository is not an object")
        elif repo and not drive_organize.REPO_NAME.fullmatch(str(repo.get("name", ""))):
            problems.append("a repository name GitHub would refuse")
        report.append({"slug": slug, "paths": len(paths), "unknown": unknown, "problems": problems})
    return report


# The moves

def folder_name(text):
    """A project's title as a OneDrive folder name."""
    cleaned = re.sub(r'[\x00-\x1f<>:"/\\|?*#%]', " ", str(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    return cleaned[:80] or "Project"


def free_name(name, taken):
    if name.lower() not in taken:
        taken.add(name.lower())
        return name
    stem, dot, ext = name.rpartition(".") if "." in name[1:] else (name, "", "")
    number = 2
    while f"{stem} ({number}){dot}{ext}".lower() in taken:
        number += 1
    taken.add(f"{stem} ({number}){dot}{ext}".lower())
    return f"{stem} ({number}){dot}{ext}"


def kept_by_apps(made):
    """The paths of the folders Microsoft 365's apps keep, read from each
    folder's name and parent, not from any list the catalog carries."""
    parents = made["parents"]
    return [f["path"] for f in made["folders"]
            if parents.get(f["id"]) == "root" and f["path"].rpartition("/")[2].strip().lower() in MANAGED]


def movable(entry, managed_paths):
    """Whether an entry may move: never the drive's top, a folder of the
    apps' own or what is inside one, nor what is in Symphony projects already."""
    path = entry["path"]
    if "/" not in path:
        return False
    first = path.split("/")[1]
    if first == HOME or any(path == m or path.startswith(m + "/") for m in managed_paths):
        return False
    return True


def plan_moves(plan, made):
    """The moves a plan asks for, in the order to make them: the home
    folder, each project's folder, then its items. An item inside another
    that moves goes with it, and an item two projects name goes to the first."""
    if made.get("provider") != "microsoft" or not isinstance(made.get("parents"), dict):
        raise ConnectorError("moves takes a OneDrive catalog that names each item's parent, as the workflow's step catalog writes it")
    lookup, parents, managed_paths = lookup_of(made), made["parents"], kept_by_apps(made)
    drive = next((e["drive"] for e in made["files"] + made["folders"] if e["drive"]), "")
    ops = [{"op": "create", "key": "home", "name": HOME, "parent": "root", "state": "todo"}]
    chosen, skipped, homes, slugs = [], [], set(), set()
    for project in plan.get("projects", [])[:drive_organize.MAX_PROJECTS]:
        slug = str(project.get("slug", ""))
        if not drive_organize.SLUG.fullmatch(slug) or slug in slugs:
            continue
        slugs.add(slug)
        for path in list(project.get("folders", [])) + list(project.get("files", [])):
            entry = lookup.get(str(path).strip().strip("/"))
            if entry is None:
                skipped.append(f"{path}: not in the catalog")
            elif not movable(entry, managed_paths):
                skipped.append(f"{entry['path']}: the drive's top, a folder of Microsoft 365's apps, or moved before")
            else:
                chosen.append((slug, project, entry))
    paths = sorted({c[2]["path"] for c in chosen})
    covered = {p for p in paths if any(p.startswith(q + "/") for q in paths if q != p)}
    taken, seen, made_for = {}, set(), set()
    for slug, project, entry in chosen:
        if entry["path"] in covered:
            skipped.append(f"{entry['path']}: moves with the folder that holds it")
            continue
        if entry["id"] in seen:
            skipped.append(f"{entry['path']}: named by two projects, goes to the first")
            continue
        seen.add(entry["id"])
        if slug not in made_for:
            made_for.add(slug)
            ops.append({"op": "create", "key": slug, "name": free_name(folder_name(project.get("title", slug)), homes),
                        "parent": "@home", "state": "todo"})
        name = entry["path"].rpartition("/")[2]
        actual = entry.get("name") or name
        new = free_name(actual, taken.setdefault(slug, set()))
        if not parents.get(entry["id"]):
            raise ConnectorError(f"the catalog names no parent for step {len(ops)}, so it could not be undone")
        ops.append({"op": "move", "item": entry["id"], "path": entry["path"], "to": f"@{slug}",
                    "name": actual, "new_name": new if new != actual else "",
                    "back": parents.get(entry["id"], ""), "state": "todo"})
    if len(ops) > MAX_OPS:
        raise ConnectorError(f"the plan asks for {len(ops)} steps, more than {MAX_OPS}: fewer, larger folders")
    return {"drive": drive, "approved": False, "ops": ops, "skipped": skipped, "ids": {}}


def moves_markdown(moves):
    lines = ["# What would move", "",
             f"{sum(op['op'] == 'move' for op in moves['ops'])} items into {HOME}/, "
             f"{sum(op['op'] == 'create' for op in moves['ops'])} new folders. Nothing has moved; "
             "the owner reads this and says go. Every move can be undone.", ""]
    names = {op["key"]: op["name"] for op in moves["ops"] if op["op"] == "create"}
    for number, op in enumerate(moves["ops"]):
        if op["op"] == "create":
            where = f"{HOME}/" if op["key"] == "home" else f"{HOME}/{op['name']}/"
            lines.append(f"{number}. new folder `{where}`")
            continue
        target = f"`{HOME}/{names[op['to'][1:]]}/`" if op["to"].startswith("@") else "the folder it came from"
        rename = f", renamed `{op['new_name']}`" if op["new_name"] else ""
        lines.append(f"{number}. move `{op['path']}` to {target}{rename}")
    if moves["skipped"]:
        lines += ["", "## Left where they are", ""] + [f"- {line}" for line in moves["skipped"]]
    return "\n".join(lines) + "\n"


def resolve(ref, ids):
    if ref == "root":
        return "root"
    if ref.startswith("@"):
        if ref[1:] not in ids:
            raise ConnectorError(f"step for {ref[1:]} has not been made yet")
        return ids[ref[1:]]
    return ref


def next_call(moves):
    """The one connector call to make next, or None when every step is done."""
    if not moves["approved"]:
        raise ConnectorError("the moves are not approved: show the owner MOVES.md and run approve only on their word")
    for number, op in enumerate(moves["ops"]):
        if op["state"] == "done":
            continue
        if op["op"] == "create":
            args = {"driveId": moves["drive"], "name": op["name"], "conflictBehavior": "fail"}
            parent = resolve(op["parent"], moves["ids"])
            if parent != "root":
                args["parentItemId"] = parent
            return {"op": number, "tool": "sharepoint_create_folder", "arguments": args,
                    "then": f"done --op {number} --id <the new folder's id>"}
        args = {"driveId": moves["drive"], "itemId": op["item"],
                "destinationParentItemId": resolve(op["to"], moves["ids"])}
        if op["new_name"]:
            args["newName"] = op["new_name"]
        return {"op": number, "tool": "sharepoint_move_item", "arguments": args, "then": f"done --op {number}"}
    return None


def done(moves, number, new_id=None):
    if not moves["approved"]:
        raise ConnectorError("the moves are not approved, so no step has been made")
    if not 0 <= number < len(moves["ops"]):
        raise ConnectorError(f"there is no step {number}")
    op = moves["ops"][number]
    if op["op"] == "create":
        if not new_id or not re.fullmatch(r"[A-Za-z0-9!_.-]{1,200}", new_id):
            raise ConnectorError("a new folder's step needs --id, the id the connector gave it")
        moves["ids"][op["key"]] = new_id
    op["state"] = "done"
    return moves


def undo(moves):
    """A plan that moves back each item that moved, last first, to the
    folder it came from under its own name. It creates and deletes nothing;
    the empty folders are listed for the owner."""
    ops = []
    for op in reversed(moves["ops"]):
        if op["op"] == "move" and op["state"] == "done" and op["back"]:
            ops.append({"op": "move", "item": op["item"], "path": f"{HOME}/.../{op['new_name'] or op['name']}",
                        "to": op["back"], "name": op["new_name"] or op["name"],
                        "new_name": op["name"] if op["new_name"] else "", "back": "", "state": "todo"})
    empty = [op["name"] for op in moves["ops"] if op["op"] == "create" and op["state"] == "done"]
    return {"drive": moves["drive"], "approved": False, "ops": ops, "ids": {},
            "skipped": [f"{name}: a folder this made, left for the owner to delete if it is empty" for name in empty]}


# The command line

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "moves"):
        command = sub.add_parser(name)
        command.add_argument("--plan", required=True)
        command.add_argument("--catalog", required=True)
        command.add_argument("--out", required=name == "moves")
    for name in ("approve", "next", "undo"):
        sub.add_parser(name).add_argument("--moves", required=True)
    recording = sub.add_parser("done")
    recording.add_argument("--moves", required=True)
    recording.add_argument("--op", required=True, type=int)
    recording.add_argument("--id")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args), indent=1))
    except (ConnectorError, KeyError, ValueError, OSError) as problem:
        print(f"drive_connector: {problem}", file=sys.stderr)
        return 1
    return 0


def run(args):
    if args.command == "check":
        return check(load(args.plan), load(args.catalog))
    if args.command == "moves":
        moves = plan_moves(load(args.plan), load(args.catalog))
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        save(out / "moves.json", moves)
        (out / "MOVES.md").write_text(moves_markdown(moves), encoding="utf-8")
        return {"steps": len(moves["ops"]), "skipped": len(moves["skipped"]), "review": str(out / "MOVES.md")}
    moves = load(args.moves)
    if args.command == "approve":
        moves["approved"] = True
        save(args.moves, moves)
        return {"approved": True, "steps": len(moves["ops"])}
    if args.command == "next":
        return next_call(moves) or {"done": True}
    if args.command == "done":
        save(args.moves, done(moves, args.op, args.id))
        return next_call(moves) or {"done": True}
    back = undo(moves)
    target = Path(args.moves).with_name("undo.json")
    if target.exists():
        raise ConnectorError(f"{target} is there already, with its own progress: run it, or move it away first")
    save(target, back)
    (target.with_name("UNDO.md")).write_text(moves_markdown(back).replace("What would move", "What would move back"),
                                             encoding="utf-8")
    return {"steps": len(back["ops"]), "plan": str(target)}


if __name__ == "__main__":
    sys.exit(main())
