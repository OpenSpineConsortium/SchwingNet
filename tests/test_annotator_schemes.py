"""The annotator-landmark registry holds together with the code it names.

docs/research/annotator-landmarks/schemes.json names, for every point a reader marks on a film,
its counterpart in 3-D: one of the QA loop's 18 landmarks (tools/qaloop_gates.py LANDMARKS), a
construction of the vendored morphometry engine (grid/bordercall/morphometry), or a construction
still to be built. A counterpart that names a landmark or a function the code does not have would
send the next session to nothing, so the names are read from the source files themselves, with
no import, which keeps the test running where numpy is missing, as on CI's python3.
"""

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMES = ROOT / "docs" / "research" / "annotator-landmarks" / "schemes.json"
GATES = ROOT / "tools" / "qaloop_gates.py"
ENGINE = ROOT / "grid" / "bordercall" / "morphometry"
QALOOP_REF = re.compile(r"qaloop:([A-Za-z_]+\.[A-Za-z_]+)")
ENGINE_REF = re.compile(r"engine:([a-z_]+)\.([A-Za-z_0-9]+)")
SOURCES = ("qaloop:", "engine:", "new: ")
KINDS = ("fixed", "silhouette")
SCHEME_FIELDS = ("key", "name", "citation", "view", "landmarks", "datasets")
LANDMARK_FIELDS = ("name", "definition", "counterpart_3d", "fixed_or_silhouette")
DATASET_FIELDS = ("name", "held", "images", "format")
DATA_ROOT = "/rs/rs_grp_oschome/go2432/data/"


def qaloop_landmarks():
    """The names in tools/qaloop_gates.py's LANDMARKS tuple, read from its source."""
    tree = ast.parse(GATES.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "LANDMARKS" for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise AssertionError("tools/qaloop_gates.py defines no LANDMARKS")


def engine_functions(module):
    """The top-level functions and classes of one module of the vendored engine."""
    path = ENGINE / (module + ".py")
    if not path.is_file():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


class SchemesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemes = json.loads(SCHEMES.read_text(encoding="ascii"))["schemes"]
        cls.points = [(s["key"], p) for s in cls.schemes for p in s["landmarks"]]

    def test_every_scheme_entry_has_its_fields(self):
        keys = [s["key"] for s in self.schemes]
        self.assertEqual(len(keys), len(set(keys)), "a scheme key is used twice")
        for s in self.schemes:
            for field in SCHEME_FIELDS:
                self.assertIn(field, s, s.get("key"))
            self.assertTrue(s["landmarks"], s["key"])
            for p in s["landmarks"]:
                for field in LANDMARK_FIELDS:
                    self.assertIn(field, p, (s["key"], p.get("name")))
            for d in s["datasets"]:
                for field in DATASET_FIELDS:
                    self.assertIn(field, d, (s["key"], d.get("name")))

    def test_held_is_a_path_under_the_data_root_or_false(self):
        for s in self.schemes:
            for d in s["datasets"]:
                held = d["held"]
                self.assertTrue(held is False or (isinstance(held, str) and held.startswith(DATA_ROOT)),
                                (s["key"], d["name"], held))

    def test_every_point_is_fixed_or_silhouette(self):
        for key, p in self.points:
            self.assertTrue(p["fixed_or_silhouette"].startswith(KINDS), (key, p["name"]))

    def test_every_counterpart_says_where_it_comes_from(self):
        for key, p in self.points:
            self.assertTrue(p["counterpart_3d"].startswith(SOURCES), (key, p["name"], p["counterpart_3d"]))

    def test_qaloop_counterparts_are_landmarks_the_loop_places(self):
        names = qaloop_landmarks()
        self.assertEqual(len(names), 18)
        for key, p in self.points:
            for name in QALOOP_REF.findall(p["counterpart_3d"]):
                self.assertIn(name, names, (key, p["name"]))

    def test_engine_counterparts_are_constructions_the_engine_has(self):
        seen = 0
        for key, p in self.points:
            for module, function in ENGINE_REF.findall(p["counterpart_3d"]):
                seen += 1
                self.assertIn(function, engine_functions(module), (key, p["name"], module))
        self.assertGreater(seen, 0)


if __name__ == "__main__":
    unittest.main()
