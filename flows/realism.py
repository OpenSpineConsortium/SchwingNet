"""The FluXray reproduction as a Metaflow flow (docs/research/flux-realism/PREREG.md).

Usage, through the launcher only (grid/realism.sbatch, the gate's word `realism <stage>`):
    python flows/launch.py realism --max-workers 1 -- --stage edit --out <realism root> \\
        --samples <FluXray samples.csv> --db <FluXray ThunderDB> --ct <CT root> --truth <truth root> \\
        --klein <klein-9B folder> --bundle <FleXray bundle> --imagenet <resnet18 .pth>
    python flows/launch.py realism --max-workers 1 -- --stage stats --out <realism root> \\
        --bundle <FleXray bundle> --imagenet <resnet18 .pth>

Two stages, each one GPU job on the owner's count, each a run of this flow:

- edit: start holds the run to the frozen PREREG and checks every input before a GPU second is
  spent (tools/realism.py inputs); prepare reads FluXray's poses and draws the subjects by the
  frozen seed into shards; each shard, one step of a foreach, renders its subjects' drawn samples,
  edits each in the plan's seed arms with klein-9B and scores every edit and its render with the
  flux000 member; join_shards applies FluXray's paired filter over every shard's scores at once,
  exports FluXray's own images of exactly the samples rendered and measures the endplates.
- stats: the kept edits and the raw renders, each against FluXray's images of the same samples, in
  the three feature spaces the PREREG names; join_comparisons reads the replication's one word
  (schwingnet.realism.replication_word) and the geometry's.

Each run works in its own folder, <out>/<stage>-<run key>-<run id>, named by the launcher's key and
the run that made it. A run cut short and resumed carries on in the folder it began, since a resume
clones start and its folder with it, the render and the edit skipping every sample already whole; a
shard that fails fails the run, since the PREREG's sample is all the drawn subjects, and a later
launch of the same key resumes it from that shard. A new run of the same key, whenever the
launcher starts one, after a run that ended well or beside one still going, begins in an empty
folder of its own, so no file of another run's draw is ever counted as this run's. An edit run that ends well writes <out>/edit.json, which names
its folder: the stats stage reads the edit through it and copies the small files the report reads,
and the stats run's key reads it with the weights the statistics load, so a new edit or new
weights start new statistics; the stats start records the job's own environment and the weights'
sha256 (tools/realism.py environment), as the edit's inputs step does for the edit. The end step
writes RECORD.json, the run's record, which names the run that made the folder (where) and the run
that ended it (ended_in), and SUMMARY.md, the lines the job's report carries, and checks the run's
CLAIM 2024 and REFORMS report (tools/report.py --study flux-realism): a report that cannot be
written or is not current makes the verdict 1, and so does an edit that made fewer renders, edits
or FluXray images than its own draw holds, so the stats never read a sample short of the PREREG's.

The rule of 2026-10-29 is kept through flows/stage.py: start holds the run to the frozen PREREG and
then to its frozen block, which must be schwingnet.realism.frozen_lines(), so the numbers the code
runs and the numbers frozen can never part; every step keeps its line on the run's progress page,
a shard's line moving with its renders and edits. The adapter's stages, lora and eval, are refused
until they have a count and a PREREG of their own.
"""

import hashlib
import json
import os
import socket
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, retry, step
from metaflow.cards import Markdown

import stage

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
for _path in (REPO / "vendor" / "beethoven-qa" / "src", REPO / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from schwingnet import realism  # noqa: E402

TOOL = REPO / "tools" / "realism.py"
KIND = "realism"
STUDY = "flux-realism"
REFRESH = 15
COMPARISONS = ("kept", "raw")
# What the stats stage copies of the edit's folder into its own, under edit/: every file the
# report reads of the edit, each small, so the stats folder alone answers the report.
EDIT_FILES = ("RECORD.json", "ENDED.json", "inputs.json", "split/split.json", "split/all.txt", "filter/filter_kept.csv",
              "filter/filter_dropped.csv", "measure/measure.md", "render/manifest.jsonl", "SUMMARY.md")


class RealismFault(Exception):
    """A step of the reproduction could not do what it was asked; the run's fault, said in words."""


def launcher_folder():
    """The folder the launcher was started in, which a relative path parameter is read from."""
    return Path(os.environ.get("SCHWINGNET_WORKDIR") or os.getcwd())


def from_launcher(path, folder=None):
    """A path parameter as the caller meant it: a relative one is read from the launcher's folder."""
    return str((folder or launcher_folder()) / path) if path and not Path(path).is_absolute() else path


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


def file_sha256(path):
    if not path:
        return "absent"
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    except OSError:
        return "unreadable"
    return digest.hexdigest()


# Files a read itself writes, which would give every launch a new key and so never resume a run:
# LMDB's lock file beside the ThunderDB's data.
WRITTEN_BY_READING = ("lock.mdb",)


def listing_line(root, path):
    """A file's path, size and modification time, or None for one gone since it was listed."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return f"{path.relative_to(root)}\t{stat.st_size}\t{stat.st_mtime_ns}"


def listing_sha256(folder):
    """One sha256 over a folder's files by path, size and modification time, cheap enough for the
    launcher's key, so a file fetched again, even at the same size, starts a new run."""
    root = Path(folder)
    if not folder or not root.is_dir():
        return "absent"
    lines = (listing_line(root, path) for path in root.rglob("*") if path.name not in WRITTEN_BY_READING and path.is_file())
    return hashlib.sha256("\n".join(sorted(line for line in lines if line)).encode("utf-8")).hexdigest()


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, for the launcher's key: for the
    edit, FluXray's samples.csv by its bytes and the ThunderDB, the CTs, the truth, the klein
    weights and the FleXray bundle by their files' names, sizes and times, so data that landed or changed
    starts a new run rather than carrying an old one on; for the stats, the edit pointer by its
    bytes, the bundle by its listing and the ImageNet weights by their bytes, so a new edit or new
    weights start new statistics."""
    def listing(flag):
        return f"{flag[2:]} {listing_sha256(from_launcher(word_value(words, flag), folder))}"
    if word_value(words, "--stage") == "stats":
        root = from_launcher(word_value(words, "--out"), folder)
        bundle, imagenet = stats_weights(words, folder, root)
        return [f"edit {file_sha256(Path(root) / 'edit.json')}", f"bundle {listing_sha256(bundle)}",
                f"imagenet {file_sha256(imagenet)}"]
    return [f"samples {file_sha256(from_launcher(word_value(words, '--samples'), folder))}",
            *(listing(flag) for flag in ("--db", "--ct", "--truth", "--klein", "--bundle"))]


def stats_weights(words, folder, root):
    """The bundle and the ImageNet weights a stats run of these words loads: the words' own, else
    the ones the edit's record names, as read_edit takes them."""
    pointer = read_json(Path(root) / "edit.json") or {}
    record = read_json(Path(pointer["folder"]) / "RECORD.json") if pointer.get("folder") else None
    paths = (record or {}).get("paths") or {}
    return [from_launcher(word_value(words, flag), folder) or paths.get(flag[2:], "") for flag in ("--bundle", "--imagenet")]


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_json(path, value):
    """A JSON file written whole or not at all, so a reader never sees half of one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def code_state():
    """The checkout's commit and whether its tree is clean, read where the step runs: a commit
    says which code ran only from a clean tree, and git that cannot be read says neither."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True)
    tree = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True)
    commit = head.stdout.strip() if head.returncode == 0 else ""
    return {"commit": commit or None, "clean_tree": bool(commit) and tree.returncode == 0 and not tree.stdout.strip()}


def run_key():
    """The launcher's key for this run, from its tag; the run id where the flow ran without it."""
    for tag in current.tags or ():
        if str(tag).startswith("key:"):
            return str(tag)[4:]
    return f"run{current.run_id}"


def last_line(text):
    return (text.strip().splitlines() or [""])[-1][:300]


def count_files(folder, suffix=".npy"):
    try:
        return sum(1 for entry in os.scandir(folder) if entry.name.endswith(suffix))
    except OSError:
        return 0


def tool(beat, name, *args, line_of=None):
    """One subcommand of tools/realism.py run to its end under the step's beat, its output kept in
    the folder's logs/, its last line said; a nonzero exit is the run's fault, said in words."""
    command = [sys.executable, str(TOOL), name, *[str(arg) for arg in args]]
    beat.say(f"{name}: running")
    code, out, err = stage.run_watched(command, beat, line_of or (lambda: f"{name}: running"), every=REFRESH, cwd=REPO)
    logs = Path(beat_folder(beat)) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    with open(logs / f"{name}.log", "a", encoding="utf-8") as log:
        log.write(f"$ {' '.join(command)}\n{out}{err}\n")
    print(out + err, end="", flush=True)
    if code != 0:
        raise RealismFault(f"tools/realism.py {name} exited {code}: {last_line(err) or last_line(out)}")
    said = last_line(out)
    beat.say(f"{name}: {said}")
    return said


def beat_folder(beat):
    return beat.folder


class RealismFlow(FlowSpec):
    which = Parameter("stage", help="edit or stats (PREREG.md); lora and eval wait for a count of their own", required=True)
    out = Parameter("out", help="the realism root, under which each run keeps <stage>-<key>-<run id>/", required=True)
    samples = Parameter("samples", help="FluXray's samples.csv", default="")
    db = Parameter("db", help="FluXray's ThunderDB folder", default="")
    ct = Parameter("ct", help="the folder the ENHANCE.PET CTs landed under", default="")
    truth = Parameter("truth", help="the folder the ENHANCE.PET ground truth landed under", default="")
    klein = Parameter("klein", help="the FLUX.2 klein-9B diffusers folder", default="")
    bundle = Parameter("bundle", help="FleXray's weights, the folder that holds ensemble.json", default="")
    imagenet = Parameter("imagenet", help="torchvision's resnet18-f37072fd.pth", default="")
    device = Parameter("device", help="the torch device of the GPU steps", default="cuda")
    commit = Parameter("commit", default="")

    def beat(self, label):
        beat = stage.Beat(self, label)
        beat.folder = self.folder
        return beat

    def path(self, *parts):
        return str(Path(self.folder, *parts))

    @step
    def start(self):
        """The run held to the frozen PREREG and its block, its folder made, and for the edit every
        input checked and hashed before any GPU work; for the stats, the edit read through its pointer."""
        with stage.Beat(self, f"{self.which}: the PREREG and the inputs") as beat:
            if self.which not in realism.FLOW_STAGES:
                raise stage.StageFault(f"the stage {self.which!r} is not one this count runs ({', '.join(realism.FLOW_STAGES)}); "
                                       "lora and eval wait for a count and a PREREG of their own")
            stage.hold_to_prereg(self, KIND)
            problems = realism.frozen_block_problems((REPO / self.prereg_path).read_text(encoding="utf-8"))
            if problems:
                raise stage.StageFault("the PREREG's frozen block and the code that runs differ: " + "; ".join(problems))
            self.key, self.root = run_key(), from_launcher(self.out)
            self.folder = str(Path(self.root) / f"{self.which}-{self.key}-{current.run_id}")
            Path(self.folder).mkdir(parents=True, exist_ok=True)
            self.started = utc_now()
            self.where = {"host": socket.gethostname(), "slurm_job": os.environ.get("SLURM_JOB_ID") or "none",
                          "run": f"{current.flow_name}/{current.run_id}", "datastore": stage.datastore_root(), **code_state()}
            write_json(Path(self.root) / f"{self.which}.last.json", {"folder": self.folder, "run": self.where["run"],
                                                                      "key": self.key, "started": self.started, "verdict": None})
            beat.folder = self.folder
            beat.say(f"held to {self.prereg_path}, sha256 {self.prereg_sha256[:16]}; folder {self.folder}")
            if self.which == "edit":
                self.check_inputs(beat)
            else:
                self.read_edit(beat)
                tool(beat, "environment", "--bundle", self.paths["bundle"], "--imagenet", self.paths["imagenet"],
                     "--out", self.path("environment.json"))
        self.route = self.which
        self.next({"edit": self.prepare, "stats": self.fan_comparisons}, condition="route")

    def check_inputs(self, beat):
        self.paths = {name: from_launcher(getattr(self, name)) for name in ("samples", "db", "ct", "truth", "klein", "bundle", "imagenet")}
        absent = [name for name, value in self.paths.items() if not value]
        if absent:
            raise RealismFault(f"the edit stage needs --{', --'.join(absent)}")
        tool(beat, "inputs", "--samples", self.paths["samples"], "--db", self.paths["db"], "--ct", self.paths["ct"],
             "--truth", self.paths["truth"], "--klein", self.paths["klein"], "--bundle", self.paths["bundle"],
             "--imagenet", self.paths["imagenet"], "--out", self.path("inputs.json"))

    def read_edit(self, beat):
        pointer = read_json(Path(self.root) / "edit.json")
        if not pointer or not Path(pointer.get("folder", "")).is_dir():
            raise RealismFault(f"no edit run that ended well is named by {Path(self.root) / 'edit.json'} (send realism edit first)")
        record = read_json(Path(pointer["folder"]) / "RECORD.json") or {}
        ended = read_json(Path(pointer["folder"]) / "ENDED.json") or {}
        if ended.get("verdict") != 0:
            raise RealismFault(f"the edit run {pointer['folder']} did not end with verdict 0")
        if record.get("prereg_sha256") != self.prereg_sha256:
            raise RealismFault(f"the edit ran under the PREREG sha256 {str(record.get('prereg_sha256'))[:16]}, this run under "
                               f"{self.prereg_sha256[:16]}: the two stages of one reproduction run under one frozen design")
        self.edit_folder = pointer["folder"]
        self.paths = {"bundle": from_launcher(self.bundle) or record["paths"]["bundle"],
                      "imagenet": from_launcher(self.imagenet) or record["paths"]["imagenet"]}
        for name in EDIT_FILES:
            source = Path(self.edit_folder) / name
            if source.is_file():
                target = Path(self.folder) / "edit" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        beat.say(f"the edit of {record.get('started')} UTC, {self.edit_folder}, its record copied under edit/")

    # --- the edit -----------------------------------------------------------------------------

    @step
    def prepare(self):
        """FluXray's poses, then the subjects drawn by the frozen seed and dealt into shards."""
        with self.beat("poses and the draw") as beat:
            plan = realism.REPLICATION
            tool(beat, "poses", "--samples", self.paths["samples"], "--inputs", self.path("inputs.json"), "--out", self.path("poses.json"))
            tool(beat, "split", "--poses", self.path("poses.json"), "--eligible", self.path("inputs.json"), "--limit", plan.subjects,
                 "--seed", plan.draw_seed, "--shard-size", plan.shard_subjects, "--out", self.path("split"))
            self.shards = sorted(str(path) for path in Path(self.path("split", "shards")).glob("*.txt"))
            if not self.shards:
                raise RealismFault("the split wrote no shard")
            beat.say(f"{len(self.shards)} shards of at most {plan.shard_subjects} subjects")
        self.next(self.shard, foreach="shards")

    @retry(times=1, minutes_between_retries=0)
    @step
    def shard(self):
        """One shard's subjects: render, edit in the plan's arms, score each edit and its render."""
        name, plan = Path(self.input).stem, realism.REPLICATION
        expected = plan.subjects * plan.poses_per_subject

        def done():
            return (f"shard {name}: renders {count_files(self.path('render', 'raw'))} of {expected}, "
                    f"edits {count_files(self.path('edit', 'edited'))} of {expected * plan.arms} in the run so far")

        with self.beat(f"shard {name}") as beat:
            tool(beat, "render", "--ct", self.paths["ct"], "--truth", self.paths["truth"], "--poses", self.path("poses.json"),
                 "--weights", self.paths["bundle"], "--out", self.path("render"), "--only", self.input,
                 "--per-subject", plan.poses_per_subject, "--draw-seed", plan.draw_seed, "--device", self.device, line_of=done)
            tool(beat, "edit", "--raw", self.path("render"), "--weights", self.paths["klein"], "--model", realism.FLUXRAY.model,
                 "--arms", plan.arms, "--only", self.input, "--out", self.path("edit"), "--device", self.device, line_of=done)
            tool(beat, "score", "--raw", self.path("render"), "--edited", self.path("edit"), "--weights", self.paths["bundle"],
                 "--only", self.input, "--out", self.path("scores", f"{name}.csv"), "--device", self.device, line_of=done)
        self.next(self.join_shards)

    @step
    def join_shards(self, inputs):
        """FluXray's paired filter over every shard's scores at once, FluXray's images of exactly the
        samples rendered, and the endplate angles at 1024 and 256."""
        self.merge_artifacts(inputs)
        with self.beat("filter, FluXray's images, endplates") as beat:
            self.said = {
                "keep": tool(beat, "keep", "--scores", self.path("scores"), "--edited", self.path("edit"), "--out", self.path("filter")),
                "export": tool(beat, "fluxray-export", "--db", self.paths["db"], "--samples", self.path("render"),
                               "--out", self.path("fluxray")),
                "measure": tool(beat, "measure", "--masks", self.path("render"), "--out", self.path("measure")),
            }
        self.next(self.end)

    # --- the statistics -----------------------------------------------------------------------

    @step
    def fan_comparisons(self):
        stage.Beat(self).passed()
        self.comparisons = list(COMPARISONS)
        self.next(self.compare, foreach="comparisons")

    @retry(times=1, minutes_between_retries=0)
    @step
    def compare(self):
        """One comparison against FluXray's images of the same samples, in the PREREG's three spaces."""
        self.comparison = self.input
        sets = {"kept": ("filter", "kept"), "raw": ("render", "raw")}
        with self.beat(f"{self.comparison} against FluXray") as beat:
            tool(beat, "stats", "--a", Path(self.edit_folder, *sets[self.comparison]), "--b", Path(self.edit_folder, "fluxray", "img"),
                 "--index", Path(self.edit_folder, "render"), "--weights", self.paths["bundle"],
                 "--imagenet-weights", self.paths["imagenet"], "--require-spaces", ",".join(realism.SPACES),
                 "--seed", realism.REPLICATION.stats_seed, "--out", self.path(self.comparison), "--device", self.device)
            report = read_json(self.path(self.comparison, "stats.json")) or {}
            self.word = report.get("verdict", "undecided")
            self.shift = (report.get("paired") or {}).get("shift_px_median")
            beat.say(f"{self.comparison} against FluXray: {self.word}")
        self.next(self.join_comparisons)

    @step
    def join_comparisons(self, inputs):
        """The replication's one word from the two comparisons, and the geometry's."""
        self.words = {each.comparison: each.word for each in inputs}
        self.shifts = {each.comparison: each.shift for each in inputs}
        self.merge_artifacts(inputs, exclude=["comparison", "word", "shift"])
        with self.beat("the replication's word") as beat:
            self.replication = realism.replication_word(self.words["kept"], self.words["raw"])
            shift = self.shifts.get("raw")
            self.geometry = "not read" if shift is None else ("holds" if shift <= realism.GEOMETRY_SHIFT_PX else "off")
            beat.say(f"replication: {self.replication}; geometry: {self.geometry} (median shift {shift} px)")
        self.next(self.end)

    # --- the record ---------------------------------------------------------------------------

    def counts(self):
        """What the run made, counted from its files."""
        if self.which == "edit":
            split = read_json(self.path("split", "split.json")) or {}
            inputs = read_json(self.path("inputs.json")) or {}
            poses = read_json(self.path("poses.json")) or {}
            return {"fluxray_samples": inputs.get("samples_rows"), "not_in_db": inputs.get("samples_not_in_db"),
                    "off_grid": len(poses.get("mismatches", [])), "eligible_subjects": len(inputs.get("eligible", [])),
                    "drawn_subjects": split.get("all"), "renders": count_files(self.path("render", "raw")),
                    "edits": count_files(self.path("edit", "edited")), "kept": count_files(self.path("filter", "kept")),
                    "fluxray_exported": count_files(self.path("fluxray", "img"))}
        return {name: (read_json(self.path(name, "stats.json")) or {}).get("sets") for name in COMPARISONS}

    def shortfalls(self):
        """What an edit run made short of its own draw, since the PREREG's sample is every drawn
        subject whole: each drawn subject's samples rendered, each render edited in every arm, and
        FluXray's image of each; none for the stats, whose tool refuses rather than run short."""
        if self.which != "edit":
            return []
        counts, plan = self.counts(), realism.REPLICATION
        renders = (counts["drawn_subjects"] or 0) * plan.poses_per_subject
        wanted = {"renders": renders, "edits": renders * plan.arms, "fluxray_exported": renders}
        return [f"{name} {counts[name]} of {want}" for name, want in wanted.items() if counts[name] != want]

    def summary_lines(self):
        if self.which == "edit":
            return [f"- {name}: {line}" for name, line in self.said.items()]
        lines = [f"- replication: {self.replication}; geometry: {self.geometry} (raw median shift {self.shifts.get('raw')} px)"]
        for name in COMPARISONS:
            table = Path(self.path(name, "stats.md"))
            lines += ["", f"### {name} against FluXray", "", table.read_text(encoding="utf-8") if table.is_file() else "no stats.md"]
        return lines

    def ended_in(self):
        """The run that ends the folder, which a resume makes another than the run in where, with
        the commit and tree it ended on, since a resume may run on a later commit of the same code."""
        return {"run": f"{current.flow_name}/{current.run_id}", "host": socket.gethostname(),
                "slurm_job": os.environ.get("SLURM_JOB_ID") or "none", "ended": utc_now(), **code_state()}

    def record(self):
        files = [path for path in Path(self.folder).rglob("*") if path.is_file() and path.stat().st_size < (64 << 20)
                 and path.suffix in (".json", ".jsonl", ".csv", ".txt", ".md") and path.name != "RECORD.json"]
        return {"study": STUDY, "stage": self.which, "run": self.where["run"], "key": self.key,
                "commit": self.commit, "clean_tree": self.where.get("clean_tree") is True and self.ended["clean_tree"],
                "prereg": self.prereg_path, "prereg_sha256": self.prereg_sha256, "frozen": realism.frozen_lines(),
                "started": self.started, "ended": self.ended["ended"], "where": self.where, "ended_in": self.ended,
                "paths": self.paths,
                "edit_folder": getattr(self, "edit_folder", None), "plan": asdict(realism.REPLICATION),
                "recipe": {k: v for k, v in realism.as_record(realism.FLUXRAY).items() if k != "prompt"},
                "counts": self.counts(), "short": self.short, "words": getattr(self, "words", None), "replication": getattr(self, "replication", None),
                "geometry": getattr(self, "geometry", None), "shifts": getattr(self, "shifts", None),
                "files": {str(path.relative_to(self.folder)): file_sha256(path) for path in sorted(files)},
                "progress_page": str(stage.page_path())}

    @card(type="blank")
    @step
    def end(self):
        """RECORD.json and SUMMARY.md, the CLAIM 2024 and REFORMS report written and checked, the
        verdict in ENDED.json, which the report never reads, and for an edit that ended well the
        pointer the stats stage reads it through."""
        with self.beat("the record and the report") as beat:
            self.ended, self.short = self.ended_in(), self.shortfalls()
            lines = self.summary_lines() + [f"- short of the draw: {', '.join(self.short)}"] * bool(self.short)
            Path(self.path("SUMMARY.md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
            write_json(self.path("RECORD.json"), self.record())
            ok, self.report_line = stage.claim_report(self.folder, study=STUDY)
            self.verdict = 0 if ok and not self.short else 1
            ended = {"folder": self.folder, "run": self.ended["run"], "started_run": self.where["run"], "key": self.key,
                     "started": self.started, "ended": self.ended["ended"], "verdict": self.verdict, "report": self.report_line}
            write_json(self.path("ENDED.json"), ended)
            write_json(Path(self.root) / f"{self.which}.last.json", ended)
            if self.which == "edit" and self.verdict == 0:
                write_json(Path(self.root) / "edit.json", ended)
            # The job's report puts its own "- " before each line it relays, so a line is printed
            # without the one SUMMARY.md's list gives it, and a blank line not at all.
            for line in [*lines, f"report: {self.report_line}", f"verdict {self.verdict}"]:
                if line.strip():
                    print(f"RealismFlow: {line.removeprefix('- ')}", flush=True)
            beat.say(f"verdict {self.verdict}; report {self.report_line}")
            stage.finish(self.verdict, [*lines[:6], f"report: {self.report_line}", f"folder: {self.folder}"])
        current.card.append(Markdown(f"# Realism {self.which}, run {current.run_id}\n\nFolder {self.folder}; verdict "
                                     f"{self.verdict}; report {self.report_line}; progress page {stage.page_path()}.\n\n"
                                     + "\n".join(lines)))


if __name__ == "__main__":
    RealismFlow()
