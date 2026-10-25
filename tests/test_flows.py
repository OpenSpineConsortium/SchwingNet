"""The pipeline's Metaflow flows and their launcher (issue #252), run for real on this machine.

Each test runs flows/launch.py with a datastore of its own under a temporary folder, as the grid
runs it under /rs/rs_grp_oschome/go2432/metaflow: BankFlow on a synthetic raw copy against the
stage it replaces, a kill mid-ingest resumed with its bank cloned, SweepFlow on a stub of
tools/block_sweep.py killed mid-row and resumed, and the two stage scripts' dispatch to the
launcher under Slurm. Metaflow is in the train feature only, so CI's python, which has none,
skips the file; run it with the train-cpu environment, as tests/test_train_resume.py is run.
"""

import base64
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from datetime import date
from pathlib import Path

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
    folder = data_root / "nih_chestxray14" / "raw" / "images_001" / "images"
    folder.mkdir(parents=True, exist_ok=True)
    for patient in range(1, 5):
        for follow in range(2):
            (folder / f"{patient:08d}_{follow:03d}.png").write_bytes(png(48, 32, patient * 2 + follow))
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


def launch(words, cwd, env, root):
    """flows/launch.py with the test's own datastore: its exit code, its JSON lines and its output."""
    done = subprocess.run([sys.executable, str(LAUNCH), words[0], "--root", str(root), *words[1:]], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=TIMEOUT)
    said = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    return done.returncode, said, done.stdout + done.stderr


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

        # the same words again, the raw copies as they were and no date given, so the date the
        # launcher chose is kept out of the key: the newest run with the key did not succeed, so it
        # is resumed, both banks cloned and the cut ingest run again
        code, said, out, calls = launch_logged(2)
        self.assertEqual(code, 0, out)
        self.assertEqual((said[0]["decision"], said[0]["origin"], said[0]["key"]), ("resume", first_run, first_key), out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertEqual([c for c in calls if c.startswith("bank.py")], [], calls)
        self.assertIn("ingest.py open_i_chest", calls)
        name = "02-bank-ingest-STAGE-REPORT.md"
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
        shutil.copy(ROOT / "flows" / "sweep.py", self.repo / "flows" / "sweep.py")
        (self.repo / "tools" / "block_sweep.py").write_text(STUB_BLOCK_SWEEP, encoding="utf-8")
        git = ["git", "-C", str(self.repo), "-c", "user.name=flow test", "-c", "user.email=flow@test", "-c", "commit.gpgsign=false",
               "-c", "gc.auto=0", "-c", "maintenance.auto=false"]
        for args in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "the stub"]):
            subprocess.run(git + args, check=True, capture_output=True, timeout=60)
        self.root, self.out, self.work = self.tmp / "metaflow", self.tmp / "smoke", self.tmp / "work"
        self.work.mkdir()

    def sweep(self, plan, n, **extra):
        """One launch of a plan whose rows the stub runs, with its own call log."""
        plan_file = self.tmp / f"{plan['plan']}.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        calls = self.tmp / f"calls-{plan['plan']}-{n}"
        calls.write_text("", encoding="utf-8")
        env = base_env(SCHWINGNET=str(self.repo), FLOW_TEST_CALLS=str(calls), FLOW_TEST_MARKER=str(self.tmp / "killed"), **extra)
        words = ["sweep", "--", "--plan", str(plan_file), "--catalog", str(self.tmp / "catalog.sqlite"), "--out", str(self.out),
                 "--environment", "train-cpu"]
        result = launch(words, self.work, env, self.root)
        return (*result, calls.read_text(encoding="utf-8").splitlines())

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
        self.assertEqual(record, {"flow": "SweepFlow", "run": said[-1]["run"], "root": str(self.root)})
        cards = sorted(p.name for p in (state / "cards").iterdir())
        self.assertEqual(cards, ["first-a.html", "first-b.html", "first-c.html", "second-d.html"], out)
        # the row's card shows the last epoch line it read, a cloned row's from the run that made it
        for name in ("first-a.html", "second-d.html"):
            shown = card_data((state / "cards" / name).read_text(encoding="utf-8"))
            self.assertIn("validation accuracy 0.75", shown, name)
            self.assertIn("Outcome: ran, matched the check.", shown, name)

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


if __name__ == "__main__":
    unittest.main()
