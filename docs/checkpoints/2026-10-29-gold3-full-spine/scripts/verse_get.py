"""Download VerSe's MICCAI mask files listed by osf_list.py, each checked against its listed size."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

def get(item, out):
    release = {"923ap": "verse19", "b2wxj": "verse20", "jtfa5": "verse19", "4skx2": "verse20"}[item["node"]]
    folder = os.path.join(out, release)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, item["path"].split("/")[-1])
    if os.path.exists(path) and os.path.getsize(path) == item["size"]:
        return path, 0
    for attempt in range(6):
        r = subprocess.run(["curl", "-sSL", "--max-time", "900", "-o", path + ".tmp", item["url"]])
        if r.returncode == 0 and os.path.getsize(path + ".tmp") == item["size"]:
            os.replace(path + ".tmp", path)
            return path, item["size"]
        subprocess.run(["sleep", str(5 * (attempt + 1))])
    return path, -1

if __name__ == "__main__":
    listing, out, ending = sys.argv[1], sys.argv[2], sys.argv[3]
    items = [x for x in json.load(open(listing)) if x["path"].endswith(ending)]
    n = 0
    with ThreadPoolExecutor(4) as pool:
        for path, size in pool.map(lambda x: get(x, out), items):
            n += 1
            if size < 0 or n % 50 == 0:
                print(n, path, size, flush=True)
    print("done", n, flush=True)
