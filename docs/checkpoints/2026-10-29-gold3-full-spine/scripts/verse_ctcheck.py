"""Set every VerSe mask's header beside its CT's: same shape and affine, so the mask's field is the CT's."""
import json, os, sys
import nibabel as nib
import numpy as np

masks, headers = sys.argv[1], sys.argv[2]
cts = {}
for row in json.load(open(headers)):
    name = os.path.basename(row["path"])[:-len(".nii.gz")]
    cts.setdefault(name, []).append(row)
same, differ, missing = 0, [], []
for release in sorted(os.listdir(masks)):
    for f in sorted(os.listdir(os.path.join(masks, release))):
        if not f.endswith("_seg.nii.gz"):
            continue
        name = f[:-len("_seg.nii.gz")]
        h = nib.load(os.path.join(masks, release, f)).header
        shape, affine = [int(x) for x in h.get_data_shape()], np.array(h.get_best_affine())
        rows = cts.get(name, [])
        if not rows:
            missing.append(f"{release}/{f}")
            continue
        ok = any(r.get("shape") == shape and np.allclose(np.array(r["affine"]), affine, atol=1e-3) for r in rows)
        if ok:
            same += 1
        else:
            differ.append(f"{release}/{f}")
print(json.dumps({"same": same, "differ": differ, "missing": missing}))
