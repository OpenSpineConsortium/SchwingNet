"""tools/organization_map.py: the map in the tree holds together, and a map
that does not is refused with each problem named, so the control panel's
Organization tab never draws a gap the check could have caught first."""

import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import organization_map  # noqa: E402

SMALL = {
    "about": "a map", "owner": "acme", "written": "2026-10-29",
    "edge_reads": "from depends on to",
    "kinds": {"vendors": "takes a copy of"},
    "groups": {"core": "the core", "systems": "outside GitHub"},
    "nodes": [
        {"name": "a", "group": "core", "visibility": "private", "role": "the project"},
        {"name": "lib", "group": "core", "visibility": "public", "role": "the library"},
        {"name": "the grid", "group": "systems", "kind": "system", "role": "a cluster"},
    ],
    "edges": [{"from": "a", "to": "lib", "kind": "vendors", "what": "tools/lib", "by": "VENDORED"}],
}


def problems(data):
    return organization_map.problems_of(copy.deepcopy(data))


def checked(argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = organization_map.main(argv)
    return code, out.getvalue()


class TheMapInTheTree(unittest.TestCase):
    def test_holds_together(self):
        code, said = checked(["check"])
        self.assertEqual(code, 0, said)
        self.assertIn("hold together", said)

    def test_the_file_is_ascii_with_sorted_keys_on_every_node_and_edge(self):
        text = organization_map.MAP.read_text(encoding="utf-8")
        self.assertTrue(text.isascii(), "the map is a document and stays ASCII")
        data = json.loads(text)
        for node in data["nodes"]:
            self.assertEqual(node["name"], node["name"].strip())
        self.assertEqual(data["owner"], "OpenSpineConsortium")


class ABrokenMap(unittest.TestCase):
    def test_a_sound_map_has_no_problem(self):
        self.assertEqual(problems(SMALL), [])

    def test_an_edge_to_a_node_that_is_not_there(self):
        data = copy.deepcopy(SMALL)
        data["edges"].append({"from": "a", "to": "ghost", "kind": "vendors", "what": "x"})
        self.assertEqual(problems(data), ["edge a -> ghost names a node that is not there: 'ghost'"])

    def test_a_kind_the_file_does_not_list(self):
        data = copy.deepcopy(SMALL)
        data["edges"][0]["kind"] = "owes"
        self.assertEqual(problems(data), ["edge a -> lib has a kind the file does not list: 'owes'"])

    def test_an_edge_listed_twice_and_one_that_says_nothing(self):
        data = copy.deepcopy(SMALL)
        data["edges"].append(dict(data["edges"][0], what=" "))
        self.assertEqual(problems(data), ["edge a -> lib is listed twice as vendors",
                                          "edge a -> lib does not say what passes"])

    def test_a_name_used_twice_and_a_group_not_listed(self):
        data = copy.deepcopy(SMALL)
        data["nodes"].append({"name": "a", "group": "elsewhere", "visibility": "public", "role": "again"})
        self.assertEqual(problems(data), ["node a is named twice",
                                          "node a has a group the file does not list: 'elsewhere'"])

    def test_a_repository_must_say_its_visibility_and_its_role(self):
        data = copy.deepcopy(SMALL)
        del data["nodes"][0]["visibility"]
        data["nodes"][1]["role"] = ""
        self.assertEqual(problems(data), ["node a must say public, internal or private, or be a system",
                                          "node lib has no role"])

    def test_a_system_needs_no_visibility(self):
        data = copy.deepcopy(SMALL)
        data["nodes"][2].pop("role")
        self.assertEqual(problems(data), [])

    def test_a_missing_key_is_named_before_anything_else(self):
        data = copy.deepcopy(SMALL)
        del data["edges"]
        data["nodes"] = "not a list"
        self.assertEqual(problems(data), ["the key edges is missing"])

    def test_check_names_the_file_and_exits_1(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "map.json"
            data = copy.deepcopy(SMALL)
            data["edges"][0]["to"] = "a"
            path.write_text(json.dumps(data), encoding="utf-8")
            code, said = checked(["check", str(path)])
            self.assertEqual(code, 1)
            self.assertEqual(said, f"{path}: edge a -> a joins a node to itself\n")
            path.write_text("{not json", encoding="utf-8")
            code, said = checked(["check", str(path)])
        self.assertEqual(code, 1)
        self.assertTrue(said.startswith(f"{path}: "))

    def test_any_other_word_prints_the_usage(self):
        code, said = checked(["draw"])
        self.assertEqual(code, 2)
        self.assertIn("usage:", said)


if __name__ == "__main__":
    unittest.main()
