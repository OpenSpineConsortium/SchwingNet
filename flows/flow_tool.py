"""What a launched flow does to run tools/flow.py run whole: V1Flow's (flows/v1.py), and the
experiment word's flow's once it is moved, since both run one tools/flow.py run, in local mode, in
one step, and differ only in the words they give it and what their start and end do around it.
This module is a plain one, no flow in it, so no flow imports another, and a change here names a
new run of every kind that lists it (tools/run_code.py).

- Paths: a path parameter is read from the folder the launcher was started in (SCHWINGNET_WORKDIR),
  since the flow's steps run in the datastore root; word_value reads a flag's value from the
  launcher's words, as key_reads does before Metaflow parses them.
- run_flow_tool, in the step that trains: tools/flow.py run under the step's card and its line on
  the run's progress page, both moving with the trainer's train/metrics.jsonl every REFRESH
  seconds; the run's folder is learnt from the .lock tools/flow.py holds it by, since the process
  says its folder on stdout only once it ends here. A run that exits other than 0, or says no
  folder, raises the flow's own fault, so the step's @retry tries it once more and tools/flow.py
  carries the run on from where the first try stopped.

The epoch line and the watched run are kept here rather than in flows/stage.py, which every launched
kind lists in its code (tools/run_code.py): a change there would name a new run of the sweep, the
DRR study and the FluXray stages too, and the launcher would no longer carry one of theirs cut short
on.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from metaflow import current
from metaflow.cards import Markdown

import stage

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
FLOW_TOOL = REPO / "tools" / "flow.py"
REFRESH = 15
FINISHED_MARK = "FINISHED.json"


def launcher_folder():
    """The folder the launcher was started in, which a relative path parameter is read from."""
    return Path(os.environ.get("SCHWINGNET_WORKDIR") or os.getcwd())


def from_launcher(path, folder=None):
    """A path parameter as the caller meant it: a relative one is read from the launcher's folder."""
    return str((folder or launcher_folder()) / path) if path and not Path(path).is_absolute() else path


def file_sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return "unreadable"


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


def inputs_read(words, folder):
    """The catalog's and the weights' bytes, which tools/flow.py names a run by, as the launcher's
    key reads them, so a file replaced at the same path is never carried on as the one it was."""
    reads = [f"catalog {file_sha256(from_launcher(word_value(words, '--catalog'), folder))}"]
    weights = word_value(words, "--weights")
    return reads + ([f"weights {file_sha256(from_launcher(weights, folder))}"] if weights else [])


def json_line(text, key):
    """The first line of the text that is a JSON object holding the key, as tools/flow.py prints
    the run's id and folder before its first step."""
    for line in text.splitlines():
        try:
            said = json.loads(line)
        except ValueError:
            continue
        if isinstance(said, dict) and key in said:
            return said
    return None


def held_folder(out, pid):
    """The run folder under out that the process holds, by the words tools/flow.py writes in its
    .lock once it runs something; None until it has."""
    for lock in Path(out).glob("*/.lock"):
        try:
            if lock.read_text(encoding="utf-8").startswith(f"pid {pid} on "):
                return lock.parent
        except OSError:
            continue
    return None


def epoch_words(metrics_file, epochs=0):
    """The last line of a trainer's train/metrics.jsonl, as the card and the page show it while it
    trains: the epoch of how many, the loss, the validation accuracy and the seconds."""
    try:
        lines = Path(metrics_file).read_text(encoding="utf-8").splitlines()
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


def run_watched(command, beat, line_of, every, started, **popen):
    """stage.run_watched, with started told the process once it runs, so line_of can find the
    folder that process holds: (exit code, stdout, stderr)."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **popen)
    started(process)
    while True:
        try:
            out, err = process.communicate(timeout=every)
            break
        except subprocess.TimeoutExpired:
            beat.tick(line_of)
    beat.tick(line_of)
    return process.returncode, out, err


def run_words(folder, epochs):
    """Where the run stands, from its folder: the last epoch while it trains, then the evaluation."""
    if folder is None:
        return "tools/flow.py is starting: the record, the split check and the witness frames."
    if (folder / FINISHED_MARK).is_file():
        return f"Finished: {folder.name}."
    if (folder / "evaluate").is_dir():
        return f"Evaluating {folder.name} on the test part."
    return f"Training {folder.name}. " + epoch_words(folder / "train" / "metrics.jsonl", epochs + 1)


def run_flow_tool(flow, command, out_root, epochs, title, fault):
    """tools/flow.py run to its end in a step decorated @card(id="run"), its card and its line on
    the page moving while it trains: (the run's id, the run's folder) as tools/flow.py says them,
    or fault raised with the exit code and the last line it wrote."""
    run_card, progress = current.card["run"], Markdown("Starting.")
    run_card.append(Markdown(title))
    run_card.append(progress)
    run_card.refresh()
    process = {}

    def line_of():
        words = run_words(held_folder(out_root, process["pid"]) if process else None, epochs)
        progress.update(words)
        run_card.refresh()
        return words

    with stage.Beat(flow, "train and evaluate") as beat:
        code, out, err = run_watched(command, beat, line_of, REFRESH, lambda running: process.update(pid=running.pid), cwd=REPO)
        print(out + err, end="", flush=True)
        said = json_line(out, "run_dir")
        if code != 0 or said is None:
            last = (err.strip().splitlines() or ["no output"])[-1]
            raise fault(f"tools/flow.py run exited {code}: {last}")
        beat.say(f"run {said.get('run_id')}, folder {said['run_dir']}")
    return said.get("run_id"), said["run_dir"]


def flow_tool_head(catalog, out, environment, epochs, seed):
    """The words of tools/flow.py run every launched flow gives, in local mode on the GPU the job
    holds, before the words of its own."""
    return [sys.executable, str(FLOW_TOOL), "run", "--catalog", catalog, "--out", out, "--mode", "local",
            "--environment", environment, "--epochs", str(epochs), "--seed", str(seed)]
