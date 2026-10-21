"""Run the level stage causally over a recorded C-arm sweep and record the overlay the talk shows.

Usage (inside the train-cpu or train-gpu environment):
    python tools/sweep.py run --run <run dir> --frames <folder of frames, or a .npy stack> --boxes <boxes.jsonl>
        --name case134 [--runtime onnxruntime|torch] [--device cpu|cuda] [--threads 8] [--fps 10.3]
        [--box-source truth|detector] [--out <folder>]
    python tools/sweep.py synthetic --catalog <catalog.sqlite> --person <person key> --out <folder> [--part test]

docs/research/demo-plan.md, section 1, and issue #13. `run` reads the frames in order, one at a
time, as the C-arm would give them, and for each runs the frame path of tools/latency.py (crop,
forward, softmax, the causal tracker's step), timed as tools/latency.py times it; then draws the
overlay: each box coloured by its track, its level and probability or "?" where the tracker
abstains, and in the corner the frame counter, the gantry angle where the boxes file gives it, this
frame's compute time, the p95 so far against the 97 ms budget, and where the boxes came from.
Nothing in the overlay reads a later frame, so the recording is what a live run would have shown.
It writes overlay/<frame>.png, sweep.jsonl (one line per frame: the boxes, the tracks, the levels,
the probabilities, the timings), summary.json (the latency summary and, where the boxes file gives
truth levels, the accuracy with its Wilson interval overall and per 15 degrees of gantry angle),
a contact sheet, and sweep.mp4 where ffmpeg is on the path, else sweep.gif.

The boxes file is JSON lines, one per frame in the frames' order: {"frame": <file name or index>,
"boxes": [[x0, y0, x1, y1], ...] in units of the frame's width and height, or "boxes_px" in pixels,
"levels": [truth level per box, optional], "gantry_deg": <optional>}. Version 1 has no detector
stage, so its boxes are truth boxes, and the overlay says so in every frame.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# As in tools/train.py: tools/profile.py must never shadow the standard library's profile module.
sys.path[0] = str(ROOT / "src")

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from collections import defaultdict  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from schwingnet.flow import wilson  # noqa: E402
from schwingnet.latency import BUDGET_MS, frame_interval_ms, nearest_rank, summarise, within_budget  # noqa: E402


def load_latency():
    spec = importlib.util.spec_from_file_location("schwingnet_latency", ROOT / "tools" / "latency.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


latency = load_latency()
IMAGE_SUFFIXES = {".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp"}
PALETTE = [(230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200), (245, 130, 48), (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60), (250, 190, 212)]
ANGLE_BIN = 15.0


class SweepError(Exception):
    """What stops a sweep with a reason a person reads."""


def frame_sources(frames):
    """The frames in order: a folder's images sorted by name, or the slices of a .npy stack."""
    path = Path(frames)
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
        if not files:
            raise SweepError(f"{path}: no image files ({', '.join(sorted(IMAGE_SUFFIXES))})")
        return [(p.name, p) for p in files]
    if path.suffix == ".npy":
        stack = np.load(path, mmap_mode="r")
        if stack.ndim != 3:
            raise SweepError(f"{path}: a stack is frames x height x width, not {stack.shape}")
        return [(str(n), (stack, n)) for n in range(stack.shape[0])]
    raise SweepError(f"{path}: neither a folder of images nor a .npy stack")


def read_raw(source):
    """The frame's pixels as stored, before windowing: what the file gives, untimed."""
    if isinstance(source, tuple):
        stack, n = source
        return np.asarray(stack[n])
    with Image.open(source) as image:
        return np.asarray(image)


def window(pixels):
    """8-bit greyscale for the stage: 8-bit frames as they are, deeper ones from the 1st to the 99th percentile."""
    if pixels.ndim == 3:
        pixels = pixels[..., :3].mean(axis=2)
    if pixels.dtype == np.uint8:
        return Image.fromarray(pixels, mode="L")
    low, high = np.percentile(pixels, (1, 99))
    scaled = np.clip((pixels.astype(np.float32) - low) / max(1e-6, float(high - low)), 0.0, 1.0)
    return Image.fromarray((scaled * 255.0).astype(np.uint8), mode="L")


def read_boxes(path, count):
    """One line per frame, in order; boxes kept as given until the frame's size is known."""
    lines = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != count:
        raise SweepError(f"{path}: {len(lines)} lines for {count} frames; one line per frame, in order")
    return lines


def unit_boxes(line, width, height):
    """The line's boxes as fractions of the frame, whichever way the file wrote them."""
    if "boxes" in line:
        boxes = [tuple(map(float, b)) for b in line["boxes"]]
    else:
        boxes = [(b[0] / width, b[1] / height, b[2] / width, b[3] / height) for b in line.get("boxes_px", [])]
    for box in boxes:
        if not (0.0 <= box[0] <= box[2] <= 1.0 and 0.0 <= box[1] <= box[3] <= 1.0):
            raise SweepError(f"frame {line.get('frame')}: box {box} is not inside the frame")
    return boxes


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def draw_overlay(image, shown, caption_lines, scale):
    """The frame in colour with each track's box, level and probability, and the caption in the corner."""
    canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    width, height = canvas.size
    label_font, caption_font = font(max(12, int(18 * scale))), font(max(11, int(16 * scale)))
    for item in shown:
        colour = PALETTE[item.ident % len(PALETTE)]
        x0, y0, x1, y1 = item.box[0] * width, item.box[1] * height, item.box[2] * width, item.box[3] * height
        draw.rectangle((x0, y0, x1, y1), outline=colour, width=max(2, int(3 * scale)))
        draw.text((x1 + 4, y0), f"{item.level} {item.probability:.2f}", fill=colour, font=label_font, stroke_width=2, stroke_fill=(0, 0, 0))
    y = 6
    for line in caption_lines:
        draw.text((8, y), line, fill=(255, 255, 255), font=caption_font, stroke_width=2, stroke_fill=(0, 0, 0))
        y += int(20 * scale) + 2
    return canvas


def angle_bin(angle):
    low = math.floor(angle / ANGLE_BIN) * ANGLE_BIN
    return f"{low:+.0f} to {low + ANGLE_BIN:+.0f} deg"


def scored(tally):
    """correct/n with its Wilson interval, for summary.json."""
    low, high = wilson(tally["correct"], tally["total"])
    return {"correct": tally["correct"], "total": tally["total"], "fraction": tally["correct"] / tally["total"], "ci95": [low, high], "abstained": tally["abstained"]}


def score_frame(tallies, shown, single, truth, angle):
    """Each box's shown level against its truth, overall and in the angle's bin; an abstention counts as wrong.

    The frame-alone guess (the stage's best level on this frame, no tracker) is tallied beside it,
    so the summary says what the tracker added or cost.
    """
    for item, alone, level in zip(shown, single, truth, strict=True):
        if level is None:
            continue
        keys = ["all frames", "all frames, frame alone (no tracker)"]
        if angle is not None:
            keys.append(angle_bin(angle))
        for key in keys:
            guess = alone if "frame alone" in key else item.level
            tallies[key]["total"] += 1
            tallies[key]["correct"] += int(guess == level)
            tallies[key]["abstained"] += int(guess == "?")


def contact_sheet(paths, out, columns=6, width=320):
    """Every k-th overlay frame on one sheet, so a reader sees the whole sweep at a glance."""
    if not paths:
        return
    step_ = max(1, len(paths) // (columns * 4))
    chosen = paths[::step_][: columns * 4]
    tiles = [Image.open(p).convert("RGB") for p in chosen]
    height = int(width * tiles[0].size[1] / tiles[0].size[0])
    rows = math.ceil(len(tiles) / columns)
    sheet = Image.new("RGB", (columns * width, rows * height), (0, 0, 0))
    for n, tile in enumerate(tiles):
        sheet.paste(tile.resize((width, height)), ((n % columns) * width, (n // columns) * height))
    sheet.save(out)


def encode_video(folder, fps, out):
    """sweep.mp4 through ffmpeg where it is on the path; else sweep.gif through Pillow."""
    frames = sorted((folder / "overlay").glob("*.png"))
    if shutil.which("ffmpeg"):
        target = out / "sweep.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{fps}", "-pattern_type", "glob", "-i", str(folder / "overlay" / "*.png"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", str(target)],
            check=True,
        )
        return target
    target = out / "sweep.gif"
    images = [Image.open(p).convert("P", palette=Image.ADAPTIVE) for p in frames]
    images[0].save(target, save_all=True, append_images=images[1:], duration=int(frame_interval_ms(fps)), loop=0)
    return target


def run_sweep(args):
    sources = frame_sources(args.frames)
    lines = read_boxes(args.boxes, len(sources))
    path = latency.FramePath(args.run, args.runtime, args.device, args.threads)
    record = json.loads((Path(args.run) / "RUN.json").read_text(encoding="utf-8"))
    out = Path(args.out or Path(args.run) / "sweep" / args.name)
    (out / "overlay").mkdir(parents=True, exist_ok=True)
    warm_image = window(read_raw(sources[0][1]))
    for _ in range(args.warmup):
        path.run(warm_image, unit_boxes(lines[0], *warm_image.size))
    path.reset()
    tallies = defaultdict(lambda: {"correct": 0, "total": 0, "abstained": 0})
    times, written = [], []
    with (out / "sweep.jsonl").open("w", encoding="utf-8") as log:
        for n, ((name, source), line) in enumerate(zip(sources, lines, strict=True)):
            raw = read_raw(source)
            started = time.perf_counter()
            image = window(raw)
            window_ms = (time.perf_counter() - started) * 1e3
            boxes = unit_boxes(line, *image.size)
            shown, probs, timing = path.run(image, boxes)
            timing["window_ms"] = window_ms
            timing["frame_ms"] += window_ms
            times.append(timing["frame_ms"])
            angle = line.get("gantry_deg")
            if line.get("levels"):
                single = [path.levels[int(np.argmax(p))] for p in probs]
                score_frame(tallies, shown, single, line["levels"], angle)
            caption = [
                f"{args.name}  frame {n + 1}/{len(sources)}" + (f"  gantry {angle:+.1f} deg" if angle is not None else ""),
                f"compute {timing['frame_ms']:.1f} ms  p95 so far {nearest_rank(times, 0.95):.1f} ms  budget {BUDGET_MS:.0f} ms",
                f"SchwingNet v1 {record['run_id']}  {args.runtime} on {latency.device_name(args.device)}  boxes: {args.box_source}",
            ]
            overlay = draw_overlay(image, shown, caption, image.size[0] / 1024)
            target = out / "overlay" / f"{n:05d}.png"
            overlay.save(target)
            written.append(target)
            log.write(json.dumps({"n": n, "frame": name, "boxes": boxes, "tracks": [s.ident for s in shown], "levels": [s.level for s in shown], "probabilities": [round(s.probability, 6) for s in shown], "truth": line.get("levels"), "gantry_deg": angle, "timing_ms": timing}) + "\n")
    total = summarise(times)
    summary = {
        "name": args.name,
        "run_id": record["run_id"],
        "code_commit": record["code_commit"],
        "runtime": args.runtime,
        "device": latency.device_name(args.device),
        "threads": args.threads,
        "box_source": args.box_source,
        "fps": args.fps,
        "frames": len(sources),
        "latency_ms": total,
        "budget_ms": BUDGET_MS,
        "within_budget": within_budget(total["p95"]),
        "accuracy": {key: scored(t) for key, t in sorted(tallies.items()) if t["total"]},
        "onnx_sha256": getattr(path, "onnx_sha256", None),
        "excludes": "acquisition, file read and decode, drawing and encoding the overlay",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    contact_sheet(written, out / "contact.png")
    summary["video"] = str(encode_video(out, args.fps, out))
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return summary


def synthetic(args):
    """A sweep in the run's input format from one person's frames of a catalog: for tests and the dry run."""
    frames = [(f, b) for f, b in latency.frames_of(args.catalog, args.part)]
    crops = latency.train.read_crops(args.catalog, (args.part,))
    mine = {c["frame"] for c in crops if c["person"] == args.person}
    if not mine:
        raise SweepError(f"no frame of {args.person} in the {args.part} part")
    levels_of = defaultdict(list)
    for crop in crops:
        levels_of[crop["frame"]].append(crop["level"])
    out = Path(args.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    chosen = [(f, b) for f, b in frames if f in mine]
    with (out / "boxes.jsonl").open("w", encoding="utf-8") as boxes_file:
        for n, (frame, boxes) in enumerate(chosen):
            name = f"{n:05d}.png"
            shutil.copyfile(frame, out / "frames" / name)
            angle = -90.0 + 180.0 * n / max(1, len(chosen) - 1)
            boxes_file.write(json.dumps({"frame": name, "boxes": [list(b) for b in boxes], "levels": levels_of[frame], "gantry_deg": angle}) + "\n")
    return {"frames": len(chosen), "out": str(out)}


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--run", required=True)
    run_p.add_argument("--frames", required=True)
    run_p.add_argument("--boxes", required=True)
    run_p.add_argument("--name", required=True)
    run_p.add_argument("--runtime", default="onnxruntime", choices=["torch", "onnxruntime"])
    run_p.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    run_p.add_argument("--threads", type=int, default=8)
    run_p.add_argument("--fps", type=float, default=10.3)
    run_p.add_argument("--warmup", type=int, default=30)
    run_p.add_argument("--box-source", default="truth", choices=["truth", "detector"])
    run_p.add_argument("--out", default=None)
    syn_p = sub.add_parser("synthetic")
    syn_p.add_argument("--catalog", required=True)
    syn_p.add_argument("--person", required=True)
    syn_p.add_argument("--out", required=True)
    syn_p.add_argument("--part", default="test")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    try:
        result = run_sweep(args) if args.command == "run" else synthetic(args)
    except (SweepError, latency.LatencyError) as error:
        print(f"sweep: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
