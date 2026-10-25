"""tools/train.py's --resume and its last batch of one crop (#252).

A run cut mid-way, as a Slurm timeout or a preemption cuts it, goes on from train/last.pt and
ends, on the CPU, on the same lines, best.pt, prior head and checkpoint.json as a run that went
through, the seconds apart; the cut is made here by the trainer's own save function raising
after its second write, patched in this process, so the trainer carries no hook for tests. A
--resume with nothing to resume, or with other arguments than the run was started with, is
refused in words, as is one whose catalog, ImageNet file or parent is not the bytes the run
started from, while the same file at another path resumes; a last.pt that cannot be read, or
whose bytes its record train/last.pt.sha256 does not name, as a stretch of zeros a node that died
left in it, is moved aside and the run trains again from epoch 0, as it is where last.pt's best
line names weights best.pt does not hold; a second trainer in a folder another holds is refused
and touches nothing; last.pt is gone once a run has finished; and the evaluator scores only a
best.pt train/checkpoint.json names by its sha256, refusing in words otherwise. W&B's run goes on
under the same id. And at 32 pixels, where batch norm cannot train on one crop, a training part
of 65 crops, whose last batch of 64 would hold one, still trains, while at 64 pixels the batches
are as they always were.

The trainer's tests need the train environment, as tests/test_train_blocks.py does, and skip
under the required check's plain python3; the W&B test needs nothing but the standard library."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

# By the module, not its classes, so this file runs none of that file's tests; imported now, since
# loading tools/train.py takes this folder's parent off the path.
import tests.test_train_blocks as blocks_tests
import tests.test_wandb_log as wandb_tests

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("torch", "PIL", "numpy", "beartype", "icontract", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
# The blocks that draw from the run's generator and hold state of their own, the prior head's
# among them, so the resumed run has every state to take back.
EVERY_BLOCK = ["normalise=imagenet", "augment=box-jitter,intensity,blur,noise", "optimiser=adamw", "weight_decay=0.01",
               "schedule=cosine", "warmup_epochs=1", "backbone_lr_scale=0.5", "sampler=balanced",
               "loss_weights=inverse-frequency", "select=balanced-accuracy", "prior=level-map", "prior_weight=0.5"]


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_resume_under_test", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def new_run(folder, run_id, witness=None):
    folder.mkdir(parents=True)
    record = {"run_id": run_id, "code_commit": "0" * 40, "catalog_sha256": "0" * 64, "catalog_version": 1, "clean_tree": True}
    (folder / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
    if witness is not None:
        (folder / "witness.json").write_text(json.dumps(witness), encoding="utf-8")
    return folder


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def untimed(line):
    """An epoch's line or the checkpoint's facts without the wall time, the one field a cut moves."""
    return {k: v for k, v in line.items() if k != "seconds"}


def lines_of(folder):
    return [json.loads(line) for line in (folder / "train" / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]


def facts_of(folder):
    return json.loads((folder / "train" / "checkpoint.json").read_text(encoding="utf-8"))


class Killed(Exception):
    """What the patched save raises, as a job cut after its write would stop."""


def cut_after(module, writes):
    """The trainer's save of last.pt, made to stop the run once it has written writes of them."""
    real, done = module.save_last, []

    def save_then_stop(folder, state):
        real(folder, state)
        done.append(state["epoch"])
        if len(done) == writes:
            raise Killed(f"cut after write {writes} of last.pt (epoch {state['epoch']})")

    return mock.patch.object(module, "save_last", save_then_stop)


def cut_at_binding(module, call, before_write):
    """The trainer's write of train/last.pt.sha256 made to stop the run at its call-th write,
    before or after it writes: save_last writes the sidecar twice an epoch, naming the new file
    beside the one in place before the rename and the new one alone after it, so the third and
    fourth writes are epoch 1's, on either side of its rename."""
    real, done = module.bind_last, []

    def bind_then_stop(folder, digests):
        done.append(len(digests))
        if len(done) == call and before_write:
            raise Killed(f"cut before write {call} of last.pt.sha256")
        real(folder, digests)
        if len(done) == call:
            raise Killed(f"cut after write {call} of last.pt.sha256")

    return mock.patch.object(module, "bind_last", bind_then_stop)


def hole_in_a_tensor(data):
    """last.pt with one 4 KiB block in the middle of its largest tensor record read back as zeros,
    as a node that died with that stretch unwritten leaves the file on CephFS; torch reads it
    without a word, since it checks no tensor record's bytes."""
    import struct
    import zipfile

    archive = zipfile.ZipFile(io.BytesIO(data))
    record = max((info for info in archive.infolist() if "/data/" in info.filename), key=lambda info: info.file_size)
    name_length, extra_length = struct.unpack("<HH", data[record.header_offset + 26 : record.header_offset + 30])
    start = record.header_offset + 30 + name_length + extra_length
    block = (start + record.file_size // 2) // 4096 * 4096
    return data[:block] + bytes(4096) + data[block + 4096 :]


def archive_with(pickled):
    """A torch file whose pickle is these bytes, every other record of the archive a saved file's,
    so torch.load reads the pickle as it reads a run's state."""
    import torch
    import zipfile

    saved, built = io.BytesIO(), io.BytesIO()
    torch.save({"epoch": 1}, saved)
    source = zipfile.ZipFile(io.BytesIO(saved.getvalue()))
    with zipfile.ZipFile(built, "w", zipfile.ZIP_STORED) as target:
        for info in source.infolist():
            target.writestr(info.filename, pickled if info.filename.endswith("data.pkl") else source.read(info))
    return built.getvalue()


# Pickles torch's weights-only loader cannot rebuild a state from, each raising an error outside
# the ones a cut file raises: the review's 1500 one-byte changes to a last.pt's pickle found the
# first two, and 6000 changes of two bytes the third (2026-10-25).
UNREBUILT = (("TypeError", b"\x80\x02ctorch._utils\n_rebuild_tensor_v2\n)R."),
             ("AttributeError", b"\x80\x02ctorch._utils\n_rebuild_tensor_v2\n()K\x00K\x01\x85K\x01\x85\x89ccollections\nOrderedDict\n)RtR."),
             ("AssertionError", b"\x80\x02K\x01Q."))


def lines_on_disk(module, seen):
    """The trainer's save of last.pt, made to note first how many whole lines metrics.jsonl holds
    on disk, read through a handle of its own, as the sweep's card reads it while the step runs."""
    real = module.save_last

    def note_then_save(folder, state):
        seen.append((folder / "metrics.jsonl").read_bytes().count(b"\n"))
        real(folder, state)

    return mock.patch.object(module, "save_last", note_then_save)


def train(catalog, folder, *extra, module=None):
    """The trainer's main on a short CPU run, its output kept; returns the exit code, stdout and stderr."""
    args = ["--catalog", str(catalog), "--out", str(folder), "--seed", "1", "--device", "cpu", "--witness", "2",
            "--keep-epochs", "0", *extra]
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = (module or load("train")).main(args)
    return rc, out.getvalue(), err.getvalue()


class ResumeCase:
    """Three runs of one configuration: through, cut after the second last.pt (epoch 1), and the
    cut one resumed; each subclass names the architecture and the blocks."""

    words = ()
    tmp = catalog = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = blocks_tests.RunWithEveryBlockTest.make_catalog(cls.tmp)
        witness = load("witness").freeze(cls.catalog, "0" * 64)
        cls.config = ["--epochs", "3", "--size", "32", *(w for word in cls.words for w in ("--block", word))]
        cls.through = new_run(cls.tmp / "through", "throughrun00", witness)
        cls.through_on_disk, module = [], load("train")
        with lines_on_disk(module, cls.through_on_disk):
            cls.through_rc = train(cls.catalog, cls.through, *cls.config, module=module)[0]
        cls.cut = new_run(cls.tmp / "cut", "cutrun000000", witness)
        module = load("train")
        with cut_after(module, 2):
            try:
                train(cls.catalog, cls.cut, *cls.config, module=module)
                cls.cut_stopped = False
            except Killed:
                cls.cut_stopped = True
        cls.after_cut = {name: (cls.cut / "train" / name).exists() for name in ("last.pt", "checkpoint.json", "best.pt")}
        cls.last_digest = digest(cls.cut / "train" / "last.pt")
        cls.mismatch = train(cls.catalog, cls.cut, *[w if w != "3" else "4" for w in cls.config], "--resume")
        cls.mismatch_left = digest(cls.cut / "train" / "last.pt")
        cls.resumed_on_disk, module = [], load("train")
        with lines_on_disk(module, cls.resumed_on_disk):
            cls.resumed_rc, cls.resumed_out, _ = train(cls.catalog, cls.cut, *cls.config, "--resume", module=module)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_cut_stopped_after_epoch_1_with_last_pt_and_no_checkpoint(self):
        self.assertEqual(self.through_rc, 0)
        self.assertTrue(self.cut_stopped)
        self.assertEqual(self.after_cut, {"last.pt": True, "checkpoint.json": False, "best.pt": False}, "epoch 1's best waits under pending/ until last.pt records it")
        self.assertIn('"resumed_after_epoch": 1', self.resumed_out)

    def test_a_resumed_run_ends_as_one_that_went_through(self):
        self.assertEqual(self.resumed_rc, 0)
        self.assertEqual([untimed(line) for line in lines_of(self.cut)], [untimed(line) for line in lines_of(self.through)])
        self.assertEqual(len(lines_of(self.cut)), 4)
        self.assertEqual(digest(self.cut / "train" / "best.pt"), digest(self.through / "train" / "best.pt"))
        self.assertEqual(untimed(facts_of(self.cut)), untimed(facts_of(self.through)))
        self.assertEqual(facts_of(self.cut)["checkpoint_sha256"], digest(self.cut / "train" / "best.pt"))

    def test_every_picture_of_the_resumed_run_is_the_uncut_runs(self):
        def pictures(folder):
            root = folder / "train"
            return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in (".png", ".jpg", ".gif")}

        mine, theirs = pictures(self.cut), pictures(self.through)
        self.assertEqual(mine, theirs)
        sheets = sorted(name for name in mine if "sheet-epoch-" in name)
        self.assertEqual(sheets, ["witness/frames/sheet-epoch-00.jpg", "witness/frames/sheet-epoch-03.jpg"], "the witness epochs before the cut are taken back")

    def test_every_epoch_line_is_on_disk_once_its_epoch_ends(self):
        # The sweep's card reads the last line every 15 s; a line left in the writer's buffer
        # would show no epoch until the step ends, and a kill would lose it.
        self.assertEqual(self.through_on_disk, [1, 2, 3, 4])
        self.assertEqual(self.resumed_on_disk, [3, 4], "the lines before the cut are on disk with the first new one")

    def test_last_pt_is_gone_after_a_finished_run(self):
        for folder in (self.through, self.cut):
            for name in ("last.pt", "last.pt.tmp", "last.pt.sha256", "last.pt.sha256.tmp", "pending"):
                self.assertFalse((folder / "train" / name).exists(), name)

    def test_a_resume_with_other_arguments_is_refused_in_words_and_touches_nothing(self):
        rc, _, err = self.mismatch
        self.assertEqual(rc, 1)
        self.assertIn("train: --resume:", err)
        self.assertIn("epochs was 3, now 4", err)
        self.assertEqual(self.mismatch_left, self.last_digest)

    def test_the_card_says_where_the_run_was_resumed(self):
        card = (self.cut / "train" / "MODEL.md").read_text(encoding="utf-8")
        self.assertIn("- Resumed after epoch 1: continued from train/last.pt", card)
        self.assertNotIn("- Resumed", (self.through / "train" / "MODEL.md").read_text(encoding="utf-8"))


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class ResumeWithEveryBlockTest(ResumeCase, unittest.TestCase):
    """resnet18 with every block on: the run's generator, the optimiser's moments and schedule
    and the prior head are what the resumed run must take back."""

    words = tuple(EVERY_BLOCK)

    def test_the_prior_head_of_the_resumed_run_is_the_uncut_runs(self):
        self.assertEqual(digest(self.cut / "train" / "prior_head.pt"), digest(self.through / "train" / "prior_head.pt"))
        self.assertEqual(facts_of(self.cut)["prior_head_sha256"], digest(self.cut / "train" / "prior_head.pt"))


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class ResumeWithDropoutTest(ResumeCase, unittest.TestCase):
    """mobilenet-v3-small, whose dropout draws from torch's global generator, which the resumed run
    must take back too (tools/train_blocks.py's module docstring)."""

    words = ("architecture=mobilenet-v3-small",)


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class ResumeBindingTest(unittest.TestCase):
    """--resume holds a cut run to the bytes of the files it started from, the catalog, the
    ImageNet file and the parent, as tools/flow.py names the run by them: the same file at another
    path resumes, and a file replaced at the same path, or another catalog, is refused in words."""

    config = ("--epochs", "3", "--size", "32")

    @classmethod
    def setUpClass(cls):
        import torch
        import torchvision

        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = blocks_tests.RunWithEveryBlockTest.make_catalog(cls.tmp)
        cls.moved_catalog = cls.tmp / "elsewhere" / "catalog.sqlite"
        cls.moved_catalog.parent.mkdir()
        shutil.copyfile(cls.catalog, cls.moved_catalog)
        (cls.tmp / "models-old").mkdir()
        torch.manual_seed(4)
        torch.save(torchvision.models.resnet18(weights=None).state_dict(), cls.tmp / "models-old" / "resnet18.pth")
        shutil.copytree(cls.tmp / "models-old", cls.tmp / "models")
        parent = new_run(cls.tmp / "parent", "parentrun000")
        assert train(cls.catalog, parent, "--epochs", "1", "--size", "32")[0] == 0
        (cls.tmp / "parent-alias").symlink_to(parent, target_is_directory=True)
        cls.parent = parent / "train" / "best.pt"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cut(self, name, *extra):
        """A run cut after its second last.pt (epoch 1), as ResumeCase cuts one."""
        folder = new_run(self.tmp / name, name.ljust(12, "0")[:12])
        module = load("train")
        with cut_after(module, 2), self.assertRaises(Killed):
            train(self.catalog, folder, *self.config, *extra, module=module)
        self.assertTrue((folder / "train" / "last.pt").is_file())
        return folder

    def resume(self, folder, *extra, catalog=None):
        return train(catalog or self.catalog, folder, *self.config, *extra, "--resume")

    def test_the_same_files_at_other_paths_resume(self):
        folder = self.cut("respelled", "--weights", str(self.tmp / "models-old" / "resnet18.pth"))
        rc, out, err = self.resume(folder, "--weights", str(self.tmp / "models" / "resnet18.pth"), catalog=self.moved_catalog)
        self.assertEqual(rc, 0, err)
        self.assertIn('"resumed_after_epoch": 1', out)
        folder = self.cut("aliased", "--init", str(self.parent))
        rc, out, err = self.resume(folder, "--init", str(self.tmp / "parent-alias" / "train" / "best.pt"))
        self.assertEqual(rc, 0, err)
        self.assertIn('"resumed_after_epoch": 1', out)

    def test_a_link_to_the_parent_file_is_read_as_the_file_it_names(self):
        # A link to the file itself sits in a folder with no RUN.json or checkpoint.json beside it;
        # read there, the parent named no run and warm_start checked none of its blocks, so a
        # parent trained on other crops warm-started without a word.
        link = self.tmp / "parent.pt"
        link.symlink_to(self.parent)
        trainer = load("train")
        through_link = trainer.parent_of(link)
        self.assertEqual(through_link, trainer.parent_of(self.parent))
        self.assertEqual((through_link["file"], through_link["run_id"], through_link["facts"]["size"]), ("best.pt", "parentrun000", 32))
        folder = new_run(self.tmp / "linked", "linkedrun000")
        rc, _, err = train(self.catalog, folder, "--epochs", "1", "--size", "64", "--init", str(link), module=trainer)
        self.assertEqual(rc, 1)
        self.assertIn("train: the parent was trained on 32-pixel crops, this run on 64", err)

    def test_a_file_replaced_at_the_same_path_is_refused(self):
        import torch
        import torchvision

        weights = self.tmp / "replaced.pth"
        shutil.copyfile(self.tmp / "models" / "resnet18.pth", weights)
        folder = self.cut("replaced", "--weights", str(weights))
        last = digest(folder / "train" / "last.pt")
        torch.manual_seed(5)
        torch.save(torchvision.models.resnet18(weights=None).state_dict(), weights)
        rc, _, err = self.resume(folder, "--weights", str(weights))
        self.assertEqual(rc, 1)
        self.assertIn("train: --resume:", err)
        self.assertIn("weights_sha256 was", err)
        self.assertEqual(digest(folder / "train" / "last.pt"), last)

    def test_another_catalog_is_refused(self):
        import sqlite3

        other = self.tmp / "other.sqlite"
        shutil.copyfile(self.catalog, other)
        db = sqlite3.connect(other)
        db.execute("PRAGMA user_version = 7")
        db.commit()
        db.close()
        folder = self.cut("recatalogued")
        rc, _, err = self.resume(folder, catalog=other)
        self.assertEqual(rc, 1)
        self.assertIn("train: --resume:", err)
        self.assertIn("catalog_sha256 was", err)


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class UnreadableLastTest(unittest.TestCase):
    """A last.pt the run cannot go on from, cut short, emptied or with a stretch of zeros a node
    that died before it reached the disk left, or with no record of its bytes, is moved aside under
    a name that says so and the run trains from epoch 0 in the same call, ending as a run that went
    through; refused, every start the flow makes would resume it and be refused again. A cut on
    either side of the rename that puts a new last.pt in place resumes from the file in place."""

    config = ("--epochs", "3", "--size", "32")

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = blocks_tests.RunWithEveryBlockTest.make_catalog(cls.tmp)
        cls.through = new_run(cls.tmp / "through", "throughrun00")
        assert train(cls.catalog, cls.through, *cls.config)[0] == 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cut_and_spoil(self, name, spoil):
        folder = new_run(self.tmp / name, name.ljust(12, "0")[:12])
        module = load("train")
        with cut_after(module, 2), self.assertRaises(Killed):
            train(self.catalog, folder, *self.config, module=module)
        last = folder / "train" / "last.pt"
        spoiled = spoil(last.read_bytes())
        last.write_bytes(spoiled)
        return folder, spoiled

    def assert_started_again(self, folder, resumed):
        """The resumed call's outcome: last.pt moved aside, the run trained from epoch 0 and ended
        as the run that went through, and its card saying so."""
        rc, out, err = resumed
        self.assertEqual(rc, 0, err)
        self.assertFalse((folder / "train" / "last.pt").exists())
        self.assertIn('"restarted_from_epoch": 0', out)
        self.assertNotIn("resumed_after_epoch", out)
        self.assertEqual([untimed(line) for line in lines_of(folder)], [untimed(line) for line in lines_of(self.through)])
        self.assertEqual(digest(folder / "train" / "best.pt"), digest(self.through / "train" / "best.pt"))
        self.assertEqual(untimed(facts_of(folder)), untimed(facts_of(self.through)))
        card = (folder / "train" / "MODEL.md").read_text(encoding="utf-8")
        self.assertIn("- Restarted from epoch 0: train/last.pt could not be resumed from", card)
        self.assertNotIn("- Resumed", card)
        return out

    def test_a_spoiled_last_pt_is_moved_aside_and_the_run_starts_again(self):
        import torch

        foreign = io.BytesIO()
        torch.save({"epoch": 1}, foreign)
        # A zip cut short, nothing, two kinds of pickle that is no pickle, zeroes, a file torch reads
        # that holds no run's state, and one 4 KiB block of zeros inside a tensor, which torch reads
        # as the state it was; last.pt.sha256 names none of them.
        spoils = (("truncated", lambda data: data[: len(data) // 2]), ("emptied", lambda data: b""),
                  ("overwritten", lambda data: b"not a torch file"), ("scribbled", lambda data: b"the epoch"),
                  ("zeroed", lambda data: bytes(len(data))), ("foreign", lambda data: foreign.getvalue()),
                  ("holed", hole_in_a_tensor))
        for name, spoil in spoils:
            with self.subTest(name):
                folder, spoiled = self.cut_and_spoil(name, spoil)
                if name == "holed":
                    state = torch.load(io.BytesIO(spoiled), map_location="cpu", weights_only=True)
                    self.assertEqual(state["epoch"], 1, "torch takes the holed file for epoch 1's state")
                out = self.assert_started_again(folder, train(self.catalog, folder, *self.config, "--resume"))
                self.assertEqual((folder / "train" / "last.pt.unreadable").read_bytes(), spoiled)
                self.assertIn("is not one last.pt.sha256 names", out)

    def test_a_last_pt_with_no_record_of_its_bytes_is_moved_aside_and_the_run_starts_again(self):
        # As a last.pt left by the code before the record would be; none was left on the grid.
        folder, _ = self.cut_and_spoil("unrecorded", lambda data: data)
        (folder / "train" / "last.pt.sha256").unlink()
        out = self.assert_started_again(folder, train(self.catalog, folder, *self.config, "--resume"))
        self.assertIn("no last.pt.sha256 names its bytes", out)

    def test_a_last_pt_torch_cannot_rebuild_is_moved_aside_and_the_run_starts_again(self):
        # Bytes the record names, as a disk that spoiled them after the record was written leaves
        # them, whose pickle makes torch.load raise an error no list of a cut file's errors names.
        for error, pickled in UNREBUILT:
            with self.subTest(error):
                folder, spoiled = self.cut_and_spoil(error.lower(), lambda data, pickled=pickled: archive_with(pickled))
                (folder / "train" / "last.pt.sha256").write_text(hashlib.sha256(spoiled).hexdigest() + "\n", encoding="ascii")
                out = self.assert_started_again(folder, train(self.catalog, folder, *self.config, "--resume"))
                self.assertIn(f'"why": "{error}"', out)

    def test_a_staged_best_pt_the_record_does_not_name_restarts_the_run_and_is_refused_no_more(self):
        # Epoch 1's best.pt waits under pending/ when the cut comes, its digest in last.pt's best
        # line; other bytes there leave no best.pt the record names, and the flow passes --resume
        # wherever last.pt is, so a refusal would come back on every start.
        folder, _ = self.cut_and_spoil("unnamed", lambda data: data)
        (folder / "train" / "pending" / "best.pt").write_bytes(b"spoiled on the disk")
        out = self.assert_started_again(folder, train(self.catalog, folder, *self.config, "--resume"))
        self.assertIn("best.pt is not there, though last.pt's best line names sha256", out)

    def test_a_cut_on_either_side_of_the_rename_resumes_from_the_file_in_place(self):
        # Epoch 1's save writes the sidecar a third and a fourth time, on either side of its rename.
        for call, before_write, after_epoch in ((3, False, 0), (4, True, 1)):
            with self.subTest(call=call, before_write=before_write):
                folder = new_run(self.tmp / f"swap-{call}", f"swap{call}".ljust(12, "0"))
                module = load("train")
                with cut_at_binding(module, call, before_write), self.assertRaises(Killed):
                    train(self.catalog, folder, *self.config, module=module)
                rc, out, err = train(self.catalog, folder, *self.config, "--resume")
                self.assertEqual(rc, 0, err)
                self.assertIn(f'"resumed_after_epoch": {after_epoch}', out)
                self.assertEqual([untimed(line) for line in lines_of(folder)], [untimed(line) for line in lines_of(self.through)])
                self.assertEqual(digest(folder / "train" / "best.pt"), digest(self.through / "train" / "best.pt"))


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class ResumeRefusalsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.train = load("train")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_resume_with_no_last_pt_is_refused_in_words(self):
        folder = new_run(self.tmp / "nothing", "nothingrun00")
        rc, _, err = train(self.tmp / "no-catalog.sqlite", folder, "--epochs", "1", "--resume", module=self.train)
        self.assertEqual(rc, 1)
        self.assertIn("nothing to resume", err)
        self.assertFalse((folder / "train" / "metrics.jsonl").exists())

    def test_a_second_trainer_in_a_folder_another_holds_is_refused_and_touches_nothing(self):
        # A flow started again after the flow of a live Slurm training job died sends a second
        # trainer into the same folder; it must stop before it settles pending/ or opens a file.
        import fcntl

        folder = new_run(self.tmp / "held", "heldrun00000")
        train_dir = folder / "train"
        (train_dir / "pending").mkdir(parents=True)
        (train_dir / "last.pt").write_bytes(b"the live run's epoch")
        (train_dir / "pending" / "best.pt").write_bytes(b"staged by the live run")
        catalog = blocks_tests.RunWithEveryBlockTest.make_catalog(self.tmp / "catalog")
        with (train_dir / ".lock").open("a+", encoding="utf-8") as live:
            fcntl.flock(live, fcntl.LOCK_EX | fcntl.LOCK_NB)
            live.write("pid 4242 on node-a, Slurm job 777\n")
            live.flush()
            before = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
            rc, _, err = train(catalog, folder, "--epochs", "1", "--resume", module=self.train)
        self.assertEqual(rc, 1)
        self.assertIn(f"train: {train_dir} is in progress: another trainer holds {train_dir / '.lock'} (pid 4242 on node-a, Slurm job 777)", err)
        after = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_a_staged_best_moves_in_only_where_the_record_names_it(self):
        folder = self.tmp / "settle" / "train"
        (folder / "pending").mkdir(parents=True)
        (folder / "pending" / "best.pt").write_bytes(b"recorded")
        (folder / "pending" / "prior_head.pt").write_bytes(b"not recorded")
        self.train.settle(folder, {"checkpoint_sha256": hashlib.sha256(b"recorded").hexdigest(), "prior_head_sha256": "0" * 64})
        self.assertEqual((folder / "best.pt").read_bytes(), b"recorded")
        self.assertFalse((folder / "prior_head.pt").exists())
        self.assertEqual(list((folder / "pending").iterdir()), [])
        (folder / "pending" / "best.pt").write_bytes(b"an epoch the cut never recorded")
        self.train.settle(folder, None)
        self.assertEqual((folder / "best.pt").read_bytes(), b"recorded")
        self.assertFalse((folder / "pending" / "best.pt").exists())

    def test_a_best_pt_the_record_does_not_name_is_said_in_words(self):
        folder = self.tmp / "unnamed" / "train"
        folder.mkdir(parents=True)
        named = {"checkpoint_sha256": hashlib.sha256(b"the recorded weights").hexdigest()}
        self.assertEqual(self.train.best_mismatch(folder, named), f"best.pt is not there, though last.pt's best line names sha256 {named['checkpoint_sha256'][:12]}")
        (folder / "best.pt").write_bytes(b"other weights")
        other = hashlib.sha256(b"other weights").hexdigest()[:12]
        self.assertEqual(self.train.best_mismatch(folder, named), f"best.pt's sha256 {other} is not {named['checkpoint_sha256'][:12]}, the one last.pt's best line names")
        (folder / "best.pt").write_bytes(b"the recorded weights")
        self.assertIsNone(self.train.best_mismatch(folder, named))
        self.assertIsNone(self.train.best_mismatch(self.tmp / "nowhere", None))


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class EvaluateRefusalsTest(unittest.TestCase):
    """tools/evaluate.py scores best.pt only where train/checkpoint.json is the record of it: one
    that cannot be read, or beside other weights than the ones it names, as a node that died or a
    disk that spoiled a file may leave them, is refused in words and nothing is written, where it
    ended in a traceback or scored the other weights. The catalog here has no test part, so the
    evaluator scores the validation part."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = blocks_tests.RunWithEveryBlockTest.make_catalog(cls.tmp)
        cls.trained = new_run(cls.tmp / "trained", "0123456789ab")
        assert train(cls.catalog, cls.trained, "--epochs", "1", "--size", "32")[0] == 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def evaluate(self, name, spoil=None):
        """The evaluator on a copy of the trained run, spoiled first where asked; the copy, the
        exit code and stderr."""
        folder = self.tmp / name
        shutil.copytree(self.trained, folder)
        if spoil:
            spoil(folder / "train")
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = load("evaluate").main(["--catalog", str(self.catalog), "--run", str(folder), "--part", "validation", "--device", "cpu"])
        return folder, rc, err.getvalue()

    def test_a_sound_run_is_scored(self):
        folder, rc, err = self.evaluate("sound")
        self.assertEqual(rc, 0, err)
        self.assertTrue((folder / "evaluate" / "results.json").is_file())

    def test_a_checkpoint_json_that_is_no_record_is_refused_in_words(self):
        spoils = (("emptied", b"", "cannot be read as a run's checkpoint record"),
                  ("halved", b'{"epoch": 1, "checkpoint_sha2', "cannot be read as a run's checkpoint record"),
                  ("listed", b"[]", "names no checkpoint_sha256"), ("unnamed", b'{"epoch": 1}', "names no checkpoint_sha256"))
        for name, text, words in spoils:
            with self.subTest(name):
                folder, rc, err = self.evaluate(name, lambda train_dir, text=text: (train_dir / "checkpoint.json").write_bytes(text))
                self.assertEqual(rc, 1)
                self.assertIn(f"evaluate: {folder / 'train' / 'checkpoint.json'}: {words}", err)
                self.assertFalse((folder / "evaluate").exists())

    def test_a_best_pt_checkpoint_json_does_not_name_is_refused_in_words(self):
        import torch

        def other_weights(train_dir):
            torch.manual_seed(9)
            torch.save(load("train").build_model(None, "cpu").state_dict(), train_dir / "best.pt")

        named = facts_of(self.trained)["checkpoint_sha256"]
        for name, spoil, words in (("replaced", other_weights, f"is not {named[:12]}, the one"), ("gone", lambda train_dir: (train_dir / "best.pt").unlink(), "not there, though")):
            with self.subTest(name):
                folder, rc, err = self.evaluate(name, spoil)
                self.assertEqual(rc, 1)
                self.assertIn(f"evaluate: {folder / 'train' / 'best.pt'}", err)
                self.assertIn(words, err)
                self.assertFalse((folder / "evaluate").exists())


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class SingleCropBatchTest(unittest.TestCase):
    """65 training crops in batches of 64 end each epoch on a batch of one crop."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = blocks_tests.RunWithEveryBlockTest.make_catalog(cls.tmp)
        cls.train = load("train")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_65(self, name, architecture, size):
        folder = new_run(self.tmp / name, f"{name}run".ljust(12, "0")[:12])
        rc, _, err = train(self.catalog, folder, "--epochs", "1", "--size", str(size), "--max-frames", "65",
                           "--block", f"architecture={architecture}", module=self.train)
        self.assertEqual(rc, 0, err)
        facts = facts_of(folder)
        self.assertEqual(facts["counts"]["train"], 65)
        return facts, (folder / "train" / "MODEL.md").read_text(encoding="utf-8")

    def test_at_32_pixels_resnet18_and_densenet121_train_on_65_crops(self):
        for architecture in ("resnet18", "densenet121"):
            with self.subTest(architecture=architecture):
                facts, card = self.run_65(f"joined-{architecture}", architecture, 32)
                self.assertEqual(facts["single_crop_batch"], "joined")
                self.assertIn(f"- Batches: {architecture} cannot train on one 32-pixel crop", card)
                self.assertIn("which then held 65", card)

    def test_at_64_pixels_the_probe_says_it_can_and_nothing_joins(self):
        import torch

        for architecture in ("resnet18", "densenet121"):
            with self.subTest(architecture=architecture):
                model = self.train.build_model(None, "cpu", architecture=architecture)
                self.assertTrue(self.train.trains_on_one_crop(model, 64))
                before = torch.get_rng_state()
                self.assertFalse(self.train.trains_on_one_crop(model, 32))
                self.assertTrue(torch.equal(before, torch.get_rng_state()), "the probe moves no random state")
                self.assertTrue(model.training, "the probe asks a copy and leaves the model as it was")
        facts, card = self.run_65("whole-resnet18", "resnet18", 64)
        self.assertNotIn("single_crop_batch", facts)
        self.assertNotIn("- Batches:", card)

    def test_the_batches_are_version_1s_unless_one_crop_is_left_over(self):
        def legacy(count, batch):
            return [(start, min(count, start + batch)) for start in range(0, count, batch)]

        for count in (0, 1, 2, 63, 64, 65, 66, 128, 129, 176):
            with self.subTest(count=count):
                self.assertEqual(self.train.batch_bounds(count, 64), legacy(count, 64))
                joined = self.train.batch_bounds(count, 64, join_single=True)
                if count in (65, 129):
                    self.assertEqual(joined, [*legacy(count, 64)[:-2], (legacy(count, 64)[-2][0], count)])
                else:
                    self.assertEqual(joined, legacy(count, 64))

    def test_a_join_that_finds_no_crop_left_over_trains_to_the_same_weights(self):
        import torch

        inputs = torch.rand(24, 1, 32, 32, generator=torch.Generator().manual_seed(2)).repeat(1, 3, 1, 1)
        targets = torch.arange(24) % 27
        states = []
        for join in (False, True):
            torch.manual_seed(9)
            model = self.train.build_model(None, "cpu")
            optimiser = torch.optim.Adam(model.parameters(), lr=1e-3)
            self.train.train_epoch(model, optimiser, inputs, targets, "cpu", 8, torch.Generator().manual_seed(5), join_single=join)
            states.append(model.state_dict())
        self.assertTrue(all(torch.equal(states[0][k], states[1][k]) for k in states[0]))

    def test_one_training_crop_that_cannot_train_on_one_is_refused_in_words(self):
        folder = new_run(self.tmp / "one", "onecroprun00")
        rc, _, err = train(self.catalog, folder, "--epochs", "1", "--size", "32", "--max-frames", "1", module=self.train)
        self.assertEqual(rc, 1)
        self.assertIn("train: one training crop: resnet18 cannot take a training step", err)
        self.assertFalse((folder / "train" / "metrics.jsonl").exists())

    def test_a_batch_of_one_that_cannot_train_on_one_is_refused_in_the_same_words(self):
        # Every batch then holds one crop, so there is nothing to join; at 64 pixels it trains.
        folder = new_run(self.tmp / "batch-one", "batchonerun0")
        rc, _, err = train(self.catalog, folder, "--epochs", "1", "--size", "32", "--batch", "1", "--max-frames", "3", module=self.train)
        self.assertEqual(rc, 1)
        self.assertIn("train: --batch 1: every batch holds one crop, and resnet18 cannot take a training step on a batch"
                      " of one 32-pixel crop, since batch norm needs more than one value per channel there", err)
        self.assertFalse((folder / "train" / "metrics.jsonl").exists())
        folder = new_run(self.tmp / "batch-one-64", "batchone6400")
        rc, _, err = train(self.catalog, folder, "--epochs", "1", "--size", "64", "--batch", "1", "--max-frames", "3", module=self.train)
        self.assertEqual(rc, 0, err)


class FakeWandb(types.ModuleType):
    """wandb as Telemetry calls it, keeping each init's keywords; online starts fail where asked."""

    def __init__(self, fail_online):
        super().__init__("wandb")
        self.starts, self.fail_online = [], fail_online

    def Settings(self, **settings):  # noqa: N802 - wandb's own name
        return settings

    def init(self, **options):
        self.starts.append(options)
        if options["mode"] == "online" and self.fail_online:
            raise RuntimeError("no route to W&B")
        return types.SimpleNamespace(url="https://wandb.ai/example/run", log=lambda *a, **k: None, finish=lambda: None)

    def teardown(self):
        pass


class TelemetryResumeTest(unittest.TestCase):
    """A resumed step's W&B run goes on under its id: online by resume="allow", which only the
    online start asks for, since offline W&B resumes nothing; offline the push joins the halves."""

    record = {"run_id": "telemetry000", "code_commit": "0" * 40, "catalog_sha256": "0" * 64, "catalog_version": 1, "clean_tree": True}

    def starts(self, key, fail_online, resume):
        tool = load("wandb_log")
        fake = FakeWandb(fail_online)
        with tempfile.TemporaryDirectory() as run_dir, mock.patch.dict(sys.modules, {"wandb": fake}), \
                mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "on", "SCHWINGNET_WANDB_MODE": "online"}), \
                mock.patch.object(tool, "key_source", return_value=key):
            telemetry = tool.Telemetry(run_dir, self.record, "train", {}, resume=resume) if resume else tool.Telemetry(run_dir, self.record, "train", {})
            self.assertIsNotNone(telemetry.run)
        return fake.starts

    def test_a_resumed_step_asks_its_online_start_to_resume_and_never_its_offline_one(self):
        online = self.starts("env", fail_online=False, resume=True)
        self.assertEqual([(s["mode"], s["id"], s["resume"]) for s in online], [("online", "telemetry000-train", "allow")])
        fallen = self.starts("env", fail_online=True, resume=True)
        self.assertEqual([(s["mode"], s["id"], s.get("resume")) for s in fallen],
                         [("online", "telemetry000-train", "allow"), ("offline", "telemetry000-train-offline", None)])
        offline = self.starts("none", fail_online=False, resume=True)
        self.assertEqual([(s["mode"], s["id"], s.get("resume")) for s in offline], [("offline", "telemetry000-train", None)])

    def test_a_fresh_step_passes_no_resume(self):
        for key, fail in (("env", False), ("env", True), ("none", False)):
            with self.subTest(key=key, fail=fail):
                self.assertTrue(all("resume" not in s for s in self.starts(key, fail, resume=False)))

    @unittest.skipIf(wandb_tests.MISSING, "needs wandb, which the train and telemetry environments hold")
    def test_offline_the_resumed_half_is_a_run_of_its_own_until_the_push_joins_it_to_the_first(self):
        """The installed wandb itself, offline as on a node with no key: the cut half and the
        resumed half are two local runs of the step's id, each in a folder of its own, and the
        push sends both in one sync to tests/test_wandb_log.py's stand-in for W&B's server, which
        then holds one run with every epoch in order."""
        tool = load("wandb_log")
        server = wandb_tests.StandIn()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, home = Path(tmp) / "run", Path(tmp) / "home"
            with mock.patch.dict(os.environ, wandb_tests.environment(home), clear=True), mock.patch.object(tool, "key_source", return_value="none"):
                for resume, epochs in ((False, (0, 1)), (True, (2, 3))):
                    telemetry = tool.Telemetry(run_dir, self.record, "train", {}, resume=resume)
                    self.assertEqual((telemetry.mode, telemetry.run.resumed), ("offline", False), telemetry.reason)
                    for epoch in epochs:
                        telemetry.log({"validation_accuracy": epoch / 4}, step=epoch)
                    telemetry.finish()
                telemetry.wandb.teardown()
            folders = tool.offline_runs(run_dir)
            self.assertEqual([sorted(p.name for p in folder.glob("*.wandb")) for folder in folders], [["run-telemetry000-train.wandb"]] * 2)
            with mock.patch.dict(os.environ, wandb_tests.environment(home, server.url, wandb_tests.PLACEHOLDER), clear=True), \
                    mock.patch.object(tool, "TOKEN_FILE", Path(tmp) / "token.env"), mock.patch.object(tool, "NETRC", Path(tmp) / "netrc"):
                outcome = tool.sync(run_dir)
            self.assertTrue(outcome["synced"], outcome)
            self.assertEqual(server.steps("telemetry000-train"), [0, 1, 2, 3])
            self.assertEqual(tool.offline_runs(run_dir), [])


if __name__ == "__main__":
    unittest.main()
