#!/usr/bin/env python3
"""The IPCAI 2025 Loop-X digital-twin cadaver (Killeen and others, arXiv 2412.08020; spine-datasets #170) read into
this project's terms: its four navigated cone-beam CTs stitched into one volume, and each X-ray's own projection
matrix carried into that volume's frame, then tested against the bone.

The set is one zip of 1,748 DICOM files from a medPhoton ImagingRing (Brainlab Loop-X): 84 X-rays (DX) and four
CBCTs of 416 slices each. The geometry is in the private group 30BB ("Navigation Registration 1.0"), read here and
nowhere documented by the authors, so every reading below was tested against the images (docs/research/
loopx-digital-twin.md says how):

- (30BB,2073), on an X-ray, 16 doubles: a 4 x 4 matrix whose rows 1, 2 and 4 are the projection from the device's
  DICOM frame (its origin the ring's isocentre) to millimetres on the image, from the image's first pixel.
- (30BB,2055), on an X-ray and on each CBCT, 16 doubles: a rigid 4 x 4 from the fixed patient array's frame to the
  image's navigation frame, which is the reconstruction's voxel frame in millimetres: its origin at the first voxel
  of instance 0 (the top slice) and its third axis running down the instances, against DICOM's z.
- (30BB,2088): the gantry tilt in degrees. The composed pose holds for untilted shots and does not for tilted ones.

    python tools/loopx_twin.py export --raw <folder of the DICOM files> --work <realxray_work/twin>   # pydicom
    python tools/loopx_twin.py pose --work <realxray_work/twin> --sheet <png>   # numpy, scipy, nibabel, Pillow

export writes each CBCT as int16 HU with its voxel-to-LPS affine and navigation, and each X-ray with a projection
and a navigation matrix as its pixels and both matrices (export.json names every file and every X-ray left out).
pose stitches the CBCTs into CT0's LPS frame (ct_stitched.nii.gz), checks the overlaps of neighbouring CBCTs, and
projects the stitched bone through every X-ray's composed pose, scoring it by edge NCC at the pose and by the best
of the image shifts within SHIFT_PX (pose.json); a frame's pose holds when its gantry is untilted, its NCC at the
pose is at least MIN_NCC and the shifted null's 95th percentile, and its best shift moves the bone by no more than
MAX_SHIFT_MM. Only counts, matrices and one contact sheet leave the grid.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

GROUP = 0x30BB
TAG_P, TAG_NAV, TAG_TILT, TAG_VIEW, TAG_SOURCE_DEG, TAG_DETECTOR_DEG = 0x2073, 0x2055, 0x2088, 0x2070, 0x2084, 0x2086
STEP_MM = 1.0           # the stitched grid
BONE_HU = 200.0
BIN = 4                 # X-ray pixels to one pixel of the pose check
SHIFT_PX = 24           # pose-check pixels searched each way for the null and the best shift
MIN_NCC = 0.1
MAX_SHIFT_MM = 5.0
MAX_TILT_DEG = 1.0


# ---- export (pydicom and numpy) --------------------------------------------------------------------------------

def tag_doubles(ds, element):
    """A private element of group 30BB as little-endian doubles, None where it is missing or holds none."""
    tag = (GROUP, element)
    if tag not in ds or ds[tag].value is None:
        return None
    raw = bytes(ds[tag].value)
    return np.frombuffer(raw, "<f8").copy() if raw and len(raw) % 8 == 0 else None


def tag_text(ds, element):
    tag = (GROUP, element)
    if tag not in ds or ds[tag].value is None:
        return None
    return bytes(ds[tag].value).decode("ascii", "replace").strip("\x00 ")


def export_ct(slices, path):
    """One CBCT as int16 HU in (slice, row, column) order, slices by rising z, with its affine and navigation."""
    slices.sort(key=lambda ds: float(ds.ImagePositionPatient[2]))
    first = slices[0]
    if [round(float(v), 4) for v in first.ImageOrientationPatient] != [1, 0, 0, 0, 1, 0]:
        raise ValueError("a CBCT that is not axial")
    row_mm, col_mm = (float(v) for v in first.PixelSpacing)
    z = [float(ds.ImagePositionPatient[2]) for ds in slices]
    dz = float(np.median(np.diff(z)))
    hu = np.stack([ds.pixel_array.astype(np.float32) * float(ds.RescaleSlope) + float(ds.RescaleIntercept) for ds in slices])
    hu = np.clip(np.round(hu), -1024, 32767).astype(np.int16)
    x0, y0, z0 = (float(v) for v in first.ImagePositionPatient)
    affine = np.array([[col_mm, 0, 0, x0], [0, row_mm, 0, y0], [0, 0, dz, z0], [0, 0, 0, 1.0]])
    nav = tag_doubles(first, TAG_NAV).reshape(4, 4)
    np.savez(path, hu=hu, affine=affine, nav=nav)
    return {"slices": len(slices), "shape_srk": list(hu.shape), "spacing_mm": [col_mm, row_mm, dz], "time": str(first.AcquisitionTime),
            "series": str(first.SeriesInstanceUID), "nav": nav.tolist()}


def export_xray(ds, path):
    """One X-ray's header and, where it carries both matrices, its pixels and matrices; else why not."""
    head = {"sop": str(ds.SOPInstanceUID), "time": str(ds.AcquisitionTime), "description": str(ds.SeriesDescription),
            "rows": int(ds.Rows), "columns": int(ds.Columns), "pixel_spacing": [float(v) for v in ds.ImagerPixelSpacing],
            "view": tag_text(ds, TAG_VIEW), "source_deg": tag_text(ds, TAG_SOURCE_DEG), "detector_deg": tag_text(ds, TAG_DETECTOR_DEG),
            "tilt_deg": tag_text(ds, TAG_TILT), "shutter": [int(v) for v in ds.get("VerticesOfThePolygonalShutter", [])]}
    P, nav = tag_doubles(ds, TAG_P), tag_doubles(ds, TAG_NAV)
    if P is None or len(P) != 16:
        return head, "no projection matrix (30BB,2073)"
    if nav is None or len(nav) != 16:
        return head, "no navigation matrix (30BB,2055): not registered to the patient array"
    P4 = P.reshape(4, 4)
    np.savez(path, pixels=ds.pixel_array.astype(np.uint16), P=P4[[0, 1, 3]], nav=nav.reshape(4, 4))
    head.update({"P": P4[[0, 1, 3]].tolist(), "nav": nav.reshape(4, 4).tolist()})
    return head, None


def export(raw, work):
    import pydicom
    work = Path(work)
    (work / "ct").mkdir(parents=True, exist_ok=True)
    (work / "xray").mkdir(parents=True, exist_ok=True)
    cts, xrays, seen = {}, [], {}
    for path in sorted(Path(raw).glob("*.dcm")):
        ds = pydicom.dcmread(str(path), force=True)
        if ds.Modality == "CT":
            cts.setdefault(str(ds.SeriesInstanceUID), []).append(ds)
            continue
        name = f"x{len(xrays):03d}"
        digest = hashlib.sha256(ds.PixelData).hexdigest()
        if digest in seen:
            xrays.append({"name": name, "file": path.name, "left_out": f"the same pixels as {seen[digest]}"})
            continue
        seen[digest] = name
        head, why = export_xray(ds, work / "xray" / f"{name}.npz")
        head.update({"name": name, "file": path.name})
        if why:
            head["left_out"] = why
        xrays.append(head)
    order = sorted(cts, key=lambda uid: str(cts[uid][0].AcquisitionTime))
    ct_meta = [dict(export_ct(cts[uid], work / "ct" / f"ct{k}.npz"), name=f"ct{k}") for k, uid in enumerate(order)]
    (work / "export.json").write_text(json.dumps({"cts": ct_meta, "xrays": xrays}, indent=1))
    kept = sum("left_out" not in x for x in xrays)
    print(f"{len(ct_meta)} CBCTs, {len(xrays)} X-ray files, {kept} with both matrices", flush=True)


# ---- frames and poses (numpy) ----------------------------------------------------------------------------------

def nav_frame(affine, n_slices):
    """DICOM LPS to the navigation frame: the voxel frame in millimetres from the first voxel of the top slice
    (instance 0), its third axis against z. Read from the stitch (the CBCTs step along it the way the anatomy runs
    only with z reversed) and from the untilted X-rays (the other signs and origins score lower)."""
    x0, y0 = affine[0, 3], affine[1, 3]
    z_top = affine[2, 3] + (n_slices - 1) * affine[2, 2]
    return np.array([[1.0, 0, 0, -x0], [0, 1.0, 0, -y0], [0, 0, -1.0, z_top], [0, 0, 0, 1.0]])


def dicom_nav(nav, frame):
    """A navigation matrix taken to DICOM LPS: the patient array's frame to the image's LPS."""
    return np.linalg.inv(frame) @ np.asarray(nav, float)


def to_world(nav_k, nav_0):
    """CBCT k's LPS to the world, CT0's LPS, both navigations in DICOM terms (dicom_nav)."""
    return nav_0 @ np.linalg.inv(nav_k)


def world_P(P_mm, nav_x, nav_0, spacing):
    """An X-ray's projection from the world to its own pixels in edge coordinates: the device's projection in
    millimetres over the world-to-device motion its navigation gives (nav_x, nav_0 in DICOM terms)."""
    S = np.diag([1.0 / spacing[1], 1.0 / spacing[0], 1.0])
    return S @ np.asarray(P_mm, float) @ np.asarray(nav_x, float) @ np.linalg.inv(nav_0)


def untilted(head):
    try:
        return abs(float(head.get("tilt_deg"))) <= MAX_TILT_DEG
    except (TypeError, ValueError):
        return False


def load_cts(work):
    meta = json.loads((Path(work) / "export.json").read_text())
    cts = []
    for m in meta["cts"]:
        z = np.load(Path(work) / "ct" / f"{m['name']}.npz")
        frame = nav_frame(z["affine"], z["hu"].shape[0])
        cts.append({"name": m["name"], "hu": z["hu"], "affine": z["affine"], "nav": dicom_nav(z["nav"], frame), "frame": frame})
    return meta, cts


def box_in_world(ct, nav_0):
    s, r, c = ct["hu"].shape
    idx = np.array([[i, j, k, 1.0] for i in (0, c - 1) for j in (0, r - 1) for k in (0, s - 1)])
    return idx @ ct["affine"].T @ to_world(ct["nav"], nav_0).T


def resample(ct, nav_0, xs, ys, zs):
    """CBCT k's HU at world points, -1024 outside it."""
    from scipy import ndimage
    pts = np.stack([xs.ravel(), ys.ravel(), zs.ravel(), np.ones(xs.size)])
    ijk = np.linalg.inv(ct["affine"]) @ np.linalg.inv(to_world(ct["nav"], nav_0)) @ pts
    return ndimage.map_coordinates(ct["hu"], [ijk[2], ijk[1], ijk[0]], order=1, cval=-1024).reshape(xs.shape)


def stitch(cts):
    """The CBCTs on one STEP_MM grid of the world, each world slice taken from the CBCT whose centre is nearest."""
    nav_0 = cts[0]["nav"]
    boxes = [box_in_world(ct, nav_0) for ct in cts]
    lo = np.floor(np.min([b.min(axis=0) for b in boxes], axis=0)[:3])
    hi = np.ceil(np.max([b.max(axis=0) for b in boxes], axis=0)[:3])
    shape = tuple(int((hi[a] - lo[a]) / STEP_MM) + 1 for a in (2, 1, 0))
    centres = np.array([b.mean(axis=0)[2] for b in boxes])
    ys, xs = np.meshgrid(lo[1] + np.arange(shape[1]) * STEP_MM, lo[0] + np.arange(shape[2]) * STEP_MM, indexing="ij")
    out = np.full(shape, -1024, np.int16)
    for zi in range(shape[0]):
        z = lo[2] + zi * STEP_MM
        k = int(np.argmin(np.abs(centres - z)))
        out[zi] = resample(cts[k], nav_0, xs, ys, np.full(xs.shape, z)).astype(np.int16)
    affine = np.diag([STEP_MM, STEP_MM, STEP_MM, 1.0])
    affine[:3, 3] = lo
    return out, affine


def ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a * a).sum() * (b * b).sum())) if a.size else 0.0
    return float((a * b).sum() / d) if d > 0 else float("nan")


def overlaps(cts, margin=5):
    """Each pair of neighbouring CBCTs on one 1 mm grid where both reach, 160 mm about the midline: the NCC of
    their HU (clipped to -200..1500) at the navigation's alignment and the best shift within margin mm."""
    nav_0 = cts[0]["nav"]
    boxes = [box_in_world(ct, nav_0) for ct in cts]
    order = list(np.argsort([b.mean(axis=0)[2] for b in boxes]))
    out = []
    for a, b in zip(order, order[1:]):
        lo = np.maximum(boxes[a].min(axis=0), boxes[b].min(axis=0))[:3]
        hi = np.minimum(boxes[a].max(axis=0), boxes[b].max(axis=0))[:3]
        xc = (lo[0] + hi[0]) / 2
        zz, yy, xx = np.meshgrid(np.arange(lo[2] + 5, hi[2] - 5), np.arange(lo[1] + 20, hi[1] - 20), np.arange(xc - 80, xc + 80), indexing="ij")
        va, vb = (np.clip(resample(cts[k], nav_0, xx, yy, zz).astype(np.float32), -200, 1500) for k in (a, b))
        m = margin
        core = va[m:-m, m:-m, m:-m]
        scores = {}
        for dz in range(-m, m + 1):
            for dy in range(-m, m + 1):
                for dx in range(-m, m + 1):
                    scores[(dx, dy, dz)] = ncc(core, vb[m + dz:vb.shape[0] - m + dz, m + dy:vb.shape[1] - m + dy, m + dx:vb.shape[2] - m + dx])
        best = max(scores, key=scores.get)
        out.append({"cbcts": [cts[a]["name"], cts[b]["name"]], "overlap_mm": round(float(hi[2] - lo[2]), 1),
                    "ncc_at_navigation": round(scores[(0, 0, 0)], 3), "best_ncc": round(scores[best], 3), "best_shift_mm_xyz": list(best)})
    return out


# ---- the pose check (numpy and scipy) --------------------------------------------------------------------------

def bone_points(vol, affine):
    """Every voxel over BONE_HU as a world point, weighted by its HU above it (capped)."""
    idx = np.argwhere(vol > BONE_HU)
    weights = np.minimum(vol[vol > BONE_HU].astype(np.float64) - BONE_HU, 1800.0)
    return idx[:, ::-1] * STEP_MM + affine[:3, 3], weights


def splat(points, weights, P, shape):
    """The bone's line integrals, roughly: each point's weight in the binned pixel its projection falls in, blurred."""
    from scipy import ndimage
    h = points @ P[:, :3].T + P[:, 3]
    ok = h[:, 2] > 0
    u, v = h[ok, 0] / h[ok, 2] / BIN, h[ok, 1] / h[ok, 2] / BIN
    inside = (u >= 0) & (u < shape[1]) & (v >= 0) & (v < shape[0])
    flat = v[inside].astype(int) * shape[1] + u[inside].astype(int)
    img = np.bincount(flat, weights=weights[ok][inside], minlength=shape[0] * shape[1]).reshape(shape)
    return ndimage.gaussian_filter(img, 1.0)


def attenuation(pixels, mask=None):
    """-log of the linear intensity over its bright end (the 99.9th percentile within the mask)."""
    I = np.maximum(np.asarray(pixels, np.float64), 1.0)
    I0 = np.percentile(I[mask] if mask is not None and mask.any() else I, 99.9)
    return -np.log(np.minimum(I / I0, 1.0))


def binned(img, f=BIN):
    h, w = (img.shape[0] // f) * f, (img.shape[1] // f) * f
    return img[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3))


def shutter_mask(vertices, shape, scale=1.0):
    """The polygonal shutter (DICOM's vertices, column then row) as a mask at the given scale of the image."""
    from PIL import Image, ImageDraw
    if len(vertices) < 6:
        return np.ones(shape, bool)
    m = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(m).polygon([(vertices[i] * scale, vertices[i + 1] * scale) for i in range(0, len(vertices), 2)], fill=1)
    return np.asarray(m, bool)


def shift_scores(real_e, drr_e, region):
    """Edge NCC within the region with the DRR's edges shifted by every whole binned pixel within SHIFT_PX."""
    pad = np.pad(drr_e, SHIFT_PX)
    h, w = real_e.shape
    a = real_e[region]
    grid = np.full((2 * SHIFT_PX + 1, 2 * SHIFT_PX + 1), np.nan)
    for dy in range(-SHIFT_PX, SHIFT_PX + 1):
        for dx in range(-SHIFT_PX, SHIFT_PX + 1):
            grid[dy + SHIFT_PX, dx + SHIFT_PX] = ncc(a, pad[SHIFT_PX - dy:SHIFT_PX - dy + h, SHIFT_PX - dx:SHIFT_PX - dx + w][region])
    return grid


def score_frame(head, pixels, P, points, weights, depth_mm):
    """A frame's pose scored: edge NCC at the pose, the shifted null, the best shift in millimetres at the bone."""
    from scipy import ndimage
    shutter = shutter_mask(head.get("shutter") or [], (pixels.shape[0] // BIN, pixels.shape[1] // BIN), 1.0 / BIN)
    shutter = ndimage.binary_erosion(shutter, iterations=4)          # the shutter's own edge is no bone's
    real = binned(attenuation(pixels, shutter_mask(head.get("shutter") or [], pixels.shape)))
    if min(real.shape) < 2 * SHIFT_PX:
        return {"scored": False, "why": f"too small to score ({pixels.shape[1]} x {pixels.shape[0]} pixels)"}, real, None
    drr = splat(points, weights, P, real.shape)
    region = shutter[:real.shape[0], :real.shape[1]] & ndimage.binary_dilation(drr > 0.05 * max(drr.max(), 1e-12), iterations=6)
    if region.sum() < 200:
        return {"scored": False, "why": "the bone projects outside the frame"}, real, drr
    grid = shift_scores(ndimage.gaussian_gradient_magnitude(real, 1.0), ndimage.gaussian_gradient_magnitude(drr, 1.0), region)
    if not np.isfinite(grid).any():
        return {"scored": False, "why": "no edge in the region"}, real, drr
    iy, ix = np.unravel_index(np.nanargmax(grid), grid.shape)
    far = np.add.outer((np.arange(grid.shape[0]) - SHIFT_PX) ** 2, (np.arange(grid.shape[1]) - SHIFT_PX) ** 2) >= 12 ** 2
    shift_px = [int((ix - SHIFT_PX) * BIN), int((iy - SHIFT_PX) * BIN)]
    focal_px = focal_of(P)
    return {"scored": True, "ncc_at_pose": round(float(grid[SHIFT_PX, SHIFT_PX]), 4), "best_ncc": round(float(np.nanmax(grid)), 4),
            "best_shift_px": shift_px, "best_shift_mm_at_bone": round(float(np.hypot(*shift_px) * depth_mm / focal_px), 2),
            "null_median": round(float(np.nanmedian(grid[far])), 4), "null_p95": round(float(np.nanpercentile(grid[far], 95)), 4)}, real, drr


def focal_of(P):
    """The focal length in pixels, from the RQ decomposition of P's left 3 x 3."""
    from scipy.linalg import rq
    K, _ = rq(np.asarray(P, float)[:, :3])
    K = K @ np.diag(np.sign(np.diag(K)))
    return float((K[0, 0] + K[1, 1]) / 2 / K[2, 2])


def verdict(head, row):
    """Why a frame's pose is not taken, or None where it holds."""
    if not untilted(head):
        return f"gantry tilted {head.get('tilt_deg')} degrees (30BB,2088): the composed pose does not hold under tilt"
    if not row.get("scored"):
        return row.get("why", "not scored")
    if row["ncc_at_pose"] < max(MIN_NCC, row["null_p95"]):
        return f"edge NCC at the pose {row['ncc_at_pose']} below {MIN_NCC} or the shifted null's 95th percentile {row['null_p95']}"
    if row["best_shift_mm_at_bone"] > MAX_SHIFT_MM:
        return f"the best shift moves the bone {row['best_shift_mm_at_bone']} mm, over {MAX_SHIFT_MM}"
    return None


def pose(work, sheet=None):
    import nibabel as nib
    work = Path(work)
    meta, cts = load_cts(work)
    vol, affine = stitch(cts)
    nib.save(nib.Nifti1Image(vol.transpose(2, 1, 0), np.diag([-1.0, -1.0, 1.0, 1.0]) @ affine), str(work / "ct_stitched.nii.gz"))
    report = {"stitched_shape_zyx": list(vol.shape), "affine_lps": affine.tolist(), "overlaps": overlaps(cts), "frames": {}}
    print(json.dumps(report["overlaps"]), flush=True)
    points, weights = bone_points(vol, affine)
    centre = np.append(points.mean(axis=0), 1.0)
    tiles = []
    for head in meta["xrays"]:
        if "left_out" in head:
            report["frames"][head["name"]] = {"held": False, "why": head["left_out"]}
            continue
        z = np.load(work / "xray" / f"{head['name']}.npz")
        nav_x = dicom_nav(z["nav"], cts[0]["frame"])
        P = world_P(z["P"], nav_x, cts[0]["nav"], head["pixel_spacing"])
        depth = float((np.asarray(z["P"]) @ nav_x @ np.linalg.inv(cts[0]["nav"]) @ centre)[2])
        row, real, drr = score_frame(head, z["pixels"], P, points, weights, depth)
        why = verdict(head, row)
        report["frames"][head["name"]] = dict(row, held=why is None, why=why, tilt_deg=head.get("tilt_deg"), source_deg=head.get("source_deg"),
                                             time=head.get("time"), size=[head["columns"], head["rows"]])
        print(head["name"], json.dumps(report["frames"][head["name"]]), flush=True)
        if drr is not None:
            tiles.append((head["name"], real, drr, row, why is None))
    (work / "pose.json").write_text(json.dumps(report, indent=1))
    if sheet:
        contact_sheet(tiles, sheet)
    held = [k for k, v in report["frames"].items() if v["held"]]
    print(f"{len(held)} of {len(report['frames'])} X-ray files hold: {held}", flush=True)
    return report


def spread(items, n):
    """n of the items evenly spaced through them, all where there are no more."""
    if len(items) <= n:
        return list(items)
    return [items[int(i)] for i in np.linspace(0, len(items) - 1, n).round()]


def contact_sheet(tiles, path, n=12, side=224):
    """Twelve frames, half that hold and half that do not, each spread through the study, with the DRR's strongest
    bone edges in red over the real image; a 64-colour palette keeps it under 300 kB."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    pick = spread([t for t in tiles if t[4]], n // 2) + spread([t for t in tiles if not t[4]], n // 2)
    sheet = Image.new("RGB", (4 * side, ((len(pick) + 3) // 4) * side), "black")
    for i, (name, real, drr, row, ok) in enumerate(pick):
        lo, hi = np.percentile(real, [1, 99])
        g = np.clip((real - lo) / max(hi - lo, 1e-6), 0, 1)
        rgb = np.stack([g, g, g], axis=-1)
        e = ndimage.gaussian_gradient_magnitude(drr, 1.0)
        if (e > 0).any():
            edge = e > np.percentile(e[e > 0], 80)
            rgb[edge] = 0.35 * rgb[edge] + 0.65 * np.array([1.0, 0.2, 0.1])
        im = Image.fromarray((rgb * 255).astype(np.uint8))
        s = side / max(im.size)
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.BILINEAR)
        tile = Image.new("RGB", (side, side), "black")
        tile.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
        label = f"{name} {'holds' if ok else 'not held'} ncc {row.get('ncc_at_pose', float('nan')):.2f}"
        ImageDraw.Draw(tile).text((4, 4), label, fill=(255, 255, 0))
        sheet.paste(tile, ((i % 4) * side, (i // 4) * side))
    sheet.convert("P", palette=Image.ADAPTIVE, colors=64).save(path, optimize=True)


LEVEL_ORDER = [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)] + ["S1", "sacrum"]
SEEN_SHARE = 0.5        # a level is seen where at least this share of its voxels projects inside the shutter


def level_voxels(ts, most=4000):
    """{level: up to most of its voxels in LPS} of TotalSegmentator's per-structure files in ts."""
    import nibabel as nib
    rng = np.random.default_rng(0)
    out = {}
    for level in LEVEL_ORDER:
        path = Path(ts) / (f"{level}.nii.gz" if level == "sacrum" else f"vertebrae_{level}.nii.gz")
        if not path.is_file():
            continue
        img = nib.load(str(path))
        idx = np.argwhere(np.asarray(img.dataobj) > 0)
        if len(idx) < 200:
            continue
        idx = idx[rng.choice(len(idx), min(most, len(idx)), replace=False)]
        out[level] = (idx @ img.affine[:3, :3].T + img.affine[:3, 3]) * np.array([-1.0, -1.0, 1.0])
    return out


def rib_reading(work, gap=5, reach=40):
    """A second reading of the column's names that owes nothing to TotalSegmentator's: the bone (over BONE_HU) in
    two boxes beside each level it drew, gap to gap + reach mm past the level's own lateral extent (its transverse
    processes), over the level's height and depth, other levels' voxels aside. A rib crosses the box of every
    thoracic level; a lumbar level's boxes hold soft tissue, or the iliac crest low down."""
    import nibabel as nib
    work = Path(work)
    vol = np.asarray(nib.load(str(work / "ct_stitched.nii.gz")).dataobj)          # (x, y, z), 1 mm
    masks = {}
    for level in LEVEL_ORDER[:-2]:
        path = work / "ts" / f"vertebrae_{level}.nii.gz"
        if path.is_file():
            m = np.asarray(nib.load(str(path)).dataobj) > 0
            if m.shape == vol.shape and m.sum() >= 200:
                masks[level] = m
    anyone = np.any(list(masks.values()), axis=0) if masks else np.zeros(vol.shape, bool)
    out = {}
    for level, m in masks.items():
        idx = np.argwhere(m)
        (x0, y0, z0), (x1, y1, z1) = idx.min(axis=0), idx.max(axis=0)
        sides = []
        for a, b in ((x0 - gap - reach, x0 - gap), (x1 + gap, x1 + gap + reach)):
            a, b = max(int(a), 0), min(int(b), vol.shape[0])
            box = vol[a:b, y0:y1 + 1, z0:z1 + 1] > BONE_HU
            sides.append(int((box & ~anyone[a:b, y0:y1 + 1, z0:z1 + 1]).sum()))
        out[level] = {"bone_voxels_beside": sides}
    return out


def levels_seen(work):
    """For every X-ray with both matrices: the levels whose voxels mostly project inside its shutter."""
    work = Path(work)
    meta, cts = load_cts(work)
    report = json.loads((work / "pose.json").read_text())
    voxels = level_voxels(work / "ts")
    seen = {}
    for head in meta["xrays"]:
        if "left_out" in head:
            continue
        z = np.load(work / "xray" / f"{head['name']}.npz")
        P = world_P(z["P"], dicom_nav(z["nav"], cts[0]["frame"]), cts[0]["nav"], head["pixel_spacing"])
        mask = shutter_mask(head.get("shutter") or [], (head["rows"], head["columns"]))
        names = []
        for level, pts in voxels.items():
            h = pts @ P[:, :3].T + P[:, 3]
            u, v = h[:, 0] / h[:, 2], h[:, 1] / h[:, 2]
            ok = (h[:, 2] > 0) & (u >= 0) & (u < head["columns"]) & (v >= 0) & (v < head["rows"])
            inside = np.zeros(len(u), bool)
            inside[ok] = mask[v[ok].astype(int), u[ok].astype(int)]
            if inside.mean() >= SEEN_SHARE:
                names.append(level)
        frame = report["frames"].get(head["name"], {})
        seen[head["name"]] = {"levels": names, "held": bool(frame.get("held")), "source_deg": head.get("source_deg"), "tilt_deg": head.get("tilt_deg")}
    out = {"segmented": list(voxels), "rib_reading": rib_reading(work), "frames": seen}
    print("bone beside each level (left, right voxels):", json.dumps({k: v["bone_voxels_beside"] for k, v in out["rib_reading"].items()}), flush=True)
    (work / "levels.json").write_text(json.dumps(out, indent=1))
    held = [f for f in seen.values() if f["held"]]
    counts = {lv: sum(lv in f["levels"] for f in held) for lv in voxels}
    print(f"levels segmented: {list(voxels)}; held frames showing each: {counts}", flush=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--raw", required=True)
    e.add_argument("--work", required=True)
    p = sub.add_parser("pose")
    p.add_argument("--work", required=True)
    p.add_argument("--sheet")
    v = sub.add_parser("levels", help="the levels each X-ray shows, once TotalSegmentator's masks are in <work>/ts")
    v.add_argument("--work", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "export":
        export(a.raw, a.work)
    elif a.cmd == "pose":
        pose(a.work, a.sheet)
    else:
        levels_seen(a.work)


if __name__ == "__main__":
    sys.exit(main())
