#!/usr/bin/env python3
"""DeepFluoro's own annotations of the frames the QA loop's external arm reads, brought to the loop's canvas.

Greg, 2026-11-01: "the fluoro X-rays for deep fluoro comes with annotations and I think they should be used somehow".
DeepFluoro (Grupp 2020) ships, for every projection, fourteen pelvic landmarks that a person placed in the specimen's
CT (vol-landmarks) and the release projected through the ground-truth pose (gt-landmarks), and a 2-D label image
(gt-seg: 1 and 2 the hemipelves, 3 the lumbar vertebrae as one class, 4 the upper sacrum where no other bone overlies
it, 5 and 6 the femurs, 7 the lower sacrum, drawn as background), made by the dataset's authors from their own 3-D
labels. Nothing in this project made them, so they check the external arm apart from TotalSegmentator, SPINEPS and
this project's handling of the pose (tools/realx_pairs.py annotations).

This tool only reads the release's HDF5 file. h5py is not in the project's environments, so it runs under any Python
that has it with numpy (the grid's fluorogen environment) and writes plain npz files the check reads with numpy
alone. It opens only the specimens and frames the arm's manifest names, so the held-out specimen (18-1109) is never
read.

The coordinates follow the export's own convention (realxray_deepfluoro_export.py in spinesurg-ct-nnunet, settled by
its deepfluoro_convention.py to 0.00 px over 14 landmarks and 111 frames): a shipped 2-D landmark is the
full-resolution (column, row) of the stored image with pixel centres on integers; the export's working image is that
down 4 in edge coordinates, (u + 0.5) / 4, turned by 180 degrees where the frame's rot-180-for-up is set; the loop's
canvas is the working image brought to 512 (tools/realx_pairs.py frame_of, square frames only). The check reprojects
the person's 3-D landmarks through the loop's own P and sets them beside these, so a convention read wrong here
shows there as an error of many pixels.

    python tools/deepfluoro_shipped.py --h5 <ipcai_2020_full_res_data.h5> --manifest <realx/deepfluoro/manifest.json> --out <folder>
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np

SIZE = 512
# The fourteen are the femoral head centres and thirteen points on the pelvis's outline. A head's centre lies inside
# the bone, where an edge measure has nothing to find, so it is the control that is not an edge.
INTERIOR = ("FH",)


def to_loop(uv, rot, cols, rows, size=SIZE):
    """Full-resolution (column, row) pixel centres to the loop canvas's edge coordinates, turned with the image."""
    uv = np.asarray(uv, float)
    out = np.empty_like(uv)
    out[..., 0] = (uv[..., 0] + 0.5) * size / cols
    out[..., 1] = (uv[..., 1] + 0.5) * size / rows
    return size - out if rot else out


def seg_to_loop(seg, rot, size=SIZE):
    """The shipped label image on the loop canvas: turned with the image, then each canvas pixel takes the label most
    of the full-resolution pixels under it carry (DeepFluoro's 1536 detector is three of them a side)."""
    seg = np.asarray(seg)
    if rot:
        seg = seg[::-1, ::-1]
    rows, cols = seg.shape
    fr, fc = rows // size, cols // size
    if fr < 1 or fc < 1 or rows % size or cols % size:
        r = ((np.arange(size) + 0.5) * rows / size).astype(int)
        c = ((np.arange(size) + 0.5) * cols / size).astype(int)
        return seg[np.ix_(r, c)].astype(np.uint8)
    blocks = seg.reshape(size, fr, size, fc)
    labels = np.unique(seg)
    counts = np.stack([(blocks == lab).sum(axis=(1, 3)) for lab in labels])
    return labels[np.argmax(counts, axis=0)].astype(np.uint8)


def is_interior(name):
    return name.split("-")[0] in INTERIOR


def sha256_of(path, chunk=1 << 24):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                return h.hexdigest()
            h.update(block)


def specimen(f, case, frame_ids):
    """One specimen's shipped annotations for the named frames, in the loop's frame and pixels."""
    pp = f["proj-params"]
    rows, cols = int(np.array(pp["num-rows"])), int(np.array(pp["num-cols"]))
    g = f[case]
    names = sorted(g["vol-landmarks"].keys())
    lm3d = np.array([np.array(g["vol-landmarks"][k], np.float64).ravel()[:3] for k in names])
    raw, rots, segs = [], [], []
    for pid in frame_ids:
        n = g["projections"][pid]
        shipped = n["gt-landmarks"]
        raw.append([np.array(shipped[k], np.float64).ravel()[:2] if k in shipped else np.full(2, np.nan) for k in names])
        rot = int(np.array(n["rot-180-for-up"]))
        rots.append(rot)
        segs.append(seg_to_loop(np.array(n["gt-seg"]["pixels"], np.uint8), rot))
    raw, rots = np.asarray(raw, float), np.asarray(rots, int)
    return {"names": np.asarray(names, dtype=str), "lm3d": lm3d, "raw": raw, "rot": rots, "cols": cols, "rows": rows,
            "seg": np.asarray(segs, np.uint8), "frame_ids": np.asarray(frame_ids, dtype=str)}


def extract(h5, manifest_path, out):
    import h5py
    manifest = json.loads(Path(manifest_path).read_text())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {"h5": str(h5), "h5_sha256": sha256_of(h5), "manifest": str(manifest_path), "persons": {}}
    with h5py.File(h5, "r") as f:
        for p in manifest["persons"]:
            case = p["case"]
            got = specimen(f, case, p["frame_ids"])
            tmp = out / f"{case}.npz.tmp-{os.getpid()}"
            with open(tmp, "wb") as fh:
                np.savez(fh, **got)
            os.replace(tmp, out / f"{case}.npz")
            summary["persons"][case] = {"frames": len(p["frame_ids"]), "landmarks": len(got["names"]),
                                        "names": [str(x) for x in got["names"]], "rot_frames": int(got["rot"].sum()),
                                        "labels": sorted(int(x) for x in np.unique(got["seg"]))}
            print(f"{case}: {len(p['frame_ids'])} frames, {len(got['names'])} landmarks, {int(got['rot'].sum())} turned", flush=True)
    summary["held_out_never_read"] = [h["person"] for h in manifest.get("held_out", [])]
    (out / "shipped.json").write_text(json.dumps(summary, indent=1))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--h5", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    extract(a.h5, a.manifest, a.out)


if __name__ == "__main__":
    main()
