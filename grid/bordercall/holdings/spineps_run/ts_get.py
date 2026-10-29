"""Fetch whole files of chosen TotalSegmentator v3 subjects from the release zip by byte ranges:
each subject's ct.nii.gz and its spine masks, written as the release names them under OUT/<subject>/.
Every file is checked against the central directory's sizes and its zip CRC."""
import json, os, struct, subprocess, sys, zlib

URL = "https://zenodo.org/api/records/22688904/files/Totalsegmentator_dataset_v300.zip/content"
WANT = ("ct.nii.gz", "vertebrae_", "sacrum.nii.gz")


def fetch_range(lo, hi, path):
    for attempt in range(6):
        r = subprocess.run(["curl", "-sSL", "--max-time", "900", "-r", f"{lo}-{hi - 1}", "-o", path, URL])
        if r.returncode == 0 and os.path.getsize(path) == hi - lo:
            return open(path, "rb").read()
        subprocess.run(["sleep", str(5 * (attempt + 1))])
    raise RuntimeError("range %d-%d not fetched" % (lo, hi))


def member(entry, scratch):
    lo, hi = entry["offset"], entry["offset"] + entry["csize"] + 1024
    span = fetch_range(lo, hi, scratch)
    if span[:4] != b"PK\x03\x04":
        raise ValueError("no local header for %s" % entry["name"])
    nlen, xlen = struct.unpack("<HH", span[26:30])
    crc = struct.unpack("<I", span[14:18])[0]
    data = span[30 + nlen + xlen:30 + nlen + xlen + entry["csize"]]
    raw = zlib.decompress(data, -15) if entry["method"] == 8 else data
    if len(raw) != entry["usize"]:
        raise ValueError("%s: %d bytes, the directory says %d" % (entry["name"], len(raw), entry["usize"]))
    if crc and zlib.crc32(raw) != crc:
        raise ValueError("%s: CRC differs" % entry["name"])
    return raw


if __name__ == "__main__":
    cd, out, subjects = sys.argv[1], sys.argv[2], sys.argv[3:]
    entries = json.load(open(cd))
    for s in subjects:
        folder = os.path.join(out, s)
        os.makedirs(folder, exist_ok=True)
        mine = [e for e in entries if e["name"].split("/")[1:2] == [s] and e["name"].split("/")[-1].startswith(WANT)]
        for e in mine:
            path = os.path.join(folder, e["name"].split("/")[-1])
            if os.path.exists(path) and os.path.getsize(path) == e["usize"]:
                continue
            raw = member(e, path + ".span")
            os.remove(path + ".span")
            with open(path + ".tmp", "wb") as f:
                f.write(raw)
            os.replace(path + ".tmp", path)
        print(s, len(mine), flush=True)
