"""Download the VerSe CTs a job list names from OSF, each checked against its listed size."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

def get(job, out):
    folder = os.path.join(out, job["release"])
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, job["name"])
    if os.path.exists(path) and os.path.getsize(path) == job["size"]:
        return job["id"], 0
    for attempt in range(6):
        r = subprocess.run(["curl", "-sSL", "--max-time", "1800", "-o", path + ".tmp", job["url"]])
        if r.returncode == 0 and os.path.getsize(path + ".tmp") == job["size"]:
            os.replace(path + ".tmp", path)
            return job["id"], job["size"]
        subprocess.run(["sleep", str(5 * (attempt + 1))])
    return job["id"], -1

if __name__ == "__main__":
    jobs, out = json.load(open(sys.argv[1])), sys.argv[2]
    with ThreadPoolExecutor(3) as pool:
        for sid, size in pool.map(lambda j: get(j, out), jobs):
            print(sid, size, flush=True)
    print("done", len(jobs), flush=True)
