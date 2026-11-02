#!/usr/bin/env python3
"""External real arms for the QA loop: CT-to-X-ray pairs from sets other than C-ArmLSpine, in the pair format the loop
already reads (tools/qaloop_samples.py save_pair), each with a manifest naming its persons and their part.

Greg, 2026-11-01: mix real fluoroscopy into the validation of the 2D landmarks so they cannot be synthetic artefacts,
DeepFluoro first, then COBRA2026. These persons serve the gates only (the external arm of docs/research/qa-loop-external/
PREREG.md): they never choose a landmark and never train a network, as the real-frame sets are test only by the harvest
directive (tools/anomaly_route.py, TEST_ONLY_SOURCES). Each set keeps a held-out part the loop never reads, so a final
test stays clean of the controller's steering.

DeepFluoro (Grupp 2020): six cadaveric lower torsos, 366 frames on a Siemens Cios Fusion with ground-truth poses. The
realxray export of 2026-09-21 (data/realxray/deepfluoro) already holds each frame converted to attenuation at 384
pixels with its K and extrinsic in the CT's LPS frame, checked against the shipped 2D labels; realxray_work/deepfluoro
holds each specimen's CT, TotalSegmentator's vertebrae and the two labellers' level names (levels.json). This tool
places the oracle's eighteen landmarks on the TotalSegmentator vertebrae of the levels both labellers name alike (the
longest consecutive such stretch, two or more), takes them to LPS as read_pair does, and projects them through each
frame's pose brought to the loop's 512 pixels. The specimen the export held out for test (18-1109) is held out here.

    python tools/realx_pairs.py deepfluoro --data <data root> --out <folder>
    python tools/realx_pairs.py cobra --data <data root> --out <folder>
    python tools/realx_pairs.py cobra_varian --data <data root> --out <folder>   # tools/cobra_varian_export.py's export
    python tools/realx_pairs.py check --out <folder>        # overlays and the box agreement, on the grid
    python tools/realx_pairs.py annotations --out <realx/deepfluoro> --shipped <folder of deepfluoro_shipped.py>

The last sets DeepFluoro's own annotations (its fourteen person-placed pelvic landmarks and its 2-D label image, read
from the release by tools/deepfluoro_shipped.py) against the arm, so the arm is checked by something this project did
not make.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[0] = str(ROOT / "src")
for _folder in (ROOT / "grid" / "autoanatomist", ROOT / "tools"):
    if str(_folder) not in sys.path:
        sys.path.insert(1, str(_folder))

import argparse  # noqa: E402
import json  # noqa: E402

import numpy as np  # noqa: E402

import deepfluoro_shipped as DS  # noqa: E402
import qaloop_samples as S  # noqa: E402

G = S.G
SIZE = 512
DEEPFLUORO_TEST = ("18-1109",)          # the realxray export's test specimen, held out here too
TS_FILES = {"T12": "vertebrae_T12", "L1": "vertebrae_L1", "L2": "vertebrae_L2", "L3": "vertebrae_L3", "L4": "vertebrae_L4",
            "L5": "vertebrae_L5", "sacrum": "sacrum"}
TO_LPS = np.array([-1.0, -1.0, 1.0])
# The namer's phantom frames are drawn within 10 degrees of the anteroposterior and lateral views (qaloop_samples
# DEFAULT_POSE); a real frame further than VIEW_TOLERANCE_DEG from both is a view the namer never saw, so it is left
# out rather than counted against it. COBRA's 24 frames a case span the whole quarter turn.
VIEW_TOLERANCE_DEG = 15.0
LEVEL_COLOURS = [(255, 80, 80), (80, 200, 255), (120, 255, 120), (255, 170, 40), (220, 120, 255), (255, 255, 255)]


def agreed_stretch(entry):
    """The longest stretch of consecutive levels both labellers name alike, two or more, else empty. The variant
    flag is not a reason to leave a case out here: in DeepFluoro it comes from the labellers' disagreement at the
    sacrum, below the stretch, which the stretch does not cross."""
    agreed = {v.get("level") for v in entry.get("vertebrae", []) if v.get("agree") and v.get("level")}
    best, run = [], []
    for lv in S.TYPE_LEVELS["typical"]:
        run = run + [lv] if lv in agreed else []
        if len(run) > len(best):
            best = list(run)
    return best if len(best) >= 2 else []


def ts_labels(folder):
    """TotalSegmentator's per-structure masks as one volume in VerSe ids, with its affine."""
    import nibabel as nib
    labels, affine = None, None
    for level, stem in TS_FILES.items():
        path = folder / f"{stem}.nii.gz"
        if not path.is_file():
            continue
        img = nib.load(str(path))
        mask = np.asarray(img.dataobj) > 0
        if labels is None:
            labels, affine = np.zeros(mask.shape, np.int16), img.affine
        if mask.shape != labels.shape:
            raise ValueError("TotalSegmentator's masks differ in shape")
        labels[mask] = S.VERSE_ID[level]
    if labels is None:
        raise ValueError("no TotalSegmentator vertebra mask")
    return labels, affine


def harvest_ts_labels(path):
    """The anomaly harvest's TotalSegmentator labels (one multi-label file a case, its class map two folders up)
    as one volume in VerSe ids, with its affine. TotalSegmentator 2.18 labels S1 apart from the rest of the
    sacrum; the sacrum here is the two together, as SPINEPS's is and as tools/cobra_varian_export.py boxed it."""
    import nibabel as nib
    path = Path(path)
    ids = {name: int(i) for i, name in json.loads((path.parent.parent / "class_map.json").read_text()).items()}
    img = nib.load(str(path))
    raw = np.asarray(img.dataobj)
    labels = np.zeros(raw.shape, np.int16)
    for level, stem in TS_FILES.items():
        labels[raw == ids[stem]] = S.VERSE_ID[level]
    labels[raw == ids["vertebrae_S1"]] = S.VERSE_ID["sacrum"]
    if not labels.any():
        raise ValueError("no TotalSegmentator vertebra label")
    return labels, img.affine


def read_ts(ts):
    """A folder of per-structure masks (the Elekta export's seg tree) or one harvest label file."""
    return ts_labels(ts) if Path(ts).is_dir() else harvest_ts_labels(ts)


def landmarks_of(labels, affine, levels):
    """The oracle's landmarks for the levels, read whole (no subregions), in LPS millimetres, the sacrum's centroid and
    its four anchor points (qaloop_samples.sacral_points)."""
    from autoanatomist.oracle import ChordOracle
    from autoanatomist import specs
    keys = tuple(specs.SEVEN + specs.EXTRA)
    names = {S.VERSE_ID[lv]: lv for lv in levels}
    readings = {r.level: r for r in ChordOracle(keys).read(labels, affine, names, None)}
    marks = np.array([readings[lv].landmarks(keys) * TO_LPS if lv in readings else np.full((len(G.LANDMARKS), 3), np.nan)
                      for lv in levels])
    sac = np.argwhere(labels == S.VERSE_ID["sacrum"])
    sacrum = (sac @ affine[:3, :3].T + affine[:3, 3]).mean(axis=0) * TO_LPS if len(sac) else np.full(3, np.nan)
    return marks, sacrum, S.sacral_points(labels, affine) * TO_LPS


def frame_of(meta, image_path):
    """One exported frame at the loop's size: the image centred on a square canvas of its longer side (so a frame
    that is not square keeps its aspect) and brought to 512, the export's K moved and scaled alike. Both exports
    write K for their own PNG in edge coordinates, pixel i spanning [i, i+1), which scaling keeps. The sign of P
    is set later by orient(); the attenuation image is upsampled bilinearly."""
    from PIL import Image
    img = Image.open(image_path).convert("L")
    w, h = img.size
    side = max(w, h)
    dx, dy = (side - w) / 2.0, (side - h) / 2.0
    canvas = Image.new("L", (side, side), 0)
    canvas.paste(img, (int(dx), int(dy)))
    s = SIZE / side
    K = np.array([[s, 0.0, s * int(dx)], [0.0, s, s * int(dy)], [0.0, 0.0, 1.0]]) @ np.asarray(meta["pose"]["K"], float)
    ext = np.asarray(meta["pose"]["ext"], float)
    P = G.projection_matrix(K, ext[:3, :3], ext[:3, 3])
    view = view_of(meta)
    if view is None:
        return None
    return {"view": view, "P": P, "image": np.asarray(canvas.resize((SIZE, SIZE), Image.BILINEAR), np.float32) / 255.0,
            "edge_ncc": float(meta["pose"].get("qc_edge_ncc", float("nan")))}


def view_of(meta):
    """ap_real within VIEW_TOLERANCE_DEG of the anteroposterior view, lat_real within it of the lateral, else None."""
    lat = meta.get("view", {}).get("lat_from_ap_deg")
    if lat is None:
        return None
    lat = abs(float(lat)) % 180.0
    lat = min(lat, 180.0 - lat)
    if lat <= VIEW_TOLERANCE_DEG:
        return "ap_real"
    if lat >= 90.0 - VIEW_TOLERANCE_DEG:
        return "lat_real"
    return None


def orient(P, points):
    """P with the sign that gives the points positive depth: projection is unchanged by the sign, the loop's
    project() reads a negative depth as behind the source."""
    pts = np.asarray(points, float).reshape(-1, 3)
    pts = pts[np.isfinite(pts).all(axis=1)]
    if not len(pts):
        return P
    w = pts @ P[2, :3] + P[2, 3]
    return -P if np.median(w) < 0 else P


def square(image_path):
    from PIL import Image
    with Image.open(image_path) as img:
        return img.size[0] == img.size[1]


def metas_by_case(export):
    metas = {}
    for path in sorted((Path(export) / "meta").glob("*.json")):
        m = json.loads(path.read_text())
        metas.setdefault(m["case"], []).append(m)
    return metas


def structure_in_view(meta, levels):
    """Whether the export kept a box for the sacrum or one of the stretch's levels on this frame, which it does
    where half the structure's projected voxels fall inside the image."""
    names = set(levels) | {"sacrum"}
    return any(kept(b) and b.get("level_ts") in names for b in meta.get("boxes", []))


def build(source, export, cases, out, in_view=None):
    """The pairs of one source. cases: (case, person, levels, TotalSegmentator folder, held-out reason or None,
    left-out reason or None), in order; a held-out or left-out case is named in the manifest and never read. With
    in_view, a frame it says shows none of the person's structures is left out and counted."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    metas = metas_by_case(export)
    manifest = {"source": source, "export": str(export), "size": SIZE, "view_tolerance_deg": VIEW_TOLERANCE_DEG,
                "persons": [], "held_out": [], "left_out": {}, "frames_left_out": {}}
    skipped = manifest["frames_left_out"]
    for case, person, levels, ts, held, left in cases:
        if held:
            manifest["held_out"].append({"person": person, "frames": len(metas.get(case, [])), "why": held})
            continue
        if left or not levels:
            manifest["left_out"][person] = left or "no two consecutive levels both labellers name alike"
            continue
        try:
            labels, affine = read_ts(Path(ts))
        except (OSError, ValueError) as exc:
            manifest["left_out"][person] = f"segmentation not read: {type(exc).__name__}"
            continue
        marks, sacrum, sacral = landmarks_of(labels, affine, levels)
        frames, ids = [], []
        for m in metas.get(case, []):
            image = Path(export) / "images" / m["split"] / f"{case}_{m['frame']}.png"
            if not image.is_file():
                continue
            if view_of(m) is None:
                skipped["oblique"] = skipped.get("oblique", 0) + 1
                continue
            if not square(image):
                # the canvas a frame that is not square is centred on holds no image at its margins, where a
                # body would count as seen; such frames are few (COBRA's collimated bands) and left out
                skipped["not square"] = skipped.get("not square", 0) + 1
                continue
            if in_view is not None and not in_view(m, levels):
                skipped["no structure in view"] = skipped.get("no structure in view", 0) + 1
                continue
            fr = frame_of(m, image)
            fr["P"] = orient(fr["P"], marks)
            frames.append(fr)
            ids.append(m["frame"])
        if not frames:
            manifest["left_out"][person] = "no exported frame"
            continue
        path = out / f"{case}.npz"
        S.save_pair(str(path), {"levels": levels, "landmarks": marks, "sacrum": sacrum, "sacral": sacral, "frames": frames, "stand_in": False})
        read = int(np.isfinite(marks).all(axis=2).sum())
        manifest["persons"].append({"person": person, "case": case, "npz": path.name, "levels": levels, "frames": len(frames), "frame_ids": ids,
                                    "landmarks_read": read, "landmarks_total": int(marks.shape[0] * marks.shape[1])})
        print(f"{case}: levels {levels}, {len(frames)} frames, {read} of {marks.shape[0] * marks.shape[1]} landmarks read", flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"{source}: {len(manifest['persons'])} persons built, {len(manifest['held_out'])} held out, {len(manifest['left_out'])} left out", flush=True)
    return manifest


def build_deepfluoro(data, out):
    data = Path(data)
    work = data / "realxray_work" / "deepfluoro"
    entries = json.loads((work / "levels.json").read_text())["cases"]
    cases = [(case, f"deepfluoro:{case}", agreed_stretch(entries[case]), work / case / "ts",
              "the export's test specimen" if case in DEEPFLUORO_TEST else None, None) for case in sorted(entries)]
    return build("deepfluoro", data / "realxray" / "deepfluoro", cases, out)


def cobra_levels(record):
    """The longest consecutive stretch of the export's structures both labellers name alike."""
    agreed = {s.get("level") for s in record.get("structures", {}).values() if s.get("level_agree") and s.get("level")}
    best, run = [], []
    for lv in S.TYPE_LEVELS["typical"]:
        run = run + [lv] if lv in agreed else []
        if len(run) > len(best):
            best = list(run)
    return best if len(best) >= 2 else []


def build_cobra(data, out, export_name="cobra_elekta_v3", source="cobra2026", ts_of=None, in_view=None):
    """COBRA2026's Elekta export (realxray_cobra_export v2, 24 frames a case, the CT-to-projection axis map confirmed
    by edge NCC case by case): the export's test cases (md5 of the case mod 10 is 8 or 9) are held out; a case whose
    column the transitional screen (cobra2026/lstv) does not call ordinary, L1 to L5 above the sacrum, is left out,
    since the real arm names the typical column. ts_of gives a case's TotalSegmentator labels where they are not the
    Elekta seg tree's; in_view is build's."""
    data = Path(data)
    export = data / "realxray" / export_name
    ts_of = ts_of or (lambda case: data / "cobra2026" / "seg" / case / "ts")
    cases = []
    for path in sorted((export / "cases").glob("*.json")):
        rec = json.loads(path.read_text())
        case = rec["case"]
        if rec.get("status") != "ok":
            cases.append((case, f"cobra2026:{case}", [], None, None, f"export status {rec.get('status')}"))
            continue
        held = "the export's test case" if rec.get("split") == "test" else None
        call = data / "cobra2026" / "lstv" / f"{case}.json"
        subtype = json.loads(call.read_text()).get("call_by_mask_id", {}).get("subtype") if call.is_file() else None
        left = None if subtype == "ordinary" else f"transitional screen: {subtype}"
        cases.append((case, f"cobra2026:{case}", cobra_levels(rec), ts_of(case), held, left))
    return build(source, export, cases, out, in_view)


def build_cobra_varian(data, out):
    """COBRA2026's Varian export (tools/cobra_varian_export.py: centres F and G, 24 frames a case, square crops
    about the lumbosacral junction, the axis map confirmed by edge NCC case by case), by build_cobra's rules, the
    TotalSegmentator labels the anomaly harvest made on the same ct_def standing for the Elekta seg tree. The Varian
    fields are pelvic and centred on the treatment target, below the spine, so many frames hold no structure of the
    column at all; a frame with no box of the sacrum or of the person's levels is left out and counted."""
    data = Path(data)
    harvest = data / "anomaly_harvest" / "cobra" / "ts"
    return build_cobra(data, out, "cobra_varian", "cobra_varian", lambda case: harvest / f"{case}.nii.gz", structure_in_view)


def box_at_size(meta, box, image_path):
    """An export's box, in its PNG's pixels, on the loop's padded 512-pixel canvas."""
    from PIL import Image
    with Image.open(image_path) as img:
        w, h = img.size
    side = max(w, h)
    s = SIZE / side
    dx, dy = int((side - w) / 2.0), int((side - h) / 2.0)
    x0, y0, x1, y1 = np.asarray(box, float)
    return s * (x0 + dx), s * (y0 + dy), s * (x1 + dx), s * (y1 + dy)


def kept(box):
    """Whether an export kept a box: DeepFluoro's export says so, COBRA's gives the visible share, kept at a half."""
    return bool(box.get("kept", box.get("visible_frac", 0.0) >= 0.5))


def check(out, data=None):
    """For every built pair: the share of each level's projected landmarks inside the export's own box for that level
    (which it drew from the same CT through the same pose), and a contact sheet of two frames a person with the
    landmarks drawn, for a look by eye."""
    from PIL import Image, ImageDraw
    out = Path(out)
    manifest = json.loads((out / "manifest.json").read_text())
    export = Path(manifest["export"]) if data else None
    tiles, report = [], {}
    for p in manifest["persons"]:
        pair = S.load_pair(str(out / p["npz"]))
        inside, total, s_in, s_total = 0, 0, 0, 0
        for k, fr in enumerate(pair["frames"]):
            uv = G.project(fr["P"], pair["landmarks"])
            if export is not None:
                meta_path = export / "meta" / f"{p['case']}_{p['frame_ids'][k]}.json"
                meta = json.loads(meta_path.read_text()) if meta_path.is_file() else None
                for i, lv in enumerate(pair["levels"]):
                    box = next((b for b in (meta or {}).get("boxes", []) if b.get("level") == lv and kept(b)), None)
                    if box is None:
                        continue
                    x0, y0, x1, y1 = box_at_size(meta, box["box"], export / "images" / meta["split"] / f"{p['case']}_{meta['frame']}.png")
                    pts = uv[i][S.in_frame(uv[i], SIZE, margin=0.0)]     # a box is clipped to the frame, so is the count
                    inside += int(((pts[:, 0] >= x0 - 6) & (pts[:, 0] <= x1 + 6) & (pts[:, 1] >= y0 - 6) & (pts[:, 1] <= y1 + 6)).sum())
                    total += len(pts)
            if k in (0, len(pair["frames"]) // 2) and len(tiles) < 24:
                # each level in its own colour, its landmarks as dots and the export's own box for it as a frame,
                # so a landmark set that sits on another level, or off the bone, shows at a glance
                im = Image.fromarray((np.clip(fr["image"], 0, 1) * 255).astype(np.uint8)).convert("RGB")
                d = ImageDraw.Draw(im)
                for i, lv in enumerate(pair["levels"]):
                    col = LEVEL_COLOURS[i % len(LEVEL_COLOURS)]
                    if export is not None and meta is not None:
                        box = next((b for b in meta.get("boxes", []) if b.get("level") == lv), None)
                        if box is not None:
                            x0, y0, x1, y1 = box_at_size(meta, box["box"], export / "images" / meta["split"] / f"{p['case']}_{meta['frame']}.png")
                            d.rectangle([x0, y0, x1, y1], outline=col, width=2)
                    for u, v in uv[i]:
                        if np.isfinite(u) and np.isfinite(v):
                            d.ellipse([u - 4, v - 4, u + 4, v + 4], fill=col, outline=(0, 0, 0))
                for u, v in G.project(fr["P"], pair["sacral"]):
                    if np.isfinite(u) and np.isfinite(v):
                        d.rectangle([u - 5, v - 5, u + 5, v + 5], outline=(255, 255, 0), width=2)
                d.text((8, 8), f"{p['case']} frame {p['frame_ids'][k]} {fr['view']}: " + " ".join(pair["levels"]) + " + S1 anchor", fill=(255, 255, 0))
                tiles.append(im.resize((384, 384)))
            if export is not None and meta is not None:
                # the anchor's points against the export's own sacrum box
                box = next((b for b in meta.get("boxes", []) if b.get("level") == "sacrum" and kept(b)), None)
                if box is not None:
                    x0, y0, x1, y1 = box_at_size(meta, box["box"], export / "images" / meta["split"] / f"{p['case']}_{meta['frame']}.png")
                    sv = G.project(fr["P"], pair["sacral"])
                    sv = sv[S.in_frame(sv, SIZE, margin=0.0)]
                    s_in += int(((sv[:, 0] >= x0 - 6) & (sv[:, 0] <= x1 + 6) & (sv[:, 1] >= y0 - 6) & (sv[:, 1] <= y1 + 6)).sum())
                    s_total += len(sv)
        report[p["person"]] = {"inside_box": inside, "points": total, "share": round(inside / total, 3) if total else None,
                               "sacral_inside_box": s_in, "sacral_points": s_total}
    if tiles:
        cols = 4
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 384, rows * 384), "white")
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % cols) * 384, (i // cols) * 384))
        sheet.save(out / "check_sheet.png")
    (out / "check.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return report


# DeepFluoro's 2-D label ids (tools/deepfluoro_shipped.py), the presence measure's own radius as the distance a point
# may sit from a labelled pixel, and the bars docs/research/qa-loop-external/README.md stated before the check ran.
SHIPPED_SPINE, SHIPPED_UPPER_SACRUM, SHIPPED_BONE = (3, 4), (4,), (1, 2, 3, 4, 5, 6)
NEAR_PX = 8
ANNOTATION_BARS = {"reprojection_median_px": 1.0, "reprojection_p90_px": 2.0, "on_spine": 0.9}
PRESENCE_BARS = {"frame_mean": 0.6, "share_low": 0.6}       # the loop's presence bars (grid/qaloop/qa_ext.json)


def distance_to(seg, labels):
    """Each canvas pixel's distance in pixels to the nearest pixel carrying one of the labels, inf where none does."""
    from scipy.ndimage import distance_transform_edt
    hit = np.isin(seg, labels)
    if not hit.any():
        return np.full(seg.shape, np.inf)
    return distance_transform_edt(~hit)


def readings(uv_shipped, uv_ours):
    """The distances between the shipped 2-D landmarks and the person's 3-D ones projected, where both are in frame."""
    ok = S.in_frame(uv_ours, SIZE, margin=0.0) & np.isfinite(uv_shipped).all(axis=-1)
    return np.linalg.norm(uv_shipped[ok] - uv_ours[ok], axis=-1)


def shipped_readings(z, k):
    """The four ways the shipped coordinates could be read (column or row first; turned with the image or not), each
    as the frame's landmarks on the loop canvas. deepfluoro_shipped.to_loop is the export's own reading."""
    raw, rot, cols, rows = z["raw"][k], int(z["rot"][k]), int(z["cols"]), int(z["rows"])
    return {(order, turned): DS.to_loop(raw if order == "column first" else raw[:, ::-1], rot if turned else 0, cols, rows)
            for order in ("column first", "row first") for turned in (True, False)}


def share_near(dist, uv, near=NEAR_PX):
    """How many of the in-frame points sit within near pixels of the labelled region, and how many were in frame."""
    uv = np.asarray(uv, float).reshape(-1, 2)
    uv = uv[S.in_frame(uv, SIZE, margin=0.0)]
    d = G.sample_at(dist, uv)
    return int((d <= near).sum()), int(len(uv))


def ratio(hit, n):
    return round(hit / n, 3) if n else None


def annotations(out, shipped):
    """DeepFluoro's own annotations against the arm, three ways (docs/research/qa-loop-external/README.md): the pose
    chain in the loop's pixels (the person's 3-D pelvic landmarks through the pair's P against the shipped 2-D ones);
    the arm's lumbar landmarks and sacral points against the shipped label image, which the dataset's authors drew
    from their own 3-D labels; and the presence measure on the landmarks a person placed, which the loop's presence
    gate must find if it can tell a real structure on these frames at all, beside the arm's own landmarks and anchor
    on the same frames. Writes annotations.json and annotations_sheet.png beside the shipped files, so the arm's own
    folder, which a running loop reads, is never written."""
    out, shipped = Path(out), Path(shipped)
    manifest = json.loads((out / "manifest.json").read_text())
    errors = {}
    spine = {"near_spine": [0, 0], "near_bone": [0, 0], "by_level": {}, "by_view": {}}
    sacral = {name: {"near_spine": [0, 0], "near_upper_sacrum": [0, 0], "near_bone": [0, 0]} for name in S.SACRAL_POINTS}
    top_to_sacrum = []
    person_edge, person_interior, ours_all, ours_anchor, ours_rows = [], [], [], [], []
    by_landmark = {}
    tiles = []
    for p in manifest["persons"]:
        pair = S.load_pair(str(out / p["npz"]))
        with np.load(shipped / f"{p['case']}.npz") as z:
            z = {k: z[k] for k in z.files}
        if [str(x) for x in z["frame_ids"]] != list(p["frame_ids"]):
            raise SystemExit(f"{p['case']}: the shipped frames are not the manifest's")
        names = [str(x) for x in z["names"]]
        edge = [i for i, n in enumerate(names) if not DS.is_interior(n)]
        interior = [i for i, n in enumerate(names) if DS.is_interior(n)]
        presence = S.pair_presence(pair)
        anchor = S.pair_anchor(pair)
        for k, fr in enumerate(pair["frames"]):
            ours = G.project(fr["P"], z["lm3d"])
            ways = shipped_readings(z, k)
            for way, uv in ways.items():
                errors.setdefault(way, []).extend(readings(uv, ours).tolist())
            uv_person = ways[("column first", True)]
            seg = z["seg"][k]
            d_spine, d_bone = distance_to(seg, SHIPPED_SPINE), distance_to(seg, SHIPPED_BONE)
            d_upper = distance_to(seg, SHIPPED_UPPER_SACRUM)
            marks = G.project(fr["P"], pair["landmarks"])
            for i, lv in enumerate(pair["levels"]):
                for key, dist in (("near_spine", d_spine), ("near_bone", d_bone)):
                    h, n = share_near(dist, marks[i])
                    spine[key][0] += h
                    spine[key][1] += n
                    for group, name in (("by_level", lv), ("by_view", fr["view"])):
                        cell = spine[group].setdefault(name, {"near_spine": [0, 0], "near_bone": [0, 0]})[key]
                        cell[0] += h
                        cell[1] += n
            sv = G.project(fr["P"], pair["sacral"])
            for j, name in enumerate(S.SACRAL_POINTS):
                for key, dist in (("near_spine", d_spine), ("near_upper_sacrum", d_upper), ("near_bone", d_bone)):
                    h, n = share_near(dist, sv[j])
                    sacral[name][key][0] += h
                    sacral[name][key][1] += n
            top = sv[S.SACRAL_POINTS.index("s1_top_centre")]
            if S.in_frame(top[None], SIZE, margin=0.0)[0]:
                top_to_sacrum.append(float(G.sample_at(d_upper, top[None])[0]))
            # the presence measure at the person's landmarks, the null drawn inside the outline they make
            seen = S.in_frame(uv_person, SIZE)
            if seen.sum() >= 3:
                body = np.where(seen[:, None], uv_person, np.nan)
                try:
                    pct, nulls = G.presence_percentiles(fr["image"], [body], range(len(names)), seed=k)
                except (ValueError, IndexError):
                    pct, nulls = np.full((1, len(names)), np.nan), 0
                if nulls:
                    for i, n in enumerate(names):
                        if np.isfinite(pct[0, i]):
                            by_landmark.setdefault(n.split("-")[0], []).append(float(pct[0, i]))
                    e, f = pct[0, edge], pct[0, interior]
                    person_edge.append(float(np.nanmean(e)) if np.isfinite(e).any() else float("nan"))
                    person_interior.append(float(np.nanmean(f)) if np.isfinite(f).any() else float("nan"))
            row = presence[k]
            ours_rows.append(row)
            ours_all.append(float(np.nanmean(row)) if np.isfinite(row).any() else float("nan"))
            ours_anchor.append(anchor[k])
            if k in (0, len(pair["frames"]) // 2) and len(tiles) < 12:
                tiles.append(annotation_tile(fr, seg, uv_person, ours, marks, sv, pair["levels"], f"{p['case']} {p['frame_ids'][k]} {fr['view']}"))
    report = {"bars": ANNOTATION_BARS, "presence_bars": PRESENCE_BARS, "near_px": NEAR_PX,
              "reprojection": reprojection_report(errors), "spine": spine_report(spine), "sacral": sacral_report(sacral, top_to_sacrum),
              "presence": {"person_outline_landmarks": G.presence_gate(person_edge, PRESENCE_BARS),
                           "person_head_centres": G.presence_gate(person_interior, PRESENCE_BARS),
                           "arm_landmarks_all_18": G.presence_gate(ours_all, PRESENCE_BARS),
                           "arm_sacral_anchor": G.presence_gate(ours_anchor, PRESENCE_BARS),
                           "by_person_landmark": {k: {"frames": len(v), "median": round(float(np.median(v)), 3),
                                                      "share_at_bar": round(float(np.mean(np.asarray(v) >= PRESENCE_BARS["frame_mean"])), 3)}
                                                  for k, v in sorted(by_landmark.items())},
                           "arm_by_landmark": arm_by_landmark(ours_rows)}}
    report["passes"] = {"reprojection": report["reprojection"]["pass"], "spine": report["spine"]["pass"],
                        "sacral": report["sacral"]["pass"], "person_landmarks_present": report["presence"]["person_outline_landmarks"]["pass"]}
    (shipped / "annotations.json").write_text(json.dumps(report, indent=1, default=float))
    if tiles:
        save_sheet(tiles, shipped / "annotations_sheet.png")
    print(json.dumps({"passes": report["passes"], "reprojection": report["reprojection"]["winner"],
                      "presence": {k: v.get("why") for k, v in report["presence"].items() if isinstance(v, dict) and "why" in v}},
                     indent=1, default=float))
    return report


def arm_by_landmark(rows):
    """Each of the arm's eighteen landmarks on the same frames: how many read it, its median percentile and the share
    at the presence bar, so a landmark the loop may choose can be set beside the person's."""
    rows = np.asarray(rows, float).reshape(-1, len(G.LANDMARKS))
    out = {}
    for j, name in enumerate(G.LANDMARKS):
        v = rows[:, j][np.isfinite(rows[:, j])]
        out[name] = {"frames": int(len(v)), "median": round(float(np.median(v)), 3) if len(v) else None,
                     "share_at_bar": round(float(np.mean(v >= PRESENCE_BARS["frame_mean"])), 3) if len(v) else None}
    return out


def reprojection_report(errors):
    """The reading with the smallest median and 90th percentile wins; it must hold the bars and stand clear of the
    next, as the export's convention test asked, or the shipped coordinates were not read the export's way."""
    rows = []
    for (order, turned), e in errors.items():
        e = np.asarray(e, float)
        rows.append({"order": order, "turned_with_image": turned, "points": int(len(e)),
                     "median_px": round(float(np.median(e)), 3) if len(e) else None,
                     "p90_px": round(float(np.percentile(e, 90)), 3) if len(e) else None,
                     "max_px": round(float(e.max()), 3) if len(e) else None})
    rows.sort(key=lambda r: (r["median_px"] if r["median_px"] is not None else 1e9, r["p90_px"] if r["p90_px"] is not None else 1e9))
    best = rows[0] if rows else {}
    nxt = rows[1] if len(rows) > 1 else {}
    held = bool(best.get("points")) and best["median_px"] <= ANNOTATION_BARS["reprojection_median_px"] \
        and best["p90_px"] <= ANNOTATION_BARS["reprojection_p90_px"]
    clear = not nxt.get("points") or (nxt["p90_px"] or 0) > 3 * max(best.get("p90_px") or 0, 0.5)
    export_way = best.get("order") == "column first" and best.get("turned_with_image") is True
    return {"pass": bool(held and clear and export_way), "winner": best, "readings": rows,
            "why": ("the export's reading wins and holds the bars" if held and clear and export_way else
                    "the shipped landmarks and the pair's pose disagree, or another reading of the coordinates wins")}


def spine_report(spine):
    def shares(cell):
        return {"near_spine": ratio(*cell["near_spine"]), "near_bone": ratio(*cell["near_bone"]),
                "points": cell["near_spine"][1]}
    total = shares(spine)
    near = total["near_spine"]
    return {"pass": near is not None and near >= ANNOTATION_BARS["on_spine"], **total,
            "by_level": {k: shares(v) for k, v in spine["by_level"].items()},
            "by_view": {k: shares(v) for k, v in spine["by_view"].items()}}


def sacral_report(sacral, top_to_sacrum):
    out = {name: {key: ratio(*cell) for key, cell in v.items()} | {"points": v["near_spine"][1]} for name, v in sacral.items()}
    held = [out[n]["near_spine"] for n in ("promontory", "s1_top_centre")]
    t = np.asarray([x for x in top_to_sacrum if np.isfinite(x)], float)
    out["s1_top_centre_to_upper_sacrum_px"] = {"frames": int(len(t)), "median": round(float(np.median(t)), 2) if len(t) else None,
                                               "p90": round(float(np.percentile(t, 90)), 2) if len(t) else None}
    out["pass"] = all(x is not None and x >= ANNOTATION_BARS["on_spine"] for x in held)
    return out


def annotation_tile(fr, seg, uv_person, uv_ours, marks, sacral, levels, title):
    """One frame: the shipped labels as outlines (vertebrae cyan, upper sacrum yellow, the rest grey), the shipped
    2-D landmarks as green crosses and the person's 3-D ones reprojected as white rings, which should sit on them,
    the arm's lumbar landmarks in their level's colour and its sacral points as yellow squares."""
    from PIL import Image, ImageDraw
    im = Image.fromarray((np.clip(fr["image"], 0, 1) * 255).astype(np.uint8)).convert("RGB")
    rgb = np.asarray(im).copy()
    for labs, col in (((1, 2, 5, 6), (150, 150, 150)), ((3,), (0, 220, 255)), ((4,), (255, 230, 0))):
        m = np.isin(seg, labs)
        edge = m & ~(np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1))
        rgb[edge] = col
    im = Image.fromarray(rgb)
    d = ImageDraw.Draw(im)
    for i, lv in enumerate(levels):
        col = LEVEL_COLOURS[i % len(LEVEL_COLOURS)]
        for u, v in marks[i]:
            if np.isfinite(u) and np.isfinite(v):
                d.ellipse([u - 3, v - 3, u + 3, v + 3], fill=col)
    for u, v in sacral:
        if np.isfinite(u) and np.isfinite(v):
            d.rectangle([u - 5, v - 5, u + 5, v + 5], outline=(255, 230, 0), width=2)
    for (u, v), (a, b) in zip(uv_person, uv_ours):
        if np.isfinite(u) and np.isfinite(v):
            d.line([u - 6, v, u + 6, v], fill=(0, 255, 0), width=2)
            d.line([u, v - 6, u, v + 6], fill=(0, 255, 0), width=2)
        if np.isfinite(a) and np.isfinite(b):
            d.ellipse([a - 7, b - 7, a + 7, b + 7], outline=(255, 255, 255), width=1)
    d.text((8, 8), title, fill=(255, 255, 0))
    return im.resize((384, 384))


def save_sheet(tiles, path, cols=4):
    from PIL import Image
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 384, rows * 384), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * 384, (i // cols) * 384))
    sheet.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("deepfluoro", "cobra", "cobra_varian"):
        d = sub.add_parser(name)
        d.add_argument("--data", required=True)
        d.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("--out", required=True)
    c.add_argument("--data")
    n = sub.add_parser("annotations")
    n.add_argument("--out", required=True)
    n.add_argument("--shipped", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "deepfluoro":
        build_deepfluoro(a.data, a.out)
    elif a.cmd == "cobra":
        build_cobra(a.data, a.out)
    elif a.cmd == "cobra_varian":
        build_cobra_varian(a.data, a.out)
    elif a.cmd == "annotations":
        annotations(a.out, a.shipped)
    else:
        check(a.out, a.data)


if __name__ == "__main__":
    main()
