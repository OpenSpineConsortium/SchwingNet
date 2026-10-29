"""LatencyFlow: one of the latency word's network jobs as a launched flow (issue #13; the owner's rule of 2026-10-29).

Started only by flows/launch.py, which grid/latency-sweep.sbatch runs in each of the jobs
grid/run-latency-sweep.sh submits for a run directory: one launcher run per Slurm job and per
task of the sweep array, each naming its part and the run directory it measures, so the word's
jobs, their classes and their resources stay as they were and only what runs inside them moves
onto the flow. The probe runs no network and stays a plain batch job.

    python flows/launch.py latency -- --part gpu --run-dir <run> --catalog <catalog> [--threads 8] [--frames 300]
    python flows/launch.py latency -- --part cpu --run-dir <run> --catalog <catalog> [--threads 8] [--frames 300]
    python flows/launch.py latency -- --part sweep --run-dir <run> --sweep <name>:bank=<folder>|<name>:<frames>:<boxes>

The parts do what the job script's body did, the same tools in the same order (tools/latency.py,
tools/sweep.py): gpu exports the run's best.pt to ONNX, checks the parity of ONNX Runtime on the
CPU, ONNX Runtime on the GPU and PyTorch on the GPU against PyTorch on the CPU, and times PyTorch
and ONNX Runtime on the GPU; cpu times both on THREADS CPU threads; sweep runs one recorded sweep
through the frame path with its overlay. A failed export or bank conversion stops its part, as
`set -e` stopped the script; a failed parity or measurement stops only its own arm, as before,
and every exit is recorded rather than raised, so the run ends with a verdict.

The run measures a network, so it keeps the owner's rule through flows/stage.py: start holds it
to docs/research/latency-and-sweep/PREREG.md, which covers the parts gpu, cpu and sweep; the
measure step's line on the run's progress page and its card move with each tool; end checks,
from the run directory's files alone and beside the tools' own refusals, that the parity rule
held as the PREREG states it, checks the run's CLAIM 2024 and REFORMS report (tools/report.py)
and writes metaflow/latency-<part>.json into the run directory, which names the Metaflow run, its
page, its verdict and its lines. The verdict is 0 only where the part ran to its end, its parity
rule held and the report is current. The record lies in a folder of its own, not at the run
directory's top, where stage.done_since reads a file's time as the time of the run's work, and a
part's record written while another part's end ran would then count as that run's own.

The parts write into the version 1 run's own folder (onnx/, latency/, evaluate/latency.json,
sweep-input/ and sweep/), and tools/report.py's run mode reads none of those files (load_run), so
checking the run's report after them is checking the report the run's own end step left; this
flow writes nothing the report reads.

The key reads the checkpoint's and the catalog's bytes and each sweep input's listing, so a
checkpoint, a catalog or a sweep replaced at the same path is never carried on as the one it was.
"""

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step
from metaflow.cards import Markdown

import stage
from flow_tool import file_sha256, from_launcher, word_value

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
LATENCY_TOOL = REPO / "tools" / "latency.py"
SWEEP_TOOL = REPO / "tools" / "sweep.py"
KIND = "latency"
PARTS = ("gpu", "cpu", "sweep")
REFRESH = 15
# The rules as the frozen PREREG states them, held here apart from src/schwingnet/latency.py, so a
# change to the code's own constants is caught by this check and never becomes the rule it checks.
BUDGET_MS = 97.0
PARITY_TOLERANCE = 1e-5
PARITY_PART = "validation"
REFERENCE = ("torch", "cpu")
# The arms whose parity each part rests on: gpu checks the three it times or the CPU job times,
# cpu times ONNX Runtime on the CPU, whose parity the gpu part showed, and PyTorch on the CPU,
# which is the reference; a sweep's arm is its runtime on the GPU.
GPU_PARITY = (("onnxruntime", "cpu"), ("onnxruntime", "cuda"), ("torch", "cuda"))
IMAGE_SUFFIXES = {".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp"}
SWEEP_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}")


class LatencyFault(Exception):
    """Words the flow cannot run as given: a part, a run directory or a sweep it does not take."""


def read_json(path):
    """A JSON object from a file, or None where it is missing, unreadable or no object."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def number(value):
    """A finite number, or None for anything else, a bool among them."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


# --- what a sweep is ------------------------------------------------------------------------------

def parse_sweep(spec):
    """A sweep's words, as the job script splits them: (name, frames, boxes) for name:frames:boxes,
    or (name, None, bank folder) for name:bank=<folder>; a LatencyFault for anything else."""
    pieces = spec.split(":")
    name = pieces[0]
    if not SWEEP_NAME.fullmatch(name):
        raise LatencyFault(f"a sweep's name is a file name of letters, digits, _, . and -, not {name!r}")
    if len(pieces) == 2 and pieces[1].startswith("bank=") and pieces[1] != "bank=":
        return name, None, pieces[1][len("bank="):]
    if len(pieces) == 3 and pieces[1] and pieces[2]:
        return name, pieces[1], pieces[2]
    raise LatencyFault(f"a sweep is name:frames:boxes or name:bank=<folder>, not {spec!r}")


def listed(paths, root):
    """The sha256 of a listing: each file's path under root, its size and its modification time."""
    lines = []
    for path in paths:
        try:
            facts = path.stat()
        except OSError:
            lines.append(f"{path.relative_to(root)}\tmissing")
            continue
        lines.append(f"{path.relative_to(root)}\t{facts.st_size}\t{facts.st_mtime_ns}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def sweep_listing(spec, folder):
    """What the key reads of a sweep's input: a bank's frames and metas of the case by their
    listing, or a folder's frames by theirs and the boxes file by its bytes."""
    try:
        name, frames, boxes = parse_sweep(spec)
    except LatencyFault:
        return "unreadable"
    if frames is None:
        bank = Path(from_launcher(boxes, folder))
        found = sorted(bank.glob(f"images/*/{name}_*")) + sorted(bank.glob(f"meta/{name}_*.json"))
        return f"bank {listed(found, bank)}"
    frames_path = Path(from_launcher(frames, folder))
    found = sorted(p for p in frames_path.iterdir() if p.is_file()) if frames_path.is_dir() else [frames_path]
    return f"frames {listed(found, frames_path.parent)} boxes {file_sha256(from_launcher(boxes, folder))}"


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, for the launcher's key: the
    checkpoint's and the catalog's bytes and the sweep's listing."""
    run = word_value(words, "--run-dir")
    reads = [f"checkpoint {file_sha256(Path(from_launcher(run, folder)) / 'train' / 'best.pt') if run else 'none'}"]
    catalog = word_value(words, "--catalog")
    reads += [f"catalog {file_sha256(from_launcher(catalog, folder))}"] if catalog else []
    sweep = word_value(words, "--sweep")
    return reads + ([f"sweep {sweep_listing(sweep, folder)}"] if sweep else [])


def prereg_part(words, folder):
    """The part a run of these words is, which the PREREG's Covers line must name, and no sha256,
    since a part is a fixed set of tool calls in this file, which the launcher's key names by the
    code's digest; none given is a part no PREREG covers."""
    return word_value(words, "--part") or "none", None


# --- what each part runs --------------------------------------------------------------------------

def command(label, tool, words, stops=False):
    """One tool call of a part: its label on the page, its words, and whether a failure stops the part."""
    return {"label": label, "tool": str(tool), "words": [str(word) for word in words], "stops": stops}


def gpu_commands(flow):
    common = ["--run", flow.run_folder, "--catalog", flow.catalog_file]
    commands = [command("export", LATENCY_TOOL, ["export", "--run", flow.run_folder], stops=True)]
    commands += [command(f"parity {runtime} on {device}", LATENCY_TOOL,
                         ["parity", *common, "--runtime", runtime, "--device", device, "--threads", flow.threads])
                 for runtime, device in GPU_PARITY]
    return commands + [command(f"measure {runtime} on cuda", LATENCY_TOOL,
                               ["measure", *common, "--runtime", runtime, "--device", "cuda", "--frames", flow.frames])
                       for runtime in ("torch", "onnxruntime")]


def cpu_commands(flow):
    common = ["--run", flow.run_folder, "--catalog", flow.catalog_file]
    return [command(f"measure {runtime} on cpu", LATENCY_TOOL,
                    ["measure", *common, "--runtime", runtime, "--device", "cpu", "--threads", flow.threads, "--frames", flow.frames])
            for runtime in ("torch", "onnxruntime")]


def sweep_commands(flow):
    name, frames, boxes = parse_sweep(flow.sweep_words)
    commands = []
    if frames is None:
        made = Path(flow.run_folder) / "sweep-input" / name
        commands.append(command(f"sweep {name} from its bank", SWEEP_TOOL,
                                ["from-bank", "--bank", from_launcher(boxes), "--case", name, "--out", made], stops=True))
        frames, boxes = made / "frames", made / "boxes.jsonl"
    else:
        frames, boxes = from_launcher(frames), from_launcher(boxes)
    return commands + [command(f"sweep {name}", SWEEP_TOOL,
                               ["run", "--run", flow.run_folder, "--frames", frames, "--boxes", boxes, "--name", name,
                                "--runtime", flow.sweep_runtime, "--device", "cuda", "--box-source", flow.box_source])]


PLANS = {"gpu": gpu_commands, "cpu": cpu_commands, "sweep": sweep_commands}


def checked_run_folder(path):
    """The run directory, refused unless tools/flow.py made it and training finished there, as
    grid/run-latency-sweep.sh refuses it before it submits anything."""
    folder = Path(path)
    for name in ("RUN.json", "train/checkpoint.json", "train/best.pt"):
        if not (folder / name).is_file():
            raise LatencyFault(f"{folder} has no {name}, so it is no run that has finished training")
    return str(folder.absolute())


def checked_words(flow):
    """Every word the part needs, refused in words where one is missing or not one the flow takes."""
    if flow.part not in PLANS:
        raise LatencyFault(f"the part is one of {', '.join(PARTS)}, not {flow.part!r}")
    if flow.part in ("gpu", "cpu") and not flow.catalog:
        raise LatencyFault(f"the {flow.part} part reads the run's catalog; name it with --catalog")
    if flow.part == "sweep" and not flow.sweep:
        raise LatencyFault("the sweep part runs one sweep; name it with --sweep")
    if flow.threads < 1 or flow.frames < 1:
        raise LatencyFault("threads and frames are at least 1")
    if flow.sweep_runtime not in ("onnxruntime", "torch") or flow.box_source not in ("truth", "detector"):
        raise LatencyFault("the sweep's runtime is onnxruntime or torch, its boxes truth or detector")


# --- what end checks, from the run directory's files ----------------------------------------------

def parity_problem(run, runtime, device):
    """Why an arm's parity does not hold for the files on disk now, as the PREREG states the rule,
    or None where it holds: equal levels and every probability within the tolerance, on validation
    crops, for this checkpoint and, for ONNX Runtime, this ONNX file. The reference needs none."""
    if (runtime, device) == REFERENCE:
        return None
    name = f"parity-{runtime}-{device}.json"
    verdict = read_json(Path(run) / "onnx" / name)
    if verdict is None:
        return f"{name} is missing, so no parity was shown"
    difference, crops = number(verdict.get("max_abs_probability_difference")), number(verdict.get("crops"))
    if verdict.get("labels_equal") is not True or difference is None or not difference < PARITY_TOLERANCE:
        return f"{name}: the levels differ or a probability is not within {PARITY_TOLERANCE} of the reference"
    if verdict.get("part") != PARITY_PART or crops is None or crops < 1:
        return f"{name}: not shown on the validation crops"
    if verdict.get("passed") is not True:
        return f"{name}: the tool did not pass it"
    if verdict.get("checkpoint_sha256") != file_sha256(Path(run) / "train" / "best.pt"):
        return f"{name}: shown for another checkpoint"
    if runtime == "onnxruntime" and verdict.get("onnx_sha256") != file_sha256(Path(run) / "onnx" / "level.onnx"):
        return f"{name}: shown for another ONNX file"
    return None


def parity_words(run, runtime, device):
    """One line on a parity: holds, with its numbers, or does not, with why."""
    problem = parity_problem(run, runtime, device)
    if problem:
        return False, f"parity {runtime} on {device}: DOES NOT HOLD, why: {problem}"
    verdict = read_json(Path(run) / "onnx" / f"parity-{runtime}-{device}.json")
    return True, (f"parity {runtime} on {device}: holds, max difference {verdict['max_abs_probability_difference']:.2g} "
                  f"on {verdict['crops']} validation crops of {verdict.get('persons')} persons, "
                  f"{verdict.get('witness_frames', 0)} witness frames first")


def arm_name(runtime, device, threads):
    """The arm's file name under latency/, as tools/latency.py names it."""
    return f"{runtime}-{device}" + (f"-{threads}t" if device == "cpu" else "")


def budget_words(p95):
    return "within the 97 ms budget" if p95 < BUDGET_MS else "not within the 97 ms budget"


def arm_words(run, runtime, device, threads):
    """One line on a timed arm: its numbers once its file is there and its parity holds."""
    name = arm_name(runtime, device, threads)
    arm = read_json(Path(run) / "latency" / f"{name}.json")
    if arm is None:
        return False, f"{name}: TIMED NOTHING, why: no latency/{name}.json"
    problem = parity_problem(run, runtime, device)
    if problem or arm.get("parity_passed") is not True:
        return False, f"{name}: A LATENCY WITHOUT PARITY, why: {problem or 'the file says parity did not pass'}"
    p50, p95 = number(arm.get("ms_per_frame_median")), number(arm.get("ms_per_frame_p95"))
    if p50 is None or p95 is None or arm.get("within_budget") is not (p95 < BUDGET_MS):
        return False, f"{name}: NOT READ, why: its percentiles or its budget word are not as the rule gives them"
    return True, f"{name}: p50 {p50:.1f} ms, p95 {p95:.1f} ms over {arm.get('frames')} frames on {arm.get('device')}, {budget_words(p95)}"


def passing_arms(run):
    """Every timed arm of the run whose parity holds now, by its p95."""
    arms = (read_json(path) for path in sorted((Path(run) / "latency").glob("*.json")))
    return [arm for arm in arms if arm and number(arm.get("ms_per_frame_p95")) is not None
            and parity_problem(run, arm.get("runtime"), arm.get("device_kind")) is None]


def headline_words(run):
    """The line on evaluate/latency.json: the fastest arm whose parity holds, with the budget's word."""
    headline = read_json(Path(run) / "evaluate" / "latency.json")
    if headline is None:
        return False, "headline: NONE, why: no evaluate/latency.json, so no arm's parity held when it was written"
    p95, passing = number(headline.get("ms_per_frame_p95")), passing_arms(run)
    if p95 is None or parity_problem(run, headline.get("runtime"), headline.get("device_kind")):
        return False, "headline: NOT READ, why: its arm's parity does not hold now"
    if not passing or p95 > min(number(arm["ms_per_frame_p95"]) for arm in passing):
        return False, "headline: NOT READ, why: it is not the fastest arm whose parity holds"
    if headline.get("within_budget") is not (p95 < BUDGET_MS):
        return False, "headline: NOT READ, why: its budget word is not as the rule gives it"
    said = "real-time, the p95 under 97 ms" if p95 < BUDGET_MS else "not real-time, the p95 not under 97 ms"
    return True, f"headline {headline.get('arm')}: p95 {p95:.1f} ms on {headline.get('device')}, {said}"


def sweep_words(run, name, runtime):
    """The line on a sweep's summary.json: its frames, its latency, the budget's word and its accuracy."""
    summary = read_json(Path(run) / "sweep" / name / "summary.json")
    if summary is None:
        return False, f"sweep {name}: NOTHING RECORDED, why: no summary.json"
    problem = parity_problem(run, runtime, "cuda")
    if problem or summary.get("runtime") != runtime:
        return False, f"sweep {name}: A LATENCY WITHOUT PARITY, why: {problem or 'another runtime ran it'}"
    if runtime == "onnxruntime" and summary.get("onnx_sha256") != file_sha256(Path(run) / "onnx" / "level.onnx"):
        return False, f"sweep {name}: A LATENCY WITHOUT PARITY, why: run on another ONNX file"
    timing = summary.get("latency_ms") if isinstance(summary.get("latency_ms"), dict) else {}
    p50, p95, frames = number(timing.get("p50")), number(timing.get("p95")), number(summary.get("frames"))
    if p50 is None or p95 is None or not frames or summary.get("within_budget") is not (p95 < BUDGET_MS):
        return False, f"sweep {name}: NOT READ, why: its frames, percentiles or budget word are not as the rule gives them"
    accuracy = (summary.get("accuracy") or {}).get("all frames") or {}
    scored = f", {accuracy['correct']}/{accuracy['total']} levels named over the truth boxes" if "total" in accuracy else ""
    return True, f"sweep {name}: {int(frames)} frames, p50 {p50:.1f} ms, p95 {p95:.1f} ms, {budget_words(p95)}{scored}"


def part_checks(flow):
    """Every line the part's verdict rests on beside its report: (holds, line)."""
    run = flow.run_folder
    if flow.part == "gpu":
        checks = [parity_words(run, runtime, device) for runtime, device in GPU_PARITY]
        checks += [arm_words(run, runtime, "cuda", flow.threads) for runtime in ("torch", "onnxruntime")]
        return checks + [headline_words(run)]
    if flow.part == "cpu":
        checks = [parity_words(run, "onnxruntime", "cpu")]
        checks += [arm_words(run, runtime, "cpu", flow.threads) for runtime in ("torch", "onnxruntime")]
        return checks + [headline_words(run)]
    return [parity_words(run, flow.sweep_runtime, "cuda"), sweep_words(run, flow.sweep_name, flow.sweep_runtime)]


def ran_words(commands, outcomes):
    """The lines of the tools that did not run to their end, and those the part never reached."""
    done = {outcome["label"]: outcome for outcome in outcomes}
    lines = []
    for planned in commands:
        outcome = done.get(planned["label"])
        if outcome is None:
            lines.append(f"{planned['label']}: NOT RUN, why: an earlier tool stopped the part")
        elif outcome["exit"] != 0:
            lines.append(f"{planned['label']}: FAILED, exit {outcome['exit']}, why: {outcome['last']}")
    return lines


def verdict_of(ran_lines, checks, report_ok):
    """0 where the part ran to its end, every check of its parity rule held and its report is current, else 1."""
    return 0 if not ran_lines and all(ok for ok, _ in checks) and report_ok else 1


def last_line(out, err):
    return ((err.strip() or out.strip()).splitlines() or ["no output"])[-1]


def running_words(flow, planned):
    """What the part is doing while a tool runs: its label and, for a sweep, the frames drawn so far."""
    if planned["words"][0] == "run" and planned["tool"] == str(SWEEP_TOOL):
        drawn = len(list((Path(flow.run_folder) / "sweep" / flow.sweep_name / "overlay").glob("*.png")))
        return f"{planned['label']}: running, {drawn} frames drawn"
    return f"{planned['label']}: running"


class LatencyFlow(FlowSpec):
    """One latency job's part on one run directory: held to its PREREG, measured by the tools, checked, reported."""

    part = Parameter("part", required=True, help="gpu, cpu or sweep: which of the latency word's jobs this run is")
    run_dir = Parameter("run-dir", required=True, help="the run directory the version 1 run made, with RUN.json and train/best.pt")
    catalog = Parameter("catalog", default="", help="the catalog the run was trained from; gpu and cpu read it")
    threads = Parameter("threads", type=int, default=8, help="CPU threads: ONNX Runtime's on the CPU in parity, the CPU arms'")
    frames = Parameter("frames", type=int, default=300, help="frames timed per arm, after the warm-up")
    sweep = Parameter("sweep", default="", help="the sweep part's one sweep: name:frames:boxes or name:bank=<folder>")
    sweep_runtime = Parameter("sweep-runtime", default="onnxruntime", help="the runtime a sweep runs through on the GPU")
    box_source = Parameter("box-source", default="truth", help="where a sweep's boxes come from: truth or detector")
    commit = Parameter("commit", default="", help="the commit of the checkout that first started the run, which the launcher passes")

    @step
    def start(self):
        """The run held to the frozen PREREG for its part, its words checked and the part's tools planned."""
        with stage.Beat(self, "prepare") as beat:
            stage.hold_to_prereg(self, KIND, self.part)
            checked_words(self)
            self.run_folder = checked_run_folder(from_launcher(self.run_dir))
            self.catalog_file = from_launcher(self.catalog)
            self.sweep_words = self.sweep
            self.sweep_name = parse_sweep(self.sweep)[0] if self.part == "sweep" else None
            self.label = self.part if self.part != "sweep" else f"sweep-{self.sweep_name}"
            self.checkpoint_sha256 = file_sha256(Path(self.run_folder) / "train" / "best.pt")
            self.catalog_sha256 = file_sha256(self.catalog_file) if self.catalog_file else None
            self.commands = PLANS[self.part](self)
            said = f"part {self.label} on {Path(self.run_folder).name}, {len(self.commands)} tools: " + ", ".join(c["label"] for c in self.commands)
            print(f"LatencyFlow: {said}", flush=True)
            beat.say(said)
        self.next(self.measure)

    @card(type="blank", id="part", refresh_interval=REFRESH)
    @step
    def measure(self):
        """The part's tools in order, each exit recorded; a tool that stops the part ends it early."""
        part_card, progress = current.card["part"], Markdown("Starting.")
        part_card.append(Markdown(f"# Latency, {self.label}\n\nRun {Path(self.run_folder).name}."))
        part_card.append(progress)
        part_card.refresh()
        self.outcomes = []
        with stage.Beat(self, self.label) as beat:
            for planned in self.commands:
                def line_of(planned=planned):
                    words = running_words(self, planned)
                    progress.update(words)
                    part_card.refresh()
                    return words

                code, out, err = stage.run_watched([sys.executable, planned["tool"], *planned["words"]], beat, line_of,
                                                   every=REFRESH, cwd=REPO)
                print(out + err, end="", flush=True)
                self.outcomes.append({"label": planned["label"], "exit": code, "last": last_line(out, err)})
                said = f"{planned['label']}: done" if code == 0 else f"{planned['label']}: FAILED, exit {code}, why: {last_line(out, err)}"
                beat.say(said)
                progress.update(said)
                part_card.refresh()
                if code != 0 and planned["stops"]:
                    break
        self.next(self.end)

    @card(type="blank")
    @step
    def end(self):
        """The part's parity rule checked from its files, its report, the verdict, metaflow/latency-<part>.json and the page."""
        with stage.Beat(self, "report") as beat:
            stage.still_held(self, KIND)
            ran = ran_words(self.commands, self.outcomes)
            checks = part_checks(self)
            report_ok, report = stage.claim_report(Path(self.run_folder), began=stage.run_began())
            self.report = report
            self.verdict = verdict_of(ran, checks, report_ok)
            judged = [(report_ok, report), *((False, line) for line in ran), *checks]
            self.lines = [line for _, line in judged]
            record = {"flow": "LatencyFlow", "part": self.label, "run": f"{current.flow_name}/{current.run_id}",
                      "root": stage.datastore_root(), "page": str(stage.page_path()), "verdict": self.verdict, "lines": self.lines}
            target = Path(self.run_folder) / "metaflow" / f"latency-{self.label}.json"
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            for line in self.lines:
                print(f"LatencyFlow: end: {line}", flush=True)
            print(f"LatencyFlow: end: part {self.label}, verdict {self.verdict}", flush=True)
            beat.say(f"verdict {self.verdict}")
            stage.finish(self.verdict, judged)
        current.card.append(Markdown(f"# Latency, {self.label}, run {Path(self.run_folder).name}\n\nVerdict {self.verdict}. "
                                     f"Progress page: {stage.page_path()}.\n\n" + "\n".join(f"- {line}" for line in self.lines)))


if __name__ == "__main__":
    LatencyFlow()
