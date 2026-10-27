"""tools/domain_gap.py's analysis in a Slurm array (prepare, shard, merge), the owner's word of
2026-10-27 17:51 UTC that the study be sharded onto the H200 nodes by the Lab Recipe's rules: the
array's result is the one-process run's to the bit, two tasks working at once share the list with
no unit done twice, a pool of spawned workers gives each unit the result it gets in one process, a
claim whose holder stopped beating is taken over and a live one never is, a task stops after three
failures in a row, a task with no list exits 0 having claimed nothing, the merge refuses while any
unit is open and says how many of which kind, and PROGRESS.txt says where the study stands in lines
that name no file and survive the grid's redaction.

It runs on the made-up corpora of tests/test_domain_gap_run.py and needs what that file needs, so
each case runs where those import and is skipped elsewhere.

    <venv>/bin/python -m unittest tests/test_domain_gap_array.py
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def neighbour():
    """tests/test_domain_gap_run.py as a module, for its corpora and fakes; its test cases are not
    bound here, so they run once, from their own file."""
    spec = importlib.util.spec_from_file_location("domain_gap_run_tests", ROOT / "tests" / "test_domain_gap_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = neighbour()
SMALL = {"PERMUTATIONS_C2ST": 5, "PERMUTATIONS_MMD": 50, "BOOTSTRAP": 50, "SPLIT_PERSONS": 12}


def small_tool():
    tool = RUN.load_tool()
    for name, value in SMALL.items():
        setattr(tool, name, value)
    tool.PROGRESS_SECONDS = 0
    return tool


def without_record(results):
    return {k: v for k, v in results.items() if k not in ("_run", "_record")}


def shard_args(out, task=0, tasks=1, workers=1):
    return argparse.Namespace(out=str(out), task=task, tasks=tasks, workers=workers, device="cpu")


def merge_args(out, groups):
    return argparse.Namespace(out=str(out), groups=str(groups), wandb="off")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@unittest.skipIf(RUN.MISSING_WHOLE, f"needs {', '.join(RUN.MISSING_WHOLE)}")
class ArrayTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.tool = small_tool()
        self.args, self.renderer = RUN.WholeRunTest.corpora(self, self.tool, self.folder)
        self.out = Path(self.args.out)
        self.analysis = self.out / "analysis"

    def tearDown(self):
        self.temporary.cleanup()

    def prepared(self):
        self.assertEqual(self.tool.prepare(self.args), 0)
        return read(self.analysis / "units.json")

    def test_the_array_gives_the_run_s_result_to_the_bit(self):
        # the one-process run first, then prepare on the same folder (every stage up to the
        # features kept), two tasks at once and the merge: results.json is the same object but
        # for the record of what ran where, and the summary the same lines but for the record's
        self.assertEqual(self.tool.run(self.args), 0)
        serial = read(self.out / "results.json")
        serial_lines = (self.out / "summary.txt").read_text(encoding="ascii").splitlines()
        (self.out / "results.json").unlink()
        record = self.prepared()
        self.assertTrue((self.analysis / "PREPARED.json").is_file())
        self.assertEqual(record["keys"], ["flexray", "imagenet", "physics"])
        self.assertEqual(set(record["invalid"]), {"flexray", "imagenet"})
        kinds = {u["kind"] for u in record["units"]}
        self.assertEqual(kinds, {"family", "group", "real", "fvf", "replication", "null", "structure", "nearest",
                                 "fd_all", "maps"})
        codes = []
        tasks = [threading.Thread(target=lambda k=k: codes.append(self.tool.shard(shard_args(self.out, k, 2))))
                 for k in range(2)]
        for thread in tasks:
            thread.start()
        for thread in tasks:
            thread.join()
        self.assertEqual(codes, [0, 0])
        self.assertEqual(self.tool.merge(merge_args(self.out, self.args.groups)), 0)
        sharded = read(self.out / "results.json")
        self.assertEqual(without_record(sharded), without_record(serial))
        lines = (self.out / "summary.txt").read_text(encoding="ascii").splitlines()
        self.assertEqual([x for x in lines if not x.startswith("record: ")],
                         [x for x in serial_lines if not x.startswith("record: ")])
        self.assertTrue(lines[1].startswith("record: jobs prepare local, array none (2 tasks), merge local; GPUs cpu x3"),
                        lines[1])
        self.assertTrue(lines[2].startswith(f"record: units {len(record['units'])} of {len(record['units'])} done, 0 failed;"
                                            " mmd backend "), lines[2])
        # both tasks worked, and no unit was done twice
        done = [json.loads(line) for path in sorted((self.analysis / "events").glob("*.jsonl"))
                for line in path.read_text(encoding="utf-8").splitlines()]
        finished = [e for e in done if e["event"] == "done"]
        self.assertEqual(sorted(e["index"] for e in finished), list(range(len(record["units"]))))
        self.assertEqual({e["task"] for e in finished}, {0, 1})
        self.assertTrue(list((self.out / "figures").glob("*.png")))
        self.assertEqual(sharded["_run"]["git_head"], serial["_run"]["git_head"])
        self.assertEqual(len(sharded["_run"]["prereg_sha256"]), 64 if self.tool.PREREG.is_file() else 0)

    def test_a_pool_of_spawned_workers_gives_each_unit_its_one_process_result(self):
        # the grid's tasks run their units in spawned workers of one thread each; the script run
        # as it runs there, on a few cheap units of the list at the study's own constants, gives
        # every unit the result the same unit gets in a process of one thread (a process of many
        # BLAS and torch threads sums in another order, which moves float32 results in their
        # seventh digit, as DEVIATIONS.md item 2 says)
        tool = RUN.load_tool()
        tool.tool = self.tool.tool
        self.tool = tool
        record = self.prepared()
        keep = [u for u in record["units"] if u["kind"] in ("real", "fd_all", "structure")][:5]
        record["units"] = keep
        record_path = self.analysis / "units.json"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "domain_gap.py"), "shard", "--out", str(self.out),
                               "--workers", "2", "--device", "cpu"], capture_output=True, text=True, timeout=900,
                              env=environment)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        one_thread = dict(environment, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        script = ("import importlib.util, json, sys\n"
                  "spec = importlib.util.spec_from_file_location('one_thread_tool', sys.argv[1])\n"
                  "tool = importlib.util.module_from_spec(spec); sys.modules[spec.name] = tool; spec.loader.exec_module(tool)\n"
                  "record = json.loads(open(sys.argv[3], encoding='utf-8').read())\n"
                  "head = tool.load_head(sys.argv[2], 'physics')\n"
                  "print(json.dumps([tool.run_unit(head, unit, record['seed'])[0] for unit in record['units']]))\n")
        alone = subprocess.run([sys.executable, "-c", script, str(ROOT / "tools" / "domain_gap.py"), str(self.out), str(record_path)],
                               capture_output=True, text=True, timeout=900, env=one_thread)
        self.assertEqual(alone.returncode, 0, alone.stderr)
        pieces = json.loads(alone.stdout.splitlines()[-1])
        for index, unit in enumerate(keep):
            here = pieces[index]
            there = read(self.analysis / "done" / f"{index:05d}.json")
            self.assertEqual(there["piece"], here, unit["id"])
            self.assertEqual(there["stamp"], record["stamp"])

    def test_a_live_claim_is_never_taken_and_a_stale_one_is(self):
        self.prepared()
        tool = self.tool
        tool.TAKEOVER_SETTLE = 0.0
        self.assertTrue(tool.try_claim(self.analysis, 3, "first"))
        self.assertFalse(tool.try_claim(self.analysis, 3, "second"))
        self.assertEqual(tool.claim_path(self.analysis, 3).read_text(encoding="ascii"), "first")
        old = time.time() - tool.STALE_SECONDS - 5
        os.utime(tool.claim_path(self.analysis, 3), (old, old))
        self.assertTrue(tool.try_claim(self.analysis, 3, "second"))
        self.assertEqual(tool.claim_path(self.analysis, 3).read_text(encoding="ascii"), "second")

    def test_a_task_waits_for_a_live_claim_then_takes_it_over_once_stale(self):
        # another task holds unit 0 and stops beating: this task does every other unit, watches
        # that one, and takes it over once its claim is stale, so the merge finds the list whole
        record = self.prepared()
        tool = self.tool
        tool.TAKEOVER_SETTLE, tool.WATCH_SECONDS, tool.STALE_SECONDS = 0.0, 0.2, 2.0
        heaviest = sorted(range(len(record["units"])), key=lambda i: (-tool.unit_cost(record["units"][i]), i))[0]
        self.assertTrue(tool.try_claim(self.analysis, heaviest, "a task that died"))
        self.assertEqual(tool.shard(shard_args(self.out)), 0)
        self.assertEqual(tool.claim_path(self.analysis, heaviest).read_text(encoding="ascii").split(" ")[0], "local")
        self.assertEqual(tool.merge(merge_args(self.out, self.args.groups)), 0)

    def test_three_failures_in_a_row_stop_the_task_and_the_merge_says_what_is_open(self):
        record = self.prepared()
        tool = self.tool
        real = tool.run_unit
        tool.run_unit = lambda head, unit, seed=0: (_ for _ in ()).throw(ArithmeticError("made up"))
        self.assertEqual(tool.shard(shard_args(self.out)), 3)
        failed = sorted(p.name for p in (self.analysis / "failed").iterdir())
        self.assertEqual(len(failed), tool.FAILURE_STREAK)
        self.assertEqual(read(self.analysis / "failed" / failed[0])["error"], "ArithmeticError")
        tool.run_unit = real
        printed = self.main_of(tool, ["merge", "--out", str(self.out), "--wandb", "off"])
        self.assertEqual(printed[0], 2)
        total = len(record["units"])
        self.assertIn(f"{total - 3} of {total} units not done (", printed[1])
        self.assertIn(" and 3 failed (", printed[1])
        self.assertFalse((self.out / "results.json").exists())
        # a fresh prepare clears the failures, keeps nothing done since nothing was, and the list completes
        self.prepared()
        self.assertEqual(list((self.analysis / "failed").iterdir()), [])
        self.assertEqual(tool.shard(shard_args(self.out)), 0)
        self.assertEqual(tool.merge(merge_args(self.out, self.args.groups)), 0)

    def test_a_broken_pool_fails_no_unit_and_a_smaller_pool_takes_its_units(self):
        # the first pool breaks every unit it is given, as a worker the OOM killer takes breaks a
        # process pool: the units are let go, not failed, and a pool of half the workers does them
        from concurrent.futures import Future, ThreadPoolExecutor
        from concurrent.futures.process import BrokenProcessPool

        class Broken:
            def submit(self, *args):
                future = Future()
                future.set_exception(BrokenProcessPool("a worker died"))
                return future

            def shutdown(self, wait=True, cancel_futures=False):
                pass

        record = self.prepared()
        tool, sizes = self.tool, []
        tool.unit_pool = lambda workers: sizes.append(workers) or (Broken() if len(sizes) == 1 else ThreadPoolExecutor(1))
        self.assertEqual(tool.shard(shard_args(self.out, workers=4)), 0)
        self.assertEqual(sizes, [4, 2])
        self.assertEqual(list((self.analysis / "failed").iterdir()), [])
        events = [json.loads(line) for path in (self.analysis / "events").glob("*.jsonl")
                  for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sum(e["event"] == "released" for e in events), 4)
        self.assertTrue(all(tool.unit_done(self.analysis, i, record["stamp"]) for i in range(len(record["units"]))))

    def test_three_broken_pools_in_a_row_stop_the_task_with_its_claims_let_go(self):
        from concurrent.futures import Future
        from concurrent.futures.process import BrokenProcessPool

        class Broken:
            def submit(self, *args):
                future = Future()
                future.set_exception(BrokenProcessPool("a worker died"))
                return future

            def shutdown(self, wait=True, cancel_futures=False):
                pass

        self.prepared()
        tool = self.tool
        tool.unit_pool = lambda workers: Broken()
        self.assertEqual(tool.shard(shard_args(self.out, workers=8)), 3)
        self.assertEqual(list((self.analysis / "failed").iterdir()), [])
        self.assertEqual(list((self.analysis / "claims").iterdir()), [])

    def test_a_unit_of_a_replaced_list_writes_nothing_and_is_no_failure(self):
        record = self.prepared()
        tool = self.tool
        with self.assertRaises(tool.ListChanged):
            tool.unit_task(str(self.out), 0, "another list's stamp")
        self.assertFalse(tool.done_path(self.analysis, 0).exists())

        class Replaced:
            def result(self):
                raise tool.ListChanged("replaced")

        task = tool.Task(self.analysis, 0, 1, "cpu", record["stamp"])
        self.assertIsNone(tool.settle(self.analysis, task, record["units"], 0, Replaced(), time.time()))
        self.assertFalse(tool.failed_path(self.analysis, 0).exists())

    def test_a_failure_names_the_frames_of_the_study_it_rose_through(self):
        def deepest():
            raise ArithmeticError("made up")

        try:
            deepest()
        except ArithmeticError as error:
            where = self.tool.where_raised(error)
        self.assertRegex(where[-1], r"^test_domain_gap_array[.]py:deepest:[0-9]+$")

        class Remote(Exception):
            tb = 'Traceback:\n  File "/grid/code/tools/domain_gap.py", line 12, in run_unit\n  File "/grid/code/tools/domain_gap_stats.py", line 34, in mmd\n'

        error = ValueError("in a worker")
        error.__cause__ = Remote()
        self.assertEqual(self.tool.where_raised(error), ["domain_gap.py:run_unit:12", "domain_gap_stats.py:mmd:34"])

    def test_events_a_killed_task_left_half_written_or_out_of_the_list_are_passed_over(self):
        record = self.prepared()
        self.assertEqual(self.tool.shard(shard_args(self.out)), 0)
        events = next((self.analysis / "events").glob("*.jsonl"))
        with open(events, "a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": "done", "index": len(record["units"]) + 5, "at": time.time(), "stamp": record["stamp"]}) + "\n")
            stream.write(json.dumps({"event": "done", "index": 0, "at": time.time(), "stamp": "an old list"}) + "\n")
            stream.write("[1, 2]\n")
            stream.write('{"event": "done", "index": 1, "at"')
        self.assertEqual(len([e for e in self.tool.events_of(self.tool.units_record(self.out)) if e["event"] == "done"]),
                         len(record["units"]))
        self.tool.write_progress(self.out, force=True)
        self.assertEqual(self.tool.merge(merge_args(self.out, self.args.groups)), 0)
        # a new prepare clears the events with the claims and the failures
        self.prepared()
        self.assertEqual(list((self.analysis / "events").iterdir()), [])

    def test_done_units_are_kept_across_a_prepare_and_other_code_does_them_again(self):
        record = self.prepared()
        tool = self.tool
        self.assertEqual(tool.shard(shard_args(self.out)), 0)
        stamp = record["stamp"]
        self.assertEqual(self.prepared()["stamp"], stamp)
        self.assertTrue(all(tool.unit_done(self.analysis, i, stamp) for i in range(len(record["units"]))))
        # other code: its digest differs, so a task refuses the list and a prepare names new units
        tool.code_digest = lambda: "0" * 64
        self.assertEqual(self.main_of(tool, ["shard", "--out", str(self.out), "--device", "cpu"])[0], 2)
        fresh = self.prepared()
        self.assertNotEqual(fresh["stamp"], stamp)
        self.assertFalse(tool.unit_done(self.analysis, 0, fresh["stamp"]))

    def test_a_task_with_no_list_claims_nothing_and_exits_0(self):
        self.assertEqual(self.tool.shard(shard_args(self.out)), 0)
        self.assertFalse((self.analysis / "claims").exists())
        printed = self.main_of(self.tool, ["merge", "--out", str(self.out), "--wandb", "off"])
        self.assertEqual(printed[0], 2)
        self.assertIn("prepare did not finish", printed[1])

    def test_progress_names_no_file_and_survives_the_grid_s_redaction(self):
        record = self.prepared()
        self.assertEqual(self.tool.shard(shard_args(self.out, 0, 1)), 0)
        lines = (self.out / "PROGRESS.txt").read_text(encoding="ascii").splitlines()
        total = len(record["units"])
        self.assertIn(f"units {total} of {total} done, 0 running, 0 failed", lines[0])
        self.assertTrue(any(line.startswith("stage render: done in ") for line in lines))
        self.assertTrue(any(line.startswith("reading physics: ") for line in lines))
        self.assertTrue(any(line.startswith("reading flexray: not read, no FleXray bundle") for line in lines))
        self.assertTrue(any(line.startswith("task 0 (local, ") for line in lines))
        self.assertTrue(any(line.startswith("timeline of units done: ") for line in lines))
        masked = subprocess.run(["sed", "-r", "-f", str(ROOT / "grid" / "redact.sed")], input="\n".join(lines) + "\n",
                                capture_output=True, text=True).stdout.splitlines()
        self.assertEqual(masked, lines)
        for line in lines:
            self.assertLessEqual(len(line), 200)
            self.assertNotIn(str(self.folder), line)
            # no image, mask or array file of the run is named; a reason may name a config file the
            # tool looks for, as "no FleXray bundle (ensemble.json)" does
            self.assertIsNone(re.search(r"\.(png|jpe?g|tiff?|dcm|npz|nii)\b", line), line)

    def main_of(self, tool, argv):
        """(the exit code, what main printed) of one command line."""
        import contextlib
        import io

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = tool.main(argv)
        return code, printed.getvalue()


if __name__ == "__main__":
    unittest.main()
