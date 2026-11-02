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
    python tools/realx_pairs.py check --out <folder>        # overlays and the box agreement, on the grid
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


def build(source, export, cases, out):
    """The pairs of one source. cases: (case, person, levels, TotalSegmentator folder, held-out reason or None,
    left-out reason or None), in order; a held-out or left-out case is named in the manifest and never read."""
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
            labels, affine = ts_labels(Path(ts))
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


def build_cobra(data, out, export_name="cobra_elekta_v3"):
    """COBRA2026's Elekta export (realxray_cobra_export v2, 24 frames a case, the CT-to-projection axis map confirmed
    by edge NCC case by case): the export's test cases (md5 of the case mod 10 is 8 or 9) are held out; a case whose
    column the transitional screen (cobra2026/lstv) does not call ordinary, L1 to L5 above the sacrum, is left out,
    since the real arm names the typical column."""
    data = Path(data)
    export = data / "realxray" / export_name
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
        ts = data / "cobra2026" / "seg" / case / "ts"
        cases.append((case, f"cobra2026:{case}", cobra_levels(rec), ts, held, left))
    return build("cobra2026", export, cases, out)


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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("deepfluoro", "cobra"):
        d = sub.add_parser(name)
        d.add_argument("--data", required=True)
        d.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("--out", required=True)
    c.add_argument("--data")
    a = ap.parse_args(argv)
    if a.cmd == "deepfluoro":
        build_deepfluoro(a.data, a.out)
    elif a.cmd == "cobra":
        build_cobra(a.data, a.out)
    else:
        check(a.out, a.data)


if __name__ == "__main__":
    main()
