"""V1Flow: the version 1 run on real frames as a launched flow (issue #53; the owner's rule of 2026-10-29).

Started only by flows/launch.py (python flows/launch.py v1 -- --catalog ... --out ... --weights
...), which grid/v1-driver.sbatch runs on the GPU Slurm gave it once it has chosen the catalog
version and checked its split again. The launcher resumes the newest run of the same words, code,
catalog, weights and PREREG that did not finish, the catalog's and the weights' bytes named by
key_reads below.

The work is tools/flow.py run's, in local mode with the train-gpu environment: one step,
train_evaluate, runs it whole, its train and evaluate steps one after the other, by the helpers
ExperimentFlow shares (flows/flow_tool.py). tools/flow.py names
the run's folder by its code, catalog and configuration and carries a run cut short on from where
it stopped (the last epoch's train/last.pt, or only what came after an evaluation that ended), so
the step retried once at once (@retry), or run again by a resume, loses at most the epoch in
progress.

The run trains a network, so it keeps the owner's rule through flows/stage.py: start holds the run
to the frozen PREREG of docs/research/v1-demo/; the step's line on the run's progress page and its
card move with the trainer's train/metrics.jsonl every REFRESH seconds; end writes and checks the
run's CLAIM 2024 and REFORMS report in its folder (tools/report.py), and the verdict is 0 only where
tools/flow.py finished the run and its report is current. end writes METAFLOW.json into the run's
folder, which names this Metaflow run and its page.
"""

import json
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, retry, step
from metaflow.cards import Markdown

import flow_tool
import stage
from flow_tool import FINISHED_MARK, file_sha256, from_launcher

KIND = "v1"
REFRESH = flow_tool.REFRESH


class V1Fault(Exception):
    """tools/flow.py could not run the run to its end; the step's fault, retried once."""


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, for the launcher's key: the
    catalog's and the weights' bytes, by which tools/flow.py names the run, so a file replaced at
    the same path is never carried on as the one it was."""
    return flow_tool.inputs_read(words, folder)


def flow_command(flow):
    command = flow_tool.flow_tool_head(flow.catalog_file, flow.out_root, flow.environment, flow.epochs, flow.seed)
    return command + (["--weights", flow.weights_file] if flow.weights_file else [])


def verdict_of(finished, report_ok):
    """0 where tools/flow.py finished the run and its report is current, else 1."""
    return 0 if finished and report_ok else 1


class V1Flow(FlowSpec):
    """The version 1 run: held to its PREREG, trained and evaluated by tools/flow.py, reported."""

    catalog = Parameter("catalog", required=True, help="the catalog file the run trains and is evaluated on")
    out = Parameter("out", required=True, help="the runs root tools/flow.py makes the run's folder under")
    weights = Parameter("weights", default="", help="the ImageNet file the trainer starts from")
    epochs = Parameter("epochs", type=int, default=20, help="epochs to train")
    seed = Parameter("seed", type=int, default=1, help="the seed every random source draws from")
    environment = Parameter("environment", default="train-gpu", help="the pixi environment the steps run in")
    commit = Parameter("commit", default="", help="the commit of the checkout that first started the run, which the launcher passes")

    @step
    def start(self):
        """The run held to the frozen PREREG, and the files it reads named by their bytes."""
        with stage.Beat(self, "prepare") as beat:
            stage.hold_to_prereg(self, KIND)
            self.catalog_file, self.out_root = from_launcher(self.catalog), from_launcher(self.out)
            self.weights_file = from_launcher(self.weights)
            self.catalog_sha256 = file_sha256(self.catalog_file)
            self.weights_sha256 = file_sha256(self.weights_file) if self.weights_file else None
            said = f"catalog {Path(self.catalog_file).name}, {self.epochs} epochs, seed {self.seed}"
            print(f"V1Flow: {said}", flush=True)
            beat.say(said)
        self.next(self.train_evaluate)

    @retry(times=1, minutes_between_retries=0)
    @card(type="blank", id="run", refresh_interval=REFRESH)
    @step
    def train_evaluate(self):
        """tools/flow.py run, in local mode: the record, training and the evaluation, carried on
        from where an earlier start stopped."""
        title = f"# Version 1\n\nCatalog {Path(self.catalog_file).name}, {self.epochs} epochs, seed {self.seed}."
        self.run_id, self.run_dir = flow_tool.run_flow_tool(self, flow_command(self), self.out_root, self.epochs, title, V1Fault)
        self.next(self.end)

    @card(type="blank")
    @step
    def end(self):
        """The run's report written and checked, the verdict, METAFLOW.json and the page's last lines."""
        with stage.Beat(self, "report") as beat:
            folder = Path(self.run_dir)
            finished = (folder / FINISHED_MARK).is_file()
            report_ok, report = stage.claim_report(folder)
            self.report = report
            self.verdict = verdict_of(finished, report_ok)
            pathspec = f"{current.flow_name}/{current.run_id}"
            record = {"flow": "V1Flow", "run": pathspec, "root": stage.datastore_root(), "page": str(stage.page_path())}
            (folder / "METAFLOW.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            lines = [report] + ([] if finished else [f"{folder.name}: no {FINISHED_MARK}, so tools/flow.py did not finish the run"])
            print(f"V1Flow: report {report}", flush=True)
            print(f"V1Flow: run {self.run_id}, verdict {self.verdict}", flush=True)
            beat.say(f"verdict {self.verdict}")
            stage.finish(self.verdict, lines)
        current.card.append(Markdown(f"# Version 1, run {self.run_id}\n\nFolder {self.run_dir}; verdict {self.verdict}. "
                                     f"Report: {report}. Progress page: {stage.page_path()}."))


if __name__ == "__main__":
    V1Flow()
