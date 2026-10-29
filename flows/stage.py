"""What every flow flows/launch.py starts does besides its own work (the owner's rule of 2026-10-29).

The rule: every deep learning job on the grid runs on the block-based Metaflow pipeline, under a
PREREG frozen before the run, with the CLAIM 2024 and REFORMS report enforced, and with a page
that shows its progress in the browser. The launcher refuses a deep kind whose PREREG is not the
one frozen before any flow starts (flows/stage_registry.py); this module is the part each flow's
steps run:

- hold_to_prereg, in start: the run held to its kind's frozen PREREG again, read from the checkout
  the steps run, and the PREREG's path and sha256 kept as the run's artifacts prereg_path and
  prereg_sha256, with the part it covers and the part's sha256 (prereg_part, prereg_part_sha256),
  so every run says which design it ran under. start's own refusal fails the flow, so the
  launcher then exits with the flow's 1, not 90, which it gives only for a refusal of its own.
- still_held, in end: a resume clones start, and the launcher's key names the PREREG's bytes, so a
  run the launcher carries on is carried on under the PREREG it started under; a resume started
  straight with `python flows/<kind>.py resume` skips both, so end holds the run to the PREREG
  start kept once more and fails where the one frozen now is another or no longer covers the part.
- Beat, around a step's work: the step's line on the run's progress page (flows/stage_progress.py),
  running from its start, then done or failed, with its last lines; run_watched runs a command
  under it and rewrites that line every BEAT_SECONDS from what the work has written so far.
- claim_report, in end: the CLAIM 2024 and REFORMS report (tools/report.py) of a run folder,
  checked against the folder's files before anything is written, since a check right after a
  write only compares the files with what was just rendered. A report that is current is the good
  case; a folder with no report has one written then and checked; a report that is not what the
  folder's files give is written anew, so the folder and the page hold the current one. Where the
  folder's work was done in this Metaflow run (done_since, from when Metaflow registered the run,
  run_began), a stale report is the run's own failure and makes its verdict 1, as does a report
  that cannot be written: no run ends well with a stale report it wrote. Where the work was done
  before this run began, a row cloned from the run a resume carries on or one tools/flow.py
  found finished, a stale report says only that tools/report.py, data/reporting/study.json or the
  checklists changed since, which no run's key names; it is written anew under the report tool
  as it is now and is well, and its line says so. Items no file answers are counted as missing
  and shown, never inferred; `check --complete`, which fails while any is missing, stays the gate
  for numbers that are to be published (tools/report.py).
- finish, in end: the verdict and the reports on the page, those not current first.

Nothing here ever fails a step for its page: a page that cannot be written or drawn, for whatever
reason, is said once on the step's log and the work goes on.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from metaflow import current

import stage_progress as progress
import stage_registry as registry

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
BEAT_SECONDS = 15
REPORT_FILES = ("claim.json", "reforms.json")
# The report's own files, which a write makes, so never a sign of when a folder's work was done.
REPORT_OUTPUTS = ("REPORT.md", *REPORT_FILES)
# What tools/flow.py writes last in a run folder, once its work and its report are done.
FINISHED_MARK = "FINISHED.json"


class StageFault(Exception):
    """What the rule asks of a run that it does not meet: a PREREG not frozen, a report not written."""


def datastore_root():
    """The datastore root the launcher named, under which every run keeps its progress folder."""
    return os.environ.get("METAFLOW_DATASTORE_SYSROOT_LOCAL") or os.getcwd()


def hold_to_prereg(flow, kind, part=None, part_sha256=None):
    """The run held to its kind's frozen PREREG, kept as the run's artifacts, and where the run is
    one part of its kind, as a sweep's plan is, to a PREREG that covers that part and its bytes
    (part_sha256); a kind with none, a stage that trains and runs no network, keeps None."""
    try:
        frozen = registry.frozen_for(kind, part, part_sha256, REPO)
    except (registry.RegistryError, registry.PreregError) as error:
        raise StageFault(str(error)) from error
    flow.prereg_path, flow.prereg_sha256 = frozen if frozen else (None, None)
    flow.prereg_part, flow.prereg_part_sha256 = part, part_sha256
    if frozen:
        print(f"{current.flow_name}: held to {frozen[0]}, sha256 {frozen[1][:16]}, as frozen", flush=True)


def still_held(flow, kind):
    """In end: the run held again to the PREREG start kept. A resume clones start, so start's hold
    is not run again, and a resume started straight, `python flows/<kind>.py resume`, skips the
    launcher's too; so end asks again whether the kind's PREREG frozen now, read from the checkout
    end runs in, covers the part start ran with its bytes as start read them, and is the one start
    kept. A StageFault where it is not, which fails the run."""
    part, part_sha256 = getattr(flow, "prereg_part", None), getattr(flow, "prereg_part_sha256", None)
    try:
        frozen = registry.frozen_for(kind, part, part_sha256, REPO)
    except (registry.RegistryError, registry.PreregError) as error:
        raise StageFault(f"the run's PREREG no longer holds at its end: {error}") from error
    kept = (flow.prereg_path, flow.prereg_sha256) if getattr(flow, "prereg_path", None) else None
    if (tuple(frozen) if frozen else None) != kept:
        started = f"{kept[0]}, sha256 {kept[1][:16]}" if kept else "no PREREG"
        now = f"{frozen[0]}, sha256 {frozen[1][:16]}" if frozen else "none"
        raise StageFault(f"the run started under {started}, and its kind's PREREG frozen now is {now}: a run is only ever "
                         f"carried on under the PREREG it started under, so start a new run")


def graph_of(flow):
    """The flow's steps in order, as Metaflow sorts its graph."""
    graph = getattr(flow, "_graph", None)
    return list(getattr(graph, "sorted_nodes", None) or [])


class Beat:
    """A step's line on its run's progress page: running from its start, done or failed at its end,
    with its last LINES_KEPT lines; one file this task alone writes, so tasks never race on it."""

    def __init__(self, flow, label=None):
        self.root, self.flow, self.run = datastore_root(), current.flow_name, current.run_id
        self.steps = graph_of(flow)
        self.task = {"step": current.step_name, "task": str(current.task_id), "label": progress.one_line(label) or None, "state": "running",
                     "attempt": current.retry_count, "started": progress.utc_now(), "lines": []}
        self.said = False

    def __enter__(self):
        self.write()
        return self

    def __exit__(self, kind, error, _):
        if error is not None:
            words = (str(error).strip().splitlines() or [kind.__name__])[-1]
            self.task["lines"] = (self.task["lines"] + [f"fault, why: {kind.__name__}: {words}"])[-progress.LINES_KEPT:]
        self.task.update(state="failed" if error is not None else "done", ended=progress.utc_now())
        self.write()
        return False

    def passed(self):
        """The line of a step that only routes the flow, written done at once."""
        self.task.update(state="done", ended=progress.utc_now())
        self.write()

    def say(self, line):
        """A line of the work's own, the newest kept last; the page is drawn again with it. Whether
        it was new, and so written."""
        line = progress.one_line(line)
        if line and (not self.task["lines"] or self.task["lines"][-1] != line):
            self.task["lines"] = (self.task["lines"] + [line])[-progress.LINES_KEPT:]
            self.write()
            return True
        return False

    def tick(self, line_of):
        """The work's line while it runs, every few seconds: kept where it is new, and the task's
        time written again either way, since the page shows a run whose files stopped moving for
        SILENT_SECONDS as silent, and an epoch can last longer than that with nothing new to say.
        A line that cannot be read is said once on the step's log, and the work goes on."""
        try:
            line = line_of()
        except Exception as error:  # the work's card or files, never a reason to stop the work
            self.fault_once(error)
            line = None
        if not self.say(line):
            self.write()

    def write(self):
        try:
            self.task["updated"] = progress.utc_now()
            progress.write_graph(self.root, self.flow, self.run, self.steps)
            progress.write_task(self.root, self.flow, self.run, self.task)
            progress.draw(self.root, self.flow, self.run)
        except Exception as error:  # a page, whatever stops it, never fails the step it shows
            self.fault_once(error)

    def fault_once(self, error):
        if not self.said:
            print(f"{self.flow}: the progress page could not be written ({type(error).__name__}: {error}); the work goes on",
                  file=sys.stderr, flush=True)
        self.said = True


def run_watched(command, beat, line_of, every=BEAT_SECONDS, **popen):
    """A command run to its end with its output kept, the beat told line_of() every few seconds
    while it runs and once at its end, so the page moves with the work and shows it alive however
    long it says nothing new (Beat.tick); line_of may move the step's card too. (exit code,
    stdout, stderr)."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **popen)
    while True:
        try:
            out, err = process.communicate(timeout=every)
            break
        except subprocess.TimeoutExpired:
            beat.tick(line_of)
    beat.tick(line_of)
    return process.returncode, out, err


def tally_words(folder):
    """The report's counts in one line a checklist, as its claim.json and reforms.json give them."""
    words = []
    for name in REPORT_FILES:
        try:
            document = json.loads((Path(folder) / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        tally = document.get("tally") or {}
        counts = ", ".join(f"{tally.get(state, 0)} {state}" for state in ("met", "declared", "not applicable", "missing"))
        words.append(f"{document.get('checklist') or name}: {counts}")
    return "; ".join(words) or "no tally read"


def report_tool(action, folder, study=None):
    """tools/report.py's write or check of one run folder, run to its end with its output kept."""
    words = ["--run", str(folder), *(["--study", study] if study else [])]
    return subprocess.run([sys.executable, str(REPO / "tools" / "report.py"), action, *words], cwd=REPO,
                          capture_output=True, text=True)


def last_words(done):
    """A tool's last line, which says why it refused."""
    return ((done.stderr or done.stdout).strip().splitlines() or [f"exit {done.returncode}"])[-1]


def run_began():
    """When this Metaflow run began, in seconds since the epoch, as Metaflow registered it: a resume
    is a run of its own, so what its origin did comes before it. None where the client cannot say,
    which holds every folder to the run (claim_report)."""
    try:
        from metaflow import Run, namespace

        namespace(None)
        return Run(f"{current.flow_name}/{current.run_id}").created_at.timestamp()
    except Exception as error:  # the client's own errors have no common base worth naming
        print(f"{current.flow_name}: when this run began could not be read ({type(error).__name__}: {error}); "
              f"every report is held to this run", file=sys.stderr, flush=True)
        return None


def done_since(folder, began):
    """Whether a folder's work was done since the run began: its FINISHED.json, which tools/flow.py
    writes last, else the newest of the files at its top the report reads, every one but the
    report's own, written then or after. Where the run's start is not known or the folder shows no
    such file, its work counts as this run's, the stricter reading."""
    if began is None:
        return True
    folder = Path(folder)
    try:
        if (folder / FINISHED_MARK).is_file():
            return (folder / FINISHED_MARK).stat().st_mtime >= began
        times = [path.stat().st_mtime for path in folder.iterdir() if path.is_file() and path.name not in REPORT_OUTPUTS]
    except OSError:
        return True
    return not times or max(times) >= began


def claim_report(folder, study=None, began=None):
    """The report of one run folder held to the folder's files: (whether it is well, one line saying
    so with its counts). The check comes first: tools/report.py's check compares the report's files
    with what a write would render now, so a check right after a write always passes, and only the
    report the folder held says whether its run kept it current. began is when this Metaflow run
    began (run_began): a stale report of work done since then is the run's failure, and of work
    done before it is written anew and well (done_since); None holds every folder to the run. The
    reason, where there is one, comes last, after "why:", which the gate's status withholds where
    it quotes a path or a value."""
    name = Path(folder).name
    if not (Path(folder) / "claim.json").is_file():
        return report_written_now(folder, name, study)
    ours = done_since(folder, began)
    whose = "the run" if ours else "an earlier run"
    checked = report_tool("check", folder, study)
    if checked.returncode == 0:
        return True, f"{name}: current as {whose} wrote it; {tally_words(folder)}"
    wrote = report_tool("write", folder, study)
    if wrote.returncode != 0:
        return False, f"{name}: NOT CURRENT as {whose} wrote it, and not written anew; why: {last_words(checked)}"
    if not ours:
        return True, (f"{name}: written anew under the report tool as it is now, its work done before this run began; "
                      f"{tally_words(folder)}; it was not current, why: {last_words(checked)}")
    return False, f"{name}: NOT CURRENT as the run wrote it, so written anew; why: {last_words(checked)}"


def report_written_now(folder, name, study=None):
    """A run folder that holds no report, a run that ended before it wrote one: written here and
    then checked, which is all a check can say of a report written at the end."""
    wrote = report_tool("write", folder, study)
    if wrote.returncode != 0:
        return False, f"{name}: NOT WRITTEN at the end; why: {last_words(wrote)}"
    checked = report_tool("check", folder, study)
    if checked.returncode != 0:
        return False, f"{name}: NOT CURRENT once written at the end; why: {last_words(checked)}"
    return True, f"{name}: current, written at the end since the run left none; {tally_words(folder)}"


def finish(verdict, reports, none_words=None):
    """The run's verdict and its reports on the page, from end: reports as claim_report gives them,
    (current, line), with those not current first, since the gate's status shows only the first
    few lines, and how many are current; none_words the line where no report was checked."""
    root, flow, run = datastore_root(), current.flow_name, current.run_id
    failing = [line for ok, line in reports if not ok]
    lines = failing + [line for ok, line in reports if ok] or ([none_words] if none_words else [])
    result = {"verdict": verdict, "lines": lines, "reports": len(reports), "not_current": len(failing), "ended": progress.utc_now()}
    try:
        progress.write_result(root, flow, run, result)
        progress.draw(root, flow, run)
    except Exception as error:  # a page, whatever stops it, never fails the end step
        print(f"{flow}: the progress page could not be written ({type(error).__name__}: {error})", file=sys.stderr, flush=True)


def page_path():
    """Where the run's page lies, for the end step's card and log."""
    return progress.run_folder(datastore_root(), current.flow_name, current.run_id) / "index.html"
