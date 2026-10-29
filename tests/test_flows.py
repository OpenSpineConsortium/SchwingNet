"""The pipeline's Metaflow flows and their launcher (issue #252), run for real on this machine.

Each test runs flows/launch.py with a datastore of its own under a temporary folder, as the grid
runs it under /rs/rs_grp_oschome/go2432/metaflow: BankFlow on a synthetic raw copy against the
stage it replaces, a kill mid-ingest resumed with its bank cloned, SweepFlow on a stub of
tools/block_sweep.py killed mid-row and resumed, and the two stage scripts' dispatch to the
launcher under Slurm. Metaflow is in the train feature only, so CI's python, which has none,
skips the file; run it with the train-cpu environment, as tests/test_train_resume.py is run.
"""

import base64
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
import zlib
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "grid"
LAUNCH = ROOT / "flows" / "launch.py"
NEEDED = ("metaflow", "beartype", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
TIMEOUT = 600


def png(width, height, seed):
    raw = bytes(((x * 7 + y * 3 + seed) % 256) for y in range(height) for x in range(width + 1))

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def write_raw_copies(data_root):
    """Two sources' raw copies as tests/schwingnet/test_chain_stages.py writes one: NIH's films
    by patient and follow-up, and Open-i's by case."""
    write_nih_raw(data_root)
    write_open_i_raw(data_root)


def write_nih_raw(data_root, patients=4):
    folder = data_root / "nih_chestxray14" / "raw" / "images_001" / "images"
    folder.mkdir(parents=True, exist_ok=True)
    for patient in range(1, patients + 1):
        for follow in range(2):
            (folder / f"{patient:08d}_{follow:03d}.png").write_bytes(png(48, 32, patient * 2 + follow))


def write_open_i_raw(data_root):
    folder = data_root / "open_i_chest" / "raw" / "NLMCXR_png"
    folder.mkdir(parents=True, exist_ok=True)
    for case in range(1, 4):
        for k in range(2):
            (folder / f"CXR{case}_{k + 1}_IM-{case:04d}-{k + 1:04d}.png").write_bytes(png(40, 40, case * 3 + k))


def write_banks(banks, refused=False):
    """The recipe folder the stage is given (BANKS): NIH's as shipped, Open-i's filled in where it
    still says "to confirm" (or as shipped, which the bank tool refuses), and VinDr-SpineXR's,
    whose raw copy the test never writes, so the stage reports it skipped."""
    banks.mkdir(parents=True, exist_ok=True)
    for name in ("nih_chestxray14", "vindr_spinexr"):
        shutil.copy(GRID / "banks" / f"{name}.json", banks / f"{name}.json")
    recipe = json.loads((GRID / "banks" / "open_i_chest.json").read_text(encoding="utf-8"))
    if not refused:
        recipe["view"]["lat_from_ap_deg"] = None
    (banks / "open_i_chest.json").write_text(json.dumps(recipe, indent=1), encoding="utf-8")


def base_env(**extra):
    """The environment a job gets, with no Slurm job, so the stage scripts run their bodies."""
    env = {k: v for k, v in os.environ.items() if k not in ("SLURM_JOB_ID", "SCHWINGNET_FLOW_STEP", "PART", "ONLY", "BANKS", "STORE", "DATA_ROOT", "INGEST_DATE")}
    env.update(SCHWINGNET=str(ROOT), PYDRV=sys.executable, METAFLOW_USER="flowtest")
    env.update(extra)
    return env


def load(path, name):
    """A file of the repository loaded as a module under a name of its own, with the warnings of
    what it imports left as a script has them, which unittest shows."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        spec.loader.exec_module(module)
    return module


def load_run_code():
    return load(ROOT / "tools" / "run_code.py", "run_code_under_test")


def launch(words, cwd, env, root):
    """flows/launch.py with the test's own datastore: its exit code, its JSON lines and its output."""
    done = subprocess.run([sys.executable, str(LAUNCH), words[0], "--root", str(root), *words[1:]], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=TIMEOUT)
    said = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    return done.returncode, said, done.stdout + done.stderr


def start_launch(words, cwd, env, root):
    """flows/launch.py started and left running, as a job on another node finds it."""
    return subprocess.Popen([sys.executable, str(LAUNCH), words[0], "--root", str(root), *words[1:]], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def finish(process):
    """A launch started by start_launch, waited for: its exit code, its JSON lines and its output."""
    out, _ = process.communicate(timeout=TIMEOUT)
    return process.returncode, [json.loads(line) for line in out.splitlines() if line.startswith("{")], out


def wait_for(path):
    deadline = time.monotonic() + TIMEOUT
    while not path.exists():
        if time.monotonic() > deadline:
            raise AssertionError(f"{path} never came")
        time.sleep(0.2)


def stage(name, cwd, env):
    done = subprocess.run(["bash", str(GRID / name)], cwd=cwd, env=env, capture_output=True, text=True, timeout=TIMEOUT)
    return done.returncode, done.stdout + done.stderr


def report_of(folder, name, data_root):
    """A stage report with its first line, the time it was written, left out, and the data root
    named the same whatever it was."""
    text = (folder / "logs" / name).read_text(encoding="utf-8")
    return text.split("\n", 1)[1].replace(str(data_root), "<data root>")


def gate_shows(log):
    """What the gate word status keeps of a failed job's log: the commands grid/gate.sh's printable
    and log_tail run on it, up to the awk filters, before the masking of what they keep."""
    script = ('tail -c 65536 | tr "\\r" "\\n" | LC_ALL=C tr -cd "\\11\\12\\40-\\176" | tail -n 400 '
              '| awk -f "$1/shape-words.awk" -f "$1/log-shapes.awk"')
    done = subprocess.run(["bash", "-c", script, "shapes", str(GRID)], input=log, capture_output=True, text=True, timeout=60)
    return done.stdout.splitlines()


def card_data(html):
    """What a Metaflow card shows, the base64 JSON its page embeds as window.__MF_DATA__[id]."""
    found = re.findall(r'__MF_DATA__\["[^"]+"\] = "([A-Za-z0-9+/=]+)"', html)
    return "".join(base64.b64decode(data).decode("utf-8") for data in found)


def shards_of(data_root):
    """Every file under each source's shards/, staging folders and reuse notes aside, with its
    bytes, the data root named the same wherever INGEST.json records it, and so is INGEST.json's
    reuse key (#260), which hashes the bank's listing with every file's modification time, so two
    banks of the same frames made a second apart differ in it alone."""
    found = {}
    for path in sorted(data_root.glob("*/shards/**/*")):
        relative = path.relative_to(data_root)
        if path.is_file() and not any(part.startswith(".") for part in relative.parts):
            data = path.read_bytes().replace(str(data_root).encode(), b"<data root>")
            found[str(relative)] = re.sub(rb'"reuse_key": "[0-9a-f]{64}"', b'"reuse_key": "<reuse key>"', data)
    return found


PYDRV_WRAPPER = '''#!{python}
"""PYDRV for the kill test: logs every tool call, and on the first ingest of KILL_SOURCE while
the marker is absent kills the Metaflow task running it, as Slurm ends a job, then exits."""
import os
import signal
import sys
from pathlib import Path

args = sys.argv[1:]
tool = Path(args[0]).name if args and args[0].endswith(".py") else "python"
source = args[args.index("--source") + 1] if "--source" in args else (Path(args[args.index("--recipe") + 1]).stem if "--recipe" in args else "")
with open(os.environ["FLOW_TEST_CALLS"], "a", encoding="utf-8") as calls:
    calls.write(f"{{tool}} {{source}}\\n")
marker = Path(os.environ["FLOW_TEST_MARKER"])
if tool == "ingest.py" and source == os.environ.get("FLOW_TEST_KILL") and not marker.exists():
    marker.write_text("", encoding="utf-8")
    pid = os.getppid()
    while pid > 1:
        command = Path(f"/proc/{{pid}}/cmdline").read_bytes().replace(b"\\0", b" ").decode()
        if " step ingest " in command:
            os.kill(pid, signal.SIGKILL)
            break
        pid = int(Path(f"/proc/{{pid}}/stat").read_text().rsplit(")", 1)[1].split()[1])
    sys.exit(137)
os.execv(sys.executable, [sys.executable, *args])
'''

# PYDRV for the filter test, named pydrv.py so its frames have a .py file as the tools' frames do:
# the bank tool's run on NIH's raw copy raises with a value in its message, as a tool's crash can.
CRASHING_PYDRV = '''#!{python}
import os
import sys

args = sys.argv[1:]


def read_the_frames(raw):
    raise ValueError(f"no frame under {{raw}} for person 12345678")


if args and args[0].endswith("bank.py") and "nih_chestxray14" in " ".join(args):
    read_the_frames(args[args.index("--raw") + 1])
os.execv(sys.executable, [sys.executable, *args])
'''


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_the_launcher_refuses_a_datastore_whose_parent_is_missing(self):
        code, said, out = launch(["bank", "--", "--sources", "nih_chestxray14"], self.tmp, base_env(), self.tmp / "no" / "such" / "metaflow")
        self.assertEqual(code, 69, out)
        self.assertIn("has no parent folder", out)
        self.assertEqual(said, [])
        self.assertFalse((self.tmp / "no").exists())

    def test_the_launcher_refuses_in_words_where_metaflow_cannot_be_imported(self):
        blocked = self.tmp / "blocked" / "metaflow"
        blocked.mkdir(parents=True)
        (blocked / "__init__.py").write_text("raise ImportError('not here, for the test')\n", encoding="utf-8")
        env = base_env(PYTHONPATH=str(blocked.parent))
        code, said, out = launch(["sweep", "--", "--plan", "p.json"], self.tmp, env, self.tmp / "metaflow")
        self.assertEqual(code, 69, out)
        self.assertIn("Metaflow is not in this python; the train-cpu and train-gpu environments carry it", out)
        self.assertEqual(said, [])

    def test_the_launcher_takes_a_flow_it_knows_and_leaves_the_commit_to_itself(self):
        for argv, words in ((["nothing"], "usage"), (["bank", "--max-workers", "0"], "whole number"),
                            (["bank", "--", "--commit", "abc"], "passes --commit itself")):
            done = subprocess.run([sys.executable, str(LAUNCH), *argv], cwd=self.tmp, env=base_env(), capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 64, done.stderr)
            self.assertIn(words, done.stderr)

    def test_every_refusal_ends_with_its_stages_rc_line_which_the_gates_status_keeps(self):
        # Finding [6] of the second review of #252: a refusal said its words alone, which the gate's
        # status withholds, so the log of a job that never started its flow showed nothing of how it ended
        missing = self.tmp / "no" / "such" / "metaflow"
        for argv, word, code in ((["bank", "--max-workers", "0"], "XR_BANK_RC", 64), (["sweep", "--", "--commit", "abc"], "SWEEP_RC", 64),
                                 (["catalog", "--root", str(missing)], "XR_CATALOG_RC", 69), (["nothing"], "LAUNCH_RC", 64)):
            done = subprocess.run([sys.executable, str(LAUNCH), *argv], cwd=self.tmp, env=base_env(), stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, timeout=60)
            self.assertEqual(done.returncode, code, done.stdout)
            self.assertRegex(done.stdout, r"^LaunchError: [^\n]+\n[^\n]+\n$")
            kept = gate_shows(done.stdout)
            self.assertEqual(kept[0], "LaunchError: <message withheld>", kept)
            self.assertRegex(kept[1], rf"^{word}={code} [0-9-]+ [0-9:]+$")
            self.assertEqual(kept[2:], ["#withheld 0"], kept)

    def main_listing(self, runs_with_key):
        """flows/launch.py's main run in this process, as a catalog job on an empty data root, with
        Metaflow's listing of the key's runs replaced by runs_with_key(module), whatever reaches it:
        its exit code, what it printed on stdout and what on stderr. Python's warnings are left as
        a script has them, which unittest shows."""
        module = load(LAUNCH, "launch_under_test")
        out, err = io.StringIO(), io.StringIO()
        argv = ["catalog", "--root", str(self.tmp / "metaflow"), "--", "--data-root", str(self.tmp / "data")]
        with mock.patch.dict(os.environ), mock.patch.object(module, "runs_with_key", runs_with_key(module)), \
                warnings.catch_warnings(), redirect_stdout(out), redirect_stderr(err):
            warnings.simplefilter("ignore", DeprecationWarning)
            code = module.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_a_broken_rule_of_the_decision_is_a_refusal_in_words_and_any_other_crash_a_traceback(self):
        # Finding [3] of the second review of #252: a run read as succeeded and not finished broke
        # decide's precondition, and the launch ended in icontract's traceback, its last line withheld
        code, out, err = self.main_listing(lambda module: lambda flow_class, key: [module.RunState("1792", finished=False, successful=True)])
        self.assertEqual(code, 70, err)
        self.assertRegex(err, r"^LaunchError: a rule of schwingnet.pipeline was broken, so no run was started or resumed: ")
        self.assertIn("a run that succeeded has finished", err)
        self.assertNotIn("Traceback", err)
        self.assertRegex(out, r"^XR_CATALOG_RC=70 [0-9-]+ [0-9:]+\n$")
        kept = gate_shows(err + out)
        self.assertEqual(kept[0], "LaunchError: <message withheld>", kept)
        self.assertRegex(kept[1], r"^XR_CATALOG_RC=70 [0-9-]+ [0-9:]+$")
        self.assertEqual(len(kept), 3, kept)

        def crash(flow_class, key):
            raise RuntimeError("Metaflow could not read run 12345678")

        code, out, err = self.main_listing(lambda module: crash)
        self.assertEqual(code, 1, err)
        self.assertIn("Traceback (most recent call last):", err)
        self.assertTrue(err.endswith("RuntimeError: Metaflow could not read run 12345678\n"), err)
        self.assertRegex(out, r"^XR_CATALOG_RC=1 [0-9-]+ [0-9:]+\n$")
        kept = gate_shows(err + out)
        self.assertEqual(kept[-3], "RuntimeError: <message withheld>", kept)
        self.assertRegex(kept[-2], r"^XR_CATALOG_RC=1 [0-9-]+ [0-9:]+$")


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class BankFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "metaflow"
        for name in ("flow", "direct"):
            (self.tmp / f"logs-{name}").mkdir()

    def direct(self, data_root, banks):
        """Stage 2 called straight, as before Metaflow, on its own data root: the reference."""
        write_raw_copies(data_root)
        return stage("02-bank-ingest.sbatch", self.tmp / "logs-direct",
                     base_env(DATA_ROOT=str(data_root), BANKS=str(banks), INGEST_DATE=date.today().isoformat()))

    def test_the_bank_flow_makes_the_shards_and_the_report_the_stage_makes(self):
        # two recipes with raw copies, one refused by the bank tool, one with none: the flow's
        # report, shards and exit code are the stage's, and the catalog flow builds on them
        banks = self.tmp / "banks"
        write_banks(banks, refused=True)
        code, out = self.direct(self.tmp / "direct", banks)
        self.assertEqual(code, 1, out)
        flow_root = self.tmp / "flow"
        write_raw_copies(flow_root)
        code, said, out = launch(["bank", "--", "--data-root", str(flow_root), "--banks", str(banks)], self.tmp / "logs-flow", base_env(), self.root)
        self.assertEqual(code, 1, out)
        self.assertEqual(said[0]["decision"], "run", out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 1), out)
        self.assertIn("XR_BANK_RC=1 ", out)
        name = "02-bank-ingest-STAGE-REPORT.md"
        report = report_of(self.tmp / "logs-flow", name, flow_root)
        self.assertEqual(report, report_of(self.tmp / "logs-direct", name, self.tmp / "direct"))
        self.assertIn("- nih_chestxray14: nih_chestxray14/", report)
        self.assertIn("- open_i_chest: bank refused: ", report)
        self.assertIn("- vindr_spinexr: skipped, nothing fetched under <data root>/vindr_spinexr/raw", report)
        self.assertEqual(shards_of(flow_root), shards_of(self.tmp / "direct"))
        self.assertTrue(shards_of(flow_root))

        # stage 3 on those shards through its own flow: the stage's report, lock and marker
        code, said, out = launch(["catalog", "--", "--data-root", str(flow_root)], self.tmp / "logs-flow", base_env(), self.root)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[-1]["verdict"]), ("run", 0), out)
        catalog = report_of(self.tmp / "logs-flow", "03-catalog-STAGE-REPORT.md", flow_root)
        self.assertIn("- manifests read: 1", catalog)
        self.assertIn("split-check of version 1: disjoint", catalog)
        self.assertEqual(len(list((flow_root / "_catalog" / "checked").iterdir())), 1)
        self.assertTrue((flow_root / "_catalog" / "BUILD.lock").exists())

    def test_a_failed_bank_flows_log_keeps_its_rc_line_and_traceback_through_the_gates_filter(self):
        banks = self.tmp / "banks"
        write_banks(banks)
        wrapper = self.tmp / "pydrv.py"
        wrapper.write_text(CRASHING_PYDRV.format(python=sys.executable), encoding="utf-8")
        wrapper.chmod(0o755)
        flow_root = self.tmp / "flow"
        write_raw_copies(flow_root)
        code, said, out = launch(["bank", "--", "--data-root", str(flow_root), "--banks", str(banks)], self.tmp / "logs-flow",
                                 base_env(PYDRV=str(wrapper)), self.root)
        self.assertEqual(code, 1, out)
        # every line the stage printed reached the log behind Metaflow's prefix, its indent stripped
        self.assertRegex(out, r"(?m)^[0-9-]+ [0-9:.]+ \[[0-9]+/end/[0-9]+ \(pid [0-9]+\)\] XR_BANK_RC=1 ")
        self.assertRegex(out, r'(?m)\] File "[^"]*pydrv\.py", line [0-9]+, in read_the_frames$')
        kept = gate_shows(out)
        self.assertRegex(kept[-2], r"^XR_BANK_RC=1 [0-9-]+ [0-9:]+$", kept)
        self.assertIn("Traceback (most recent call last):", kept)
        self.assertTrue(any(re.fullmatch(r'  File "[^"]*/pydrv\.py", line [0-9]+, in read_the_frames', line) for line in kept), kept)
        self.assertIn("ValueError: <message withheld>", kept)
        self.assertIn("== nih_chestxray14", kept)
        self.assertFalse(any("12345678" in line or str(flow_root) in line for line in kept), kept)

    def launch_logged(self, words, n, kill="open_i_chest"):
        """A launch through the kill test's PYDRV, which kills the task of the first ingest of
        KILL while no earlier launch of the test has killed one: its result and its tool calls."""
        wrapper = self.tmp / "pydrv"
        wrapper.write_text(PYDRV_WRAPPER.format(python=sys.executable), encoding="utf-8")
        wrapper.chmod(0o755)
        calls = self.tmp / f"calls-{n}"
        calls.write_text("", encoding="utf-8")
        env = base_env(PYDRV=str(wrapper), FLOW_TEST_CALLS=str(calls), FLOW_TEST_MARKER=str(self.tmp / "killed"), FLOW_TEST_KILL=kill)
        result = launch(words, self.tmp / "logs-flow", env, self.root)
        return (*result, calls.read_text(encoding="utf-8").splitlines())

    def test_a_kill_mid_ingest_resumes_there_with_the_banks_cloned_and_a_later_launch_runs_anew(self):
        banks = self.tmp / "banks"
        write_banks(banks)
        code, out = self.direct(self.tmp / "direct", banks)
        self.assertEqual(code, 0, out)
        flow_root = self.tmp / "flow"
        write_raw_copies(flow_root)
        words = ["bank", "--", "--data-root", str(flow_root), "--banks", str(banks)]

        def launch_logged(n):
            return self.launch_logged(words, n)

        code, said, out, calls = launch_logged(1)
        self.assertNotEqual(code, 0, out)
        self.assertEqual(said[0]["decision"], "run", out)
        self.assertEqual(said[-1]["successful"], False, out)
        first_run, first_key = said[-1]["run"].split("/")[1], said[0]["key"]
        self.assertIn("ingest.py open_i_chest", calls)
        self.assertEqual(sorted(c for c in calls if c.startswith("bank.py")), ["bank.py nih_chestxray14", "bank.py open_i_chest"])
        # the report says the run was cut short, with what it had done: NIH's line, written as NIH
        # finished, and start's skipped line, under the time the run began
        name = "02-bank-ingest-STAGE-REPORT.md"
        report = (self.tmp / "logs-flow" / "logs" / name).read_text(encoding="utf-8")
        self.assertEqual([line for line in report.splitlines() if line.startswith("- ")][0][:35], "- nih_chestxray14: nih_chestxray14/")
        self.assertEqual([line for line in report.splitlines() if line.startswith("- ")][1:],
                         [f"- vindr_spinexr: skipped, nothing fetched under {flow_root}/vindr_spinexr/raw"])
        self.assertRegex(report, r"\nNot finished as of [0-9-]+ [0-9:]+: 1 of 2 recipes with a raw copy done; ")
        self.assertNotIn("Every recipe that had a raw copy", report)

        # the same words again, the raw copies as they were and no date given, so the date the
        # launcher chose is kept out of the key: the newest run with the key did not succeed, so it
        # is resumed, both banks cloned and the cut ingest run again
        code, said, out, calls = launch_logged(2)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[0]["key"]), ("resume", first_run, first_key), out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertEqual([c for c in calls if c.startswith("bank.py")], [], calls)
        self.assertIn("ingest.py open_i_chest", calls)
        self.assertEqual(report_of(self.tmp / "logs-flow", name, flow_root), report_of(self.tmp / "logs-direct", name, self.tmp / "direct"))
        self.assertEqual(shards_of(flow_root), shards_of(self.tmp / "direct"))

        # a third launch after the success is a new run; the tools find their work already there
        code, said, out, calls = launch_logged(3)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("run", None), out)
        self.assertEqual(sorted(c for c in calls if c.split()[0] in ("bank.py", "ingest.py")),
                         ["bank.py nih_chestxray14", "bank.py open_i_chest", "ingest.py nih_chestxray14", "ingest.py open_i_chest"])
        self.assertIn("already there", (self.tmp / "logs-flow" / "logs" / name).read_text(encoding="utf-8"))
        self.assertEqual(shards_of(flow_root), shards_of(self.tmp / "direct"))

    def test_a_raw_copy_fetched_since_a_kill_starts_a_new_run_that_banks_it(self):
        banks = self.tmp / "banks"
        write_banks(banks)
        flow_root = self.tmp / "flow"
        write_nih_raw(flow_root)
        words = ["bank", "--", "--data-root", str(flow_root), "--banks", str(banks)]
        code, said, out, calls = self.launch_logged(words, 1, kill="nih_chestxray14")
        self.assertEqual(said[-1]["successful"], False, out)
        first_key = said[0]["key"]
        # cut before any recipe was done: the report start wrote, its skipped lines and no more
        report = (self.tmp / "logs-flow" / "logs" / "02-bank-ingest-STAGE-REPORT.md").read_text(encoding="utf-8")
        self.assertEqual([line for line in report.splitlines() if line.startswith("- ")],
                         [f"- open_i_chest: skipped, nothing fetched under {flow_root}/open_i_chest/raw",
                          f"- vindr_spinexr: skipped, nothing fetched under {flow_root}/vindr_spinexr/raw"])
        self.assertRegex(report, r"^# Stage 2, bank and ingest: [0-9-]+ [0-9:]+\n")
        self.assertRegex(report, r"\nNot finished as of [0-9-]+ [0-9:]+: 0 of 1 recipes with a raw copy done; ")

        # Open-i's raw copy lands before the job is queued again: the run that listed it as not
        # fetched is not resumed, so Open-i is banked and ingested and nothing says it was skipped
        write_open_i_raw(flow_root)
        code, said, out, calls = self.launch_logged(words, 2)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("run", None), out)
        self.assertNotEqual(said[0]["key"], first_key)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertIn("bank.py open_i_chest", calls)
        report = (self.tmp / "logs-flow" / "logs" / "02-bank-ingest-STAGE-REPORT.md").read_text(encoding="utf-8")
        self.assertIn("- open_i_chest: open_i_chest/", report)
        self.assertNotIn("open_i_chest: skipped", report)
        self.assertTrue(list(flow_root.glob("open_i_chest/shards/*/MANIFEST.json")))

    def test_a_raw_copy_that_grew_since_its_bank_was_made_is_banked_again_not_cloned(self):
        banks = self.tmp / "banks"
        write_banks(banks)
        flow_root = self.tmp / "flow"
        write_raw_copies(flow_root)
        words = ["bank", "--", "--data-root", str(flow_root), "--banks", str(banks)]
        code, said, out, calls = self.launch_logged(words, 1)
        self.assertEqual(said[-1]["successful"], False, out)
        self.assertIn("bank.py nih_chestxray14", calls)

        # the cut was at Open-i's ingest, NIH's bank done; NIH's raw copy then grows by a patient
        write_nih_raw(flow_root, patients=5)
        code, said, out, calls = self.launch_logged(words, 2)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("run", None), out)
        self.assertIn("bank.py nih_chestxray14", calls)
        report = (self.tmp / "logs-flow" / "logs" / "02-bank-ingest-STAGE-REPORT.md").read_text(encoding="utf-8")
        self.assertRegex(report, r"- nih_chestxray14: nih_chestxray14/[^ ]+ written 10 frames, 5 persons")

    def test_a_date_the_caller_gave_is_in_the_key_so_another_date_runs_anew(self):
        banks = self.tmp / "banks"
        write_banks(banks)
        flow_root = self.tmp / "flow"
        write_raw_copies(flow_root)
        words = ["bank", "--", "--data-root", str(flow_root), "--banks", str(banks)]
        code, said, out, calls = self.launch_logged([*words, "--date", "2026-10-01"], 1)
        self.assertEqual(said[-1]["successful"], False, out)
        first_run, first_key = said[-1]["run"].split("/")[1], said[0]["key"]

        # another date asked for is another run, so the ingest the kill cut is made under that
        # date, where a resume would have cloned the first; NIH's bank, unchanged, is answered by
        # the ingest's own reuse note (#260) with the shard already there, as the stage's would be
        code, said, out, calls = self.launch_logged([*words, "--date", "2026-10-20"], 2)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("run", None), out)
        self.assertNotEqual(said[0]["key"], first_key)
        self.assertEqual([p.parent.parent.name for p in flow_root.glob("*/shards/2026-10-20-*")], ["open_i_chest"])
        self.assertEqual([p.parent.parent.name for p in flow_root.glob("*/shards/2026-10-01-*")], ["nih_chestxray14"])
        report = (self.tmp / "logs-flow" / "logs" / "02-bank-ingest-STAGE-REPORT.md").read_text(encoding="utf-8")
        self.assertIn("ingest date 2026-10-20;", report)

        # the first date asked for again names the first key, whose cut run is resumed
        code, said, out, calls = self.launch_logged([*words, "--date", "2026-10-01"], 3)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[0]["key"]), ("resume", first_run, first_key), out)

    def test_with_no_raw_copy_the_flow_steps_past_the_foreach_to_the_report(self):
        banks = self.tmp / "banks"
        write_banks(banks)
        code, said, out = launch(["bank", "--", "--data-root", str(self.tmp / "empty"), "--banks", str(banks), "--sources", "vindr_spinexr open_i_chest"],
                                 self.tmp / "logs-flow", base_env(), self.root)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        report = (self.tmp / "logs-flow" / "logs" / "02-bank-ingest-STAGE-REPORT.md").read_text(encoding="utf-8")
        self.assertEqual([line for line in report.splitlines() if line.startswith("- ")],
                         [f"- open_i_chest: skipped, nothing fetched under {self.tmp}/empty/open_i_chest/raw",
                          f"- vindr_spinexr: skipped, nothing fetched under {self.tmp}/empty/vindr_spinexr/raw"])
        self.assertIn("Every recipe that had a raw copy was banked and ingested.", report)


STUB_BLOCK_SWEEP = '''"""A stand-in for tools/block_sweep.py's prepare, row and results, writing the files the real
commands write that SweepFlow reads, logging each call, and killing the flow once mid-row."""
import json
import os
import signal
import sys
import time
from pathlib import Path


def log(words):
    with open(os.environ["FLOW_TEST_CALLS"], "a", encoding="utf-8") as calls:
        calls.write(words + "\\n")


def value(flag):
    return sys.argv[sys.argv.index(flag) + 1]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True) + "\\n", encoding="utf-8")


def ancestor(test):
    pid = os.getppid()
    while pid > 1:
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\\0", b" ").decode()
        if test(command):
            return pid
        pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
    return None


def kill_the_job():
    """As Slurm ends a job: the flow's runtime first, so nothing retries, then the task."""
    runtime = ancestor(lambda c: "sweep.py --quiet " in c and " step " not in c)
    task = ancestor(lambda c: " step first " in c or " step second " in c)
    for pid in (runtime, task):
        if pid:
            os.kill(pid, signal.SIGKILL)
    sys.exit(137)


def hold():
    """A row that lasts until the test lets it end, as a row trains for hours, saying it holds."""
    Path(os.environ["FLOW_TEST_HELD"]).write_text("", encoding="utf-8")
    for _ in range(3000):
        if Path(os.environ["FLOW_TEST_RELEASE"]).exists():
            return
        time.sleep(0.2)


def prepare():
    plan = json.loads(Path(value("--plan")).read_text(encoding="utf-8"))
    state = Path(value("--out")) / plan["plan"] / "state"
    rows = plan["first"] + plan["second"]
    write(state / "PLAN.json", {"plan": plan["plan"], "rows": [{"slug": s} for s in rows], "epochs": 3})
    write(state / "CHECK.json", {"rows": [{"slug": s, "predicted": "runs", "code": None, "why": ""} for s in rows]})
    log("prepare")
    print(json.dumps({"state": str(state), "first": plan["first"], "second": plan["second"]}), flush=True)


def row():
    state, slug = Path(value("--state")), value("--slug")
    log(f"row {slug}")
    write(state / slug / "train" / "metrics.jsonl", {"epoch": 2, "train_loss": 0.25, "validation_accuracy": 0.75, "seconds": 3.0})
    if slug == os.environ.get("FLOW_TEST_FAULT"):
        print(f"block_sweep: row {slug}: could not record the row", file=sys.stderr)
        sys.exit(2)
    marker = Path(os.environ["FLOW_TEST_MARKER"])
    if slug == os.environ.get("FLOW_TEST_KILL") and not marker.exists():
        marker.write_text("", encoding="utf-8")
        kill_the_job()
    if slug == os.environ.get("FLOW_TEST_HOLD"):
        hold()
    entry = {"slug": slug, "outcome": "ran", "code": None, "matched": True, "predicted": "runs", "role": "cover",
             "validation_accuracy": 0.75, "test_accuracy": 0.5, "wandb": []}
    write(state / "rows" / f"{slug}.json", entry)
    print(json.dumps(entry, sort_keys=True), flush=True)


def results():
    state = Path(sys.argv[2])
    plan = json.loads((state / "PLAN.json").read_text(encoding="utf-8"))
    entries = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((state / "rows").glob("*.json"))]
    counts = {"rows": len(plan["rows"]), "ran": len(entries), "refused": 0, "not_applicable": 0, "failed": 0,
              "to_come": len(plan["rows"]) - len(entries), "mismatched": 0}
    write(state / "results.json", {"plan": plan["plan"], "state": str(state), "counts": counts, "rows": entries})
    log("results")
    print(json.dumps({"counts": counts}), flush=True)


{"prepare": prepare, "row": row, "results": results}[sys.argv[1]]()
'''


# A stand-in for tools/report.py: write leaves the three files of a report in the run folder, and
# check passes unless the row's slug is in FLOW_TEST_STALE, as a report not what the run gives fails;
# each call is logged beside the stub of block_sweep's, in <its log>.reports.
STUB_REPORT = '''"""A stand-in for tools/report.py in SweepFlowTest."""
import json
import os
import sys
from pathlib import Path

action, folder = sys.argv[1], Path(sys.argv[sys.argv.index("--run") + 1])
with open(os.environ["FLOW_TEST_CALLS"] + ".reports", "a", encoding="utf-8") as calls:
    calls.write(f"{action} {folder.name}\\n")
if action == "write":
    tally = {"met": 20, "declared": 3, "not applicable": 2, "missing": 4}
    for name, checklist in (("claim.json", "CLAIM 2024"), ("reforms.json", "REFORMS")):
        (folder / name).write_text(json.dumps({"checklist": checklist, "tally": tally}), encoding="utf-8")
    (folder / "REPORT.md").write_text("# Report\\n", encoding="utf-8")
elif folder.name in os.environ.get("FLOW_TEST_STALE", "").split():
    print(f"{folder.name}: REPORT.md not what the run gives", file=sys.stderr)
    sys.exit(1)
else:
    print(f"{folder.name}: report current")
'''
# The smoke test's PREREG as the test repository freezes it: the plans the tests run, by name.
TEST_PREREG = "# The test's design\n\nCovers: live, gone, race, smoke, merged, faulty, nothing, reported\n"


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class SweepFlowTest(unittest.TestCase):
    """SweepFlow over a stub of block_sweep in a temporary copy of the repository's flow, so the
    graph, the resume and the faults are tested without a GPU and in seconds."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        (self.repo / "flows").mkdir(parents=True)
        (self.repo / "tools").mkdir()
        for name in ("sweep.py", "stage.py", "stage_progress.py", "stage_registry.py", "registry.txt"):
            shutil.copy(ROOT / "flows" / name, self.repo / "flows" / name)
        (self.repo / "tools" / "block_sweep.py").write_text(STUB_BLOCK_SWEEP, encoding="utf-8")
        (self.repo / "tools" / "report.py").write_text(STUB_REPORT, encoding="utf-8")
        prereg = self.repo / "docs" / "research" / "block-smoke"
        prereg.mkdir(parents=True)
        (prereg / "PREREG.md").write_text(TEST_PREREG, encoding="utf-8")
        (prereg / "PREREG.md.sha256").write_text(f"{hashlib.sha256(TEST_PREREG.encode()).hexdigest()}  PREREG.md\n", encoding="ascii")
        # The launcher names the run by the code the sweep runs (tools/run_code.py), so every file
        # of that list is here, the two above and a line of stand-in for each of the rest.
        shutil.copy(ROOT / "tools" / "run_code.py", self.repo / "tools" / "run_code.py")
        for name in load_run_code().KINDS["sweep"]:
            path = self.repo / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {name}, a stand-in\n", encoding="utf-8")
        subprocess.run(self.git("init", "-q"), check=True, capture_output=True, timeout=60)
        self.commit("the stub")
        self.root, self.out, self.work = self.tmp / "metaflow", self.tmp / "smoke", self.tmp / "work"
        self.work.mkdir()

    def git(self, *words):
        return ["git", "-C", str(self.repo), "-c", "user.name=flow test", "-c", "user.email=flow@test", "-c", "commit.gpgsign=false",
                "-c", "gc.auto=0", "-c", "gc.autoDetach=false", "-c", "maintenance.auto=false", "-c", "maintenance.autoDetach=false", *words]

    def commit(self, message):
        for words in (["add", "-A"], ["commit", "-q", "-m", message]):
            subprocess.run(self.git(*words), check=True, capture_output=True, timeout=60)

    def sweep_launch(self, plan, n, **extra):
        """The words and the environment of a launch of a plan whose rows the stub runs, and the
        call log of its own the stub writes."""
        plan_file = self.tmp / f"{plan['plan']}.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        calls = self.tmp / f"calls-{plan['plan']}-{n}"
        calls.write_text("", encoding="utf-8")
        env = base_env(SCHWINGNET=str(self.repo), FLOW_TEST_CALLS=str(calls), FLOW_TEST_MARKER=str(self.tmp / "killed"), **extra)
        words = ["sweep", "--", "--plan", str(plan_file), "--catalog", str(self.tmp / "catalog.sqlite"), "--out", str(self.out),
                 "--environment", "train-cpu"]
        return words, env, calls

    def sweep(self, plan, n, **extra):
        """One launch of a plan whose rows the stub runs, with its own call log."""
        words, env, calls = self.sweep_launch(plan, n, **extra)
        result = launch(words, self.work, env, self.root)
        return (*result, calls.read_text(encoding="utf-8").splitlines())

    def test_a_second_launch_never_resumes_a_live_run_and_clones_none_of_its_rows(self):
        plan = {"plan": "live", "first": ["a", "b", "c"], "second": ["d"]}
        held, release = self.tmp / "held", self.tmp / "release"
        words, env, _ = self.sweep_launch(plan, 1, FLOW_TEST_HOLD="c", FLOW_TEST_HELD=str(held), FLOW_TEST_RELEASE=str(release))
        first = start_launch(words, self.work, env, self.root)
        self.addCleanup(first.kill)
        self.addCleanup(release.touch)
        wait_for(held)

        # the first run is live, rows a and b done and c training: a second launch of the same
        # words starts a run of its own, as a resume would clone a and b from a run still going
        code, said, out, calls = self.sweep(plan, 2)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("run", None), out)
        self.assertEqual(calls, ["prepare", "row a", "row b", "row c", "row d", "results"])
        release.touch()
        code, first_said, first_out = finish(first)
        self.assertEqual((code, first_said[-1]["successful"]), (0, True), first_out)
        self.assertEqual(said[0]["live"], first_said[-1]["run"].split("/")[1], out)

    def test_a_beat_left_by_a_launcher_that_is_gone_keeps_no_run_from_being_resumed(self):
        plan = {"plan": "gone", "first": ["a", "b"], "second": []}
        code, said, out, calls = self.sweep(plan, 1, FLOW_TEST_KILL="b")
        self.assertEqual(code, 137, out)
        first_run, key = said[-1]["run"].split("/")[1], said[0]["key"]
        beats = self.root / "launches" / "SweepFlow" / key
        self.assertEqual(list(beats.glob("*.json")), [], "the launcher took its beat away as its flow ended")

        # beats a killed job could leave: one on this host by a process that is gone, one of this
        # very Slurm job before Slurm queued it again, and one from another node too long ago
        gone = subprocess.Popen(["true"])
        gone.wait()
        now = time.time()
        records = {"here": {"host": socket.gethostname(), "pid": gone.pid, "slurm_job": "", "beat": now},
                   "requeued": {"host": "node7", "pid": 4, "slurm_job": "4242", "beat": now},
                   "old": {"host": "node8", "pid": 5, "slurm_job": "4243", "beat": now - 3600}}
        beats.mkdir(parents=True, exist_ok=True)
        for name, record in records.items():
            (beats / f"{name}.json").write_text(json.dumps({**record, "key": key, "run": first_run}), encoding="utf-8")
        code, said, out, calls = self.sweep(plan, 2, SLURM_JOB_ID="4242")
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[0].get("live")), ("resume", first_run, None), out)
        self.assertEqual(calls, ["row b", "results"])

    def test_a_fresh_beat_naming_a_run_the_listing_lacks_keeps_the_newest_from_being_resumed(self):
        plan = {"plan": "race", "first": ["a", "b"], "second": []}
        code, said, out, calls = self.sweep(plan, 1, FLOW_TEST_KILL="b")
        self.assertEqual(code, 137, out)
        first_run, key = said[-1]["run"].split("/")[1], said[0]["key"]

        # a launch on another node that began resuming the cut run after this one listed the
        # runs and before it read the beats: its beat names a run this listing lacks
        beats = self.root / "launches" / "SweepFlow" / key
        beats.mkdir(parents=True, exist_ok=True)
        record = {"key": key, "run": "9" + first_run, "host": "node9", "pid": 6, "slurm_job": "4244", "beat": time.time()}
        (beats / "node9-6.json").write_text(json.dumps(record), encoding="utf-8")
        code, said, out, calls = self.sweep(plan, 2)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[0]["live"]), ("run", None, first_run), out)
        self.assertEqual(calls, ["prepare", "row a", "row b", "results"])

    def test_a_sweep_killed_mid_row_resumes_that_row_and_the_warm_starts_alone(self):
        plan = {"plan": "smoke", "first": ["a", "b", "c"], "second": ["d"]}
        code, said, out, calls = self.sweep(plan, 1, FLOW_TEST_KILL="c")
        self.assertEqual(code, 137, out)
        self.assertEqual(said[0]["decision"], "run", out)
        self.assertEqual(said[-1]["successful"], False, out)
        first_run = said[-1]["run"].split("/")[1]
        self.assertEqual(calls, ["prepare", "row a", "row b", "row c"])

        code, said, out, calls = self.sweep(plan, 2, FLOW_TEST_KILL="c")
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("resume", first_run), out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        # start and the rows that finished were cloned: only the cut row, the warm start and the results ran
        self.assertEqual(calls, ["row c", "row d", "results"])
        state = self.out / "smoke" / "state"
        record = json.loads((state / "METAFLOW.json").read_text(encoding="utf-8"))
        page = str(self.root / "progress" / "SweepFlow" / said[-1]["run"].split("/")[1] / "index.html")
        self.assertEqual(record, {"flow": "SweepFlow", "run": said[-1]["run"], "root": str(self.root), "page": page})
        cards = sorted(p.name for p in (state / "cards").iterdir())
        self.assertEqual(cards, ["first-a.html", "first-b.html", "first-c.html", "second-d.html"], out)
        # the row's card shows the last epoch line it read, a cloned row's from the run that made it
        for name in ("first-a.html", "second-d.html"):
            shown = card_data((state / "cards" / name).read_text(encoding="utf-8"))
            self.assertIn("validation accuracy 0.75", shown, name)
            self.assertIn("Outcome: ran, matched the check.", shown, name)

    def test_a_merge_that_changes_nothing_the_sweep_runs_carries_the_cut_run_on_and_one_that_does_not(self):
        # Finding 27 of #252: main merges many times a day, most merges change nothing a sweep
        # runs, and a key with the commit in it started every cut sweep over after one.
        plan = {"plan": "merged", "first": ["a", "b"], "second": []}
        code, said, out, _ = self.sweep(plan, 1, FLOW_TEST_KILL="b")
        self.assertEqual(code, 137, out)
        first_run, first_key = said[-1]["run"].split("/")[1], said[0]["key"]
        self.assertEqual(said[0]["code"], load_run_code().digest("sweep", self.repo), out)
        (self.repo / "docs").mkdir(exist_ok=True)
        (self.repo / "docs" / "note.md").write_text("a page no sweep runs\n", encoding="utf-8")
        self.commit("a merge that changes nothing the sweep runs")
        code, said, out, calls = self.sweep(plan, 2)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[0]["key"]), ("resume", first_run, first_key), out)
        self.assertEqual(calls, ["row b", "results"])

        (self.tmp / "killed").unlink()
        code, said, out, _ = self.sweep(plan, 3, FLOW_TEST_KILL="b")
        self.assertEqual((code, said[0]["decision"]), (137, "run"), out)
        with (self.repo / "tools" / "train.py").open("a", encoding="utf-8") as trainer:
            trainer.write("# the trainer, changed\n")
        self.commit("a change to the trainer, which every row runs")
        code, said, out, calls = self.sweep(plan, 4)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("run", None), out)
        self.assertNotEqual(said[0]["key"], first_key)
        self.assertEqual(calls, ["prepare", "row a", "row b", "results"])

        # an edited plan is no plan the cut run was making: its bytes are in the key too
        (self.tmp / "killed").unlink()
        code, said, out, _ = self.sweep(plan, 5, FLOW_TEST_KILL="b")
        self.assertEqual(code, 137, out)
        code, said, out, calls = self.sweep({**plan, "about": "edited"}, 6)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("run", None), out)
        self.assertEqual(calls, ["prepare", "row a", "row b", "results"])

    def test_a_row_that_cannot_be_recorded_is_retried_once_then_caught_and_the_rest_still_run(self):
        code, said, out, calls = self.sweep({"plan": "faulty", "first": ["bad", "ok"], "second": []}, 1, FLOW_TEST_FAULT="bad")
        self.assertEqual(code, 1, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 1), out)
        self.assertEqual((calls[0], calls[-1], sorted(calls[1:-1])), ("prepare", "results", ["row bad", "row bad", "row ok"]), calls)
        self.assertIn("SweepFlow: FAULT in row bad: ", out)
        self.assertIn("could not record the row", out)

        # a plan with nothing to run steps past both foreach steps to the results
        code, said, out, calls = self.sweep({"plan": "nothing", "first": [], "second": []}, 1)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertEqual(calls, ["prepare", "results"])

    def progress_of(self, said):
        folder = self.root / "progress" / "SweepFlow" / said[-1]["run"].split("/")[1]
        return folder, (folder / "PROGRESS.txt").read_text(encoding="utf-8").splitlines()

    def test_a_sweep_ends_with_every_rows_report_checked_its_verdict_and_its_page(self):
        # the owner's rule of 2026-10-29: the run is held to the frozen PREREG, every row that ran has
        # its CLAIM and REFORMS report checked in end, and the run's page shows each step and the verdict
        code, said, out, calls = self.sweep({"plan": "reported", "first": ["a", "b"], "second": ["c"]}, 1)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        reports = (self.tmp / "calls-reported-1.reports").read_text(encoding="utf-8").split("\n")
        self.assertEqual(sorted(filter(None, reports)), ["check a", "check b", "check c", "write a", "write b", "write c"])
        folder, lines = self.progress_of(said)
        self.assertRegex(lines[0], rf"^flow SweepFlow/{said[-1]['run'].split('/')[1]} sweep: succeeded, started ")
        self.assertRegex(lines[1], r"PREREG docs/research/block-smoke/PREREG\.md sha256 [0-9a-f]{12}$")
        self.assertIn("step first: done; 2 done of 2", lines)
        self.assertIn("task first a: done; Outcome: ran, matched the check.", lines)
        self.assertIn("step end: done", lines)
        self.assertIn("report: a: current; CLAIM 2024: 20 met, 3 declared, 2 not applicable, 4 missing; "
                      "REFORMS: 20 met, 3 declared, 2 not applicable, 4 missing", lines)
        self.assertEqual(lines[-2:], ["verdict: 0", "ended: the launcher exited 0, the flow succeeded"])
        self.assertIn("SweepFlow", (folder / "index.html").read_text(encoding="utf-8"))
        self.assertIn(f'href="SweepFlow/{folder.name}/index.html"', (self.root / "progress" / "index.html").read_text(encoding="utf-8"))
        read = subprocess.run([sys.executable, "-c", (
            "import json, sys; from metaflow import Run, namespace; namespace(None); r = Run(sys.argv[1]); "
            "print(json.dumps([r.data.prereg_path, r.data.reports]))"), said[-1]["run"]], cwd=self.root,
            env=base_env(METAFLOW_DATASTORE_SYSROOT_LOCAL=str(self.root), METAFLOW_DEFAULT_DATASTORE="local",
                         METAFLOW_DEFAULT_METADATA="local"), capture_output=True, text=True, timeout=120)
        self.assertEqual(read.returncode, 0, read.stderr)
        prereg_path, reports = json.loads(read.stdout.splitlines()[-1])
        self.assertEqual(prereg_path, "docs/research/block-smoke/PREREG.md")
        self.assertEqual(len(reports), 3)

    def test_a_row_whose_report_is_not_current_makes_the_verdict_1_whatever_the_row_did(self):
        code, said, out, calls = self.sweep({"plan": "reported", "first": ["a", "b"], "second": []}, 1, FLOW_TEST_STALE="b")
        self.assertEqual(code, 1, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 1), out)
        _, lines = self.progress_of(said)
        self.assertIn("report: b: NOT CURRENT, why: b: REPORT.md not what the run gives", lines)
        self.assertIn("verdict: 1", lines)
        self.assertRegex(lines[0], r" sweep: failed, started ")

    def test_a_plan_the_frozen_prereg_does_not_cover_or_a_moved_prereg_starts_nothing(self):
        code, said, out, calls = self.sweep({"plan": "trials", "first": ["a"], "second": []}, 1)
        self.assertEqual(code, 90, out)
        self.assertIn("covers live, gone, race, smoke, merged, faulty, nothing, reported, not trials", out)
        self.assertEqual((said, calls), ([], []), out)
        self.assertFalse((self.root / "progress").exists())
        with (self.repo / "docs" / "research" / "block-smoke" / "PREREG.md").open("a", encoding="utf-8") as prereg:
            prereg.write("An edit after the freeze.\n")
        self.commit("an edit to the PREREG after its freeze")
        code, said, out, calls = self.sweep({"plan": "smoke", "first": ["a"], "second": []}, 2)
        self.assertEqual(code, 90, out)
        self.assertIn("STOP: docs/research/block-smoke/PREREG.md changed since the freeze", out)
        self.assertEqual((said, calls), ([], []), out)


# A failed stage 2 job's log under the launcher, in the shape Metaflow 2.19.39 gave it (measured
# 2026-10-25): every line a task printed behind "<date> <time> [<run>/<step>/<task> (pid N)] " and
# stripped of its own leading blanks, so a traceback's frames and source lines lost their indent.
FLOW_LOG = """{"decision": "run", "flow": "bank", "key": "68974c7ccabf5595", "origin": null, "root": "/rs/x/metaflow"}
2026-10-25 04:29:45.289 Workflow starting (run-id 1792902585286456):
2026-10-25 04:29:46.714 [1792902585286456/bank/3 (pid 21494)] Task is starting.
2026-10-25 04:29:47.553 [1792902585286456/bank/3 (pid 21494)] XR_BANK start 2026-10-25 04:29:47 on node12 job 4242 commit f16efe8
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)] == nih_chestxray14: 2026-10-25 04:29:47
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)] Traceback (most recent call last):
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)] File "/home/u/SchwingNet/tools/bank.py", line 761, in main
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)] counts = run_once(recipe, raw, bank, args.workers)
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)] ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)] File "/home/u/SchwingNet/tools/bank.py", line 512, in keys_of
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)] ValueError: no frame under /rs/data/nih/raw/00012345 for person 12345678
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)] - nih_chestxray14: bank refused: ValueError: no frame for person 12345678
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)]
2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)]\x20
2026-10-25 04:29:49.051 [1792902585286456/bank/3 (pid 21494)] - x: 2026-10-25 04:29:49.050 [1792902585286456/bank/3 (pid 21494)] XR_BANK_RC=0 2026-10-25 04:29:58
2026-10-25 04:29:59.472 [1792902585286456/end/8 (pid 25629)] XR_BANK_RC=1 2026-10-25 04:29:58
2026-10-25 04:29:59.474 Done!
{"flow": "bank", "run": "BankFlow/1792902585286456", "successful": true, "verdict": 1}
2026-10-25 05:00:01.002 [1792902599999999/catalog/2 (pid 7)] XR_CATALOG start 2026-10-25 05:00:01 on node12 job 4243
2026-10-25 05:00:01.010 [1792902599999999/catalog/2 (pid 7)] XR_CATALOG lock 2026-10-25 05:00:01
2026-10-25 05:00:09.010 [1792902599999999/catalog/2 (pid 7)] XR_CATALOG_RC=1 2026-10-25 05:00:09
Traceback (most recent call last):
  File "/home/u/SchwingNet/flows/launch.py", line 256, in <module>
    sys.exit(main())
"""


class GateFilterTest(unittest.TestCase):
    """grid/log-shapes.awk on a flow's log, as the gate word status runs it (#252); plain bash and
    awk, so it runs wherever the other tests do."""

    def test_the_filter_reads_a_flows_lines_behind_metaflows_prefix_and_no_more(self):
        kept = gate_shows(FLOW_LOG)
        self.assertEqual(kept[:-1], [
            "XR_BANK start 2026-10-25 04:29:47 on node12 job 4242",
            "== nih_chestxray14",
            "Traceback (most recent call last):",
            '  File "/home/u/SchwingNet/tools/bank.py", line 761, in main',
            "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^",
            '  File "/home/u/SchwingNet/tools/bank.py", line 512, in keys_of',
            "ValueError: <message withheld>",
            "XR_BANK_RC=1 2026-10-25 04:29:58",
            "XR_CATALOG start 2026-10-25 05:00:01 on node12 job 4243",
            "XR_CATALOG lock 2026-10-25 05:00:01",
            "XR_CATALOG_RC=1 2026-10-25 05:00:09",
            "Traceback (most recent call last):",
            '  File "/home/u/SchwingNet/flows/launch.py", line 256, in <module>',
            "    sys.exit(main())",
        ])
        # the source line under the prefix lost its indent, so nothing tells it from any other line
        # the task printed, and it is withheld with the rest; a prefix's text inside a line is no prefix
        self.assertEqual(kept[-1], "#withheld 8")
        self.assertFalse(any("12345678" in line or "run_once" in line for line in kept), kept)


# PYDRV for the two-launcher test: a build logs how many manifests it was given, and the first
# holds stage 3's build lock until the release file is there, as a long build does.
CATALOG_PYDRV = """#!/bin/bash
[ "$2" = split-check ] && { echo '{"disjoint": true}'; exit 0; }
[ "$2" = build ] || exit 0
printf '%s\\n' "$@" | grep -c -- '^--manifest$' >> "$FLOW_TEST_BUILDS"
if [ "$(wc -l < "$FLOW_TEST_BUILDS")" -eq 1 ]; then
  : > "$FLOW_TEST_HELD"
  for _ in $(seq 3000); do [ -e "$FLOW_TEST_RELEASE" ] && break; sleep 0.2; done
fi
echo '{"file": "catalog-000001-0123456789ab.sqlite", "new": true, "version": 1}'
"""

# The flow tests' sitecustomize, put first on PYTHONPATH, so every python a launch starts imports it
# as it begins: it acts once, where FLOW_TEST_HOOK says, and makes FLOW_TEST_MARKER as it does.
FLOW_HOOK = '''"""A launch's processes as the grid can cut them, once, where FLOW_TEST_HOOK says.

persist: the flow's runtime exits 137 as Metaflow is about to save the run's parameters, a kill
landing after Metaflow registered the run and before it saved them. end: the end step's task kills
the runtime and itself as it begins, as Slurm ends a job, every step before it done. pause: the
launcher says it has listed the runs, then waits for the test's word before it reads the beats.
"""
import os
import signal
import sys
import time
from pathlib import Path

WHERE = os.environ.get("FLOW_TEST_HOOK", "")
MARKER = Path(os.environ.get("FLOW_TEST_MARKER") or "/nonexistent/marker")
SCRIPT = sys.argv[0] if sys.argv else ""
WORDS = " ".join(sys.argv)


def once():
    """Whether the hook acts now: only while its marker is not there, which it then makes."""
    if MARKER.exists():
        return False
    MARKER.write_text("", encoding="utf-8")
    return True


def ancestor(test):
    pid = os.getppid()
    while pid > 1:
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\\0", b" ").decode()
        if test(command):
            return pid
        pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
    return None


def exit_as_the_parameters_are_saved():
    from metaflow import runtime

    saved = runtime.NativeRuntime.persist_constants

    def persist_constants(self, task_id=None):
        if once():
            os._exit(137)
        return saved(self, task_id)

    runtime.NativeRuntime.persist_constants = persist_constants


def kill_the_job():
    if once():
        flow = ancestor(lambda command: SCRIPT in command and " step " not in command)
        if flow:
            os.kill(flow, signal.SIGKILL)
        os._exit(137)


def pause_before_the_beats():
    def profile(frame, event, arg):
        if event == "call" and frame.f_code.co_name == "read_beats" and once():
            sys.setprofile(None)
            Path(os.environ["FLOW_TEST_LISTED"]).write_text("", encoding="utf-8")
            while not Path(os.environ["FLOW_TEST_GO"]).exists():
                time.sleep(0.1)

    sys.setprofile(profile)


in_a_flow = "/flows/" in SCRIPT and not SCRIPT.endswith("/launch.py")
if WHERE == "persist" and in_a_flow and " step " not in WORDS:
    exit_as_the_parameters_are_saved()
elif WHERE == "end" and in_a_flow and " step end " in WORDS:
    kill_the_job()
elif WHERE == "pause" and SCRIPT.endswith("/flows/launch.py"):
    pause_before_the_beats()
'''


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class CatalogFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root, self.work, self.data = self.tmp / "metaflow", self.tmp / "work", self.tmp / "data"
        self.work.mkdir()
        self.builds, self.held, self.release = self.tmp / "builds", self.tmp / "held", self.tmp / "release"
        self.words = ["catalog", "--", "--data-root", str(self.data)]

    def shard(self, name):
        folder = self.data / "carmlspine" / "shards" / name
        folder.mkdir(parents=True)
        (folder / "MANIFEST.json").write_text("{}\n", encoding="utf-8")

    def builder(self, **extra):
        """The environment of a launch whose builds CATALOG_PYDRV logs, the first held until the
        release file is there."""
        pydrv = self.tmp / "pydrv"
        pydrv.write_text(CATALOG_PYDRV, encoding="utf-8")
        pydrv.chmod(0o755)
        return base_env(PYDRV=str(pydrv), FLOW_TEST_BUILDS=str(self.builds), FLOW_TEST_HELD=str(self.held),
                        FLOW_TEST_RELEASE=str(self.release), BUILD_LOCK_WAIT="600", TMPDIR_OVERRIDE=str(self.tmp / "t"), **extra)

    def hooked(self, where, **extra):
        """The builder's environment with FLOW_HOOK imported by every python the launch starts."""
        hooks = self.tmp / "hooks"
        hooks.mkdir(exist_ok=True)
        (hooks / "sitecustomize.py").write_text(FLOW_HOOK, encoding="utf-8")
        path = os.pathsep.join(part for part in (str(hooks), os.environ.get("PYTHONPATH", "")) if part)
        return self.builder(PYTHONPATH=path, FLOW_TEST_HOOK=where, FLOW_TEST_MARKER=str(self.tmp / f"{where}-done"), **extra)

    def built(self):
        """How many manifests each build was given, in order."""
        return self.builds.read_text(encoding="utf-8").split() if self.builds.exists() else []

    def test_a_second_catalog_job_never_resumes_a_live_build_and_waits_on_its_lock(self):
        self.shard("a")
        env = self.builder()
        first = start_launch(self.words, self.work, env, self.root)
        self.addCleanup(first.kill)
        self.addCleanup(self.release.touch)
        wait_for(self.held)

        # the first build still holds the lock: a second job of the same words on the same shards
        # starts a run of its own, which waits on the lock and then builds, where a resume of the
        # live run would carry its build on
        second = start_launch(self.words, self.work, env, self.root)
        self.addCleanup(second.kill)
        decision = json.loads(second.stdout.readline())
        self.assertEqual((decision["decision"], decision["origin"]), ("run", None), decision)
        self.release.touch()
        code, first_said, first_out = finish(first)
        self.assertEqual((code, first_said[-1]["verdict"]), (0, 0), first_out)
        code, said, out = finish(second)
        self.assertEqual((code, said[-1]["verdict"]), (0, 0), out)
        self.assertEqual(decision["live"], first_said[-1]["run"].split("/")[1])
        self.assertEqual(self.built(), ["1", "1"])

    def test_a_run_killed_before_metaflow_saved_its_parameters_is_never_resumed(self):
        # Finding [1] of the second review of #252: Metaflow registers a run, its key tag with it,
        # before it saves the run's parameters, and refuses to resume a run that has none, after it
        # has registered the resume as one more run of the key with none; resumed, such a run made
        # every later job of the same words fail before any step
        self.shard("a")
        self.release.touch()
        code, said, cut_log = finish(start_launch(self.words, self.work, self.hooked("persist"), self.root))
        self.assertEqual(code, 137, cut_log)
        self.assertEqual((said[0]["decision"], said[-1]["successful"]), ("run", False), cut_log)
        self.assertTrue(said[-1]["run"], cut_log)

        code, said, log = finish(start_launch(self.words, self.work, self.hooked("persist"), self.root))
        self.assertEqual(code, 0, log)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[-1]["verdict"]), ("run", None, 0), log)
        self.assertEqual(self.built(), ["1"])
        # the cut job's log, which held no line the gate's status keeps, ends with the launcher's own
        self.assertRegex(gate_shows(cut_log)[-2], r"^XR_CATALOG_RC=137 [0-9-]+ [0-9:]+$", cut_log)

    def test_a_build_cut_in_end_is_carried_on_only_while_no_shard_has_landed(self):
        # Finding [2] of the second review of #252: a run cut after its build, resumed, clones the
        # build, so the manifests the build read are in the key
        self.shard("a")
        self.release.touch()
        code, said, log = finish(start_launch(self.words, self.work, self.hooked("end"), self.root))
        self.assertEqual((code, said[-1]["successful"]), (137, False), log)
        self.assertEqual(self.built(), ["1"])

        # a shard lands before the job is sent again: the cut build lacks it, so a run of its own builds both
        self.shard("b")
        code, said, log = finish(start_launch(self.words, self.work, self.builder(), self.root))
        self.assertEqual(code, 0, log)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[-1]["verdict"]), ("run", None, 0), log)
        self.assertEqual(self.built(), ["1", "2"])

        # cut after its build again, and sent again with nothing new on the data root: the cut run
        # is carried on, its build cloned
        (self.tmp / "end-done").unlink()
        code, said, log = finish(start_launch(self.words, self.work, self.hooked("end"), self.root))
        self.assertEqual((code, said[0]["decision"]), (137, "run"), log)
        cut = said[-1]["run"].split("/")[1]
        code, said, log = finish(start_launch(self.words, self.work, self.builder(), self.root))
        self.assertEqual(code, 0, log)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[-1]["verdict"]), ("resume", cut, 0), log)
        self.assertEqual(self.built(), ["1", "2", "2"])

    def test_a_success_read_between_the_end_tasks_two_flags_starts_a_new_run(self):
        # Finding [3] of the second review of #252: Metaflow writes the end task's ok and success as
        # two files, one after the other, so a read between them saw a run that succeeded and had
        # not finished, which broke decide's precondition and ended the launch in a traceback; that
        # moment is made here by taking the ok's file away from a run that succeeded
        self.shard("a")
        self.release.touch()
        code, said, log = finish(start_launch(self.words, self.work, self.builder(), self.root))
        self.assertEqual(code, 0, log)
        done = said[-1]["run"].split("/")[1]
        flags = list((self.root / ".metaflow" / "CatalogFlow" / done / "end").glob("*/_meta/*_artifact__task_ok.json"))
        self.assertEqual(len(flags), 1, flags)
        flags[0].unlink()
        code, said, log = finish(start_launch(self.words, self.work, self.builder(), self.root))
        self.assertEqual(code, 0, log)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("run", None), log)

    def test_the_key_reads_every_manifest_the_stage_builds_from_and_no_other(self):
        # Finding [2] of the second review of #252: the key names the manifests by the stage's own
        # listing, at the one depth, through no link and in no dot folder, each by its path, size and
        # sha256, a name the build cannot read among them
        data_root = self.tmp / "volume" / "shards" / "data"
        for folder in ("carmlspine/shards/a", "carmlspine/shards/.ingest-a-x1y2", ".staging/shards/b", "carmlspine/.reuse/k1",
                       "lumos/shards/c", "lumos/shards/c/deeper", "elsewhere/shards/d"):
            (data_root / folder).mkdir(parents=True)
            (data_root / folder / "MANIFEST.json").write_text(json.dumps({"shard": folder}) + "\n", encoding="utf-8")
        (data_root / "linked").symlink_to(data_root / "elsewhere")
        (data_root / "lumos" / "shards" / "e").symlink_to(data_root / "carmlspine" / "shards" / "a")
        (data_root / "lumos" / "shards" / "f").mkdir()
        (data_root / "lumos" / "shards" / "f" / "MANIFEST.json").symlink_to(self.tmp / "nowhere.json")
        builds = self.tmp / "builds"
        pydrv = self.tmp / "build-pydrv"
        pydrv.write_text('#!/bin/bash\n[ "$2" = build ] && printf "%s\\n" "$@" >> "$FLOW_TEST_BUILDS"\nexit 0\n', encoding="utf-8")
        pydrv.chmod(0o755)
        env = base_env(PYDRV=str(pydrv), FLOW_TEST_BUILDS=str(builds), DATA_ROOT=str(data_root), TMPDIR_OVERRIDE=str(self.tmp / "t"),
                       BUILD_LOCK_WAIT="10")
        stage("03-catalog.sbatch", self.work, env)
        args = builds.read_text(encoding="utf-8").splitlines()
        built = sorted(str(Path(args[at + 1]).relative_to(data_root)) for at, word in enumerate(args) if word == "--manifest")
        self.assertEqual(built, ["carmlspine/shards/a/MANIFEST.json", "elsewhere/shards/d/MANIFEST.json",
                                 "lumos/shards/c/MANIFEST.json", "lumos/shards/f/MANIFEST.json"])

        flow = load(ROOT / "flows" / "catalog.py", "catalog_flow_under_test")
        reads = flow.key_reads(["--data-root", str(data_root)], self.work)
        self.assertEqual(sorted(line.split()[0] for line in reads), built)
        manifest = data_root / "carmlspine" / "shards" / "a" / "MANIFEST.json"
        data = manifest.read_bytes()
        self.assertIn(f"carmlspine/shards/a/MANIFEST.json {len(data)} {hashlib.sha256(data).hexdigest()}", reads)
        self.assertIn("lumos/shards/f/MANIFEST.json unreadable", reads)
        # a relative data root is read from the launcher's folder, and a rewritten manifest is another read
        self.assertEqual(flow.key_reads(["--data-root=../volume/shards/data"], self.work), reads)
        manifest.write_text(json.dumps({"shard": "carmlspine/shards/a", "frames": 2}) + "\n", encoding="utf-8")
        self.assertNotEqual(flow.key_reads(["--data-root", str(data_root)], self.work), reads)

    def test_a_run_that_ended_well_after_the_listing_is_read_again_and_not_resumed(self):
        # Finding [3] of the second review of #252: a second job lists the first's run while it
        # builds, the first ends well and its launcher takes its beat away, and the second then reads
        # no beat for it; it reads the run again before it resumes it, where it cloned the first's build
        self.shard("a")
        first = start_launch(self.words, self.work, self.builder(), self.root)
        self.addCleanup(first.kill)
        self.addCleanup(self.release.touch)
        wait_for(self.held)
        listed, go = self.tmp / "listed", self.tmp / "go"
        second = start_launch(self.words, self.work, self.hooked("pause", FLOW_TEST_LISTED=str(listed), FLOW_TEST_GO=str(go)), self.root)
        self.addCleanup(second.kill)
        self.addCleanup(go.touch)
        wait_for(listed)
        self.release.touch()
        code, first_said, first_out = finish(first)
        self.assertEqual((code, first_said[-1]["successful"]), (0, True), first_out)
        go.touch()
        code, said, log = finish(second)
        self.assertEqual(code, 0, log)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[0]["live"]), ("run", None, None), log)
        self.assertEqual(self.built(), ["1", "1"])


# Logs a call of the launcher only; the stage's own small reads of a recipe print nothing.
FAKE_PYDRV = '''#!/bin/bash
case "$1" in */flows/launch.py) printf '%s\\n' "$@" > "$FLOW_TEST_ARGS" ;; esac
'''


class StageDispatchTest(unittest.TestCase):
    """grid/02-bank-ingest.sbatch and grid/03-catalog.sbatch exec the launcher in a Slurm job and
    run their bodies otherwise; plain bash, so it runs wherever the other tests do."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.pydrv = self.tmp / "pydrv"
        self.pydrv.write_text(FAKE_PYDRV, encoding="utf-8")
        self.pydrv.chmod(0o755)
        self.args = self.tmp / "args"
        (self.tmp / "banks").mkdir()
        (self.tmp / "data").mkdir()
        shutil.copy(GRID / "banks" / "vindr_spinexr.json", self.tmp / "banks" / "vindr_spinexr.json")

    def run_stage(self, name, **extra):
        self.args.unlink(missing_ok=True)
        env = base_env(PYDRV=str(self.pydrv), FLOW_TEST_ARGS=str(self.args), TMPDIR_OVERRIDE=str(self.tmp / "t"), **extra)
        code, out = stage(name, self.tmp, env)
        return code, out, self.args.read_text(encoding="utf-8").splitlines() if self.args.exists() else None

    def test_stage_2_execs_the_launcher_with_what_the_caller_gave_in_a_slurm_job(self):
        code, out, args = self.run_stage("02-bank-ingest.sbatch", SLURM_JOB_ID="4242", ONLY="nih_chestxray14 lumos", DATA_ROOT="/d",
                                         BANKS="/b", INGEST_DATE="2026-10-24")
        self.assertEqual(code, 0, out)
        self.assertEqual(args, [str(ROOT / "flows" / "launch.py"), "bank", "--max-workers", "1", "--", "--sources", "nih_chestxray14 lumos",
                                "--data-root", "/d", "--banks", "/b", "--date", "2026-10-24"])
        self.assertEqual(out, "")
        code, out, args = self.run_stage("02-bank-ingest.sbatch", SLURM_JOB_ID="4242")
        self.assertEqual(args, [str(ROOT / "flows" / "launch.py"), "bank", "--max-workers", "1", "--"])

    def test_stage_2_runs_its_body_outside_slurm_and_as_a_flow_step(self):
        for extra in ({}, {"SLURM_JOB_ID": "4242", "SCHWINGNET_FLOW_STEP": "1"}):
            code, out, args = self.run_stage("02-bank-ingest.sbatch", BANKS=str(self.tmp / "banks"), DATA_ROOT=str(self.tmp / "data"), **extra)
            self.assertEqual(code, 0, out)
            self.assertIsNone(args, extra)
            self.assertIn("XR_BANK_RC=0 ", out)
            report = (self.tmp / "logs" / "02-bank-ingest-STAGE-REPORT.md").read_text(encoding="utf-8")
            self.assertIn(f"- vindr_spinexr: skipped, nothing fetched under {self.tmp}/data/vindr_spinexr/raw", report)
        code, out, args = self.run_stage("02-bank-ingest.sbatch", BANKS=str(self.tmp / "banks"), PART="both")
        self.assertEqual(code, 2, out)
        self.assertIn("PART is bank, ingest or unset for both, not both; nothing ran", out)

    def test_stage_3_execs_the_launcher_in_a_slurm_job_and_runs_its_body_otherwise(self):
        code, out, args = self.run_stage("03-catalog.sbatch", SLURM_JOB_ID="4242", DATA_ROOT="/d", STORE="/s")
        self.assertEqual(code, 0, out)
        self.assertEqual(args, [str(ROOT / "flows" / "launch.py"), "catalog", "--max-workers", "1", "--", "--data-root", "/d", "--store", "/s"])
        code, out, args = self.run_stage("03-catalog.sbatch", SLURM_JOB_ID="4242")
        self.assertEqual(args, [str(ROOT / "flows" / "launch.py"), "catalog", "--max-workers", "1", "--"])
        for extra in ({}, {"SLURM_JOB_ID": "4242", "SCHWINGNET_FLOW_STEP": "1"}):
            code, out, args = self.run_stage("03-catalog.sbatch", DATA_ROOT=str(self.tmp / "data"), BUILD_LOCK_WAIT="10", **extra)
            self.assertEqual(code, 1, out)
            self.assertIsNone(args, extra)
            self.assertIn("no MANIFEST.json under", out)
            self.assertIn("XR_CATALOG_RC=1 ", out)

    def test_stage_3_lists_no_dot_folder_even_under_a_data_root_inside_a_shards_folder(self):
        # a shard being staged (shards/.ingest-*), ingest's reuse notes beside shards/ (#260) and a
        # dot source folder are never built from, wherever the data root lies
        data_root = self.tmp / "volume" / "shards" / "data"
        for folder in ("carmlspine/shards/a", "carmlspine/shards/.ingest-a-x1y2", ".staging/shards/b", "carmlspine/.reuse/k1"):
            (data_root / folder).mkdir(parents=True)
            (data_root / folder / "MANIFEST.json").write_text("{}\n", encoding="utf-8")
        builds = self.tmp / "builds"
        pydrv = self.tmp / "build-pydrv"
        pydrv.write_text('#!/bin/bash\n[ "$2" = build ] || exit 0\necho "$*" >> "$FLOW_TEST_BUILDS"\n'
                         'echo \'{"file": "catalog-000001-0123456789ab.sqlite", "new": true, "version": 1}\'\n', encoding="utf-8")
        pydrv.chmod(0o755)
        env = base_env(PYDRV=str(pydrv), FLOW_TEST_BUILDS=str(builds), DATA_ROOT=str(data_root), TMPDIR_OVERRIDE=str(self.tmp / "t"),
                       BUILD_LOCK_WAIT="10", SCHWINGNET=str(ROOT))
        code, out = stage("03-catalog.sbatch", self.tmp, env)
        self.assertEqual(code, 0, out)
        build = builds.read_text(encoding="utf-8")
        self.assertEqual(build.count("--manifest "), 1, build)
        self.assertIn(f"--manifest {data_root}/carmlspine/shards/a/MANIFEST.json", build)
        self.assertIn("- manifests read: 1", out)


# A stand-in for the body of grid/drr-gap.sbatch and of grid/drr-seg.sbatch, run by the flows' working
# steps: what each part leaves that its flow reads, each call logged with the words and the Slurm
# variables that reached it through the launcher, Metaflow and the step, and the flow killed once
# mid-part, as Slurm ends a job, where FLOW_TEST_KILL names the part.
STUB_STUDY_BODY = """\"\"\"A stand-in for the job scripts' bodies in DrrGapFlowTest and DrrSegFlowTest.\"\"\"
import json
import os
import signal
import sys
from pathlib import Path

env = os.environ


def ancestor(test):
    pid = os.getppid()
    while pid > 1:
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\\0", b" ").decode()
        if test(command):
            return pid
        pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
    return None


def kill_the_job(flow, step):
    runtime = ancestor(lambda c: f"{flow} --quiet " in c and " step " not in c)
    task = ancestor(lambda c: f" step {step} " in c)
    for pid in (runtime, task):
        if pid:
            os.kill(pid, signal.SIGKILL)
    sys.exit(137)


part = env.get("STEP", "segment")
words = [part, f"task={env.get('DRR_GAP_TASK', '-')}", f"tasks={env.get('DRR_GAP_TASK_COUNT') or env.get('SHARD_TASKS') or '-'}",
         f"prepare={env.get('PREPARE_JOB', '-')}", f"job={env.get('SLURM_JOB_ID', '-')}",
         f"array={env.get('SLURM_ARRAY_JOB_ID', '-')}_{env.get('SLURM_ARRAY_TASK_ID', '-')}",
         f"step={env.get('SCHWINGNET_FLOW_STEP', '-')}", f"checkout={env.get('SN_CHECKOUT', '-')}"]
with open(env["FLOW_TEST_CALLS"], "a", encoding="utf-8") as calls:
    calls.write(" ".join(words) + "\\n")
if part == "segment":
    masks = Path(env["FLOW_TEST_MASKS"])
    masks.mkdir(parents=True, exist_ok=True)
    (masks / "SEGMENT.json").write_text(json.dumps({"plan": {"to_run": 2}, "done": [{"id": "s0001"}]}), encoding="utf-8")
else:
    out = Path(env["DRR_GAP_OUT"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "PROGRESS.txt").write_text(f"{part}: 3 of 4 units\\n", encoding="utf-8")
marker = Path(env["FLOW_TEST_MARKER"])
if part == env.get("FLOW_TEST_KILL") and not marker.exists():
    marker.write_text("", encoding="utf-8")
    kill_the_job("drr_seg.py" if part == "segment" else "drr_gap.py", "segment" if part == "segment" else "work")
code = int(env.get("FLOW_TEST_RC", "0"))
if part == "merge" and code == 0:
    record = Path(env["SN_STUDY_RECORD"])
    record.mkdir(parents=True, exist_ok=True)
    (record / "BENCH.md").write_text("# bench flexray_drr_gap: job 4242 on node1, commit 0123456, 2026-10-29 12:00:00 UTC\\n"
                                     "- exit 0 at 2026-10-29 13:00:00 UTC\\n", encoding="utf-8")
    (record / "summary.txt").write_text("study drr-domain-gap; the stand-in's summary\\n", encoding="utf-8")
print(f"- {part}: exit {code}", flush=True)
sys.exit(code)
"""
# tools/report.py's study mode as the stand-in gives it: a recorded run of the study is a folder with
# BENCH.md and summary.txt and no RUN.json, read only under --study, its report rendered from those
# two files, so the merge's run is tested on the study's own terms whatever the training stand-in
# above asks of a run folder.
STUB_STUDY_REPORT = '''"""A stand-in for tools/report.py's study mode in DrrGapFlowTest."""
import hashlib
import json
import os
import sys
from pathlib import Path

action, folder = sys.argv[1], Path(sys.argv[sys.argv.index("--run") + 1])
study = sys.argv[sys.argv.index("--study") + 1] if "--study" in sys.argv else None
with open(os.environ["FLOW_TEST_CALLS"] + ".reports", "a", encoding="utf-8") as calls:
    calls.write(f"{action} {folder.name} {study}\\n")
if study != "drr-domain-gap":
    print(f"report: {folder}: no RUN.json, so this is not a run folder", file=sys.stderr)
    sys.exit(1)
for name in ("BENCH.md", "summary.txt"):
    if not (folder / name).is_file():
        print(f"report: {folder}: no {name}, so this is not a recorded {study} run", file=sys.stderr)
        sys.exit(1)
digest = hashlib.sha256((folder / "BENCH.md").read_bytes() + (folder / "summary.txt").read_bytes()).hexdigest()
tally = {"met": 18, "declared": 4, "not applicable": 5, "missing": 2}
rendered = {"REPORT.md": f"# The report of the study run whose record is {digest}\\n"}
for name, checklist in (("claim.json", "CLAIM 2024"), ("reforms.json", "REFORMS")):
    rendered[name] = json.dumps({"study": study, "checklist": checklist, "record_sha256": digest, "tally": tally}) + "\\n"
if action == "write":
    for name, text in rendered.items():
        (folder / name).write_text(text, encoding="utf-8")
    sys.exit(0)
held = {name: (folder / name).read_text(encoding="utf-8") if (folder / name).is_file() else "" for name in rendered}
stale = [name for name, text in rendered.items() if held[name] != text]
if stale or folder.name in os.environ.get("FLOW_TEST_STALE", "").split():
    print(f"{folder}: {', '.join(stale) or 'REPORT.md'} not what the record gives", file=sys.stderr)
    sys.exit(1)
print(f"{folder}: report current")
'''
# The job scripts as the flows' steps run them: the body alone, the stand-in above. Their drivers,
# which start the launcher, are tests/test_gate.py's to test, and the registry's check reads the
# launcher's line here.
STUB_STUDY_SCRIPT = """#!/bin/bash
# Its driver starts flows/launch.py {kind}; the test runs the body alone.
exec "$FLOW_TEST_PYTHON" "$(dirname "$0")/../tools/study_body_stub.py"
"""
# The study's PREREG as the test repository freezes it, with no Covers line, as the study's has none.
STUDY_PREREG = "# The test's study\n\nOne design for every part.\n"


def drr_code_paths():
    """What the study's prepare copies at its commit, as grid/drr-gap.sbatch lists it in CODE_PATHS."""
    listed = re.search(r"^CODE_PATHS=\((.*?)\)$", (GRID / "drr-gap.sbatch").read_text(encoding="utf-8"), re.M | re.S)
    return listed.group(1).split()


class StudyRepository:
    """A scratch repository holding the two flows as they are, the stand-ins above, the real
    tools/run_code.py with a stand-in for every other file the two kinds name, and a frozen PREREG;
    and the copy the study's prepare makes of it, as git archive and its COPY.txt."""

    def __init__(self, tmp):
        self.tmp, self.repo = tmp, tmp / "repo"
        for name in ("drr_gap.py", "drr_seg.py", "stage.py", "stage_progress.py", "stage_registry.py", "registry.txt"):
            self.write(f"flows/{name}", (ROOT / "flows" / name).read_text(encoding="utf-8"))
        self.write("tools/run_code.py", (ROOT / "tools" / "run_code.py").read_text(encoding="utf-8"))
        self.write("tools/report.py", STUB_STUDY_REPORT)
        self.write("tools/study_body_stub.py", STUB_STUDY_BODY)
        for kind, script in (("drr_gap", "drr-gap.sbatch"), ("drr_seg", "drr-seg.sbatch")):
            self.write(f"grid/{script}", STUB_STUDY_SCRIPT.format(kind=kind))
        self.write("docs/research/drr-domain-gap/PREREG.md", STUDY_PREREG)
        self.write("docs/research/drr-domain-gap/PREREG.md.sha256", f"{hashlib.sha256(STUDY_PREREG.encode()).hexdigest()}  PREREG.md\n")
        code = load_run_code()
        for name in [*code.KINDS["drr_gap"], *code.KINDS["drr_seg"], *drr_code_paths()]:
            folder = name.endswith("/") or (ROOT / name).is_dir()
            path = self.repo / name / "one.json" if folder else self.repo / name
            if not path.exists() and not (folder and (self.repo / name).is_dir()):
                self.write(path.relative_to(self.repo).as_posix(), f"# {name}, a stand-in\n")
        subprocess.run(self.git("init", "-q"), check=True, capture_output=True, timeout=60)
        self.commit("the study's stand-ins")

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def git(self, *words):
        return ["git", "-C", str(self.repo), "-c", "user.name=flow test", "-c", "user.email=flow@test", "-c", "commit.gpgsign=false",
                "-c", "gc.auto=0", "-c", "gc.autoDetach=false", "-c", "maintenance.auto=false", "-c", "maintenance.autoDetach=false", *words]

    def commit(self, message):
        for words in (["add", "-A"], ["commit", "-q", "-m", message]):
            subprocess.run(self.git(*words), check=True, capture_output=True, timeout=60)
        return subprocess.run(self.git("rev-parse", "HEAD"), check=True, capture_output=True, text=True, timeout=60).stdout.strip()

    def copy(self):
        """The copy prepare makes at the commit: git archive of CODE_PATHS, with COPY.txt naming the
        commit and the files, and no .git."""
        commit = subprocess.run(self.git("rev-parse", "HEAD"), check=True, capture_output=True, text=True, timeout=60).stdout.strip()
        code = self.tmp / f"code-{commit[:7]}"
        code.mkdir()
        archive = subprocess.run(self.git("archive", commit, "--", *drr_code_paths()), check=True, capture_output=True, timeout=60)
        subprocess.run(["tar", "-x", "-C", str(code)], input=archive.stdout, check=True, timeout=60)
        listed = subprocess.run(self.git("-c", "core.quotePath=false", "ls-tree", "-r", "--name-only", commit, "--", *drr_code_paths()),
                                check=True, capture_output=True, text=True, timeout=60).stdout
        (code / "COPY.txt").write_text(f"{commit}\n{listed}", encoding="utf-8")
        return code, commit


def page_lines(root, flow, said):
    """The run's PROGRESS.txt, as the gate's status shows it."""
    folder = root / "progress" / flow / said[-1]["run"].split("/")[1]
    return (folder / "PROGRESS.txt").read_text(encoding="utf-8").splitlines()


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class DrrGapFlowTest(unittest.TestCase):
    """DrrGapFlow started by the launcher from the copy of the code the study's prepare makes, its
    parts' bodies stand-ins, so the copy's naming of the run, each part, the merge's report, a shard
    cut and resumed and a moved PREREG are tested without a GPU and in seconds."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.study = StudyRepository(self.tmp)
        self.code, self.commit = self.study.copy()
        self.root, self.out, self.work = self.tmp / "metaflow", self.tmp / "bench" / "flexray_drr_gap", self.tmp / "work"
        self.work.mkdir()
        self.calls = self.tmp / "calls"

    def part(self, part, *words, **extra):
        """One launch of a part from the copy: its exit code, its JSON lines, its output and the
        stand-in's calls it made."""
        self.calls.write_text("", encoding="utf-8")
        env = base_env(SCHWINGNET=str(self.code), SN_CHECKOUT=str(self.study.repo), FLOW_TEST_CALLS=str(self.calls),
                       FLOW_TEST_MARKER=str(self.tmp / "killed"), FLOW_TEST_PYTHON=sys.executable, **extra)
        args = ["drr_gap", "--max-workers", "1", "--", "--part", part, "--prepare-job", "4242", "--out", str(self.out), *words]
        result = launch(args, self.work, env, self.root)
        return (*result, self.calls.read_text(encoding="utf-8").splitlines())

    def test_each_part_runs_from_the_copy_and_the_merge_writes_and_checks_the_studys_report(self):
        code, said, out, calls = self.part("prepare", SLURM_JOB_ID="4242")
        self.assertEqual(code, 0, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        # the copy holds no .git: the launcher names the run's commit and code from its COPY.txt, the
        # code's digest the one the checkout gives at that commit
        self.assertFalse((self.code / ".git").exists())
        self.assertEqual(said[0]["code"], load_run_code().digest("drr_gap", self.study.repo), out)
        self.assertEqual(calls, [f"prepare task=- tasks=- prepare=4242 job=4242 array=-_- step=1 checkout={self.study.repo}"])
        lines = page_lines(self.root, "DrrGapFlow", said)
        self.assertRegex(lines[0], r"^flow DrrGapFlow/\d+ drr_gap: succeeded, ")
        self.assertIn(f"commit {self.commit[:7]}", lines[1])
        self.assertRegex(lines[1], r"PREREG docs/research/drr-domain-gap/PREREG\.md sha256 [0-9a-f]{12}$")
        self.assertTrue(any(line.startswith("task work ") and line.endswith("prepare: exit 0") for line in lines), lines)
        self.assertTrue(any("the study's CLAIM and REFORMS report is the merge's" in line for line in lines) or
                        any(line.startswith("report: prepare: exit 0") for line in lines), lines)
        self.assertFalse((self.out / "runs").exists(), "a part other than the merge leaves no record")

        # a shard's task and the array's count reach its body, and the Slurm variables with them
        code, said, out, calls = self.part("shard", "--task", "1", "--tasks", "2", SLURM_JOB_ID="4244", SLURM_ARRAY_JOB_ID="4243",
                                           SLURM_ARRAY_TASK_ID="1")
        self.assertEqual(code, 0, out)
        self.assertEqual(calls, [f"shard task=1 tasks=2 prepare=4242 job=4244 array=4243_1 step=1 checkout={self.study.repo}"])

        code, said, out, calls = self.part("merge", "--tasks", "2", SLURM_JOB_ID="4246")
        self.assertEqual(code, 0, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertEqual(calls, [f"merge task=- tasks=2 prepare=4242 job=4246 array=-_- step=1 checkout={self.study.repo}"])
        record = self.out / "runs" / "4242"
        # the record is written and checked as a recorded run of the study, under --study
        reports = (self.tmp / "calls.reports").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sorted(reports), ["check 4242 drr-domain-gap", "write 4242 drr-domain-gap"])
        self.assertTrue((record / "claim.json").is_file())
        note = json.loads((record / "METAFLOW.json").read_text(encoding="utf-8"))
        self.assertEqual((note["flow"], note["run"], note["root"]), ("DrrGapFlow", said[-1]["run"], str(self.root)))
        lines = page_lines(self.root, "DrrGapFlow", said)
        self.assertTrue(any(re.match(r"report: 4242: current", line) for line in lines), lines)
        self.assertIn("verdict: 0", lines)

    def test_a_shard_cut_mid_work_is_resumed_by_the_same_words_and_runs_its_body_again(self):
        code, said, out, calls = self.part("shard", "--task", "0", "--tasks", "2", FLOW_TEST_KILL="shard")
        self.assertEqual(code, 137, out)
        self.assertEqual(said[-1]["successful"], False, out)
        first = said[-1]["run"].split("/")[1]
        self.assertEqual(len(calls), 1, calls)

        # the job sent again with the same words carries the cut run on, its start cloned and the
        # shard's body run again, which goes on from the claims the cut run left
        code, said, out, calls = self.part("shard", "--task", "0", "--tasks", "2", FLOW_TEST_KILL="shard")
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("resume", first), out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertEqual(len(calls), 1, calls)
        self.assertTrue(calls[0].startswith("shard task=0 tasks=2 "), calls)

        # another task of the array is another run, never a resume of this one
        code, said, out, calls = self.part("shard", "--task", "1", "--tasks", "2")
        self.assertEqual((code, said[0]["decision"], said[0]["origin"]), (0, "run", None), out)

    def test_a_merge_whose_study_report_is_not_current_ends_with_verdict_1(self):
        code, said, out, calls = self.part("merge", "--tasks", "2", FLOW_TEST_STALE="4242")
        self.assertEqual(code, 1, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 1), out)
        lines = page_lines(self.root, "DrrGapFlow", said)
        self.assertTrue(any(line.startswith("report: 4242: NOT CURRENT") for line in lines), lines)
        self.assertIn("verdict: 1", lines)
        self.assertRegex(lines[0], r" drr_gap: failed, ")
        self.assertIn("DRR_GAP_RC=1 ", out)

    def test_a_part_whose_body_failed_ends_with_verdict_1_and_no_report(self):
        code, said, out, calls = self.part("merge", "--tasks", "2", FLOW_TEST_RC="3")
        self.assertEqual(code, 1, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 1), out)
        self.assertFalse((self.tmp / "calls.reports").exists(), "a merge that did not end 0 has no record to report")
        self.assertIn("DrrGapFlow: merge: exit 3, as its line under analysis/steps/ says; verdict 1", out)

    def test_a_copy_whose_prereg_moved_starts_no_part(self):
        with (self.code / "docs" / "research" / "drr-domain-gap" / "PREREG.md").open("a", encoding="utf-8") as prereg:
            prereg.write("An edit after the freeze.\n")
        code, said, out, calls = self.part("prepare")
        self.assertEqual(code, 90, out)
        self.assertIn("STOP: docs/research/drr-domain-gap/PREREG.md changed since the freeze", out)
        self.assertEqual((said, calls), ([], []), out)
        self.assertIn("DRR_GAP_RC=90 ", out)


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class DrrSegFlowTest(unittest.TestCase):
    """DrrSegFlow started by the launcher from the checkout, its body a stand-in."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.study = StudyRepository(self.tmp)
        self.root, self.work, self.masks = self.tmp / "metaflow", self.tmp / "work", self.tmp / "data" / "moose"
        self.work.mkdir()
        self.calls = self.tmp / "calls"

    def segment(self, **extra):
        self.calls.write_text("", encoding="utf-8")
        env = base_env(SCHWINGNET=str(self.study.repo), FLOW_TEST_CALLS=str(self.calls), FLOW_TEST_MARKER=str(self.tmp / "killed"),
                       FLOW_TEST_PYTHON=sys.executable, FLOW_TEST_MASKS=str(self.masks), **extra)
        args = ["drr_seg", "--max-workers", "1", "--", "--out", str(self.tmp / "bench" / "flexray_drr_seg"), "--masks", str(self.masks)]
        result = launch(args, self.work, env, self.root)
        return (*result, self.calls.read_text(encoding="utf-8").splitlines())

    def test_a_cut_segmentation_is_resumed_and_a_failed_one_ends_with_verdict_1(self):
        code, said, out, calls = self.segment(FLOW_TEST_KILL="segment", SLURM_JOB_ID="4250")
        self.assertEqual(code, 137, out)
        first = said[-1]["run"].split("/")[1]
        self.assertEqual(calls, ["segment task=- tasks=- prepare=- job=4250 array=-_- step=1 checkout=-"])
        code, said, out, calls = self.segment(FLOW_TEST_KILL="segment")
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"]), ("resume", first), out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertEqual(said[0]["code"], load_run_code().digest("drr_seg", self.study.repo), out)
        lines = page_lines(self.root, "DrrSegFlow", said)
        self.assertRegex(lines[1], r"PREREG docs/research/drr-domain-gap/PREREG\.md sha256 [0-9a-f]{12}$")
        self.assertTrue(any(line.startswith("task segment ") and line.endswith("segment: exit 0") for line in lines), lines)
        self.assertIn("DRR_SEG_RC=0 ", out)

        code, said, out, calls = self.segment(FLOW_TEST_RC="2")
        self.assertEqual((code, said[0]["decision"]), (1, "run"), out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 1), out)
        self.assertIn("DrrSegFlow: segment: exit 2;", out)


if __name__ == "__main__":
    unittest.main()
