"""Run SPINEPS's CT models on CPU over one CT of a job list, into its own folder.

    run_spineps.py JOBS.json OUT ID [THREADS]

Each job is {"id", "ct", "release"}: the CT and its release mask (a file, or a folder of one mask per
level). SPINEPS's VIBESeg step, which finds the spine before the semantic model, holds a 73-class
prediction of the whole field in memory, and on a 37 x 37 x 42 cm field it took 12 GB and was killed.
So the CT is cut first to the box the release's own levels occupy, widened by MARGIN_MM in the plane
and HEAD_FOOT_MARGIN_MM along the head-foot axis (beyond the release's head-most and foot-most
levels, where C2 and the sacrum lie when the release does not draw them), and clipped to the field.

OUT/<id>/sub-<id>_ct.nii.gz is SPINEPS's input: the cut CT as published, where SPINEPS takes its grid,
else the cut CT resampled to 1 mm isotropic with cubic interpolation, since SPINEPS's CT model refuses
a scan whose slices are thicker than its pixels. OUT/<id>/ctgrid/ holds SPINEPS's vertebra and
subregion masks on the whole CT's grid: placed back by the cut's offset where the CT went in as it is,
resampled back nearest-neighbour otherwise; input.json says how.

A CT whose masks are on its grid already is skipped. Run one CT a process, so a CT killed for memory
loses only itself. The instance model runs one cutout at a time: four at a time took 13.8 GB.

From verse766 on, SPINEPS's spine-finding step (VIBESeg, which SPINEPS runs only to cut its input to
the spine) runs first in a process of its own, tools/vibeseg_alone.py, which writes its mask where
SPINEPS looks and SPINEPS then reuses it; and that process keeps one of VIBESeg's three folds' logits
in memory at a time (tools/fold_patch.py, the running sum on disk). In SPINEPS's own process the step
sat beside the three SPINEPS models already loaded, about 9 GB before its first tile, and verse108,
verse649 and verse766 passed the container's 14.3 GB inside it. The mask is SPINEPS's own bit for bit:
on verse255, run both ways, no voxel of 38,398,530 differed, at a peak of 9.8 GB alone. input.json
says which CTs ran this way."""
import json
import os
import resource
import shutil
import subprocess
import sys
import time
import traceback

import nibabel as nib
import numpy as np
import torch

ISO_MM = 1.0
MARGIN_MM = 60.0
HEAD_FOOT_MARGIN_MM = 200.0
SLAB = 64
FOLD_PATCH = ("VIBESeg run alone first by tools/vibeseg_alone.py with tools/fold_patch.py: its folds "
              "summed from disk, one in memory at a time; SPINEPS reused its mask")
REUSED = ("a spine-finding mask an earlier run left was reused; which process made it is not recorded")


def release_box(release):
    """(lower, upper) voxel indices of every voxel the release's masks label, on the CT's grid."""
    paths = ([os.path.join(release, f) for f in sorted(os.listdir(release))
              if f.startswith("vertebrae_") or f == "sacrum.nii.gz"] if os.path.isdir(release) else [release])
    low, high = None, None
    for path in paths:
        img = nib.load(path)
        depth = img.shape[2]
        for k in range(0, depth, SLAB):   # a slab at a time: VerSe's largest mask is 4 GB as float64
            data = np.asanyarray(img.dataobj[:, :, k:k + SLAB])
            if data.ndim > 3:
                data = data.reshape(data.shape[:3])
            where = np.argwhere(np.rint(data) != 0) if data.dtype.kind == "f" else np.argwhere(data != 0)
            if not len(where):
                continue
            where[:, 2] += k
            a, b = where.min(0), where.max(0)
            low = a if low is None else np.minimum(low, a)
            high = b if high is None else np.maximum(high, b)
    return low, high


def crop_box(ct, release):
    low, high = release_box(release)
    zooms = np.array(ct.header.get_zooms()[:3], float)
    axis = int(np.argmax(np.abs(ct.affine[2, :3])))
    margin = np.full(3, MARGIN_MM)
    margin[axis] = HEAD_FOOT_MARGIN_MM
    pad = np.ceil(margin / zooms).astype(int)
    shape = np.array(ct.shape[:3])
    start = np.maximum(low - pad, 0)
    stop = np.minimum(high + pad + 1, shape)
    return [int(v) for v in start], [int(v) for v in stop]


def cut_ct(ct_path, release, target):
    """The CT cut to the release's box, written to target; returns the box."""
    ct = nib.load(ct_path)
    start, stop = crop_box(ct, release)
    cut = ct.slicer[start[0]:stop[0], start[1]:stop[1], start[2]:stop[2]]
    data = np.asanyarray(cut.dataobj)
    out = nib.Nifti1Image(data, cut.affine, cut.header)
    nib.save(out, target + ".tmp.nii.gz")
    os.replace(target + ".tmp.nii.gz", target)
    return {"start": start, "stop": stop, "shape": [int(n) for n in ct.shape[:3]],
            "margin_mm": MARGIN_MM, "head_foot_margin_mm": HEAD_FOOT_MARGIN_MM}


def prepare_input(folder, sid, ct_path, release):
    """SPINEPS's input in folder: the cut CT as it is, or resampled to 1 mm; returns (how, box)."""
    from TPTBox import NII
    link = os.path.join(folder, f"sub-{sid}_ct.nii.gz")
    cut = os.path.join(folder, "cut_ct.nii.gz")
    box_file = os.path.join(folder, "cut_box.json")
    if not os.path.exists(box_file):
        box = cut_ct(ct_path, release, cut)
        json.dump(box, open(box_file, "w"))
    box = json.load(open(box_file))
    nii = NII.load(cut, seg=False)
    if nii.get_plane() == "iso":
        if not os.path.exists(link):
            shutil.copyfile(cut, link + ".tmp.nii.gz")
            os.replace(link + ".tmp.nii.gz", link)
        return "as_is", box
    if not os.path.exists(link):
        iso = nii.rescale((ISO_MM, ISO_MM, ISO_MM), order=3, verbose=False)
        iso.save(link + ".tmp.nii.gz", verbose=False)
        os.replace(link + ".tmp.nii.gz", link)
    return "resampled_1mm_iso_cubic", box


def derivative(folder, sid, kind):
    return os.path.join(folder, "derivatives_seg", f"sub-{sid}_mod-ct_seg-{kind}_msk.nii.gz")


def placed_back(source, ct, box):
    """A mask on the cut grid, as it is, placed into the whole CT's grid by the cut's offset."""
    mask = nib.load(source)
    cut_affine = ct.slicer[box["start"][0]:box["stop"][0], box["start"][1]:box["stop"][1],
                           box["start"][2]:box["stop"][2]].affine
    if mask.shape[:3] != tuple(b - a for a, b in zip(box["start"], box["stop"])) or not np.allclose(mask.affine, cut_affine, atol=1e-3):
        raise ValueError("SPINEPS's mask is not on the cut CT's grid")
    whole = np.zeros(ct.shape[:3], np.uint16)
    s, e = box["start"], box["stop"]
    whole[s[0]:e[0], s[1]:e[1], s[2]:e[2]] = np.asanyarray(mask.dataobj).astype(np.uint16)
    return nib.Nifti1Image(whole, ct.affine)


def resampled_back(source, ct_path):
    from TPTBox import NII
    ct = NII.load(ct_path, seg=False)
    mask = NII.load(source, seg=True).resample_from_to(ct, order=0, verbose=False)
    mask.set_dtype_(np.uint16)
    return mask


def to_ct_grid(folder, sid, ct_path, how, box):
    out = os.path.join(folder, "ctgrid")
    os.makedirs(out, exist_ok=True)
    ct = nib.load(ct_path)
    for kind, name in (("vert", "vert.nii.gz"), ("spine", "spine.nii.gz")):
        target = os.path.join(out, name)
        if os.path.exists(target):
            continue
        source = derivative(folder, sid, kind)
        if how == "as_is":
            nib.save(placed_back(source, ct, box), target + ".tmp.nii.gz")
        else:
            resampled_back(source, ct_path).save(target + ".tmp.nii.gz", verbose=False)
        os.replace(target + ".tmp.nii.gz", target)
    json.dump({"input": how, "iso_mm": ISO_MM if how != "as_is" else None, "cut": box,
               "fold_patch": spine_finding_record(folder, sid)},
              open(os.path.join(out, "input.json"), "w"))


def spine_finding_alone(folder, sid, threads):
    """VIBESeg's mask for SPINEPS's input, made in a child process unless it is there already."""
    target = derivative(folder, sid, "VIBESeg-100")
    if os.path.exists(target):
        return
    os.makedirs(os.path.dirname(target), exist_ok=True)
    here = os.path.dirname(os.path.abspath(__file__))
    done = subprocess.run([sys.executable, "-W", "ignore", os.path.join(here, "vibeseg_alone.py"),
                           os.path.join(folder, f"sub-{sid}_ct.nii.gz"), target, "patched", str(threads)])
    if done.returncode != 0 or not os.path.exists(target):
        raise RuntimeError("the spine-finding step's own process ended with %s" % done.returncode)
    with open(os.path.join(folder, "vibeseg_alone.done"), "w") as f:   # beside SPINEPS's folder, not in it
        f.write(FOLD_PATCH + "\n")


def spine_finding_record(folder, sid):
    """How the spine-finding mask SPINEPS reused was made: by vibeseg_alone.py in this script, where it
    left its mark, else by a run before the mark was kept (verse561's, by SPINEPS's own process at
    12:18 UTC on 2026-10-29, before fold_patch existed)."""
    return FOLD_PATCH if os.path.exists(os.path.join(folder, "vibeseg_alone.done")) else REUSED


def main(listfile, out, sid, threads):
    torch.set_num_threads(threads)
    job = next(j for j in json.load(open(listfile)) if j["id"] == sid)
    folder = os.path.join(out, sid)
    os.makedirs(folder, exist_ok=True)
    if os.path.exists(os.path.join(folder, "ctgrid", "input.json")):
        print(sid, "done before", flush=True)
        return 0
    t = time.time()
    try:
        how, box = prepare_input(folder, sid, job["ct"], job["release"])
        if not os.path.exists(derivative(folder, sid, "vert")):
            spine_finding_alone(folder, sid, threads)
            from spineps import SpinepsPipeline
            from spineps.config import InstanceConfig
            pipe = SpinepsPipeline("ct", "ct_instance", "ct_labeling", use_cpu=True)
            res = pipe.segment(os.path.join(folder, f"sub-{sid}_ct.nii.gz"), output_in_memory=False,
                               instance=InstanceConfig(batch_size=1))
            if not res.success:
                print(sid, "FAILED", res.errcode, how, round(time.time() - t), flush=True)
                return 1
        to_ct_grid(folder, sid, job["ct"], how, box)
        print(sid, "OK", how, round(time.time() - t), "maxrss_mb",
              resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, flush=True)
        return 0
    except Exception as e:
        traceback.print_exc()
        print(sid, "ERROR", type(e).__name__, e, round(time.time() - t), flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 4))
