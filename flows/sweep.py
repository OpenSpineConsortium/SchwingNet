"""SweepFlow: one plan of the block smoke test, every row a branch of a foreach (issue #252).

Started only by flows/launch.py (python flows/launch.py sweep -- --plan ... --catalog ... --out
...), which resumes the newest run of the same words, code and plan that did not finish, the
plan's bytes named by key_reads below; grid/sweep-driver.sbatch runs every row through that
launcher, so Metaflow's resume is the one way a sweep cut short is continued.

The work is tools/block_sweep.py's: start runs `prepare`, which makes the plan's state folder
and names the rows to run, those with no parent first and the warm starts second, since a warm
start reads its parent's train/best.pt. Each row is one branch of a foreach that runs `row`,
which runs the row through tools/flow.py and records what came of it against the check's
prediction, whatever came; end runs `results`. A row whose `row` could not run or record it
(exit 2, or any exit but 0) raises, is retried once at once (@retry), and is then caught
(@catch) and counted as a fault, so one row's fault never stops the others. A job killed
mid-row is resumed with every finished row cloned, the cut row run again, and tools/flow.py
carries that row on from its last epoch (tools/train.py --resume).

Each row's card refreshes every REFRESH seconds with the last line of its train/metrics.jsonl,
so `python flows/sweep.py card server` on the grid shows the row moving; end exports every card
it can find into the state folder's cards/ and writes METAFLOW.json there, which names this run.

The sweep trains networks, so it keeps the owner's rule of 2026-10-29 through flows/stage.py:
start holds the run to the block smoke test's frozen PREREG (docs/research/block-smoke/PREREG.md)
and end holds it there again, since a resume clones start; every step keeps its line on the
run's progress page, a row's line moving with its epochs; and end checks the CLAIM 2024 and
REFORMS report (tools/report.py) of every row that ran as the row left it: a row whose report is
not what its run gives, or cannot be written where the row left none, makes the verdict 1,
whatever the row did.

Where a list is empty, Metaflow 2.19's switch, a conditional next, steps past its foreach, which
Metaflow refuses over nothing.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, catch, current, retry, step
from metaflow.cards import Markdown, Table

import stage

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
BLOCK_SWEEP = REPO / "tools" / "block_sweep.py"
KIND = "sweep"
RAN = "ran"
REFRESH = 15
LAST_HOPS = 10
# What start keeps of the PREREG the run is held to (stage.hold_to_prereg), carried through both
# joins so end can hold the run to it again (stage.still_held).
PREREG_ARTIFACTS = ("prereg_path", "prereg_sha256", "prereg_part", "prereg_part_sha256")


class SweepFault(Exception):
    """block_sweep could not do what the step asked of it; the run's fault, not a row's outcome."""


def launcher_folder():
    """The folder the launcher was started in, which a relative path parameter is read from."""
    return Path(os.environ.get("SCHWINGNET_WORKDIR") or os.getcwd())


def from_launcher(path, folder=None):
    """A path parameter as the caller meant it: a relative one is read from the launcher's folder."""
    return str((folder or launcher_folder()) / path) if path and not Path(path).is_absolute() else path


def file_sha256(path):
    """The file's sha256, or None where it cannot be read."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def word_value(words, flag):
    """The value the words give a flag, the last one as click takes it; '' where they give none."""
    value, rest = "", list(words)
    while rest:
        word = rest.pop(0)
        if word == flag and rest:
            value = rest.pop(0)
        elif word.startswith(flag + "="):
            value = word[len(flag) + 1:]
    return value


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, for the launcher's key: the plan
    file's bytes, since start makes the state folder and its lists of rows from the plan and resume
    clones start, so an edited plan is never carried on as the plan it was. Read in the launcher,
    from its folder, as start reads the same word."""
    return [f"plan {file_sha256(from_launcher(word_value(words, '--plan'), folder)) or 'unreadable'}"]


def plan_part(plan_file):
    """The plan's name, grid/sweeps/<name>.json, the part of the sweep's PREREG a run of it is."""
    return Path(plan_file).stem if plan_file else ""


def prereg_part(words, folder):
    """The part a run of these words is, for the launcher: the plan's name and the sha256 of its
    bytes, which the smoke test's PREREG must cover, since a plan made again or edited since the
    freeze is another design under the same name; the trials are another design, with no PREREG
    yet. Read from the launcher's folder, as start reads the same word."""
    plan_file = from_launcher(word_value(words, "--plan"), folder)
    return plan_part(plan_file), file_sha256(plan_file)


def weights_words(weights):
    """The weights parameter, space-separated ARCH=FILE, as block_sweep's --weights values."""
    words = []
    for word in weights.split():
        arch, sep, file = word.partition("=")
        words.append(f"{arch}={from_launcher(file)}" if sep else from_launcher(word))
    return words


def json_line(text, key):
    """The last line of the text that is a JSON object holding the key."""
    for line in reversed(text.splitlines()):
        try:
            said = json.loads(line)
        except ValueError:
            continue
        if isinstance(said, dict) and key in said:
            return said
    return None


def block_sweep(args):
    """block_sweep run by path, its output printed into the step's log as it ended."""
    done = subprocess.run([sys.executable, str(BLOCK_SWEEP), *args], cwd=REPO, capture_output=True, text=True)
    print(done.stdout + done.stderr, end="", flush=True)
    return done


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def prediction_words(state, slug):
    """What the check said of the row, from the state's CHECK.json, for the card."""
    check = read_json(Path(state) / "CHECK.json") or {}
    row = next((r for r in check.get("rows", []) if isinstance(r, dict) and r.get("slug") == slug), None)
    if not row:
        return "The check's prediction for this row was not read."
    code = f" ({row['code']})" if row.get("code") else ""
    return f"The check predicts: {row.get('predicted')}{code}. {row.get('why') or ''}".strip()


def progress_words(state, slug, epochs):
    """The row's last epoch line, as its card shows it while it trains."""
    try:
        lines = (Path(state) / slug / "train" / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        line = json.loads(lines[-1]) if lines else None
    except (OSError, ValueError):
        line = None
    if not isinstance(line, dict):
        return "No epoch written yet."
    words = [f"epoch {line.get('epoch')}" + (f" of {epochs - 1}" if epochs else "")]
    for key in ("train_loss", "validation_accuracy", "validation_balanced_accuracy", "seconds"):
        value = line.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            words.append(f"{key.replace('_', ' ')} {value:.4g}")
    return "Last epoch: " + ", ".join(words) + "."


def outcome_words(entry):
    if not isinstance(entry, dict):
        return "No outcome was recorded."
    matched = {True: "matched the check", False: "DID NOT MATCH THE CHECK"}.get(entry.get("matched"), "not compared")
    code = f" ({entry['code']})" if entry.get("code") else ""
    return f"Outcome: {entry.get('outcome')}{code}, {matched}."


def row_command(flow):
    command = [sys.executable, str(BLOCK_SWEEP), "row", "--state", flow.state, "--slug", flow.slug,
               "--catalog", flow.catalog_file, "--environment", flow.environment]
    command += ["--epochs", str(flow.epochs)] if flow.epochs > 0 else []
    command += [part for word in flow.weights_words for part in ("--weights", word)]
    return command + (["--keep-epoch-weights"] if flow.keep_epoch_weights else [])


def run_row(flow):
    """One row through `block_sweep.py row`, its card and its line on the progress page moved
    with its epochs while it runs; a fault raises."""
    flow.slug = flow.input
    row_card = current.card["row"]
    row_card.append(Markdown(f"# {flow.slug}\n\n{prediction_words(flow.state, flow.slug)}"))
    progress = Markdown("Starting.")
    row_card.append(progress)
    row_card.refresh()

    def epoch_line():
        words = progress_words(flow.state, flow.slug, flow.plan_epochs)
        progress.update(words)
        row_card.refresh()
        return words

    with stage.Beat(flow, flow.slug) as beat:
        code, out, err = stage.run_watched(row_command(flow), beat, epoch_line, every=REFRESH, cwd=REPO)
        print(out + err, end="", flush=True)
        flow.entry = json_line(out, "outcome") if code == 0 else None
        if flow.entry is None:
            last = (err.strip().splitlines() or ["no output"])[-1]
            row_card.append(Markdown(f"Fault: block_sweep row exited {code}: {last}"))
            row_card.refresh()
            raise SweepFault(f"block_sweep row {flow.slug} exited {code} with no row recorded: {last}")
        row_card.append(Markdown(outcome_words(flow.entry)))
        beat.say(outcome_words(flow.entry))


def faults_of(inputs):
    """The rows a phase's @catch recorded, by slug, with the fault's last line."""
    found = []
    for branch in inputs:
        fault = getattr(branch, "fault", None)
        if fault is not None:
            words = (str(fault).strip().splitlines() or ["a fault"])[-1]
            found.append({"slug": getattr(branch, "slug", None) or branch.input, "fault": words})
    return found


def card_html(task):
    """A task's row card, or its origin's for a task resume cloned, which made none of its own."""
    from metaflow import Task
    from metaflow.cards import get_cards

    for _ in range(LAST_HOPS):
        try:
            cards = get_cards(task, id="row")
            if len(cards):
                return cards[0].get()
        except Exception:  # Metaflow raises for a task with no card; best-effort, said below
            pass
        origin = getattr(task, "origin_pathspec", None)
        if not origin:
            return None
        task = Task(origin)
    return None


def export_cards(pathspec, state):
    """Every row card of the run into STATE/cards/<step>-<slug>.html; a missing one in one line."""
    from metaflow import Run, namespace

    namespace(None)
    folder = Path(state) / "cards"
    folder.mkdir(parents=True, exist_ok=True)
    run = Run(pathspec)
    for name in ("first", "second"):
        try:
            tasks = list(run[name])
        except Exception:  # a step its switch stepped past has no tasks
            continue
        for task in tasks:
            try:
                slug = task["slug"].data
            except Exception:
                slug = task.id
            html = card_html(task)
            if html is None:
                print(f"sweep: no card found for {name} {slug} (task {task.pathspec})", flush=True)
            else:
                (folder / f"{name}-{slug}.html").write_text(html, encoding="utf-8")


def number_words(value):
    return "-" if not isinstance(value, (int, float)) or isinstance(value, bool) else f"{value:.3f}"


def results_rows(results):
    rows = []
    for e in results.get("rows", []):
        predicted = str(e.get("predicted")) + (f" ({e['predicted_code']})" if e.get("predicted_code") else "")
        outcome = str(e.get("outcome")) + (f" ({e['code']})" if e.get("code") else "")
        matched = {True: "matched", False: "MISMATCHED"}.get(e.get("matched"), "-")
        rows.append([str(e.get("slug")), str(e.get("role")), predicted, outcome, matched,
                     number_words(e.get("validation_accuracy")), number_words(e.get("test_accuracy")),
                     " ".join(e.get("wandb") or []) or "-"])
    return rows


def verdict_of(results, faults, reports):
    """0 when every row was recorded and did what the check predicted, and every row that ran
    has its report current, else 1."""
    counts = results.get("counts", {})
    clean = all(counts.get(key) == 0 for key in ("failed", "mismatched", "to_come"))
    return 0 if clean and not faults and all(ok for ok, _ in reports) else 1


def row_reports(state, results):
    """The CLAIM 2024 and REFORMS report of every row that ran, each checked in the row's own run
    folder, where tools/flow.py wrote it after the row's last step, and written there only where
    the row left none (stage.claim_report): (current, line)."""
    return [stage.claim_report(Path(state) / entry["slug"]) for entry in results.get("rows", [])
            if isinstance(entry, dict) and entry.get("outcome") == RAN]


class SweepFlow(FlowSpec):
    """One smoke plan: prepare, the rows with no parent, the warm starts, the results."""

    plan = Parameter("plan", required=True, help="the plan file, grid/sweeps/<plan>.json")
    catalog = Parameter("catalog", required=True, help="the catalog file the rows train on")
    out = Parameter("out", required=True, help="the smoke root the state folder is made under")
    environment = Parameter("environment", default="train-gpu", help="the pixi environment a row trains in")
    epochs = Parameter("epochs", type=int, default=0, help="epochs per row; 0 for the plan's")
    weights = Parameter("weights", default="", help="space-separated ARCH=FILE, the ImageNet files")
    keep_epoch_weights = Parameter("keep-epoch-weights", type=bool, default=False,
                                   help="keep each row's train/epochs/*.pt")
    commit = Parameter("commit", default="", help="the commit of the checkout that first started the run, which the launcher passes")

    @step
    def start(self):
        """The run held to the frozen PREREG, then block_sweep prepare: the state folder, and the
        two lists of rows to run."""
        with stage.Beat(self, "prepare") as beat:
            self.plan_file, self.catalog_file = from_launcher(self.plan), from_launcher(self.catalog)
            stage.hold_to_prereg(self, KIND, plan_part(self.plan_file), file_sha256(self.plan_file))
            self.out_root, self.weights_words = from_launcher(self.out), weights_words(self.weights)
            plan = read_json(self.plan_file) or {}
            self.plan_epochs = self.epochs or (plan.get("epochs") if isinstance(plan.get("epochs"), int) else 0)
            args = ["prepare", "--plan", self.plan_file, "--catalog", self.catalog_file, "--out", self.out_root]
            args += ["--epochs", str(self.epochs)] if self.epochs > 0 else []
            done = block_sweep(args + [part for word in self.weights_words for part in ("--weights", word)])
            prepared = json_line(done.stdout, "state") if done.returncode == 0 else None
            if prepared is None:
                raise SweepFault(f"block_sweep prepare exited {done.returncode} and named no state folder")
            self.state = prepared["state"]
            self.first_rows, self.second_rows = list(prepared["first"]), list(prepared["second"])
            self.faults = []
            said = f"state {self.state}, {len(self.first_rows)} rows first, {len(self.second_rows)} warm starts after"
            print(f"SweepFlow: {said}", flush=True)
            beat.say(said)
        self.first_route = "rows" if self.first_rows else "none"
        self.next({"rows": self.fan_first, "none": self.middle}, condition="first_route")

    @step
    def fan_first(self):
        stage.Beat(self).passed()
        self.next(self.first, foreach="first_rows")

    @catch(var="fault")
    @retry(times=1, minutes_between_retries=0)
    @card(type="blank", id="row", refresh_interval=REFRESH)
    @step
    def first(self):
        """A row with no parent."""
        run_row(self)
        self.next(self.join_first)

    @step
    def join_first(self, inputs):
        with stage.Beat(self):
            self.merge_artifacts(inputs, include=["state", "catalog_file", "weights_words", "plan_epochs", "second_rows", "faults",
                                                  *PREREG_ARTIFACTS])
            self.faults = self.faults + faults_of(inputs)
        self.next(self.middle)

    @step
    def middle(self):
        """The warm starts come only now, since each reads a parent's train/best.pt."""
        with stage.Beat(self):
            self.second_route = "rows" if self.second_rows else "none"
        self.next({"rows": self.fan_second, "none": self.end}, condition="second_route")

    @step
    def fan_second(self):
        stage.Beat(self).passed()
        self.next(self.second, foreach="second_rows")

    @catch(var="fault")
    @retry(times=1, minutes_between_retries=0)
    @card(type="blank", id="row", refresh_interval=REFRESH)
    @step
    def second(self):
        """A warm start, after its parent."""
        run_row(self)
        self.next(self.join_second)

    @step
    def join_second(self, inputs):
        with stage.Beat(self):
            self.merge_artifacts(inputs, include=["state", "faults", *PREREG_ARTIFACTS])
            self.faults = self.faults + faults_of(inputs)
        self.next(self.end)

    @card(type="blank")
    @step
    def end(self):
        """The run held to the PREREG start kept, whatever resumed it; block_sweep results, every
        row's report checked, the verdict, METAFLOW.json, the cards, the results card and the
        progress page's last lines."""
        with stage.Beat(self, "results") as beat:
            stage.still_held(self, KIND)
            done = block_sweep(["results", self.state])
            results = read_json(Path(self.state) / "results.json") if done.returncode == 0 else None
            if results is None:
                raise SweepFault(f"block_sweep results exited {done.returncode} and left no results.json in {self.state}")
            self.counts = results.get("counts", {})
            reports = row_reports(self.state, results)
            self.reports = [line for _, line in reports]
            self.verdict = verdict_of(results, self.faults, reports)
            pathspec = f"{current.flow_name}/{current.run_id}"
            root = os.environ.get("METAFLOW_DATASTORE_SYSROOT_LOCAL") or os.getcwd()
            record = {"flow": "SweepFlow", "run": pathspec, "root": root, "page": str(stage.page_path())}
            (Path(self.state) / "METAFLOW.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            export_cards(pathspec, self.state)
            for fault in self.faults:
                print(f"SweepFlow: FAULT in row {fault['slug']}: {fault['fault']}", flush=True)
            for line in self.reports:
                print(f"SweepFlow: report {line}", flush=True)
            said = f"{json.dumps(self.counts, sort_keys=True)}, faults {len(self.faults)}, verdict {self.verdict}"
            print(f"SweepFlow: {said}", flush=True)
            beat.say(said)
            stage.finish(self.verdict, reports, "no row ran, so no row has a report to check")
        current.card.append(Markdown(f"# Smoke plan {results.get('plan')}\n\nState {self.state}; counts "
                                     f"{json.dumps(self.counts, sort_keys=True)}; faults {len(self.faults)}; verdict {self.verdict}. "
                                     f"Progress page: {stage.page_path()}."))
        current.card.append(Table(results_rows(results), headers=["row", "role", "predicted", "outcome", "matched",
                                                                  "validation", "test", "W&B"]))
        current.card.append(Markdown("## CLAIM 2024 and REFORMS reports\n\n" + "\n".join(f"- {line}" for line in self.reports)
                                     if self.reports else "No row ran, so no row has a report to check."))


if __name__ == "__main__":
    SweepFlow()
