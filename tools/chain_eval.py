"""Score the counting prior against the crop classifier, choosing its settings on validation only.

Usage (inside the train-cpu or train-gpu environment, after tools/evaluate.py):
    python tools/chain_eval.py --catalog <catalog.sqlite> --run <run dir> --prior <prior.json>
        [--device cpu] [--batch 64]

docs/research/ct-priors-for-2d-detection.md, item 1. The run's best checkpoint gives every crop a
posterior over the 27 levels. Crops of one frame, ordered along the column by their centres
(src/schwingnet/chain.py axis_positions), are decoded twice: each crop alone, the classifier's
answer, and as one column under the prior from tools/chain_stats.py. Three settings are chosen on
the validation part and nowhere else: the scale between the CTs' ratios and the boxes' (the
median log gap-to-height of validation frames' true neighbours, less the prior's), the spacing
weight and the abstain margin, the pair with the best validation accuracy among labelled bodies,
an abstained body counted wrong, so abstaining never buys accuracy. Then the test part is read
once with those settings. Each number is a result row with its Wilson interval and the run's
stamp, written to evaluate/chain.json and evaluate/chain.md beside the evaluator's, with the
abstain rate and the transitional stratum apart, never pooled.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[0] = str(ROOT / "src")

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import statistics  # noqa: E402
from collections import defaultdict  # noqa: E402

import torch  # noqa: E402
from schwingnet.catalog import LEVELS, TRANSITIONAL  # noqa: E402
from schwingnet.chain import (  # noqa: E402
    Body,
    ChainPrior,
    Spacing,
    axis_positions,
    decode,
    independent,
    shifted,
)
from schwingnet.flow import ResultRow, result_line  # noqa: E402

WEIGHTS = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
MARGINS = (0.0, math.log(2.0), math.log(4.0), math.log(10.0))


def load_trainer():
    spec = importlib.util.spec_from_file_location("schwingnet_train", ROOT / "tools" / "train.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_prior(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    spacing = {k: Spacing(v["mu"], v["sigma"]) for k, v in raw["spacing"].items()}
    fallback = Spacing(raw["fallback"]["mu"], raw["fallback"]["sigma"])
    return ChainPrior(spacing, fallback, dict(raw["columns"]))


def posteriors(train, model, crops, size, device, batch):
    """Each crop's softmax over LEVELS, as a dict, from the run's best weights."""
    inputs, _ = train.load_crops(crops, size, {})
    model.eval()
    out = []
    with torch.no_grad():
        for start in range(0, len(inputs), batch):
            probs = torch.softmax(model(inputs[start : start + batch].to(device)), dim=1).cpu()
            out.extend({LEVELS[i]: float(p) for i, p in enumerate(row) if p > 1e-6} for row in probs)
    return out


def frames_of(crops, posts):
    """Crops grouped by frame, each frame's bodies sorted along its column with their truth."""
    grouped = defaultdict(list)
    for crop, post in zip(crops, posts, strict=True):
        grouped[crop["sha256"]].append((crop, post))
    frames = []
    for items in grouped.values():
        centres = [(0.5 * (c["box"][0] + c["box"][2]), 0.5 * (c["box"][1] + c["box"][3])) for c, _ in items]
        places = axis_positions(centres)
        order = sorted(range(len(items)), key=lambda k: places[k])
        bodies, truth, persons = [], [], []
        last = None
        for k in order:
            crop, post = items[k]
            if last is not None and places[k] <= last:
                continue
            last = places[k]
            bodies.append(Body(places[k], crop["box"][3] - crop["box"][1], post))
            truth.append(crop["level"])
            persons.append(crop["person"])
        frames.append((bodies, truth, persons))
    return frames


def scale_offset(frames, prior):
    """The validation frames' median log gap-to-height of true neighbours, less the prior's."""
    observed = []
    for bodies, truth, _ in frames:
        for a, b, la, lb in zip(bodies, bodies[1:], truth, truth[1:], strict=False):
            if LEVELS.index(lb) - LEVELS.index(la) == 1 and a.height + b.height > 0:
                observed.append(math.log((b.position - a.position) / (0.5 * (a.height + b.height))))
    return statistics.median(observed) - prior.fallback.mu if observed else 0.0


def labels_for(bodies, prior, weight, margin, chain):
    if not chain:
        return list(independent(bodies)), False
    decoded = decode(bodies, prior, weight, margin)
    if not decoded.labels:
        return ["?"] * len(bodies), True
    return (["?"] * len(bodies) if decoded.abstain else list(decoded.labels)), decoded.abstain


def score(frames, prior, weight, margin, chain):
    """Correct and total per stratum with persons, and how many bodies abstained."""
    strata = defaultdict(lambda: {"correct": 0, "total": 0, "persons": set()})
    abstained = 0
    for bodies, truth, persons in frames:
        labels, abstain = labels_for(bodies, prior, weight, margin, chain)
        abstained += len(bodies) if abstain else 0
        for guess, level, person in zip(labels, truth, persons, strict=True):
            keys = ["all levels"] + (["transitional (T13, L6)"] if level in TRANSITIONAL else [])
            for key in keys:
                strata[key]["correct"] += int(guess == level)
                strata[key]["total"] += 1
                strata[key]["persons"].add(person)
    return strata, abstained


def choose(frames, prior):
    """The weight and margin with the best validation accuracy, abstentions counted wrong."""
    best = None
    for weight in WEIGHTS:
        for margin in MARGINS:
            strata, _ = score(frames, prior, weight, margin, chain=True)
            right = strata["all levels"]["correct"]
            if best is None or right > best[0]:
                best = (right, weight, margin)
    return best[1], best[2]


def rows(strata, record, measure):
    found = []
    for stratum, t in sorted(strata.items()):
        found.append(ResultRow(measure=measure, stratum=stratum, correct=t["correct"], total=t["total"],
                               persons=len(t["persons"]), run_id=record["run_id"],
                               code_commit=record["code_commit"], clean_tree=record["clean_tree"],
                               catalog_sha256=record["catalog_sha256"]))
    return found


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--prior", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch", type=int, default=64)
    return parser.parse_args(argv)


def run(args):
    train = load_trainer()
    out = Path(args.run)
    record = json.loads((out / "RUN.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((out / "train" / "checkpoint.json").read_text(encoding="utf-8"))
    model = train.build_model(None, args.device)
    model.load_state_dict(torch.load(out / "train" / "best.pt", map_location=args.device, weights_only=True))
    size = int(checkpoint["size"])
    prior = load_prior(args.prior)
    parts = {}
    for part in ("validation", "test"):
        crops = train.read_crops(args.catalog, (part,))
        if not crops:
            raise train.TrainError(f"the catalog has no labelled crops in the {part} part")
        parts[part] = frames_of(crops, posteriors(train, model, crops, size, args.device, args.batch))
    offset = scale_offset(parts["validation"], prior)
    prior = shifted(prior, offset)
    weight, margin = choose(parts["validation"], prior)
    found, summary = [], {"offset": offset, "weight": weight, "margin": margin}
    for chain, measure in ((False, "accuracy, each crop alone"), (True, "accuracy, one column")):
        strata, abstained = score(parts["test"], prior, weight, margin, chain)
        found += rows(strata, record, measure)
        summary[f"abstained ({measure})"] = abstained
    folder = out / "evaluate"
    folder.mkdir(parents=True, exist_ok=True)
    summary["rows"] = [r.model_dump() for r in found]
    (folder / "chain.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="ascii")
    lines = [result_line(r) for r in found]
    note = f"Settings from validation only: offset {offset:.3f}, weight {weight}, margin {margin:.3f}."
    (folder / "chain.md").write_text("\n".join([note, "", *lines]) + "\n", encoding="ascii")
    print(note)
    for line in lines:
        print(line)
    return 0


def main(argv=None):
    return run(parse(argv))


if __name__ == "__main__":
    sys.exit(main())
