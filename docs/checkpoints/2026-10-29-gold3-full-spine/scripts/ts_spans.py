"""Fetch chosen members of the TotalSegmentator v3 zip by range requests, one span per subject, kept as raw zip bytes."""
import collections, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

URL = "https://zenodo.org/api/records/22688904/files/Totalsegmentator_dataset_v300.zip/content"
WANT = ("vertebrae_", "sacrum.nii.gz", "rib_", "skull.nii.gz", "spinal_cord.nii.gz", "hip_left.nii.gz", "hip_right.nii.gz")

def wanted(name):
    return "/segmentations/" in name and name.split("/")[-1].startswith(WANT)

def spans(cd):
    by = collections.defaultdict(list)
    for x in json.load(open(cd)):
        if wanted(x["name"]):
            by[x["name"].split("/")[1]].append(x)
    out = {}
    for s, xs in sorted(by.items()):
        lo = min(x["offset"] for x in xs)
        hi = max(x["offset"] + x["csize"] + 1024 for x in xs)
        out[s] = {"lo": lo, "hi": hi, "entries": xs}
    return out

def fetch(args):
    s, sp, out = args
    path = os.path.join(out, s + ".span")
    if os.path.exists(path) and os.path.getsize(path) == sp["hi"] - sp["lo"]:
        return s, 0
    for attempt in range(6):
        r = subprocess.run(["curl", "-sSL", "--max-time", "900", "-r", f"{sp['lo']}-{sp['hi'] - 1}", "-o", path + ".tmp", URL])
        if r.returncode == 0 and os.path.getsize(path + ".tmp") == sp["hi"] - sp["lo"]:
            os.replace(path + ".tmp", path)
            return s, sp["hi"] - sp["lo"]
    return s, -1

if __name__ == "__main__":
    cd, out = sys.argv[1], sys.argv[2]
    sp = spans(cd)
    json.dump(sp, open(os.path.join(out, "index.json"), "w"))
    n = 0
    with ThreadPoolExecutor(6) as pool:
        for s, size in pool.map(fetch, [(s, v, out) for s, v in sp.items()]):
            n += 1
            if size < 0 or n % 100 == 0:
                print(n, s, size, flush=True)
    print("done", n, flush=True)
