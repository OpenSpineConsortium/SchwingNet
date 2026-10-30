"""The auto-anatomist screen's trial and join, run for real on small synthetic CTs: two trials of a
CPU plan train, read their validation CT after each epoch and write entries the join reads and
decides on, a label the plan does not name never reaches a crop, a row whose CT is missing is
refused with 2, environments other than the pinned one are refused with 3, and a trial whose loss or
weights stop being finite numbers stops with 1 before it reads.

It needs the trial's environment, the packages schwingnet.autoanatomist_screen.PINS names beside
beartype and icontract, which neither CI's python3 nor the pixi environments hold, so it is skipped
there: run it in a virtual environment holding the pins over Python 3.11, as
    <venv>/bin/python -m unittest tests.test_autoanatomist_trial -v
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRIAL = ROOT / "tools" / "autoanatomist_trial.py"
JOIN = ROOT / "tools" / "autoanatomist_join.py"
NEEDED = ("jax", "flax", "optax", "nibabel", "scipy", "numpy", "beartype", "icontract", "matplotlib")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
# Five lumbar levels, labels 20 to 24 as ENHANCE.PET numbers them; C2 (2), the sacrum (28) and a
# hip (26) are drawn too, and the plan names none of them.
NAMED = {str(label): f"L{label - 19}" for label in range(20, 25)}
UNNAMED = (2, 26, 28)


def draw_spine(folder, name, seed):
    """A small CT and its label map: five vertebrae 30 mm apart along z, an unnamed label above
    and below them and a hip beside, at 2 mm, as NIfTI on one grid."""
    import nibabel as nib
    import numpy as np

    rng = np.random.default_rng(seed)
    shape = (60, 60, 110)
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    grid = np.stack(np.meshgrid(*[np.arange(n) * 2.0 for n in shape], indexing="ij"), -1)
    labels = np.zeros(shape, np.uint8)
    centres = {2: (60, 60, 200), 20: (60, 60, 170), 21: (60, 62, 140), 22: (60, 64, 110), 23: (60, 62, 80),
               24: (60, 60, 50), 28: (60, 58, 20), 26: (95, 60, 30)}
    for label, centre in centres.items():
        inside = (((grid - np.array(centre, float) - rng.normal(0, 1, 3)) / np.array([12.0, 10.0, 9.0])) ** 2).sum(-1) < 1
        labels[inside] = label
    ct = np.where(labels > 0, 400.0, -50.0) + rng.normal(0, 20, shape)
    (folder / "ct").mkdir(parents=True, exist_ok=True)
    (folder / "labels" / "Vertebrae").mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(ct.astype(np.int16), affine), folder / "ct" / f"{name}.nii.gz")
    nib.save(nib.Nifti1Image(labels, affine), folder / "labels" / "Vertebrae" / f"{name}.nii.gz")


def plan_record(rows):
    return {"screen": "synthetic_screen", "purpose": "The trial and the join on synthetic CTs.", "class": "batch",
            "layout": "series",
            "data": {"synth": {"ct": "ct", "labels": "labels", "labels_folder": "Vertebrae", "names": NAMED}},
            "rows": rows, "split": {"salt": "s", "validation_share": 0.5}, "test": "off",
            "fixed": ["objective=mask", "naming=off", "widths=4:8:8"],
            "arms": {"joint": ["schedule=joint"], "null": ["schedule=fixed", "lam_fixed=1", "w_fixed=0", "w_feature=0"]},
            "null": "null", "seeds": [1], "epochs": 2, "evaluate_every": 1, "batch": 2, "measure": "distance_mm"}


@unittest.skipIf(MISSING, f"needs the trial's environment ({', '.join(MISSING)} missing)")
class TrialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.data, cls.out = root / "data", root / "study"
        rows = []
        for n, part in enumerate(("train", "train", "train", "validation")):
            draw_spine(cls.data, f"{n:04d}", seed=n)
            rows.append({"item": f"synth:{n:04d}", "person": f"synth:{n:04d}", "part": part, "source": "synth"})
        cls.plan = root / "plan.json"
        cls.plan.write_text(json.dumps(plan_record(rows)), encoding="utf-8")
        cls.done = [cls.trial(task) for task in (0, 1)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def trial(cls, task, plan=None, out=None):
        command = [sys.executable, str(TRIAL), "--plan", str(plan or cls.plan), "--task", str(task), "--tasks", "2",
                   "--data", str(cls.data), "--out", str(out or cls.out), "--workers", "2", "--scratch", cls.tmp.name]
        return subprocess.run(command, capture_output=True, text=True, timeout=1200)

    def test_each_trial_writes_an_entry_with_a_reading_after_each_epoch(self):
        for done in self.done:
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        for trial in ("joint_s1", "null_s1"):
            folder = self.out / "trials" / trial
            entry = json.loads((folder / "entry.json").read_text(encoding="utf-8"))
            self.assertEqual([p["epoch"] for p in entry["epochs"]], [1, 2])
            self.assertEqual([p["steps"] for p in entry["epochs"]], [2, 4])
            self.assertEqual(entry["final"]["distance_mm"], entry["epochs"][-1]["distance_mm"])
            self.assertEqual((entry["train_rows"], entry["validation_rows"]), (3, 1))
            readings = (folder / "readings.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual([json.loads(line)["epoch"] for line in readings], [1, 2])
            self.assertTrue((folder / "session" / "state.npz").is_file())
            environment = json.loads((folder / "environment.json").read_text(encoding="utf-8"))
            self.assertEqual(environment["crops"], {"train": 15, "validation": 5})
            self.assertEqual(environment["matmul_precision"], "highest")
            self.assertIn("jax", environment["gpu_stack"])
            self.assertEqual(environment["step_seconds"]["steps"], 4)
            self.assertGreater(entry["seconds_per_crop"], 0.0)
            self.assertFalse((folder / "why.txt").exists())

    def test_the_latents_are_keyed_by_row_and_level_and_no_unnamed_label_reaches_a_crop(self):
        import numpy as np

        with np.load(self.out / "trials" / "null_s1" / "latents.npz") as z:
            self.assertEqual(z["train_latent"].shape, (15, 8))
            self.assertEqual(sorted(set(z["validation_item"].tolist())), ["synth:0003"])
            self.assertEqual(sorted(set(z["train_name"].tolist())), list(range(17, 22)))
        # The tool puts its own folders on the path as it loads, so the test's path is put back after.
        kept = list(sys.path)
        try:
            spec = importlib.util.spec_from_file_location("autoanatomist_trial", TRIAL)
            tool = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tool)
        finally:
            sys.path[:] = kept
        import nibabel as nib

        copy = Path(self.tmp.name) / "copy.nii"
        tool.spine_only_copy(str(self.data / "labels" / "Vertebrae" / "0000.nii.gz"), str(copy), NAMED)
        kept = np.asanyarray(nib.load(copy).dataobj)
        original = nib.load(self.data / "labels" / "Vertebrae" / "0000.nii.gz")
        self.assertEqual(sorted(set(np.unique(kept).tolist())), [0, 20, 21, 22, 23, 24])
        self.assertTrue(np.allclose(nib.load(copy).affine, original.affine))
        self.assertTrue(np.array_equal(kept > 0, np.isin(np.asanyarray(original.dataobj), list(range(20, 25)))))

    def test_the_join_decides_on_the_two_entries(self):
        done = subprocess.run([sys.executable, str(JOIN), "--plan", str(self.plan), "--out", str(self.out)],
                              capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        decision = json.loads((self.out / "join" / "DECISION.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["failed"], {})
        self.assertIn(decision["arms"]["joint"]["beats_null"], (True, False))
        for name in ("curves.png", "finals.png", "SUMMARY.md"):
            self.assertTrue((self.out / "join" / name).is_file(), name)

    def test_a_missing_ct_is_refused_with_2_and_said_in_why(self):
        record = json.loads(self.plan.read_text(encoding="utf-8"))
        record["rows"][0]["item"] = record["rows"][0]["person"] = "synth:0099"
        plan = Path(self.tmp.name) / "missing.json"
        plan.write_text(json.dumps(record), encoding="utf-8")
        out = Path(self.tmp.name) / "missing-study"
        done = self.trial(0, plan=plan, out=out)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("no CT 0099.nii.gz", (out / "trials" / "joint_s1" / "why.txt").read_text(encoding="utf-8"))
        self.assertFalse((out / "trials" / "joint_s1" / "entry.json").exists())

    def test_a_task_the_plan_does_not_hold_is_refused_with_2_before_any_folder(self):
        out = Path(self.tmp.name) / "task-study"
        done = self.trial(2, out=out)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("outside the array", done.stdout)
        self.assertFalse(out.exists())


def load_tool():
    """The trial tool as a module; it puts its own folders on the path as it loads, so the test's
    path is put back after."""
    kept = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location("autoanatomist_trial", TRIAL)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
    finally:
        sys.path[:] = kept
    return tool


@unittest.skipIf(MISSING, f"needs the trial's environment ({', '.join(MISSING)} missing)")
class DivergenceTest(unittest.TestCase):
    """A diverged network outlines nothing, so every crop would read the worst distance as though
    it were a result: the trial stops with 1 at the first loss, or the first reading's weights,
    that is not a finite number."""

    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()
        rows = [{"item": f"synth:{n:04d}", "person": f"synth:{n:04d}", "part": part, "source": "synth"}
                for n, part in enumerate(("train", "train", "train", "validation"))]
        cls.plan = cls.tool.plan_of(plan_record(rows))
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def session(self, nan_weights):
        import jax
        import jax.numpy as jnp
        from flax import nnx

        sys.path.insert(0, str(ROOT / "grid" / "autoanatomist"))
        try:
            from autoanatomist.blocks import parse
            from autoanatomist.session import Session
        finally:
            sys.path.remove(str(ROOT / "grid" / "autoanatomist"))
        session = Session.new(parse(["objective=mask", "naming=off", "widths=4:8:8", "seed=1"]))
        if nan_weights:
            graph, state = nnx.split(session.model)
            spoiled = jax.tree.map(lambda x: x * jnp.nan if jnp.issubdtype(x.dtype, jnp.floating) else x, state)
            session.model = nnx.merge(graph, spoiled)
        return session

    def train_and_read(self, session, totals):
        def train(ex, steps, on_step):
            for step, total in zip(range(steps), totals, strict=False):
                on_step({"step": step, "total": total, "seconds": 0.1})

        def evaluate(ex):
            raise AssertionError("a diverged network was read")

        session.train, session.evaluate = train, evaluate
        with self.assertRaises(self.tool.TrialRefused) as caught:
            self.tool.train_and_read(session, None, None, self.plan, Path(self.tmp.name), lambda line: None)
        return caught.exception

    def test_a_loss_that_is_not_a_finite_number_stops_the_trial_with_1(self):
        refused = self.train_and_read(self.session(nan_weights=False), [0.5, float("nan")])
        self.assertEqual(refused.code, 1)
        self.assertIn("training diverged: the loss of step 1 is nan", str(refused))

    def test_weights_that_are_not_finite_numbers_stop_the_first_reading_with_1(self):
        self.assertTrue(self.tool.weights_finite(self.session(nan_weights=False)))
        refused = self.train_and_read(self.session(nan_weights=True), [0.5, 0.5])
        self.assertEqual(refused.code, 1)
        self.assertIn("a weight is not a finite number after epoch 1", str(refused))

    def test_a_steady_step_is_the_median_so_the_steps_that_compile_count_for_nothing(self):
        self.assertEqual(self.tool.steady_seconds([12.3, 1.92, 1.85, 1.64, 2.21]), 1.92)
        self.assertEqual(self.tool.steady_seconds([]), 0.0)


if __name__ == "__main__":
    unittest.main()
