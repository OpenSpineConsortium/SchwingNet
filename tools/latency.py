"""Export the level stage to ONNX, prove it gives PyTorch's outputs, and time the whole frame path.

Usage (inside the train-cpu or train-gpu environment):
    python tools/latency.py export  --run <run dir>
    python tools/latency.py parity  --run <run dir> --catalog <catalog.sqlite> --runtime torch|onnxruntime
        [--device cpu|cuda] [--threads 8] [--part validation] [--crops 64]
    python tools/latency.py measure --run <run dir> --catalog <catalog.sqlite> --runtime torch|onnxruntime
        [--device cpu|cuda] [--threads 8] [--frames 300] [--warmup 30] [--part test]

docs/research/demo-plan.md, sections 1 and W6, and issue #13. `export` writes onnx/level.onnx
from the run's best.pt with a batch axis that may vary, since a frame holds as many crops as it
has vertebrae. `parity` compares one arm, a runtime on a device, with the reference, PyTorch on
the CPU in float32, on the same crops and writes onnx/parity-<runtime>-<device>.json: every
predicted level equal and every softmax probability within 1e-5 (schwingnet.latency.parity_holds),
on the crops the run was validated on, never test crops. TF32 is off on both runtimes' GPU paths,
so a GPU arm computes in float32 as the reference does; PyTorch on the CPU is the reference and
needs no file.
`measure` times each frame as the demo runs it, one frame at a time, the model resident and
warmed up, the frame already decoded (acquisition and decode are the C-arm's and the file's, not
SchwingNet's): crop and resize every box, the forward pass, the softmax and the causal tracker's
step. It refuses an arm whose parity did not pass for that runtime, that device and, for ONNX
Runtime, that same file, so no latency number exists for outputs that differ. Each arm writes
latency/<arm>.json, and evaluate/latency.json holds the fastest arm whose parity still holds when
the headline is written, under the keys the evaluation page reads.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# As in tools/train.py: this folder leaves the path so tools/profile.py never shadows the
# standard library's profile module, which torch imports.
sys.path[0] = str(ROOT / "src")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import platform  # noqa: E402
import time  # noqa: E402
from collections import OrderedDict  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from schwingnet.latency import BUDGET_MS, PARITY_TOLERANCE, parity_holds, summarise, within_budget  # noqa: E402
from schwingnet.sweep import Tracker, step  # noqa: E402


def load_trainer():
    spec = importlib.util.spec_from_file_location("schwingnet_train", ROOT / "tools" / "train.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


train = load_trainer()
# float32 on the GPU as on the CPU: TF32 would change the outputs past the parity tolerance.
torch.backends.cudnn.allow_tf32 = False
torch.backends.cuda.matmul.allow_tf32 = False
ONNX_NAME = "level.onnx"
REFERENCE = ("torch", "cpu")
OPSET = 17


class LatencyError(Exception):
    """What stops an export, a parity check or a measurement with a reason a person reads."""


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checkpoint_of(run):
    """The run's checkpoint facts (size, levels) and the path of its weights."""
    folder = Path(run) / "train"
    facts_file, weights = folder / "checkpoint.json", folder / "best.pt"
    if not facts_file.is_file() or not weights.is_file():
        raise LatencyError(f"{folder}: no checkpoint.json and best.pt; train the run first")
    return json.loads(facts_file.read_text(encoding="utf-8")), weights


def load_torch_model(run, device):
    """The run's level stage in PyTorch, in eval mode on the device."""
    facts, weights = checkpoint_of(run)
    model = train.model_for(facts, device)
    model.load_state_dict(torch.load(weights, map_location=device, weights_only=True))
    model.eval()
    return model, facts


def export(run):
    """onnx/level.onnx from best.pt, a variable batch axis, checked by onnx's own checker."""
    import onnx

    model, facts = load_torch_model(run, "cpu")
    size = int(facts["size"])
    folder = Path(run) / "onnx"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ONNX_NAME
    dummy = torch.zeros(1, 3, size, size)
    torch.onnx.export(
        model, (dummy,), str(path), input_names=["crops"], output_names=["logits"],
        dynamic_axes={"crops": {0: "boxes"}, "logits": {0: "boxes"}}, opset_version=OPSET, dynamo=False,
    )
    onnx.checker.check_model(onnx.load(str(path)))
    facts_out = {"onnx": str(path), "onnx_sha256": sha256_of(path), "checkpoint_sha256": sha256_of(checkpoint_of(run)[1]), "opset": OPSET, "size": size, "torch": torch.__version__, "onnx_version": onnx.__version__}
    (folder / "export.json").write_text(json.dumps(facts_out, indent=1) + "\n", encoding="utf-8")
    return facts_out


def ort_session(path, device, threads):
    """An ONNX Runtime session on the device, with the thread count fixed for CPU."""
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = ["CPUExecutionProvider"]
    if device == "cuda":
        if "CUDAExecutionProvider" not in ort.get_available_providers():
            raise LatencyError("ONNX Runtime here has no CUDA provider; run in the train-gpu environment on a GPU node")
        providers = [("CUDAExecutionProvider", {"use_tf32": "0"}), "CPUExecutionProvider"]
    return ort.InferenceSession(str(path), sess_options=options, providers=providers)


def softmax(logits):
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


def parity_file(run, runtime, device):
    return Path(run) / "onnx" / f"parity-{runtime}-{device}.json"


def exported_sha256(run):
    """The ONNX file's sha256, refused when it is not the file export.json names."""
    folder = Path(run) / "onnx"
    export_file = folder / "export.json"
    if not export_file.is_file() or not (folder / ONNX_NAME).is_file():
        raise LatencyError(f"{folder}: no export.json and {ONNX_NAME}; run export first")
    actual = sha256_of(folder / ONNX_NAME)
    if actual != json.loads(export_file.read_text(encoding="utf-8"))["onnx_sha256"]:
        raise LatencyError(f"{folder / ONNX_NAME}: not the file export.json names")
    return actual


def witness_frames(run, part):
    """The sha256 of each frame the run's witness list draws in this part, or none without a list.

    The witness list (witness.json, written by tools/flow.py before any step) is the fixed set of
    frames the evaluation page draws at every checkpoint, so parity shown on them is parity on the
    very frames a reader sees; only frames whose role is this part count, never a test frame.
    """
    listing = Path(run) / "witness.json"
    if not listing.is_file():
        return set()
    frames = json.loads(listing.read_text(encoding="utf-8")).get("frames", [])
    return {f["sha256"] for f in frames if f.get("role") == part and f.get("part") == part}


def parity_crops(run, catalog, part, crops_wanted):
    """The crops parity reads, the witness frames' first, and how many of them are witness crops.

    Every crop of a witness frame is kept even past `crops_wanted`, so the witness frames are
    shown whole; the rest of the part fills up to `crops_wanted` in the catalog's own order.
    """
    every = train.read_crops(catalog, (part,))
    if not every:
        raise LatencyError(f"the catalog has no labelled crops in the {part} part")
    witnessed = witness_frames(run, part)
    first = [c for c in every if c["sha256"] in witnessed]
    rest = [c for c in every if c["sha256"] not in witnessed]
    return first + rest[: max(0, crops_wanted - len(first))], len(first)


def parity(run, catalog, part, crops_wanted, runtime, device, threads):
    """One arm against PyTorch on the CPU, on the same crops; its parity file says whether they agree."""
    if (runtime, device) == REFERENCE:
        raise LatencyError("PyTorch on the CPU is the reference; it has no parity of its own to check")
    onnx_sha256 = exported_sha256(run) if runtime == "onnxruntime" else None
    model, facts = load_torch_model(run, "cpu")
    crops, witnessed = parity_crops(run, catalog, part, crops_wanted)
    inputs, _ = train.load_crops(crops, int(facts["size"]), {})
    with torch.no_grad():
        reference = torch.softmax(model(inputs), dim=1).numpy()
    if runtime == "onnxruntime":
        session = ort_session(Path(run) / "onnx" / ONNX_NAME, device, threads)
        candidate = softmax(session.run(["logits"], {"crops": inputs.numpy()})[0])
    else:
        on_device, _ = load_torch_model(run, device)
        with torch.no_grad():
            candidate = torch.softmax(on_device(inputs.to(device)), dim=1).cpu().numpy()
    difference = float(np.abs(reference - candidate).max())
    labels_equal = bool((reference.argmax(axis=1) == candidate.argmax(axis=1)).all())
    verdict = {
        "runtime": runtime,
        "device": device,
        "threads": threads,
        "reference": "torch on the CPU, float32",
        "onnx_sha256": onnx_sha256,
        "checkpoint_sha256": sha256_of(checkpoint_of(run)[1]),
        "part": part,
        "crops": len(crops),
        "persons": len({c["person"] for c in crops}),
        "witness_frames": len({c["sha256"] for c in crops[:witnessed]}),
        "witness_crops": witnessed,
        "max_abs_probability_difference": difference,
        "labels_equal": labels_equal,
        "tolerance": PARITY_TOLERANCE,
        "passed": parity_holds(difference, labels_equal, len(crops)),
    }
    target = parity_file(run, runtime, device)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(verdict, indent=1) + "\n", encoding="utf-8")
    return verdict


def parity_problem(run, runtime, device):
    """Why an arm may not be timed or shown, or None when its parity holds for what is on disk now."""
    if (runtime, device) == REFERENCE:
        return None
    verdict_file = parity_file(run, runtime, device)
    if not verdict_file.is_file():
        return f"{verdict_file.name} is missing: no latency is measured for {runtime} on {device} before parity"
    verdict = json.loads(verdict_file.read_text(encoding="utf-8"))
    if not verdict.get("passed"):
        return f"{verdict_file.name}: parity did not pass for {runtime} on {device}"
    if verdict.get("checkpoint_sha256") != sha256_of(checkpoint_of(run)[1]):
        return f"{verdict_file.name}: parity was shown for another checkpoint"
    if runtime == "onnxruntime":
        try:
            current = exported_sha256(run)
        except LatencyError as error:
            return str(error)
        if verdict.get("onnx_sha256") != current:
            return f"{verdict_file.name}: parity was shown for another ONNX file"
    return None


def require_parity(run, runtime, device):
    """The ONNX file's sha256 (None for PyTorch), once the arm's parity holds."""
    problem = parity_problem(run, runtime, device)
    if problem:
        raise LatencyError(problem)
    return exported_sha256(run) if runtime == "onnxruntime" else None


def crop_from_image(image, box, size):
    """The body's crop from an already decoded frame, by train.crop_pixels' own arithmetic."""
    width, height = image.size
    x0, y0, x1, y1 = box
    pad_x, pad_y = (x1 - x0) * train.PAD, (y1 - y0) * train.PAD
    pixels = (
        max(0, int((x0 - pad_x) * width)),
        max(0, int((y0 - pad_y) * height)),
        min(width, int((x1 + pad_x) * width) + 1),
        min(height, int((y1 + pad_y) * height) + 1),
    )
    crop = image.crop(pixels).resize((size, size), Image.BILINEAR)
    return np.asarray(crop, dtype=np.float32) / 255.0


class FramePath:
    """One frame in, the tracker's view of it out: crop, forward, softmax, track; each part timed.

    The model is loaded once and stays resident; `run` is what a live demo does per frame, so its
    timing is the frame path's and nothing else's. Boxes are unit boxes (0..1 of width and height).
    """

    def __init__(self, run, runtime, device, threads):
        self.runtime, self.device, self.threads = runtime, device, threads
        self.model, facts = load_torch_model(run, device)
        self.size, self.levels = int(facts["size"]), list(facts["levels"])
        self.session = None
        self.onnx_sha256 = require_parity(run, runtime, device)
        if runtime == "onnxruntime":
            self.session = ort_session(Path(run) / "onnx" / ONNX_NAME, device, threads)
        self.reset()

    def reset(self):
        self.tracker = Tracker()

    def _sync(self):
        if self.device == "cuda":
            torch.cuda.synchronize()

    def probabilities(self, crops):
        if self.session is not None:
            return softmax(self.session.run(["logits"], {"crops": crops})[0])
        with torch.no_grad():
            tensor = torch.from_numpy(crops).to(self.device)
            out = torch.softmax(self.model(tensor), dim=1)
            return out.cpu().numpy()

    def run(self, image, boxes):
        """The tracker's view of one decoded frame, and the milliseconds each part took."""
        self._sync()
        start = time.perf_counter()
        crops = np.stack([crop_from_image(image, box, self.size) for box in boxes]) if boxes else np.zeros((0, 1, self.size, self.size), np.float32)
        crops = np.ascontiguousarray(np.repeat(crops[:, None, :, :] if crops.ndim == 3 else crops, 3, axis=1), dtype=np.float32)
        cropped = time.perf_counter()
        probs = self.probabilities(crops) if boxes else np.zeros((0, len(self.levels)), np.float32)
        self._sync()
        modelled = time.perf_counter()
        self.tracker, shown = step(self.tracker, [tuple(map(float, b)) for b in boxes], [list(map(float, p)) for p in probs], self.levels)
        done = time.perf_counter()
        timing = {"preprocess_ms": (cropped - start) * 1e3, "model_ms": (modelled - cropped) * 1e3, "track_ms": (done - modelled) * 1e3, "frame_ms": (done - start) * 1e3}
        return shown, probs, timing


def frames_of(catalog, part):
    """Each frame of a part once, with its unit boxes in a fixed order, from the catalog's labels."""
    frames = OrderedDict()
    for crop in train.read_crops(catalog, (part,)):
        frames.setdefault(crop["frame"], []).append(crop["box"])
    if not frames:
        raise LatencyError(f"the catalog has no labelled frames in the {part} part")
    return list(frames.items())


def device_name(device):
    if device == "cuda":
        return torch.cuda.get_device_name(0)
    return f"{platform.processor() or platform.machine()} ({os.cpu_count()} cores visible)"


def arm_name(runtime, device, threads):
    return f"{runtime}-{device}" + (f"-{threads}t" if device == "cpu" else "")


def measure(run, catalog, runtime, device, threads, frames_wanted, warmup, part):
    """Time the frame path over the part's frames, warm-up first and excluded; write the arm's file."""
    torch.set_num_threads(threads)
    path = FramePath(run, runtime, device, threads)
    frames = frames_of(catalog, part)
    decoded = [(Image.open(f).convert("L"), boxes) for f, boxes in frames]
    for image, _ in decoded:
        image.load()
    for n in range(warmup):
        image, boxes = decoded[n % len(decoded)]
        path.run(image, boxes)
    path.reset()
    samples = []
    for n in range(frames_wanted):
        image, boxes = decoded[n % len(decoded)]
        samples.append(path.run(image, boxes)[2])
    total = summarise([s["frame_ms"] for s in samples])
    per_stage = {k: summarise([s[k] for s in samples]) for k in ("preprocess_ms", "model_ms", "track_ms")}
    record = json.loads((Path(run) / "RUN.json").read_text(encoding="utf-8"))
    arm = {
        "arm": arm_name(runtime, device, threads),
        "run_id": record["run_id"],
        "code_commit": record["code_commit"],
        "runtime": runtime,
        "device_kind": device,
        "device": device_name(device),
        "threads": threads,
        "batch": 1,
        "frames": total["frames"],
        "distinct_frames": len(decoded),
        "boxes_per_frame_mean": sum(len(b) for _, b in decoded) / len(decoded),
        "warmup_frames": warmup,
        "ms_per_frame_median": total["p50"],
        "ms_per_frame_p95": total["p95"],
        "ms_per_frame_p99": total["p99"],
        "frame": total,
        "per_stage": per_stage,
        "budget_ms": BUDGET_MS,
        "within_budget": within_budget(total["p95"]),
        "parity_passed": True,
        "part": part,
        "onnx_sha256": path.onnx_sha256,
        "excludes": "acquisition, file read and decode, display",
        "torch": torch.__version__,
    }
    folder = Path(run) / "latency"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{arm['arm']}.json").write_text(json.dumps(arm, indent=1) + "\n", encoding="utf-8")
    write_headline(run)
    return arm


def write_headline(run):
    """evaluate/latency.json: the fastest arm by p95 whose parity holds, for the evaluation page."""
    arms = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((Path(run) / "latency").glob("*.json"))]
    # parity is read again now, so an arm whose file, checkpoint or verdict changed since it was
    # timed is never the headline
    passing = [a for a in arms if parity_problem(run, a["runtime"], a["device_kind"]) is None]
    if not passing:
        (Path(run) / "evaluate" / "latency.json").unlink(missing_ok=True)
        return None
    best = min(passing, key=lambda a: (a["ms_per_frame_p95"], a["arm"]))
    folder = Path(run) / "evaluate"
    folder.mkdir(parents=True, exist_ok=True)
    headline = dict(best, arms=[a["arm"] for a in arms])
    (folder / "latency.json").write_text(json.dumps(headline, indent=1) + "\n", encoding="utf-8")
    return headline


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    export_p = sub.add_parser("export")
    export_p.add_argument("--run", required=True)
    parity_p = sub.add_parser("parity")
    parity_p.add_argument("--run", required=True)
    parity_p.add_argument("--catalog", required=True)
    parity_p.add_argument("--part", default="validation", choices=["train", "validation"], help="never the test part")
    parity_p.add_argument("--crops", type=int, default=64)
    parity_p.add_argument("--runtime", choices=["torch", "onnxruntime"], required=True)
    parity_p.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parity_p.add_argument("--threads", type=int, default=8)
    measure_p = sub.add_parser("measure")
    measure_p.add_argument("--run", required=True)
    measure_p.add_argument("--catalog", required=True)
    measure_p.add_argument("--runtime", choices=["torch", "onnxruntime"], required=True)
    measure_p.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    measure_p.add_argument("--threads", type=int, default=8)
    measure_p.add_argument("--frames", type=int, default=300)
    measure_p.add_argument("--warmup", type=int, default=30)
    measure_p.add_argument("--part", default="test")
    return parser.parse_args(argv)


def run_command(args):
    if args.command == "export":
        return export(args.run)
    if args.command == "parity":
        verdict = parity(args.run, args.catalog, args.part, args.crops, args.runtime, args.device, args.threads)
        if not verdict["passed"]:
            raise LatencyError(f"parity failed: {json.dumps(verdict)}")
        return verdict
    if args.frames < 1 or args.warmup < 0 or args.threads < 1:
        raise LatencyError("frames and threads are at least 1, warm-up at least 0")
    return measure(args.run, args.catalog, args.runtime, args.device, args.threads, args.frames, args.warmup, args.part)


def main(argv=None):
    try:
        print(json.dumps(run_command(parse(argv)), indent=1))
        return 0
    except (LatencyError, train.TrainError) as error:
        print(f"latency: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
