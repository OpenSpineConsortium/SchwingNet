#!/usr/bin/env python3
"""The QA loop's fingerprint samples: runs of bodies with their eighteen landmarks projected into a
C-arm's frame, from three sources (docs/research/qa-loop/PREREG.md).

- Phantoms: each anomaly class's columns drawn by the vendored phantom's draw_levels (schwingcheck's
  correlated draw), each level's landmarks placed exactly from its drawn shape (where the oracle's
  chords end on a perfect mask of that shape), the column bent into a lordosis and tilted, and
  projected through C-arm poses drawn about the anteroposterior and lateral views.
- Pairs: C-ArmLSpine's cases, each CBCT's SPINEPS masks read by the oracle on the levels its two
  labellers agree on, the landmarks projected through the poses registered to the same person's
  spot frames, and the frames themselves, for the presence gate.
- Stand-ins: for a machine with no C-ArmLSpine (the smoke run), typical phantoms rendered and read
  by the oracle, a frame splatted from their bone through a pose, and the pose perturbed by up to a
  degree and three millimetres as a registration's error. Every sample and frame of a stand-in says
  so, and the gates' results carry it.

What leaves this module is arrays in memory and, for the pairs and the stand-ins, one cache file a
case under the folder the caller names, on the grid; no frame's file name, no header value and no
path of a case is written or printed. The C-ArmLSpine persons on data/splits/test-persons.json are
never read, and the others are dealt by data/splits/rule.json's hash: validation persons are the
gates', training persons the selection's.
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

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402

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


G = load_tool("qaloop_gates")

# The columns the fingerprint names runs in, from T12 down, as schwingcheck.columns lays each type out.
TYPE_LEVELS = {"typical": ["T12", "L1", "L2", "L3", "L4", "L5"],
               "six_lumbar": ["T12", "L1", "L2", "L3", "L4", "L5", "L6"],
               "four_lumbar": ["T12", "L1", "L2", "L3", "L4"],
               "t13": ["T12", "T13", "L1", "L2", "L3", "L4", "L5"]}
CLASSES = G.CLASSES
# The sagittal angle of each level about its left-right axis, in degrees, counted from the column's
# last level up: a lordosis whose segments open 13, 10, 7 and 5 degrees from the bottom, near the
# published segmental lordosis of a standing adult's lumbar spine; a person's scale shrinks it, as
# lying prone on the table does.
LORDOSIS_FROM_BOTTOM = (-15.0, -2.0, 8.0, 15.0, 20.0, 22.0, 24.0, 25.0)
BODY_POINTS = 10                     # the first ten landmarks lie on the body; a body is in view when all ten are
SACRUM_BELOW_MM = 15.0               # how far below the last disc the sacrum's top sits, for a phantom's anchor
DEFAULT_POSE = {"yaw": 10.0, "tilt": 10.0, "roll": 10.0, "centre_mm": 20.0, "sod": (600.0, 700.0),
                "sdd": (1100.0, 1200.0), "pixel_mm": 0.6, "size": 512}
VERSE_ID = {"T11": 18, "T12": 19, "L1": 20, "L2": 21, "L3": 22, "L4": 23, "L5": 24, "L6": 25, "sacrum": 26, "T13": 28}


# ---------------------------------------------------------------- phantoms

def level_landmarks(lv):
    """A level's eighteen landmarks in its own frame (x right, y anterior with the body's posterior
    wall at y = 0, z up), where the oracle's chords end on a perfect mask of its drawn shape: the
    end-plates' widths and depths at their planes, the posterior wall's height in the body's
    posterior tenth, the canal's width and depth at mid-height, the transverse span at the processes'
    tips and the spinous process from the canal's posterior wall to its farthest point."""
    h = lv.H / 2.0
    wall = 0.05 * (lv.D_top + lv.D_bot)
    yc = -lv.CD / 2.0
    tip = -lv.CD - lv.T - lv.LS
    return np.array([
        [lv.W_top / 2, lv.D_top / 2, h], [-lv.W_top / 2, lv.D_top / 2, h],
        [0.0, 0.0, h], [0.0, lv.D_top, h],
        [lv.W_bot / 2, lv.D_bot / 2, -h], [-lv.W_bot / 2, lv.D_bot / 2, -h],
        [0.0, 0.0, -h], [0.0, lv.D_bot, -h],
        [0.0, wall, h], [0.0, wall, -h],
        [lv.CW / 2, yc, 0.0], [-lv.CW / 2, yc, 0.0],
        [0.0, -lv.CD, 0.0], [0.0, 0.0, 0.0],
        [lv.TP / 2, yc, 0.0], [-lv.TP / 2, yc, 0.0],
        [0.0, -lv.CD, 0.0], [0.0, tip, -6.0],
    ])


def column_of(kind, seed):
    """One phantom person's levels from T12 to the column's end: the class's column drawn by the
    vendored phantom, whose generator draws every level of one person together."""
    from autoanatomist import phantom
    from schwingcheck import columns as C
    names = C.phenotype_levels(kind)[0]
    start = names.index("T12")
    return phantom.draw_levels(kind, seed=seed, start="T12", count=len(names) - start)


def bent_column(levels, rng, lordosis=(0.3, 1.2), spread_deg=2.0):
    """The column laid out as a curve: each level turned about its left-right axis by the lordosis
    (scaled by a factor drawn from the given range, plus a spread), with a small coronal and axial
    turn, and its posterior wall's middle a disc below the one above along the two levels' axes;
    the whole column tilted by a random turn. Returns each level's origin and rotation (its local
    axes as columns) and the column's own axes, right, anterior and up."""
    from autoanatomist import phantom
    scale = rng.uniform(*lordosis)
    n = len(levels)
    sag = [scale * LORDOSIS_FROM_BOTTOM[min(n - 1 - i, len(LORDOSIS_FROM_BOTTOM) - 1)] + rng.normal(0, spread_deg)
           for i in range(n)]
    R0 = G.rotation(rng.normal(size=3), rng.uniform(0.0, 12.0))
    rots = np.array([R0 @ G.rotation((1, 0, 0), a) @ G.rotation((0, 1, 0), rng.normal(0, spread_deg))
                     @ G.rotation((0, 0, 1), rng.normal(0, spread_deg)) for a in sag])
    origins = np.zeros((n, 3))
    for i in range(1, n):
        a, b = levels[i - 1], levels[i]
        up_a, up_b = rots[i - 1][:, 2], rots[i][:, 2]
        mid = (up_a + up_b) / np.linalg.norm(up_a + up_b)
        disc = phantom.DISC_SHARE * 0.5 * (a.H + b.H)
        origins[i] = origins[i - 1] - up_a * a.H / 2 - mid * disc - up_b * b.H / 2
    return origins, rots, R0[:, 0], R0[:, 1], R0[:, 2]


def world_landmarks(levels, origins, rots):
    """Every level's landmarks in the world, (levels, 18, 3)."""
    return np.array([o + level_landmarks(lv) @ R.T for lv, o, R in zip(levels, origins, rots)])


def sacrum_point(levels, origins, rots):
    """Where the sacrum's top would sit below the column's last level, for a phantom has none."""
    from autoanatomist import phantom
    lv, o, R = levels[-1], origins[-1], rots[-1]
    below = phantom.DISC_SHARE * lv.H + SACRUM_BELOW_MM
    return o + R @ np.array([0.0, 0.5 * lv.D_bot, -lv.H / 2 - below])


def draw_pose(rng, pose):
    """One C-arm pose's turns and distances, drawn about the view's nominal pose."""
    return {"yaw": rng.uniform(-pose["yaw"], pose["yaw"]), "tilt": rng.uniform(-pose["tilt"], pose["tilt"]),
            "roll": rng.uniform(-pose["roll"], pose["roll"]), "sod": rng.uniform(*pose["sod"]),
            "sdd": rng.uniform(*pose["sdd"])}


def in_frame(uv, size, margin=4.0):
    """Which points lie inside the frame, margin pixels in from its edges."""
    uv = np.asarray(uv, float)
    with np.errstate(invalid="ignore"):
        return np.all(np.isfinite(uv), axis=-1) & np.all((uv >= margin) & (uv < size - margin), axis=-1)


def visible_block(uv, size):
    """The longest run of consecutive levels whose bodies are wholly in the frame, the lower of two
    of one length; empty when no body is."""
    seen = in_frame(uv[:, :BODY_POINTS], size).all(axis=1)
    best, here = [], []
    for i, ok in enumerate(seen):
        here = here + [i] if ok else []
        if len(here) >= len(best):
            best = list(here)
    return best


def runs_of(block, names, last, sacrum_in, k_max, rng, anchors=("none", "bottom")):
    """The runs a frame gives: for each length from 2 to k_max that the block holds, one stretch of
    it at a place drawn at random, not anchored; and, where the block ends at the column's last level
    with the sacrum in the frame below it, the block's last bodies, anchored at the bottom."""
    out = []
    n = len(block)
    for k in range(2, min(k_max, n) + 1):
        if "none" in anchors:
            s = int(rng.integers(0, n - k + 1))
            out.append(("none", block[s:s + k]))
        if "bottom" in anchors and sacrum_in and names[block[-1]] == last:
            out.append(("bottom", block[n - k:]))
    return out


def frame_samples(uv, names, last, sacrum_in, size, k_max, rng, view, kind, person, anchors=("none", "bottom")):
    """The samples of one frame: its runs, each body's eighteen points with those outside the frame
    missing, as a detector could not see them."""
    uv = np.array(uv, float)
    uv[~in_frame(uv, size)] = np.nan
    block = visible_block(uv, size)
    samples = []
    for anchor, rows in runs_of(block, names, last, sacrum_in, k_max, rng, anchors):
        samples.append({"points": uv[rows], "names": [names[i] for i in rows], "view": view, "anchor": anchor,
                        "type": kind, "person": person})
    return samples


def phantom_person_samples(kind, seed, frames_per_view, k_max, noise_px, pose=None, lordosis=(0.3, 1.2)):
    """One phantom person's samples: the column drawn, bent and tilted, then frames_per_view frames in
    each view, each centred on a level drawn at random with the C-arm's turns and distances drawn
    about the view, the landmarks projected with noise_px of noise as a detector's error."""
    pose = dict(DEFAULT_POSE, **(pose or {}))
    rng = np.random.default_rng(seed)
    levels = column_of(kind, seed)
    names = [lv.name for lv in levels]
    origins, rots, ex, ey, ez = bent_column(levels, rng, lordosis)
    world = world_landmarks(levels, origins, rots)
    centres = world[:, :BODY_POINTS].mean(axis=1)
    sacrum = sacrum_point(levels, origins, rots)
    person = f"phantom:{kind}:{seed}"
    out = []
    for view in G.VIEWS:
        for _ in range(frames_per_view):
            aim = centres[int(rng.integers(0, len(levels)))] + rng.normal(0, pose["centre_mm"], 3)
            p = draw_pose(rng, pose)
            K, R, t = G.carm_camera(aim, ex, ey, ez, view, p["yaw"], p["tilt"], p["roll"], p["sod"], p["sdd"],
                                    pose["pixel_mm"], pose["size"])
            P = G.projection_matrix(K, R, t)
            uv = G.project(P, world) + rng.normal(0, noise_px, (len(levels), len(G.LANDMARKS), 2))
            sacrum_in = bool(in_frame(G.project(P, sacrum[None])[0], pose["size"]))
            out += frame_samples(uv, names, names[-1], sacrum_in, pose["size"], k_max, rng, view, kind, person)
    return out


def phantom_samples(classes, seeds, frames_per_view, k_max, noise_px, pose=None, lordosis=(0.3, 1.2)):
    """Every class's persons' samples: seeds maps each class to its persons' seeds."""
    out = []
    for kind in classes:
        for seed in seeds[kind]:
            out += phantom_person_samples(kind, seed, frames_per_view, k_max, noise_px, pose, lordosis)
    return out


def seeds_for(classes, count, part, round_offset=0):
    """Each class's persons' seeds, disjoint between the selection and the gate and between classes:
    the gate's seeds sit a million above the selection's, each class's a hundred thousand apart."""
    base = 1_000_000 if part == "gate" else 0
    return {kind: [base + 100_000 * i + 1 + j + round_offset for j in range(count)] for i, kind in enumerate(classes)}


# ---------------------------------------------------------------- the split rule

def split_part(person, rule, test_persons):
    """data/splits/rule.json's part of a person: test where the person is on test-persons.json,
    validation where the first eight bytes of the hash fall below the share, training otherwise."""
    if person in test_persons:
        return "test"
    value = int.from_bytes(hashlib.sha256(f"schwingnet-split|{rule['salt']}|{person}".encode()).digest()[:8], "big")
    return "validation" if value < rule["validation_share"] * 2 ** 64 else "training"


def split_rule():
    rule = json.loads((ROOT / "data" / "splits" / "rule.json").read_text())
    tests = {r["person"] for r in json.loads((ROOT / "data" / "splits" / "test-persons.json").read_text())}
    return rule, tests


# ---------------------------------------------------------------- C-ArmLSpine's pairs

def frame_key(path):
    return hashlib.sha1(os.path.basename(path).encode()).hexdigest()[:12]


def stored_to_atten(img):
    """Bone bright: minus the log of the stored value, as the poses' registration saw the frame."""
    x = img.astype(np.float64)
    lo = np.percentile(x, 0.1)
    return -np.log(np.clip(x - lo + 1.0, 1.0, None) / (np.percentile(x, 99.9) - lo + 1.0))


def block_mean(x, f):
    H, W = x.shape[0] // f, x.shape[1] // f
    return x[: H * f, : W * f].reshape(H, f, W, f).mean((1, 3))


def read_frame(path, size):
    """A spot frame as attenuation, brought down by whole blocks to about size pixels a side; returns
    the image and the factor it was brought down by."""
    import pydicom
    ds = pydicom.dcmread(path)
    img = ds.pixel_array
    if img.ndim != 2:
        raise ValueError("a spot frame is one 2-D image")
    if str(getattr(ds, "PhotometricInterpretation", "")) == "MONOCHROME1":
        img = img.max() - img
    f = max(1, int(round(img.shape[1] / size)))
    return block_mean(stored_to_atten(img), f).astype(np.float32), f


def pose_files(root, case):
    """The pose of each view a case has, AP from _ref and LAT from _ref2 where it exists, else _ref,
    from pose_150/ (the poses refit at the detector's true pitch) where that folder exists."""
    folder = root / "pose_150" if (root / "pose_150").is_dir() else root / "pose"
    out = {}
    for view, real in (("AP", "ap_real"), ("LAT", "lat_real")):
        tags = ("_ref2", "_ref") if view == "LAT" else ("_ref",)
        for tag in tags:
            p = folder / f"{case}_{view}{tag}.json"
            if p.is_file():
                out[real] = p
                break
    return out


def agreed_levels(entry):
    """The typical column's levels the two labellers agree on, by name, for a case with no variant
    flag; None for a flagged case, which the loop leaves out."""
    if entry.get("variant_flags"):
        return None
    agreed = {v.get("level") for v in entry.get("vertebrae", []) if v.get("agree") and v.get("level")}
    return [lv for lv in TYPE_LEVELS["typical"] if lv in agreed]


def read_pair(root, case, levels, size=512):
    """One case's pair, read on the grid: the oracle's landmarks on its SPINEPS masks for the agreed
    levels and the sacrum's centroid, in LPS millimetres as the poses take them, and each posed
    view's frame with its projection matrix brought down to the frame's size."""
    import nibabel as nib
    from autoanatomist.oracle import ChordOracle
    from autoanatomist import specs
    vert = nib.load(str(root / "spineps" / f"{case}_seg-vert_msk.nii.gz"))
    labels = np.asarray(vert.dataobj).astype(np.int16)
    sub_path = root / "spineps" / f"{case}_seg-spine_msk.nii.gz"
    sub = np.asarray(nib.load(str(sub_path)).dataobj).astype(np.int16) if sub_path.is_file() else None
    if sub is not None and sub.shape != labels.shape:
        sub = None
    names = {VERSE_ID[lv]: lv for lv in levels}
    keys = tuple(specs.SEVEN + specs.EXTRA)
    readings = {r.level: r for r in ChordOracle(keys).read(labels, vert.affine, names, sub)}
    to_lps = np.array([-1.0, -1.0, 1.0])
    marks = np.array([readings[lv].landmarks(keys) * to_lps if lv in readings else np.full((len(G.LANDMARKS), 3), np.nan)
                      for lv in levels])
    sac = np.argwhere(labels == VERSE_ID["sacrum"])
    sacrum = (sac @ vert.affine[:3, :3].T + vert.affine[:3, 3]).mean(axis=0) * to_lps if len(sac) else np.full(3, np.nan)
    frames = []
    folder = root / "unpacked" / "C-ArmLSpine" / case
    files = [str(p) for p in folder.rglob("*") if p.is_file()] if folder.is_dir() else []
    for view, pose_path in sorted(pose_files(root, case).items()):
        pose = json.loads(pose_path.read_text())
        match = [p for p in files if pose.get("frame_key") and frame_key(p) == pose["frame_key"]]
        match = match or [p for p in files if pose.get("frame") and os.path.basename(p) == pose["frame"]]
        if not match:
            continue
        image, f = read_frame(match[0], size)
        K = np.diag([1.0 / f, 1.0 / f, 1.0]) @ np.asarray(pose["K"], float)
        frames.append({"view": view, "P": G.projection_matrix(K, pose["R"], pose["t"]), "image": image,
                       "edge_ncc": float(pose.get("edge_ncc", float("nan")))})
    return {"levels": list(levels), "landmarks": marks, "sacrum": sacrum, "frames": frames, "stand_in": False}


def save_pair(path, pair):
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "wb") as f:
        np.savez(f, levels=np.asarray(pair["levels"], dtype=str), landmarks=pair["landmarks"], sacrum=pair["sacrum"],
                 views=np.asarray([fr["view"] for fr in pair["frames"]], dtype=str),
                 P=np.asarray([fr["P"] for fr in pair["frames"]]).reshape(-1, 3, 4),
                 images=np.asarray([fr["image"] for fr in pair["frames"]], np.float32),
                 edge_ncc=np.asarray([fr.get("edge_ncc", np.nan) for fr in pair["frames"]], float),
                 stand_in=np.asarray(pair["stand_in"]))
    os.replace(tmp, path)


def load_pair(path):
    with np.load(path) as z:
        frames = [{"view": str(v), "P": P, "image": img, "edge_ncc": float(e)}
                  for v, P, img, e in zip(z["views"], z["P"], z["images"], z["edge_ncc"])]
        return {"levels": [str(x) for x in z["levels"]], "landmarks": z["landmarks"], "sacrum": z["sacrum"],
                "frames": frames, "stand_in": bool(z["stand_in"])}


def carm_cases(root):
    """The C-ArmLSpine cases with a CBCT mask, a pose and an entry in levels.json, each with its part
    by the split rule; the test persons are named and left unread."""
    rule, tests = split_rule()
    entries = json.loads((root / "levels.json").read_text())
    entries = entries.get("cases", entries)
    out, skipped = [], {"test": 0, "flagged": 0, "no mask": 0, "no pose": 0, "too few levels": 0}
    for case in sorted(entries):
        person = f"carmlspine:{case}"
        part = split_part(person, rule, tests)
        if part == "test":
            skipped["test"] += 1
            continue
        levels = agreed_levels(entries[case])
        if levels is None:
            skipped["flagged"] += 1
        elif len(levels) < 2:
            skipped["too few levels"] += 1
        elif not (root / "spineps" / f"{case}_seg-vert_msk.nii.gz").is_file():
            skipped["no mask"] += 1
        elif not pose_files(root, case):
            skipped["no pose"] += 1
        else:
            out.append({"case": case, "person": person, "part": part, "levels": levels})
    return out, skipped


def cpu_only():
    """A pool's worker keeps off the card, whose memory the round's own process holds: JAX, where a
    module the worker imports brings it in, starts on the CPU."""
    os.environ["JAX_PLATFORMS"] = "cpu"


def pair_job(args):
    """One case read and cached, for a pool; returns the cache file, or why it could not be read in
    words that name no file."""
    cpu_only()
    root, case, levels, cache, size = args
    path = os.path.join(cache, f"{case}.npz")
    if os.path.exists(path):
        return path, None
    try:
        save_pair(path, read_pair(Path(root), case, levels, size))
        return path, None
    except Exception as exc:          # one case's failure is counted, never fatal to the rest
        return None, type(exc).__name__


# ---------------------------------------------------------------- stand-ins

def make_stand_in(seed, frames_per_view=2, size=512, pixel_mm=0.6):
    """A stand-in pair: a typical phantom from T12 to L5 rendered and read by the oracle, a frame in
    each view splatted from its bone voxels through a drawn pose, and the pose the samples are
    projected through perturbed from the true one by up to a degree and three millimetres."""
    from autoanatomist import phantom
    from autoanatomist.oracle import ChordOracle
    from autoanatomist import specs
    rng = np.random.default_rng(seed)
    levels = column_of("typical", seed)
    tilt = (tuple(float(v) for v in rng.normal(size=3)), float(rng.uniform(0.0, 10.0)))
    ph = phantom.render(levels, spacing=(1.25,) * 3, tilt=tilt, sub=1, noise_hu=0.0, seed=seed)
    keys = tuple(specs.SEVEN + specs.EXTRA)
    readings = {r.level: r for r in ChordOracle(keys).read(ph.labels, ph.affine, ph.names)}
    names = [lv.name for lv in levels]
    marks = np.array([readings[n].landmarks(keys) if n in readings else np.full((len(G.LANDMARKS), 3), np.nan)
                      for n in names])
    R0 = G.rotation(tilt[0], tilt[1])
    centre = ph.centres.mean(axis=0)
    bone = np.argwhere(ph.hu > 150.0)
    world = bone @ ph.affine[:3, :3].T + ph.affine[:3, 3]
    weight = (ph.hu[tuple(bone.T)] + 1000.0) / 1000.0
    frames = []
    for view in G.VIEWS:
        for _ in range(frames_per_view):
            p = draw_pose(rng, DEFAULT_POSE)
            aim = centre + rng.normal(0, 15.0, 3)
            K, R, t = G.carm_camera(aim, R0[:, 0], R0[:, 1], R0[:, 2], view, p["yaw"], p["tilt"], p["roll"],
                                    p["sod"], p["sdd"], pixel_mm, size)
            image = splat(world, weight, G.projection_matrix(K, R, t), size)
            R_fit = G.rotation(rng.normal(size=3), rng.uniform(0.0, 1.0)) @ R
            shift = rng.normal(size=3)
            t_fit = t + shift / np.linalg.norm(shift) * rng.uniform(0.0, 3.0)
            frames.append({"view": f"{view}_real", "P": G.projection_matrix(K, R_fit, t_fit), "image": image,
                           "edge_ncc": float("nan")})
    sacrum = ph.centres[-1] - R0[:, 2] * (levels[-1].H / 2 + phantom.DISC_SHARE * levels[-1].H + SACRUM_BELOW_MM)
    return {"levels": names, "landmarks": marks, "sacrum": sacrum, "frames": frames, "stand_in": True}


def splat(world, weight, P, size):
    """A frame from bone voxels: each voxel's weight added at the pixel it projects to, blurred so
    the voxels' gaps close; bone bright, as the real frames are read."""
    uv = G.project(P, world)
    ok = np.all(np.isfinite(uv), axis=1)
    c, r = np.floor(uv[ok, 0]).astype(int), np.floor(uv[ok, 1]).astype(int)
    inside = (c >= 0) & (c < size) & (r >= 0) & (r < size)
    image = np.bincount(r[inside] * size + c[inside], weights=weight[ok][inside], minlength=size * size)
    return G.smooth(image.reshape(size, size), 2.0).astype(np.float32)


def stand_in_job(args):
    cpu_only()
    seed, cache, size = args
    path = os.path.join(cache, f"standin-{seed}.npz")
    if not os.path.exists(path):
        save_pair(path, make_stand_in(seed, size=size))
    return path, None


# ---------------------------------------------------------------- pairs to samples

def pair_samples(pair, person, k_max, size=512):
    """A pair's samples: in each posed frame, the agreed levels' landmarks projected through the
    frame's pose, the visible run's stretches named among the typical column, never anchored (the
    real arm's models are the typical column's alone, so an anchored run would name itself)."""
    rng = np.random.default_rng(int(hashlib.sha1(person.encode()).hexdigest()[:8], 16))
    out = []
    for fr in pair["frames"]:
        uv = G.project(fr["P"], pair["landmarks"])
        out += frame_samples(uv, pair["levels"], pair["levels"][-1], False, size, k_max, rng, fr["view"], "typical",
                             person, anchors=("none",))
    return out


def column_means(a):
    """Each column's mean over its numbers, NaN for a column with none, without numpy's warning."""
    a = np.asarray(a, float)
    ok = np.isfinite(a)
    n = ok.sum(axis=0)
    return np.where(n > 0, np.where(ok, a, 0.0).sum(axis=0) / np.maximum(n, 1), np.nan)


def pair_presence(pair, radius=8, sigma=1.5, null_per_body=200, size=512):
    """Each posed frame's evidence for every landmark: the percentile of the strongest edge near the
    landmark's projection against points drawn inside the visible bodies, averaged over the
    visible bodies; (frames, 18), NaN where no body is in view."""
    rows = []
    for i, fr in enumerate(pair["frames"]):
        uv = G.project(fr["P"], pair["landmarks"])
        uv[~in_frame(uv, size)] = np.nan
        block = visible_block(uv, size)
        if not block:
            rows.append(np.full(len(G.LANDMARKS), np.nan))
            continue
        pct, _ = G.presence_percentiles(fr["image"], [uv[j] for j in block], range(len(G.LANDMARKS)), radius, sigma,
                                        null_per_body, seed=i)
        rows.append(column_means(pct))
    return np.asarray(rows).reshape(-1, len(G.LANDMARKS))
