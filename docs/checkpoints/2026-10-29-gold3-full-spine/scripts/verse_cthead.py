"""Read the NIfTI header of every VerSe CT by a ranged read of its first 16 KB; no CT is downloaded."""
import io, json, subprocess, sys, zlib
from concurrent.futures import ThreadPoolExecutor
import nibabel as nib

def head(item):
    for attempt in range(5):
        r = subprocess.run(["curl", "-sSL", "--max-time", "120", "-r", "0-16383", item["url"]], capture_output=True)
        if r.returncode == 0 and len(r.stdout) >= 1024:
            try:
                raw = zlib.decompressobj(31).decompress(r.stdout)
                h = nib.Nifti1Header.from_fileobj(io.BytesIO(raw[:352]))
                return {"node": item["node"], "path": item["path"], "size": item["size"],
                        "shape": [int(x) for x in h.get_data_shape()], "zooms": [float(x) for x in h.get_zooms()],
                        "affine": h.get_best_affine().round(6).tolist(), "dtype": str(h.get_data_dtype()),
                        "sform_code": int(h["sform_code"]), "qform_code": int(h["qform_code"])}
            except Exception as e:
                err = repr(e)
        else:
            err = "curl %d" % r.returncode
        subprocess.run(["sleep", str(3 * (attempt + 1))])
    return {"node": item["node"], "path": item["path"], "error": err}

if __name__ == "__main__":
    listing, out = sys.argv[1], sys.argv[2]
    items = [x for x in json.load(open(listing)) if x["path"].endswith(".nii.gz") and not x["path"].endswith("_seg.nii.gz")]
    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(head, items))
    json.dump(rows, open(out, "w"), indent=0)
    print(len(rows), sum("error" in r for r in rows))
