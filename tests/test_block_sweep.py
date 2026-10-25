"""tools/block_sweep.py's smoke test commands (#252): the plans are a function of the code, the
check predicts from a catalog's facts what the trainer will do, the state of a sweep is rebuilt
from its rows alone, and, where torch is installed, a small plan run row by row through the real
flow and trainer does what the check predicted for every row.

The pure parts need the package's checkers (beartype, icontract, pydantic), so they run in the
default environment (`pixi run --locked python -m unittest tests.test_block_sweep`) and skip under
the required check's plain python3; the run of the rows needs the train environment too
(`pixi run --locked -e train-cpu python -m unittest tests.test_block_sweep`), as
tests/test_train_blocks.py does."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("beartype", "icontract", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
TORCH_NEEDED = ("torch", "torchvision", "onnx", "onnxruntime", "PIL", *NEEDED)
TORCH_MISSING = [name for name in TORCH_NEEDED if importlib.util.find_spec(name) is None]
PLANS = {"synthetic": ("cover", "synthetic"), "real": ("cover", "v1"), "two_source": ("cover", "with:vindr_spinexr")}
SLUG = re.compile(r"(?:(?:imagenet|init|refuse|trial)-)?[a-z0-9-]+-\d+px-[0-9a-f]{8}")
# Small enough to build in seconds, large enough that every part holds labelled crops.
TINY = ("--frames", "80", "--cases", "6", "--test-frames", "15", "--unlabelled-frames", "20", "--seed", "3")


def load(root=ROOT, name="block_sweep"):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", root / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_run_code(root=ROOT):
    return load(root, "run_code")


def said(module, *argv):
    """What a command printed, and its exit code, run in this process."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(list(map(str, argv)))
    return code, out.getvalue(), err.getvalue()


def samples_of(row):
    """A plan row's samples cut, as its words name it."""
    return next((word.split("=", 1)[1] for word in row["blocks"] if word.startswith("samples=")), "all")


def tiny_catalog(module, into):
    code, out, err = said(module, "synthetic", "--into", into, *TINY)
    if code != 0:
        raise AssertionError(err)
    return json.loads(out)["catalog"]


@unittest.skipIf(MISSING, f"needs the package's checkers ({', '.join(MISSING)} missing)")
class PlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sweep = load()

    def plan(self, *argv):
        code, out, err = said(self.sweep, *argv)
        self.assertEqual(code, 0, err)
        return out

    def test_each_plan_file_is_the_output_of_its_command(self):
        for name, (command, catalog) in PLANS.items():
            made = self.plan(command, "--name", name, "--catalog", catalog, "--epochs", 3, "--seed", 1)
            self.assertEqual(made, (ROOT / "grid" / "sweeps" / f"{name}.json").read_text(encoding="utf-8"), name)
        made = self.plan("trials", "--catalog", "v1", "--epochs", 20, "--seed", 1)
        self.assertEqual(made, (ROOT / "grid" / "sweeps" / "trials.json").read_text(encoding="utf-8"))

    def test_a_plan_file_is_sorted_json_with_indent_one_that_bash_can_read(self):
        text = (ROOT / "grid" / "sweeps" / "real.json").read_text(encoding="utf-8")
        plan = json.loads(text)
        self.assertEqual(text, json.dumps(plan, indent=1, sort_keys=True) + "\n")
        self.assertEqual(set(plan), {"plan", "about", "catalog", "epochs", "seed", "rows"})
        self.assertIn('\n "catalog": "v1",\n', text, "the gate reads the catalog field with sed")
        self.assertIn('"weights": "resnet18"', text, "and greps for a row that names weights")
        self.assertTrue(text.isascii())

    def test_the_cover_has_its_halves_then_its_routes_and_every_slug_follows_from_its_row(self):
        from schwingnet.blocks import as_record, parse

        rows = json.loads((ROOT / "grid" / "sweeps" / "synthetic.json").read_text(encoding="utf-8"))["rows"]
        roles = [row["role"] for row in rows]
        self.assertEqual(roles, ["cover"] * 20 + ["imagenet", "init", "init", "refuse", "refuse", "refuse", "refuse"])
        self.assertEqual(len({row["slug"] for row in rows}), len(rows))
        for row in rows:
            self.assertRegex(row["slug"], SLUG)
            self.assertLessEqual(len(row["slug"]), 80)
            record = {"blocks": as_record(parse(row["blocks"])), "size": row["size"], "weights": row["weights"], "init": row["init"]}
            digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:8]
            self.assertTrue(row["slug"].endswith(f"-{row['size']}px-{digest}"), row["slug"])
        first = rows[0]
        self.assertEqual((first["blocks"], first["size"]), ([], 64), "the first row is version 1's training")
        self.assertEqual([row["init"] for row in rows if row["init"]], [first["slug"]] * 4)
        cuts = [row for row in rows[:20] if "sources=@first-labelled" in row["blocks"]]
        prior = ["prior=level-map", "prior_weight=0.5"]
        self.assertEqual([(row["blocks"], row["size"]) for row in cuts],
                         [(["samples=only-sources", "sources=@first-labelled"], 64), (["samples=drop-sources", "sources=@first-labelled"], 64),
                          (["samples=only-sources", "sources=@first-labelled", *prior], 64), (["samples=drop-sources", "sources=@first-labelled", *prior], 64)])
        self.assertEqual([rows.index(row) for row in cuts], [8, 9, 18, 19], "each half closes with its two source cuts")
        architectures = {word for row in rows[:20] if row not in cuts for word in row["blocks"] if word.startswith("architecture=")}
        self.assertEqual(len(architectures), 7, "every architecture but resnet18 is named on a row whose cut trains")

    def test_the_strict_cover_is_the_pairwise_array_and_its_four_source_cut_rows(self):
        plan = json.loads(self.plan("cover", "--name", "strict", "--catalog", "synthetic", "--strict"))
        roles = [row["role"] for row in plan["rows"]]
        self.assertEqual(roles.count("cover"), 36)
        self.assertIn("pairwise", plan["about"])

    def test_the_trials_are_six_arms_from_imagenet(self):
        plan = json.loads((ROOT / "grid" / "sweeps" / "trials.json").read_text(encoding="utf-8"))
        rows = plan["rows"]
        self.assertEqual([row["size"] for row in rows], [64, 64, 64, 96, 64, 64])
        self.assertTrue(all(row["role"] == "trial" and row["weights"] == "resnet18" and row["slug"].startswith("trial-resnet18-") for row in rows))
        self.assertEqual(rows[0]["blocks"], [])
        self.assertEqual(rows[1]["blocks"], ["normalise=imagenet", "augment=box-jitter,intensity,blur,noise,strong"])
        self.assertIn("sampler=balanced", rows[5]["blocks"])
        self.assertIn("backbone_lr_scale=0.1", rows[5]["blocks"])
        for source in ("Nat Mach Intell 5:294", "MICCAI 2025", "J Clin Med 14:7671"):
            self.assertIn(source, plan["about"])

    def test_each_source_is_cited_for_what_it_did(self):
        # Kwak, Ro and Kang 2025 trained with AdamW, a cosine schedule and a warm-up and chose by
        # the highest accuracy, with no balanced sampling or balanced accuracy anywhere, so their
        # paper stands behind the third arm's recipe and not behind the balanced arms.
        about = json.loads((ROOT / "grid" / "sweeps" / "trials.json").read_text(encoding="utf-8"))["about"]
        clauses = about.split("; ")
        tuned = next(clause for clause in clauses if "AdamW" in clause)
        balanced = next(clause for clause in clauses if "balanced sampling" in clause)
        self.assertIn("Kwak, Ro and Kang 2025", tuned)
        self.assertIn("224 pixels", tuned, "and it says how the arm differs from their recipe")
        self.assertNotIn("Kwak", balanced)

    def test_a_plan_with_a_name_or_catalog_the_gate_cannot_take_is_refused(self):
        for argv in (("cover", "--name", "Real", "--catalog", "v1"), ("cover", "--name", "real", "--catalog", "v2"),
                     ("cover", "--name", "real", "--catalog", "with:VinDr")):
            code, _, err = said(self.sweep, *argv)
            self.assertEqual(code, 1, argv)
            self.assertIn("block_sweep:", err)


@unittest.skipIf(MISSING, f"needs the package's checkers ({', '.join(MISSING)} missing)")
class CheckTest(unittest.TestCase):
    """The check against a small synthetic catalog, built with the tools and no torch."""

    @classmethod
    def setUpClass(cls):
        cls.sweep = load()
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = tiny_catalog(cls.sweep, cls.tmp / "synthetic")
        cls.facts = cls.sweep.read_facts(cls.catalog)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def verdicts(self, plan="synthetic", *weights):
        code, out, err = said(self.sweep, "check", "--catalog", self.catalog, "--plan", ROOT / "grid" / "sweeps" / f"{plan}.json", "--json", *weights)
        self.assertEqual(code, 0, err)
        return {row["slug"]: row for row in json.loads(out)["rows"]}

    def test_the_facts_tell_the_annotated_sources_from_the_unannotated_one(self):
        # The labelled bank is split between C-ArmLSpine's route and a render's, so the source
        # cuts have two labelled sources to cut between.
        self.assertEqual((self.facts["labelled"], self.facts["unlabelled"]), (["carmlspine", "verse_2d_projections"], ["vindr_spinexr"]))
        table = {(row["source"], row["part"]): row for row in self.facts["table"]}
        self.assertGreater(table["carmlspine", "train"]["crops_with_map"], 0)
        self.assertLess(table["carmlspine", "train"]["crops_with_map"], table["carmlspine", "train"]["labelled_crops"])
        self.assertEqual(table["vindr_spinexr", "train"]["labelled_crops"], 0)
        self.assertGreater(table["vindr_spinexr", "train"]["frames"], 0)
        self.assertEqual(table["carmlspine", "test"]["persons"], 5, "the five frozen test persons")
        self.assertFalse(any(c["part"] == "test" for c in self.facts["crops"]), "the check, like the trainer, never reads a test crop")

    def test_the_facts_table_counts_the_test_parts_labels_and_maps_too(self):
        # The table says what each part holds, the frozen test persons' labelled crops among it,
        # counted as the trainer and the evaluator read labels, so no reader takes the test part
        # for unlabelled; only the predictions leave it out.
        import sqlite3

        db = sqlite3.connect(f"file:{self.catalog}?mode=ro", uri=True)
        try:
            counted = dict(db.execute("SELECT i.part, COUNT(*) FROM label l JOIN item i ON i.sha256 = l.item AND i.shard = l.shard"
                                      " JOIN shard s ON s.name = i.shard WHERE i.source = 'carmlspine' GROUP BY i.part"))
            mapped = dict(db.execute("SELECT i.part, COUNT(*) FROM label l JOIN item i ON i.sha256 = l.item AND i.shard = l.shard"
                                     " WHERE i.source = 'carmlspine' AND i.level_map IS NOT NULL GROUP BY i.part"))
        finally:
            db.close()
        table = {(row["source"], row["part"]): row for row in self.facts["table"]}
        for part in ("train", "validation", "test"):
            self.assertEqual(table["carmlspine", part]["labelled_crops"], counted[part], part)
            self.assertEqual(table["carmlspine", part]["crops_with_map"], mapped[part], part)
        self.assertGreater(table["carmlspine", "test"]["labelled_crops"], 0)
        code, page, err = said(self.sweep, "check", "--catalog", self.catalog, "--all", "--sizes", "64")
        self.assertEqual(code, 0, err)
        test = table["carmlspine", "test"]
        self.assertIn(f"| carmlspine | test | {test['frames']} | {test['labelled_crops']} | {test['crops_with_map']} | {test['persons']} |", page)

    def test_each_row_of_the_synthetic_plan_is_predicted(self):
        rows = json.loads((ROOT / "grid" / "sweeps" / "synthetic.json").read_text(encoding="utf-8"))["rows"]
        verdicts = self.verdicts("synthetic", "--weights", "resnet18=/nowhere/resnet18.pth")
        for row in rows:
            found = verdicts[row["slug"]]
            if row["role"] in ("cover", "imagenet", "init"):
                self.assertEqual(found["predicted"], "runs", (row["slug"], found))
                self.assertGreater(found["train_crops"], 0)
        refusals = [verdicts[row["slug"]]["code"] for row in rows if row["role"] == "refuse"]
        self.assertEqual(refusals, ["cut-leaves-none", "source-absent", "init-mismatch", "init-and-weights"])

    def test_every_cut_trains_in_each_half_and_the_source_cuts_on_a_strict_part(self):
        rows = json.loads((ROOT / "grid" / "sweeps" / "synthetic.json").read_text(encoding="utf-8"))["rows"]
        verdicts = self.verdicts("synthetic")
        everything = verdicts[rows[0]["slug"]]["train_crops"]
        for prior in (False, True):
            half = [row for row in rows if row["role"] == "cover" and any(word.startswith("prior=") for word in row["blocks"]) == prior]
            for cut in ("all", "only-sources", "drop-sources", "cap-per-person"):
                trained = [verdicts[row["slug"]] for row in half if samples_of(row) == cut and verdicts[row["slug"]]["predicted"] == "runs"]
                self.assertTrue(trained, f"no row of samples={cut} trains with the prior {'on' if prior else 'off'}")
                if cut in ("only-sources", "drop-sources"):
                    self.assertTrue(any(0 < found["train_crops"] < everything for found in trained), (cut, prior, trained))

    def test_a_row_that_needs_a_file_or_a_source_the_catalog_lacks_is_not_applicable(self):
        verdicts = self.verdicts("synthetic")
        rows = json.loads((ROOT / "grid" / "sweeps" / "synthetic.json").read_text(encoding="utf-8"))["rows"]
        weighted = [row["slug"] for row in rows if row["weights"]]
        self.assertEqual(len(weighted), 2)
        self.assertTrue(all(verdicts[slug]["predicted"] == "not applicable" for slug in weighted))
        alone = dict(self.facts, unlabelled=[])
        plan = json.loads((ROOT / "grid" / "sweeps" / "real.json").read_text(encoding="utf-8"))
        predicted = self.sweep.plan_verdicts(plan, alone, {"resnet18": "w.pth"})
        dropping = [row["slug"] for row in plan["rows"] if "sources=@unlabelled" in row["blocks"]]
        self.assertEqual(len(dropping), 1)
        self.assertEqual(predicted[dropping[0]]["predicted"], "not applicable")
        self.assertIn("@unlabelled names no source", predicted[dropping[0]]["why"])

    def test_on_a_catalog_with_one_labelled_source_the_source_cuts_say_why_they_do_not_apply(self):
        # Catalog version 1 holds C-ArmLSpine alone, so a cut to one labelled source of several
        # would keep every crop or none: the four rows are not applicable, saying so, and no
        # other row loses its prediction.
        plan = json.loads((ROOT / "grid" / "sweeps" / "real.json").read_text(encoding="utf-8"))
        one = dict(self.facts, labelled=["carmlspine"], unlabelled=[], crops=[c for c in self.facts["crops"] if c["source"] == "carmlspine"])
        predicted = self.sweep.plan_verdicts(plan, one, {"resnet18": "w.pth"})
        cuts = [row["slug"] for row in plan["rows"] if "sources=@first-labelled" in row["blocks"]]
        self.assertEqual(len(cuts), 4)
        for slug in cuts:
            self.assertEqual(predicted[slug]["predicted"], "not applicable")
            self.assertIn("one source with labelled crops (carmlspine)", predicted[slug]["why"])
            self.assertIn("needs two", predicted[slug]["why"])
        others = [row for row in plan["rows"] if row["role"] == "cover" and row["slug"] not in cuts]
        self.assertTrue(all(predicted[row["slug"]]["predicted"] == "runs" for row in others))
        page = self.sweep.plan_markdown(self.catalog, one, plan, predicted)
        self.assertIn("the first labelled source of several (@first-labelled): none, its train part has one source with labelled crops (carmlspine)", page)

    def test_the_rules_are_asked_in_the_trainers_order(self):
        from schwingnet.blocks import parse

        crops = self.facts["crops"]
        verdict = self.sweep.crops_verdict
        prior = parse(["prior=level-map", "prior_weight=0.5"])
        no_maps = dict(self.facts, crops=[dict(c, map=False) for c in crops])
        self.assertEqual(verdict(prior, 64, no_maps)["code"], "no-map")
        self.assertEqual(verdict(prior, 16, self.facts)["code"], "prior-size")
        self.assertEqual(verdict(prior, 32, self.facts)["predicted"], "runs")
        one = [next(c for c in crops if c["part"] == "train")] + [c for c in crops if c["part"] == "validation"]
        single = dict(self.facts, crops=one)
        self.assertEqual(verdict(parse([]), 32, single)["code"], "one-crop")
        self.assertEqual(verdict(parse([]), 64, single)["predicted"], "runs")
        unscored = dict(self.facts, crops=[c for c in crops if c["part"] == "train"])
        self.assertEqual(verdict(parse([]), 64, unscored)["code"], "no-validation")
        self.assertEqual(verdict(parse(["samples=only-sources", "sources=elsewhere"]), 64, self.facts)["code"], "source-absent")
        parent = (parse([]), 96)
        self.assertEqual(verdict(parse([]), 64, self.facts, parent)["code"], "init-mismatch")
        self.assertEqual(verdict(parse(["denoise=median"]), 96, self.facts, parent)["code"], "init-mismatch")
        self.assertEqual(verdict(parse(["sampler=balanced"]), 96, self.facts, parent)["predicted"], "runs")

    def test_every_named_combination_is_counted_at_every_size(self):
        code, out, err = said(self.sweep, "check", "--catalog", self.catalog, "--all", "--json")
        self.assertEqual(code, 0, err)
        document = json.loads(out)
        cells = document["all"]
        self.assertEqual(len(cells), 4 * 4 * 2)
        self.assertEqual((document["named_per_cell"], document["with_augment_per_cell"]), (1536, 49152))
        for size in (32, 64, 96, 128):
            mine = [c for c in cells if c["size"] == size]
            self.assertEqual(sum(c["named"] for c in mine), 12288)
            self.assertEqual(sum(c["with_augment"] for c in mine), 393216)
            self.assertTrue(all(c["predicted"] == "runs" for c in mine), "every cut trains where two sources hold labelled crops")
            dropping = [c for c in mine if c["samples"] == "drop-sources"]
            self.assertTrue(all("training crops" in c["why"] and c["train_crops"] < max(d["train_crops"] for d in mine) for c in dropping))
        code, page, _ = said(self.sweep, "check", "--catalog", self.catalog, "--all", "--sizes", "32,64")
        self.assertEqual(code, 0)
        self.assertIn("| 32 | 12,288 | 0 | 0 | 12,288 | 393,216 |", page)
        self.assertIn("| 64 | 12,288 | 0 | 0 | 12,288 | 393,216 |", page)
        self.assertNotIn("| 96 |", page)
        self.assertIn("prior_weight is above 0 with prior=level-map, and only there", page)

    def test_a_size_the_rules_were_not_measured_at_is_refused_in_words(self):
        # The prior's head and a batch of one crop depend on the architecture between the sizes
        # measured (densenet121 cannot forward at 16 pixels, the prior head builds at 30 for six
        # of eight), so the check decides only at 32, 64, 96 and 128 and says so.
        for sizes in ("16", "30", "48", "16,64", "256"):
            code, out, err = said(self.sweep, "check", "--catalog", self.catalog, "--all", "--sizes", sizes)
            self.assertEqual((code, out), (1, ""), sizes)
            self.assertIn("32, 64, 96 and 128", err, sizes)
        plan = json.loads((ROOT / "grid" / "sweeps" / "synthetic.json").read_text(encoding="utf-8"))
        plan["rows"] = [dict(plan["rows"][0], size=48)]
        path = self.tmp / "at-48.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        code, out, err = said(self.sweep, "check", "--catalog", self.catalog, "--plan", path)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("48", err)
        self.assertIn("32, 64, 96 and 128", err)

    def test_the_synthetic_catalog_is_built_once_and_found_again(self):
        folder = self.tmp / "synthetic"
        store = Path(self.catalog).parent.parent
        before = (folder / "SYNTHETIC.json").read_bytes(), (store / "VERSIONS.jsonl").read_bytes()
        code, out, _ = said(self.sweep, "synthetic", "--into", folder, *TINY)
        self.assertEqual((code, json.loads(out)), (0, {"catalog": self.catalog, "reused": True}))
        self.assertEqual(before, ((folder / "SYNTHETIC.json").read_bytes(), (store / "VERSIONS.jsonl").read_bytes()))

    def test_prepare_writes_the_state_once_and_lists_the_rows_to_run(self):
        out = self.tmp / "smoke"
        plan = ROOT / "grid" / "sweeps" / "synthetic.json"
        code, printed, err = said(self.sweep, "prepare", "--plan", plan, "--catalog", self.catalog, "--out", out)
        self.assertEqual(code, 0, err)
        answer = json.loads(printed)
        code_sha256 = load_run_code().digest("state")
        named = hashlib.sha256(f"state {code_sha256}\nplan {hashlib.sha256(plan.read_bytes()).hexdigest()}\n".encode("ascii")).hexdigest()
        digest = hashlib.sha256(Path(self.catalog).read_bytes()).hexdigest()
        state = out / "synthetic" / f"{named[:8]}-{digest[:8]}"
        self.assertEqual(answer["state"], str(state))
        self.assertEqual(said(self.sweep, "state", "--plan", plan, "--catalog", self.catalog, "--out", out), (0, f"{state}\n", ""))
        rows = json.loads(plan.read_text(encoding="utf-8"))["rows"]
        weighted = {row["slug"] for row in rows if row["weights"]}
        self.assertEqual(answer["first"], [row["slug"] for row in rows if not row["init"] and row["slug"] not in weighted])
        self.assertEqual(answer["second"], [row["slug"] for row in rows if row["init"] and row["slug"] not in weighted])
        self.assertEqual(sorted(p.stem for p in (state / "rows").glob("*.json")), sorted(weighted), "the rows not applicable are recorded at once")
        resolved = json.loads((state / "PLAN.json").read_text(encoding="utf-8"))
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual((resolved["code_sha256"], resolved["commit"]), (code_sha256, head))
        self.assertEqual(resolved["rows"][9]["blocks"], ["samples=drop-sources", "sources=carmlspine"])
        self.assertEqual(resolved["rows"][9]["planned_blocks"], ["samples=drop-sources", "sources=@first-labelled"])
        results = json.loads((state / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(results["counts"], {"rows": 27, "ran": 0, "refused": 0, "not_applicable": 2, "failed": 0, "to_come": 25, "mismatched": 0})
        names = ("PLAN.json", "CHECK.json", "CHECK-ALL.md")
        stamps = {name: (state / name).stat().st_mtime_ns for name in names}
        (state / "rows" / "kept-by-hand.json").write_text("{}", encoding="utf-8")
        code, again, _ = said(self.sweep, "prepare", "--plan", plan, "--catalog", self.catalog, "--out", out)
        self.assertEqual((code, json.loads(again)), (0, answer))
        self.assertEqual(stamps, {name: (state / name).stat().st_mtime_ns for name in names})
        self.assertEqual((state / "rows" / "kept-by-hand.json").read_text(encoding="utf-8"), "{}")

    def test_another_epoch_count_gets_a_state_of_its_own_and_a_row_asked_for_another_is_refused(self):
        out = self.tmp / "smoke-epochs"
        plan = ROOT / "grid" / "sweeps" / "synthetic.json"
        code, printed, err = said(self.sweep, "prepare", "--plan", plan, "--catalog", self.catalog, "--out", out)
        self.assertEqual(code, 0, err)
        own = Path(json.loads(printed)["state"])
        code, same, err = said(self.sweep, "prepare", "--plan", plan, "--catalog", self.catalog, "--out", out, "--epochs", "3")
        self.assertEqual((code, Path(json.loads(same)["state"])), (0, own), "the plan's own count names the plan's folder")
        code, printed, err = said(self.sweep, "prepare", "--plan", plan, "--catalog", self.catalog, "--out", out, "--epochs", "2")
        self.assertEqual(code, 0, err)
        other = Path(json.loads(printed)["state"])
        self.assertEqual(other, own.with_name(own.name + "-e2"))
        self.assertEqual(json.loads((other / "PLAN.json").read_text(encoding="utf-8"))["epochs"], 2)
        self.assertEqual(json.loads((own / "PLAN.json").read_text(encoding="utf-8"))["epochs"], 3)
        slug = json.loads(printed)["first"][0]
        code, _, err = said(self.sweep, "row", "--state", own, "--slug", slug, "--catalog", self.catalog, "--epochs", "2")
        self.assertEqual(code, 2)
        self.assertIn("prepare with --epochs 2", err)

    def test_a_row_asked_to_train_on_another_catalog_is_refused(self):
        # A state is named for its catalog's sha256 and PLAN.json records it, so a row given
        # another file would land one catalog's result under another's path.
        out = self.tmp / "smoke-other-catalog"
        code, printed, err = said(self.sweep, "prepare", "--plan", ROOT / "grid" / "sweeps" / "synthetic.json", "--catalog", self.catalog, "--out", out)
        self.assertEqual(code, 0, err)
        state = Path(json.loads(printed)["state"])
        other = self.tmp / "other.sqlite"
        other.write_bytes(Path(self.catalog).read_bytes() + b"\0")
        plan = json.loads((state / "PLAN.json").read_text(encoding="utf-8"))
        slug = next(row["slug"] for row in plan["rows"] if row["role"] == "imagenet")
        (state / "rows" / f"{slug}.json").unlink()
        code, _, err = said(self.sweep, "row", "--state", state, "--slug", slug, "--catalog", other)
        self.assertEqual(code, 2)
        self.assertIn(plan["catalog_sha256"][:12], err)
        self.assertIn("not the catalog", err)
        self.assertFalse((state / "rows" / f"{slug}.json").exists(), "nothing is recorded for it")
        code, _, err = said(self.sweep, "row", "--state", state, "--slug", slug, "--catalog", self.catalog)
        self.assertEqual(code, 0, err)

    def test_a_row_that_cannot_be_run_exits_two(self):
        code, _, err = said(self.sweep, "row", "--state", self.tmp / "no-state", "--slug", "x", "--catalog", self.catalog)
        self.assertEqual(code, 2)
        self.assertIn("run prepare first", err)
        out = self.tmp / "smoke-two"
        code, printed, _ = said(self.sweep, "prepare", "--plan", ROOT / "grid" / "sweeps" / "real.json", "--catalog", self.catalog, "--out", out)
        state = json.loads(printed)["state"]
        code, _, err = said(self.sweep, "row", "--state", state, "--slug", "resnet18-64px-00000000", "--catalog", self.catalog)
        self.assertEqual(code, 2)
        self.assertIn("no row resnet18-64px-00000000", err)


def with_words(words, **changed):
    """TINY's words with some values changed, as `synthetic` takes them."""
    out = list(words)
    for name, value in changed.items():
        out[out.index(f"--{name.replace('_', '-')}") + 1] = str(value)
    return out


QUIET_GIT = ["-c", "gc.auto=0", "-c", "gc.autoDetach=false", "-c", "maintenance.auto=false", "-c", "maintenance.autoDetach=false",
             "-c", "user.name=test", "-c", "user.email=test@example.invalid"]


def commit_all(repo, message):
    for words in (["add", "-A"], ["commit", "-q", "-m", message]):
        subprocess.run(["git", "-C", str(repo), *QUIET_GIT, *words], check=True, capture_output=True)


def head_of(repo):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def tool_in(repo, *argv, timeout=600):
    """block_sweep in a copy of the repository, as the grid's checkout runs it: what it printed."""
    done = subprocess.run([sys.executable, str(repo / "tools" / "block_sweep.py"), *map(str, argv)], cwd=repo, capture_output=True, text=True,
                          timeout=timeout, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    if done.returncode != 0:
        raise AssertionError(f"block_sweep {argv[0]} exited {done.returncode}: {done.stderr[-3000:]}")
    return done.stdout


def append_line(path, line):
    with path.open("a", encoding="utf-8") as out:
        out.write(line + "\n")


@unittest.skipIf(MISSING, f"needs the package's checkers ({', '.join(MISSING)} missing)")
class StateNameTest(unittest.TestCase):
    """A sweep's state is named by the code its rows run and its plan file, and not by the commit
    it was prepared on (finding 27 of #252): main merges many times a day, and a sweep cut short
    and started again after a merge that changes none of that code must carry its finished rows
    on. In a clean copy of the repository, as the grid's checkout is, so a tool can be changed and
    committed there."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.repo = cls.tmp / "repo"
        clean_copy(cls.repo)
        cls.catalog = json.loads(tool_in(cls.repo, "synthetic", "--into", cls.tmp / "synthetic", *TINY))["catalog"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_merge_that_changes_no_code_a_row_runs_names_the_same_state_and_keeps_its_first_commit(self):
        plan = self.tmp / "plan.json"
        shutil.copyfile(ROOT / "grid" / "sweeps" / "synthetic.json", plan)
        words = ["--plan", plan, "--catalog", self.catalog, "--out", self.tmp / "smoke"]
        first, prepared_on = json.loads(tool_in(self.repo, "prepare", *words)), head_of(self.repo)
        state = Path(first["state"])
        self.assertEqual(tool_in(self.repo, "state", *words), f"{state}\n")
        recorded = json.loads((state / "PLAN.json").read_text(encoding="utf-8"))
        self.assertEqual((recorded["commit"], recorded["code_sha256"]), (prepared_on, load_run_code(self.repo).digest("state")))
        append_line(self.repo / "tools" / "textbook_site.py", "# a page no row runs")
        commit_all(self.repo, "a merge that changes nothing a row runs")
        self.assertEqual(json.loads(tool_in(self.repo, "prepare", *words)), first)
        self.assertEqual(json.loads((state / "PLAN.json").read_text(encoding="utf-8"))["commit"], prepared_on, "the commit it was first prepared on")
        append_line(self.repo / "tools" / "train.py", "# the trainer, changed")
        commit_all(self.repo, "a change to the trainer")
        other = Path(tool_in(self.repo, "state", *words).strip())
        self.assertNotEqual(other, state, "a change to the code a row runs names another state")
        self.assertEqual((other.parent, other.name[8:]), (state.parent, state.name[8:]), "the same plan and catalog")
        edited = json.loads(plan.read_text(encoding="utf-8"))
        plan.write_text(json.dumps({**edited, "about": edited["about"] + " Edited."}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        self.assertNotIn(Path(tool_in(self.repo, "state", *words).strip()), (state, other), "an edited plan names another state")


@unittest.skipIf(MISSING, f"needs the package's checkers ({', '.join(MISSING)} missing)")
class SyntheticBuildTest(unittest.TestCase):
    """The synthetic catalog is found again where its arguments and the code that makes it are
    the same, built anew where either differs, and never blocked by a build cut short. The runs
    are in a clean copy of the repository's tools, as the grid's checkout is, so a tool can be
    changed there."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.repo = cls.tmp / "repo"
        clean_copy(cls.repo)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, into, words=TINY):
        done = subprocess.run([sys.executable, str(self.repo / "tools" / "block_sweep.py"), "synthetic", "--into", str(into), *words],
                              cwd=self.repo, capture_output=True, text=True, timeout=600, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def commit(self, message):
        commit_all(self.repo, message)

    def test_other_arguments_build_anew_and_the_folder_they_replace_goes(self):
        into = self.tmp / "arguments"
        first = self.build(into)
        second = self.build(into, with_words(TINY, frames=81))
        self.assertFalse(second["reused"])
        self.assertNotEqual(second["catalog"], first["catalog"])
        self.assertTrue(Path(second["catalog"]).is_file())
        self.assertFalse(Path(first["catalog"]).exists(), "the build the record no longer names is removed")
        record = json.loads((into / "SYNTHETIC.json").read_text(encoding="utf-8"))
        self.assertEqual((record["arguments"]["frames"], record["catalog"]), (81, second["catalog"]))
        self.assertEqual(self.build(into, with_words(TINY, frames=81)), {"catalog": second["catalog"], "reused": True})

    def test_a_build_cut_short_never_blocks_the_next(self):
        # Cut between the catalog's version file and its log line, the one moment a catalog build
        # leaves what the next build at the same commit refuses ("a file of that name is already
        # there"), and before the record: the next run builds afresh and drops the cut folder.
        into = self.tmp / "cut"
        first = Path(self.build(into)["catalog"])
        store = first.parent.parent
        (store / "VERSIONS.jsonl").write_text("", encoding="utf-8")
        (store / "CURRENT").unlink()
        (into / "SYNTHETIC.json").unlink()
        again = self.build(into)
        self.assertFalse(again["reused"])
        self.assertTrue(Path(again["catalog"]).is_file())
        self.assertFalse(store.exists(), "the cut build's folder is cleared")

    def test_the_code_that_makes_it_builds_it_again_and_other_code_does_not(self):
        into = self.tmp / "code"
        first = self.build(into)
        with (self.repo / "tools" / "train.py").open("a", encoding="utf-8") as out:
            out.write("# a change the synthetic catalog does not depend on\n")
        self.commit("an unrelated change")
        self.assertEqual(self.build(into), {"catalog": first["catalog"], "reused": True}, "a merge elsewhere rebuilds nothing")
        with (self.repo / "tools" / "synthetic_bank.py").open("a", encoding="utf-8") as out:
            out.write("# a change to the bank's writer\n")
        self.commit("a change to the bank's writer")
        rebuilt = self.build(into)
        self.assertFalse(rebuilt["reused"], "a catalog older code made is made again")
        self.assertNotEqual(rebuilt["catalog"], first["catalog"])


@unittest.skipIf(MISSING, f"needs the package's checkers ({', '.join(MISSING)} missing)")
class ResultsTest(unittest.TestCase):
    """results.json, RESULTS.md and PROGRESS.txt from a state folder made by hand, and what a row's
    logs say came of it."""

    @classmethod
    def setUpClass(cls):
        cls.sweep = load()

    def setUp(self):
        self.state = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.state, ignore_errors=True)

    def make_state(self):
        rows = [{"slug": f"resnet18-64px-0000000{n}", "role": "cover", "size": 64, "blocks": [], "planned_blocks": [], "weights": None, "init": None} for n in range(3)]
        plan = {"plan": "handmade", "about": "", "catalog": "v1", "catalog_file": "/data/catalog-000001-abcdefabcdef.sqlite", "catalog_sha256": "a" * 64,
                "catalog_version": 1, "commit": "b" * 40, "epochs": 1, "seed": 1, "state": str(self.state), "rows": rows}
        check = {"rows": [{"slug": r["slug"], "role": "cover", "predicted": p, "code": c, "why": "", "train_crops": 9}
                          for r, (p, c) in zip(rows, [("runs", None), ("refused", "no-map"), ("runs", None)], strict=True)]}
        (self.state / "PLAN.json").write_text(json.dumps(plan), encoding="utf-8")
        (self.state / "CHECK.json").write_text(json.dumps(check), encoding="utf-8")
        ran = self.state / rows[0]["slug"]
        (ran / "train").mkdir(parents=True)
        (ran / "evaluate").mkdir()
        (ran / "RUN.json").write_text(json.dumps({"run_id": "1234567890ab"}), encoding="utf-8")
        (ran / "train" / "checkpoint.json").write_text(json.dumps({"validation_accuracy": 0.5, "counts": {"train": 9}}), encoding="utf-8")
        (ran / "evaluate" / "results.json").write_text(json.dumps({"rows": [{"measure": "accuracy", "stratum": "all levels", "correct": 3, "total": 4}]}), encoding="utf-8")
        (ran / "wandb-sync.json").write_text(json.dumps({"synced": True, "urls": ["https://wandb.ai/x/y/runs/abc"]}), encoding="utf-8")
        predictions = {entry["slug"]: entry for entry in check["rows"]}
        for row, (outcome, code) in ((rows[0], ("ran", None)), (rows[1], ("refused", "one-crop"))):
            entry = self.sweep.entry_of(row, predictions[row["slug"]], outcome, code, "", self.state)
            (self.state / "rows").mkdir(exist_ok=True)
            (self.state / "rows" / f"{row['slug']}.json").write_text(json.dumps(entry), encoding="utf-8")
        return rows

    def test_the_results_are_rebuilt_from_the_rows_alone(self):
        rows = self.make_state()
        code, printed, err = said(self.sweep, "results", self.state)
        self.assertEqual(code, 0, err)
        results = json.loads((self.state / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(results["counts"], {"rows": 3, "ran": 1, "refused": 1, "not_applicable": 0, "failed": 0, "to_come": 1, "mismatched": 1})
        self.assertEqual(json.loads(printed)["counts"], results["counts"])
        first, second, third = results["rows"]
        self.assertEqual((first["run_id"], first["train_crops"], first["validation_accuracy"], first["test_accuracy"]), ("1234567890ab", 9, 0.5, 0.75))
        self.assertEqual(first["wandb"], ["https://wandb.ai/x/y/runs/abc"])
        self.assertTrue(first["matched"])
        self.assertFalse(second["matched"], "refused for another code than the one predicted")
        self.assertEqual((third["outcome"], third["matched"]), ("to-come", None))
        page = (self.state / "RESULTS.md").read_text(encoding="utf-8")
        self.assertIn("1 DID NOT DO WHAT THE CHECK PREDICTED", page)
        self.assertIn(f"| {rows[0]['slug']} | cover | 64 | version 1 | runs | ran | matched | 9 | 0.500 | 0.750 |", page)
        lines = (self.state / "PROGRESS.txt").read_text(encoding="utf-8").splitlines()
        self.assertRegex(lines[0], r"^plan handmade state \S+ rows 3 ran 1 refused 1 not_applicable 0 failed 0 to_come 1 mismatched 1 updated \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(lines[1:], [f"row {rows[0]['slug']} ran matched", f"row {rows[1]['slug']} refused mismatched", f"row {rows[2]['slug']} to-come -",
                                     "wandb https://wandb.ai/x/y/runs/abc"])
        self.assertFalse([p for p in self.state.iterdir() if p.name.startswith(".") and p.name != ".lock"], "no half-written file left beside its place")

    def test_progress_holds_at_most_sixty_lines(self):
        entries = [{"slug": f"r{n}", "outcome": "ran", "matched": True, "wandb": [f"https://wandb.ai/a/b/runs/{n}"]} for n in range(50)]
        results = {"plan": "p", "state": "s", "updated_at": "2026-10-24T00:00:00Z", "rows": entries,
                   "counts": {"rows": 50, "ran": 50, "refused": 0, "not_applicable": 0, "failed": 0, "to_come": 0, "mismatched": 0}}
        self.assertEqual(len(self.sweep.progress_text(results).splitlines()), 60)

    def write_logs(self, slug, flow, train=None):
        (self.state / f"{slug}.flow.log").write_text(flow, encoding="utf-8")
        if train is not None:
            (self.state / slug).mkdir(exist_ok=True)
            (self.state / slug / "train.log").write_text(train, encoding="utf-8")

    def test_a_rows_outcome_is_read_from_its_last_attempt(self):
        observed = self.sweep.observed
        self.write_logs("a", "flow: train exited 1; see a/train.log\n", '{"epoch": 0}\ntrain: prior=level-map: no training crop comes from a frame with a level map; a map rides\n')
        self.assertEqual(observed(self.state, "a", 1)[:2], ("refused", "no-map"))
        self.write_logs("b", "flow: train exited 1; see b/train.log\n",
                        "train: one training crop: resnet18 cannot take a training step\n\n=== train run again at 2026-10-24T00:00:00Z, the run's folder held: restarted ===\nTraceback (most recent call last):\nValueError: boom\n")
        self.assertEqual(observed(self.state, "b", 1)[:2], ("failed", None))
        self.write_logs("c", "flow: blocks: weight_decay is for adamw\n")
        self.assertEqual(observed(self.state, "c", 1)[:2], ("refused", "problems"))
        self.write_logs("d", "flow: --init /s/p/train/best.pt: no parent checkpoint there\n")
        self.assertEqual(observed(self.state, "d", 1)[:2], ("failed", None))
        self.write_logs("e", "flow: train exited 1; see e/train.log\n", "train: a run starts from ImageNet (--weights) or from a parent (--init), not both\n")
        self.assertEqual(observed(self.state, "e", 1)[:2], ("refused", "init-and-weights"))
        self.write_logs("f", "", None)
        (self.state / "f" / "evaluate").mkdir(parents=True)
        (self.state / "f" / "evaluate" / "results.json").write_text("{}", encoding="utf-8")
        self.assertEqual(observed(self.state, "f", 0)[:2], ("ran", None))
        self.assertEqual(observed(self.state, "f", 1)[:2], ("failed", None), "a flow that exited 1 did not finish, whatever its folder holds")

    def test_every_refusal_code_is_found_in_the_words_the_tools_refuse_with(self):
        texts = {
            "problems": "blocks: weight_decay is for adamw",
            "init-and-weights": "a run starts from ImageNet (--weights) or from a parent (--init), not both",
            "source-absent": "sources=vindr_spinexr: not in the catalog's train part, whose sources are carmlspine",
            "cut-leaves-none": "the samples block (samples=drop-sources sources=carmlspine) leaves none of the 9 training crops",
            "no-validation": "the catalog has no labelled train or validation crops",
            "init-mismatch": "the parent was trained on 64-pixel crops, this run on 96",
            "no-map": "prior=level-map: no training crop comes from a frame with a level map; a map rides in a render's shard",
            "prior-size": "at 16-pixel crops no stage of resnet18 keeps 8 cells across the crop for the prior's head; the shallowest, layer1, gives 4 by 4; take a larger crop",
            "one-crop": "one training crop: resnet18 cannot take a training step on a batch of one 32-pixel crop",
        }
        self.assertEqual(set(texts), set(self.sweep.REFUSALS))
        for code, text in texts.items():
            self.assertEqual(self.sweep.code_of(f"train: {text}"), code, text)


def fake_pixi(folder, repo):
    """A pixi that runs `pixi run [--locked] [-e ENV] python ARGS` with this test's python and the
    copy's package on the path, as the real one runs the locked environment."""
    path = folder / "pixi"
    path.write_text(
        "#!/bin/bash\n"
        "[ \"$1\" = run ] || exit 64\nshift\n"
        "while [ $# -gt 0 ]; do case \"$1\" in --locked|--frozen) shift ;; -e|--environment) shift 2 ;; *) break ;; esac; done\n"
        "[ \"$1\" = python ] && shift\n"
        f"PYTHONPATH={repo}/src:{repo}/vendor/beethoven-qa/src exec {sys.executable} \"$@\"\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def clean_copy(into):
    """The repository's tools, package, pinned copy and data as they stand here, committed in a
    repository of their own: the flow refuses a dirty tree, and a working copy being changed is
    one, so the rows run from a clean commit of the same files."""
    for name in ("tools", "src", "vendor", "data"):
        shutil.copytree(ROOT / name, into / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # pixi.lock too, since a run is named by the code it runs and the locked environment is part of it
    for name in ("pyproject.toml", "pixi.toml", "pixi.lock", ".gitignore"):
        shutil.copyfile(ROOT / name, into / name)
    subprocess.run(["git", "-C", str(into), *QUIET_GIT, "init", "-q"], check=True, capture_output=True)
    commit_all(into, "a copy for the smoke rows")


@unittest.skipIf(TORCH_MISSING, f"needs the train environment ({', '.join(TORCH_MISSING)} missing)")
class RowRunTest(unittest.TestCase):
    """prepare, then row for one row of each role on a tiny synthetic catalog, each through the
    real flow and trainer for one epoch on the CPU: every row does what the check predicted."""

    @classmethod
    def setUpClass(cls):
        import torch
        import torchvision

        cls.tmp = Path(tempfile.mkdtemp())
        try:
            cls.run_rows(torch, torchvision)
        except BaseException:
            # unittest calls no tearDownClass after a failed setUpClass, and the rows' weights
            # are hundreds of megabytes, so a failure here removes them itself.
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise

    @classmethod
    def run_rows(cls, torch, torchvision):
        cls.repo = cls.tmp / "repo"
        clean_copy(cls.repo)
        (cls.tmp / "bin").mkdir()
        fake_pixi(cls.tmp / "bin", cls.repo)
        cls.weights = cls.tmp / "resnet18.pth"
        torch.save(torchvision.models.resnet18(weights=None).state_dict(), cls.weights)
        cls.env = dict(os.environ, PATH=f"{cls.tmp / 'bin'}:{os.environ['PATH']}", SCHWINGNET_WANDB="off", PYTHONDONTWRITEBYTECODE="1",
                       PYTHONPATH=f"{cls.repo}/src:{cls.repo}/vendor/beethoven-qa/src")
        cls.catalog = json.loads(cls.tool("synthetic", "--into", cls.tmp / "synthetic", *TINY))["catalog"]
        rows = json.loads((ROOT / "grid" / "sweeps" / "synthetic.json").read_text(encoding="utf-8"))["rows"]
        cuts = [row for row in rows if row["role"] == "cover" and "sources=@first-labelled" in row["blocks"] and "prior=level-map" not in row["blocks"]]
        chosen = [rows[0], *cuts, *(row for row in rows if row["role"] != "cover")]
        cls.plan = cls.tmp / "plan.json"
        cls.plan.write_text(json.dumps({"plan": "tiny", "about": "", "catalog": "synthetic", "epochs": 1, "seed": 1, "rows": chosen}), encoding="utf-8")
        cls.prepared = json.loads(cls.tool("prepare", "--plan", cls.plan, "--catalog", cls.catalog, "--out", cls.tmp / "smoke", "--weights", f"resnet18={cls.weights}"))
        cls.state = Path(cls.prepared["state"])
        cls.entries = {}
        for slug in cls.prepared["first"] + cls.prepared["second"]:
            cls.entries[slug] = json.loads(cls.tool("row", "--state", cls.state, "--slug", slug, "--catalog", cls.catalog,
                                                    "--environment", "train-cpu", "--weights", f"resnet18={cls.weights}"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def tool(cls, *argv):
        done = subprocess.run([sys.executable, str(cls.repo / "tools" / "block_sweep.py"), *map(str, argv)], cwd=cls.repo, env=cls.env,
                              capture_output=True, text=True, timeout=1800)
        if done.returncode != 0:
            raise AssertionError(f"block_sweep {argv[0]} exited {done.returncode}: {done.stderr[-3000:]}")
        return done.stdout

    def test_every_row_did_what_the_check_predicted(self):
        self.assertEqual(len(self.entries), 10)
        wrong = {slug: (e["predicted"], e["predicted_code"], e["outcome"], e["code"], e["why"]) for slug, e in self.entries.items() if not e["matched"]}
        self.assertEqual(wrong, {}, "a row whose outcome differs from its prediction is a bug")
        outcomes = sorted((e["role"], e["outcome"], e["code"] or "") for e in self.entries.values())
        self.assertEqual(outcomes, [("cover", "ran", ""), ("cover", "ran", ""), ("cover", "ran", ""), ("imagenet", "ran", ""), ("init", "ran", ""),
                                    ("init", "ran", ""), ("refuse", "refused", "cut-leaves-none"), ("refuse", "refused", "init-and-weights"),
                                    ("refuse", "refused", "init-mismatch"), ("refuse", "refused", "source-absent")])
        results = json.loads((self.state / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(results["counts"], {"rows": 10, "ran": 6, "refused": 4, "not_applicable": 0, "failed": 0, "to_come": 0, "mismatched": 0})
        ran = [e for e in self.entries.values() if e["outcome"] == "ran"]
        self.assertTrue(all(e["run_id"] and e["train_crops"] and e["test_accuracy"] is not None for e in ran))

    def test_each_source_cut_trained_on_a_strict_part_of_the_labelled_crops(self):
        rows = json.loads(self.plan.read_text(encoding="utf-8"))["rows"]
        everything = self.entries[rows[0]["slug"]]["train_crops"]
        kept = {samples_of(row): self.entries[row["slug"]]["train_crops"] for row in rows[1:3]}
        self.assertEqual(set(kept), {"only-sources", "drop-sources"})
        self.assertTrue(all(0 < count < everything for count in kept.values()), (kept, everything))
        self.assertEqual(sum(kept.values()), everything, "the crops kept and the crops dropped of one source make the whole")

    def test_a_row_that_ran_keeps_best_pt_and_drops_each_epochs_weights(self):
        parent = self.state / self.prepared["first"][0]
        self.assertTrue((parent / "train" / "best.pt").is_file(), "a warm start reads it")
        self.assertEqual(list((parent / "train" / "epochs").glob("*.pt")), [])

    def test_a_finished_row_run_again_records_the_same_entry_and_trains_nothing(self):
        slug = self.prepared["first"][0]
        log = self.state / slug / "train.log"
        before = log.read_bytes()
        again = json.loads(self.tool("row", "--state", self.state, "--slug", slug, "--catalog", self.catalog, "--environment", "train-cpu"))
        self.assertEqual(again, self.entries[slug])
        self.assertEqual(log.read_bytes(), before)
        self.assertIn('"reused": "finished"', (self.state / f"{slug}.flow.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
