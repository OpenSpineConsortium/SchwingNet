"""tools/figure_run.py answers a textbook figure's Re-run issue from the figure's committed record
alone: an author who may not write is refused, the id comes only from the body's fixed line and is
matched before it names a file, a grid figure gets its command and nothing is submitted, a figure with
no command gets its Explore links, and a runner figure runs its recorded command and may change nothing
outside its own chapter folder."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import figure_run  # noqa: E402
import textbook_site  # noqa: E402

QUIET = {"gc.auto": "0", "gc.autoDetach": "false", "maintenance.auto": "false", "maintenance.autoDetach": "false",
         "receive.autogc": "false"}
GIT_ENV = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_NAME": "Test",
           "GIT_COMMITTER_EMAIL": "test@example.invalid", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_COUNT": str(len(QUIET)),
           **{f"GIT_CONFIG_KEY_{i}": key for i, key in enumerate(QUIET)},
           **{f"GIT_CONFIG_VALUE_{i}": value for i, value in enumerate(QUIET.values())}}


def figure(fid, where, command=None):
    return {"id": fid, "title": f"Figure {fid}", "caption": "A caption.", "chapter": fid[:2], "grade": "Reported",
            "status": "current",
            "source": {"kind": "artifact", "artifact": "artifacts/a/", "artifact_url": None, "made_by": "tools/draw.py",
                       "commit": None, "data": ["data/x.json"], "run": None, "notes": "Traced by hand."},
            "explore": [{"label": "The method", "href": "docs/method.md"},
                        {"label": "Upstream", "href": "https://github.com/OpenSpineConsortium/spine-program/blob/abc/x.py"}],
            "rerun": {"where": where, "command": command, "cost": "CPU, seconds", "needs_owner_word": where == "grid"}}


def event(body, association="OWNER", action="opened", labels=("figure-rerun",), label=None):
    out = {"action": action, "issue": {"number": 7, "body": body, "author_association": association,
                                        "labels": [{"name": n} for n in labels]}}
    if label:
        out["label"] = {"name": label}
    return out


class Planning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        figs = cls.root / "docs" / "textbook" / "figures" / "10"
        figs.mkdir(parents=True)
        for fid, where, command in (("10/on-a-runner", "actions", "python3 tools/draw.py"),
                                    ("10/on-the-grid", "grid", "sbatch slurm/draw.sh"),
                                    ("10/no-command", "none", None)):
            (cls.root / "docs" / "textbook" / "figures" / f"{fid}.json").write_text(
                json.dumps(figure(fid, where, command)), encoding="utf-8")
        (figs / "wrong-id.json").write_text(json.dumps(figure("10/something-else", "actions", "rm -rf /")), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def decide(self, ev):
        return figure_run.decide(ev, self.root, "OWNER/NAME", "42")

    def test_a_reader_who_may_not_write_is_refused(self):
        for association in ("NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", None):
            got = self.decide(event("figure-rerun-id: 10/on-a-runner", association=association))
            self.assertEqual(got["action"], "refuse", association)
            self.assertIn("Nothing was run", got["comment"])

    def test_a_runner_figure_runs_its_recorded_command_on_its_own_branch(self):
        got = self.decide(event("Some words.\nfigure-rerun-id: 10/on-a-runner\nMore words."))
        self.assertEqual(got["action"], "actions")
        self.assertEqual(got["command"], "python3 tools/draw.py")
        self.assertEqual(got["branch"], "figure-rerun/10-on-a-runner-42")

    def test_a_grid_figure_gets_its_command_and_nothing_is_submitted(self):
        got = self.decide(event("figure-rerun-id: 10/on-the-grid", association="COLLABORATOR"))
        self.assertEqual(got["action"], "grid")
        self.assertIn("sbatch slurm/draw.sh", got["comment"])
        self.assertIn("https://github.com/OWNER/NAME/actions/workflows/grid.yml", got["comment"])
        self.assertIn("nothing is submitted", got["comment"])
        self.assertIn("this issue is not that word", got["comment"])
        self.assertNotIn("command", {k for k in got if k != "comment"})

    def test_a_figure_with_no_command_gets_its_explore_links(self):
        got = self.decide(event("figure-rerun-id: 10/no-command", association="MEMBER"))
        self.assertEqual(got["action"], "none")
        self.assertIn("https://github.com/OWNER/NAME/blob/HEAD/docs/method.md", got["comment"])
        self.assertIn("https://github.com/OpenSpineConsortium/spine-program/blob/abc/x.py", got["comment"])
        self.assertIn("Traced by hand.", got["comment"])

    def test_the_id_comes_only_from_the_fixed_line_and_names_no_file_outside(self):
        for body in ("figure-rerun-id: ../../../etc/passwd", "figure-rerun-id: 10/../../x",
                     "please run 10/on-a-runner", "figure-rerun-id: 10/missing",
                     "figure-rerun-id: 10/on-a-runner\nfigure-rerun-id: 10/on-the-grid",
                     "figure-rerun-id: 10/wrong-id"):
            self.assertEqual(self.decide(event(body))["action"], "invalid", body)
        self.assertIsNone(figure_run.load_record(self.root, "10/../../x"))

    def test_other_events_and_other_labels_do_nothing(self):
        self.assertEqual(self.decide(event("figure-rerun-id: 10/on-a-runner", action="labeled", label="bug"))["action"], "skip")
        self.assertEqual(self.decide(event("figure-rerun-id: 10/on-a-runner", action="closed"))["action"], "skip")
        self.assertEqual(self.decide(event("An ordinary issue.", labels=()))["action"], "skip")
        self.assertEqual(self.decide(event("figure-rerun-id: 10/on-a-runner", action="labeled",
                                           label="figure-rerun"))["action"], "actions")

    def test_the_comment_carries_the_marker_that_answers_an_issue_once(self):
        for body in ("figure-rerun-id: 10/on-a-runner", "figure-rerun-id: 10/missing"):
            self.assertTrue(self.decide(event(body))["comment"].startswith(figure_run.MARKER))

    def test_plan_writes_the_comment_and_the_outputs(self):
        ev = self.root / "event.json"
        ev.write_text(json.dumps(event("figure-rerun-id: 10/on-a-runner")), encoding="utf-8")
        outputs = self.root / "outputs"
        comment = self.root / "comment.md"
        old = os.environ.get("GITHUB_OUTPUT")
        os.environ["GITHUB_OUTPUT"] = str(outputs)
        try:
            figure_run.main(["plan", "--event", str(ev), "--repo", "OWNER/NAME", "--run-number", "3",
                             "--comment", str(comment), "--root", str(self.root)])
        finally:
            if old is None:
                os.environ.pop("GITHUB_OUTPUT")
            else:
                os.environ["GITHUB_OUTPUT"] = old
        self.assertIn("action=actions\n", outputs.read_text(encoding="utf-8"))
        self.assertIn("branch=figure-rerun/10-on-a-runner-3\n", outputs.read_text(encoding="utf-8"))
        self.assertIn("python3 tools/draw.py", comment.read_text(encoding="utf-8"))


class Running(unittest.TestCase):
    def repo(self, tmp, command):
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True, env={**os.environ, **GIT_ENV})
        path = root / "docs" / "textbook" / "figures" / "10" / "drawn.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(figure("10/drawn", "actions", command)), encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, env={**os.environ, **GIT_ENV})
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "a figure"], check=True, env={**os.environ, **GIT_ENV})
        return root

    def test_the_recorded_command_runs_and_its_figure_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(tmp, "echo '<svg/>' > docs/textbook/figures/10/drawn.svg")
            self.assertEqual(figure_run.run(root, "10/drawn"), ["docs/textbook/figures/10/drawn.svg"])

    def test_a_command_that_writes_elsewhere_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(tmp, "echo x > stray.txt")
            with self.assertRaises(SystemExit) as caught:
                figure_run.run(root, "10/drawn")
            self.assertIn("stray.txt", str(caught.exception))

    def test_a_figure_not_recorded_for_a_runner_is_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.repo(tmp, "echo x > stray.txt")
            with self.assertRaises(SystemExit):
                figure_run.run(root, "10/missing")
            self.assertFalse((root / "stray.txt").exists())


class TheRepositorysFigures(unittest.TestCase):
    def test_every_committed_record_is_whole_and_its_image_is_there(self):
        base = ROOT / "docs" / "textbook" / "figures"
        records = sorted(p for p in base.glob("*/*.json") if textbook_site.is_figure(p)) if base.is_dir() else []
        keys = {"id", "title", "caption", "chapter", "grade", "status", "source", "explore", "rerun"}
        for path in records:
            with self.subTest(path=path.name):
                rec = json.loads(path.read_text(encoding="ascii"))
                self.assertLessEqual(keys, set(rec))
                self.assertEqual(rec["id"], f"{path.parent.name}/{path.stem}")
                self.assertIn(rec["grade"], {"Measured", "Reported", "Inferred", "Unverified"})
                self.assertIn(rec["status"], {"current", "a record, not a final value"})
                self.assertIn(rec["rerun"]["where"], {"actions", "grid", "none"})
                if rec["rerun"]["where"] == "grid":
                    self.assertTrue(rec["rerun"]["needs_owner_word"])
                if rec["rerun"]["where"] != "none":
                    self.assertTrue(rec["rerun"]["command"])
                self.assertTrue(any(path.with_suffix(ext).exists() for ext in (".png", ".svg")))
                for ext in (".png", ".svg", ".html"):
                    if path.with_suffix(ext).exists():
                        self.assertLess(path.with_suffix(ext).stat().st_size, 2 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
