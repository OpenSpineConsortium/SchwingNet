"""tools/drive_connector.py: a plan checked against the catalog the
organizer's Graph walk writes, and the plan's moves written for the owner to
read, made one call at a time only once approved, and undone back to where
each item came from. Every name here is made up."""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import drive_connector  # noqa: E402
import drive_organize  # noqa: E402

DRIVE = "b!fakeDriveId-0123456789"


def item(number):
    """A business OneDrive item id: 01 and 32 capitals or digits."""
    return "01" + f"{number:032d}".replace("0", "A")


TREE = {"root": [("Budget 2026", "folder", 0, 1), ("Novel", "folder", 0, 2), ("Recordings", "folder", 0, 3),
                 ("loose.txt", "file", 12, 4)],
        item(1): [("ledger.xlsx", "file", 2048, 11), ("Receipts", "folder", 0, 12)],
        item(2): [("chapter 1.docx", "file", 900, 21), ("cover.psd", "file", 5000, 22)],
        item(3): [("call.mp4", "file", 9, 51)],
        item(12): [("r1.pdf", "file", 300, 31)]}


class MemoryOneDrive:
    """Answers as drive_sync.Microsoft does, from TREE and its extras."""

    def __init__(self, extra=None):
        self.kids = {key: list(value) for key, value in TREE.items()}
        for key, value in (extra or {}).items():
            self.kids.setdefault(key, []).extend(value)
        self.read = []

    def graph(self, name, kind, size, number):
        found = {"id": item(number), "name": name, "size": size, "parentReference": {"driveId": DRIVE},
                 "lastModifiedDateTime": "2026-09-01T00:00:00Z", "webUrl": f"https://example.invalid/{number}"}
        found[kind] = {} if kind == "folder" else {"mimeType": "application/octet-stream"}
        return found

    def meta(self, drive, item_id):
        return {"id": "01ROOT", "name": "root", "folder": {}, "parentReference": {"driveId": DRIVE}}

    def children(self, drive, item_id):
        self.read.append(item_id)
        return [self.graph(*entry) for entry in self.kids.get(item_id, [])]


def plan(*projects):
    return {"summary": "s", "unsorted": [], "directions": [], "projects": list(projects)}


def project(slug, title, *paths, repository=None):
    found = {"slug": slug, "title": title, "domain": "accounting", "summary": "s", "folders": list(paths),
             "files": [], "directions": ["d"], "plan": "p",
             "tasks": [{"title": "t", "owner": "", "files": [], "body": "b"}]}
    if repository:
        found["repository"] = repository
    return found


class Drive(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def catalog(self, extra=None):
        self.drive = MemoryOneDrive(extra)
        found, problems, stopped = drive_organize.walk("microsoft", self.drive, [{"id": "root", "name": "OneDrive"}])
        return drive_organize.catalog_of("microsoft", found, problems, stopped)


class Catalog(Drive):
    def test_the_graph_walk_names_each_parent_and_the_apps_folders(self):
        made = self.catalog()
        paths = {f["path"] for f in made["files"]}
        self.assertIn("OneDrive/Budget 2026/Receipts/r1.pdf", paths)
        self.assertEqual(made["parents"][item(12)], item(1))
        self.assertEqual(made["parents"][item(1)], "root")
        self.assertEqual(made["managed"], ["OneDrive/Recordings"])
        self.assertNotIn(item(3), self.drive.read)
        self.assertNotIn("OneDrive/Recordings/call.mp4", paths)
        self.assertTrue(made["complete"])

    def test_the_drives_top_named_by_its_own_id_is_root_too(self):
        class ByOwnId(MemoryOneDrive):
            def meta(self, drive, item_id):
                return {"id": "01ROOT", "name": "root", "folder": {}, "root": {}, "parentReference": {"driveId": DRIVE}}

            def children(self, drive, item_id):
                return super().children(drive, "root" if item_id == "root" else item_id)

        found, _, _ = drive_organize.walk("microsoft", ByOwnId(), [{"id": "01ROOT", "name": "OneDrive", "drive": DRIVE}])
        made = drive_organize.catalog_of("microsoft", found, [], False)
        self.assertEqual(made["parents"][item(1)], "root")
        self.assertEqual(made["managed"], ["OneDrive/Recordings"])

    def test_check_names_the_paths_the_catalog_lacks(self):
        made = self.catalog()
        self.assertIn("repository is not an object",
                      drive_connector.check(plan(project("b", "B", repository="x")), made)[0]["problems"])
        report = drive_connector.check(plan(project("books", "Books", "OneDrive/Novel", "OneDrive/Nowhere",
                                                    repository={"name": "bad name", "team": True, "why": "w"})),
                                       made)
        self.assertEqual(report[0]["unknown"], ["OneDrive/Nowhere"])
        self.assertIn("a repository name GitHub would refuse", report[0]["problems"])


class Moves(Drive):
    def moves(self, *projects):
        return drive_connector.plan_moves(plan(*projects), self.catalog())

    def test_each_project_gets_a_folder_and_its_items_move_into_it(self):
        moves = self.moves(project("budget", "Budget: 2026/27", "OneDrive/Budget 2026"),
                           project("novel", "The novel", "OneDrive/Novel/chapter 1.docx"))
        kinds = [(op["op"], op.get("name")) for op in moves["ops"]]
        self.assertEqual(kinds, [("create", "Symphony projects"), ("create", "Budget 2026 27"),
                                 ("move", "Budget 2026"), ("create", "The novel"), ("move", "chapter 1.docx")])
        self.assertEqual(moves["ops"][2]["back"], "root")
        self.assertEqual(moves["ops"][4]["back"], item(2))
        self.assertFalse(moves["approved"])

    def test_what_may_not_move_stays_and_is_said(self):
        moves = self.moves(project("a", "A", "OneDrive", "OneDrive/Recordings", "OneDrive/Budget 2026",
                                   "OneDrive/Budget 2026/ledger.xlsx", "OneDrive/Gone"),
                           project("b", "B", "OneDrive/Budget 2026"))
        moved = [op["path"] for op in moves["ops"] if op["op"] == "move"]
        self.assertEqual(moved, ["OneDrive/Budget 2026"])
        said = " ".join(moves["skipped"])
        for words in ("OneDrive: the drive's top", "OneDrive/Recordings", "moves with the folder that holds it",
                      "OneDrive/Gone: not in the catalog", "named by two projects"):
            self.assertIn(words, said)

    def test_moves_take_only_a_catalog_that_names_parents(self):
        made = self.catalog()
        for key in ("parents", "provider"):
            broken = {k: v for k, v in made.items() if k != key}
            with self.assertRaises(drive_connector.ConnectorError):
                drive_connector.plan_moves(plan(project("a", "A", "OneDrive/Novel")), broken)
        made["managed"] = []
        moves = drive_connector.plan_moves(plan(project("a", "A", "OneDrive/Recordings")), made)
        self.assertEqual([op for op in moves["ops"] if op["op"] == "move"], [])

    def test_a_slug_twice_is_planned_once(self):
        moves = self.moves(project("a", "A", "OneDrive/Gone"), project("a", "A again", "OneDrive/Novel"))
        self.assertEqual([op for op in moves["ops"] if op["op"] == "move"], [])

    def test_nothing_is_recorded_done_before_approval_and_undo_keeps_its_progress(self):
        moves = self.moves(project("budget", "Budget", "OneDrive/Budget 2026"))
        with self.assertRaises(drive_connector.ConnectorError):
            drive_connector.done(moves, 0, "HOME1")
        path = self.dir / "moves.json"
        path.write_text(json.dumps(moves))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(drive_connector.main(["undo", "--moves", str(path)]), 0)
            self.assertEqual(drive_connector.main(["undo", "--moves", str(path)]), 1)

    def test_a_name_twice_in_one_project_is_renamed(self):
        made = self.catalog({item(1): [("notes.txt", "file", 1, 41)], item(2): [("notes.txt", "file", 1, 42)]})
        moves = drive_connector.plan_moves(plan(project("n", "Notes", "OneDrive/Budget 2026/notes.txt",
                                                        "OneDrive/Novel/notes.txt")), made)
        self.assertEqual([op["new_name"] for op in moves["ops"] if op["op"] == "move"], ["", "notes (2).txt"])

    def test_nothing_is_called_until_approved_then_one_step_at_a_time(self):
        moves = self.moves(project("budget", "Budget", "OneDrive/Budget 2026"))
        with self.assertRaises(drive_connector.ConnectorError):
            drive_connector.next_call(moves)
        moves["approved"] = True
        call = drive_connector.next_call(moves)
        self.assertEqual(call["tool"], "sharepoint_create_folder")
        self.assertNotIn("parentItemId", call["arguments"])
        with self.assertRaises(drive_connector.ConnectorError):
            drive_connector.done(moves, 0)
        drive_connector.done(moves, 0, "HOME1")
        self.assertEqual(drive_connector.next_call(moves)["arguments"]["parentItemId"], "HOME1")
        drive_connector.done(moves, 1, "PROJ1")
        call = drive_connector.next_call(moves)
        self.assertEqual(call["arguments"], {"driveId": DRIVE, "itemId": item(1), "destinationParentItemId": "PROJ1"})
        drive_connector.done(moves, 2)
        self.assertIsNone(drive_connector.next_call(moves))

    def test_undo_moves_back_what_moved_and_deletes_nothing(self):
        made = self.catalog({item(1): [("notes.txt", "file", 1, 41)], item(2): [("notes.txt", "file", 1, 42)]})
        moves = drive_connector.plan_moves(plan(project("n", "Notes", "OneDrive/Budget 2026/notes.txt",
                                                        "OneDrive/Novel/notes.txt")), made)
        moves["approved"] = True
        drive_connector.done(moves, 0, "HOME1")
        drive_connector.done(moves, 1, "PROJ1")
        drive_connector.done(moves, 2)
        drive_connector.done(moves, 3)
        back = drive_connector.undo(moves)
        self.assertEqual([(op["item"], op["to"], op["new_name"]) for op in back["ops"]],
                         [(item(42), item(2), "notes.txt"), (item(41), item(1), "")])
        self.assertFalse(back["approved"])
        self.assertEqual(len(back["skipped"]), 2)
        self.assertNotIn("delete", json.dumps(back["ops"]))
        self.assertIn("the folder it came from", drive_connector.moves_markdown(back))

    def test_the_command_line_writes_the_review_and_refuses_unapproved(self):
        out = self.dir / "out"
        out.mkdir()
        (out / "catalog.json").write_text(json.dumps(self.catalog()))
        plan_path = self.dir / "plan.json"
        plan_path.write_text(json.dumps(plan(project("budget", "Budget", "OneDrive/Budget 2026"))))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(drive_connector.main(["moves", "--plan", str(plan_path), "--catalog",
                                                   str(out / "catalog.json"), "--out", str(out)]), 0)
            self.assertEqual(drive_connector.main(["next", "--moves", str(out / "moves.json")]), 1)
        self.assertIn("not approved", err.getvalue())
        self.assertIn("move `OneDrive/Budget 2026` to `Symphony projects/Budget/`", (out / "MOVES.md").read_text())


if __name__ == "__main__":
    unittest.main()
