"""Time tools/profile.py on three transcripts, the real one and two synthetic
sessions of 3,000 and 6,000 calls, in two trees, main and new, best of three:
the hook timings of step 1. Argument: a folder holding real.jsonl, s3000.jsonl,
s6000.jsonl and r4/main and r4/new, copies of the two trees."""
import subprocess, sys, time
from pathlib import Path
T = Path(sys.argv[1])
rows = []
for name in ("real", "s3000", "s6000"):
    for tree in ("main", "new"):
        best = None
        for _ in range(3):
            out = T / "r4" / f"{tree}-{name}.json"
            start = time.perf_counter()
            subprocess.run([sys.executable, str(T / "r4" / tree / "tools" / "profile.py"), str(T / f"{name}.jsonl"),
                            "--no-helpers", "--json", str(out)], check=True, capture_output=True)
            spent = time.perf_counter() - start
            best = spent if best is None else min(best, spent)
        rows.append((name, tree, best))
        print(name, tree, f"{best:.2f}", flush=True)
