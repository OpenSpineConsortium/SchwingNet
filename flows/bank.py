"""BankFlow: stage 2 of the X-ray chain, bank and ingest, as a Metaflow flow (issue #252).

Started only by flows/launch.py (python flows/launch.py bank -- --sources "<ids>" ...), which
resumes the newest run of the same words and commit that did not finish. grid/02-bank-ingest.sbatch
execs that launcher whenever Slurm runs it, so every job of stage 2 runs here.

The work is the stage's own: each step runs grid/02-bank-ingest.sbatch for one recipe and one half
of its loop body (PART=bank, then PART=ingest), with SCHWINGNET_FLOW_STEP=1 so the script runs its
body rather than the launcher again. What Metaflow adds is where a cut job starts again: one
branch of a foreach per recipe and one step per half, so a job killed mid-ingest is resumed at
that recipe's ingest with its bank cloned, and every recipe that finished is cloned whole. A
stage's refusal (a bank or an ingest refused) is its own report line, recorded and not raised,
as the stage recorded it before; only a kill or a crash of the step itself fails the run.

When no recipe has a raw copy, start goes straight to end by Metaflow 2.19's switch, a
conditional next, since a foreach over nothing is refused; end writes the stage's report
either way, logs/02-bank-ingest-STAGE-REPORT.md under the launcher's working folder, in the
stage's words, so the gate's status reads it where it always did.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step
from metaflow.cards import Markdown, Table

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
STAGE = REPO / "grid" / "02-bank-ingest.sbatch"
REPORT = Path("logs") / "02-bank-ingest-STAGE-REPORT.md"
ALL_WELL = "Every recipe that had a raw copy was banked and ingested."
SOME_FAILED = ("Some recipes failed; the lines above say which, the job's log, which the gate word "
               "status shows, says why.")
TO_CONFIRM = ("A recipe spelled 'to confirm' is filled in from the page, by pull request, and the gate "
              "word fetch <id> runs this stage again for that id.")


def launcher_folder():
    """The folder the launcher was started in, where the stage's report has always been written."""
    return Path(os.environ.get("SCHWINGNET_WORKDIR") or os.getcwd())


def from_launcher(path):
    """A path parameter as the caller meant it: a relative one is read from the launcher's folder."""
    return str(launcher_folder() / path) if path and not Path(path).is_absolute() else path


def raw_of(recipe, identity, data_root):
    """The recipe's raw folder as the stage reads it; a recipe that cannot be read names none,
    which the stage reports as nothing fetched, as its own reading gives an empty path."""
    if data_root:
        return f"{data_root}/{identity}/raw"
    try:
        return str(json.loads(recipe.read_text(encoding="utf-8"))["raw"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def fetched(raw):
    """The stage's test: a folder with anything in it."""
    folder = Path(raw) if raw else None
    try:
        return bool(folder) and folder.is_dir() and any(folder.iterdir())
    except OSError:
        return False


def short_commit():
    """The commit as the stage writes it, 0000000 where git cannot say, so the report reads as it always did."""
    try:
        done = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    except OSError:
        return "0000000"
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else "0000000"


def step_folder(identity, part):
    """A working folder of the step's own under the run's, so each recipe's half writes its own
    report and none reads another's; under the datastore root, which the launcher runs in."""
    root = Path(os.environ.get("METAFLOW_DATASTORE_SYSROOT_LOCAL") or os.getcwd())
    folder = root / "work" / current.flow_name / str(current.run_id) / identity / part
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def run_stage(identity, part, ingest_date, data_root, banks):
    """One half of the stage's loop body for one recipe: its output, exit code and report lines."""
    folder = step_folder(identity, part)
    env = dict(os.environ, SCHWINGNET=str(REPO), ONLY=identity, PART=part, INGEST_DATE=ingest_date,
               DATA_ROOT=data_root, BANKS=banks, SCHWINGNET_FLOW_STEP="1")
    done = subprocess.run(["bash", str(STAGE)], cwd=folder, env=env, capture_output=True, text=True)
    output = done.stdout + done.stderr
    print(output, end="" if output.endswith("\n") else "\n", flush=True)
    try:
        report = (folder / REPORT).read_text(encoding="utf-8")
    except OSError:
        report = ""
    lines = [line for line in report.splitlines() if line.startswith(f"- {identity}: ")]
    return output, done.returncode, lines


def last_counts(output):
    """The plain values of the last JSON object the tool printed (bank.py's counts, ingest's
    summary, which it indents over many lines), for the card; nothing where it printed none."""
    decoder, found, at = json.JSONDecoder(), None, 0
    while (at := output.find("{", at)) >= 0:
        if at == 0 or output[at - 1] == "\n":
            try:
                said, end = decoder.raw_decode(output, at)
            except ValueError:
                said, end = None, at + 1
            found = said if isinstance(said, dict) else found
            at = max(end, at + 1)
        else:
            at += 1
    if not found:
        return []
    return [[key, str(value)] for key, value in sorted(found.items()) if isinstance(value, (int, float, str))]


def stamp():
    """The time as the stage's date '+%F %T' writes it."""
    return f"{datetime.now():%Y-%m-%d %H:%M:%S}"


def is_skipped(lines):
    return any(" skipped, nothing fetched under " in line for line in lines)


def report_text(order, lines, failed, short, ingest_date):
    """logs/02-bank-ingest-STAGE-REPORT.md as the stage writes it, a line per recipe in order."""
    out = [f"# Stage 2, bank and ingest: {stamp()}", "",
           f"Code commit {short}, ingest date {ingest_date}; one line per recipe under grid/banks/.", ""]
    for identity in order:
        out += lines.get(identity, [])
    out += ["", SOME_FAILED if failed else ALL_WELL, TO_CONFIRM]
    return "\n".join(out) + "\n"


def write_whole(path, text):
    """Written beside and renamed into place, so the gate's status never reads half a report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(text, encoding="utf-8")
    os.replace(part, path)


def half_card(identity, part, code, lines, output):
    current.card.append(Markdown(f"# {identity}: {part}"))
    current.card.append(Markdown(f"The stage's {part} half exited {code}."))
    current.card.append(Markdown("\n".join(lines) if lines else "No report line from this half."))
    counts = last_counts(output)
    if counts:
        current.card.append(Table(counts, headers=["count", "value"]))


class BankFlow(FlowSpec):
    """Stage 2 of the X-ray chain: each recipe's raw copy into a bank, each bank into a shard."""

    sources = Parameter("sources", default="", help="space-separated recipe ids; empty for every recipe")
    date = Parameter("date", default="", help="the ingest date, chosen once per run by the launcher")
    data_root = Parameter("data-root", default="", help="each source under <root>/<id>/ (issue #40)")
    banks = Parameter("banks", default="", help="the recipe folder; empty for grid/banks")
    commit = Parameter("commit", default="", help="the checkout's commit, which the launcher passes")

    @step
    def start(self):
        """The recipes as the stage lists them; one with no raw copy is its skipped line now."""
        self.banks_folder = from_launcher(self.banks) or str(REPO / "grid" / "banks")
        self.data_folder = from_launcher(self.data_root)
        self.ingest_date = self.date or datetime.now().date().isoformat()
        self.short_commit = short_commit()
        wanted = self.sources.split()
        self.order, self.lines, self.todo = [], {}, []
        for recipe in sorted(Path(self.banks_folder).glob("*.json")):
            identity = recipe.stem
            # bash's glob, which the stage lists the recipes with, takes no dot file
            if identity.startswith(".") or (wanted and identity not in wanted):
                continue
            self.order.append(identity)
            raw = raw_of(recipe, identity, self.data_folder)
            if fetched(raw):
                self.todo.append(identity)
            else:
                self.lines[identity] = [f"- {identity}: skipped, nothing fetched under {raw}"]
        self.failed = []
        self.route = "bank" if self.todo else "none"
        print(f"BankFlow: {len(self.order)} recipes, {len(self.todo)} with a raw copy, date {self.ingest_date}", flush=True)
        self.next({"bank": self.fan, "none": self.end}, condition="route")

    @step
    def fan(self):
        self.next(self.bank, foreach="todo")

    @card(type="blank")
    @step
    def bank(self):
        """The bank half for one recipe: tools/bank.py --run on its raw copy."""
        self.source = self.input
        self.bank_output, self.bank_code, self.bank_lines = run_stage(
            self.source, "bank", self.ingest_date, self.data_folder, self.banks_folder)
        half_card(self.source, "bank", self.bank_code, self.bank_lines, self.bank_output)
        self.next(self.ingest)

    @card(type="blank")
    @step
    def ingest(self):
        """The ingest half: the bank into a shard, skipped where the bank half refused."""
        if self.bank_code != 0:
            self.ingest_output, self.ingest_code, self.ingest_lines = "", None, []
            current.card.append(Markdown(f"# {self.source}: ingest\n\nNot run: the bank half refused."))
        else:
            self.ingest_output, self.ingest_code, self.ingest_lines = run_stage(
                self.source, "ingest", self.ingest_date, self.data_folder, self.banks_folder)
            half_card(self.source, "ingest", self.ingest_code, self.ingest_lines, self.ingest_output)
        self.next(self.join)

    @step
    def join(self, inputs):
        """Each recipe's lines beside the skipped ones, and which recipes failed."""
        self.merge_artifacts(inputs, include=["order", "short_commit", "ingest_date", "banks_folder", "data_folder"])
        self.lines = dict(inputs[0].lines)
        self.failed = []
        for branch in inputs:
            # a raw copy gone between start and the bank half is skipped by both halves alike
            self.lines[branch.source] = branch.bank_lines + [line for line in branch.ingest_lines if line not in branch.bank_lines]
            if branch.bank_code != 0 or branch.ingest_code not in (0, None):
                self.failed.append(branch.source)
        self.next(self.end)

    @card(type="blank")
    @step
    def end(self):
        """The stage's report, written where the stage wrote it, printed with its exit line."""
        report = report_text(self.order, self.lines, self.failed, self.short_commit, self.ingest_date)
        write_whole(launcher_folder() / REPORT, report)
        self.verdict = 1 if self.failed else 0
        print(report, end="", flush=True)
        print(f"XR_BANK_RC={self.verdict} {stamp()}", flush=True)
        skipped = [i for i in self.order if is_skipped(self.lines.get(i, []))]
        banked = [i for i in self.order if i not in self.failed and i not in skipped]
        current.card.append(Markdown(f"# Stage 2, bank and ingest\n\nIngest date {self.ingest_date}, commit {self.short_commit}."))
        current.card.append(Table([["recipes", str(len(self.order))], ["banked and ingested", str(len(banked))],
                                   ["skipped", str(len(skipped))],
                                   ["refused", str(len(self.failed))]], headers=["recipes", "count"]))
        current.card.append(Markdown(report))


if __name__ == "__main__":
    BankFlow()
