#!/usr/bin/env python3
"""One trial of the auto-anatomist screen on one card: the plan's rows cut into crops, the network
trained under the trial's words in one call, read on the validation CTs every few epochs, and its
entry written for the join (docs/research/autoanatomist-screen/README.md).

    python tools/autoanatomist_trial.py --plan PLAN.json --task N --tasks M --data DATA_ROOT \\
        --out STUDY_FOLDER [--workers K] [--scratch FOLDER]

The task names one trial of schwingnet.autoanatomist_screen.trials(plan), the order every node
counts them in. Each row's CT is the file <id>.nii.gz under the plan's ct folder, its label map the
file of the same name under the labels folder whose nearest folder is labels_folder, where <id> is
the row's item less its source and the colon (enhance_pet:0022 is 0022.nii.gz), each found once or
the trial refuses. The second channel of every crop is every named vertebra, so each label map is
copied first with every label the plan does not name zeroed, C1, C2, the sacrum and the hips
among them, on the same grid and never reoriented, and the copy is what the vendored rows read.
The rows' crops are rendered by a pool of processes that never touch the card into a cache under
the scratch folder, one file a row, and read back by the vendored examples_for; each row's jitter
is drawn once, from a seed its item gives, as the vendored package draws it.

The session (grid/autoanatomist/autoanatomist/session.py) trains every step in one call, so one
step function serves the whole trial; after each epoch evaluation_epochs names, the callback reads
the validation CTs on the CT-only path (Session.evaluate) and keeps the reading. The trial's folder,
STUDY_FOLDER/trials/<trial>/, then holds readings.jsonl (every reading whole), latents.npz (each
crop's bottleneck vector on the CT-only path, training and validation, keyed by row and level),
session/ (the weights, the optimizer and every step's row, Session.save), environment.json (the
host, the card, the packages and the timings) and entry.json last, checked by entry_problems
before it is written, which the join reads; PROGRESS.txt says where the trial is, a line an event.
A trial that cannot finish leaves why.txt and no entry, and the join counts it failed; so does one
whose training diverged, a step's loss or, at a reading, a weight no longer a finite number, which
would otherwise read every crop empty and so a finite worst distance.

Exit 0 with the entry written; 2 for a plan, a task or an input that does not hold; 3 for an
environment whose packages are not the pinned ones (schwingnet.autoanatomist_screen.PINS); 4 for a
plan of the gpu class on a node where JAX sees no GPU; 1 for a trial that failed while training.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# As in tools/train.py: this folder leaves the path so tools/profile.py never shadows the standard
# library's profile; the package, the pinned beethoven-qa and the vendored auto-anatomist join it.
sys.path[0] = str(ROOT / "src")
for _folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "grid" / "autoanatomist"):
    if str(_folder) not in sys.path:
        sys.path.insert(1, str(_folder))

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import multiprocessing  # noqa: E402
import os  # noqa: E402
import platform  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import statistics  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from importlib import metadata  # noqa: E402

from schwingnet.autoanatomist_screen import (  # noqa: E402
    ENTRY_VERSION,
    FINAL_KEYS,
    PINS,
    entry_problems,
    evaluation_epochs,
    plan_of,
    plan_problems,
    steps_per_epoch,
    task_problems,
    total_steps,
    train_count,
    trials,
)

TRIAL_OUTPUTS = ("entry.json", "why.txt", "readings.jsonl", "latents.npz", "environment.json", "PROGRESS.txt")


class TrialRefused(Exception):
    """What keeps a trial from starting, with the exit it ends with."""

    def __init__(self, code, why):
        super().__init__(why)
        self.code = code


# --- the inputs -------------------------------------------------------------------------------------


def files_named(root):
    """Every .nii.gz under a folder by its name less .nii.gz, with each path it was found at."""
    found = {}
    for path in sorted(Path(root).rglob("*.nii.gz")):
        found.setdefault(path.name[: -len(".nii.gz")], []).append(path)
    return found


def file_id(row):
    """The file name a row's item gives: the item less its source and the colon."""
    prefix = row["source"] + ":"
    if not row["item"].startswith(prefix):
        raise TrialRefused(2, f"{row['item']} is not named <source>:<id> for its source {row['source']}")
    return row["item"][len(prefix):]


def one_of(paths, what):
    if not paths:
        raise TrialRefused(2, f"no {what}")
    if len(paths) > 1:
        raise TrialRefused(2, f"{what} is found twice ({paths[0]} and {paths[1]}), so which to read is a guess")
    return paths[0]


def inputs_of(plan, data_root):
    """Each row's CT and label map on the data root, found once each, or the trial refused."""
    found = {}
    for source, entry in plan.data.items():
        cts = files_named(Path(data_root) / entry["ct"])
        labels = {name: [p for p in paths if entry["labels_folder"] in p.parent.parts[-1:]]
                  for name, paths in files_named(Path(data_root) / entry["labels"]).items()}
        for row in (r for r in plan.rows if r["source"] == source):
            name = file_id(row)
            found[row["item"]] = (one_of(cts.get(name, []), f"CT {name}.nii.gz under {entry['ct']}"),
                                  one_of(labels.get(name, []), f"label map {entry['labels_folder']}/{name}.nii.gz"))
    return found


def row_seed(item):
    """The seed of a row's one jitter draw, from its item alone, so every trial cuts a row alike."""
    return int.from_bytes(hashlib.sha256(item.encode("utf-8")).digest()[:4], "big")


def session_rows(plan, inputs, scratch):
    """The vendored package's volume rows, each reading the spine-only copy its label map gets,
    with the original label map the copy is made from, in the plan's order."""
    rows = []
    for row in plan.rows:
        ct, labels = inputs[row["item"]]
        names = plan.data[row["source"]]["names"]
        copy = Path(scratch) / "labels" / f"{row['source']}-{file_id(row)}.nii"
        rows.append(({"kind": "volume", "id": row["item"], "ct": str(ct), "labels": str(copy), "names": dict(names),
                      "seed": row_seed(row["item"]), "frame": "centroid"}, str(labels), row["part"]))
    return rows


# --- the crops --------------------------------------------------------------------------------------


def spine_only_copy(source, target, names):
    """A copy of a label map holding only the labels names gives, every other label zeroed, on
    the same grid with the same header, written uncompressed for the render alone."""
    import nibabel as nib
    import numpy as np

    image = nib.load(source)
    labels = np.asanyarray(image.dataobj)
    if not np.issubdtype(labels.dtype, np.integer):
        labels = np.rint(labels).astype(np.int32)
    kept = np.where(np.isin(labels, [int(value) for value in names]), labels, 0).astype(labels.dtype)
    header = image.header.copy()
    header.set_data_dtype(kept.dtype)
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(kept, image.affine, header), target)


def render_one(job):
    """One row's crops into the cache, from its spine-only copy, which goes once they are cut:
    (row id, seconds, None) or (row id, seconds, why it could not be cut)."""
    row, labels, cfg, cache = job
    from autoanatomist import rows as vendored

    began = time.time()
    path = Path(cache) / (vendored.row_digest(row, cfg) + ".npz")
    if path.is_file():
        return row["id"], 0.0, None
    try:
        spine_only_copy(labels, row["labels"], row["names"])
        vendored.save_part(str(path), vendored.render_row(row, cfg))
    except (OSError, ValueError) as error:
        return row["id"], time.time() - began, f"{type(error).__name__}: {error}"
    finally:
        Path(row["labels"]).unlink(missing_ok=True)
    return row["id"], time.time() - began, None


def render_cache(jobs, workers, progress):
    """Every row's crops cut by a pool of spawned processes that see no GPU, so the card stays the
    trial's: JAX_PLATFORMS is cpu in the pool's environment alone."""
    before = os.environ.get("JAX_PLATFORMS")
    os.environ["JAX_PLATFORMS"] = "cpu"
    try:
        pool = multiprocessing.get_context("spawn").Pool(workers)
    finally:
        if before is None:
            os.environ.pop("JAX_PLATFORMS", None)
        else:
            os.environ["JAX_PLATFORMS"] = before
    seconds, failed = [], []
    with pool:
        for done, (item, took, why) in enumerate(pool.imap_unordered(render_one, jobs), start=1):
            seconds.append(took)
            if why:
                failed.append(f"{item}: {why}")
            if done % 10 == 0 or done == len(jobs):
                progress(f"crops cut for {done} of {len(jobs)} rows")
    if failed:
        raise TrialRefused(2, f"{len(failed)} rows could not be cut, first {failed[0]}")
    return seconds


# --- the trial --------------------------------------------------------------------------------------


def measure(value):
    """A reading's value as JSON keeps it: a finite float or int, else null."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    value = float(value)
    return value if math.isfinite(value) else None


def point_of(epoch, steps, losses, reading):
    return {"epoch": epoch, "steps": steps, "loss": measure(sum(losses) / len(losses)) if losses else None,
            "dice": measure(reading["dice"]), "distance_mm": measure(reading["distance_mm"]),
            "surface_missing": measure(reading["surface_missing"]), "centroid_mm": measure(reading["centroid_mm"]),
            "name_accuracy": measure(reading["named_right"])}


def plain(value):
    """A reading as JSON holds it: numpy numbers as Python ones, non-finite floats as null."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, str) or value is None:
        return value
    return measure(value)


def weights_finite(session):
    """Whether every weight of the network is a finite number, so a reading reads a trained network
    and not one the update after the last finite loss made NaN."""
    import jax
    import jax.numpy as jnp
    from flax import nnx

    return all(bool(jnp.isfinite(leaf).all()) for leaf in jax.tree_util.tree_leaves(nnx.state(session.model, nnx.Param)))


def train_and_read(session, train_ex, validation_ex, plan, folder, progress):
    """Every step in one call, a reading after each epoch evaluation_epochs names: (points, each
    step row's seconds). A step whose loss is not a finite number, or a reading whose weights are
    not, stops the trial with 1, since a diverged network outlines nothing and every crop would read
    the worst distance as though it were a result."""
    per_epoch = steps_per_epoch(train_count(plan), plan.batch)
    read_at, points, losses, seconds = set(evaluation_epochs(plan)), [], [], []

    def on_step(row):
        if not math.isfinite(row["total"]):
            raise TrialRefused(1, f"training diverged: the loss of step {row['step']} is {row['total']}")
        losses.append(row["total"])
        seconds.append(row["seconds"])
        done = row["step"] + 1
        if done % per_epoch:
            return
        epoch = done // per_epoch
        if epoch in read_at:
            if not weights_finite(session):
                raise TrialRefused(1, f"training diverged: a weight is not a finite number after epoch {epoch}")
            reading = session.evaluate(validation_ex)
            with open(folder / "readings.jsonl", "a", encoding="utf-8") as handle:
                handle.write(json.dumps(plain(dict(reading, epoch=epoch))) + "\n")
            points.append(point_of(epoch, done, losses[-per_epoch:], reading))
            progress(f"epoch {epoch} of {plan.epochs}: distance {points[-1]['distance_mm']} mm, "
                     f"dice {points[-1]['dice']}, loss {points[-1]['loss']}")
        elif epoch % 5 == 0:
            progress(f"epoch {epoch} of {plan.epochs}: loss {sum(losses[-per_epoch:]) / per_epoch:.4f}")

    session.train(train_ex, total_steps(plan), on_step=on_step)
    return points, seconds


def steady_seconds(seconds):
    """A step's seconds once nothing compiles: the median step, since a step whose batch has a shape
    not seen before traces and compiles inside its timing, and those steps are few."""
    return statistics.median(seconds) if seconds else 0.0


def save_latents(session, examples, items, folder):
    """Each crop's latent on the CT-only path, keyed by its row's item, part and level index."""
    import numpy as np

    arrays = {}
    for part, ex in examples.items():
        arrays[f"{part}_latent"] = session.latents(ex)
        arrays[f"{part}_item"] = np.array([items[part][int(s)] for s in ex.spine])
        arrays[f"{part}_name"] = np.asarray(ex.names)
    np.savez(folder / "latents.npz", **arrays)


def check_environment(plan):
    """The installed packages against the pins and the backend against the plan's class: the
    versions found, the backend and the devices, or the trial refused (3 or 4)."""
    import jax

    found = {}
    for pin in PINS:
        name, version = pin.split("==")
        name = name.split("[")[0]
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = None
        if found[name] != version:
            raise TrialRefused(3, f"{name} is {found[name]} here, and the pins say {version}")
    backend = jax.default_backend()
    if plan.job_class == "gpu" and backend != "gpu":
        raise TrialRefused(4, f"the plan is of the gpu class and JAX's backend here is {backend}")
    return found, backend, [d.device_kind for d in jax.devices()]


def gpu_stack():
    """The versions of JAX and of every NVIDIA library the venv holds, which the cuda12 extra takes as
    ranges, so the CUDA stack a trial ran on is on record beside the pins."""
    found = {}
    for dist in metadata.distributions():
        name = dist.metadata["Name"] or ""
        if name.lower().startswith(("nvidia-", "jax")):
            found[name] = dist.version
    return dict(sorted(found.items()))


def write_json(path, value):
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def run_trial(args, plan, trial, folder, progress):
    began = time.time()
    found, backend, devices = check_environment(plan)
    import jax

    # Every card computes float32 as float32: an L40S would otherwise take its convolutions in TF32
    # while a V100 cannot, and one array's trials land on both.
    jax.config.update("jax_default_matmul_precision", "highest")
    from autoanatomist import rows as vendored
    from autoanatomist.blocks import parse
    from autoanatomist.session import Session

    session = Session.new(parse(list(trial.words)))
    progress(f"{trial.id}: {' '.join(trial.words)} on {backend} ({', '.join(devices)})")
    scratch = Path(tempfile.mkdtemp(prefix=f"autoanatomist-{trial.id}-", dir=args.scratch))
    try:
        rows = session_rows(plan, inputs_of(plan, args.data), scratch)
        cache = scratch / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        jobs = [(row, labels, session.cfg, str(cache)) for row, labels, _ in rows]
        cut = render_cache(jobs, max(1, min(args.workers, len(jobs))), progress)
        rendered = time.time() - began
        parts = {part: [row for row, _, p in rows if p == part] for part in ("train", "validation")}
        examples = {part: vendored.examples_for(parts[part], session.cfg, str(cache)) for part in parts}
        items = {part: [row["id"] for row in parts[part]] for part in parts}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    progress(f"{len(examples['train'])} training and {len(examples['validation'])} validation crops")
    points, step_seconds = train_and_read(session, examples["train"], examples["validation"], plan, folder, progress)
    session.save(str(folder / "session"))
    save_latents(session, examples, items, folder)
    spines = examples["train"].spines()
    step_crops = plan.batch * (sum(len(s) for s in spines) / len(spines))
    environment = {"host": socket.gethostname(), "slurm_job": os.environ.get("SLURM_JOB_ID") or "none",
                   "slurm_array_job": os.environ.get("SLURM_ARRAY_JOB_ID") or "none",
                   "slurm_array_task": os.environ.get("SLURM_ARRAY_TASK_ID") or "none",
                   "python": platform.python_version(), "backend": backend, "devices": devices, "packages": found,
                   "pins": list(PINS), "gpu_stack": gpu_stack(),
                   "matmul_precision": str(jax.config.jax_default_matmul_precision),
                   "step_seconds": {"steps": len(step_seconds), "first": round(step_seconds[0], 3) if step_seconds else None,
                                    "median": round(steady_seconds(step_seconds), 4), "sum": round(sum(step_seconds), 1)},
                   "workers": args.workers, "render_seconds": round(rendered, 1),
                   "row_render_seconds_max": round(max(cut), 1) if cut else None,
                   "train_and_read_seconds": round(time.time() - began - rendered, 1),
                   "crops": {part: int(len(ex)) for part, ex in examples.items()}}
    write_json(folder / "environment.json", environment)
    return {"version": ENTRY_VERSION, "screen": plan.screen, "trial": trial.id, "arm": trial.arm, "seed": trial.seed,
            "words": list(trial.words), "steps": total_steps(plan), "epochs": points,
            "final": {key: points[-1][key] for key in FINAL_KEYS},
            "seconds": round(time.time() - began, 3),
            "seconds_per_crop": steady_seconds(step_seconds) / step_crops if step_crops else 0.0,
            "train_rows": len(parts["train"]), "validation_rows": len(parts["validation"])}


def trial_of(args):
    """The plan read and the task's trial, or the trial refused with 2."""
    try:
        record = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise TrialRefused(2, f"the plan {args.plan} cannot be read ({type(error).__name__})") from error
    found = plan_problems(record)
    if found:
        raise TrialRefused(2, f"the plan does not hold: {found[0]}")
    plan = plan_of(record)
    found = task_problems(plan, args.task, args.tasks)
    if found:
        raise TrialRefused(2, found[0])
    return plan, trials(plan)[args.task]


def main(argv=None):
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    top.add_argument("--plan", required=True, help="the screen's plan file, grid/screens/<plan>.json")
    top.add_argument("--task", type=int, required=True, help="the trial's place in the plan's order, from 0")
    top.add_argument("--tasks", type=int, required=True, help="how many trials the plan holds, the array's size")
    top.add_argument("--data", required=True, help="the data root the plan's folders lie under")
    top.add_argument("--out", required=True, help="the study's folder, under which trials/<trial>/ is written")
    top.add_argument("--workers", type=int, default=min(8, len(os.sched_getaffinity(0))),
                     help="processes cutting crops (default: the CPUs this job holds, at most 8)")
    top.add_argument("--scratch", default=None, help="the folder the label copies and the crop cache go in (default TMPDIR)")
    args = top.parse_args(argv)
    try:
        plan, trial = trial_of(args)
    except TrialRefused as refused:
        print(f"autoanatomist_trial: {refused}", flush=True)
        return refused.code
    folder = Path(args.out) / "trials" / trial.id
    folder.mkdir(parents=True, exist_ok=True)
    for name in TRIAL_OUTPUTS:
        (folder / name).unlink(missing_ok=True)
    shutil.rmtree(folder / "session", ignore_errors=True)

    def progress(line):
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        with open(folder / "PROGRESS.txt", "a", encoding="utf-8") as handle:
            handle.write(f"{stamp} UTC {line}\n")
        print(f"autoanatomist_trial: {line}", flush=True)

    try:
        entry = run_trial(args, plan, trial, folder, progress)
        found = entry_problems(entry, trial, plan)
        if found:
            raise TrialRefused(1, f"the entry it would write does not hold: {found[0]}")
    except TrialRefused as refused:
        (folder / "why.txt").write_text(f"{refused}\n", encoding="utf-8")
        progress(f"refused: {refused}")
        return refused.code
    except Exception as error:  # whatever stops the training, said in why.txt, the trial failed
        (folder / "why.txt").write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
        progress(f"failed: {type(error).__name__}: {error}")
        raise
    write_json(folder / "entry.json", entry)
    progress(f"{trial.id}: final distance {entry['final']['distance_mm']} mm, dice {entry['final']['dice']}, "
             f"{entry['seconds']:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
