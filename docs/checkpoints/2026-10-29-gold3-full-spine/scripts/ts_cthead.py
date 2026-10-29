"""Read the NIfTI header of every TotalSegmentator v3 CT from the release zip by a ranged read of its member's first bytes."""
import io, json, struct, subprocess, sys, zlib
from concurrent.futures import ThreadPoolExecutor
import nibabel as nib

URL = "https://zenodo.org/api/records/22688904/files/Totalsegmentator_dataset_v300.zip/content"

def head(entry):
    lo = entry["offset"]
    err = None
    for attempt in range(6):
        r = subprocess.run(["curl", "-sSL", "--max-time", "120", "-r", f"{lo}-{lo + 24575}", URL], capture_output=True)
        data = r.stdout
        if r.returncode == 0 and data[:4] == b"PK\x03\x04":
            try:
                n, m = struct.unpack("<HH", data[26:30])
                gz = zlib.decompressobj(-15).decompress(data[30 + n + m:])
                raw = zlib.decompressobj(31).decompress(gz)
                h = nib.Nifti1Header.from_fileobj(io.BytesIO(raw[:352]))
                return {"id": entry["name"].split("/")[1], "shape": [int(x) for x in h.get_data_shape()][:3],
                        "affine": h.get_best_affine().round(6).tolist()}
            except Exception as e:
                err = repr(e)
        else:
            err = "curl %d %r" % (r.returncode, data[:60])
        subprocess.run(["sleep", str(4 * (attempt + 1))])
    return {"id": entry["name"].split("/")[1], "error": err}

if __name__ == "__main__":
    cd, out = sys.argv[1], sys.argv[2]
    cts = [x for x in json.load(open(cd)) if x["name"].endswith("/ct.nii.gz")]
    with ThreadPoolExecutor(4) as pool:
        rows = list(pool.map(head, cts))
    json.dump(rows, open(out, "w"))
    print(len(rows), sum("error" in r for r in rows), flush=True)
