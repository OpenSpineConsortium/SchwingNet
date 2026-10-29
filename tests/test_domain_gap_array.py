"""tools/domain_gap.py's analysis in a Slurm array (prepare, shard, merge), the owner's word of
2026-10-27 17:51 UTC that the study be sharded onto the H200 nodes by the Lab Recipe's rules: the
array's result is the one-process run's to the bit (both in a process of one BLAS, OpenMP and
torch thread, as the grid's workers run), two tasks working at once share the list with no unit
done twice, a pool of spawned workers gives each unit the result it gets in one process, a
claim whose holder stopped beating is taken over and a live one never is, a task stops after three
failures in a row, a task with no list exits 0 having claimed nothing, the merge refuses while any
unit is open and says how many of which kind, PROGRESS.txt says where the study stands in lines
that name no file and survive the grid's redaction, and the run log says what each step did as it
did it, Slurm's TERM among the ends (the owner's ask of 2026-10-28 00:23 UTC for real-time logging).

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
import signal
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
ONE_THREAD = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
IN_ONE_THREAD = "DOMAIN_GAP_TEST_ONE_THREAD"


def in_one_thread():
    return os.environ.get(IN_ONE_THREAD) == "1"


def rerun_in_one_thread(case, name):
    """The test case name again in a new process whose BLAS, OpenMP and torch libraries each start
    with one thread, as the grid's workers do (tools/domain_gap.py, unit_pool): the libraries read
    these settings when they load, and OpenMP's is each thread's own after that, so a new process
    is the one place that sets them for every thread it starts."""
    script = ("import importlib.util, sys, unittest\n"
              "spec = importlib.util.spec_from_file_location('domain_gap_array_one_thread', sys.argv[1])\n"
              "tests = importlib.util.module_from_spec(spec); spec.loader.exec_module(tests)\n"
              "result = unittest.TextTestRunner(verbosity=2).run(tests.ArrayTest(sys.argv[2]))\n"
              "sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)\n")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **ONE_THREAD, **{IN_ONE_THREAD: "1"})
    done = subprocess.run([sys.executable, "-c", script, str(Path(__file__).resolve()), name],
                          capture_output=True, text=True, timeout=1800, env=environment)
    case.assertEqual(done.returncode, 0, (done.stdout + done.stderr)[-6000:])


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
        # for the record of what ran where, and the summary the same lines but for the record's.
        # Both run in a process of one library thread, as the grid's workers do: how BLAS splits
        # a product among its threads changes the order it sums in (the study's z64 times its
        # transpose comes out differently with one, two, three and four threads), and with four
        # the run and the array did not always agree in the last digit of a silhouette
        # (DEVIATIONS.md, item 2)
        if not in_one_thread():
            rerun_in_one_thread(self, "test_the_array_gives_the_run_s_result_to_the_bit")
            return
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
        self.assertIn(f"task 0: took over the stale claim on unit {heaviest}, whose holder had not beaten for 0 min", self.logged())
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
        logged = self.logged()
        self.assertEqual(len([line for line in logged if " FAILED after " in line and "(ArithmeticError; its job's log has the message)" in line]), 3)
        self.assertNotIn("made up", "\n".join(logged))
        self.assertEqual(logged[-1], "task 0: stopped after 3 failures in a row, 0 done here")
        tool.run_unit = real
        printed = self.main_of(tool, ["merge", "--out", str(self.out), "--wandb", "off"])
        self.assertEqual(printed[0], 2)
        total = len(record["units"])
        self.assertIn(f"{total - 3} of {total} units not done (", printed[1])
        self.assertTrue(self.logged()[-2].startswith(f"merge: refused, {total - 3} of {total} units not done ("), self.logged())
        self.assertEqual(self.logged()[-1], "merge: FAILED, as its step's line in the bench report says")
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
        tool.unit_pool = lambda workers, processes=None: sizes.append(workers) or (Broken() if len(sizes) == 1 else ThreadPoolExecutor(1))
        self.assertEqual(tool.shard(shard_args(self.out, workers=4)), 0)
        self.assertEqual(sizes, [4, 2])
        self.assertEqual(list((self.analysis / "failed").iterdir()), [])
        self.assertIn("task 0: a worker died and broke the pool of 4: 4 units let go and claimed again by 2 workers", self.logged())
        events = [json.loads(line) for path in (self.analysis / "events").glob("*.jsonl")
                  for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sum(e["event"] == "released" for e in events), 4)
        self.assertTrue(all(tool.unit_done(self.analysis, i, record["stamp"]) for i in range(len(record["units"]))))

    def test_pools_that_always_break_halve_to_one_worker_and_three_lone_deaths_stop_the_task(self):
        # a pool that cannot run anything: halved to one worker, whose death fails its one unit,
        # then the full count again, until three units have failed alone in a row
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
        tool, sizes = self.tool, []
        tool.unit_pool = lambda workers, processes=None: sizes.append((workers, processes)) or Broken()
        self.assertEqual(tool.shard(shard_args(self.out, workers=8)), 3)
        self.assertEqual(sizes[:6], [(8, None), (4, True), (2, True), (1, True), (8, True), (4, True)])
        failed = sorted(p.name for p in (self.analysis / "failed").iterdir())
        self.assertEqual(len(failed), tool.FAILURE_STREAK)
        self.assertEqual({read(self.analysis / "failed" / name)["error"] for name in failed}, {"BrokenProcessPool"})
        alone = [line for line in self.logged() if " alone, so it is failed, and a pool of 8 workers goes on" in line]
        self.assertEqual(len(alone), tool.FAILURE_STREAK, self.logged())
        self.assertLessEqual({p.name for p in (self.analysis / "claims").iterdir()}, {name[:-len(".json")] for name in failed})

    def test_a_unit_that_kills_its_worker_fails_alone_and_every_other_unit_is_done(self):
        # one unit breaks every pool it is in, as one too big for the job's memory would: the pools
        # halve until it runs alone, it alone is failed, and the full pool does the rest
        from concurrent.futures import Future
        from concurrent.futures.process import BrokenProcessPool

        record = self.prepared()
        tool = self.tool
        units = record["units"]
        poison = sorted(range(len(units)), key=lambda i: (-tool.unit_cost(units[i]), i))[0]

        class Pool:
            def __init__(self):
                self.broken = False

            def submit(self, fn, *args):
                future = Future()
                if self.broken or args[1] == poison:
                    self.broken = True
                    future.set_exception(BrokenProcessPool("a worker died"))
                    return future
                try:
                    future.set_result(fn(*args))
                except Exception as error:  # the real unit's own failure, as a pool would hand it back
                    future.set_exception(error)
                return future

            def shutdown(self, wait=True, cancel_futures=False):
                pass

        sizes = []
        tool.unit_pool = lambda workers, processes=None: sizes.append(workers) or Pool()
        self.assertEqual(tool.shard(shard_args(self.out, workers=4)), 0)
        self.assertIn(1, sizes)
        failed = [p.name for p in (self.analysis / "failed").iterdir()]
        self.assertEqual(failed, [f"{poison:05d}.json"])
        self.assertEqual(read(self.analysis / "failed" / failed[0])["error"], "BrokenProcessPool")
        self.assertTrue(all(tool.unit_done(self.analysis, i, record["stamp"]) for i in range(len(units)) if i != poison))

    def test_a_list_the_volume_will_not_read_for_a_while_stops_no_task(self):
        # units.json unreadable for every read after the task's first: no task stops, and each
        # unit is still written, since only a list read whole with another stamp is a new one
        record = self.prepared()
        tool = self.tool
        tool.LIST_RETRY_SECONDS = 0.0
        real, reads = tool.units_record, []
        tool.units_record = lambda out: reads.append(1) or (real(out) if len(reads) == 1 else None)
        self.assertEqual(tool.shard(shard_args(self.out)), 0)
        self.assertGreater(len(reads), 1)
        self.assertTrue(all(tool.unit_done(self.analysis, i, record["stamp"]) for i in range(len(record["units"]))))

    def test_a_unit_of_a_replaced_list_writes_nothing_and_is_no_failure(self):
        record = self.prepared()
        tool = self.tool
        with self.assertRaises(tool.ListChanged):
            tool.unit_task(str(self.out), 0, record["units"][0], record["seed"], "another list's stamp")
        self.assertFalse(tool.done_path(self.analysis, 0).exists())

        class Replaced:
            def result(self):
                raise tool.ListChanged("replaced")

        # this task's claim is let go; one another task has taken since is left as it stands
        task = tool.Task(self.analysis, 0, 1, "cpu", record["stamp"])
        self.assertTrue(tool.try_claim(self.analysis, 0, task.token))
        self.assertTrue(tool.try_claim(self.analysis, 1, "another task"))
        for index in (0, 1):
            self.assertIsNone(tool.settle(self.analysis, task, record["units"], index, Replaced(), time.time()))
            self.assertFalse(tool.failed_path(self.analysis, index).exists())
        self.assertFalse(tool.claim_path(self.analysis, 0).exists())
        self.assertEqual(tool.claim_path(self.analysis, 1).read_text(encoding="ascii"), "another task")

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

    def test_the_run_log_says_what_each_step_did_as_it_did_it(self):
        # the owner's ask of 2026-10-28 00:23 UTC, "make sure there is realtime logging in the
        # CLAIMS/REPORT": prepare's start and each stage, each task's start with its node and card and
        # its end, the merge's reading back; PROGRESS.txt ends with the newest, each unit done among
        # them; runlog writes RUNLOG.txt with every unit and prints at most RUNLOG_REPORT lines with
        # the quarter marks, every line surviving the grid's redaction and naming no file
        record = self.prepared()
        tool, total = self.tool, len(record["units"])
        self.assertEqual(self.logged()[:3], ["prepare: started as job local on " + socket_name(), "prepare: computes on cpu",
                                             "prepare: stage render started"])
        self.assertIn("prepare: stage features done after ", "\n".join(self.logged()))
        self.assertEqual(self.logged()[-1], f"prepare: {total} units listed over 3 readings (2 not read), so the array's tasks claim them")
        codes = []
        tasks = [threading.Thread(target=lambda k=k: codes.append(tool.shard(shard_args(self.out, k, 2)))) for k in range(2)]
        for thread in tasks:
            thread.start()
        for thread in tasks:
            thread.join()
        self.assertEqual(codes, [0, 0])
        logged = self.logged()
        for k in range(2):
            self.assertIn(f"task {k}: started as job local of 2 tasks on {socket_name()}, cpu, 1 worker, {total} units in the list", logged)
            self.assertEqual(len([line for line in logged if line.startswith(f"task {k}: finished, nothing left to claim: ")]), 1)
        progress = (self.out / "PROGRESS.txt").read_text(encoding="ascii").splitlines()
        newest = [line for line in progress if line.startswith("log: ")]
        self.assertEqual(len(newest), tool.RUNLOG_TAIL)
        self.assertEqual(progress[-len(newest):], newest)
        self.assertTrue(any(re.fullmatch(r"log: \d\d:\d\d:\d\d task [01]: unit physics/\S+ done in \d+[.]\d s", line) for line in newest), newest)
        self.assertRegex(newest[-1], r"^log: \d\d:\d\d:\d\d task [01]: finished, nothing left to claim: ")
        # the step's last line reaches PROGRESS.txt however lately it was rewritten
        tool.PROGRESS_SECONDS = 3600
        self.assertEqual(self.main_of(tool, ["merge", "--out", str(self.out), "--groups", str(self.args.groups), "--wandb", "off"])[0], 0)
        self.assertEqual(self.logged()[-1], "merge: results.json, the figures and summary.txt written")
        self.assertTrue((self.out / "PROGRESS.txt").read_text(encoding="ascii").splitlines()[-1].endswith(
            " merge: results.json, the figures and summary.txt written"))
        self.assertIn(f"merge: every one of the {total} units read back as done, from 2 tasks; the jobs ran on cpu x3,"
                      " prepare's among them", self.logged())
        code, printed = self.main_of(tool, ["runlog", "--out", str(self.out)])
        self.assertEqual(code, 0)
        lines = printed.splitlines()
        self.assertLessEqual(len(lines), tool.RUNLOG_REPORT)
        self.assertTrue(all(re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \S", line) for line in lines), lines)
        marks = [line[20:] for line in lines if line[20:].startswith("units: ")]
        counts = [-(-total * share // 4) for share in (1, 2, 3, 4)]
        self.assertEqual(marks, [f"units: 1 of {total} done, the first"]
                         + [f"units: {count} of {total} done ({count / total:.0%})" for count in counts])
        self.assertFalse(any(" unit physics/" in line and " done in " in line for line in lines))
        # the tasks' routine starts and finishes are one line each, every other line of them kept
        self.assertFalse(any(re.search(r" task \d: (started|finished)", line) for line in lines), lines)
        self.assertEqual(len([line for line in lines if line[20:].startswith("tasks: 2 started from ")
                              and line.endswith(" on 1 node, cpu x2")]), 1, lines)
        self.assertEqual(len([line for line in lines if line[20:].startswith("tasks: 2 finished with nothing left to claim from ")
                              and line.endswith(f", {total} units done and 0 failed among them")]), 1, lines)
        whole = (self.out / "RUNLOG.txt").read_text(encoding="ascii").splitlines()
        self.assertEqual(len([line for line in whole if " done in " in line and ": unit " in line]), total)
        masked = subprocess.run(["sed", "-r", "-f", str(ROOT / "grid" / "redact.sed")], input="\n".join(whole + lines) + "\n",
                                capture_output=True, text=True).stdout.splitlines()
        self.assertEqual(masked, whole + lines)
        for line in whole + newest:
            self.assertNotIn(str(self.folder), line)
            self.assertIsNone(re.search(r"\.(png|jpe?g|tiff?|dcm|npz|nii)\b", line), line)
        # a unit a slow task finished after another task took it over is done twice, and counts once
        done = next(json.loads(line) for path in sorted((self.analysis / "events").glob("*.jsonl"))
                    for line in path.read_text(encoding="utf-8").splitlines() if json.loads(line)["event"] == "done")
        later = {**done, "at": time.time() + 1, "task": 9}
        (self.analysis / "events" / "task-0009-1.jsonl").write_text(json.dumps(later) + "\n", encoding="utf-8")
        self.assertEqual(self.main_of(tool, ["runlog", "--out", str(self.out)]), (0, printed))
        whole = (self.out / "RUNLOG.txt").read_text(encoding="ascii").splitlines()
        self.assertEqual(len([line for line in whole if " done in " in line and ": unit " in line]), total)
        # a report with less room than the log keeps every quarter mark, the first line and the
        # merge's last, and says once how many it left out and where they are
        tool.RUNLOG_REPORT = 8
        code, cut = self.main_of(tool, ["runlog", "--out", str(self.out)])
        cut = cut.splitlines()
        self.assertEqual((code, len(cut)), (0, 8), cut)
        self.assertEqual([line[20:] for line in cut if line[20:].startswith("units: ")], marks)
        self.assertEqual([line for line in cut if line.startswith("... ")],
                         [f"... {len(lines) - 7} lines not shown here; the run folder's RUNLOG.txt holds them"])
        self.assertEqual((cut[0], cut[-1]), (lines[0], lines[-1]))
        self.assertEqual(lines[-1][20:], "merge: results.json, the figures and summary.txt written")
        # a new prepare starts the run log over: nothing of the chain before it is read as this one's,
        # and its units, done already, count from the start
        self.prepared()
        self.assertFalse(any(line.startswith(("task ", "merge: ")) for line in self.logged()), self.logged())
        self.assertEqual(self.logged()[-1], f"prepare: {total} units listed over 3 readings (2 not read), so the array's tasks"
                                            f" claim them; {total} of them an earlier chain left done, which count as done")

    def test_the_run_log_says_how_every_task_ended_its_failures_among_them(self):
        # a task that stops at a step's own refusal, or at an error nobody foresaw, says so in its
        # own file by the kind of the error alone, so the CLAIM report shows every task's end
        self.prepared()
        tool = self.tool
        code_digest = tool.code_digest
        tool.code_digest = lambda: "not the code prepare planned the units with"
        argv = ["shard", "--out", str(self.out), "--tasks", "16", "--device", "cpu"]
        self.assertEqual(self.main_of(tool, argv + ["--task", "2"])[0], 2)
        tool.code_digest = code_digest
        tool.gpu_self_test = lambda device: (_ for _ in ()).throw(KeyError(str(self.folder)))
        with self.assertRaises(KeyError):
            self.main_of(tool, argv + ["--task", "3"])
        ends = [line for line in self.logged() if line.startswith("task ")]
        self.assertEqual(ends, ["task 2: FAILED, as its step's line in the bench report says",
                                "task 3: FAILED with KeyError, as its job's log says"])
        writers = {path.stem.split("-")[1] for path in (self.analysis / "runlog").glob("task-*.txt")}
        self.assertEqual(writers, {"0002", "0003"})
        self.assertRegex((self.out / "PROGRESS.txt").read_text(encoding="ascii").splitlines()[-1],
                         r"^log: \d\d:\d\d:\d\d task 3: FAILED with KeyError, as its job's log says$")

    def test_a_new_chain_reads_no_unit_of_the_one_before_it_as_its_own(self):
        # until a new prepare clears the events after its heads, they are the earlier chain's: a
        # prepare that Slurm ends before then leaves PROGRESS.txt and the report's run log with its
        # own lines alone, never the earlier chain's units done or their quarter marks
        record = self.prepared()
        tool, total = self.tool, len(record["units"])
        self.assertEqual(tool.shard(shard_args(self.out)), 0)
        self.assertEqual(tool.merge(merge_args(self.out, self.args.groups)), 0)
        tool.stage_features = lambda *args: (_ for _ in ()).throw(tool.Terminated())
        with self.assertRaises(tool.Terminated):
            tool.prepare(self.args)
        # Slurm's TERM in a stage is said as such, never as the stage's failure
        self.assertRegex(self.logged()[-1], r"^prepare: stage features ended by Slurm \(TERM\) after \d+ s$")
        self.assertFalse(any("FAILED" in line for line in self.logged()), self.logged())
        self.assertEqual(len([e for e in tool.events_of(tool.units_record(self.out)) if e["event"] == "done"]), total)
        newest = [line for line in (self.out / "PROGRESS.txt").read_text(encoding="ascii").splitlines() if line.startswith("log: ")]
        self.assertTrue(newest)
        self.assertTrue(all(line[14:].startswith("prepare: ") for line in newest), newest)
        code, printed = self.main_of(tool, ["runlog", "--out", str(self.out)])
        self.assertEqual(code, 0)
        self.assertTrue(all(line[20:].startswith("prepare: ") for line in printed.splitlines()), printed)
        whole = (self.out / "RUNLOG.txt").read_text(encoding="ascii").splitlines()
        self.assertFalse(any(": unit " in line for line in whole), whole)

    def test_a_retry_s_quarter_marks_count_the_units_an_earlier_chain_left_done(self):
        # the designed retry: a chain cut short, a new prepare that keeps its done units, a second
        # array that does the rest; the marks reach the whole list and each count is the list's own
        record = self.prepared()
        tool, total = self.tool, len(record["units"])
        run_unit, ran = tool.run_unit, []

        def cut_after_five(head, unit, seed=0):
            if len(ran) == 5:
                raise tool.Terminated()
            ran.append(unit["id"])
            return run_unit(head, unit, seed)

        tool.run_unit = cut_after_five
        self.assertEqual(tool.shard(shard_args(self.out)), 143)
        tool.run_unit = run_unit
        self.prepared()
        self.assertEqual(self.logged()[-1], f"prepare: {total} units listed over 3 readings (2 not read), so the array's tasks"
                                            " claim them; 5 of them an earlier chain left done, which count as done")
        self.assertEqual(tool.shard(shard_args(self.out)), 0)
        self.assertEqual(tool.merge(merge_args(self.out, self.args.groups)), 0)
        code, printed = self.main_of(tool, ["runlog", "--out", str(self.out)])
        self.assertEqual(code, 0)
        marks = [line[20:] for line in printed.splitlines() if line[20:].startswith("units: ")]
        counts = [count for count in (-(-total * share // 4) for share in (1, 2, 3, 4)) if count > 5]
        self.assertEqual(marks, [f"units: {count} of {total} done ({count / total:.0%})" for count in counts])

    def test_slurm_s_term_ends_a_step_with_143_and_says_so_in_the_run_log(self):
        # Slurm's TERM at a task's time limit or a cancel: raised where the step stands, never counted
        # as a unit's failure, said as the step's last line, the task beating terminated
        record = self.prepared()
        tool = self.tool
        tool.run_unit = lambda head, unit, seed=0: (_ for _ in ()).throw(tool.Terminated())
        self.assertEqual(tool.shard(shard_args(self.out, 3, 16)), 143)
        self.assertEqual(list((self.analysis / "failed").iterdir()), [])
        self.assertEqual(self.logged()[-1], "task 3: ended by Slurm (TERM: its time, or a cancel) with 0 done and 0 failed here")
        self.assertEqual(read(self.analysis / "tasks" / "0003.json")["state"], "terminated")
        # through the command line, a real TERM: main turns it into the step's last line and 143,
        # and puts back the handler it found
        before = signal.getsignal(signal.SIGTERM)

        def term_now(*args):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(30)
            raise AssertionError("TERM did not end the step")

        tool.claim_loop = term_now
        code, _ = self.main_of(tool, ["shard", "--out", str(self.out), "--task", "5", "--tasks", "16", "--device", "cpu"])
        self.assertEqual(code, 143)
        self.assertEqual(self.logged()[-1], "task 5: ended by Slurm (TERM: its time, or a cancel) with 0 done and 0 failed here")
        tool.open_units = term_now
        code, _ = self.main_of(tool, ["merge", "--out", str(self.out), "--wandb", "off"])
        self.assertEqual(code, 143)
        self.assertEqual(self.logged()[-1], "merge: ended by Slurm (TERM: its time, or a cancel)")
        self.assertIs(signal.getsignal(signal.SIGTERM), before)
        self.assertEqual(len(record["units"]), len(self.tool.units_record(self.out)["units"]))

    def test_a_second_term_cuts_none_of_what_the_first_one_writes(self):
        # Slurm signals every process of the step and Apptainer's starter passes its TERM on, so a
        # second comes a moment after the first: it neither cuts the task's closing line and record
        # nor lets Terminated out of main
        self.prepared()
        tool = self.tool
        write_progress, sent = tool.write_progress, []

        def second_term(*args, **kwargs):
            if not sent:
                sent.append(True)
                os.kill(os.getpid(), signal.SIGTERM)
            return write_progress(*args, **kwargs)

        def term_now(*args):
            tool.write_progress = second_term
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(30)
            raise AssertionError("TERM did not end the step")

        before = signal.getsignal(signal.SIGTERM)
        tool.claim_loop = term_now
        code, _ = self.main_of(tool, ["shard", "--out", str(self.out), "--task", "5", "--tasks", "16", "--device", "cpu"])
        self.assertEqual(code, 143)
        self.assertEqual(sent, [True])
        self.assertEqual(self.logged()[-1], "task 5: ended by Slurm (TERM: its time, or a cancel) with 0 done and 0 failed here")
        self.assertEqual(read(self.analysis / "tasks" / "0005.json")["state"], "terminated")
        self.assertIs(signal.getsignal(signal.SIGTERM), before)
        sent.clear()
        tool.write_progress = write_progress
        tool.open_units = term_now
        code, _ = self.main_of(tool, ["merge", "--out", str(self.out), "--wandb", "off"])
        self.assertEqual(code, 143)
        self.assertEqual(sent, [True])
        self.assertEqual(self.logged()[-1], "merge: ended by Slurm (TERM: its time, or a cancel)")
        self.assertIs(signal.getsignal(signal.SIGTERM), before)

    def test_a_term_once_a_step_is_ending_cuts_nothing_and_the_reason_is_its_job_log_s_last_line(self):
        # a TERM while a task writes how it finished, or while main notes a step's failure, ends
        # nothing more: the step's closing lines stand and its code is the one it was ending with
        self.prepared()
        tool = self.tool
        before = signal.getsignal(signal.SIGTERM)
        beat, claim_loop, sent = tool.Task.beat, tool.claim_loop, []

        def term_at_finish(task, claims, state="running"):
            if state == "finished" and not sent:
                sent.append(True)
                os.kill(os.getpid(), signal.SIGTERM)
            return beat(task, claims, state=state)

        tool.Task.beat, tool.claim_loop = term_at_finish, lambda *args: 0
        argv = ["shard", "--out", str(self.out), "--tasks", "16", "--device", "cpu"]
        self.assertEqual(self.main_of(tool, argv + ["--task", "4"])[0], 0)
        self.assertEqual(sent, [True])
        ends = [line for line in self.logged() if line.startswith("task 4: ")]
        self.assertEqual(ends[1:], ["task 4: finished, nothing left to claim: 0 done and 0 failed here"])
        self.assertEqual(read(self.analysis / "tasks" / "0004.json")["state"], "finished")
        tool.Task.beat, tool.claim_loop = beat, claim_loop
        # a TERM while main writes the failure's line: the line stands, the code is 2, no traceback
        runlog_note, code_digest = tool.runlog_note, tool.code_digest
        sent.clear()

        def term_on_failure(out, text, writer=None):
            if "FAILED" in text and not sent:
                sent.append(True)
                os.kill(os.getpid(), signal.SIGTERM)
            return runlog_note(out, text, writer)

        tool.runlog_note, tool.code_digest = term_on_failure, lambda: "not the code prepare planned the units with"
        code, printed = self.main_of(tool, argv + ["--task", "6"])
        self.assertEqual((code, sent), (2, [True]))
        self.assertIn("task 6: FAILED, as its step's line in the bench report says", self.logged())
        self.assertEqual(printed.splitlines()[-1], "drr-gap FAILED: the code differs from the code prepare planned the units with")
        self.assertIs(signal.getsignal(signal.SIGTERM), before)
        # where the volume takes neither the run log's line nor PROGRESS.txt, the job's log still
        # ends with the reason, which the bench report quotes as the step's last line
        tool.runlog_note = runlog_note
        blocked = self.out / "not-a-folder"
        blocked.write_text("", encoding="ascii")
        runlog_folder, own_part = tool.runlog_folder, tool.own_part
        tool.runlog_folder = lambda out: blocked / "runlog"
        tool.own_part = lambda path: blocked / "progress.part"
        code, printed = self.main_of(tool, argv + ["--task", "7"])
        self.assertEqual(code, 2)
        self.assertIn("run log not written: ", printed)
        self.assertEqual(printed.splitlines()[-1], "drr-gap FAILED: the code differs from the code prepare planned the units with")
        tool.runlog_folder, tool.own_part, tool.code_digest = runlog_folder, own_part, code_digest
        # an earlier run log prepare cannot clear ends nothing: prepare goes on and says it started
        (tool.runlog_folder(self.out) / "a-folder").mkdir()
        self.assertEqual(tool.prepare(self.args), 0)
        self.assertIn("prepare: started as job local on " + socket_name(), self.logged())

    def test_a_term_counts_the_units_running_when_it_came(self):
        # a TERM while the task waits on a unit it handed the pool names that unit as running, so
        # the done count with it says what the task left half done
        self.prepared()
        tool = self.tool
        release = threading.Event()

        def held_until_released(head, unit, seed=0):
            # writes nothing once released, so the folder is left as the TERM found it
            release.wait(30)
            raise RuntimeError("released by the test")

        tool.run_unit = held_until_released
        timer = threading.Timer(1.5, os.kill, (os.getpid(), signal.SIGTERM))
        timer.start()
        try:
            code, _ = self.main_of(tool, ["shard", "--out", str(self.out), "--task", "0", "--tasks", "1", "--device", "cpu"])
        finally:
            timer.cancel()
            release.set()
            time.sleep(0.5)
        self.assertEqual(code, 143)
        self.assertEqual(self.logged()[-1], "task 0: ended by Slurm (TERM: its time, or a cancel) with 0 done and 0 failed"
                                            " here, 1 running when it came")

    def test_a_card_with_no_room_sends_the_mmd_to_the_cpu_and_fails_no_unit(self):
        # a shard's workers share one card of whatever size the gpu class gave the task: a test the
        # card has no room for runs with numpy, whose permutations are drawn the same, so its numbers
        # are the card's but for the last digits; the unit is done, its backend says numpy, and the run
        # log says which unit went to the CPU
        record = self.prepared()
        tool = self.tool
        stats = tool.stats()
        mmd_test, tried = stats.mmd_test, []

        def card_full(*args, backend="auto", **kwargs):
            tried.append(backend)
            if backend != "numpy":
                raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
            return mmd_test(*args, backend=backend, **kwargs)

        rng = __import__("numpy").random.default_rng(0)
        x, y = rng.normal(size=(12, 3)), rng.normal(size=(12, 3)) + 0.5
        persons = [f"p{i}" for i in range(12)]
        expected = mmd_test(x, y, persons, [f"q{i}" for i in range(12)], perms=20, seed=3, backend="numpy")
        stats.mmd_test = card_full
        tool.stats = lambda: stats  # each call loads the module afresh, and the stand-in must be the one read
        try:
            tool._MMD_RUNS.update(tests=0, cpu=0)
            got = tool.mmd_where_it_fits(stats, x, y, persons, [f"q{i}" for i in range(12)], perms=20, seed=3)
            self.assertEqual(got, expected)
            self.assertEqual(tried, ["auto", "numpy"])
            tool.chosen_backend = lambda: "torch-cuda"
            self.assertEqual(tool.mmd_backend(), "numpy")
            tool._MMD_RUNS.update(tests=3)
            self.assertEqual(tool.mmd_backend(), "torch-cuda+numpy")
            tool._MMD_RUNS.update(tests=0, cpu=0)
            self.assertEqual(tool.mmd_backend(), "torch-cuda")
            self.assertEqual(tool.shard(shard_args(self.out)), 0)
        finally:
            stats.mmd_test = mmd_test
        total = len(record["units"])
        self.assertEqual(list((self.analysis / "failed").iterdir()), [])
        # a unit that runs an MMD test says numpy; one that runs none, a map's, names the backend its
        # tests would have taken, as before
        backends = [read(path)["backend"] for path in (self.analysis / "done").glob("*.json")]
        self.assertEqual(len(backends), total)
        self.assertLessEqual(set(backends), {"numpy", "torch-cuda"})
        moved = [line for line in self.logged() if line.endswith("ran its MMD on the CPU (numpy), since the card had no room left for it")]
        self.assertGreater(len(moved), 1)
        self.assertEqual(len(moved), backends.count("numpy"))
        # the report keeps their count, one line, so its room holds every failure and quarter mark
        report = [line[20:] for line in tool.run_log_lines(self.out, every_unit=False)]
        self.assertFalse(any(" ran its MMD on the CPU (" in line for line in report), report)
        folded = [line for line in report if line.startswith(f"units: {len(moved)} ran their MMD on the CPU from ")]
        self.assertEqual(len(folded), 1, report)
        self.assertTrue(folded[0].endswith(", since their cards had no room left for it"))
        # an error that is not the card's room is the unit's failure as before
        stats.mmd_test = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("CUDA error: an illegal memory access"))
        try:
            with self.assertRaises(RuntimeError):
                tool.mmd_where_it_fits(stats, x, y, persons, persons)
        finally:
            stats.mmd_test = mmd_test

    def test_one_writer_s_run_log_is_bounded_and_the_report_s_middle_is_cut(self):
        tool = self.tool
        tool.RUNLOG_FILE_LINES = 3
        for n in range(6):
            tool.runlog_note(self.out, f"task 2: line {n}", writer="task-0002-1")
        self.assertEqual([text for _, text in tool.runlog_entries(self.out)],
                         ["task 2: line 0", "task 2: line 1",
                          "task 2: this step's run log is full, so its later lines are in its job's log alone"])
        lines = [f"line {n}" for n in range(60)]
        cut = tool.cut_keeping(lines, 50)
        self.assertEqual(len(cut), 50)
        self.assertEqual(cut[:25], lines[:25])
        self.assertEqual(cut[26:], lines[-24:])
        self.assertEqual(cut[25], "... 11 lines not shown here; the run folder's RUNLOG.txt holds them")
        self.assertEqual(tool.cut_keeping(lines[:50], 50), lines[:50])
        # the report's cut keeps every quarter mark and every line of something gone wrong, wherever
        # it falls, and of the rest the first and the last
        telling = {7: "units: 1 of 64 done, the first", 30: "task 4: unit physics/fd_all FAILED after 3 s (ValueError; ...)",
                   31: "units: 16 of 64 done (25%)", 33: "task 9: took over the stale claim on unit 12, whose holder had not"
                   " beaten for 20 min", 40: "task 2: ended by Slurm (TERM: its time, or a cancel) with 3 done and 0 failed here"}
        lines = [telling.get(n, f"task {n}: started as job {n} of 16 tasks") for n in range(70)]
        cut = tool.cut_keeping(lines, 50)
        self.assertEqual(len(cut), 50)
        self.assertTrue(set(telling.values()) <= set(cut))
        self.assertEqual(cut[:7], lines[:7])
        self.assertEqual(cut[-22:], lines[-22:])
        self.assertEqual(len([line for line in cut if line.startswith("... ")]), 1)
        self.assertIn("... 21 lines not shown here; the run folder's RUNLOG.txt holds them", cut)
        self.assertEqual(tool.cut_keeping(lines[:50], 50), lines[:50])
        marks = [f"units: {n} of 60 done ({n / 60:.0%})" for n in range(1, 61)]
        self.assertEqual(tool.cut_keeping(marks, 50),
                         marks[:25] + ["... 11 lines not shown here; the run folder's RUNLOG.txt holds them"] + marks[-24:])
        # more lines of something gone wrong than the room holds: every quarter mark still, then the
        # first and the last of the failures, then none of the routine lines
        lines = ([f"task {n % 16}: unit physics/u{n} FAILED after 1 s (ValueError)" for n in range(60)]
                 + [f"units: {n} of 64 done ({n / 64:.0%})" for n in (16, 32, 48, 64)] + ["prepare: started as job 1 on node1"])
        cut = tool.cut_keeping(lines, 50)
        self.assertEqual(len(cut), 50)
        self.assertEqual(cut[-4:], lines[-5:-1])
        self.assertEqual(cut[:23], lines[:23])
        self.assertEqual(cut[23], "... 16 lines not shown here; the run folder's RUNLOG.txt holds them")
        self.assertEqual(cut[24:46], lines[38:60])
        # a line cut short before its time was whole, or one with no time, is passed over
        with open(tool.runlog_folder(self.out) / "task-0009-1.txt", "a", encoding="ascii") as stream:
            stream.write("not a time\n12")
        self.assertEqual(len(tool.runlog_entries(self.out)), 3)

    def logged(self):
        """The run log's lines so far, oldest first, without their times."""
        return [text for _, text in self.tool.runlog_entries(self.out)]

    def main_of(self, tool, argv):
        """(the exit code, what main printed) of one command line."""
        import contextlib
        import io

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = tool.main(argv)
        return code, printed.getvalue()


def socket_name():
    import socket

    return socket.gethostname()


if __name__ == "__main__":
    unittest.main()
