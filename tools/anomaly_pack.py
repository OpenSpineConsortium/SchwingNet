"""The anomaly route's pack stage (#391, stage 3): the selection resolved to CTs and masks, the masks rewritten to the 28 canonical ids, the splits, FleXray's manifests and the size the admission reads.

Usage (standard library only; grid/anomaly.sbatch runs each step with STAGE=pack under $PYDRV):
    python tools/anomaly_pack.py rows --selection CSV --holdout JSON --data DIR --home DIR --registry CSV --harvest DIR --out DIR [--segmenter spineps]
    python tools/anomaly_pack.py guard-list --rows CSV --out DIR
    python tools/anomaly_pack.py testgate --rows CSV [--masks CSV]
    python tools/anomaly_pack.py size --rows CSV --landing DIR
    python tools/anomaly_pack.py rewrite --rows CSV --guard TXT --masks DIR --out DIR
    python tools/anomaly_pack.py split --rows CSV --masks CSV --g3 JSON --validation JSON --out DIR [--distrust ctsp] [--uncounted pack|drop]
    python tools/anomaly_pack.py trainval --splits CSV --out DIR
    python tools/anomaly_pack.py manifest --splits CSV --masks CSV --rows CSV --dataset NAME [--hu=-1000,2000] [--crops X,Y,Z] --out DIR

Each step prints one markdown section of counts and digests to stdout, writes the same text as <out>/<step>.md
and its CSV under --out; case ids, person keys and paths go only into the CSVs, since the report that leaves
the grid carries counts alone (docs/research/spineps-anomaly-route.md). An error exits 1 with one fixed
sentence on stderr that names a count or a reason, never a path or a case.

Why the stage is cut this way: a row is packed whole or not at all, so every CT is resolved and its header
read before a byte lands (the admission reads rows.csv alone); VerSe and CTSpinoPelvic1K keep their expert
release masks and every other row takes a SPINEPS mask the guard (spineps_ids.py check --strict) listed OK,
never a raw-id or TotalSegmentator store; a mask is countable when C1 or C2 and the sacrum are in the field
by the mask, the record or the ctd, and complete when both come from the mask with no body missing between,
which decides its package, since FleXray routes the loss by dataset name and a partial mask under the standard
loss would teach absence; the G3 validation and test transitional persons are packed under g3_excluded and
trained on by nothing; the validation split is drawn by rank under the frozen rule of
data/splits/anomaly-validation.json, whose digest the next pull request copies in.

The canonical names, the VerSe alphabet and the id maps below are carried here as constants; their home is
src/schwingnet/segmenters.py once #401 lands (the segmenter block), and this tool never imports src/schwingnet.
"""

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def sibling(name):
    """A tool beside this one, loaded by path: tools/ is no package and never joins sys.path, since
    tools/profile.py would shadow the standard library's profile for anything imported after it."""
    file = TOOLS / f"{name}.py"
    found = sys.modules.get(name)
    if found is not None and getattr(found, "__file__", None) == str(file):
        return found
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


nifti_label = sibling("nifti_label")

# The segmentation model is a configurable block (the owner, 2026-10-26): spineps is production, moose only
# replicates FleXray's own dataset, and no MOOSE mask exists on the grid, so this stage refuses it.
SEGMENTERS = ("spineps", "moose")
# The 28 canonical ids: background, C1-C7, T1-T12, T13, L1-L5, L6, sacrum (src/schwingnet/segmenters.py once #401 lands).
CANONICAL = (["background"] + [f"vertebra_c{i}" for i in range(1, 8)] + [f"vertebra_t{i}" for i in range(1, 13)]
             + ["vertebra_t13"] + [f"vertebra_l{i}" for i in range(1, 6)] + ["vertebra_l6", "sacrum"])
T13, L6, SACRUM = 20, 26, 27
# The VerSe alphabet (C1-C7 1-7, T1-T12 8-19, L1-L5 20-24, L6 25, sacrum 26, T13 28) to the canonical ids;
# 29 is CTSpinoPelvic1K's retired S1, the sacrum too (spineps_ids.py:93-94; ctsp_registry_census.py:289-292).
VERSE_TO_CANONICAL = {**{i: i for i in range(1, 20)}, 28: T13, **{20 + i: 21 + i for i in range(5)},
                      25: L6, 26: SACRUM, 29: SACRUM}
# The coccyx, the hips and femurs, the ribs, the lumbar ribs, the hardware (DATA_MANIFEST.md:599-601) and TPTBox's
# metal (80, spineps_ids.py:95-96) go to background, each counted.
DROPPED = {27} | set(range(30, 69)) | {nifti_label.METAL}
METAL_NOTABLE_ML = 5.0
TRANSITIONAL = {"L6", "T13", "four_lumbar", "both_L6_T13"}
ORDINARY = {"", "none", "ordinary"}
# The bodies a count passes through, in canonical ids; T13 (20) and L6 (26) are variants, so their absence is no gap.
PRESACRAL = list(range(1, 20)) + list(range(21, 26))
TOP_IDS = {1, 2}
# One ThunderDB value holds a row's float16 image and uint8 label; lmdbm doubles its map at most twelve times
# from 1 MiB inside one write (lmdbm.py:58, :121-136), so a payload past 3 GiB is refused before any byte lands.
PAYLOAD_LIMIT = 3 * 2 ** 30
PAYLOAD_PER_VOXEL = 3
# What a row costs under the landing, uncompressed: float16 image, uint8 label in the package, uint8 mask file.
PACKED_PER_VOXEL = 4
ROW_OVERHEAD = 64
MASK = "_seg-vert_msk.nii.gz"
VERIDAH_MASK = "_seg-vert_msk_veridah.nii.gz"
CTD = "_ctd.json"
# Collections the selection may carry that resolve to nothing in this version, counted and never fatal.
UNKNOWN_COLLECTIONS = {"deepfluoro", "geneva", "spinesac", "ljubljana"}
# A harvest key in the registry's spelling, as tools/anomaly_route.py keys them.
KEY_ALIASES = {"totalsegmentator_v2": "ts"}
# A holdout person's collection from its key's prefix, in the selection's spelling of winning_source.
COLLECTION_OF_PREFIX = {"verse": "verse", "ctsp": "ctsp", "ts": "totalsegmentator", "cobra": "cobra2026"}
DATASETS = {"schwingnet_spine": "complete", "schwingnet_spine_partial": "partial"}
HU_WINDOW = (-1000.0, 2000.0)
VALIDATION_PREFIX = "schwingnet-anomaly-validation"
SKIPPED_NAME = "veridah_skipped_name"
PACKED = ("rewritten", "kept")
TRAINED = ("train", "val")

ROW_COLUMNS = ["person", "collection", "case", "sample_id", "variant", "subtype", "tier", "role", "fold", "segmenter",
               "ct", "mask", "mask_kind", "ctd", "status", "ls_record", "voxels", "dims"]
MASK_COLUMNS = ["person", "collection", "case", "sample_id", "role", "src", "dst", "status", "reason", "ids_in",
                "ids_out", "dropped", "metal_voxels", "metal_ml", "top", "top_from", "sacrum_from", "gap",
                "countable", "complete", "voxels", "dims", "seconds"]
SPLIT_COLUMNS = ["sample_id", "person", "case", "split", "why", "countable", "complete", "variant", "subtype",
                 "collection", "role", "fold"]


class Failed(Exception):
    """The stage stops: str(self) is the fixed sentence for stderr, which names a count or a reason only."""


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def emit(out, name, lines):
    """The step's section printed and kept as <out>/<name>.md, so the sbatch appends it to the report."""
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if out:
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / f"{name}.md").write_text(text, encoding="utf-8")


def flag(value):
    return value is True or value == "True"


def tally(counter, keys=None):
    """'a 3, b 1' over keys in a fixed order, else the counter's by count; 'none' when empty."""
    items = [(key, counter[key]) for key in keys] if keys else counter.most_common()
    return ", ".join(f"{key} {count}" for key, count in items) or "none"


# ---------------------------------------------------------------------------------------------------- rows
def sample_id(collection, case):
    """FleXray's sample id: the collection, two underscores, the case with every path character made safe;
    never starting with an underscore (packaging.py:566-567)."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(case).replace("/", "__"))
    out = f"{collection}__{safe}"
    return out if not out.startswith("_") else "c" + out


def registry_key(key):
    """A harvest key in the registry's spelling, so a stream screened twice is one person (anomaly_route.py)."""
    prefix, _, rest = key.partition(":")
    return f"{KEY_ALIASES[prefix]}:{rest}" if rest and prefix in KEY_ALIASES else key


def collection_of(person):
    prefix = person.partition(":")[0]
    return COLLECTION_OF_PREFIX.get(prefix, prefix)


def read_selection(path):
    return read_csv(path)


def holdout_rows(holdout):
    """One row per scan of each held-out person, role holdout: the holdout tests every scan it names."""
    rows = []
    for entry in holdout.get("persons", []):
        for scan in entry.get("scans", []):
            rows.append({"person": entry["person"], "collection": collection_of(entry["person"]), "case": scan,
                         "variant": entry.get("variant", ""), "tier": "", "role": "holdout", "fold": ""})
    return rows


def fold_of(holdout):
    return {entry["person"]: str(entry["fold"]) for entry in holdout.get("folds", [])}


def read_table(path):
    """A cases.csv (case, ct) as a dict, empty where the file is not there."""
    path = Path(path)
    if not path.is_file():
        return {}
    return {row.get("case", ""): row.get("ct", "") for row in read_csv(path)}


def table_ct(table, keys):
    """The ct a cases.csv names for the first of keys it lists, else None."""
    listed = read_table(table)
    for key in keys:
        if listed.get(key):
            return Path(listed[key])
    return None


def harvest_stores(data, prefix):
    """The anomaly harvest's SPINEPS folders of the collections named after a set, by name."""
    root = Path(data) / "anomaly_harvest"
    if not root.is_dir():
        return []
    return [folder / "spineps" for folder in sorted(root.iterdir())
            if folder.is_dir() and folder.name.startswith(prefix) and (folder / "spineps").is_dir()]


def spineps_pair(store, stem):
    return (Path(store) / f"{stem}{MASK}", Path(store) / f"{stem}{CTD}")


def other_ct_pairs(data, source, case):
    """The other_ct stream's SPINEPS output, the VERIDAH-named copy first (other_ct_screen.py:248-249, :253-256)."""
    store = Path(data) / "anomaly_harvest" / "other_ct" / source / "spineps"
    safe = case.replace("/", "__")
    return [(store / f"{safe}{VERIDAH_MASK}", store / f"{safe}{CTD}"), spineps_pair(store, safe)]


def stores_verse(case, data, home):
    scan = Path(home) / "VerSeFusion" / "data" / "unified" / f"scan-{case}"
    ctd = Path(home) / "bench_ts" / "spineps" / "native" / f"VERSE_{case}{CTD}"
    return {"ct": [scan / f"scan-{case}_ct.nii.gz"], "missing": "no_ct",
            "masks": [(scan / f"scan-{case}_msk.nii.gz", ctd)], "kind": "release"}


def stores_ctsp(case, data, home):
    root = Path(home) / "data" / "CTSpinoPelvic1K"
    return {"ct": [root / "ct" / f"{case}_ct.nii.gz"], "missing": "no_ct",
            "masks": [(root / "labels" / f"{case}_label.nii.gz", Path(data) / "spineps" / "ctsp" / f"CTSP_{case}{CTD}")],
            "kind": "release"}


def stores_totalsegmentator(case, data, home):
    """The CT from the bench's cases.csv, else the corpus folder (never its segmentations/); the relabelled
    copy of the SPINEPS mask first, the bench's native store after it, where the guard tells a raw mask."""
    stem = case if case.startswith("TS_") else f"TS_{case}"
    subject = stem[3:]
    ct = [table_ct(Path(home) / "bench_ts" / "cases.csv", (case, stem, subject)),
          Path(home) / "data" / "TotalSegmentator" / subject / "ct.nii.gz"]
    stores = [Path(data) / "spineps" / "ctd_relabel" / "bench_ts_native", Path(home) / "bench_ts" / "spineps" / "native"]
    return {"ct": ct, "missing": "no_ct", "masks": [spineps_pair(store, stem) for store in stores], "kind": "spineps"}


def stores_cobra(case, data, home):
    """COBRA2026: a NIfTI where the screen left one, else no_nifti (the .mha is another tool's to convert);
    the named stores only, never seg/spineps, whose ids are raw."""
    root = Path(data) / "cobra2026"
    ct = [root / "lstv" / "nifti" / f"{case}_ct.nii.gz", root / "varian" / "nifti" / f"{case}_ct.nii.gz",
          root / "seg" / case / "ct_def.nii.gz"]
    stores = [root / "lstv" / "seg", Path(data) / "spineps" / "cobra_varian"] + harvest_stores(data, "cobra")
    return {"ct": ct, "missing": "no_nifti", "masks": [spineps_pair(store, case) for store in stores], "kind": "spineps"}


def stores_carmlspine(case, data, home):
    stores = [Path(data) / "carmlspine" / "spineps"] + harvest_stores(data, "carmlspine")
    return {"ct": [table_ct(Path(data) / "carmlspine" / "cases.csv", (case,))], "missing": "no_ct",
            "masks": [spineps_pair(store, case) for store in stores], "kind": "spineps"}


def stores_ctspine1k(case, data, home):
    subject, _, stem = case.partition("/")
    return {"ct": [Path(data) / "ctspine1k" / "raw_data" / "volumes" / subject / f"{stem}.nii.gz"], "missing": "no_ct",
            "masks": other_ct_pairs(data, "ctspine1k", case), "kind": "spineps"}


def stores_ribfrac(case, data, home):
    return {"ct": [Path(data) / "ribfrac" / "images" / f"{case}-image.nii.gz"], "missing": "no_ct",
            "masks": other_ct_pairs(data, "ribfrac", case), "kind": "spineps"}


def stores_harvest(collection, case, data, home):
    """Any other collection is the acquisition screen's: its cases.csv names the CT (a source already in NIfTI
    keeps its raw path there), the nifti folder is the fallback, and its spineps folder holds the mask."""
    root = Path(data) / "anomaly_harvest" / collection
    ct = [table_ct(root / "cases.csv", (case,)), Path(data) / collection / "nifti" / f"{case}_ct.nii.gz"]
    return {"ct": ct, "missing": "no_ct", "masks": [spineps_pair(root / "spineps", case)], "kind": "spineps"}


STORES = {"verse": stores_verse, "ctsp": stores_ctsp, "totalsegmentator": stores_totalsegmentator,
          "cobra2026": stores_cobra, "carmlspine": stores_carmlspine, "ctspine1k": stores_ctspine1k,
          "ribfrac": stores_ribfrac}


def resolve(row, data, home, exists=None):
    """The row's CT, mask, the mask's kind and its ctd, first store found wins; status ok, no_ct, no_nifti,
    no_mask or unknown_collection."""
    exists = exists or (lambda path: Path(path).is_file())
    found = {"ct": "", "mask": "", "mask_kind": "", "ctd": "", "status": "ok"}
    collection, case = row["collection"], row["case"]
    if collection in UNKNOWN_COLLECTIONS:
        found["status"] = "unknown_collection"
        return found
    finder = STORES.get(collection)
    stores = finder(case, data, home) if finder else stores_harvest(collection, case, data, home)
    ct = next((path for path in stores["ct"] if path and exists(path)), None)
    if ct is None:
        found["status"] = stores["missing"]
        return found
    found["ct"] = str(ct)
    pair = next(((mask, ctd) for mask, ctd in stores["masks"] if exists(mask)), None)
    if pair is None:
        found["status"] = "no_mask"
        return found
    found["mask"], found["mask_kind"] = str(pair[0]), stores["kind"]
    found["ctd"] = str(pair[1]) if exists(pair[1]) else ""
    return found


def record_flags(registry, harvest):
    """person -> (junction_ls_in_fov, subtype) from registry.csv and every harvest rows.csv, the registry
    first, since harvest persons are not in the registry and a stream screened twice is one person."""
    flags = {}
    for row in read_csv(registry):
        flags.setdefault(row["patient_key"], (flag(row.get("junction_ls_in_fov")), row.get("subtype", "")))
    for path in sorted(Path(harvest).glob("*/rows.csv")) if harvest and Path(harvest).is_dir() else []:
        for row in read_csv(path):
            key = registry_key(row.get("patient_key") or f"{path.parent.name}:{row.get('case', '')}")
            flags.setdefault(key, (flag(row.get("junction_ls_in_fov")), row.get("subtype", "")))
    return flags


def census(rows):
    """Every ok row's CT header read for its voxels and dims, one gzip block each; a header that cannot be
    read is no_nifti, and a payload past the ThunderDB limit is payload_too_large."""
    for row in rows:
        if row["status"] != "ok":
            continue
        try:
            header = nifti_label.read_header(row["ct"])
            voxels = nifti_label.voxel_count(header.dims)
        except (nifti_label.NotNifti, nifti_label.LabelRefused, OSError):
            row["status"] = "no_nifti"
            continue
        row["voxels"], row["dims"] = str(voxels), "x".join(str(d) for d in header.dims[1:4])
        if voxels * PAYLOAD_PER_VOXEL > PAYLOAD_LIMIT:
            row["status"] = "payload_too_large"
    return rows


ROW_STATUSES = ("ok", "no_ct", "no_nifti", "no_mask", "unknown_collection", "payload_too_large")


def rows_lines(rows, holdout, segmenter):
    held = holdout.get("persons", [])
    status = Counter(row["status"] for row in rows)
    kinds = Counter(row["mask_kind"] for row in rows if row["status"] == "ok")
    lines = ["## rows", "", f"- segmenter: {segmenter}",
             f"- selection: {sum(row['role'] != 'holdout' for row in rows)} rows; holdout: {len(held)} persons, "
             f"{sum(len(entry.get('scans', [])) for entry in held)} scans",
             f"- status: {tally(status, ROW_STATUSES)}",
             f"- masks: release {kinds['release']}, spineps {kinds['spineps']}", "",
             "| collection | role | rows | " + " | ".join(ROW_STATUSES) + " |", "|---|---|---|" + "---|" * len(ROW_STATUSES)]
    groups = defaultdict(Counter)
    for row in rows:
        groups[(row["collection"], row["role"])][row["status"]] += 1
    for (collection, role), counts in sorted(groups.items()):
        lines.append(f"| {collection} | {role} | {sum(counts.values())} | " + " | ".join(str(counts[s]) for s in ROW_STATUSES) + " |")
    return lines


def cmd_rows(args):
    if args.segmenter != "spineps":
        raise Failed("the moose segmenter is not built for this stage: no MOOSE mask exists on the grid")
    holdout = read_json(args.holdout)
    folds = fold_of(holdout)
    rows = read_selection(args.selection) + holdout_rows(holdout)
    flags = record_flags(args.registry, args.harvest)
    for row in rows:
        row.setdefault("subtype", "")
        row["fold"] = row.get("fold") or folds.get(row["person"], "")
        row["segmenter"] = args.segmenter
        row["sample_id"] = sample_id(row["collection"], row["case"])
        row.update(resolve(row, args.data, args.home))
        ls, subtype = flags.get(row["person"], (False, ""))
        row["ls_record"], row["subtype"] = str(ls), row.get("subtype") or subtype
        row["voxels"], row["dims"] = "", ""
    census(rows)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "rows.csv", ROW_COLUMNS, rows)
    emit(out, "rows", rows_lines(rows, holdout, args.segmenter))
    return 0


# ---------------------------------------------------------------------------------------------------- guard
def cmd_guard_list(args):
    rows = read_csv(args.rows)
    masks = sorted({row["mask"] for row in rows if row["status"] == "ok" and row["mask_kind"] == "spineps"})
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "guard-list.txt").write_text("".join(f"{mask}\n" for mask in masks), encoding="utf-8")
    emit(out, "guard-list", ["## guard-list", "", f"- {len(masks)} SPINEPS masks for spineps_ids.py check --strict"])
    return 0


def read_guard(path):
    """mask -> (listed OK, verdict) from spineps_ids.py check's lines: 'OK   <path>: <verdict>' splits on the
    last ': ', 'FAIL <path>: SPINEPS ids ... [<verdict>]: ...' names the path before ': SPINEPS ids' and the
    verdict in the brackets; any other line (a warning, a traceback) says nothing."""
    verdicts = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("OK   "):
            mask, sep, verdict = line[5:].rpartition(": ")
            if sep:
                verdicts[mask] = (True, verdict.strip())
        elif line.startswith("FAIL "):
            mask, sep, rest = line[5:].partition(": SPINEPS ids")
            found = re.search(r"\[([^\]]+)\]", rest)
            if sep and found:
                verdicts[mask] = (False, found.group(1))
    return verdicts


# ---------------------------------------------------------------------------------------------------- rewrite
def ctd_ids(path):
    """The VerSe ids a TPTBox POI ctd names, the integer keys of its last element; None where there is no ctd
    to read (spineps_ids.py:149-174)."""
    if not path or not Path(path).is_file():
        return None
    try:
        points = read_json(path)
    except ValueError:
        return None
    if not isinstance(points, list) or not points or not isinstance(points[-1], dict):
        return None
    return {int(key) for key in points[-1] if str(key).lstrip("-").isdigit()}


def countable_of(ids_out, ctd, ls_record):
    """Whether a count can run from the top of the field to the sacrum, and where each end is known from:
    the mask, the record (junction_ls_in_fov) or the ctd's names; complete when both ends are in the mask and
    no presacral body is missing between the highest and lowest present."""
    present = set(ids_out)
    ctd = set(ctd or ())
    if present & TOP_IDS:
        top_from = "mask"
    elif 2 in ctd:
        top_from = "ctd"
    else:
        top_from = "none"
    if SACRUM in present:
        sacrum_from = "mask"
    elif ls_record:
        sacrum_from = "record"
    elif 26 in ctd:
        sacrum_from = "ctd"
    else:
        sacrum_from = "none"
    bodies = sorted(v for v in present if v in PRESACRAL)
    gap = any(v not in present for v in PRESACRAL if bodies and bodies[0] < v < bodies[-1])
    countable = top_from != "none" and sacrum_from != "none"
    complete = countable and top_from == sacrum_from == "mask" and not gap
    top = min((v for v in present if v != SACRUM), default="")
    return {"top": top, "top_from": top_from, "sacrum_from": sacrum_from, "gap": gap, "countable": countable,
            "complete": complete}


def sidecar_matches(sidecar, src, dst):
    """The sidecar's record when it names this source at its present size and mtime and the written file at
    its present size, so a mask written once is not written again; None otherwise."""
    try:
        record = read_json(sidecar)
        source, written = os.stat(src), os.stat(dst)
    except (OSError, ValueError):
        return None
    same = (record.get("src") == str(src) and record.get("src_size") == source.st_size
            and record.get("src_mtime") == source.st_mtime and record.get("dst_size") == written.st_size)
    return record if same else None


def rewrite_one(row, masks_dir):
    """The row's mask rewritten under the landing as <sample_id>.nii.gz with a sidecar, or kept when the
    sidecar says it was written from this very source; (record, 'rewritten' or 'kept')."""
    src = row["mask"]
    dst = Path(masks_dir) / f"{row['sample_id']}.nii.gz"
    sidecar = Path(masks_dir) / f"{row['sample_id']}.json"
    kept = sidecar_matches(sidecar, src, dst)
    if kept:
        return kept, "kept"
    ct_header = nifti_label.read_header(row["ct"])
    done = nifti_label.rewrite(src, dst, VERSE_TO_CANONICAL, DROPPED, ct_header)
    source = os.stat(src)
    record = {"src": str(src), "src_size": source.st_size, "src_mtime": source.st_mtime, "dst": str(dst),
              "dst_size": os.stat(dst).st_size, "ids_in": list(done.ids_in), "ids_out": list(done.ids_out),
              "dropped": {str(k): v for k, v in sorted(done.dropped_counts.items())}, "metal_voxels": done.metal_voxels,
              "metal_ml": done.metal_ml, "voxels": done.voxels, "dims": list(done.dims), "seconds": done.seconds}
    part = Path(str(sidecar) + ".part")
    part.write_text(json.dumps(record) + "\n", encoding="utf-8")
    os.replace(part, sidecar)
    return record, "rewritten"


def mask_record(row):
    return {"person": row["person"], "collection": row["collection"], "case": row["case"], "sample_id": row["sample_id"],
            "role": row["role"], "src": row["mask"], "dst": "", "status": "", "reason": "", "ids_in": "", "ids_out": "",
            "dropped": "", "metal_voxels": "", "metal_ml": "", "top": "", "top_from": "", "sacrum_from": "", "gap": "",
            "countable": "", "complete": "", "voxels": "", "dims": "", "seconds": ""}


def guard_verdict(row, guard):
    """The reason a SPINEPS mask is refused by the guard, or None when it was listed OK or needs no guard."""
    if row["mask_kind"] != "spineps":
        return None
    listed = guard.get(row["mask"])
    if listed is None:
        return "guard_unlisted"
    return None if listed[0] else listed[1]


def fill_measured(rec, record, row):
    ctd = ctd_ids(row["ctd"])
    measure = countable_of(record["ids_out"], ctd, flag(row["ls_record"]))
    rec.update({"dst": record["dst"], "ids_in": " ".join(map(str, record["ids_in"])),
                "ids_out": " ".join(map(str, record["ids_out"])),
                "dropped": " ".join(f"{k}:{v}" for k, v in record["dropped"].items()),
                "metal_voxels": str(record["metal_voxels"]), "metal_ml": f"{record['metal_ml']:.4f}",
                "voxels": str(record["voxels"]), "dims": "x".join(map(str, record["dims"])),
                "seconds": f"{record['seconds']:.3f}"})
    rec.update({key: str(value) for key, value in measure.items()})
    return ctd is None


def masks_lines(records, rows_by_id, timings, counts):
    packed = [rec for rec in records if rec["status"] in PACKED]
    kinds = Counter(rows_by_id[rec["sample_id"]]["mask_kind"] for rec in packed if rec["status"] == "rewritten")
    guard = Counter(rec["reason"] for rec in records if rec["status"] == "guard_refused" and rec["reason"] != SKIPPED_NAME)
    skipped = sum(rec["reason"] == SKIPPED_NAME for rec in records if rec["status"] == "guard_refused")
    unreadable = Counter(rec["reason"] for rec in records if rec["status"] == "refused")
    dropped_masks, dropped_voxels = Counter(), Counter()
    for rec in packed:
        for item in rec["dropped"].split():
            key, _, voxels = item.partition(":")
            dropped_masks[int(key)] += 1
            dropped_voxels[int(key)] += int(voxels)
    metal = [rec for rec in packed if int(rec["metal_voxels"] or 0)]
    heavy = sum(float(rec["metal_ml"]) >= METAL_NOTABLE_ML for rec in metal)
    measure = {key: Counter(rec[key] for rec in packed) for key in ("top_from", "sacrum_from")}
    lines = ["## masks", "",
             f"- rewritten {sum(rec['status'] == 'rewritten' for rec in records)} (release {kinds['release']}, "
             f"spineps {kinds['spineps']}); kept {sum(rec['status'] == 'kept' for rec in records)} from an earlier run",
             f"- refused by the guard {sum(guard.values()) + skipped}: {tally(guard)}; {SKIPPED_NAME} {skipped} apart",
             f"- unreadable {sum(unreadable.values())}: {tally(unreadable)}",
             f"- no_ctd {counts['no_ctd']}",
             "- dropped ids: " + (", ".join(f"{k} in {dropped_masks[k]} masks ({dropped_voxels[k]} voxels)" for k in sorted(dropped_masks)) or "none"),
             f"- metal: {len(metal)} masks, {heavy} of them {METAL_NOTABLE_ML:g} ml or more",
             f"- countable {sum(flag(rec['countable']) for rec in packed)}, complete {sum(flag(rec['complete']) for rec in packed)}, "
             f"partial {sum(flag(rec['countable']) and not flag(rec['complete']) for rec in packed)}, "
             f"uncountable {sum(not flag(rec['countable']) for rec in packed)}",
             f"- top_from: {tally(measure['top_from'], ('mask', 'ctd', 'none'))}; sacrum_from: "
             f"{tally(measure['sacrum_from'], ('mask', 'record', 'ctd', 'none'))}; gap {sum(flag(rec['gap']) for rec in packed)}"]
    if timings:
        lines.append(f"- seconds: median {statistics.median(timings):.2f}, least {min(timings):.2f}, most {max(timings):.2f}, "
                     f"total {sum(timings):.1f} over {len(timings)} masks rewritten in this run")
    else:
        lines.append("- seconds: no mask rewritten in this run")
    return lines


def cmd_rewrite(args):
    rows = [row for row in read_csv(args.rows) if row["status"] == "ok"]
    rows_by_id = {row["sample_id"]: row for row in rows}
    guard = read_guard(args.guard) if args.guard else {}
    masks_dir = Path(args.masks)
    masks_dir.mkdir(parents=True, exist_ok=True)
    records, timings, counts = [], [], Counter()
    for row in rows:
        rec = mask_record(row)
        verdict = guard_verdict(row, guard)
        if verdict:
            rec["status"], rec["reason"] = "guard_refused", verdict
        else:
            try:
                record, rec["status"] = rewrite_one(row, masks_dir)
            except nifti_label.LabelRefused as refused:
                rec["status"], rec["reason"] = "refused", refused.reason
            except (nifti_label.NotNifti, OSError):
                rec["status"], rec["reason"] = "refused", "no_nifti"
            else:
                if fill_measured(rec, record, row):
                    counts["no_ctd"] += 1
                if rec["status"] == "rewritten":
                    timings.append(record["seconds"])
        records.append(rec)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "masks.csv", MASK_COLUMNS, records)
    emit(out, "masks", masks_lines(records, rows_by_id, timings, counts))
    return 0


def cmd_testgate(args):
    """The count of test and holdout rows that cannot be packed: unresolved in rows.csv, refused in masks.csv."""
    rows = read_csv(args.rows)
    bad = {row["sample_id"] for row in rows if row["role"] in ("test", "holdout") and row["status"] != "ok"}
    if args.masks and Path(args.masks).is_file():
        bad |= {rec["sample_id"] for rec in read_csv(args.masks) if rec["role"] in ("test", "holdout") and rec["status"] not in PACKED}
    print(len(bad))
    return 0


# ---------------------------------------------------------------------------------------------------- split
def validation_rank(person, salt):
    """A person's place in the validation draw: the first 8 bytes of a salted sha256, as the holdout ranks."""
    digest = hashlib.sha256(f"{VALIDATION_PREFIX}|{salt}|{person}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def draw_validation(pool, rule):
    """Per variant, the persons of the pool (person -> variant) with the lowest rank up to the rule's count;
    a variant whose pool is smaller gives what it has. (drawn set, drawn per variant, shortfall per variant)."""
    by_variant = defaultdict(list)
    for person, variant in pool.items():
        by_variant[variant].append(person)
    drawn, taken, short = set(), {}, {}
    for variant, want in rule["counts"].items():
        people = sorted(by_variant.get(variant, []), key=lambda person: validation_rank(person, rule["salt"]))[:want]
        drawn.update(people)
        taken[variant], short[variant] = len(people), want - len(people)
    return drawn, taken, short


def draw_digest(drawn):
    return hashlib.sha256("\n".join(sorted(drawn)).encode("utf-8")).hexdigest()


def g3_key(key):
    """A person key in the G3 split's spelling, as spinesurg-ct-nnunet tools/make_split.py norm_key writes it."""
    key = str(key).strip()
    if ":" not in key:
        return key
    corpus, person = key.split(":", 1)
    corpus = {"totalseg": "ts", "totalsegmentator": "ts", "sim": "spinalai", "carmlspine_real": "carmlspine",
              "geneva_hip": "geneva"}.get(corpus, corpus)
    if corpus == "ts":
        person = re.sub(r"^TS_", "", person)
    elif corpus == "ctsp" and person.isdigit():
        person = person.zfill(4)
    elif corpus == "nhanes" and person.isdigit():
        person = str(int(person)).zfill(5)
    elif corpus == "case" and person.isdigit():
        corpus, person = "carmlspine", f"case{person}"
    elif corpus == "gl" and person.isdigit():
        corpus, person = "verse", f"gl{person}"
    elif corpus == "verse" and person.isdigit():
        person = f"verse{person}"
    return f"{corpus}:{person}"


def g3_side(person, g3):
    """The G3 side of a person, resolved through raw_to_group and group_of to the group representative that
    side_of_person keys (make_split.py's OUTPUT CONTRACT); None for a person the split never placed."""
    key = g3_key(person)
    raw_to_group, group_of = g3.get("raw_to_group", {}), g3.get("group_of", {})
    representative = raw_to_group.get(person) or raw_to_group.get(key) or group_of.get(key) or key
    return g3.get("side_of_person", {}).get(representative)


def transitional(variant, subtype):
    """A person G3 calls transitional: any subtype but none or ordinary (the G1 subtypes, Castellvi, a
    sacralised L5 and a lumbar rib among them), or a variant of the count."""
    return subtype not in ORDINARY or variant in TRANSITIONAL


def assign(row, measured, side, drawn, distrusted, uncounted_mode):
    """(split, why) for a packed row, or None when the switch drops an uncounted row."""
    if row["role"] == "holdout":
        return "holdout", "holdout"
    if row["role"] == "test":
        return "test", "test"
    if row["collection"] in distrusted:
        verdict = ("uncounted", "distrusted")
    elif not measured["countable"]:
        verdict = ("uncounted", "uncountable")
    elif transitional(row["variant"], row["subtype"]) and side in ("val", "test"):
        return "g3_excluded", f"transitional on G3 {side}"
    elif row["person"] in drawn:
        return "val", "drawn"
    else:
        return "train", "train"
    return None if uncounted_mode == "drop" else verdict


def digest_differs(frozen, digest):
    """Whether a frozen draw, by its 16 or 64 hex digest, names another draw than this one."""
    given = str((frozen or {}).get("digest") or "").strip().lower()
    return bool(given) and not (len(given) >= 16 and digest.startswith(given))


def splits_lines(entries, drawn_counts, shortfalls, rule, digest, excluded, uncounted_mode, dropped):
    variants = ("L6", "T13", "four_lumbar", "both_L6_T13")
    groups = defaultdict(Counter)
    for entry in entries:
        key = (entry["collection"], entry["role"], entry["split"], "complete" if flag(entry["complete"]) else "partial")
        groups[key]["rows"] += 1
        groups[key][entry["variant"]] += 1
        groups[key]["countable"] += flag(entry["countable"])
    lines = ["## splits", "", "| collection | role | split | completeness | rows | " + " | ".join(variants) + " | countable |",
             "|---|---|---|---|---|" + "---|" * (len(variants) + 1)]
    for key, counts in sorted(groups.items()):
        lines.append("| " + " | ".join(key) + f" | {counts['rows']} | " + " | ".join(str(counts[v]) for v in variants)
                     + f" | {counts['countable']} |")
    measure = {key: Counter(entry[key] for entry in entries) for key in ("top_from", "sacrum_from")}
    splits = Counter(entry["split"] for entry in entries)
    lines += ["", f"- splits: {tally(splits, ('train', 'val', 'test', 'holdout', 'uncounted', 'g3_excluded'))}",
              f"- uncounted: {tally(Counter(entry['why'] for entry in entries if entry['split'] == 'uncounted'), ('distrusted', 'uncountable'))}"
              + (f"; {dropped} rows dropped by --uncounted drop" if uncounted_mode == "drop" else "; packed, trained on by nothing"),
              f"- G3: {len(excluded)} persons excluded, {sum(variant == 'normal' for variant in excluded.values())} of them variant normal",
              f"- validation: rule {rule['rank']}",
              f"- validation: salt {rule['salt']}; counts {json.dumps(rule['counts'])}; drawn "
              + ", ".join(f"{variant} {drawn_counts[variant]}" + (f" (short {shortfalls[variant]})" if shortfalls[variant] else "")
                          for variant in rule["counts"]) + f"; sha256 {digest[:16]}",
              f"- top_from: {tally(measure['top_from'], ('mask', 'ctd', 'none'))}; sacrum_from: "
              f"{tally(measure['sacrum_from'], ('mask', 'record', 'ctd', 'none'))}; gap {sum(flag(entry['gap']) for entry in entries)}"]
    return lines


def subject_disjoint(entries):
    """The persons that sit in two splits of one package, as packaging.py:370-376 would refuse."""
    sides = defaultdict(set)
    for entry in entries:
        sides[("complete" if flag(entry["complete"]) else "partial", entry["person"])].add(entry["split"])
    return sorted(person for (_, person), splits in sides.items() if len(splits) > 1)


def cmd_split(args):
    rows = {row["sample_id"]: row for row in read_csv(args.rows)}
    masks = [rec for rec in read_csv(args.masks) if rec["status"] in PACKED]
    g3, validation = read_json(args.g3), read_json(args.validation)
    distrusted = {name for name in args.distrust.split(",") if name}
    entries = []
    for rec in masks:
        row = rows[rec["sample_id"]]
        entry = dict(row, **{key: rec[key] for key in ("sample_id", "countable", "complete", "top_from", "sacrum_from", "gap")})
        entry["side"] = g3_side(row["person"], g3)
        entry["excluded"] = transitional(row["variant"], row["subtype"]) and entry["side"] in ("val", "test")
        entries.append(entry)
    pool = {entry["person"]: entry["variant"] for entry in entries
            if entry["role"] == "train" and flag(entry["countable"]) and entry["collection"] not in distrusted
            and not entry["excluded"] and not entry["fold"]}
    drawn, drawn_counts, shortfalls = draw_validation(pool, validation["rule"])
    digest = draw_digest(drawn)
    if digest_differs(validation.get("drawn"), digest):
        raise Failed("the validation draw differs from the frozen one")
    kept, excluded, dropped = [], {}, 0
    for entry in entries:
        measured = {"countable": flag(entry["countable"]), "complete": flag(entry["complete"])}
        verdict = assign(entry, measured, entry["side"], drawn, distrusted, args.uncounted)
        if verdict is None:
            dropped += 1
            continue
        entry["split"], entry["why"] = verdict
        if entry["split"] == "g3_excluded":
            excluded[entry["person"]] = entry["variant"]
        kept.append(entry)
    doubled = subject_disjoint(kept)
    if doubled:
        raise Failed(f"{len(doubled)} persons sit in two splits of one package")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "splits.csv", SPLIT_COLUMNS, kept)
    emit(out, "splits", splits_lines(kept, drawn_counts, shortfalls, validation["rule"], digest, excluded, args.uncounted, dropped))
    return 0


def cmd_trainval(args):
    """The persons of the train and val rows, for tools/anomaly_route.py check --holdout ... --list."""
    rows = read_csv(args.splits)
    persons = {split: sorted({row["person"] for row in rows if row["split"] == split}) for split in TRAINED}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "trainval.csv", ["person"], [{"person": person} for person in sorted(set(persons["train"]) | set(persons["val"]))])
    emit(out, "trainval", ["## trainval", "", f"- {len(set(persons['train']) | set(persons['val']))} persons "
                                               f"(train {len(persons['train'])}, val {len(persons['val'])})"])
    return 0


# ---------------------------------------------------------------------------------------------------- manifest
def parse_pair(text, what):
    parts = [part for part in re.split(r"[,\s]+", text.strip()) if part]
    if len(parts) != 2:
        raise Failed(f"--{what} takes two numbers")
    return [float(part) for part in parts]


def parse_crops(text):
    parts = [part for part in re.split(r"[,\s]+", text.strip()) if part]
    if len(parts) != 3 or not all(part.isdigit() and int(part) > 0 for part in parts):
        raise Failed("--crops takes three positive integers X,Y,Z")
    return [int(part) for part in parts]


def sample_of(entry, row, rec):
    """One FleXray sample: the person as subject_id, absolute image and label, the row's facts as metadata."""
    return {"sample_id": entry["sample_id"], "subject_id": entry["person"], "split": entry["split"],
            "image": str(Path(row["ct"]).resolve()), "label": str(Path(rec["dst"]).resolve()),
            "metadata": {"person": entry["person"], "collection": row["collection"], "case": row["case"],
                         "variant": row["variant"], "subtype": row["subtype"], "tier": row["tier"], "role": row["role"],
                         "fold": row["fold"], "countable": flag(rec["countable"]),
                         "completeness": "complete" if flag(rec["complete"]) else "partial",
                         "top_from": rec["top_from"], "sacrum_from": rec["sacrum_from"], "gap": flag(rec["gap"]),
                         "mask_kind": row["mask_kind"], "why": entry["why"], "segmenter": row.get("segmenter", "")}}


def cmd_manifest(args):
    if args.dataset not in DATASETS:
        raise Failed("the dataset is schwingnet_spine or schwingnet_spine_partial")
    window = parse_pair(args.hu, "hu")
    if not window[0] < window[1]:
        raise Failed("--hu takes an increasing low,high pair")
    crops = parse_crops(args.crops) if args.crops else None
    rows = {row["sample_id"]: row for row in read_csv(args.rows)}
    masks = {rec["sample_id"]: rec for rec in read_csv(args.masks) if rec["status"] in PACKED}
    wanted = DATASETS[args.dataset]
    samples = []
    for entry in read_csv(args.splits):
        rec = masks.get(entry["sample_id"])
        if rec is None or ("complete" if flag(rec["complete"]) else "partial") != wanted:
            continue
        samples.append(sample_of(entry, rows[entry["sample_id"]], rec))
    if crops:
        off = [s for s in samples if rows[s["sample_id"]]["dims"].split("x")[:2] != [str(crops[0]), str(crops[1])]]
        if off:
            raise Failed(f"{len(off)} rows are not {crops[0]} by {crops[1]} in plane")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = f"manifest-{args.dataset}"
    if not samples:
        emit(out, name, [f"## manifest {args.dataset}", "", "- no sample; no manifest written"])
        return 0
    manifest = {"schema_version": 1, "dataset_name": args.dataset, "dataset_type": "ct-seg",
                "stored_labels": {str(i): label for i, label in enumerate(CANONICAL)},
                "preprocessing": {"hu_window": [int(v) if v.is_integer() else v for v in window]}}
    if crops:
        manifest["crops"] = {"size": crops}
    manifest["samples"] = samples
    # JSON is YAML: json.dumps with an indent and ': ' separators is a flow document yaml.safe_load reads.
    text = json.dumps(manifest, indent=1) + "\n"
    (out / f"{name}.yml").write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    per_split = Counter(sample["split"] for sample in samples)
    emit(out, name, [f"## manifest {args.dataset}", "", f"- samples {len(samples)}: {tally(per_split)}",
                     f"- sha256 {digest[:16]}" + (f"; crops {'x'.join(map(str, crops))}" if crops else "; whole volumes")])
    return 0


# ---------------------------------------------------------------------------------------------------- size
def cmd_size(args):
    """The last line is '<total> <need> <how>' for size_and_admit: the uncompressed bytes every ok row lands
    (float16 image, uint8 label, uint8 mask) less the masks already written and verified, never a package."""
    rows = read_csv(args.rows)
    ok = [row for row in rows if row["status"] == "ok"]
    masks_dir = Path(args.landing) / "masks"
    total = verified = 0
    for row in ok:
        voxels = int(row["voxels"] or 0)
        total += voxels * PACKED_PER_VOXEL + ROW_OVERHEAD
        if sidecar_matches(masks_dir / f"{row['sample_id']}.json", row["mask"], masks_dir / f"{row['sample_id']}.nii.gz"):
            verified += voxels
    print(f"- payload_too_large: {sum(row['status'] == 'payload_too_large' for row in rows)} rows refused before the census")
    print(f"{total} {total - verified} header census of {len(ok)} CTs: float16 image, uint8 label and uint8 mask, uncompressed")
    return 0


# ---------------------------------------------------------------------------------------------------- main
def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("rows", help="resolve every row of the selection and the holdout to its CT and mask")
    for name in ("selection", "holdout", "data", "home", "registry", "harvest", "out"):
        one.add_argument(f"--{name}", required=True)
    one.add_argument("--segmenter", choices=SEGMENTERS, default="spineps")
    one = sub.add_parser("guard-list", help="the SPINEPS masks for spineps_ids.py check --strict")
    one.add_argument("--rows", required=True)
    one.add_argument("--out", required=True)
    one = sub.add_parser("testgate", help="print the count of test and holdout rows that cannot be packed")
    one.add_argument("--rows", required=True)
    one.add_argument("--masks")
    one = sub.add_parser("size", help="print '<total> <need> <how>' for the size rule's admission")
    one.add_argument("--rows", required=True)
    one.add_argument("--landing", required=True)
    one = sub.add_parser("rewrite", help="rewrite every mask to the canonical ids under the landing")
    one.add_argument("--rows", required=True)
    one.add_argument("--guard")
    one.add_argument("--masks", required=True)
    one.add_argument("--out", required=True)
    one = sub.add_parser("split", help="assign every packed row its split")
    for name in ("rows", "masks", "g3", "validation", "out"):
        one.add_argument(f"--{name}", required=True)
    one.add_argument("--distrust", default="ctsp")
    one.add_argument("--uncounted", choices=("pack", "drop"), default="pack")
    one = sub.add_parser("trainval", help="the train and val persons for the route check")
    one.add_argument("--splits", required=True)
    one.add_argument("--out", required=True)
    one = sub.add_parser("manifest", help="write one dataset's FleXray manifest")
    for name in ("splits", "masks", "rows", "dataset", "out"):
        one.add_argument(f"--{name}", required=True)
    one.add_argument("--hu", default=f"{HU_WINDOW[0]:g},{HU_WINDOW[1]:g}", help="low,high; spelled --hu=-1000,2000")
    one.add_argument("--crops", help="X,Y,Z: add FleXray's crops block, refused unless every row is X by Y in plane")
    return parser


COMMANDS = {"rows": cmd_rows, "guard-list": cmd_guard_list, "testgate": cmd_testgate, "size": cmd_size,
            "rewrite": cmd_rewrite, "split": cmd_split, "trainval": cmd_trainval, "manifest": cmd_manifest}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except Failed as failed:
        print(f"FAILED: {failed}", file=sys.stderr)
    except OSError as error:
        print(f"FAILED: a file could not be read or written ({error.strerror or 'unknown error'})", file=sys.stderr)
    except (json.JSONDecodeError, csv.Error):
        print("FAILED: an input file could not be parsed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
