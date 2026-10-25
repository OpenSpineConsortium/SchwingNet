"""tools/experiments_panel.py: the recorded runs are read with version 1's blocks spelled out where a
run names none, the page inlines its data and loads nothing, the record is a figure the site reads,
a request's issue carries the lines the workflow reads, and the currency check fails on a stale page."""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


panel = load("experiments_panel")
textbook_site = load("textbook_site")
eval_page = load("eval_page")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class RecordsAreRead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = panel.panel_data(ROOT)
        cls.runs = {run["id"]: run for run in cls.data["runs"]}
        cls.catalog = panel.block_catalog(ROOT)

    def test_the_ledgers_runs_are_read_with_their_outcome(self):
        for run_id in ("a767a466f5c1", "cd37124c487d"):
            run = self.runs[run_id]
            self.assertTrue(HEX40.match(run["repro"]["commit"]), run_id)
            self.assertTrue(run["repro"]["clean_tree"] and run["repro"]["split_disjoint"])
            self.assertEqual(run["input"]["catalog"][:9], "catalog 1")
            self.assertTrue(run["input"]["synthetic"], "both recorded runs are dry runs on the synthetic bank")
            self.assertGreater(run["test"]["total"], 0)
            self.assertAlmostEqual(run["test"]["accuracy"], run["test"]["correct"] / run["test"]["total"])
            self.assertIn(run["best"]["epoch"], [m["epoch"] for m in run["metrics"]])
            self.assertTrue(run["model"]["architecture"].startswith("torchvision resnet18"))
            self.assertEqual(run["model"]["parameters"], "not recorded")
            self.assertEqual(run["repro"]["reforms"]["met"] + run["repro"]["reforms"]["missing"], 32)
            self.assertEqual(run["repro"]["report"], {"complete": False, "missing": 48})
            self.assertTrue(run["repro"]["command"].startswith(f"git checkout {run['repro']['commit'][:12]} && python3 tools/flow.py run"))
            self.assertEqual(run["run_json"], f"docs/research/v1-demo/runs/{run_id}/RUN.json")
        self.assertEqual(self.runs["a767a466f5c1"]["wandb"]["status"], "not logged")
        self.assertEqual(self.runs["cd37124c487d"]["wandb"]["status"], "offline")
        self.assertIn("no W&B key", self.runs["cd37124c487d"]["wandb"]["why"])
        self.assertTrue(self.data["dry_runs_only"])

    def test_every_run_has_every_block_with_version_1_where_it_named_none(self):
        for run in self.data["runs"]:
            self.assertTrue(set(self.catalog["fields"]) <= set(run["blocks"]), run["id"])
            if not run["blocks_recorded"]:
                self.assertEqual(run["named"], [], run["id"])
                self.assertEqual(run["blocks"]["architecture"], "resnet18")
                self.assertEqual(run["blocks"]["augment"], [])
                for name in self.catalog["fields"]:
                    self.assertEqual(run["blocks"][name], self.catalog["defaults"][name], name)

    def test_a_recorded_block_is_named_in_the_fields_order(self):
        blocks = panel.fill_blocks({"architecture": "resnet34", "augment": ["box-jitter", "intensity"], "weight_decay": 0.01, "optimiser": "adamw"}, self.catalog)
        self.assertEqual(panel.named_words(blocks, self.catalog), ["augment=box-jitter,intensity", "optimiser=adamw", "weight_decay=0.01", "architecture=resnet34"])
        self.assertEqual(panel.named_words(panel.fill_blocks(None, self.catalog), self.catalog), [])

    def test_the_catalog_is_what_blocks_py_defines(self):
        self.assertEqual(self.catalog["fields"][:3], ["normalise", "augment", "optimiser"])
        self.assertIn("resnet18", self.catalog["choices"]["architecture"])
        self.assertEqual(self.catalog["options"]["augment"], ["box-jitter", "intensity", "blur", "noise"])
        self.assertIn("weight_decay", self.catalog["numbers"])
        self.assertEqual(self.catalog["by_person"], "cap-per-person")
        self.assertEqual([r["name"] for r in panel.recipes(ROOT)], ["commercial", "commercial-share-alike", "non-commercial", "research-internal"])
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from schwingnet import blocks
        except ImportError:
            self.skipTest("the package's dependencies are not here; the gate lane holds the two equal")
        self.assertEqual(self.catalog["fields"], list(blocks.FIELDS))
        self.assertEqual(self.catalog["defaults"], blocks.as_record(blocks.DEFAULT))
        self.assertEqual(self.catalog["choices"], {k: list(v) for k, v in blocks.CHOICES.items()})

    def test_wilson_is_the_evaluation_pages(self):
        for correct, total in ((430, 431), (556, 556), (0, 10), (7, 20)):
            theirs = eval_page.wilson(correct, total)
            ours = panel.wilson(correct, total)
            self.assertAlmostEqual(ours[0], theirs[0], places=9)
            self.assertAlmostEqual(ours[1], theirs[1], places=9)


class TheFigure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = panel.outputs(ROOT)
        cls.html = cls.outputs["experiments.html"]

    def test_the_page_inlines_its_data_and_loads_nothing(self):
        self.assertIn("const DATA=", self.html)
        for run_id in ("a767a466f5c1", "cd37124c487d"):
            self.assertIn(run_id, self.html)
        self.assertIsNone(re.search(r"<script[^>]*\ssrc=", self.html))
        self.assertNotIn("<link", self.html)
        self.assertNotIn("fetch(", self.html)
        self.assertEqual(self.html.count("<script>"), 1)
        self.assertEqual(self.html.count("</script>"), 1)
        self.assertIn("schwingnet.experiment", self.html)
        self.assertIn("schwingnet.open", self.html)
        self.assertIn("@media (prefers-color-scheme:dark){:root:not([data-theme=light])", self.html)
        self.assertIn(":root[data-theme=dark]", self.html)
        self.assertIn("dry run on the synthetic bank", self.html)
        blob = json.loads(re.search(r"const DATA=(.*?);\n", self.html).group(1).replace("<\\/", "</"))
        self.assertEqual(len(blob["runs"]), len(panel.run_folders(ROOT)))
        self.assertEqual(blob["epochs_most"], panel.EPOCHS_MOST)

    def test_the_record_is_a_figure_the_site_reads(self):
        path = ROOT / panel.OUT / "experiments.json"
        self.assertTrue(textbook_site.is_figure(path))
        record = json.loads(self.outputs["experiments.json"])
        self.assertEqual(record["id"], "35/experiments")
        self.assertEqual(record["rerun"], {"where": "actions", "command": "python3 tools/experiments_panel.py write", "cost": "CPU, a second", "needs_owner_word": False})
        self.assertEqual(record["status"], "a record, not a final value")
        self.assertIn("docs/research/v1-demo/runs/", record["source"]["data"])
        chapter = (ROOT / panel.CHAPTER).read_text(encoding="utf-8").splitlines()
        image = next(i for i, line in enumerate(chapter) if textbook_site.FIGURE_IMAGE.match(line) and "experiments.svg" in line)
        self.assertTrue(textbook_site.FIGURE_CAPTION.match(chapter[image + 1]), "the caption follows the image line")
        self.assertIn("experiments.json", chapter[image + 1])

    def test_the_site_shows_what_a_framed_figure_posts(self):
        # The book frames a figure with sandbox="allow-scripts", so the figure's links and the combination
        # its panel names reach the page around it by postMessage; every page of the site listens, checks
        # the source against its own figure frames and answers a request to act with "no connector".
        shell = textbook_site.page("A chapter", "<p>body</p>", "", "")
        self.assertIn(textbook_site.MESSAGE_JS, shell)
        for word in ("schwingnet.open", "schwingnet.experiment", "schwingnet.dispatch", "schwingnet.read", "no connector", "contentWindow === source", "figure-bar"):
            self.assertIn(word, shell, word)
        self.assertNotIn("e.origin", textbook_site.MESSAGE_JS, "a sandboxed frame's origin is null, so the source is checked instead")

    def test_the_page_starts_only_the_two_request_workflows_as_the_viewer(self):
        # A figure is framed content, and some figures are exported artifacts, so the page's dispatcher starts
        # experiment.yml on SchwingNet and storage.yml on spine-datasets and nothing else, whatever a message
        # names; node runs the page's own script against a stand-in connector that records each call.
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed here; CI's runner has it")
        script = re.search(r"<script>(.*)</script>", textbook_site.MESSAGE_JS, re.S).group(1)
        harness = """
const calls = [];
globalThis.window = globalThis;
window.addEventListener = function () {};
globalThis.document = {querySelectorAll: () => [], createElement: () => ({}), body: {appendChild() {}}, addEventListener() {}};
window.claude = {use: async () => ({callTool: async (server, tool, input) => { calls.push([server, tool, input.owner + "/" + input.repo, input.workflow_id]); return {}; }})};
""" + script + """
const asks = [
  {repo: "OpenSpineConsortium/SchwingNet", workflow: "experiment.yml", inputs: {epochs: 3}},
  {repo: "OpenSpineConsortium/spine-datasets", workflow: "storage.yml", inputs: {selection: "-a"}},
  {repo: "OpenSpineConsortium/SchwingNet", workflow: "research.yml"},
  {repo: "OpenSpineConsortium/SchwingNet", workflow: "constructor"},
  {repo: "OpenSpineConsortium/spine-datasets", workflow: "experiment.yml"},
  {repo: "OpenSpineConsortium/hpcworker", workflow: "experiment.yml"},
];
Promise.all(asks.map((a) => window.schwingnetDispatch(a))).then((results) => {
  console.log(JSON.stringify({results, calls}));
});
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dispatch.js"
            path.write_text(harness, encoding="utf-8")
            run = subprocess.run([node, str(path)], capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        seen = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual([r["ok"] for r in seen["results"]], [True, True, False, False, False, False])
        self.assertEqual([r.get("error") for r in seen["results"][2:]],
                         ["workflow not allowed", "workflow not allowed", "workflow not allowed", "repository not allowed"])
        self.assertEqual(seen["calls"], [["GitHub", "actions_run_trigger", "OpenSpineConsortium/SchwingNet", "experiment.yml"],
                                         ["GitHub", "actions_run_trigger", "OpenSpineConsortium/spine-datasets", "storage.yml"]])

    def test_the_svg_draws_every_run(self):
        svg = self.outputs["experiments.svg"]
        for run_id in ("a767a466f5c1", "cd37124c487d"):
            self.assertIn(run_id, svg)
        self.assertIn("prefers-color-scheme:dark", svg)

    def test_the_written_files_are_what_the_records_give(self):
        self.assertEqual(panel.stale(ROOT), [])
        for name, text in self.outputs.items():
            self.assertEqual((ROOT / panel.OUT / name).read_text(encoding="utf-8"), text, name)

    def test_the_currency_check_fails_on_a_stale_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (panel.BLOCKS_PY, panel.LEDGER):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / rel, root / rel)
            shutil.copytree(ROOT / panel.RECIPES, root / panel.RECIPES)
            shutil.copytree(ROOT / panel.RUNS / "cd37124c487d", root / panel.RUNS / "cd37124c487d",
                            ignore=shutil.ignore_patterns("*.png", "*.jpg", "frames", "witness"))
            self.assertEqual(panel.main(["write", "--root", str(root)]), 0)
            self.assertEqual(panel.stale(root), [])
            self.assertEqual(panel.main(["check", "--root", str(root)]), 0)
            page = root / panel.OUT / "experiments.html"
            page.write_text(page.read_text(encoding="utf-8").replace("The experiments panel", "An edited page"), encoding="utf-8")
            self.assertEqual(panel.stale(root), ["experiments.html"])
            self.assertEqual(panel.main(["check", "--root", str(root)]), 1)
            (root / panel.OUT / "experiments.svg").unlink()
            self.assertEqual(panel.stale(root), ["experiments.html", "experiments.svg"])


class TheRequest(unittest.TestCase):
    def test_the_issue_carries_the_lines_the_workflow_reads(self):
        body = panel.issue_body(["architecture=resnet34", "augment=box-jitter"], 20, 1, 4.0, "non-commercial")
        lines = body.splitlines()
        self.assertEqual(lines[0], panel.ISSUE_MARKER)
        self.assertEqual(lines[1:6], ["recipe: non-commercial", "epochs: 20", "seed: 1", "hours: 4.0", "block: architecture=resnet34"])
        self.assertEqual(lines[6], "block: augment=box-jitter")
        self.assertIn("--recipe non-commercial --block architecture=resnet34 --block augment=box-jitter", body)
        url = panel.issue_url([], 4, 1, 4.0, "none")
        self.assertTrue(url.startswith("https://github.com/OpenSpineConsortium/SchwingNet/issues/new?"))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query["labels"], ["experiment"])
        self.assertEqual(query["title"], ["Experiment: version 1 (no block named), 4 epochs"])
        self.assertIn("recipe: none\nepochs: 4\n", query["body"][0])

    def test_the_flow_command_names_only_what_differs_from_version_1(self):
        self.assertEqual(panel.flow_command([], 20, 1, 4, "none"), panel.FLOW_HEAD + " --epochs 20 --seed 1 --hours 4")
        self.assertEqual(panel.flow_command(["denoise=median"], 20, 2, 4, "commercial"), panel.FLOW_HEAD + " --epochs 20 --seed 2 --hours 4 --recipe commercial --block denoise=median")


if __name__ == "__main__":
    unittest.main()
