"""The FluXray reproduction's flow (flows/realism.py), run for real through flows/launch.py.

Each test runs the launcher with a datastore of its own over a scratch repository that holds the
flow, the stage helpers, the registry, the frozen PREREG, the real report (tools/report.py with
tools/realism_report.py) and a stand-in for tools/realism.py that writes the files each subcommand
writes, so the graph, the PREREG hold, the edit then the stats, the report the end step checks, the
progress page and the resume of a failed shard are tested without a GPU and in seconds. Metaflow is
in the train feature only, so CI's python, which has none, skips the file; run it with the
train-cpu environment, as tests/test_flows.py is run.
"""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCH = ROOT / "flows" / "launch.py"
NEEDED = ("metaflow", "beartype", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
TIMEOUT = 600
PREREG = "docs/research/flux-realism/PREREG.md"
# What the scratch repository copies whole: the flow and what it runs, and the report with what it reads.
COPIED = ("flows/realism.py", "flows/stage.py", "flows/stage_progress.py", "flows/stage_registry.py", "flows/registry.txt",
          "src/schwingnet/__init__.py", "src/schwingnet/realism.py", "tools/run_code.py", "tools/report.py",
          "tools/realism_report.py", "data/reporting/checklists.json", "data/reporting/study.json",
          "data/reporting/studies/flux-realism.json", "data/reporting/studies/drr-domain-gap.json", "data/licences.json",
          "grid/realism.sbatch", PREREG, PREREG + ".sha256")
SUBJECTS = [f"s{n:02d}" for n in range(12)]

# A stand-in for tools/realism.py: every subcommand the flow runs, writing the files the real one
# writes in the shapes the flow and the report read, its calls logged to FLOW_TEST_CALLS; the
# render of the shard FLOW_TEST_FAIL names fails, as a GPU fault would.
STUB_TOOL = r'''"""A stand-in for tools/realism.py in tests/test_realism_flow.py."""
import json
import os
import sys
from pathlib import Path

SUBJECTS = %(subjects)r
command, words = sys.argv[1], sys.argv[2:]


def value(flag, default=""):
    return words[words.index(flag) + 1] if flag in words else default


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def only():
    return Path(value("--only")).read_text(encoding="utf-8").split() if value("--only") else SUBJECTS


with open(os.environ["FLOW_TEST_CALLS"], "a", encoding="utf-8") as calls:
    calls.write(command + (" " + Path(value("--only")).stem if value("--only") else "") + "\n")
out = Path(value("--out"))
if command == "inputs":
    record = {"model": "klein-9b", "samples_sha256": "1" * 64, "samples_rows": 60, "samples_not_in_db": 1,
              "db_sha256": "2" * 64, "klein_sha256": "3" * 64, "bundle_sha256": "4" * 64, "imagenet_sha256": "6" * 64,
              "eligible": SUBJECTS, "environment": {"diffusers": "0.42.0", "gpu": "STAND-IN", "cuda": "none"},
              "pins_differ": []}
    write(out, json.dumps(record))
    print(f"inputs: klein-9b, 60 FluXray samples (1 not in the ThunderDB), {len(SUBJECTS)} subjects with CT and truth")
elif command == "poses":
    write(out, json.dumps({"subjects": SUBJECTS, "mismatches": ["off-1", "off-2"]}))
    print(f"{len(SUBJECTS)} subjects, 2 samples off the grid")
elif command == "split":
    shard = int(value("--shard-size"))
    write(out / "split.json", json.dumps({"seed": int(value("--seed")), "from": len(SUBJECTS), "all": len(SUBJECTS),
                                          "train": 8, "eval": 4, "shards": 2}))
    write(out / "all.txt", "".join(s + "\n" for s in SUBJECTS))
    for n in range(0, len(SUBJECTS), shard):
        write(out / "shards" / f"{n // shard:03d}.txt", "".join(s + "\n" for s in SUBJECTS[n:n + shard]))
    print(f"{len(SUBJECTS)} of {len(SUBJECTS)} subjects drawn")
elif command == "render":
    if Path(value("--only")).stem == os.environ.get("FLOW_TEST_FAIL"):
        print("CUDA error: the stand-in's fault", file=sys.stderr)
        sys.exit(1)
    for subject in only():
        for pose in range(int(value("--per-subject"))):
            name = f"{subject}_p{pose}"
            write(out / "raw" / f"{name}.npy", "raw")
            with open(out / "manifest.jsonl", "a", encoding="utf-8") as manifest:
                manifest.write(json.dumps({"sample_id": name, "subject_id": subject}) + "\n")
    print(f"rendered {len(only())} subjects")
elif command == "edit":
    for path in sorted((Path(value("--raw")) / "raw").glob("*.npy")):
        if path.stem.split("_")[0] in only():
            for arm in range(int(value("--arms"))):
                write(out / "edited" / f"{path.stem}_a{arm}.npy", "edited")
    print(f"edited {len(only())} subjects")
elif command == "score":
    write(out, "sample_id\n" + "".join(s + "\n" for s in only()))
    print("scored")
elif command == "keep":
    edits = sorted((Path(value("--edited")) / "edited").glob("*.npy"))
    write(out / "filter_kept.csv", "sample_id\n" + "".join(p.stem + "\n" for p in edits[1:]))
    write(out / "filter_dropped.csv", "sample_id\n" + "".join(p.stem + "\n" for p in edits[:1]))
    for path in edits[1:]:
        write(out / "kept" / path.name, "kept")
    print(f"{len(edits) - 1} of {len(edits)} edits kept")
elif command == "fluxray-export":
    rows = Path(value("--samples"), "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    rows = rows[: len(rows) - int(os.environ.get("FLOW_TEST_SHORT", "0"))]
    for row in rows:
        write(out / "img" / (json.loads(row)["sample_id"] + ".npy"), "fluxray")
    print(f"{len(rows)} FluXray images")
elif command == "measure":
    write(out / "measure.md", "| level | angle |\n|---|---|\n")
    print("measured")
elif command == "environment":
    record = {"environment": {"diffusers": "0.42.0", "torch": "stand-in", "gpu": "STAND-IN STATS", "cuda": "none"},
              "pins_differ": [], "bundle": value("--bundle"), "bundle_sha256": "4" * 64, "imagenet": value("--imagenet"),
              "imagenet_sha256": "6" * 64}
    write(out, json.dumps(record))
    print("environment: torch stand-in on STAND-IN STATS, every pin holds")
elif command == "stats":
    auc = 0.9 if "raw" in value("--a") else 0.52
    word = "separable" if auc > 0.6 else "indistinguishable"
    side = {"c2st": {"auc": auc, "low": auc - 0.05, "high": auc + 0.05}, "mmd": {"p": 0.5, "q": 0.5}}
    null = {"c2st": {"auc": 0.5, "low": 0.45, "high": 0.55}}
    spaces = {space: {"a_vs_b": side, "b_split_half": null, "arm_null": null, "nulls_separable": False, "verdict": word}
              for space in value("--require-spaces").split(",")}
    report = {"seed": int(value("--seed")), "sets": {"a": {"n": 90, "subjects": 12}, "b": {"n": 48, "subjects": 12}},
              "rules": {"neighbours": "stand-in", "auc_interval": "stand-in", "permutation": "stand-in", "multiplicity": "stand-in"},
              "spaces": spaces, "verdict": word, "paired": {"shift_px_median": 0.25}}
    write(out / "stats.json", json.dumps(report))
    write(out / "stats.md", f"| space | verdict |\n|---|---|\n| all | {word} |\n")
    print(f"verdict {word}")
else:
    print(f"the stand-in has no {command}", file=sys.stderr)
    sys.exit(2)
'''


def base_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("SLURM_JOB_ID", "SCHWINGNET_FLOW_STEP")}
    env.update(METAFLOW_USER="flowtest", **extra)
    return env


def launch(words, cwd, env, root):
    """flows/launch.py with the test's own datastore: its exit code, its JSON lines and its output."""
    done = subprocess.run([sys.executable, str(LAUNCH), words[0], "--root", str(root), *words[1:]], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=TIMEOUT)
    said = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    return done.returncode, said, done.stdout + done.stderr


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class RealismFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        for name in COPIED:
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, self.repo / name)
        shutil.copytree(ROOT / "vendor" / "beethoven-qa" / "src", self.repo / "vendor" / "beethoven-qa" / "src")
        (self.repo / "tools" / "realism.py").write_text(STUB_TOOL % {"subjects": SUBJECTS}, encoding="utf-8")
        run_code = self.repo / "tools" / "run_code.py"
        spec = importlib.util.spec_from_file_location("run_code_for_realism_test", run_code)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in module.KINDS["realism"]:
            path = self.repo / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {name}, a stand-in\n", encoding="utf-8")
        subprocess.run(self.git("init", "-q"), check=True, capture_output=True, timeout=60)
        self.commit("the stand-in")
        self.root, self.out, self.work = self.tmp / "metaflow", self.tmp / "realism", self.tmp / "work"
        self.work.mkdir()
        self.inputs = {name: self.tmp / name for name in ("samples.csv", "db", "ct", "truth", "klein", "bundle", "resnet18.pth")}
        for name, path in self.inputs.items():
            if "." in name:
                path.write_text("stand-in\n", encoding="utf-8")
            else:
                path.mkdir()
                (path / "stand-in").write_text("stand-in\n", encoding="utf-8")

    def git(self, *words):
        return ["git", "-C", str(self.repo), "-c", "user.name=flow test", "-c", "user.email=flow@test", "-c", "commit.gpgsign=false",
                "-c", "gc.auto=0", "-c", "gc.autoDetach=false", "-c", "maintenance.auto=false", "-c", "maintenance.autoDetach=false", *words]

    def commit(self, message):
        for words in (["add", "-A"], ["commit", "-q", "-m", message]):
            subprocess.run(self.git(*words), check=True, capture_output=True, timeout=60)

    def words(self, stage):
        given = ["--stage", stage, "--out", str(self.out), "--bundle", str(self.inputs["bundle"]),
                 "--imagenet", str(self.inputs["resnet18.pth"]), "--device", "cpu"]
        if stage == "edit":
            given += ["--samples", str(self.inputs["samples.csv"]), "--db", str(self.inputs["db"]), "--ct", str(self.inputs["ct"]),
                      "--truth", str(self.inputs["truth"]), "--klein", str(self.inputs["klein"])]
        return ["realism", "--max-workers", "1", "--", *given]

    def run_stage(self, stage, n, **extra):
        """One launch of a stage with its own call log: exit code, JSON lines, output, the calls."""
        calls = self.tmp / f"calls-{stage}-{n}"
        calls.write_text("", encoding="utf-8")
        env = base_env(SCHWINGNET=str(self.repo), FLOW_TEST_CALLS=str(calls), **extra)
        code, said, out = launch(self.words(stage), self.work, env, self.root)
        return code, said, out, calls.read_text(encoding="utf-8").splitlines()

    def last(self, stage):
        return json.loads((self.out / f"{stage}.last.json").read_text(encoding="utf-8"))

    def progress(self, said):
        folder = self.root / "progress" / "RealismFlow" / said[-1]["run"].split("/")[1]
        return folder, (folder / "PROGRESS.txt").read_text(encoding="utf-8").splitlines()

    def report_rows(self, folder, checklist):
        document = json.loads((Path(folder) / f"{checklist}.json").read_text(encoding="utf-8"))
        return {row["id"]: row for row in document["items"]}

    def test_the_edit_then_the_stats_run_through_the_launcher_with_their_reports_and_pages(self):
        code, said, out, calls = self.run_stage("edit", 1)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertEqual(calls, ["inputs", "poses", "split", "render 000", "edit 000", "score 000", "render 001", "edit 001",
                                 "score 001", "keep", "fluxray-export", "measure"])
        edit = Path(self.last("edit")["folder"])
        self.assertEqual(edit.parent, self.out)
        self.assertTrue(edit.name.startswith("edit-"))
        self.assertEqual(json.loads((self.out / "edit.json").read_text(encoding="utf-8"))["folder"], str(edit))
        record = json.loads((edit / "RECORD.json").read_text(encoding="utf-8"))
        self.assertEqual((record["study"], record["stage"], record["prereg"]), ("flux-realism", "edit", PREREG))
        self.assertNotIn("verdict", record)
        self.assertEqual(record["counts"]["renders"], 12 * 4)
        self.assertEqual(record["counts"]["edits"], 12 * 4 * 2)
        self.assertEqual(json.loads((edit / "ENDED.json").read_text(encoding="utf-8"))["verdict"], 0)
        claim = self.report_rows(edit, "claim")
        self.assertEqual(claim["7"]["state"], "met", claim["7"])
        self.assertIn("needs the stats stage's run", claim["37"]["evidence"])
        # the stand-in drew 12 subjects of the plan's 100, so the report says the run did not make every drawn sample
        corrupt = self.report_rows(edit, "reforms")["4b"]
        self.assertEqual(corrupt["state"], "missing")
        self.assertIn("renders 48 of 400", corrupt["evidence"])
        _, lines = self.progress(said)
        self.assertIn("verdict: 0", lines)
        self.assertTrue(any(line.startswith("report: ") and ": current; CLAIM 2024: " in line for line in lines), lines)

        code, said, out, calls = self.run_stage("stats", 1)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertEqual((calls[0], sorted(calls[1:])), ("environment", ["stats", "stats"]))
        stats = Path(self.last("stats")["folder"])
        self.assertTrue((stats / "edit" / "RECORD.json").is_file())
        self.assertEqual(json.loads((stats / "environment.json").read_text(encoding="utf-8"))["bundle"], str(self.inputs["bundle"]))
        record = json.loads((stats / "RECORD.json").read_text(encoding="utf-8"))
        self.assertEqual((record["replication"], record["geometry"]), ("reproduced", "holds"))
        self.assertEqual(record["words"], {"kept": "indistinguishable", "raw": "separable"})
        claim, reforms = self.report_rows(stats, "claim"), self.report_rows(stats, "reforms")
        code_missing = [row["id"] for row in [*claim.values(), *reforms.values()] if row["basis"] == "code" and row["state"] == "missing"]
        self.assertEqual(code_missing, ["4b"])
        self.assertIn("replication: reproduced", claim["37"]["evidence"])
        self.assertIn("RealismFlow", (self.progress(said)[0] / "index.html").read_text(encoding="utf-8"))

        # the same words again, after a run that ended well, are a new run of the same key (the gate
        # never sends them: a report that ended well queues nothing), begun in an empty folder of its
        # own so no file of the first draw is counted as its own; the new edit pointer names it
        first = (self.out / "edit.json").read_bytes()
        code, said, out, calls = self.run_stage("edit", 2)
        self.assertEqual(code, 0, out)
        self.assertEqual(said[0]["decision"], "run", out)
        again = Path(self.last("edit")["folder"])
        self.assertNotEqual(again, edit)
        self.assertEqual(again.name.rsplit("-", 1)[0], edit.name.rsplit("-", 1)[0])
        self.assertEqual(calls[:4], ["inputs", "poses", "split", "render 000"])
        self.assertEqual(json.loads((self.out / "edit.json").read_text(encoding="utf-8"))["folder"], str(again))
        self.assertNotEqual((self.out / "edit.json").read_bytes(), first)
        self.assertEqual(json.loads((again / "RECORD.json").read_text(encoding="utf-8"))["counts"]["renders"], 12 * 4)

    def test_a_stage_this_count_does_not_run_starts_no_tool(self):
        for stage in ("lora", "eval"):
            code, said, out, calls = self.run_stage(stage, 1)
            self.assertNotEqual(code, 0, out)
            self.assertIn("lora and eval wait for a count and a PREREG of their own", out)
            self.assertEqual(calls, [])

    def test_the_stats_refuse_without_an_edit_that_ended_well(self):
        code, said, out, calls = self.run_stage("stats", 1)
        self.assertNotEqual(code, 0, out)
        self.assertIn("send realism edit first", out)
        self.assertEqual(calls, [])

    def point_at_an_edit(self, verdict, prereg_sha256):
        """An edit folder by hand, with the ENDED.json and RECORD.json the stats read, named by edit.json."""
        folder = self.out / f"edit-by-hand-{verdict}-{prereg_sha256[:4]}"
        folder.mkdir(parents=True)
        paths = {"bundle": str(self.inputs["bundle"]), "imagenet": str(self.inputs["resnet18.pth"])}
        (folder / "ENDED.json").write_text(json.dumps({"verdict": verdict}), encoding="utf-8")
        (folder / "RECORD.json").write_text(json.dumps({"prereg_sha256": prereg_sha256, "paths": paths}), encoding="utf-8")
        (self.out / "edit.json").write_text(json.dumps({"folder": str(folder), "verdict": verdict}), encoding="utf-8")

    def test_the_stats_refuse_an_edit_whose_verdict_was_not_0_or_whose_prereg_differs(self):
        frozen = (self.repo / (PREREG + ".sha256")).read_text(encoding="ascii").split()[0]
        cases = ((1, frozen, "did not end with verdict 0"), (0, "0" * 64, "run under one frozen design"))
        for n, (verdict, prereg_sha256, said_why) in enumerate(cases):
            with self.subTest(verdict=verdict, prereg=prereg_sha256[:4]):
                self.point_at_an_edit(verdict, prereg_sha256)
                code, said, out, calls = self.run_stage("stats", n)
                self.assertNotEqual(code, 0, out)
                self.assertIn(said_why, out)
                self.assertEqual(calls, [])

    def test_an_edit_whose_report_fails_ends_with_verdict_1_and_names_no_edit_for_the_stats(self):
        (self.repo / "data" / "reporting" / "studies" / "flux-realism.json").write_text("{ not json\n", encoding="utf-8")
        self.commit("an answers file the report cannot read")
        code, said, out, calls = self.run_stage("edit", 1)
        self.assertEqual(code, 1, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 1), out)
        self.assertEqual(calls[-3:], ["keep", "fluxray-export", "measure"])
        self.assertFalse((self.out / "edit.json").exists())
        ended = self.last("edit")
        self.assertEqual(ended["verdict"], 1)
        self.assertIn("NOT CURRENT", ended["report"])
        code, said, out, calls = self.run_stage("stats", 1)
        self.assertNotEqual(code, 0, out)
        self.assertIn("send realism edit first", out)
        self.assertEqual(calls, [])

    def test_an_edit_short_of_its_draw_ends_with_verdict_1_and_names_no_edit_for_the_stats(self):
        code, said, out, calls = self.run_stage("edit", 1, FLOW_TEST_SHORT="1")
        self.assertEqual(code, 1, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 1), out)
        self.assertFalse((self.out / "edit.json").exists())
        summary = (Path(self.last("edit")["folder"]) / "SUMMARY.md").read_text(encoding="utf-8")
        self.assertIn("short of the draw: fluxray_exported 47 of 48", summary)

    def test_a_shard_that_fails_fails_the_run_and_the_word_again_resumes_from_it(self):
        code, said, out, calls = self.run_stage("edit", 1, FLOW_TEST_FAIL="001")
        self.assertNotEqual(code, 0, out)
        self.assertEqual(calls.count("render 001"), 2, calls)  # retried once, then the run fails
        self.assertFalse((self.out / "edit.json").exists())
        code, said, out, calls = self.run_stage("edit", 2)
        self.assertEqual(code, 0, out)
        self.assertEqual(said[0]["decision"], "resume", out)
        self.assertEqual(calls, ["render 001", "edit 001", "score 001", "keep", "fluxray-export", "measure"])
        self.assertEqual(len(list((self.out).glob("edit-*"))), 1)
        # the resume clones start, so the folder and where name the run that failed; the record and
        # the pointers name the run that ended it too, which the job's report and the stats read
        folder = Path(self.last("edit")["folder"])
        ended, record = (json.loads((folder / name).read_text(encoding="utf-8")) for name in ("ENDED.json", "RECORD.json"))
        self.assertEqual((ended["run"], record["ended_in"]["run"]), (said[-1]["run"], said[-1]["run"]))
        self.assertNotEqual(ended["started_run"], ended["run"])
        self.assertEqual(record["where"]["run"], ended["started_run"])
        self.assertTrue(folder.name.endswith("-" + ended["started_run"].split("/")[1]), folder)

    def test_a_failed_run_whose_cts_changed_is_begun_again_not_resumed(self):
        code, said, out, calls = self.run_stage("edit", 1, FLOW_TEST_FAIL="001")
        self.assertNotEqual(code, 0, out)
        (self.inputs["ct"] / "landed-since").write_text("a CT that landed after the first run\n", encoding="utf-8")
        code, said, out, calls = self.run_stage("edit", 2)
        self.assertEqual(code, 0, out)
        self.assertEqual(said[0]["decision"], "run", out)
        self.assertEqual(calls[:3], ["inputs", "poses", "split"])
        self.assertEqual(len(list(self.out.glob("edit-*"))), 2)

    def test_a_frozen_block_that_differs_from_the_code_starts_no_tool(self):
        prereg = self.repo / PREREG
        text = prereg.read_text(encoding="utf-8").replace("verdict.geometry_shift_px = 1.0", "verdict.geometry_shift_px = 2.0")
        self.assertIn("verdict.geometry_shift_px = 2.0", text)
        prereg.write_text(text, encoding="utf-8")
        (self.repo / (PREREG + ".sha256")).write_text(f"{hashlib.sha256(text.encode()).hexdigest()}  PREREG.md\n", encoding="ascii")
        self.commit("a frozen block that is not the code's")
        code, said, out, calls = self.run_stage("edit", 1)
        self.assertNotEqual(code, 0, out)
        self.assertIn("the PREREG's frozen block and the code that runs differ", out)
        self.assertIn("verdict.geometry_shift_px", out)
        self.assertEqual(calls, [])

    def test_a_prereg_moved_since_its_freeze_starts_nothing(self):
        with (self.repo / PREREG).open("a", encoding="utf-8") as prereg:
            prereg.write("An edit after the freeze.\n")
        self.commit("an edit to the PREREG after its freeze")
        code, said, out, calls = self.run_stage("edit", 1)
        self.assertEqual(code, 90, out)
        self.assertEqual((said, calls), ([], []), out)


if __name__ == "__main__":
    unittest.main()
