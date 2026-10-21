"""Export the level stage to ONNX, prove it gives PyTorch's outputs, and time the whole frame path.

Usage (inside the train-cpu or train-gpu environment):
    python tools/latency.py export  --run <run dir>
    python tools/latency.py parity  --run <run dir> --catalog <catalog.sqlite> [--part validation] [--crops 64] [--device cpu]
    python tools/latency.py measure --run <run dir> --catalog <catalog.sqlite> --runtime torch|onnxruntime
        [--device cpu|cuda] [--threads 8] [--frames 300] [--warmup 30] [--part test]

docs/research/demo-plan.md, sections 1 and W6, and issue #13. `export` writes onnx/level.onnx
from the run's best.pt with a batch axis that may vary, since a frame holds as many crops as it
has vertebrae. `parity` runs PyTorch and ONNX Runtime on the same crops and writes
onnx/parity.json: every predicted level equal and every softmax probability within 1e-5
(schwingnet.latency.parity_holds), on the crops the run was validated on, never test crops.
`measure` times each frame as the demo runs it, one frame at a time, the model resident and
warmed up, the frame already decoded (acquisition and decode are the C-arm's and the file's, not
SchwingNet's): crop and resize every box, the forward pass, the softmax and the causal tracker's
step. It refuses ONNX Runtime unless parity passed for the same file, so no latency number exists
for a runtime whose outputs differ. Each arm writes latency/<arm>.json, and evaluate/latency.json
holds the fastest arm whose parity holds, under the keys the evaluation page reads.
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
from schwingnet.sweep import step  # noqa: E402


def load_trainer():
    spec = importlib.util.spec_from_file_location("schwingnet_train", ROOT / "tools" / "train.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


train = load_trainer()
ONNX_NAME = "level.onnx"
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
    model = train.build_model(None, device)
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
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ort.InferenceSession(str(path), sess_options=options, providers=providers)


def softmax(logits):
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


def parity(run, catalog, part, crops_wanted, device):
    """PyTorch against ONNX Runtime on the same crops; onnx/parity.json says whether they agree."""
    folder = Path(run) / "onnx"
    export_file = folder / "export.json"
    if not export_file.is_file():
        raise LatencyError(f"{folder}: no export.json; run export first")
    exported = json.loads(export_file.read_text(encoding="utf-8"))
    if sha256_of(folder / ONNX_NAME) != exported["onnx_sha256"]:
        raise LatencyError(f"{folder / ONNX_NAME}: not the file export.json names")
    model, facts = load_torch_model(run, device)
    crops = [c for c in train.read_crops(catalog, (part,))][:crops_wanted]
    if not crops:
        raise LatencyError(f"the catalog has no labelled crops in the {part} part")
    inputs, _ = train.load_crops(crops, int(facts["size"]), {})
    with torch.no_grad():
        reference = torch.softmax(model(inputs.to(device)), dim=1).cpu().numpy()
    session = ort_session(folder / ONNX_NAME, device, 1)
    candidate = softmax(session.run(["logits"], {"crops": inputs.numpy()})[0])
    difference = float(np.abs(reference - candidate).max())
    labels_equal = bool((reference.argmax(axis=1) == candidate.argmax(axis=1)).all())
    verdict = {
        "onnx_sha256": exported["onnx_sha256"],
        "part": part,
        "crops": len(crops),
        "persons": len({c["person"] for c in crops}),
        "device": device,
        "max_abs_probability_difference": difference,
        "labels_equal": labels_equal,
        "tolerance": PARITY_TOLERANCE,
        "passed": parity_holds(difference, labels_equal, len(crops)),
    }
    (folder / "parity.json").write_text(json.dumps(verdict, indent=1) + "\n", encoding="utf-8")
    return verdict


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
        if runtime == "onnxruntime":
            self.onnx_sha256 = require_parity(run)
            self.session = ort_session(Path(run) / "onnx" / ONNX_NAME, device, threads)
        self.reset()

    def reset(self):
        self.tracks, self.next_ident = [], 1

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
        self.tracks, shown, self.next_ident = step(self.tracks, self.next_ident, [tuple(map(float, b)) for b in boxes], [list(map(float, p)) for p in probs], self.levels)
        done = time.perf_counter()
        timing = {"preprocess_ms": (cropped - start) * 1e3, "model_ms": (modelled - cropped) * 1e3, "track_ms": (done - modelled) * 1e3, "frame_ms": (done - start) * 1e3}
        return shown, probs, timing


def require_parity(run):
    """The ONNX file's sha256, once parity.json says it passed for that same file."""
    folder = Path(run) / "onnx"
    verdict_file = folder / "parity.json"
    if not verdict_file.is_file():
        raise LatencyError(f"{folder}: no parity.json; no latency is measured for ONNX Runtime before parity")
    verdict = json.loads(verdict_file.read_text(encoding="utf-8"))
    actual = sha256_of(folder / ONNX_NAME)
    if not verdict.get("passed") or verdict.get("onnx_sha256") != actual:
        raise LatencyError(f"{verdict_file}: parity did not pass for this file; no latency is measured for it")
    return actual


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
        "onnx_sha256": getattr(path, "onnx_sha256", None),
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
    passing = [a for a in arms if a.get("parity_passed")]
    if not passing:
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
    parity_p.add_argument("--device", default="cpu")
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
        verdict = parity(args.run, args.catalog, args.part, args.crops, args.device)
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
