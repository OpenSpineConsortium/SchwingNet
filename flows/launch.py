"""Start or resume one of the pipeline's Metaflow flows: the one way a flow starts on the grid.

Usage:
    python flows/launch.py {bank|catalog|sweep} [--max-workers N] [--root DIR] -- <flow parameters>

The grid ends jobs from outside, a Slurm time limit or a preemption killing the whole job, and
the gate word that queued it queues it again. Metaflow carries a run that did not finish on with
`resume --origin-run-id`, cloning every step and every branch of a foreach that finished and
running only the rest, but it must be told which run. So every job of a pipeline stage starts
here: the launch is named by a key, the hash of the flow, the commit, the flow's parameters as
given and, for bank, every recipe it lists with its raw folder's state (reads_of), since resume
clones steps made from inputs the words do not name (schwingnet.pipeline.run_key); every run
carries the key as a tag, and the newest run with that key decides (schwingnet.pipeline.decide):
one that did not succeed is resumed, else a new run starts. A job queued again with the same
words therefore continues where the killed one stopped, and a change of code, of configuration
or of a raw copy starts afresh. Bank's --date is in the key when the caller gave it, so a job
asking for another date runs anew under it; where the words name none, the launcher chooses
today for a new run, after the key is taken, and resume keeps it with the other parameters, so
the same words on another day still continue the cut run.

A run still running is never resumed, since a resume clones what it has done so far, a build
made before the shards that landed since among them: while its flow lasts the launcher keeps a
heartbeat, <root>/launches/<Flow>/<key>/<host>-<pid>.json, rewritten every minute and naming the
run once Metaflow has, with the host, the process and the Slurm job, and takes it away when the
flow ends. A newest run whose launcher's beat is fresh is live (schwingnet.pipeline.marked_live),
and a launch of the same key then starts a run of its own beside it, as two jobs of a stage ran
before Metaflow, the stage's own locks, catalog's BUILD.lock among them, ordering what may not
overlap. A beat left by a launcher killed with its job counts no
more once it is LIVE_SECONDS old, at once where it names this very Slurm job, which Slurm queued
again, and at once where it names a process on this host that is gone.

The first line on stdout is the decision, as JSON, flushed before the flow starts, with "live"
the id of a newest run passed over as live; the last says which run it was and how it ended; the exit code is the flow's own where it failed, else
the end step's verdict (0 all well, 1 otherwise), so a job's afterok means what it meant before.

The datastore is local, on the lab volume: --root, else $SCHWINGNET_METAFLOW, else
/rs/rs_grp_oschome/go2432/metaflow. The flow runs with that folder as its working directory:
Metaflow 2.19.39 writes a task's card under the .metaflow folder it finds by walking up from the
working directory, while its card reader looks under the datastore root the task's metadata
names, so a flow started anywhere else writes cards nobody can read (measured, flows/README.md).
The folder the launcher was started in reaches the flow as SCHWINGNET_WORKDIR: the stages write
their reports under it, as they did before Metaflow, and a relative path among the parameters
is read from it.
"""

import importlib.util
import json
import math
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor" / "beethoven-qa" / "src"))

from schwingnet.pipeline import RESUME, Beat, RunState, decide, marked_live, run_key  # noqa: E402

FLOWS = {"bank": "BankFlow", "catalog": "CatalogFlow", "sweep": "SweepFlow"}
DEFAULT_ROOT = "/rs/rs_grp_oschome/go2432/metaflow"
NO_METAFLOW = (
    "Metaflow is not in this python; the train-cpu and train-gpu environments carry it, "
    "and the gate word start installs them"
)
EX_USAGE = 64
EX_UNAVAILABLE = 69
BEAT_SECONDS = 60
USAGE = "usage: python flows/launch.py {bank|catalog|sweep} [--max-workers N] [--root DIR] -- <flow parameters>"


class LaunchError(Exception):
    """A refusal in words, with the exit code the job ends with."""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def parse(argv):
    """The flow's name, the launcher's own options and the flow's words after the --."""
    if "--" in argv:
        cut = argv.index("--")
        own, words = argv[:cut], argv[cut + 1:]
    else:
        own, words = argv, []
    if not own or own[0] not in FLOWS:
        raise LaunchError(USAGE, EX_USAGE)
    name, options = own[0], {"max_workers": 1, "root": None}
    rest = own[1:]
    while rest:
        flag = rest.pop(0)
        if flag not in ("--max-workers", "--root") or not rest:
            raise LaunchError(USAGE, EX_USAGE)
        value = rest.pop(0)
        if flag == "--root":
            options["root"] = value
        elif value.isascii() and value.isdigit() and len(value) <= 4 and int(value) >= 1:
            options["max_workers"] = int(value)
        else:
            raise LaunchError(f"--max-workers takes a whole number from 1 to 9999, not {value}", EX_USAGE)
    if any(word == "--commit" or word.startswith("--commit=") for word in words):
        raise LaunchError("the launcher passes --commit itself, the checkout's own; leave it out", EX_USAGE)
    return name, options, words


def names_a_date(words):
    return any(word == "--date" or word.startswith("--date=") for word in words)


def datastore_root(given):
    """The folder Metaflow keeps .metaflow in, as an absolute path; nothing is checked yet."""
    return Path(given or os.environ.get("SCHWINGNET_METAFLOW") or DEFAULT_ROOT).expanduser().absolute()


def require_parent(root):
    """The root's parent must be there, as the lab volume is on the grid: a root on a volume that
    is not mounted would otherwise be made on the node's own disk and lost with the job."""
    if not root.parent.is_dir():
        raise LaunchError(
            f"the Metaflow datastore {root} has no parent folder {root.parent}; on the grid it is "
            f"the lab volume's, elsewhere name one with --root or SCHWINGNET_METAFLOW",
            EX_UNAVAILABLE,
        )


def repository():
    return Path(os.environ.get("SCHWINGNET") or ROOT).absolute()


def commit_of(repo):
    """The checkout's full commit, which the key and the flow's --commit carry."""
    try:
        done = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    except OSError as error:  # no git where the launcher runs, a box without it among them
        raise LaunchError(f"git could not be run to read the commit of {repo}: {error}", EX_UNAVAILABLE) from error
    commit = done.stdout.strip()
    if done.returncode != 0 or len(commit) != 40:
        raise LaunchError(f"git could not read the commit of {repo}: {done.stderr.strip()}", EX_UNAVAILABLE)
    return commit


def reads_of(name, repo, words):
    """What the flow reads that its words do not name, for the key: bank's recipes and raw copies,
    listed by the flow's own file in the checkout (flows/bank.py's key_reads), so the launcher
    lists them exactly as start will; nothing for the other flows. Loaded once Metaflow is set
    up, since that file imports it."""
    if name != "bank":
        return []
    spec = importlib.util.spec_from_file_location("schwingnet_bank_flow", repo / "flows" / "bank.py")
    flow = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(flow)
    return flow.key_reads(words, Path.cwd())


def point_metaflow_at(root):
    """Metaflow reads its settings once, when it is first imported, so these are set before that,
    in this process and in the flow's, which inherits them."""
    os.environ["METAFLOW_DATASTORE_SYSROOT_LOCAL"] = str(root)
    os.environ["METAFLOW_DEFAULT_DATASTORE"] = "local"
    os.environ["METAFLOW_DEFAULT_METADATA"] = "local"
    if not os.environ.get("METAFLOW_USER"):
        os.environ["METAFLOW_USER"] = os.environ.get("USER") or "schwingnet"


def require_metaflow():
    try:
        import metaflow  # noqa: F401
    except Exception as error:  # a broken install refuses as a missing one does
        raise LaunchError(f"{NO_METAFLOW} ({type(error).__name__}: {error})", EX_UNAVAILABLE) from error


def runs_with_key(flow_class, key):
    """The runs of the flow tagged with the key, newest first; none where the flow never ran."""
    from metaflow import Flow, namespace
    from metaflow.exception import MetaflowNotFound

    namespace(None)
    try:
        runs = list(Flow(flow_class).runs(f"key:{key}"))
    except MetaflowNotFound:
        return []
    runs.sort(key=lambda run: (run.created_at, run.id), reverse=True)
    return [RunState(run.id, bool(run.finished), bool(run.successful)) for run in runs]


def beats_folder(root, flow_class, key):
    """Where the launchers of one key keep their beats: under the datastore root, which every node
    sees, beside Metaflow's .metaflow and never in it."""
    return root / "launches" / flow_class / key


def this_launcher():
    """This launcher's host, process and Slurm job, "" outside one, as its beat names them."""
    return socket.gethostname(), os.getpid(), os.environ.get("SLURM_JOB_ID", "")


def gone_here(record, host):
    """Whether a beat was written on this host by a process that is no longer there, or whose
    number this launcher now holds: that launcher is gone, whatever its beat's time says."""
    pid = record.get("pid")
    if record.get("host") != host:
        return False
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OverflowError):  # no such process, or a number none can have
        return True
    except PermissionError:  # another user's process, which is there
        return False
    return False


def beat_of(record):
    """A beat file's record as a pipeline.Beat, or None where it does not hold together."""
    if not isinstance(record, dict):
        return None
    run, job, at = record.get("run"), record.get("slurm_job"), record.get("beat")
    if isinstance(run, str) and isinstance(job, str) and isinstance(at, (int, float)) and not isinstance(at, bool):
        return Beat(run, job, float(at)) if math.isfinite(at) else None
    return None


def read_beats(folder, host):
    """The beats of the key's launchers, less those of launchers gone from this host; a file that
    cannot be read or does not hold together is no beat."""
    beats = []
    for path in sorted(folder.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        beat = beat_of(record)
        if beat is not None and not gone_here(record, host):
            beats.append(beat)
    return beats


class Heartbeat:
    """This launcher's beat while its flow runs: written before the flow starts, so a run the flow
    makes always has one, naming the run within a second of Metaflow's writing its id, rewritten
    every BEAT_SECONDS, and taken away when the flow ends. A write that fails is said once and
    tried again at the next beat."""

    def __init__(self, folder, key, run_id_file):
        host, pid, job = this_launcher()
        self.path = folder / f"{re.sub(r'[^A-Za-z0-9._-]', '_', host)}-{pid}.json"
        self.run_id_file = run_id_file
        self.record = {"key": key, "run": "", "host": host, "pid": pid, "slurm_job": job, "beat": 0.0}
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.beat_on, daemon=True)
        self.said = False

    def __enter__(self):
        self.write()
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=10)
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def beat_on(self):
        last = time.monotonic()
        while not self.stop.wait(1.0):
            named = self.record["run"] or self.named_run()
            if named != self.record["run"] or time.monotonic() - last >= BEAT_SECONDS:
                self.record["run"] = named
                self.write()
                last = time.monotonic()

    def named_run(self):
        try:
            return self.run_id_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def write(self):
        self.record["beat"] = time.time()
        part = self.path.with_name(self.path.name + ".part")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            part.write_text(json.dumps(self.record, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(part, self.path)
        except OSError as error:
            if not self.said:
                print(f"launch: the heartbeat {self.path} could not be written: {error}", file=sys.stderr, flush=True)
            self.said = True


def flow_command(name, repo, decision, origin, options, words, key, commit, run_id_file, today):
    """The flow's command line: a new run with the words, or a resume, which clones them."""
    command = [sys.executable, str(repo / "flows" / f"{name}.py"), "--quiet"]
    tags = ["--tag", f"key:{key}", "--tag", f"commit:{commit[:7]}"]
    workers = ["--max-workers", str(options["max_workers"])]
    if decision == RESUME:
        return command + ["resume", "--origin-run-id", origin, *workers, *tags, "--run-id-file", run_id_file]
    command += ["run", *workers, *tags, "--run-id-file", run_id_file, *words, "--commit", commit]
    if name == "bank" and not names_a_date(words):
        command += ["--date", today]
    return command


def ended(flow_class, run_id):
    """Whether the run succeeded and the verdict its end step set, as far as Metaflow says; a run
    Metaflow cannot find, one that died before it was recorded, did not succeed."""
    if not run_id:
        return False, None
    from metaflow import Run, namespace

    namespace(None)
    try:
        run = Run(f"{flow_class}/{run_id}")
        if not run.successful:
            return False, None
        verdict = getattr(run["end"].task.data, "verdict", None)
    except Exception as error:  # the client's own errors have no common base worth naming
        print(f"launch: Metaflow could not say how {flow_class}/{run_id} ended: {error}", file=sys.stderr, flush=True)
        return False, None
    return True, verdict if isinstance(verdict, int) and not isinstance(verdict, bool) else None


def exit_code(flow_code, verdict):
    """The flow's own code where it failed (a signal as a shell gives it), else the verdict."""
    if flow_code < 0:
        return 128 - flow_code
    if flow_code != 0:
        return flow_code
    return verdict if verdict in (0, 1) else 1


def say(record):
    print(json.dumps(record, sort_keys=True), flush=True)


def run_flow(command, root, repo):
    """The flow, its output passing through, in the datastore root (cards, above)."""
    env = dict(os.environ, SCHWINGNET=str(repo), SCHWINGNET_WORKDIR=os.getcwd())
    return subprocess.run(command, cwd=root, env=env).returncode


def launch(argv):
    name, options, words = parse(argv)
    root = datastore_root(options["root"])
    point_metaflow_at(root)
    require_metaflow()
    require_parent(root)
    (root / ".metaflow").mkdir(parents=True, exist_ok=True)
    repo = repository()
    commit = commit_of(repo)
    key = run_key(name, commit, words, reads_of(name, repo, words))
    flow_class = FLOWS[name]
    folder = beats_folder(root, flow_class, key)
    host, _, job = this_launcher()
    # the runs before the beats: a run listed was made after its launcher's beat was written
    runs = runs_with_key(flow_class, key)
    runs = marked_live(runs, read_beats(folder, host), job, time.time())
    decision, origin = decide(runs)
    live = runs[0].run_id if runs and runs[0].live and not runs[0].successful else None
    say({"decision": decision, "flow": name, "key": key, "live": live, "origin": origin, "root": str(root)})
    with tempfile.TemporaryDirectory(prefix="launch-") as scratch:
        run_id_file = Path(scratch) / "run-id"
        command = flow_command(name, repo, decision, origin, options, words, key, commit, str(run_id_file),
                               date.today().isoformat())
        with Heartbeat(folder, key, run_id_file):
            flow_code = run_flow(command, root, repo)
        run_id = run_id_file.read_text(encoding="utf-8").strip() if run_id_file.is_file() else ""
    successful, verdict = ended(flow_class, run_id)
    say({"flow": name, "run": f"{flow_class}/{run_id}" if run_id else None, "successful": successful,
         "verdict": verdict})
    return exit_code(flow_code, verdict)


def main(argv=None):
    try:
        return launch(sys.argv[1:] if argv is None else argv)
    except LaunchError as error:
        print(f"launch: {error}", file=sys.stderr, flush=True)
        return error.code


if __name__ == "__main__":
    sys.exit(main())
