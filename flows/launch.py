"""Start or resume one of the pipeline's Metaflow flows: the one way a flow starts on the grid.

Usage:
    python flows/launch.py <kind> [--max-workers N] [--root DIR] -- <flow parameters>

The kinds are the flows flows/registry.txt lists, bank, catalog and sweep among them.

The grid ends jobs from outside, a Slurm time limit or a preemption killing the whole job, and
the gate word that queued it queues it again. Metaflow carries a run that did not finish on with
`resume --origin-run-id`, cloning every step and every branch of a foreach that finished and
running only the rest, but it must be told which run. So every job of a pipeline stage starts
here: the launch is named by a key, the hash of the flow, the code it runs, the flow's parameters
as given and what the flow reads that they do not name, since resume clones steps made from
inputs the words do not name (schwingnet.pipeline.run_key). The code is tools/run_code.py's
digest of the files the flow's kind executes (code_of), not the commit: main merges many times a
day and most merges change nothing a flow runs, so a job cut short and queued again after one
carries its run on, where a key with the commit in it started the run over (issue #252, finding
27). What it reads is listed by the flow's own key_reads (reads_of): for bank every recipe it
lists with its raw folder's state, for catalog every shard manifest the build would read with
its size and sha256, for sweep the plan file's bytes. Every run carries the key as a tag, and the
newest run with that key decides (schwingnet.pipeline.decide): one that did not succeed is
resumed where Metaflow saved its parameters, else a new run starts. A job queued again with the
same words therefore continues where the killed one stopped, and a change of code, of
configuration, of a plan, of a raw copy or of a shard starts afresh. A new run is given the
checkout's --commit, which resume clones with
the other parameters, so a resumed run names the commit it was first started on, which holds
the same code; its tags name the commit that launched it and the code's digest beside the key.
Bank's --date is in the key when the caller gave it, so a job
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
overlap. A beat left by a launcher killed with its job counts no more once it is LIVE_SECONDS
old, at once where it names this very Slurm job, which Slurm queued again, and at once where it
names a process on this host that is gone. The runs are listed before the beats are read, each
by one read of its end task, and the newest is read again before it is resumed (decision_of), so
a run that ended well in the meantime is never resumed as one that had not.

The first line on stdout is the decision, as JSON, flushed before the flow starts, with "live"
the id of a newest run passed over as live; after the flow's own lines a second JSON line says
which run it was and how it ended. The exit code is the flow's own where it failed, else the end
step's verdict (0 all well, 1 otherwise), so a job's afterok means what it meant before. The flow
runs in a process group of its own, and a SIGTERM or SIGINT the launcher is sent while it runs,
Slurm's at a time limit or a preemption among them, is passed on to every process of the flow;
what has not ended STOP_GRACE_SECONDS later is killed, the beat is taken away as at any end, so
the job Slurm queues again resumes the run at once, the page says which signal ended it, and the
launcher exits 128 plus the signal's number, 143 for SIGTERM, as a shell reports a killed job. The
signal is passed on before a word of it is said, and a word the launcher cannot write, its reader
gone as a pipe's reader goes with its job, is dropped (tell), so no stop is ever cut short by its
own message; a launcher that breaks while its flow runs kills the flow before its beat goes. A
refusal is the line LaunchError: <words> on stderr, before any flow starts, with the exit code 64
for words the launcher does not take, 69 for what the node lacks and 70 for a rule of
schwingnet.pipeline the runs broke; anything else that stops it prints its traceback and exits 1.
Whatever the end, the last line on stdout is the kind's word in flows/registry.txt with the exit
code and the time, as XR_CATALOG_RC=0 2026-10-25 12:00:00: the gate's status keeps that line and
withholds the words of every other, so a job's log shows how the launcher ended wherever it ended.

Every deep learning flow is held to a frozen PREREG (the owner's rule of 2026-10-29): the registry
names the PREREG.md of each kind that trains or runs a network, and the launcher refuses one whose
PREREG is missing or no longer the one its PREREG.md.sha256 froze before any flow starts, with the
Lab Recipe's exit 90 (flows/stage_registry.py), and so too a run whose part of its kind, a sweep's
plan, the frozen PREREG does not cover, by its name and, where the PREREG names them, its bytes.
The PREREG's path and sha256 are among what the key
reads, so a run is only ever carried on under the PREREG it started under, and every run of such a
kind is tagged prereg:<12> beside the key. Once Metaflow has named the run, the launcher writes the
head of its progress page (flows/stage_progress.py), <root>/progress/<Flow>/<run>/run.json, since a
resumed run clones start and never runs it, and when the flow ends it writes how it ended there.

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
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor" / "beethoven-qa" / "src"))

sys.path.insert(0, str(ROOT / "flows"))

import stage_progress  # noqa: E402
import stage_registry  # noqa: E402
from beethoven_qa.contracts import ViolationError  # noqa: E402
from schwingnet.pipeline import RESUME, Beat, RunState, decide, marked_live, run_key  # noqa: E402

DEFAULT_ROOT = "/rs/rs_grp_oschome/go2432/metaflow"
NO_METAFLOW = (
    "Metaflow is not in this python; the train-cpu and train-gpu environments carry it, "
    "and the gate word start installs them"
)
EX_USAGE = 64
EX_UNAVAILABLE = 69
EX_SOFTWARE = 70
BEAT_SECONDS = 60
# Slurm stops a job with SIGTERM, at its time limit and on a preemption, and job submit sends one
# to the batch shell two minutes before the limit (--signal=B:TERM@120), which the bank and catalog
# scripts exec the launcher as; a person stops a launch with SIGINT. The flow runs in a process
# group of its own, so the launcher passes either on to every process of it, the Metaflow runtime
# and each task with what it runs, gives them STOP_GRACE_SECONDS to end, as grid/drr-gap.sbatch gives
# its tool, and then kills what is left, so no process of the flow outlives the launcher.
STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT)
STOP_GRACE_SECONDS = 60
POLL_SECONDS = 0.5
# The word of the line every exit of the launcher ends with, each kind's in flows/registry.txt: the
# one the bank and catalog stages' scripts end with when they run straight, and for the sweep one
# apart from the SN_SWEEP_RC its driver prints after the launcher's. The gate's status keeps such a
# line and withholds every other the launcher prints, so a job shows how it ended wherever it ended
# (the second review of #252, finding 6). A kind the registry does not list, or a registry that
# cannot be read, ends with LAUNCH_RC.
NO_WORD = "LAUNCH_RC"


def tell(text, stream=None):
    """One line of the launcher's own, flushed, on stderr unless another stream is named. A reader
    that has gone, as a pipe's reader killed with its job by Slurm's TERM, never stops the launcher,
    least of all in the middle of stopping its flow: the stream is pointed at /dev/null from then on,
    so neither this line nor Python's own flush at exit fails again. A line said by a signal's
    handler while the main thread was writing one is dropped as well, since Python refuses that
    second write rather than mixing the two."""
    stream = sys.stderr if stream is None else stream
    try:
        print(text, file=stream, flush=True)
    except RuntimeError:  # a reentrant write, from a signal's handler: the line is lost, not the stop
        pass
    except (OSError, ValueError):  # a reader gone (BrokenPipeError among them) or a stream closed
        to_nowhere(stream)


def to_nowhere(stream):
    """The stream's file pointed at /dev/null, where it has one."""
    try:
        nowhere = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(nowhere, stream.fileno())
        finally:
            os.close(nowhere)
    except (OSError, ValueError):
        pass


class LaunchError(Exception):
    """A refusal in words, with the exit code the job ends with."""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def usage(flows):
    return f"usage: python flows/launch.py {{{'|'.join(flows)}}} [--max-workers N] [--root DIR] -- <flow parameters>"


def flows_listed(repo):
    """The flows the checkout's registry lists, by kind (flows/registry.txt)."""
    try:
        return stage_registry.entries(repo)
    except stage_registry.RegistryError as error:
        raise LaunchError(f"the registry of flows cannot be read: {error}", EX_UNAVAILABLE) from error


def parse(argv, flows):
    """The flow's name, the launcher's own options and the flow's words after the --."""
    if "--" in argv:
        cut = argv.index("--")
        own, words = argv[:cut], argv[cut + 1:]
    else:
        own, words = argv, []
    if not own or own[0] not in flows:
        raise LaunchError(usage(flows), EX_USAGE)
    name, options = own[0], {"max_workers": 1, "root": None}
    rest = own[1:]
    while rest:
        flag = rest.pop(0)
        if flag not in ("--max-workers", "--root") or not rest:
            raise LaunchError(usage(flows), EX_USAGE)
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


def require_prereg(name, repo, part=None, part_sha256=None):
    """The kind's frozen PREREG, (path, sha256), None for a stage that trains and runs no network;
    refused with the Lab Recipe's exit 90 where it is missing or moved, or covers no such part or
    not the part's bytes, before any flow starts."""
    try:
        return stage_registry.frozen_for(name, part, part_sha256, repo)
    except stage_registry.PreregError as error:
        raise LaunchError(f"the {name} flow's runs are held to a frozen PREREG (the owner's rule of 2026-10-29), "
                          f"so none was started or resumed: {error}", stage_registry.EX_PREREG) from error


def prereg_reads(prereg):
    """What the key reads of the PREREG: its path and its bytes' sha256."""
    return [f"prereg {prereg[0]} {prereg[1]}"] if prereg else []


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
    """The checkout's full commit, which a new run's --commit and every run's tag carry."""
    try:
        done = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    except OSError as error:  # no git where the launcher runs, a box without it among them
        raise LaunchError(f"git could not be run to read the commit of {repo}: {error}", EX_UNAVAILABLE) from error
    commit = done.stdout.strip()
    if done.returncode != 0 or len(commit) != 40:
        raise LaunchError(f"git could not read the commit of {repo}: {done.stderr.strip()}", EX_UNAVAILABLE)
    return commit


def code_of(repo, name):
    """The digest of the code the flow runs, by the checkout's own tools/run_code.py and its list
    for the flow's kind, read from the checkout's tracked files."""
    spec = importlib.util.spec_from_file_location("schwingnet_tool_run_code", repo / "tools" / "run_code.py")
    tool = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(tool)
    except OSError as error:
        raise LaunchError(f"no tools/run_code.py in {repo} to name the {name} flow's code by: {error}", EX_UNAVAILABLE) from error
    try:
        return tool.digest(name, repo)
    except tool.RunCodeError as error:
        raise LaunchError(f"the code the {name} flow runs cannot be named: {error}", EX_UNAVAILABLE) from error


def flow_module(name, repo):
    """The flow's own file in the checkout, loaded once Metaflow is set up, since those files
    import it."""
    if str(repo / "flows") not in sys.path:
        sys.path.insert(0, str(repo / "flows"))
    spec = importlib.util.spec_from_file_location(f"schwingnet_{name}_flow", repo / "flows" / f"{name}.py")
    flow = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(flow)
    return flow


def reads_of(flow, words):
    """What the flow reads that its words do not name, for the key, listed by the flow's own
    key_reads, so the launcher lists them exactly as the flow will: bank's recipes and raw copies,
    the sweep's plan; nothing for a flow with no key_reads."""
    key_reads = getattr(flow, "key_reads", None)
    return key_reads(words, Path.cwd()) if key_reads else []


def part_of(flow, words):
    """The part of its kind a run of these words is and the sha256 of the part's bytes, by the
    flow's own prereg_part, as the sweep's plan is; (None, None) for a flow whose runs are all of
    one design."""
    prereg_part = getattr(flow, "prereg_part", None)
    return prereg_part(words, Path.cwd()) if prereg_part else (None, None)


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


def end_state(run):
    """Whether the run finished and whether it succeeded, from one read of its end task. Metaflow
    registers a task's artifacts a file at a time once it has marked the attempt done, its success
    and its ok among them, so two reads of a run, as its two properties make, can fall on either
    side of one of those files: a run that succeeded read as not finished broke decide's rule and
    ended the launch in a traceback (the second review of #252, finding 3). The success is read
    first, and counts as finished, since Metaflow sets it only with the ok."""
    end = run.end_task
    if end is None:
        return False, False
    successful = bool(end.successful)
    return successful or bool(end.finished), successful


def parameters_saved(run):
    """Whether Metaflow saved the run's parameters, its _parameters task done, as it is before any
    step runs and in a resume that got that far: a run killed after Metaflow registered it and
    before then has no such task, or one not done, and Metaflow refuses to resume it."""
    try:
        task = run["_parameters"].task
    except KeyError:
        return False
    return task is not None and bool(task.finished)


def run_state(run):
    finished, successful = end_state(run)
    return RunState(run.id, finished, successful, parameters_saved=parameters_saved(run))


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
    return [run_state(run) for run in runs]


def read_again(flow_class, run):
    """The run as Metaflow has it now, marked live as it was."""
    from metaflow import Run, namespace

    namespace(None)
    return run_state(Run(f"{flow_class}/{run.run_id}"))._replace(live=run.live)


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

    def __init__(self, folder, key, run_id_file, page=None):
        host, pid, job = this_launcher()
        self.page = page
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
        """The beat first and the page after it, since the beat is what keeps another launch from
        resuming a run still going, and the page's drawing, which reads every run's view, takes
        longer; Page never raises, so a page that fails never stops the beat."""
        last = time.monotonic()
        while not self.stop.wait(1.0):
            named = self.record["run"] or self.named_run()
            if named != self.record["run"] or time.monotonic() - last >= BEAT_SECONDS:
                newly_named = named != self.record["run"]
                self.record["run"] = named
                self.write()
                last = time.monotonic()
                if newly_named and self.page:
                    self.page.begin(named)

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
                tell(f"launch: the heartbeat {self.path} could not be written: {error}")
            self.said = True


class Page:
    """The run's progress page as the launcher keeps it: the head once Metaflow has named the run,
    how the flow ended once it has; a page that cannot be written or drawn, for whatever reason, is
    said once, and neither the beat nor the run waits on it."""

    def __init__(self, root, head):
        self.root, self.head, self.run, self.said = root, head, "", False
        self.started = stage_progress.utc_now()

    def begin(self, run):
        """The head of a run Metaflow has named, started when the launcher started its flow, since
        the launcher may name the run only as its flow ends, one that ended within the second."""
        self.run = run
        self.write(lambda: stage_progress.write_head(self.root, dict(self.head, run=run, started=self.started)))

    def end(self, record, run=""):
        """How the flow ended, as the launcher saw it, on the page of the run it ran; a flow that
        ended before the heartbeat's first look named its run is begun here first, so its page has
        its head."""
        if run and not self.run:
            self.begin(run)
        if self.run:
            self.write(lambda: stage_progress.write_launch(self.root, self.head["flow"], self.run, record))

    def write(self, writing):
        try:
            writing()
            stage_progress.draw(self.root, self.head["flow"], self.run)
        except Exception as error:  # a page, whatever stops it, never stops the beat or the launch
            if not self.said:
                tell(f"launch: the progress page could not be written: {type(error).__name__}: {error}")
            self.said = True


def page_head(name, flow_class, key, commit, code, prereg, decision, origin):
    host, _, job = this_launcher()
    return {"flow": flow_class, "kind": name, "key": key, "commit": commit[:7], "code": code[:12],
            "prereg": prereg[0] if prereg else None, "prereg_sha256": prereg[1] if prereg else None,
            "origin": origin if decision == RESUME else None, "decision": decision, "host": host, "slurm_job": job}


def decision_of(flow_class, key, folder):
    """Run anew or resume, and the runs that says it, newest first. The runs are listed before the
    beats are read, so a run listed was made after its launcher's beat was written; and the newest
    is read again after them before it is resumed, since a run that ended well after the listing,
    its launcher gone before the beats were read, would be resumed as one that had not, every step
    of it cloned (the second review of #252, finding 3)."""
    host, _, job = this_launcher()
    runs = runs_with_key(flow_class, key)
    runs = marked_live(runs, read_beats(folder, host), job, time.time())
    decision, origin = decide(runs)
    if decision == RESUME:
        runs = [read_again(flow_class, runs[0]), *runs[1:]]
        decision, origin = decide(runs)
    return runs, decision, origin


def run_tags(key, commit, code, prereg=None):
    """What every run is tagged with: the key that finds it, the commit of the checkout that
    launched it, the code's digest and, for a deep learning flow, its PREREG's, as Metaflow's UI
    and client filter runs by."""
    tags = [f"key:{key}", f"commit:{commit[:7]}", f"code:{code[:12]}", *([f"prereg:{prereg[1][:12]}"] if prereg else [])]
    return [word for tag in tags for word in ("--tag", tag)]


def flow_command(name, repo, decision, origin, options, words, tags, commit, run_id_file, today):
    """The flow's command line: a new run with the words, or a resume, which clones them."""
    command = [sys.executable, str(repo / "flows" / f"{name}.py"), "--quiet"]
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
        tell(f"launch: Metaflow could not say how {flow_class}/{run_id} ended: {error}")
        return False, None
    return True, verdict if isinstance(verdict, int) and not isinstance(verdict, bool) else None


def exit_code(flow_code, verdict, stopped_by=None):
    """The signal that stopped the launcher as a shell gives it, else the flow's own code where it
    failed (a signal as a shell gives it), else the verdict."""
    if stopped_by:
        return 128 + stopped_by
    if flow_code < 0:
        return 128 - flow_code
    if flow_code != 0:
        return flow_code
    return verdict if verdict in (0, 1) else 1


def say(record):
    tell(json.dumps(record, sort_keys=True), sys.stdout)


def live_members(group):
    """The processes of a process group that have not ended, from /proc, as Linux gives them; None
    where /proc cannot be listed."""
    try:
        entries = [entry for entry in os.listdir("/proc") if entry.isdigit()]
    except OSError:
        return None
    members = []
    for entry in entries:
        try:
            fields = Path(f"/proc/{entry}/stat").read_text(encoding="ascii", errors="replace").rsplit(")", 1)[1].split()
        except (OSError, IndexError):  # a process that ended while it was read
            continue
        if len(fields) > 2 and fields[2] == str(group) and fields[0] != "Z":
            members.append(int(entry))
    return members


class FlowProcess:
    """The flow's process, in a process group of its own, and the stop signal the launcher was sent
    while it ran, passed on to the whole group (STOP_SIGNALS above)."""

    def __init__(self):
        self.process, self.stopped_by, self.deadline = None, None, None

    def stop(self, signum, _frame=None):
        """A stop signal's handler: passed on to the flow's group, which has until the deadline, and
        only then said, since the saying may meet a reader that has gone (tell)."""
        first = self.stopped_by is None
        if first:
            self.stopped_by, self.deadline = signum, time.monotonic() + STOP_GRACE_SECONDS
        self.signal_group(signum)
        if first:
            tell(f"launch: {signal.Signals(signum).name}: passed on to every process of the flow, which has "
                 f"{STOP_GRACE_SECONDS} s to end")

    def signal_group(self, signum):
        if self.process is None:
            return
        try:
            os.killpg(self.process.pid, signum)
        except (ProcessLookupError, PermissionError):  # the group has ended, or holds no process of ours
            pass

    def group_alive(self):
        """Whether a process of the flow's group has not yet ended. A zombie has ended and waits
        only for its parent to read it, which no one may do for a task whose runtime died, so it is
        not counted where /proc tells it apart; elsewhere the group's answer to signal 0 decides."""
        members = live_members(self.process.pid)
        if members is not None:
            return bool(members)
        try:
            os.killpg(self.process.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def run(self, command, cwd, env):
        """The flow's exit code once it has ended: as before where nothing stopped the launcher,
        and where a signal did, once every process of its group has ended or been killed at the
        deadline."""
        self.process = subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True)
        if self.stopped_by is not None:  # a signal that came before the flow began
            self.signal_group(self.stopped_by)
        code = None
        while True:
            if code is None:
                try:
                    code = self.process.wait(timeout=POLL_SECONDS)
                except subprocess.TimeoutExpired:
                    pass
            else:
                time.sleep(POLL_SECONDS)
            if code is not None and (self.stopped_by is None or not self.group_alive()):
                return code
            if self.deadline is not None and time.monotonic() >= self.deadline:
                self.signal_group(signal.SIGKILL)
                tell(f"launch: the flow's processes did not end within {STOP_GRACE_SECONDS} s, so they were killed")
                return code if code is not None else self.process.wait()


def run_flow(command, root, repo):
    """The flow, its output passing through, in the datastore root (cards, above), with a stop
    signal the launcher is sent while it runs passed on to it (FlowProcess): (the flow's exit code,
    the signal that stopped the launcher or None)."""
    env = dict(os.environ, SCHWINGNET=str(repo), SCHWINGNET_WORKDIR=os.getcwd())
    flow = FlowProcess()
    previous = {signum: signal.signal(signum, flow.stop) for signum in STOP_SIGNALS}
    try:
        code = flow.run(command, root, env)
    except BaseException:
        # The beat is taken away as the launcher unwinds, so a flow left running would be resumed
        # by the next launch of its key while it still runs; nothing of it outlives a broken launcher.
        flow.signal_group(signal.SIGKILL)
        raise
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return code, flow.stopped_by


def ended_words(code_out, successful, stopped_by):
    """How the launch ended, in the words its page shows."""
    if stopped_by:
        return (f"the launcher was stopped by {signal.Signals(stopped_by).name}, stopped its flow and exited {code_out}, "
                f"the flow {'succeeded' if successful else 'did not succeed'}")
    return f"the launcher exited {code_out}, the flow {'succeeded' if successful else 'did not succeed'}"


def launch(argv):
    repo = repository()
    flows = flows_listed(repo)
    name, options, words = parse(argv, flows)
    prereg = require_prereg(name, repo)
    root = datastore_root(options["root"])
    point_metaflow_at(root)
    require_metaflow()
    require_parent(root)
    # The part a run is can be read only from the flow's own file, which imports Metaflow; it is
    # refused there, before the datastore is touched and before git or the code digest is asked.
    flow = flow_module(name, repo)
    prereg = require_prereg(name, repo, *part_of(flow, words)) if prereg else prereg
    (root / ".metaflow").mkdir(parents=True, exist_ok=True)
    commit, code = commit_of(repo), code_of(repo, name)
    key = run_key(name, code, words, [*reads_of(flow, words), *prereg_reads(prereg)])
    flow_class = flows[name]["class"]
    folder = beats_folder(root, flow_class, key)
    runs, decision, origin = decision_of(flow_class, key, folder)
    live = runs[0].run_id if runs and runs[0].live and not runs[0].successful else None
    say({"code": code, "decision": decision, "flow": name, "key": key, "live": live, "origin": origin, "root": str(root)})
    page = Page(root, page_head(name, flow_class, key, commit, code, prereg, decision, origin))
    with tempfile.TemporaryDirectory(prefix="launch-") as scratch:
        run_id_file = Path(scratch) / "run-id"
        command = flow_command(name, repo, decision, origin, options, words, run_tags(key, commit, code, prereg), commit,
                               str(run_id_file), date.today().isoformat())
        with Heartbeat(folder, key, run_id_file, page):
            flow_code, stopped_by = run_flow(command, root, repo)
        run_id = run_id_file.read_text(encoding="utf-8").strip() if run_id_file.is_file() else ""
    successful, verdict = ended(flow_class, run_id)
    code_out = exit_code(flow_code, verdict, stopped_by)
    page.end({"words": ended_words(code_out, successful, stopped_by), "exit": code_out, "successful": successful,
              "verdict": verdict, "signal": signal.Signals(stopped_by).name if stopped_by else None,
              "at": stage_progress.utc_now()}, run_id)
    say({"flow": name, "run": f"{flow_class}/{run_id}" if run_id else None, "successful": successful,
         "verdict": verdict})
    return code_out


def refused(error):
    """A refusal in words, as the line LaunchError: <words>, whose words the gate's status withholds."""
    tell(f"LaunchError: {error}")
    return error.code


def rc_word(argv):
    """The word of the launcher's last line for the kind asked, LAUNCH_RC where the registry lists
    no such kind or cannot be read."""
    try:
        listed = stage_registry.entries(repository())
    except stage_registry.RegistryError:
        return NO_WORD
    kind = argv[0] if argv else ""
    return listed[kind]["word"] if kind in listed else NO_WORD


def say_ended(argv, code):
    """The launcher's last line: its stage's word, the exit code and the time, and no value of a run."""
    tell(f"{rc_word(argv)}={code} {datetime.now():%Y-%m-%d %H:%M:%S}", sys.stdout)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        code = launch(argv)
    except LaunchError as error:
        code = refused(error)
    except ViolationError as error:
        code = refused(LaunchError(f"a rule of schwingnet.pipeline was broken, so no run was started or resumed: {error}",
                                   EX_SOFTWARE))
    except Exception:  # anything else ends the job as Python ends it, with its traceback, and then the line
        tell(traceback.format_exc().rstrip())
        code = 1
    say_ended(argv, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
