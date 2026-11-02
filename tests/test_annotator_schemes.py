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
# Every "qaloop:" or "engine:" in a counterpart is read as one reference, the name running from the colon to the
# first space, comma, semicolon or bracket; a reference that does not have the shape below is an error in itself,
# so a misspelt or empty one fails rather than passing unread.
REFERENCE = re.compile(r"\b(qaloop|engine):([^\s,;()]*)")
QALOOP_NAME = re.compile(r"[a-z_]+\.[a-z_]+")
ENGINE_NAME = re.compile(r"([a-z_]+)\.([A-Za-z_][A-Za-z_0-9]*)")
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


def references(text):
    """The (source, name) of every qaloop: and engine: reference in a counterpart's text."""
    return REFERENCE.findall(text)


def reference_problems(text, landmarks, functions_of):
    """What is wrong with a counterpart's references: a name of the wrong shape, a landmark the loop does not place,
    or an engine function its module does not define. Empty when every reference holds."""
    problems = []
    for source, name in references(text):
        if source == "qaloop":
            if not QALOOP_NAME.fullmatch(name):
                problems.append("qaloop reference %r is not a landmark's name" % name)
            elif name not in landmarks:
                problems.append("qaloop:%s is not one of the 18 LANDMARKS" % name)
            continue
        shape = ENGINE_NAME.fullmatch(name)
        if not shape:
            problems.append("engine reference %r is not module.function" % name)
        elif shape.group(2) not in functions_of(shape.group(1)):
            problems.append("engine:%s is not defined in grid/bordercall/morphometry/%s.py" % (name, shape.group(1)))
    return problems


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

    def test_the_loop_places_18_landmarks(self):
        self.assertEqual(len(qaloop_landmarks()), 18)

    def test_every_reference_names_a_landmark_or_an_engine_construction(self):
        names = qaloop_landmarks()
        sources = set()
        for key, p in self.points:
            for source, _ in references(p["counterpart_3d"]):
                sources.add(source)
            self.assertEqual(reference_problems(p["counterpart_3d"], names, engine_functions), [], (key, p["name"]))
        self.assertEqual(sources, {"qaloop", "engine"}, "the registry names no landmark or no engine construction")

    def test_a_reference_of_the_wrong_shape_is_caught(self):
        names = qaloop_landmarks()
        for bad in ("qaloop: endplate.right", "qaloop:endplate2.right", "qaloop:endplate.rigth", "qaloop:",
                    "engine:Pelvis.socket_centre", "engine: pelvis.socket_centre", "engine:pelvis.socket_center",
                    "engine:pelvis", "new: x (engine:pelvis.socket_center)"):
            self.assertTrue(reference_problems(bad, names, engine_functions), bad)
        for good in ("qaloop:endplate.right", "engine:pelvis.socket_centre", "engine:column.wall_corner(top)",
                     "new: x (engine:pelvis.s1_plate gives its centre); qaloop:h_post.inferior"):
            self.assertEqual(reference_problems(good, names, engine_functions), [], good)


if __name__ == "__main__":
    unittest.main()
