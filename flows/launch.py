"""Start or resume one of the pipeline's Metaflow flows: the one way a flow starts on the grid.

Usage:
    python flows/launch.py {bank|catalog|sweep} [--max-workers N] [--root DIR] -- <flow parameters>

The grid ends jobs from outside, a Slurm time limit or a preemption killing the whole job, and
the gate word that queued it queues it again. Metaflow carries a run that did not finish on with
`resume --origin-run-id`, cloning every step and every branch of a foreach that finished and
running only the rest, but it must be told which run. So every job of a pipeline stage starts
here: the launch is named by a key, the hash of the flow, the commit and the flow's parameters
as given (schwingnet.pipeline.run_key), every run carries the key as a tag, and the newest run
with that key decides (schwingnet.pipeline.decide): one that did not succeed is resumed, else a
new run starts. A job queued again with the same words therefore continues where the killed one
stopped, and a change of code or of configuration starts afresh. Bank's --date is left out of
the key, since it is chosen once per run here and resume keeps it with the other parameters.

The first line on stdout is the decision, as JSON, flushed before the flow starts, and the last
says which run it was and how it ended; the exit code is the flow's own where it failed, else
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

import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor" / "beethoven-qa" / "src"))

from schwingnet.pipeline import RESUME, RunState, decide, run_key  # noqa: E402

FLOWS = {"bank": "BankFlow", "catalog": "CatalogFlow", "sweep": "SweepFlow"}
DEFAULT_ROOT = "/rs/rs_grp_oschome/go2432/metaflow"
NO_METAFLOW = (
    "Metaflow is not in this python; the train-cpu and train-gpu environments carry it, "
    "and the gate word start installs them"
)
EX_USAGE = 64
EX_UNAVAILABLE = 69
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


def without_date(words):
    """The words the key is taken over: all but --date and its value, which resume keeps itself."""
    kept, skip = [], False
    for word in words:
        if skip:
            skip = False
        elif word == "--date":
            skip = True
        elif not word.startswith("--date="):
            kept.append(word)
    return kept


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
    key = run_key(name, commit, without_date(words))
    flow_class = FLOWS[name]
    decision, origin = decide(runs_with_key(flow_class, key))
    say({"decision": decision, "flow": name, "key": key, "origin": origin, "root": str(root)})
    with tempfile.TemporaryDirectory(prefix="launch-") as scratch:
        run_id_file = Path(scratch) / "run-id"
        command = flow_command(name, repo, decision, origin, options, words, key, commit, str(run_id_file),
                               date.today().isoformat())
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
