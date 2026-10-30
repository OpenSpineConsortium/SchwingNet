"""Tests of tools/pipeline_sandbox.py, the pipeline sandbox's rules in Python: the contract against the
recipes, every block and template under tools/sandbox/, the manifest check on one broken manifest per
problem code, the experiment route's requests against the experiments panel, the page as section 16 of
the sandbox's contract assembles it, and, where node is installed, the JavaScript engine giving the same
results on the same pipelines and manifests."""

import copy
import importlib.util
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "pipeline_sandbox.py"
ENGINE = ROOT / "tools" / "sandbox" / "engine.js"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sandbox = load("pipeline_sandbox")
panel = sandbox.panel

# Every problem code of the manifest check (section 13).
MANIFEST_CODES = {"id", "field", "port", "accepts", "op", "ref", "param", "rule", "reads", "job", "determinism",
                  "generic", "needs", "code", "today", "text", "size", "card"}


def probe(name, axes, sizes, dtype):
    """A probe type as the contract holds one: a full type record with level targets and all three parts."""
    return {"name": name, "type": {"kind": "data", "axes": axes, "sizes": sizes, "dtype": dtype, "targets": "level",
                                   "classes": 27, "parts": ["train", "validation", "test"], "persons": True,
                                   "modality": "any", "licence": "uncut", "sources": [], "family": None,
                                   "rank": len([a for a in axes if a in "DHW"]), "trained": False}}


def fixture_contract():
    """A contract of section 3's shape, kept here so that the manifest tests stand without DATA's files."""
    return {
        "contract": 1,
        "stages": [{"id": stage, "title": stage.title(), "what": f"the {stage} stage"} for stage in sandbox.STAGES],
        "kinds": {kind: f"a {kind}" for kind in sandbox.KINDS},
        "axes": {axis: f"the axis {axis}" for axis in sandbox.AXES},
        "spatial": ["D", "H", "W"], "dtypes": list(sandbox.DTYPES), "targets": list(sandbox.TARGETS),
        "parts": list(sandbox.PARTS), "modalities": list(sandbox.MODALITIES), "licences": list(sandbox.LICENCES),
        "job_classes": list(sandbox.JOB_CLASSES), "today": list(sandbox.TODAY), "code": list(sandbox.CODE),
        "deterministic": list(sandbox.DETERMINISTIC), "needs": list(sandbox.NEEDS), "glyphs": list(sandbox.GLYPHS),
        "limits": dict(sandbox.LIMITS),
        "probes": [probe("frames, 2-D grey 64", ["N", "C", "H", "W"], {"C": 1, "H": 64, "W": 64}, "uint8"),
                   probe("frames, 2-D colour 224", ["N", "C", "H", "W"], {"C": 3, "H": 224, "W": 224}, "float32"),
                   probe("volumes, 3-D grey 96", ["N", "C", "D", "H", "W"], {"C": 1, "D": 96, "H": 96, "W": 96}, "int16"),
                   probe("clips, 2-D grey", ["N", "T", "C", "H", "W"], {"T": 16, "C": 1, "H": 64, "W": 64}, "uint8"),
                   probe("a table", ["N", "F"], {"F": 32}, "float32")],
        "requirements": [],
    }


def good_manifest():
    """A block that keeps every rule: a crop over any data with H and W, seeded, generic over every rank."""
    return {
        "block": 1, "id": "crop_test", "version": 1, "title": "Crop for a test", "stage": "prepare",
        "summary": "Crops every sample to a square of the given size.",
        "does": "A block of the tests: it takes any data with H and W axes and crops both to the size.",
        "glyph": "crop",
        "inputs": [{"name": "data", "accepts": {"kind": ["data"], "has_axes": ["H", "W"]}, "optional": False,
                    "what": "the samples"}],
        "outputs": [{"name": "crops", "from": "data", "ops": [["size", "H", "@param.size"], ["size", "W", "@param.size"]],
                     "what": "the crops"}],
        "params": [
            {"name": "size", "kind": "int", "low": 8, "high": 512, "default": 64, "vary": True, "what": "the side"},
            {"name": "mode", "kind": "choice", "choices": ["centre", "random"], "default": "centre", "vary": True},
            {"name": "jitter", "kind": "float", "low": 0, "high": 1, "default": 0.0, "vary": False},
            {"name": "seed", "kind": "int", "low": 0, "high": 999, "default": 1},
        ],
        "rules": [{"when": {"jitter": {"above": 0}}, "need": {"mode": {"in": ["random"]}},
                   "say": "jitter above 0 needs mode=random"}],
        "reads": {"parts": []},
        "job": {"class": "cpu", "hours": 1, "cpus": 2, "memory_gb": 8, "with_upstream": False, "array": False},
        "deterministic": "seeded", "seed_param": "seed", "nondeterminism": "",
        "generic": {"rank": [1, 2, 3], "time": "any", "channels": "any", "sizes": "any", "why": ""},
        "resolve": None,
        "needs": ["python", "numpy"],
        "code": "existing", "implemented_by": ["tools/pipeline_sandbox.py"],
        "today": {"status": "word", "route": "", "word": "census gold3", "flow": "", "note": ""},
        "experiment": None,
        "card": None,
    }


def set_in(manifest, path, value):
    """Sets one place of a manifest, named as a list of keys and indices."""
    target = manifest
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def broken(*changes):
    """The good manifest with each (path, value) set."""
    manifest = good_manifest()
    for path, value in changes:
        set_in(manifest, path, value)
    return manifest


def with_extra_output():
    manifest = good_manifest()
    manifest["outputs"].append(copy.deepcopy(manifest["outputs"][0]))
    return manifest


def with_extra_op():
    manifest = good_manifest()
    manifest["outputs"][0]["ops"].append(["grow", "H"])
    return manifest


def with_key(key, value):
    manifest = good_manifest()
    manifest[key] = value
    return manifest


# One mutation of the good manifest per problem, each with every (code, field) pair it must give.
MUTATIONS = [
    ("id", lambda: broken((["id"], "Bad Id")), [("id", "id")]),
    ("block", lambda: broken((["block"], 2)), [("field", "block")]),
    ("version", lambda: broken((["version"], 0)), [("field", "version")]),
    ("title", lambda: broken((["title"], "")), [("field", "title")]),
    ("stage", lambda: broken((["stage"], "nowhere")), [("field", "stage")]),
    ("summary", lambda: broken((["summary"], "x" * 121)), [("field", "summary")]),
    ("does", lambda: broken((["does"], "")), [("field", "does")]),
    ("glyph", lambda: broken((["glyph"], "nope")), [("field", "glyph")]),
    ("resolve", lambda: broken((["resolve"], 5)), [("field", "resolve")]),
    ("experiment", lambda: broken((["experiment"], 5)), [("field", "experiment")]),
    ("input optional", lambda: broken((["inputs", 0, "optional"], "yes")), [("port", "inputs")]),
    ("output twice", with_extra_output, [("port", "outputs")]),
    ("accepts key", lambda: broken((["inputs", 0, "accepts", "colour"], ["red"])), [("accepts", "inputs")]),
    ("unknown op", with_extra_op, [("op", "outputs")]),
    ("ref", lambda: broken((["outputs", 0, "ops", 0], ["size", "H", "@param.nothing"])), [("ref", "outputs")]),
    ("default", lambda: broken((["params", 0, "default"], 9999)), [("param", "params")]),
    ("rule", lambda: broken((["rules", 0, "when"], {"nothing": {"above": 0}})), [("rule", "rules")]),
    ("reads test", lambda: broken((["reads", "parts"], ["test"])), [("reads", "reads")]),
    ("cpus", lambda: broken((["job", "cpus"], 0)), [("job", "job")]),
    ("deterministic", lambda: broken((["deterministic"], "maybe")), [("determinism", "deterministic")]),
    ("seed_param", lambda: broken((["seed_param"], "mode")), [("determinism", "seed_param")]),
    ("nondeterminism", lambda: broken((["deterministic"], "declared"), (["nondeterminism"], "short")),
     [("determinism", "nondeterminism")]),
    ("generic why", lambda: broken((["generic", "rank"], [2])), [("generic", "generic")]),
    ("probe", lambda: broken((["inputs", 0, "accepts", "dtype"], ["float32"])), [("generic", "generic")]),
    ("needs", lambda: broken((["needs"], ["python", "tensorflow"])), [("needs", "needs")]),
    ("implemented_by", lambda: broken((["implemented_by"], [])), [("code", "implemented_by")]),
    ("planned code", lambda: broken((["code"], "planned")), [("code", "code")]),
    ("pending", lambda: broken((["today", "status"], "pending")), [("today", "today")]),
    ("pending, no pull request", lambda: broken((["code"], "planned"), (["implemented_by"], []),
                                               (["today", "status"], "pending")), [("today", "today")]),
    ("masks, not float32", lambda: broken((["inputs", 0, "accepts", "targets"], ["mask"]),
                                          (["inputs", 0, "accepts", "dtype"], ["float32"])), [("generic", "generic")]),
    ("planned today", lambda: broken((["today", "status"], "planned")), [("today", "today")]),
    ("non-ASCII", lambda: broken((["summary"], "Crops caf\u00e9 samples.")), [("text", "summary")]),
    ("key", lambda: with_key("caf\u00e9", 1), [("text", None)]),
    ("size", lambda: broken((["params", 0, "what"], "x" * 17000)), [("size", None)]),
    ("card", lambda: broken((["card"], {"origin": "here"})), [("card", "card")]),
    ("not an object", lambda: ["a", "list"], [("field", None)]),
]


# Variants of the good manifest that keep every rule: planned code that an unmerged pull request builds
# (pending, the note naming it), and a first input that asks for masks or for data not split yet, which
# R8's probes take on, since they hold the shapes a block takes and not what its data means.
ACCEPTED = [
    ("planned code a pull request builds", lambda: broken((["code"], "planned"), (["implemented_by"], []),
                                                          (["today", "status"], "pending"),
                                                          (["today", "note"], "Built on the unmerged pull request #483."))),
    ("masks", lambda: broken((["inputs", 0, "accepts", "targets"], ["mask"]))),
    ("points or masks", lambda: broken((["inputs", 0, "accepts", "targets"], ["points", "mask"]))),
    ("not split yet", lambda: broken((["inputs", 0, "accepts", "parts"], "unsplit"))),
]


def pairs(problems):
    """The sorted (code, field) pairs of a manifest's problems, the comparison section 13 asks for."""
    return sorted(((p["code"], p["field"]) for p in problems), key=lambda pair: (pair[0], pair[1] or ""))


def problem_tuples(problems):
    """Each problem as (code, node, port, field, level), sorted, the comparison section 10 asks for."""
    rows = [tuple(p.get(key) for key in ("code", "node", "port", "field", "level")) for p in problems]
    return sorted(rows, key=lambda row: tuple("\0" if v is None else str(v) for v in row))


def as_json(value):
    """A result as JSON carries it: undefined left out of objects, a whole float written as an int."""
    return whole_numbers(sandbox.plain(value))


def whole_numbers(value):
    """Numbers as both engines' JSON compares them: a whole number within 2 ** 53 as an int, any other as a
    double, so the digits JSON.stringify writes for a double past 2 ** 53 read as that same double."""
    if isinstance(value, float) and value.is_integer() and abs(value) <= 2 ** 53:
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2 ** 53:
        return float(value)
    if isinstance(value, dict):
        return {key: whole_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [whole_numbers(item) for item in value]
    return value


def real_data():
    data, problems = sandbox.sandbox_data(ROOT)
    if data is None or problems:
        raise AssertionError(f"tools/sandbox/ cannot be read: {problems}")
    return data


def template(data, template_id):
    return copy.deepcopy(next(t for t in data["templates"] if t["id"] == template_id))


def node_of(spec, block_id):
    return next(n for n in spec["nodes"] if n["block"] == block_id)


class NumbersAndText(unittest.TestCase):
    def test_numbers_are_written_as_python_writes_them(self):
        self.assertEqual(sandbox.format_number(0.0078125), "0.007812")
        self.assertEqual(sandbox.format_number(4.0), "4")
        self.assertEqual(sandbox.format_number(0.0001), "0.0001")
        self.assertEqual(sandbox.py_g(4.0), "4")
        self.assertEqual(sandbox.py_g(0.5), "0.5")
        self.assertEqual(sandbox.py_round(16.004999, 2), 16.0)

    def test_string_of_a_number_is_javascripts(self):
        for value, text in ((1e21, "1e+21"), (1e20, "100000000000000000000"), (1e-7, "1e-7"),
                            (0.000001, "0.000001"), (123.456, "123.456"), (-0.0, "0"), (5.0, "5")):
            self.assertEqual(sandbox.js_text(value), text)
        self.assertEqual(sandbox.js_text([1, None, "a"]), "1,,a")
        self.assertEqual(sandbox.js_text(True), "true")

    def test_canonical_json_sorts_keys_and_refuses_what_it_cannot_write(self):
        self.assertEqual(sandbox.canonical({"b": [1, 2.5], "a": None}), '{"a":null,"b":[1,2.5]}')
        with self.assertRaises(sandbox.CanonicalError):
            sandbox.canonical({"name": "caf\u00e9"})
        with self.assertRaises(sandbox.CanonicalError):
            sandbox.canonical({"value": float("nan")})

    def test_float_plain(self):
        self.assertTrue(sandbox.float_plain(0))
        self.assertTrue(sandbox.float_plain(0.0001))
        self.assertTrue(sandbox.float_plain(123.456789))
        self.assertFalse(sandbox.float_plain(0.00005))
        self.assertFalse(sandbox.float_plain(0.1234567))
        self.assertFalse(sandbox.float_plain(1e9))

    def test_json_is_read_as_javascript_reads_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "value.json"
            path.write_text('{"big": 12345678901234567890, "small": 7}', encoding="utf-8")
            value = sandbox.load_json(path)
            self.assertEqual(value["big"], 12345678901234567890.0)
            self.assertIsInstance(value["big"], float)
            self.assertEqual(value["small"], 7)
            path.write_text('{"x": NaN}', encoding="utf-8")
            with self.assertRaises(ValueError):
                sandbox.load_json(path)


class ContractAndRecipes(unittest.TestCase):
    def test_the_contract_and_the_recipes_agree(self):
        contract = sandbox.load_json(ROOT / sandbox.CONTRACT)
        self.assertEqual(sandbox.licence_problems(contract, ROOT), [])

    def test_a_licence_out_of_order_is_named(self):
        contract = sandbox.load_json(ROOT / sandbox.CONTRACT)
        contract["licences"] = list(reversed(contract["licences"]))
        self.assertEqual(len(sandbox.licence_problems(contract, ROOT)), 1)

    def test_the_experiment_data_is_the_panels(self):
        experiment = sandbox.experiment_data(ROOT)
        self.assertEqual(experiment["flow"], panel.FLOW_HEAD)
        self.assertEqual(experiment["hours_most"], 48)
        self.assertEqual(experiment["recipes"], [r["name"] for r in panel.recipes(ROOT)])
        self.assertEqual(experiment["fields"], panel.block_catalog(ROOT)["fields"])


class Manifests(unittest.TestCase):
    def test_the_good_manifest_keeps_every_rule(self):
        self.assertEqual(sandbox.check_manifest(good_manifest(), fixture_contract()), [])
        self.assertEqual(sandbox.code_problems(good_manifest(), ROOT), [])

    def test_each_broken_manifest_gives_its_problem(self):
        contract = fixture_contract()
        for name, make, expected in MUTATIONS:
            with self.subTest(name):
                self.assertEqual(pairs(sandbox.check_manifest(make(), contract)), pairs(
                    [{"code": code, "field": field} for code, field in expected]))

    def test_the_mutations_cover_every_code(self):
        self.assertEqual({code for _name, _make, expected in MUTATIONS for code, _field in expected}, MANIFEST_CODES)

    def test_planned_code_may_be_pending_and_a_block_may_ask_for_masks_or_unsplit_data(self):
        contract = fixture_contract()
        for name, make in ACCEPTED:
            with self.subTest(name):
                self.assertEqual(sandbox.check_manifest(make(), contract), [])

    def test_problems_merge_one_per_code_and_field(self):
        manifest = good_manifest()
        manifest["needs"] = ["tensorflow", "tensorflow"]
        problems = sandbox.check_manifest(manifest, fixture_contract())
        self.assertEqual(pairs(problems), [("needs", "needs")])
        self.assertIn("; ", problems[0]["text"])

    def test_own_code_needs_its_module_and_test(self):
        manifest = good_manifest()
        manifest["code"], manifest["implemented_by"] = "own", ["tools/sandbox/blocks/crop_test.py"]
        self.assertEqual(sandbox.check_manifest(manifest, fixture_contract()), [])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(pairs(sandbox.code_problems(manifest, root)),
                             [("code", "implemented_by"), ("code", "implemented_by")])
            module = root / "tools" / "sandbox" / "blocks" / "crop_test.py"
            module.parent.mkdir(parents=True)
            module.write_text('"""A crop."""\n\n\ndef run(inputs, params, context):\n    return inputs\n', encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_sandbox_block_crop_test.py").write_text('"""Its test."""\n', encoding="utf-8")
            self.assertEqual(sandbox.code_problems(manifest, root), [])
            module.write_text('"""A crop."""\n\n\ndef run(inputs, params):\n    return inputs\n', encoding="utf-8")
            self.assertEqual(len(sandbox.code_problems(manifest, root)), 1)

    def test_existing_code_names_files_that_are_there(self):
        manifest = broken((["implemented_by"], ["tools/no_such_tool.py", "../outside.py"]))
        self.assertEqual(pairs(sandbox.code_problems(manifest, ROOT)), [("code", "implemented_by"), ("code", "implemented_by")])

    def test_every_block_keeps_every_rule(self):
        contract = sandbox.load_json(ROOT / sandbox.CONTRACT)
        files = sandbox.load_folder(ROOT, sandbox.BLOCKS)
        self.assertGreater(len(files), 0)
        ids = []
        for rel, stem, value, error in files:
            with self.subTest(rel):
                self.assertIsNone(error)
                self.assertEqual(sandbox.block_file_problems(value, contract, ROOT), [])
                self.assertEqual(value["id"], stem)
                ids.append(value["id"])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sandbox.block_problems(ROOT, contract), [])


class Templates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = real_data()

    def test_every_template_compiles_to_what_it_expects(self):
        self.assertGreater(len(self.data["templates"]), 0)
        for spec in self.data["templates"]:
            with self.subTest(spec["id"]):
                prop = sandbox.propagate(spec, self.data)
                self.assertEqual([p for p in prop["problems"] if p["level"] == "error"], [])
                result = sandbox.compile_spec(spec, self.data)
                self.assertEqual(sandbox.expect_of(result), {key: spec["expect"][key] for key in sandbox.EXPECT_KEYS})
                for request in result["requests"]:
                    record, problems = panel.check_request(request["body"], ROOT)
                    self.assertEqual(problems, [])
                    self.assertIsNotNone(record)

    def test_every_template_file_holds(self):
        self.assertEqual(sandbox.template_problems(ROOT, self.data), [])

    def test_a_request_is_the_panels_own(self):
        result = sandbox.compile_spec(template(self.data, "screen_arms"), self.data)
        for request in result["requests"]:
            self.assertEqual(request["title"], panel.request_title(request["named"], str(request["epochs"])))
            self.assertEqual(request["body"], panel.issue_body(request["named"], str(request["epochs"]),
                                                               str(request["seed"]), request["hours_word"],
                                                               request["recipe"]))
            query = dict(urllib.parse.parse_qsl(request["url"].split("?", 1)[1]))
            self.assertEqual(query, {"title": request["title"], "labels": "experiment", "body": request["body"]})

    def test_the_digest_ignores_order_and_layout_and_sees_a_param(self):
        for spec in self.data["templates"]:
            with self.subTest(spec["id"]):
                before = sandbox.digest(spec, self.data)
                self.assertRegex(before, "^[0-9a-f]{64}$")
                moved = copy.deepcopy(spec)
                shuffle = random.Random(spec["id"])
                shuffle.shuffle(moved["nodes"])
                shuffle.shuffle(moved["edges"])
                moved["layout"] = {key: [x + 300, y + 150] for key, (x, y) in moved["layout"].items()}
                moved["about"] = "Moved about."
                self.assertEqual(sandbox.digest(moved, self.data), before)
                changed = copy.deepcopy(spec)
                node, name, value = self.some_other_value(changed)
                node.setdefault("params", {})[name] = value
                self.assertNotEqual(sandbox.digest(changed, self.data), before)

    def some_other_value(self, spec):
        """A node and one of its int or choice params, with a valid value other than the one it has."""
        blocks = sandbox.block_map(self.data)
        for node in spec["nodes"]:
            params = sandbox.effective_params(node, blocks[node["block"]])
            for p in sandbox.params_of(blocks[node["block"]]):
                if p["kind"] == "int" and p["low"] < p["high"]:
                    other = p["low"] if params[p["name"]] != p["low"] else p["high"]
                    return node, p["name"], other
                if p["kind"] == "choice" and len(p["choices"]) > 1:
                    return node, p["name"], next(c for c in p["choices"] if c != params[p["name"]])
        raise AssertionError(f"{spec['id']} has no node with a param to change")

    def test_a_spec_holding_a_mention_is_refused(self):
        """The pipeline's issue carries the name and the spec, and an issue the owner opens with @claude in it
        starts claude.yml, so a name or a node holding @ is an error and the page offers no link."""
        for name, change in (("ask @claude", lambda s: None),
                             ("plain", lambda s: s["nodes"][0].setdefault("params", {}).__setitem__("@claude", 1))):
            with self.subTest(name):
                spec = copy.deepcopy(template(self.data, "latent_prior"))
                spec["name"] = name
                change(spec)
                problems = sandbox.compile_spec(spec, self.data)["problems"]
                self.assertTrue(any(p["code"] == "text" and p["level"] == "error" and "@" in p["text"]
                                    for p in problems), problems)

    def test_split_data_is_not_split_again_and_morphometry_needs_masks(self):
        """The splits take data not split yet: the catalog arrives split by the frozen rule, which a second
        split could only contradict. Morphometry refuses volumes that carry no masks."""
        def pair(source, params, block, port):
            return {"sandbox": 1, "name": "a pair", "edges": [{"from": "n1", "out": "data", "to": "n2", "in": port}],
                    "nodes": [{"id": "n1", "block": source, "version": 1, "params": params},
                              {"id": "n2", "block": block, "version": 1, "params": {}}]}
        cases = (("catalog_v1", {}, "split_person", "data", "parts"),
                 ("catalog_v1", {}, "split_anomaly_aware", "data", "parts"),
                 ("folder_import", {"axes": ["N", "C", "D", "H", "W"], "modality": "ct"}, "morphometry", "masks", "targets"))
        for source, params, block, port, field in cases:
            with self.subTest(block):
                problems = problem_tuples(sandbox.propagate(pair(source, params, block, port), self.data)["problems"])
                self.assertIn(("type", "n2", port, field, "error"), problems)
                self.assertEqual([p for p in problems if p[-1] == "error"], [("type", "n2", port, field, "error")])
        gold = pair("gold3_ct", {}, "morphometry", "masks")
        self.assertEqual([p for p in sandbox.propagate(gold, self.data)["problems"] if p["level"] == "error"], [])


class FloatPlain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = real_data()

    def compiled(self, weight_decay):
        spec = template(self.data, "experiment_v1")
        node_of(spec, "train_classifier")["params"].update({"optimiser": "adamw", "weight_decay": weight_decay})
        return sandbox.compile_spec(spec, self.data)

    def test_a_weight_decay_below_0_0001_is_refused_on_the_experiment_route(self):
        result = self.compiled(0.00005)
        self.assertEqual(result["route"], "pipeline")
        self.assertIn("float_plain", [why["code"] for why in result["why"]])
        self.assertEqual(result["requests"], [])

    def test_a_weight_decay_of_0_0001_is_taken(self):
        result = self.compiled(0.0001)
        self.assertEqual(result["route"], "experiment")
        self.assertEqual(len(result["requests"]), 1)
        request = result["requests"][0]
        self.assertIn("weight_decay=0.0001", request["named"])
        record, problems = panel.check_request(request["body"], ROOT)
        self.assertEqual(problems, [])
        self.assertIsNotNone(record)


class Page(unittest.TestCase):
    INPUTS = {"page.css": "body{margin:0}\n", "shell.html": "<main id=\"app\"></main>\n", "engine.js": "var E=1;\n",
              "ui.js": "var glyphs={crop:1};\n"}

    def write_inputs(self, root, names):
        folder = Path(root) / sandbox.SANDBOX
        folder.mkdir(parents=True, exist_ok=True)
        for name in names:
            (folder / name).write_text(self.INPUTS[name], encoding="ascii")

    def test_the_two_editions_are_assembled_byte_for_byte(self):
        texts = {"page.css": "CSS", "shell.html": "SHELL", "engine.js": "ENGINE", "ui.js": "UI"}
        self.assertEqual(sandbox.repository_page(texts, "JSON"), (
            '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex, nofollow">'
            '<title>Pipeline Sandbox</title><meta name="claude:viewport-fit-sides" content="cover"><style>CSS</style></head>'
            '<body>SHELL<script>const SANDBOX_DATA=JSON;\nENGINE\nUI</script></body></html>\n'))
        self.assertEqual(sandbox.artifact_page(texts, "JSON"), (
            '<title>Pipeline Sandbox</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n<style>CSS</style>\n'
            'SHELL\n<script>const SANDBOX_DATA=JSON;\nENGINE\nUI</script>\n'))

    def test_the_data_cannot_end_the_script(self):
        text = sandbox.data_json({"about": "</script><script>", "n": 1.5})
        self.assertNotIn("</", text)
        self.assertEqual(json.loads(text), {"about": "</script><script>", "n": 1.5})

    def test_a_missing_input_is_named_and_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write_inputs(folder, ("page.css", "shell.html", "engine.js"))
            for command in ("write", "check"):
                run = subprocess.run([sys.executable, str(TOOL), command, "--root", folder], capture_output=True,
                                     text=True, timeout=120)
                self.assertEqual(run.returncode, 1, run.stderr)
                self.assertIn("tools/sandbox/ui.js: missing", run.stderr)
            self.assertFalse((Path(folder) / sandbox.PAGE).exists())

    def test_an_input_that_would_break_the_page_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write_inputs(folder, self.INPUTS)
            self.assertEqual(sandbox.page_inputs(folder)[1], [])
            for name, text in (("ui.js", "var s='</script>';\n"), ("engine.js", "var s='<!-- x';\n"),
                               ("page.css", "@import url(x.css);\n"), ("shell.html", "<script src=x.js></script>\n"),
                               ("ui.js", "fetch('x');\n"), ("page.css", "body{content:'\u00e9'}\n")):
                with self.subTest(name=name, text=text):
                    (Path(folder) / sandbox.SANDBOX / name).write_text(text, encoding="utf-8")
                    problems = sandbox.page_inputs(folder)[1]
                    self.assertTrue(problems and all(line.startswith(f"tools/sandbox/{name}:") for line in problems))
                    (Path(folder) / sandbox.SANDBOX / name).write_text(self.INPUTS[name], encoding="ascii")

    def test_glyph_keys_are_read_from_the_glyph_table(self):
        keys = sandbox.glyph_keys('var G = {crop: a, "splitFamilies": b, \'ct\' : c};\nx.unet = 1;')
        self.assertTrue({"crop", "splitFamilies", "ct"} <= keys)
        self.assertNotIn("unet", keys)

    def test_the_written_page_is_current_and_loads_nothing(self):
        self.assertEqual(sandbox.page_problems(ROOT), [])
        page = (ROOT / sandbox.PAGE).read_bytes()
        text = page.decode("ascii")
        self.assertNotIn("\r", text)
        lowered = text.lower()
        for word in ("<script src", "<link", "@import", "fetch(", "xmlhttprequest"):
            self.assertNotIn(word, lowered)
        self.assertEqual(lowered.count("<script"), 1)
        self.assertEqual(lowered.count("</script"), 1)

    def test_every_glyph_is_drawn(self):
        contract = sandbox.load_json(ROOT / sandbox.CONTRACT)
        self.assertTrue((ROOT / sandbox.SANDBOX / "ui.js").is_file())
        self.assertEqual(sandbox.glyph_problems(ROOT, contract), [])


# The pipelines the two engines are compared on, beyond the templates: each edge of section 10 once.
def edge_specs(data):
    v1 = template(data, "experiment_v1")
    specs = []

    def variant(name, change):
        spec = copy.deepcopy(v1)
        spec["name"] = name
        change(spec)
        specs.append(spec)

    variant("a cycle", lambda s: s["edges"].append({"from": "n8", "out": "report", "to": "n1", "in": "data"}))
    variant("an unknown block", lambda s: s["nodes"].append({"id": "n9", "block": "no_such_block", "version": 1, "params": {}}))
    variant("a bad port", lambda s: s["edges"].__setitem__(0, dict(s["edges"][0], out="nothing")))
    variant("bad ids", lambda s: s["nodes"].extend([{"id": "x1", "block": "augment", "version": 1, "params": {}},
                                                    dict(copy.deepcopy(s["nodes"][1]))]))
    variant("an older version", lambda s: s["nodes"][0].__setitem__("version", 7))
    variant("an unknown param", lambda s: node_of(s, "classifier")["params"].__setitem__("depth", 3))
    variant("a bad value", lambda s: node_of(s, "train_classifier")["params"].__setitem__("epochs", 0))
    variant("hours varied", lambda s: node_of(s, "train_classifier").__setitem__("vary", {"hours": [1, 2]}))
    variant("too many runs", lambda s: node_of(s, "train_classifier").__setitem__(
        "vary", {"epochs": list(range(1, 11)), "seed": list(range(1, 8))}))
    variant("outside only", lambda s: node_of(s, "classifier")["params"].__setitem__("architecture", "resnet50"))
    variant("a rule broken", lambda s: node_of(s, "train_classifier")["params"].__setitem__("weight_decay", 0.01))
    variant("weight decay 0.00005", lambda s: node_of(s, "train_classifier")["params"].update(
        {"optimiser": "adamw", "weight_decay": 0.00005}))
    variant("weight decay 0.0001", lambda s: node_of(s, "train_classifier")["params"].update(
        {"optimiser": "adamw", "weight_decay": 0.0001}))
    variant("hours 2.5, seed 7", lambda s: node_of(s, "train_classifier")["params"].update({"hours": 2.5, "seed": 7}))
    variant("an input left open", lambda s: s["edges"].pop(3))
    variant("two edges into one input", lambda s: s["edges"].append(dict(s["edges"][2])))
    variant("caf\u00e9", lambda s: None)
    variant("ask @claude", lambda s: None)
    variant("a mention in a param", lambda s: node_of(s, "classifier")["params"].__setitem__("@someone", 1))
    variant("a block twice", lambda s: (s["nodes"].append({"id": "n9", "block": "augment", "version": 1, "params": {}}),
                                        s["edges"].append({"from": "n3", "out": "data", "to": "n9", "in": "data"})))
    variant("a block of the tests, varied", lambda s: (
        s["nodes"].append({"id": "n9", "block": "crop_test", "version": 1, "params": {"jitter": 0.5},
                           "vary": {"size": [32, 64], "mode": ["centre", "random"]}}),
        s["edges"].append({"from": "n2", "out": "crops", "to": "n9", "in": "data"})))
    variant("a block that reads test", lambda s: (
        s["nodes"].append({"id": "n9", "block": "peek_test", "version": 1, "params": {}}),
        s["edges"].append({"from": "n1", "out": "data", "to": "n9", "in": "data"})))
    specs += [{"sandbox": 1, "name": "", "nodes": [], "edges": []}, {"name": "no lists"},
              {"nodes": [5, {"id": "n1"}], "edges": [{"from": "n1"}, "x"]}]
    return specs


def peeking_manifest():
    """A block of the tests that reads the test part outside evaluation, which propagate refuses."""
    manifest = good_manifest()
    manifest["id"], manifest["reads"] = "peek_test", {"parts": ["train", "test"]}
    return manifest


def varied_specs(data, count):
    """Random small changes to the templates, seeded, so that the comparison reaches paths no one listed."""
    pick = random.Random(20261030)
    blocks = sandbox.block_map(data)
    out = []
    for at in range(count):
        spec = copy.deepcopy(pick.choice(data["templates"]))
        spec["name"] = f"varied {at}"
        node = pick.choice(spec["nodes"])
        params = sandbox.params_of(blocks.get(node["block"]))
        if params and pick.random() < 0.6:
            p = pick.choice(params)
            values = p.get("choices") or [p.get("low"), p.get("high"), p.get("default")]
            node.setdefault("params", {})[p["name"]] = pick.choice(values)
            if p.get("vary") and pick.random() < 0.5:
                node["vary"] = {p["name"]: pick.sample(list(values), k=min(2, len(values)))}
        if spec["edges"] and pick.random() < 0.3:
            spec["edges"].pop(pick.randrange(len(spec["edges"])))
        out.append(spec)
    return out


def varied_manifests(data, count):
    """Random small breaks of the real manifests, seeded: a key dropped, or a value replaced by another's."""
    pick = random.Random(30102026)
    fillers = [None, 0, -1, 1.5, "", "x", [], ["data"], {}, True, "@param.nothing", "@in.data.kind", ["kind", "data"]]
    out = []
    for _ in range(count):
        manifest = copy.deepcopy(pick.choice(data["blocks"]))
        key = pick.choice(list(manifest))
        if pick.random() < 0.3:
            del manifest[key]
        elif isinstance(manifest[key], list) and manifest[key] and pick.random() < 0.5:
            manifest[key][pick.randrange(len(manifest[key]))] = pick.choice(fillers)
        else:
            manifest[key] = pick.choice(fillers)
        out.append(manifest)
    return out


def huge_specs(data, size=3001):
    """Every template with each node varying one or two params over size copies of a value, so that fans,
    tasks and hours pass 2 ** 53, where JavaScript's doubles round and Python's ints would not."""
    blocks = sandbox.block_map(data)
    out = []
    for spec in copy.deepcopy(data["templates"]):
        spec["name"] = f"huge {spec['name']}"
        for node in spec["nodes"]:
            params = sandbox.params_of(blocks.get(node["block"]))
            given = node.get("params", {})
            varied = [p for p in params if p.get("vary")][:2] or params[:1]
            node["vary"] = {p["name"]: [given.get(p["name"], p.get("default"))] * size for p in varied}
        out.append(spec)
    return out


NODE_SCRIPT = r"""
"use strict";
var fs = require("fs");
var SB = require(process.argv[2]);
var input = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
function canonicalOf(spec) {
  try { return SB.canonical(SB.specOf(spec, input.data)); } catch (e) { return null; }
}
var out = {
  specs: input.specs.map(function (spec) {
    var prop = SB.propagate(spec, input.data);
    return {canonical: canonicalOf(spec), digest: SB.digest(spec, input.data), propagate: prop,
      jobs: SB.jobs(spec, input.data, prop), compile: SB.compile(spec, input.data)};
  }),
  manifests: input.manifests.map(function (m) { return SB.checkManifest(m, input.contract); })
};
process.stdout.write(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node is not installed here; CI's runners have it")
class SameAsTheEngine(unittest.TestCase):
    """The JavaScript engine and this module give the same results on the same pipelines and manifests."""

    @classmethod
    def setUpClass(cls):
        data = real_data()
        data["blocks"] = data["blocks"] + [good_manifest(), peeking_manifest()]
        manifests = (list(data["blocks"]) + [make() for _name, make, _expected in MUTATIONS]
                     + [make() for _name, make in ACCEPTED] + varied_manifests(data, 150))
        specs = list(data["templates"]) + edge_specs(data) + varied_specs(data, 80) + huge_specs(data)
        payload = {"data": data, "specs": specs, "manifests": manifests, "contract": data["contract"]}
        with tempfile.TemporaryDirectory() as folder:
            given = Path(folder) / "given.json"
            given.write_text(json.dumps(sandbox.plain(payload)), encoding="ascii")
            script = Path(folder) / "same.js"
            script.write_text(NODE_SCRIPT, encoding="ascii")
            run = subprocess.run(["node", str(script), str(ENGINE), str(given)], capture_output=True, text=True,
                                 timeout=300)
            if run.returncode:
                raise AssertionError(f"node failed: {run.stderr[-2000:]}")
            cls.given = sandbox.load_json(given)
        cls.engine = whole_numbers(json.loads(run.stdout))

    def test_pipelines(self):
        data = self.given["data"]
        for spec, theirs in zip(self.given["specs"], self.engine["specs"], strict=True):
            with self.subTest(spec.get("name") if isinstance(spec, dict) else spec):
                self.assertEqual(sandbox.canonical_text(spec, data), theirs["canonical"])
                self.assertEqual(sandbox.digest(spec, data), theirs["digest"])
                prop = sandbox.propagate(spec, data)
                self.same_propagation(prop, theirs["propagate"])
                planned = sandbox.jobs(spec, data, prop)
                self.assertEqual(as_json(planned["rows"]), theirs["jobs"]["rows"])
                self.assertEqual(as_json(planned["totals"]), theirs["jobs"]["totals"])
                self.assertEqual(problem_tuples(planned["problems"]), problem_tuples(theirs["jobs"]["problems"]))
                self.same_compile(sandbox.compile_spec(spec, data), theirs["compile"])

    def same_propagation(self, ours, theirs):
        self.assertEqual(ours["order"], theirs["order"])
        self.assertEqual(problem_tuples(ours["problems"]), problem_tuples(theirs["problems"]))
        self.assertEqual(sorted(ours["nodes"]), sorted(theirs["nodes"]))
        for node_id, entry in ours["nodes"].items():
            other = theirs["nodes"][node_id]
            for key in ("inputs", "outputs", "fan", "combinations"):
                self.assertEqual(as_json(entry[key]), other[key], f"{node_id} {key}")
            self.assertEqual(problem_tuples(entry["problems"]), problem_tuples(other["problems"]), node_id)

    def same_compile(self, ours, theirs):
        for key in ("digest", "route", "ready", "plan", "jobs", "pipeline_issue"):
            self.assertEqual(as_json(ours[key]), theirs[key], key)
        self.assertEqual([why["code"] for why in ours["why"]], [why["code"] for why in theirs["why"]])
        self.assertEqual(problem_tuples(ours["problems"]), problem_tuples(theirs["problems"]))
        self.assertEqual(len(ours["requests"]), len(theirs["requests"]))
        for mine, other in zip(ours["requests"], theirs["requests"], strict=True):
            for key in ("title", "body", "named", "lines", "command", "combination", "blocks", "recipe", "epochs",
                        "seed", "hours", "hours_word"):
                self.assertEqual(as_json(mine[key]), other[key], key)
            mine_url, mine_query = mine["url"].split("?", 1)
            other_url, other_query = other["url"].split("?", 1)
            self.assertEqual(mine_url, other_url)
            self.assertEqual(urllib.parse.parse_qsl(mine_query, keep_blank_values=True),
                             urllib.parse.parse_qsl(other_query, keep_blank_values=True))

    def test_manifests(self):
        contract = self.given["contract"]
        for manifest, theirs in zip(self.given["manifests"], self.engine["manifests"], strict=True):
            with self.subTest(manifest.get("id") if isinstance(manifest, dict) else manifest):
                self.assertEqual(pairs(sandbox.check_manifest(manifest, contract)), pairs(theirs))


if __name__ == "__main__":
    unittest.main()
