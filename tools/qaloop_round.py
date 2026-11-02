#!/usr/bin/env python3
"""One round of the QA loop (flows/qaloop.py, docs/research/qa-loop/PREREG.md): the network
trained further, then every gate's question asked of what the round has, the answers written to
gates.json for the flow's controller (tools/qaloop_gates.py, controller) to decide the next round.

    python tools/qaloop_round.py --plan PLAN.json --state STATE.json --out ROUND_FOLDER \\
        --work WORK_FOLDER [--data DATA_ROOT] [--workers K]

The plan is grid/qaloop/<plan>.json; the state is what the controller carries from round to round
(the round's number, its configuration, every earlier round's held-out distance, the space the
round before measured and the folder of the session it saved). WORK_FOLDER holds what the rounds
share: the crops' cache, one file a row, and the pairs' cache, one file a case; ROUND_FOLDER this
round's gates.json, PROGRESS.txt, a line an event, and its session (the network, its optimizer and
every step's row since the first round), so a round run again starts from the round before's.

What a round does, in order:

1. The space plan: the bytes on disk and the peak memory each block took per unit in the earlier
   rounds (or a first measure), against the disk and memory free, gives how many rows, cases and
   processes fit at once; the pools below take that many workers and the controller grows the rows
   no further than the memory holds.
2. The pairs: C-ArmLSpine's cases under the data root's carmlspine folder, read once by a pool and
   cached (tools/qaloop_samples.py); where there is none and the plan allows it, stand-ins, said so.
3. The network: each anomaly class's phantom rows (the plan's start level and count), the selection's
   seeds apart from the gate's, rendered into crops by a pool, then steps_per_round more steps of
   the session under the plan's words with the configuration's name weight.
4. The gates: convergence from the session's record and the held-out distance of every round;
   anomaly from each class's held crops (Dice, the name head, a nearest-class-mean probe on the
   latent); the fingerprint chosen by the greedy search over the landmarks the presence floor keeps,
   on the selection's phantoms and pairs, and judged on the gate's; presence on the gate's real
   frames; real naming on the gate's pairs; latency of the naming path.

Exit 0 with gates.json written; 2 for a plan or state that does not hold; 1 for a round that failed,
with why.txt beside it.
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
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import multiprocessing  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402
from concurrent.futures.process import BrokenProcessPool  # noqa: E402

import numpy as np  # noqa: E402


def load_tool(name):
    """A module of tools/ by its path, since tools/ is not on the path."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S = load_tool("qaloop_samples")
G = S.G

# Each anomaly class's level, the one its crops are judged on, and where its training rows start:
# four levels from there hold that level and its neighbours.
KEY_LEVEL = {"six_lumbar": "L6", "four_lumbar": "L4", "t13": "T13", "lumbar_rib": "L1", "no_rib_t12": "T12"}
ROW_START = {"typical": "L2", "lumbar_rib": "T12", "no_rib_t12": "T11", "six_lumbar": "L3", "four_lumbar": "L1",
             "t13": "T12"}
ROW_COUNT = 4
GATE_SEED = 1_000_000          # the gate's rows and persons are drawn from seeds this far above the selection's
WATCH_SEED = 2_000_000         # the watch's held rows, apart from both, so stopping early never looks at the gate's
RAM_SHARE, DISK_SHARE = 0.8, 0.9
INSANE_EXIT = 3                # a round stopped by numbers that cannot be right; the flow runs it no second time


class InsaneAnswer(Exception):
    """A check whose numbers cannot be right (tools/qaloop_gates.py, insane)."""


class Progress:
    """PROGRESS.txt, a line an event, read by the flow's beat."""

    def __init__(self, folder):
        self.path = Path(folder) / "PROGRESS.txt"
        self.began = time.time()

    def say(self, words):
        line = f"{time.time() - self.began:8.1f}s {words}"
        with open(self.path, "a") as f:
            f.write(line + "\n")
        print(line, flush=True)


# ---------------------------------------------------------------- measuring space

def peak_reset():
    """Start a new peak of resident memory for this process (Linux: writing 5 to clear_refs resets
    VmHWM); False where the kernel will not, and the peak then runs from the process's start."""
    try:
        with open("/proc/self/clear_refs", "w") as f:
            f.write("5")
        return True
    except OSError:
        return False


def peak_bytes():
    """The process's peak resident memory since the last reset, in bytes."""
    try:
        for line in open("/proc/self/status"):
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
    except OSError:
        pass
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def rss_of(pid):
    """A process's resident memory in bytes; 0 where it has gone or cannot be read."""
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def descendants(pid):
    """Every process below pid, its children and theirs, read from /proc."""
    parent_of = {}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return []
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as f:
                stat = f.read()
            # the parent is the field after the state, which follows the command's last parenthesis
            parent_of[int(entry)] = int(stat[stat.rindex(")") + 2:].split()[1])
        except (OSError, ValueError, IndexError):
            continue
    out, frontier = [], [pid]
    while frontier:
        here = frontier.pop()
        kids = [c for c, q in parent_of.items() if q == here]
        out += kids
        frontier += kids
    return out


def tree_rss():
    """The resident memory of this process and every process below it: a pool's spawned workers count."""
    me = os.getpid()
    return rss_of(me) + sum(rss_of(c) for c in descendants(me))


class PeakWatch:
    """The most resident memory this process and the processes it started held above what they held
    when the block began, sampled every `every` seconds by a thread and joined with this process's
    own peak since the block began: one process's peak alone misses a pool's workers."""

    def __init__(self, every=0.25):
        self.every, self.peak, self.base, self.top = every, 0, 0, 0
        self._stop = threading.Event()
        self._thread = None
        self._own = False

    def __enter__(self):
        self.base = tree_rss()
        self.top = self.base
        self._own = peak_reset()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def _sample(self):
        while not self._stop.wait(self.every):
            self.top = max(self.top, tree_rss())

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        self.top = max(self.top, tree_rss(), peak_bytes() if self._own else 0)
        self.peak = max(self.top - self.base, 0)
        return False


def meminfo(name):
    """A line of /proc/meminfo in bytes, or None."""
    try:
        for line in open("/proc/meminfo"):
            if line.startswith(name + ":"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def read_number(path):
    try:
        text = Path(path).read_text().strip()
    except OSError:
        return None
    if text == "max":
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    return value if value < 2 ** 60 else None


def reclaimable(folder, v2):
    """The page cache a cgroup holds that the kernel gives back before it kills: its inactive files."""
    key = "inactive_file" if v2 else "total_inactive_file"
    try:
        for line in open(Path(folder) / "memory.stat"):
            name, _, value = line.partition(" ")
            if name == key:
                return int(value)
    except (OSError, ValueError):
        pass
    return 0


def cgroup_rooms():
    """The room left under each memory limit of this process's own cgroups, cgroup v2's and v1's
    memory controller's, at its own path and at every parent's up to the root: {where: bytes}. A
    Slurm job's limit is on its job's cgroup, never on the root, which is why the path is walked."""
    out = {}
    try:
        lines = Path("/proc/self/cgroup").read_text().splitlines()
    except OSError:
        return out
    for line in lines:
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        _, controllers, path = parts
        if controllers == "":
            base, limit_name, use_name, v2 = Path("/sys/fs/cgroup"), "memory.max", "memory.current", True
        elif "memory" in controllers.split(","):
            base, limit_name, use_name, v2 = Path("/sys/fs/cgroup/memory"), "memory.limit_in_bytes", "memory.usage_in_bytes", False
        else:
            continue
        folder = base / path.lstrip("/")
        while True:
            limit, use = read_number(folder / limit_name), read_number(folder / use_name)
            if limit is not None and use is not None:
                out[f"cgroup {folder}"] = limit - max(use - reclaimable(folder, v2), 0)
            if folder == base or base not in folder.parents:
                break
            folder = folder.parent
    return out


def slurm_limit():
    """The memory Slurm gave the job, in bytes, from its environment; None outside a job or where unsaid."""
    per_node = os.environ.get("SLURM_MEM_PER_NODE")
    if per_node and per_node.isdigit():
        return int(per_node) * 2 ** 20
    per_cpu, count = os.environ.get("SLURM_MEM_PER_CPU"), os.environ.get("SLURM_CPUS_ON_NODE")
    if per_cpu and per_cpu.isdigit() and count and count.isdigit():
        return int(per_cpu) * int(count) * 2 ** 20
    return None


def memory_bounds():
    """Each bound on the memory this job may still take, by where it comes from: the host's
    MemAvailable, the room under every cgroup limit above this process, and Slurm's grant less what
    this process and its children hold."""
    bounds = {}
    avail = meminfo("MemAvailable")
    if avail is not None:
        bounds["MemAvailable"] = avail
    bounds.update(cgroup_rooms())
    granted = slurm_limit()
    if granted is not None:
        bounds["Slurm's grant"] = granted - tree_rss()
    return bounds


def free_memory():
    """The memory this job may still take: the least of its bounds, or 0 where none can be read, so a
    host that says nothing grows nothing."""
    bounds = memory_bounds()
    return max(min(bounds.values()), 0) if bounds else 0


def binding_bound():
    """The name of the bound that binds now, for the record."""
    bounds = memory_bounds()
    return min(bounds, key=bounds.get) if bounds else "none readable"


def folder_bytes(folder):
    total = 0
    for dirpath, _, files in os.walk(folder):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total


class Space:
    """Each block's measure this round: its bytes on disk and peak memory, per unit of the block."""

    def __init__(self):
        self.blocks = {}

    def measure(self, name, unit, units, disk_bytes, peak):
        """One block: its bytes on disk and the peak memory it took above where it began (a PeakWatch's
        peak, every process of the block counted), each per unit; peak None where none was watched."""
        units = max(int(units), 1)
        self.blocks[name] = {"unit": unit, "units": units, "disk_bytes": int(disk_bytes / units),
                             "rss_bytes": int(peak / units) if peak is not None else 0,
                             "peak_bytes": int(peak) if peak is not None else 0}


def cpus():
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count() or 1


def workers_for(per_unit_ram, asked, ram):
    """How many processes a pool takes: every CPU the job has, or the plan's number, no more than
    the free memory holds at the measured peak of one unit."""
    n = asked or cpus()
    if per_unit_ram > 0:
        n = min(n, max(1, int(ram * RAM_SHARE // per_unit_ram)))
    return max(1, n)


# ---------------------------------------------------------------- the network's rows

def class_rows(classes, per_class, part, spacing, noise):
    """Each class's phantom rows: per_class rows of four levels from the class's start, the gate's
    seeds a million above the selection's and the watch's two million, so no row is in two parts."""
    base = {"gate": GATE_SEED, "watch": WATCH_SEED}.get(part, 0)
    rows = []
    for i, kind in enumerate(classes):
        for j in range(per_class):
            seed = base + 10_000 * i + j
            rows.append({"kind": "phantom", "id": f"{part}-{kind}-{seed}", "phenotype": kind, "start": ROW_START[kind],
                         "count": ROW_COUNT, "seed": seed, "spacing": float(spacing), "sub": 1, "noise": float(noise)})
    return rows


def render_job(args):
    """One row's crops rendered into the cache, for a pool that never touches the card."""
    S.cpu_only()
    row, cfg_record, cache, jitter = args
    from autoanatomist import rows as R
    from autoanatomist.model import Config
    cfg = Config(**cfg_record)
    path = os.path.join(cache, R.row_digest(row, cfg, jitter) + ".npz")
    if not os.path.exists(path):
        R.save_part(path, R.render_row(row, cfg, jitter))
    return path


def config_record(cfg):
    return {"keys": tuple(cfg.keys), "widths": tuple(cfg.widths), "shape": tuple(cfg.shape), "spacing": cfg.spacing,
            "groups": cfg.groups, "normalise": cfg.normalise, "architecture": cfg.architecture,
            "objective": cfg.objective}


def examples(rows, cfg, cache, workers, say):
    """The rows' crops, the ones not cached rendered first by a pool of workers, then read in order."""
    from autoanatomist import rows as R
    os.makedirs(cache, exist_ok=True)
    todo = [r for r in rows if not os.path.exists(os.path.join(cache, R.row_digest(r, cfg, True) + ".npz"))]
    if todo:
        say(f"rendering {len(todo)} rows with {workers} workers")
        run_pool(render_job, [(r, config_record(cfg), cache, True) for r in todo], workers, say)
    return R.examples_for(rows, cfg, cache)


def row_classes(ex, rows):
    """Each crop's class and level name: the phenotype of the row it came from and its level."""
    from autoanatomist import naming
    kinds = np.asarray([rows[s]["phenotype"] for s in ex.spine])
    levels = np.asarray([naming.NAMES[int(n)] for n in ex.names])
    return kinds, levels


def probe_labels(kinds, levels):
    """The probe's label of each crop: an anomaly class's own level is that class, every crop of a
    typical row normal, and the other crops of an anomalous row none, being typical levels of an
    anomalous column."""
    out = []
    for k, lv in zip(kinds, levels):
        if k == "typical":
            out.append("normal")
        elif KEY_LEVEL.get(k) == lv:
            out.append(k)
        else:
            out.append(None)
    return out


def session_for(source, words, say):
    """The round's session: the one the round before saved (its folder, source), its words brought
    to these words (the controller changes only the name weight, which the next step takes up), or
    a new one for the first round."""
    from autoanatomist import blocks
    from autoanatomist.session import Session
    folder = Path(source) if source else None
    b = blocks.parse(words)
    if folder is not None and (folder / "session.json").is_file():
        s = Session.load(str(folder))
        if s.blocks.words() != b.words():
            say(f"session words now {' '.join(b.changed())}")
            s.blocks = b
        return s
    say(f"new session: {' '.join(b.changed())}")
    return Session.new(b)


def per_crop(session, ex, batch=16):
    """The CT-only path on every crop: its target vertebra's hard Dice, the name head's name and
    the latent. The logits are brought back onto the crops' grid batch crops at a time, since all of
    them at once would hold every crop's full grid on the card together."""
    import jax
    import jax.numpy as jnp
    from autoanatomist import train
    out = train.predict(session.model, ex.hu)
    logits = out["logits"]
    dice = []
    for at in range(0, len(logits), batch):
        part = logits[at:at + batch]
        shape = (len(part),) + tuple(session.cfg.shape) + (part.shape[-1],)
        up = np.asarray(jax.image.resize(jnp.asarray(part), shape, "trilinear"))
        dice.append(train.hard_dice(up > 0.0, ex.masks[at:at + batch] >= train.MASK_THRESHOLD)[:, 0])
    dice = np.concatenate(dice) if dice else np.empty(0)
    return dice, np.argmax(out["name_logits"], -1), np.asarray(out["latent"])


def latents_of(session, ex):
    """The latent of every crop on the CT-only path, which is all the probe needs of the selection."""
    from autoanatomist import train
    return np.asarray(train.predict(session.model, ex.hu)["latent"])


def anomaly_result(classes, gate, sel, bars):
    """The anomaly gate from the gate's crops and the selection's latents."""
    kinds, levels = gate["kinds"], gate["levels"]
    train_lab = probe_labels(sel["kinds"], sel["levels"])
    test_lab = probe_labels(kinds, levels)
    keep_tr = [i for i, x in enumerate(train_lab) if x is not None]
    keep_te = [i for i, x in enumerate(test_lab) if x is not None]
    recall = G.probe(sel["latent"][keep_tr], [train_lab[i] for i in keep_tr],
                     gate["latent"][keep_te], [test_lab[i] for i in keep_te]) if keep_tr and keep_te else {}
    per_class = {}
    names = [c if c != "typical" else "normal" for c in classes]
    for kind, label in zip(classes, names):
        m = (kinds == "typical") if kind == "typical" else (kinds == kind) & (levels == KEY_LEVEL[kind])
        n = int(m.sum())
        probed = recall.get(label, {})
        probe_n = int(probed.get("n", 0))
        probe_recall = float(probed.get("recall", float("nan")))
        per_class[label] = {"n": n, "dice": float(gate["dice"][m].mean()) if n else float("nan"),
                            "named_right": float(gate["right"][m].mean()) if n else float("nan"),
                            "probe_recall": probe_recall, "probe_n": probe_n,
                            "dice_low": G.mean_low(gate["dice"][m]) if n else float("nan"),
                            "named_low": G.wilson(int(gate["right"][m].sum()), n)[0] if n else float("nan"),
                            "probe_low": (G.wilson(int(round(probe_recall * probe_n)), probe_n)[0]
                                          if probe_n and math.isfinite(probe_recall) else float("nan"))}
    result = G.anomaly_gate(per_class, bars, names)
    result["per_class"] = per_class
    return result


# ---------------------------------------------------------------- the pairs

def pairs_for(plan, data, work, workers, say):
    """The pairs the round reads: C-ArmLSpine's cases where the data root holds them, else the plan's
    stand-ins, else none; each with its person and part. Returns (pairs, record)."""
    spec = plan.get("pairs", {})
    size = int(spec.get("size", 512))
    cache = Path(work) / "pairs"
    cache.mkdir(parents=True, exist_ok=True)
    root = Path(data) / spec.get("root", "carmlspine") if data else None
    if root is not None and (root / "levels.json").is_file():
        cases, skipped = S.carm_cases(root)
        say(f"pairs: {len(cases)} C-ArmLSpine cases to read with {workers} workers; left out {skipped}")
        jobs = [(str(root), c["case"], c["levels"], str(cache), size) for c in cases]
        results = run_pool(S.pair_job, jobs, workers)
        failed = {}
        pairs = []
        for c, (path, why) in zip(cases, results):
            if path is None:
                failed[why] = failed.get(why, 0) + 1
                continue
            pairs.append(dict(S.load_pair(path), person=c["person"], part=c["part"], source="carmlspine"))
        record = {"source": "C-ArmLSpine", "cases": len(cases), "read": len(pairs), "left_out": skipped,
                  "failed": failed, "stand_in": False}
        external, record["external"] = external_pairs(spec, data, say)
        return pairs + external, record
    count = int(spec.get("stand_ins", 0))
    if count <= 0:
        say("pairs: none (no C-ArmLSpine under the data root and no stand-ins in the plan)")
        return [], {"source": "none", "stand_in": False}
    say(f"pairs: no C-ArmLSpine here; {count} stand-ins with {workers} workers")
    seeds = [7_000_000 + i for i in range(count)]
    results = run_pool(S.stand_in_job, [(s, str(cache), size) for s in seeds], workers)
    pairs = []
    for i, (seed, (path, _)) in enumerate(zip(seeds, results)):
        part = "validation" if i % 3 == 2 else "training"
        pairs.append(dict(S.load_pair(path), person=f"standin:{seed}", part=part))
    return pairs, {"source": "stand-ins", "cases": count, "read": len(pairs), "stand_in": True}


def external_pairs(spec, data, say):
    """The plan's external real arms (tools/realx_pairs.py, docs/research/qa-loop-external/PREREG.md): each source's
    built pairs under the data root, every one the gates' (part validation), none the selection's; the persons a
    source holds out for its own test are named in its manifest and never read. Returns (pairs, record)."""
    pairs, record = [], {}
    for ext in spec.get("external", []):
        folder = Path(data) / ext["folder"]
        raw = (folder / "manifest.json").read_bytes()
        manifest = json.loads(raw)
        if manifest.get("source") != ext["source"] or int(manifest.get("size", 0)) != int(spec.get("size", 512)):
            raise RuntimeError(f"external arm {ext['source']}: its manifest names {manifest.get('source')} at "
                               f"{manifest.get('size')} pixels, not {ext['source']} at {spec.get('size', 512)}")
        got = [dict(S.load_pair(str(folder / q["npz"])), person=q["person"], part="validation", source=ext["source"])
               for q in manifest["persons"]]
        pairs += got
        record[ext["source"]] = {"persons": len(got), "frames": sum(len(q["frames"]) for q in got),
                                 "held_out": len(manifest.get("held_out", [])), "left_out": len(manifest.get("left_out", {})),
                                 "manifest_sha256": hashlib.sha256(raw).hexdigest()}
        say(f"pairs: {ext['source']}: {len(got)} persons, {record[ext['source']]['frames']} frames, all the gates'; "
            f"{record[ext['source']]['held_out']} held out for its test, {record[ext['source']]['left_out']} left out")
    return pairs, record


def run_pool(fn, jobs, workers, say=None):
    """Each job's answer, in the jobs' order, from a pool of spawned processes. A worker the kernel
    kills, as it does one that runs the memory out, breaks the pool; the jobs not answered yet are
    then run again with half the workers, down to one, in this process, so a round slows rather than
    hangs on a dead worker as a plain Pool would."""
    results = {}
    todo = list(range(len(jobs)))
    n = min(max(int(workers), 1), max(len(jobs), 1))
    while todo:
        if n <= 1 or len(todo) == 1:
            for i in todo:
                results[i] = fn(jobs[i])
            break
        try:
            with ProcessPoolExecutor(n, mp_context=multiprocessing.get_context("spawn")) as pool:
                futures = {pool.submit(fn, jobs[i]): i for i in todo}
                for future in as_completed(futures):
                    results[futures[future]] = future.result()
            todo = []
        except BrokenProcessPool:
            todo = [i for i in todo if i not in results]
            n //= 2
            if say:
                say(f"a worker was killed, the memory likely run out; {len(todo)} jobs again with {max(n, 1)} workers")
    return [results[i] for i in range(len(jobs))]


def presence_by_part(pairs, spec):
    """Every frame's evidence for every landmark, the selection's frames apart from the gate's, and the gate's
    frames again by the source they came from."""
    out = {"training": [], "validation": []}
    by_source = {}
    for pair in pairs:
        rows = S.pair_presence(pair, spec.get("radius", 8), spec.get("sigma", 1.5), spec.get("null_per_body", 200))
        out[pair["part"]] += [r for r in rows]
        if pair["part"] == "validation":
            by_source.setdefault(pair.get("source", "carmlspine"), []).extend(rows)
    result = {k: np.asarray(v).reshape(-1, len(G.LANDMARKS)) for k, v in out.items()}
    result["by_source"] = {k: np.asarray(v).reshape(-1, len(G.LANDMARKS)) for k, v in by_source.items()}
    return result


def frame_means_of(rows, chosen):
    return [float(np.nanmean(r[chosen])) if np.isfinite(r[chosen]).any() else float("nan") for r in rows]


def by_source_part(pairs, presence, sel_packs, chosen, ceiling, bars, spec, say):
    """Each source's own real naming and presence on the gate's frames, and the sacral anchor's presence, recorded
    beside the pooled gates so a source that fails is seen; none of it moves the controller (the external PREREG,
    section 3)."""
    out = {}
    runs_by = {}
    for pair in pairs:
        if pair["part"] == "validation":
            runs_by.setdefault(pair.get("source", "carmlspine"), []).extend(
                S.pair_samples(pair, pair["person"], spec["k_max"], spec["size"]))
    for source, runs in sorted(runs_by.items()):
        entry = {"runs": len(runs)}
        if runs:
            _, table = gate_cells(sel_packs, G.pack(runs), chosen, S.TYPE_LEVELS)
            entry["real_naming"] = G.fingerprint_gate(table, bars["real_naming"], ("none",), "real", ceiling)
        if presence is not None and source in presence["by_source"] and len(presence["by_source"][source]):
            entry["presence"] = G.presence_gate(frame_means_of(presence["by_source"][source], chosen), bars["presence"])
        out[source] = entry
    anchor, anchor_by = [], {}
    for pair in pairs:
        if pair["part"] == "validation":
            means = S.pair_anchor(pair, spec["radius"], spec["sigma"], spec["null_per_body"], spec["size"])
            anchor += means
            anchor_by.setdefault(pair.get("source", "carmlspine"), []).extend(means)
    checks = {"anchor": G.presence_gate(anchor, bars["presence"])}
    for source, means in anchor_by.items():
        out.setdefault(source, {})["anchor"] = G.presence_gate(means, bars["presence"])
    for source, entry in sorted(out.items()):
        words = [f"{k} {'pass' if v.get('pass') else 'fail'}" for k, v in entry.items() if isinstance(v, dict)]
        say(f"by source: {source}: {entry.get('runs', 0)} real gate runs; " + ", ".join(words))
    say(f"anchor: {checks['anchor']['why']}")
    return out, checks


# ---------------------------------------------------------------- the round

def gate_cells(model_packs, gate_packs, chosen, type_levels):
    feats = G.features_of(model_packs, chosen)
    namer = G.Namer(G.NameModel().fit(model_packs, feats), type_levels)
    return namer, G.cells(G.name_rows(namer, gate_packs, G.features_of(gate_packs, chosen)))


def plain(obj):
    """JSON's form of the round's record: numpy's numbers as Python's, a number that is not finite
    as its name in words, so the file is JSON every reader takes."""
    if isinstance(obj, dict):
        return {str(k): plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [plain(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return plain(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        x = float(obj)
        return x if math.isfinite(x) else ("inf" if x > 0 else "-inf" if x < 0 else "nan")
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def run_round(plan, state, out, work, data, asked_workers):
    say = Progress(out).say
    config = dict(plan["start"], **state.get("config", {}))
    round_no = int(state.get("round", 0))
    bars = plan["bars"]
    watch = plan["watch"]
    classes = list(plan["classes"])
    space = Space()
    earlier = state.get("space", {}).get("blocks", {})
    ram = free_memory()
    say(f"round {round_no}: config {json.dumps(config, sort_keys=True)}; free memory {ram / 2**30:.1f} GiB "
        f"({binding_bound()} binds)")
    record = {"round": round_no, "config": config, "plan": plan["plan"], "gates": {}, "seconds": {},
              "memory_bounds": {k: int(v) for k, v in memory_bounds().items()}}

    # the pairs
    t0 = time.time()
    workers = workers_for(earlier.get("pairs", {}).get("rss_bytes", 0), asked_workers, ram)
    with PeakWatch() as peak:
        pairs, pair_record = pairs_for(plan, data, work, workers, say)
    space.measure("pairs", "case", max(len(pairs), 1), folder_bytes(Path(work) / "pairs"), peak.peak)
    record["pairs"] = pair_record
    record["seconds"]["pairs"] = time.time() - t0

    # the network's rows: the selection's, the gate's and the watch's, each from seeds of its own
    t0 = time.time()
    from autoanatomist.model import Config  # noqa: F401  (the JAX side starts here)
    from autoanatomist import train
    words = list(plan["words"]) + [f"w_name={config['w_name']}"]
    source = state.get("session") or ""
    if source and not (Path(source) / "session.json").is_file():
        raise RuntimeError(f"the round before saved no session where the state says ({Path(source).parent.name}/session)")
    session = session_for(source, words, say)
    rp = plan.get("phantom_rows", {})
    spacing, noise = rp.get("spacing", 1.25), rp.get("noise", 20.0)
    sel_rows = class_rows(classes, int(config["phantoms_per_class"]), "selection", spacing, noise)
    gate_rows = class_rows(classes, int(rp.get("gate_per_class", 2)), "gate", spacing, noise)
    watch_rows = class_rows(classes, int(watch["watch_per_class"]), "watch", spacing, noise)
    workers = workers_for(earlier.get("crops", {}).get("rss_bytes", 0), asked_workers, ram)
    cache = str(Path(work) / "crops")
    with PeakWatch() as peak:
        sel_ex = examples(sel_rows, session.cfg, cache, workers, say)
        gate_ex = examples(gate_rows, session.cfg, cache, workers, say)
        watch_ex = examples(watch_rows, session.cfg, cache, workers, say)
    held_rows = len(sel_rows) + len(gate_rows) + len(watch_rows)
    row_bytes = (sel_ex.hu.nbytes + sel_ex.masks.nbytes + sel_ex.targets.nbytes) / max(len(sel_rows), 1)
    space.measure("crops", "row", held_rows, folder_bytes(cache), peak.peak)
    space.blocks["crops"]["memory_bytes"] = int(row_bytes)
    record["seconds"]["crops"] = time.time() - t0

    # the training, watched a check at a time
    t0 = time.time()
    trained, wstate = train_watched(session, sel_ex, watch_ex, len(sel_rows), plan, state, round_no, out, say)
    record["watch"] = wstate
    # The round's own session folder, its steps' rows carried on from the round before's, so a round
    # run again after a cut starts from the same session and writes the same rows.
    saved = Path(out) / "session"
    saved.mkdir(parents=True, exist_ok=True)
    (saved / "record.jsonl").unlink(missing_ok=True)
    if source and (Path(source) / "record.jsonl").is_file():
        shutil.copyfile(Path(source) / "record.jsonl", saved / "record.jsonl")
    session.save(str(saved))
    record["seconds"]["train"] = time.time() - t0

    # the held gates
    t0 = time.time()
    with PeakWatch() as peak:
        held = train.evaluate_masks(session.model, gate_ex)
        dice, named, latent = per_crop(session, gate_ex)
        kinds, levels = row_classes(gate_ex, gate_rows)
        sel_latent = latents_of(session, sel_ex)
        sel_kinds, sel_levels = row_classes(sel_ex, sel_rows)
        gate_view = {"kinds": kinds, "levels": levels, "dice": dice, "right": named == gate_ex.names, "latent": latent}
        sel_view = {"kinds": sel_kinds, "levels": sel_levels, "latent": sel_latent}
        totals = read_totals(saved)
        history = list(state.get("held", [])) + [held["distance_mm"]]
        record["gates"]["convergence"] = G.convergence(totals, history, bars["convergence"])
        record["gates"]["anomaly"] = anomaly_result(classes, gate_view, sel_view, bars["anomaly"])
    record["held"] = {k: held[k] for k in ("dice", "dice_every", "distance_mm", "centroid_mm", "named_right",
                                           "named_within_one", "crops")}
    record["held_history"] = history
    space.measure("evaluate", "round", 1, 0, peak.peak)
    record["seconds"]["evaluate"] = time.time() - t0
    say(f"held: Dice {held['dice']:.3f}, distance {held['distance_mm']:.2f} mm, named right {held['named_right']:.3f}")

    # the fingerprint
    t0 = time.time()
    fp = plan["fingerprint"]
    persons = int(config["fingerprint_persons"])
    gate_persons = int(fp["gate_persons"])
    with PeakWatch() as peak:
        fingerprint_part(plan, config, record, pairs, pair_record, persons, gate_persons, round_no, say)
    # The fingerprint's memory grows with its persons, the selection's and the gate's of every type,
    # so it is measured a person, and the next round's persons a type are as many as the memory holds.
    space.measure("fingerprint", "person", (persons + gate_persons) * len(classes), 0, peak.peak)
    record["seconds"]["fingerprint"] = time.time() - t0

    # the space plan for the next round
    space.measure("round", "round", 1, folder_bytes(out), None)
    disk = shutil.disk_usage(work)
    plan_space = G.space_plan(space.blocks, disk.free, free_memory(), DISK_SHARE, RAM_SHARE)
    # What the memory holds next round: the rows held now and more in half the share of what is still
    # free with them held, the fingerprint's persons a type in the other half, so the controller may
    # grow both in one round and the two together still fit.
    room = free_memory() * RAM_SHARE / 2
    plan_space["rows_fit"] = held_rows + int(room // max(row_bytes, 1))
    per_person = space.blocks["fingerprint"]["rss_bytes"]
    plan_space["persons_fit"] = persons + int(room // (per_person * len(classes))) if per_person > 0 else None
    record["space"] = plan_space
    record["gates"] = {g: record["gates"].get(g) for g in plan.get("gates", G.GATES)}
    record["stand_in"] = bool(pair_record.get("stand_in", False))
    record["environment"] = environment()
    for g, r in record["gates"].items():
        say(f"gate {g}: {'pass' if r and r.get('pass') else 'fail'}"
            + (f" ({r.get('missing') or r.get('why') or '; '.join(r.get('failing', [])[:3])})" if r and not r.get("pass") else ""))
    return record


def train_watched(session, sel_ex, watch_ex, rows, plan, state, round_no, out, say):
    """The round's training, a check at a time (tools/qaloop_gates.py, the training watch): every
    every_epochs the check's loss and the watch rows' held Dice and surface distance written to
    TREND.jsonl, said on PROGRESS.txt and logged to Weights and Biases where it runs; a check whose
    numbers cannot be right raises InsaneAnswer; training stops once the held measures have gained
    nothing for patience_epochs, and rests in later rounds until the rows it trains on grow.
    Returns (steps trained, the watch's state)."""
    from autoanatomist import train
    watch = plan["watch"]
    w = dict(state.get("watch") or {})
    spines = len(sel_ex.spines())
    per_step = int(session.blocks.batch) / max(spines, 1)
    epoch0 = float(w.get("epoch", 0.0))
    w_name = float(session.blocks.w_name)
    # The loss is its terms weighted, so a new name weight moves it however well the network does: its
    # best is counted afresh from the first check under the new weight, or the explode test would read
    # the controller's own change as a network gone wrong.
    reweighted = w.get("w_name") is not None and float(w["w_name"]) != w_name
    if reweighted:
        w.pop("best_loss", None)
    # Training that rests starts again when what it trains on changes: more rows, or a new weight.
    if G.stalled(w, watch) and (rows > int(w.get("rows", 0)) or reweighted):
        what = (f"the rows grew from {w.get('rows')} to {rows}" if rows > int(w.get("rows", 0))
                else f"the name weight went from {w['w_name']} to {w_name}")
        say(f"{what}: training starts again, {watch['patience_epochs']} epochs to gain")
        w.update(best_epoch=epoch0, since_best=0.0)
    steps = int(plan["steps_per_round"])
    if G.stalled(w, watch):
        say(f"training rests: the held measures gained nothing in {w['since_best']:.1f} epochs and neither the "
            f"rows nor the weights have changed")
        steps = 0
    every = max(1, int(round(watch["every_epochs"] / per_step)))
    trend = Path(out) / "TREND.jsonl"
    trend.unlink(missing_ok=True)
    telemetry = round_telemetry(out, plan, state, round_no, {"rows": rows, "spines": spines, "every_steps": every,
                                                              "epochs_per_step": per_step})
    say(f"training up to {steps} steps from step {session.step} (epoch {epoch0:.1f}) on {rows} rows ({len(sel_ex)} crops), "
        f"a check every {every} steps ({every * per_step:.1f} epochs)")
    done, checks = 0, 0
    try:
        while done < steps:
            chunk = session.train(sel_ex, min(every, steps - done))
            done += len(chunk)
            losses = np.asarray([r["total"] for r in chunk], float)
            held = train.evaluate_masks(session.model, watch_ex)
            point = {"round": round_no, "step": int(session.step), "round_steps": done, "epoch": epoch0 + done * per_step,
                     "loss": float(losses.mean()), "loss_last": float(losses[-1]), "held_dice": float(held["dice"]),
                     "held_distance_mm": float(held["distance_mm"]), "held_named_right": float(held["named_right"]),
                     "surface_missing": int(held["surface_missing"]), "crops": int(held["crops"])}
            why = G.insane(point, w.get("best_loss"), watch, float(held["surface_bound_mm"]))
            if why is None:
                w, point["gained"] = G.watch_step(w, point, watch)
                point["since_best"] = w["since_best"]
            checks += 1
            with open(trend, "a") as f:
                f.write(json.dumps(plain(point), sort_keys=True) + "\n")
            telemetry.log({k: v for k, v in point.items() if isinstance(v, (int, float))}, step=point["step"])
            if why is not None:
                say(f"insane at epoch {point['epoch']:.1f}: {why}")
                raise InsaneAnswer(why)
            say(f"epoch {point['epoch']:.1f}, step {point['step']}: loss {point['loss']:.4f}; held Dice "
                f"{point['held_dice']:.3f}, distance {point['held_distance_mm']:.2f} mm; last gain at epoch "
                f"{w['best_epoch']:.1f} ({w['since_best']:.1f} since)")
            if G.stalled(w, watch):
                say(f"training stops: no gain of {watch['min_gain']} in {w['since_best']:.1f} epochs, "
                    f"the watch's patience {watch['patience_epochs']}")
                break
    finally:
        telemetry.summary({"round": round_no, "checks": checks, "trained_steps": done})
        telemetry.finish()
    w.update(rows=rows, epoch=epoch0 + done * per_step, trained_steps=done, checks=checks, w_name=w_name,
             stalled=G.stalled(w, watch), epochs_per_step=per_step, every_steps=every)
    return done, w


def round_telemetry(out, plan, state, round_no, config):
    """The round's Weights and Biases run, one a round grouped by the loop's run, its x axis the
    session's step; a no-op wherever W&B is off, absent or cannot start (tools/wandb_log.py)."""
    tool = load_tool("wandb_log")
    group = "".join(c if c.isalnum() or c in "-_" else "-" for c in str(state.get("wandb_group") or f"qaloop-{plan['plan']}"))[:48]
    record = {"run_id": group, "code_commit": str(state.get("commit") or "unknown"), "catalog_sha256": "none",
              "catalog_version": "none", "clean_tree": True}
    return tool.Telemetry(out, record, f"round{round_no:03d}", dict(config, plan=plan["plan"], round=round_no), resume=True)


def fingerprint_part(plan, config, record, pairs, pair_record, persons, gate_persons, round_no, say):
    """The fingerprint and the gates that read it: the greedy search over the landmarks the presence
    floor keeps, on the selection's phantoms and pairs, judged on the gate's; presence on the gate's
    real frames; real naming on the gate's pairs; latency of the naming path."""
    bars = plan["bars"]
    classes = list(plan["classes"])
    fp = plan["fingerprint"]
    sel_samples = S.phantom_samples(classes, S.seeds_for(classes, persons, "selection"), fp["frames_per_view"],
                                    fp["k_max"], fp["noise_px"], fp.get("pose"), tuple(fp.get("lordosis", (0.3, 1.2))))
    # The gate's phantom persons are drawn anew each round, so a change the controller made from one
    # round's answers is judged on persons it was not chosen on.
    gate_seeds = S.seeds_for(classes, gate_persons, "gate", round_offset=round_no * gate_persons)
    gate_samples = S.phantom_samples(classes, gate_seeds, fp["frames_per_view"], fp["k_max"], fp["noise_px"],
                                     fp.get("pose"), tuple(fp.get("lordosis", (0.3, 1.2))))
    real_sel, real_gate = [], []
    for pair in pairs:
        runs = S.pair_samples(pair, pair["person"], fp["k_max"], int(plan.get("pairs", {}).get("size", 512)))
        (real_gate if pair["part"] == "validation" else real_sel).extend(runs)
    presence = presence_by_part(pairs, plan.get("presence", {})) if pairs else None
    pool = list(range(len(G.LANDMARKS)))
    floor = float(config.get("presence_floor", 0.0))
    by_landmark = {}
    if presence is not None and len(presence["training"]):
        means = S.column_means(presence["training"])
        by_landmark = {G.LANDMARKS[i]: float(means[i]) for i in range(len(G.LANDMARKS))}
        pool = floor_pool(pool, means, floor)
        say(f"presence floor {floor:.2f} keeps {len(pool)} of {len(G.LANDMARKS)} landmarks")
    sel_packs = G.pack(sel_samples + real_sel)
    gate_packs = G.pack(gate_samples + real_gate)
    say(f"fingerprint: {G.count(sel_packs)} selection runs ({len(real_sel)} real), {G.count(gate_packs)} gate runs "
        f"({len(real_gate)} real)")
    chosen, trace = G.greedy_select(sel_packs, pool, S.TYPE_LEVELS, int(config["max_landmarks"]),
                                    float(fp.get("min_gain", 0.005)), int(fp.get("folds", 3)), log=say)
    record["fingerprint"] = {"chosen": [G.LANDMARKS[i] for i in chosen], "trace": trace, "pool": [G.LANDMARKS[i] for i in pool],
                             "presence_by_landmark": by_landmark, "selection_runs": G.count(sel_packs),
                             "gate_runs": G.count(gate_packs), "real_selection_runs": len(real_sel),
                             "real_gate_runs": len(real_gate)}
    if trace:
        record["fingerprint"]["objective"] = trace[-1].get("objective") if isinstance(trace[-1], dict) else None
    if not chosen:
        record["gates"]["fingerprint"] = {"pass": False, "missing": "no landmark pair could be scored"}
        record["gates"]["real_naming"] = {"pass": False, "missing": "no fingerprint was chosen"}
        record["gates"]["presence"] = {"pass": False, "missing": "no fingerprint was chosen"}
        record["gates"]["latency"] = {"pass": False, "missing": "no fingerprint was chosen"}
        return
    namer, table = gate_cells(sel_packs, gate_packs, chosen, S.TYPE_LEVELS)
    _, ceiling = gate_cells(sel_packs, gate_packs, pool, S.TYPE_LEVELS)
    record["cells"] = table
    record["ceiling_cells"] = ceiling
    record["gates"]["fingerprint"] = G.fingerprint_gate(table, bars["fingerprint"], fp.get("anchors", G.ANCHORS),
                                                        "phantom", ceiling)
    if real_gate:
        real = G.fingerprint_gate(table, bars["real_naming"], ("none",), "real", ceiling)
        real["stand_in"] = pair_record.get("stand_in", False)
        record["gates"]["real_naming"] = real
    else:
        record["gates"]["real_naming"] = {"pass": False, "missing": "no gate person's frame shows two agreed levels"}
    if presence is not None and len(presence["validation"]):
        frame_means = [float(np.nanmean(r[chosen])) if np.isfinite(r[chosen]).any() else float("nan")
                       for r in presence["validation"]]
        pres = G.presence_gate(frame_means, bars["presence"])
        pres["stand_in"] = pair_record.get("stand_in", False)
        record["gates"]["presence"] = pres
    else:
        record["gates"]["presence"] = {"pass": False, "missing": "no gate frame to look at"}
    if plan.get("pairs", {}).get("external") or plan.get("anchor"):
        pres = plan.get("presence", {})
        spec = {"k_max": fp["k_max"], "size": int(plan.get("pairs", {}).get("size", 512)), "radius": pres.get("radius", 8),
                "sigma": pres.get("sigma", 1.5), "null_per_body": pres.get("null_per_body", 200)}
        record["by_source"], record["checks"] = by_source_part(pairs, presence, sel_packs, chosen, ceiling, bars, spec, say)
    seconds = G.time_naming(namer, gate_packs, chosen, int(plan.get("latency_runs", 500)))
    lat = G.latency_gate(seconds, bars["latency"])
    lat["what"] = "the 2-D naming path alone (features and every hypothesis), no landmark detector"
    record["gates"]["latency"] = lat


def floor_pool(pool, means, floor):
    """The landmarks the presence floor keeps: those whose mean percentile on the selection's frames
    is a number at or above it; with a floor of 0 every landmark stays, measured or not. Where fewer
    than two would stay, the two best measured stay, since the search starts from a pair."""
    if floor <= 0:
        return list(pool)
    kept = [i for i in pool if math.isfinite(means[i]) and means[i] >= floor]
    if len(kept) >= 2:
        return kept
    measured = sorted((i for i in pool if math.isfinite(means[i])), key=lambda i: -means[i])
    return sorted(measured[:2]) if len(measured) >= 2 else list(pool)


def environment():
    """Where the round ran, for the report: the Python, the packages the round imports, the host's
    processors and JAX's backend and devices, read once JAX is imported."""
    import platform
    from importlib import metadata
    packages = {}
    for name in ("numpy", "scipy", "jax", "jaxlib", "flax", "optax", "nibabel", "pydicom"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    out = {"python": platform.python_version(), "packages": packages, "cpus": cpus()}
    try:
        import jax
        out["backend"] = jax.default_backend()
        out["devices"] = [str(d.device_kind) for d in jax.devices()]
    except Exception as error:  # the record says JAX could not be read; the round itself will fail on it
        out["backend"] = f"unread: {type(error).__name__}"
    return out


def read_totals(folder):
    path = Path(folder) / "record.jsonl"
    return [json.loads(line)["total"] for line in open(path)] if path.is_file() else []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--plan", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--data", default="")
    ap.add_argument("--workers", type=int, default=0)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    plan = json.loads(Path(a.plan).read_text())
    state = json.loads(Path(a.state).read_text())
    problems = G.plan_problems(plan)
    if problems:
        Path(a.out, "why.txt").write_text("\n".join(problems) + "\n")
        print("\n".join(problems), file=sys.stderr)
        return 2
    try:
        record = run_round(plan, state, a.out, a.work, a.data, a.workers)
    except InsaneAnswer as error:
        Path(a.out, "why.txt").write_text(f"insane answer: {error}\n")
        print(f"insane answer: {error}", file=sys.stderr)
        return INSANE_EXIT
    except Exception:
        Path(a.out, "why.txt").write_text(traceback.format_exc())
        traceback.print_exc()
        return 1
    tmp = Path(a.out, "gates.json.tmp")
    tmp.write_text(json.dumps(plain(record), indent=1, sort_keys=True) + "\n")
    os.replace(tmp, Path(a.out, "gates.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
