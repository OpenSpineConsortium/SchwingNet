"""Score public spine and pelvis X-ray models, as published, against the record (issue #287).

Usage (inside grid/bench.sbatch's throwaway environment, which holds the public package):
    python tools/bench_public.py flexray-carmlspine --weights <bundle dir> --bank <bank dir> --out <dir>
    python tools/bench_public.py flexray-deepfluoro --weights <bundle dir> --h5 <file.h5> --out <dir>
    python tools/bench_public.py xvr-summary --csv <registration.csv> --out <dir>

docs/research/public-spine-and-pelvis-models-to-benchmark.md sets out the three jobs; the owner
gave the word and the count on 2026-10-25. Nothing here trains or tunes: each model runs with the
weights its authors published, and every rule below was fixed before any frame was scored.

FleXray on C-ArmLSpine names the level of each truth box. Each vertebra channel, and the
sacrum's, covers some share of the box at probability 0.5 or more; the box takes the channel
that covers most of it, and counts as undetected where that share is under a quarter
(DETECTED_SHARE). Accuracy is read twice, as the record reads the reported stack: over detected
bodies (A2.1) and with the undetected counted wrong (A2.6), each with its Wilson interval, by
view, with the share of wrong names one level off. A truth level with no FleXray channel (L6) is
counted apart. The flagship, each of the five members and the ensemble are scored, so the
members' share of edited renders reads as an ablation at no training cost.

FleXray on DeepFluoro is its own published benchmark (0.916 mean Dice), scored to show that this
install runs the model as its authors did: Dice on the hips, the femurs, the sacrum and the
lumbar spine, the four structures its eval contract maps DeepFluoro's labels to, with the four
views both FleXray and xvr leave out. How DeepFluoro's stored pixels reached FleXray is not
written down, so both readings are scored, as stored and as -log of the stored intensity, and
both are reported.

xvr on DeepFluoro runs xvr's own register and evaluate scripts (grid/bench.sbatch); this tool
only sums its CSV into the median and the submillimetre share of the final mTRE.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# As in tools/train.py: this folder leaves the path so tools/profile.py never shadows the
# standard library's profile module, which torch imports.
sys.path[0] = str(ROOT / "src")

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
import statistics  # noqa: E402

DETECTED_SHARE = 0.25
PROBABILITY = 0.5
Z95 = 1.96
LEVEL_ORDER = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"] + [f"T{n}" for n in range(1, 13)] + \
    ["L1", "L2", "L3", "L4", "L5", "L6", "sacrum"]
VIEW_GROUPS = {"AP": "ap", "LAT": "lateral", "LAT2": "lateral", "OBL": "oblique"}
# DeepFluoro's stored labels (FleXray's configs/datasets/DeepFluoro.yml) to the structures its
# eval contract scores, with the model channels each structure is read from.
DEEPFLUORO_STRUCTURES = {
    "hips": ({1, 2}, ["hips"]),
    "femurs": ({5, 6}, ["femurs"]),
    "sacrum": ({4, 7}, ["sacrum"]),
    "lumbar_spine": ({3}, ["vertebra_l1", "vertebra_l2", "vertebra_l3", "vertebra_l4", "vertebra_l5"]),
}
# The specimens of the IPCAI 2020 file in DeepFluoro's subject order, and the four views with
# questionable poses that FleXray and xvr both skip (DeepFluoroLabeling-IPCAI2020 issue 8).
DEEPFLUORO_SUBJECTS = ["17-1882", "18-1109", "18-0725", "18-2799", "18-2800", "17-1905"]
DEEPFLUORO_SKIP = {("subject01", "003"), ("subject01", "050"), ("subject04", "002"), ("subject04", "004")}


def wilson(correct, total, z=Z95):
    """The Wilson score interval of a proportion, as (low, high); (0, 1) where nothing was counted."""
    if total == 0:
        return (0.0, 1.0)
    p = correct / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    scale = 1 + z * z / total
    return ((centre - spread) / scale, (centre + spread) / scale)


def level_of_channel(name):
    """The level a FleXray channel names (vertebra_l4 is L4, sacrum is sacrum), or None."""
    if name.lower() == "sacrum":
        return "sacrum"
    match = re.fullmatch(r"vertebra_([ctl])(\d{1,2})", name.lower())
    return f"{match.group(1).upper()}{int(match.group(2))}" if match else None


def truth_level(text):
    """A bank box's level in the record's spelling, S1 read as the sacrum; None where it names none."""
    if text is None:
        return None
    text = str(text)
    if text.upper() in ("S1", "SACRUM"):
        return "sacrum"
    return text if text in LEVEL_ORDER else None


def canvas_box(box, height, width, side=256):
    """A pixel box [x0, y0, x1, y1] of a frame as rows and columns of FleXray's square canvas,
    which pads the frame to a centred square and resizes it to side by side; at least one pixel."""
    x0, y0, x1, y1 = (float(v) for v in box)
    square = max(height, width)
    top, left = (square - height) // 2, (square - width) // 2
    scale = side / square

    def clamp(v):
        return min(side, max(0, int(round(v))))

    r0, r1 = clamp((y0 + top) * scale), clamp((y1 + top) * scale)
    c0, c1 = clamp((x0 + left) * scale), clamp((x1 + left) * scale)
    r1, c1 = max(r1, min(side, r0 + 1)), max(c1, min(side, c0 + 1))
    r0, c0 = min(r0, r1 - 1), min(c0, c1 - 1)
    return r0, r1, c0, c1


def name_box(shares):
    """The level a box takes from {level: share of the box covered}, or None where none reaches
    DETECTED_SHARE; ties go to the level earlier in LEVEL_ORDER, so the call never depends on order."""
    if not shares:
        return None
    best = max(shares.values())
    if best < DETECTED_SHARE:
        return None
    return min((level for level, share in shares.items() if share == best), key=LEVEL_ORDER.index)


def one_off(named, truth):
    """Whether a wrong name is the neighbouring level of the truth."""
    if named not in LEVEL_ORDER or truth not in LEVEL_ORDER:
        return False
    return abs(LEVEL_ORDER.index(named) - LEVEL_ORDER.index(truth)) == 1


def tally(rows):
    """Accuracy over detected bodies and over all bodies, with intervals, from per-box rows
    of {"truth", "named"}; rows whose truth has no channel are counted apart."""
    scored = [r for r in rows if r["has_channel"]]
    detected = [r for r in scored if r["named"] is not None]
    right = sum(r["named"] == r["truth"] for r in detected)
    wrong = [r for r in detected if r["named"] != r["truth"]]
    return {
        "bodies": len(scored),
        "detected": len(detected),
        "correct": right,
        "accuracy_detected": right / len(detected) if detected else None,
        "accuracy_detected_ci": wilson(right, len(detected)),
        "accuracy_all": right / len(scored) if scored else None,
        "accuracy_all_ci": wilson(right, len(scored)),
        "wrong_one_off": sum(one_off(r["named"], r["truth"]) for r in wrong),
        "wrong": len(wrong),
        "no_channel": len(rows) - len(scored),
    }


def tally_by_view(rows):
    """tally over every row and over each view group."""
    out = {"all": tally(rows)}
    for group in sorted(set(VIEW_GROUPS.values()) | {"other"}):
        subset = [r for r in rows if r["view"] == group]
        if subset:
            out[group] = tally(subset)
    return out


def dice(predicted, truth):
    """Dice of two boolean arrays; None where both are empty, which no mean takes."""
    both = int((predicted & truth).sum())
    total = int(predicted.sum()) + int(truth.sum())
    return None if total == 0 else 2 * both / total


def frames_of(bank):
    """Every (image, meta) pair of a bank: images/<part>/<stem>.png beside meta/<stem>.json."""
    for image in sorted((bank / "images").rglob("*.png")):
        meta = bank / "meta" / (image.stem + ".json")
        if meta.is_file():
            yield image, json.loads(meta.read_text(encoding="utf-8"))


def view_group(meta):
    view = meta.get("view")
    return VIEW_GROUPS.get(view, "other") if isinstance(view, str) else "other"


def score_frame(probabilities, channels, meta, height, width):
    """Per-box rows of one frame from FleXray's probabilities (channels by height by width of the canvas)."""
    import numpy as np

    rows = []
    for box in meta.get("boxes") or []:
        truth = truth_level(box.get("level"))
        if truth is None or box.get("kept") is False:
            continue
        r0, r1, c0, c1 = canvas_box(box["box"], height, width, probabilities.shape[-1])
        patch = probabilities[:, r0:r1, c0:c1] >= PROBABILITY
        shares = {level: float(np.mean(patch[i])) for level, i in channels.items()}
        rows.append({"truth": truth, "named": name_box(shares), "has_channel": truth in channels,
                     "view": view_group(meta)})
    return rows


def configurations(weights):
    """The FleXray configurations scored: the flagship, each member, then the ensemble."""
    members = sorted(p.name for p in (weights / "members").iterdir() if p.is_dir()) if (weights / "members").is_dir() else []
    return [("flagship", {})] + [(m, {"subfolder": f"members/{m}"}) for m in members] + [("ensemble", {"ensemble": True})]


def flexray_carmlspine(args):
    import numpy as np
    from fxr.inference import FleXraySegmenter
    from PIL import Image

    out = {"bank": str(args.bank), "weights": str(args.weights), "detected_share": DETECTED_SHARE,
           "probability": PROBABILITY, "configurations": {}}
    frames = list(frames_of(args.bank))
    out["frames"] = len(frames)
    for label, options in configurations(args.weights):
        model = FleXraySegmenter.from_pretrained(str(args.weights), **options)
        channels = {level_of_channel(n): i for i, n in enumerate(model.label_names) if level_of_channel(n)}
        rows = []
        for image, meta in frames:
            with Image.open(image) as picture:
                width, height = picture.size
                probabilities = model.predict(picture.convert("L")).probabilities[0].cpu().numpy()
            rows.extend(score_frame(probabilities, channels, meta, height, width))
        out["configurations"][label] = tally_by_view(rows)
        out.setdefault("channels", sorted(channels, key=LEVEL_ORDER.index))
        print(f"{label}: {json.dumps(out['configurations'][label]['all'])}", flush=True)
    write(args.out / "flexray-carmlspine.json", out)


def deepfluoro_views(h5):
    """(subject, view, pixels, labels, rotate) for each projection of the IPCAI 2020 file."""
    import numpy as np

    for number, specimen in enumerate(DEEPFLUORO_SUBJECTS, start=1):
        if specimen not in h5:
            continue
        subject = f"subject{number:02d}"
        projections = h5[specimen]["projections"]
        for view in sorted(projections):
            group = projections[view]
            if (subject, view) in DEEPFLUORO_SKIP or "gt-seg" not in group:
                continue
            rotate = bool(np.asarray(group["rot-180-for-up"])) if "rot-180-for-up" in group else False
            yield subject, view, np.asarray(group["image/pixels"], dtype="float32"), np.asarray(group["gt-seg"]), rotate


def readings(pixels):
    """The two readings of DeepFluoro's stored pixels scored, each scaled to 0..1."""
    import numpy as np

    def unit(a):
        low, high = float(a.min()), float(a.max())
        return (a - low) / (high - low) if high > low else np.zeros_like(a)

    stored = unit(pixels)
    attenuation = unit(-np.log(np.clip(pixels, 1e-6, None) / max(float(pixels.max()), 1e-6)))
    return {"as_stored": stored, "minus_log": attenuation}


def flexray_deepfluoro(args):
    import h5py
    import numpy as np
    from fxr.inference import FleXraySegmenter
    from PIL import Image

    model = FleXraySegmenter.from_pretrained(str(args.weights))
    index = {n: i for i, n in enumerate(model.label_names)}
    scores = {reading: {s: [] for s in DEEPFLUORO_STRUCTURES} for reading in ("as_stored", "minus_log")}
    views = 0
    with h5py.File(args.h5, "r") as h5:
        for _subject, _view, pixels, labels, rotate in deepfluoro_views(h5):
            if rotate:
                pixels, labels = np.rot90(pixels, 2).copy(), np.rot90(labels, 2).copy()
            side = model.preprocessing.image_size[0]
            truth = np.asarray(Image.fromarray(labels.astype("uint8")).resize((side, side), Image.NEAREST))
            views += 1
            for reading, image in readings(pixels).items():
                probabilities = model.predict(image).probabilities[0].cpu().numpy()
                for structure, (stored, channels) in DEEPFLUORO_STRUCTURES.items():
                    predicted = np.zeros(truth.shape, dtype=bool)
                    for channel in channels:
                        predicted |= probabilities[index[channel]] >= PROBABILITY
                    value = dice(predicted, np.isin(truth, list(stored)))
                    if value is not None:
                        scores[reading][structure].append(value)
    out = {"h5": str(args.h5), "views": views, "published_mean_dice": 0.916, "readings": {}}
    for reading, by_structure in scores.items():
        means = {s: statistics.fmean(v) for s, v in by_structure.items() if v}
        out["readings"][reading] = {"per_structure": means, "counts": {s: len(v) for s, v in by_structure.items()},
                                    "mean_dice": statistics.fmean(means.values()) if means else None}
        print(f"{reading}: {json.dumps(out['readings'][reading])}", flush=True)
    write(args.out / "flexray-deepfluoro.json", out)


def xvr_summary(args):
    """The final mTRE of xvr's own evaluation CSV, summed as its paper reports it."""
    with open(args.csv, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r["pose"] == "final"]
    mtre = sorted(float(r["mTRE_cpos"]) for r in rows)
    out = {"csv": str(args.csv), "views": len(mtre), "published_median_mtre_mm": 1.1,
           "median_mtre_mm": statistics.median(mtre) if mtre else None,
           "submillimetre_share": sum(v < 1.0 for v in mtre) / len(mtre) if mtre else None,
           "median_runtime_s": statistics.median(float(r["runtime"]) for r in rows) if rows else None}
    print(json.dumps(out), flush=True)
    write(args.out / "xvr-deepfluoro.json", out)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("flexray-carmlspine")
    one.add_argument("--weights", type=Path, required=True)
    one.add_argument("--bank", type=Path, required=True)
    two = sub.add_parser("flexray-deepfluoro")
    two.add_argument("--weights", type=Path, required=True)
    two.add_argument("--h5", type=Path, required=True)
    three = sub.add_parser("xvr-summary")
    three.add_argument("--csv", type=Path, required=True)
    for each in (one, two, three):
        each.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    {"flexray-carmlspine": flexray_carmlspine, "flexray-deepfluoro": flexray_deepfluoro,
     "xvr-summary": xvr_summary}[args.command](args)


if __name__ == "__main__":
    main()
