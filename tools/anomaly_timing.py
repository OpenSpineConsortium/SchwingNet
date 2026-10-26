"""The anomaly route's timing stage (#398, stage 2): the paired CTs that lack a SPINEPS mask, ten of them timed, and the estimate.

Usage (standard library only; grid/anomaly.sbatch runs it with STAGE=timing):
    python tools/anomaly_timing.py gpu --smi "<name>, <compute capability>"
    python tools/anomaly_timing.py inventory --data <data root> --work <realxray work root> --out <dir>
    python tools/anomaly_timing.py pick --inventory <dir>/inventory.csv --count 10 --out <dir>
    python tools/anomaly_timing.py estimate --timing-dir <dir>/spineps --inventory <dir>/inventory.csv [--gpu <line>]

Chapter 21's rule 14 puts a timing run before any production array, and rule 8 a GPU self-test before the first
case. The paired sets are the ones the route keeps test-only (docs/research/spineps-anomaly-route.md, section 2):
COBRA2026, C-ArmLSpine, DeepFluoro and LUMOS. For each the inventory reads where the records say its CTs and its
SPINEPS masks lie, and counts a mask only where VERIDAH named it: the old Elekta harvest under cobra2026/seg/spineps
carries raw instance ids and is reported apart (spinesurg-ct-nnunet tools/cobra_lstv_screen.py, tools/spineps_ids.py).
The ten CTs timed are drawn by rank among the CTs that lack a named mask and already have a NIfTI, since converting
a .mha or an H5 is another tool's work; what lacks a NIfTI is counted and left for the production array's request.
The report that leaves the grid carries counts and seconds only, never a case id or a path.
"""

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

SALT = "2026-10-25"
MASK = "_seg-vert_msk.nii.gz"
# Exit code of a stage that landed on a node its environment cannot use: the gate queues the stage
# again at the same commit, since no code was at fault (grid/gate.sh, word_anomaly).
NODE_UNUSABLE = 4
# The spineps environment's torch 2.6 cu124 build carries kernels up to compute capability 9 (Hopper) and none for
# Blackwell, 10 and above (B200 sm_100, the RTX PRO cards sm_120: the grid's ymh3 and ymh4, symphony-template
# docs/checkpoints/2026-10-20-claude-code/topic-memories/ruleclass-super-detector-run.md), so a stage that lands there
# spends nothing and leaves.
BLACKWELL_MAJOR = 10
WALL_HOURS = 8.0


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def rank(key):
    """A CT's place in the draw: the first 8 bytes of a salted sha256, as the holdout ranks a person."""
    digest = hashlib.sha256(f"schwingnet-anomaly-timing|{SALT}|{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def gpu_verdict(smi):
    """One line and an exit code from nvidia-smi's 'name, compute_cap' line: 0 to go on, NODE_UNUSABLE to leave the node."""
    text = (smi or "").strip()
    if not text:
        return NODE_UNUSABLE, "GPU: none seen (nvidia-smi gave nothing on this node); the stage leaves it and is sent again"
    name, _, cap = text.rpartition(",")
    name = name.strip() or text
    found = re.match(r"\s*(\d+)\.(\d+)\s*$", cap)
    if not found:
        return 0, f"GPU: {name} (compute capability unread: {cap.strip() or 'blank'})"
    major, minor = int(found.group(1)), int(found.group(2))
    if major >= BLACKWELL_MAJOR:
        return NODE_UNUSABLE, (f"GPU: {name}, sm_{major}{minor}: a Blackwell card, which the spineps environment's "
                               "torch 2.6 cu124 build cannot run; the stage leaves this node and is sent again")
    return 0, f"GPU: {name}, sm_{major}{minor}"


def mask_in(stores, case):
    """The first store that holds the case's vertebra mask, as (store name, path), else None."""
    for name, folder in stores:
        path = Path(folder) / f"{case}{MASK}"
        if path.is_file():
            return name, path
    return None


def first_file(candidates):
    for path in candidates:
        if Path(path).is_file():
            return Path(path)
    return None


def harvest_stores(data, prefix):
    """The anomaly harvest's SPINEPS folders of the collections named after a set, newest name first."""
    root = Path(data) / "anomaly_harvest"
    if not root.is_dir():
        return []
    return [(f"anomaly_harvest/{folder.name}/spineps", folder / "spineps")
            for folder in sorted(root.iterdir()) if folder.is_dir() and folder.name.startswith(prefix) and (folder / "spineps").is_dir()]


def cobra_rows(data):
    """COBRA2026: every case under cobra2026/cases ships ct_def.mha; NIfTIs and named masks lie where the screen left them."""
    root = Path(data) / "cobra2026"
    cases = root / "cases"
    if not cases.is_dir():
        return []
    named = [("cobra2026/lstv/seg", root / "lstv" / "seg"), ("spineps/cobra_varian", Path(data) / "spineps" / "cobra_varian")]
    named += harvest_stores(data, "cobra")
    raw = [("cobra2026/seg/spineps (raw ids)", root / "seg" / "spineps")]
    rows = []
    for folder in sorted(path for path in cases.iterdir() if path.is_dir()):
        case = folder.name
        nifti = first_file([root / "lstv" / "nifti" / f"{case}_ct.nii.gz", root / "varian" / "nifti" / f"{case}_ct.nii.gz",
                            root / "seg" / case / "ct_def.nii.gz"])
        mha = folder / "ct_def.mha"
        if nifti:
            ct, kind = nifti, "nifti"
        elif mha.is_file():
            ct, kind = mha, "mha"
        else:
            ct, kind = "", "none"
        rows.append(row("cobra", case, ct, kind, mask_in(named, case), mask_in(raw, case)))
    return rows


def table_rows(name, table, stores):
    """A set whose CTs a cases.csv lists (case, ct): C-ArmLSpine's, or DeepFluoro's realxray export."""
    if not Path(table).is_file():
        return []
    rows = []
    for entry in read_csv(table):
        case, ct = entry.get("case", ""), entry.get("ct", "")
        kind = "nifti" if ct and Path(ct).is_file() and ct.endswith((".nii", ".nii.gz")) else ("missing" if ct else "none")
        rows.append(row(name, case, ct if kind == "nifti" else "", kind, mask_in(stores, case), None))
    return rows


def deepfluoro_rows(data, work):
    """DeepFluoro: the realxray export's NIfTIs where its ct stage ran, else the shipped H5 and vendor DICOM, which need an export."""
    exported = Path(work) / "deepfluoro"
    rows = table_rows("deepfluoro", exported / "cases.csv", [("realxray_work/deepfluoro/spineps", exported / "spineps")])
    if rows:
        return rows
    h5 = sorted(Path(data).glob("deepfluoro_h5/raw/deepfluoro/*.h5"))
    rows = [row("deepfluoro", path.stem, path, "h5", None, None) for path in h5]
    vendor = Path(data) / "deepfluoro_vendor"
    if vendor.is_dir():
        rows += [row("deepfluoro", folder.name, folder, "dicom", None, None) for folder in sorted(vendor.iterdir()) if folder.is_dir()]
    return rows


def lumos_rows(data):
    """LUMOS: what the fetch left, zips and DICOM, none of it a NIfTI; its pairing is unproven (spine-datasets #207)."""
    root = Path(data) / "zenodo_lumos"
    if not root.is_dir():
        return []
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix == ".zip":
            rows.append(row("lumos", path.stem, path, "zip", None, None))
        elif path.is_file() and path.name.endswith((".nii", ".nii.gz")) and "ct" in path.name.lower():
            rows.append(row("lumos", path.name.split(".")[0], path, "nifti", None, None))
    return rows


def row(set_name, case, ct, kind, named, raw):
    if named:
        status = "named"
    elif raw:
        status = "raw"
    elif kind == "nifti":
        status = "lacking"
    else:
        status = "no_nifti"
    return {"set": set_name, "case": case, "ct": str(ct) if ct else "", "ct_kind": kind,
            "mask": str(named[1]) if named else (str(raw[1]) if raw else ""),
            "mask_store": named[0] if named else (raw[0] if raw else ""), "status": status}


def inventory(data, work):
    rows = cobra_rows(data)
    rows += table_rows("carmlspine", Path(data) / "carmlspine" / "cases.csv",
                       [("carmlspine/spineps", Path(data) / "carmlspine" / "spineps")] + harvest_stores(data, "carmlspine"))
    rows += deepfluoro_rows(data, work)
    rows += lumos_rows(data)
    return rows


STATUS_WORDS = {"named": "a VERIDAH-named SPINEPS mask", "raw": "a raw-id mask only (counts as lacking)",
                "lacking": "a NIfTI and no named mask", "no_nifti": "no NIfTI (.mha, H5, DICOM or a zip; an export first)"}


def inventory_lines(rows):
    counts = Counter((entry["set"], entry["status"]) for entry in rows)
    stores = Counter((entry["set"], entry["mask_store"]) for entry in rows if entry["mask_store"])
    lines = ["## The paired CTs and their SPINEPS masks", "", "| set | CTs | named mask | raw-id mask | NIfTI, no mask | no NIfTI |",
             "|---|---|---|---|---|---|"]
    for name in sorted({entry["set"] for entry in rows}):
        total = sum(count for (set_name, _), count in counts.items() if set_name == name)
        lines.append(f"| {name} | {total} | " + " | ".join(str(counts[(name, status)]) for status in ("named", "raw", "lacking", "no_nifti")) + " |")
    if not rows:
        lines.append("| (no paired set found under the data root) | 0 | 0 | 0 | 0 | 0 |")
    lines += ["", "Masks by store:", ""] + [f"- {name}: {store}: {count}" for (name, store), count in sorted(stores.items())]
    lines += ["", "A CT lacks a mask when its only mask carries raw instance ids, since no level is named by a SPINEPS id.",
              "LUMOS is listed and never timed: the pairing of CT n with film n is still a hypothesis (spine-datasets #207)."]
    return lines + [""]


def shares(total, weights):
    """Largest-remainder shares of total over weights, as the holdout splits a draw over the releases."""
    whole = sum(weights.values())
    if whole == 0 or total == 0:
        return {key: 0 for key in weights}
    exact = {key: total * weight / whole for key, weight in weights.items()}
    parts = {key: min(int(value), weights[key]) for key, value in exact.items()}
    left = total - sum(parts.values())
    for key in sorted(weights, key=lambda key: (-(exact[key] - parts[key]), key)):
        if left <= 0:
            break
        if parts[key] < weights[key]:
            parts[key] += 1
            left -= 1
    return parts


def pick(rows, count):
    """The CTs to time: by rank among those with a NIfTI and no named mask, shared over the sets by how many each lacks; never LUMOS."""
    eligible = defaultdict(list)
    for entry in rows:
        if entry["status"] in ("lacking", "raw") and entry["ct_kind"] == "nifti" and entry["set"] != "lumos":
            eligible[entry["set"]].append(entry)
    parts = shares(min(count, sum(map(len, eligible.values()))), {name: len(entries) for name, entries in eligible.items()})
    chosen = {}
    for name, entries in sorted(eligible.items()):
        ordered = sorted(entries, key=lambda entry: rank(f"{entry['set']}:{entry['case']}"))
        chosen[name] = [{"case": entry["case"], "ct": entry["ct"]} for entry in ordered[: parts[name]]]
    return chosen


def pick_lines(chosen, rows, count):
    lacking = Counter(entry["set"] for entry in rows if entry["status"] in ("lacking", "raw") and entry["set"] != "lumos")
    ready = Counter(entry["set"] for entry in rows if entry["status"] in ("lacking", "raw") and entry["ct_kind"] == "nifti" and entry["set"] != "lumos")
    picked = sum(map(len, chosen.values()))
    lines = ["## The CTs timed", "", f"Asked for {count}; picked {picked} by rank among the {sum(ready.values())} CTs with a NIfTI and no "
             f"named mask, of {sum(lacking.values())} lacking one in all.", "", "| set | lacking | of them with a NIfTI | picked |", "|---|---|---|---|"]
    lines += [f"| {name} | {lacking[name]} | {ready[name]} | {len(chosen.get(name, []))} |" for name in sorted(lacking)]
    if picked < count and sum(ready.values()) < sum(lacking.values()):
        lines += ["", f"Fewer than {count}: {sum(lacking.values()) - sum(ready.values())} of the lacking CTs have no NIfTI yet, "
                  "which the production array's request must bring."]
    elif picked < count:
        lines += ["", f"Fewer than {count}: only {picked} paired CTs lack a named mask."]
    return lines + [""]


def timings(timing_dir):
    """Every case's seconds from run_spineps_cases.py's timing_shard*.jsonl files under the stage's spineps folder."""
    done, failed = [], 0
    for path in sorted(Path(timing_dir).rglob("timing_shard*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("ok"):
                done.append(float(record.get("seconds", 0)))
            else:
                failed += 1
    return done, failed


def estimate(done, failed, lacking, gpu=""):
    lines = ["## The timing, and the estimate for the production array", ""]
    if gpu:
        lines.append(f"{gpu}")
    lines.append(f"Timed {len(done)} CTs; {failed} failed.")
    if not done:
        lines += ["", "No CT finished, so no estimate; the job's log says why."]
        return lines + [""]
    median = statistics.median(done)
    lines += [f"Seconds per CT: median {median:.0f}, least {min(done):.0f}, most {max(done):.0f}.", ""]
    total = sum(lacking.values())
    if total == 0:
        return lines + ["No paired CT lacks a named mask after this run, so no production array is needed.", ""]
    hours = total * median / 3600
    tasks = max(1, int(-(-hours // WALL_HOURS)))
    array = "one job" if tasks == 1 else f"an array of {tasks} tasks"
    lines += [f"CTs still lacking a named mask after this run: {total} (" + ", ".join(f"{name} {count}" for name, count in sorted(lacking.items())) + ").",
              f"At the median, one GPU would take {hours:.1f} hours for them; {array} keeps each under {WALL_HOURS:.0f} hours.",
              "The production array is not approved: this estimate is for the owner's count, asked once as a decision."]
    return lines + [""]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("gpu")
    one.add_argument("--smi", default="")
    one = sub.add_parser("inventory")
    one.add_argument("--data", required=True)
    one.add_argument("--work", required=True)
    one.add_argument("--out", required=True)
    one = sub.add_parser("pick")
    one.add_argument("--inventory", required=True)
    one.add_argument("--count", type=int, default=10)
    one.add_argument("--out", required=True)
    one = sub.add_parser("estimate")
    one.add_argument("--timing-dir", required=True)
    one.add_argument("--inventory", required=True)
    one.add_argument("--gpu", default="")
    args = parser.parse_args(argv)
    if args.command == "gpu":
        code, line = gpu_verdict(args.smi)
        print(line)
        return code
    if args.command == "inventory":
        rows = inventory(args.data, args.work)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        write_csv(out / "inventory.csv", ["set", "case", "ct", "ct_kind", "mask", "mask_store", "status"], rows)
        print("\n".join(inventory_lines(rows)))
        return 0
    if args.command == "pick":
        rows = read_csv(args.inventory)
        chosen = pick(rows, args.count)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, entries in chosen.items():
            if entries:
                write_csv(out / f"cases-{name}.csv", ["case", "ct"], entries)
        (out / "picked.json").write_text(json.dumps({name: len(entries) for name, entries in chosen.items()}, indent=1) + "\n", encoding="utf-8")
        print("\n".join(pick_lines(chosen, rows, args.count)))
        return 0
    rows = read_csv(args.inventory)
    done, failed = timings(args.timing_dir)
    timed = {(entry["set"], entry["case"]) for entry in rows if entry["status"] in ("lacking", "raw")}
    masks_now = set()
    for path in Path(args.timing_dir).rglob(f"*{MASK}"):
        masks_now.add((path.parent.name, path.name[: -len(MASK)]))
    lacking = Counter(name for name, case in timed if name != "lumos" and (name, case) not in masks_now)
    print("\n".join(estimate(done, failed, lacking, args.gpu)))
    # A run where no CT finished decided nothing: the stage fails, so the gate queues it again once a fix lands.
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
