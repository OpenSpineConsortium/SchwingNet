"""ExperimentFlow: one requested combination of data and blocks as a launched flow (issue #248; the
owner's rule of 2026-10-29).

Started only by flows/launch.py (python flows/launch.py experiment -- --issue N --request FILE
--catalog ... --out ... --weights ... --epochs ... --seed ... --hours ... --recipe ... --blocks ...),
which grid/experiment-driver.sbatch runs on the GPU Slurm gave it, once it has read the request
the gate fetched from the branch experiments, checked its values against this checkout's blocks
and recipes, chosen the catalog version and checked its split again. The launcher resumes the
newest run of the same words, code, request, catalog, weights and PREREG that did not finish, the
request's, the catalog's and the weights' bytes named by key_reads below.

The work is tools/flow.py run's, as version 1's is (flows/v1.py), in local mode with the train-gpu
environment: one step, train_evaluate, runs it whole by the shared helpers of flows/flow_tool.py,
with the request's recipe, epochs, seed, hours and block words. tools/flow.py names the run's
folder by its code, catalog and configuration and carries a run cut short on from where it stopped,
so the step retried once at once (@retry), or run again by a resume, loses at most the epoch in
progress.

The run trains a network, so it keeps the owner's rule through flows/stage.py: start holds the run
to the frozen PREREG of docs/research/experiments/, which pre-registers every requested
combination as an estimate with no bar, its configuration the request recorded before the run;
the step's line on the run's progress page and its card move with the trainer's
train/metrics.jsonl every REFRESH seconds; end holds the run to that PREREG again
(stage.still_held, since a resume clones start), writes and checks the run's CLAIM 2024 and
REFORMS report in its folder (tools/report.py), strict for work done since this Metaflow run
began, and the verdict is 0 only where tools/flow.py finished the run and its report is current.
end writes METAFLOW.json into the run's folder, which names this Metaflow run, its page and the
request it ran.
"""

import json
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, retry, step
from metaflow.cards import Markdown

import flow_tool
import stage
from flow_tool import FINISHED_MARK, file_sha256, from_launcher

KIND = "experiment"
REFRESH = flow_tool.REFRESH


class ExperimentFault(Exception):
    """tools/flow.py could not run the run to its end; the step's fault, retried once."""


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, for the launcher's key: the
    request's bytes, which the words restate, and the catalog's and the weights' bytes, by which
    tools/flow.py names the run, so a file replaced at the same path is never carried on as the
    one it was."""
    request = flow_tool.word_value(words, "--request")
    return [f"request {file_sha256(from_launcher(request, folder))}"] + flow_tool.inputs_read(words, folder)


IMAGENET_ARCHITECTURE = "resnet18"


def request_values(path):
    """The request's values in the driver's line grammar (grid/experiment-driver.sbatch): recipe,
    epochs, seed and hours once each, block lines in order; a line of another shape is refused."""
    values, blocks = {"recipe": "none"}, []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(": ")
        if key == "block":
            blocks.append(value)
        elif key in ("recipe", "epochs", "seed", "hours"):
            values[key] = value
        else:
            raise ExperimentFault(f"the request's line {line[:60]!r} is not one the gate takes")
    values["blocks"] = " ".join(blocks)
    return values


def request_disagreements(values, flow):
    """Each word the run was given that differs from its request, so a hand launch never trains one
    configuration and records another."""
    given = {"recipe": flow.recipe, "epochs": str(flow.epochs), "seed": str(flow.seed), "hours": str(flow.hours),
             "blocks": " ".join(flow.blocks.split())}
    return [f"{key}: the request says {values.get(key, 'nothing')!r}, the run was given {given[key]!r}"
            for key in given if values.get(key) != given[key]]


def architecture_refusal(blocks):
    """The words that refuse a request for an architecture with no ImageNet file on the grid, else
    nothing: every requested combination starts from ImageNet, as version 1 does."""
    for word in blocks.split():
        key, _, value = word.partition("=")
        if key == "architecture" and value != IMAGENET_ARCHITECTURE:
            return f"architecture={value}: no ImageNet file for it on the grid, so the request waits for one"
    return ""


def record_name(folder, issue):
    """METAFLOW.json where the run's folder holds none or one of this issue's ExperimentFlow; else a
    file of the issue's own beside it, so a request that equals version 1's never overwrites the
    record of the V1Flow run that made the folder."""
    record = Path(folder) / "METAFLOW.json"
    if not record.is_file():
        return record.name
    try:
        held = json.loads(record.read_text(encoding="utf-8"))
    except ValueError:
        held = {}
    if held.get("flow") == "ExperimentFlow" and held.get("issue") == issue:
        return record.name
    return f"METAFLOW-experiment-{issue}.json"


def block_words(blocks):
    """The request's KEY=VALUE words, one --block each, as tools/flow.py takes them."""
    words = []
    for word in blocks.split():
        words += ["--block", word]
    return words


def flow_command(flow):
    command = flow_tool.flow_tool_head(flow.catalog_file, flow.out_root, flow.environment, flow.epochs, flow.seed)
    command += ["--hours", flow.hours, "--weights", flow.weights_file]
    command += [] if flow.recipe == "none" else ["--recipe", flow.recipe]
    return command + block_words(flow.blocks)


def verdict_of(finished, report_ok):
    """0 where tools/flow.py finished the run and its report is current, else 1."""
    return 0 if finished and report_ok else 1


class ExperimentFlow(FlowSpec):
    """One requested combination: held to its PREREG, trained and evaluated by tools/flow.py, reported."""

    issue = Parameter("issue", type=int, required=True, help="the issue labelled experiment that asked for the run")
    request = Parameter("request", required=True, help="the request's lines as the gate fetched them from the branch experiments")
    catalog = Parameter("catalog", required=True, help="the catalog file the run trains and is evaluated on")
    out = Parameter("out", required=True, help="the runs root tools/flow.py makes the run's folder under")
    weights = Parameter("weights", required=True, help="the ImageNet file the trainer starts from")
    epochs = Parameter("epochs", type=int, required=True, help="epochs to train, as the request says")
    seed = Parameter("seed", type=int, required=True, help="the seed every random source draws from, as the request says")
    hours = Parameter("hours", required=True, help="the training's hours, as the request says")
    recipe = Parameter("recipe", default="none", help="the recipe under data/recipes/ the request names, or none")
    blocks = Parameter("blocks", default="", help="the request's KEY=VALUE block words, separated by spaces")
    environment = Parameter("environment", default="train-gpu", help="the pixi environment the steps run in")
    commit = Parameter("commit", default="", help="the commit of the checkout that first started the run, which the launcher passes")

    @step
    def start(self):
        """The run held to the frozen PREREG, and the files it reads named by their bytes."""
        with stage.Beat(self, "prepare") as beat:
            stage.hold_to_prereg(self, KIND)
            self.request_file = from_launcher(self.request)
            self.catalog_file, self.out_root = from_launcher(self.catalog), from_launcher(self.out)
            self.weights_file = from_launcher(self.weights)
            self.request_sha256 = file_sha256(self.request_file)
            refused = architecture_refusal(self.blocks)
            if refused:
                raise ExperimentFault(refused)
            differ = request_disagreements(request_values(self.request_file), self)
            if differ:
                raise ExperimentFault("the run's words are not its request's: " + "; ".join(differ))
            self.catalog_sha256 = file_sha256(self.catalog_file)
            self.weights_sha256 = file_sha256(self.weights_file)
            said = (f"issue #{self.issue}: recipe {self.recipe}, {self.epochs} epochs, seed {self.seed}, "
                    f"blocks {self.blocks or 'none (version 1)'}, catalog {Path(self.catalog_file).name}")
            print(f"ExperimentFlow: {said}", flush=True)
            beat.say(said)
        self.next(self.train_evaluate)

    @retry(times=1, minutes_between_retries=0)
    @card(type="blank", id="run", refresh_interval=REFRESH)
    @step
    def train_evaluate(self):
        """tools/flow.py run, in local mode: the record, training and the evaluation, carried on
        from where an earlier start stopped."""
        title = (f"# Experiment #{self.issue}\n\nRecipe {self.recipe}, blocks {self.blocks or 'none (version 1)'}, "
                 f"{self.epochs} epochs, seed {self.seed}, catalog {Path(self.catalog_file).name}.")
        self.run_id, self.run_dir = flow_tool.run_flow_tool(self, flow_command(self), self.out_root, self.epochs, title,
                                                             ExperimentFault)
        self.next(self.end)

    @card(type="blank")
    @step
    def end(self):
        """The run's report written and checked, the verdict, METAFLOW.json and the page's last lines."""
        with stage.Beat(self, "report") as beat:
            stage.still_held(self, KIND)
            print(json.dumps({"run_id": self.run_id, "run_dir": self.run_dir}), flush=True)
            folder = Path(self.run_dir)
            request_now = file_sha256(self.request_file)
            request_held = request_now == self.request_sha256
            moved = [] if request_held else [(False, f"the request file changed during the run: sha256 "
                                                     f"{self.request_sha256[:12]} at start, {request_now[:12]} at the end")]
            finished = (folder / FINISHED_MARK).is_file()
            report_ok, report = stage.claim_report(folder, began=stage.run_began())
            self.report = report
            self.verdict = verdict_of(finished and request_held, report_ok)
            pathspec = f"{current.flow_name}/{current.run_id}"
            record = {"flow": "ExperimentFlow", "run": pathspec, "root": stage.datastore_root(), "page": str(stage.page_path()),
                      "issue": self.issue, "request_sha256": self.request_sha256}
            (folder / record_name(folder, self.issue)).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            unfinished = [] if finished else [(False, f"{folder.name}: no {FINISHED_MARK}, so tools/flow.py did not finish the run")]
            print(f"ExperimentFlow: report {report}", flush=True)
            print(f"ExperimentFlow: run {self.run_id}, verdict {self.verdict}", flush=True)
            beat.say(f"verdict {self.verdict}")
            stage.finish(self.verdict, unfinished + moved + [(report_ok, report)])
        current.card.append(Markdown(f"# Experiment #{self.issue}, run {self.run_id}\n\nFolder {self.run_dir}; verdict "
                                     f"{self.verdict}. Report: {report}. Progress page: {stage.page_path()}."))


if __name__ == "__main__":
    ExperimentFlow()
