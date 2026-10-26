"""The bordercall corpus on the grid: every SPINEPS mask with C2, named by counting from C2.

    python3 tools/bordercall_corpus.py inventory --tiers DIR --out DIR [--limit N]
    python3 tools/bordercall_corpus.py build --tiers DIR --moller DIR --out DIR [--limit N] [--workers N]
    python3 tools/bordercall_corpus.py report --out DIR

Why this exists. bordercall (OpenSpineConsortium/bordercall) names a vertebral border from the
shape of the bone and scores only records whose column can be counted from C2, since a name
nobody counted is a reader's call and not a fact. CTSpinoPelvic1K, which it was built on, is
a lumbar corpus with no C2, so the question it asks, which junction the shape names most
robustly in normal and anomalous spines, needs a full-spine corpus. The grid holds SPINEPS
masks for about 17,000 CTs, listed one row per CT by the transitional census in
$RS/ruleclass/tiers/tier1.tsv and tier2.tsv with the mask, its centroid file and whether its
ids are VerSe names or raw instance ids. Nothing is segmented again (the owner's word of
2026-10-25): this tool reads those masks and writes, for every countable one, a label volume
in bordercall's VerSe-native scheme whose names come from the count and nothing else.

How a level is named. The instances are ordered cranio-caudally by centroid. The one the
centroid file calls C2 (the dens makes it the one call a labeller gets right) is C2, and
every instance below it is named by its ordinal: the standard column C1 to C7, T1 to T12,
L1 to L6. The labeller's own names below C2 are never used for the truth, since VERIDAH
skips and over-calls levels (spinesurg-ct-nnunet's tools/spineps_ids.py says how, and the
census's DATA.md). A column with a gap between two instances wider than its neighbours'
spacing allows is not countable, since a missed body would shift every name below it, and is
set aside with its reason. Two bodies fused into one instance with its centroid between them,
or a sacrum instance that swallowed the lowest lumbar body (the census's CLASSIFIERS.md, rule
R9, saw L6 inside the sacrum instance in 7 of 18 CTSP cases read L6), leave no gap and pass
as countable one body short; the report says so, and nothing here can catch them.

The phenotype comes from an independent reading of the ribs: the Moller arm of the census
measured every rib on the TotalSegmentator output and assigned it to the vertebra it joins
(arms/moller_fast/<collection>/<case>_rib_measurements.csv). A vertebra bearing a rib over
38 mm on either side is rib-bearing, as the census's rule 1 reads it. Under the count-based
names a thirteenth rib-bearing body is "L1 bearing a rib" (bordercall's class lumbar_rib),
a column whose twelfth thoracic bears no rib is no_rib_T12, and six or four lumbar
identifiers are what the count says, four only with the sacrum in view, since a field that
ends at L4 says nothing about L5. A case with no rib reading is countable with its class
unknown unless the count alone settles it (six or four lumbar bodies), and the report says
how many.

Three namings are kept side by side for the owner's question of how many shape-versus-name
disagreements are counted anomalies: the count (the truth bordercall scores against), the
ribs (the independent arm) and VERIDAH's own names (the labeller, for the record).

The grid job (grid/bordercall.sbatch, the word `bordercall <stage>`) runs inventory and build,
then bordercall's own measure, border, breakout, sweep, plot and the Panjabi check over the
label tree, and writes the report the gate prints. Standard library plus numpy and nibabel,
which the SPINEPS environment on the grid has; spinesurg-ct-nnunet's tools/spineps_ids.py is
used for a raw mask's relabel through its centroid file where it can be imported, and a raw
mask is set aside where it cannot.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

# bordercall's VerSe-native scheme, repeated here so this file needs no import from the copy
CERVICAL_IDS = tuple(range(1, 8))
THORACIC_IDS = tuple(range(8, 20))
LUMBAR_IDS = tuple(range(20, 26))
STANDARD = CERVICAL_IDS + THORACIC_IDS + LUMBAR_IDS          # C1 ... L6 by ordinal
SACRUM_IDS = (26, 29)
T13_ID = 28
C2_ID = 2
NAMES = {}
for _i, _v in enumerate(CERVICAL_IDS, 1):
    NAMES[_v] = "C%d" % _i
for _i, _v in enumerate(THORACIC_IDS, 1):
    NAMES[_v] = "T%d" % _i
for _i, _v in enumerate(LUMBAR_IDS, 1):
    NAMES[_v] = "L%d" % _i
NAMES[T13_ID] = "T13"
NAMES[26] = "sacrum"
NAMES[29] = "sacrum"
VERTEBRA_IDS = STANDARD + (T13_ID,)
RIB_BEARING_MM = 38.0           # the census's rule 1: a rib over this (strictly) on either side makes the body rib-bearing
GAP_FACTOR = 1.8                # a centroid gap wider than this many times its neighbours' spacing is a missed body
GAP_NEIGHBOURS = 2              # the gaps on each side a gap is compared with (cervical bodies sit half as far apart as lumbar)
MIN_VOXELS = 500                # an instance smaller than this is a fragment, not a vertebra

TIER_COLUMNS = ("tier", "collection", "case_id", "person_key", "spineps_vert", "spineps_spine",
                "spineps_ctd", "spineps_ids", "spineps_store", "real_frames", "registry_flags")
ROW_FIELDS = ["case", "collection", "case_id", "person_key", "tier", "spineps_ids", "spineps_store",
              "status", "reason", "countable", "has_c1", "has_c2", "has_sacrum", "n_instances",
              "n_from_c2", "lowest_by_count", "topmost", "phenotype", "phenotype_known", "n_lumbar",
              "has_l6", "has_t13", "has_lumbar_rib", "lowest_rib_bearing", "lowest_rib_bearing_id",
              "first_rib_bearing", "n_rib_bearing", "veridah_lowest_rib_bearing", "veridah_l1_offset", "veridah_names_agree",
              "real_frames", "registry_flags", "label_file"]


# ---- reading the census's lists -----------------------------------------------------------

def read_tiers(tiers_dir):
    """Every row of tier1.tsv then tier2.tsv that names a SPINEPS mask, in a fixed order."""
    rows = []
    for name in ("tier1.tsv", "tier2.tsv"):
        path = Path(tiers_dir) / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                if r.get("spineps_vert"):
                    rows.append({k: r.get(k, "") for k in TIER_COLUMNS})
    rows.sort(key=lambda r: (r["tier"], r["collection"], r["case_id"]))
    return rows


def case_key(row):
    return "%s__%s" % (row["collection"], row["case_id"])


# ---- the centroid file ----------------------------------------------------------------------

def find_ctd(mask_path):
    p = Path(mask_path)
    stem = p.name
    for suffix in ("_seg-vert_msk.nii.gz", "_seg-vert_msk_veridah.nii.gz", ".nii.gz", ".nii"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    for cand in (p.with_name(stem + "_seg-vert_ctd.json"), p.with_name(stem + "_ctd.json"),
                 p.with_name(stem + "_seg-vert_msk_ctd.json")):
        if cand.exists():
            return str(cand)
    return ""


# ---- the mask ---------------------------------------------------------------------------------

def load_spineps_ids():
    """spinesurg-ct-nnunet's guard, where the grid has it; None elsewhere."""
    ssn = os.environ.get("SSN", os.path.expanduser("~/spinesurg-ct-nnunet"))
    tools = os.path.join(ssn, "tools")
    if not os.path.exists(os.path.join(tools, "spineps_ids.py")):
        return None
    if tools not in sys.path:
        sys.path.append(tools)
    try:
        import spineps_ids                                      # noqa: F401
        return spineps_ids
    except Exception:                                           # noqa: BLE001
        return None


def load_named_mask(row, guard):
    """(array in canonical orientation, affine, voxel size, {instance id: VERIDAH name id}, note).

    A verse_coded or relabelled mask is read as it is. A raw mask is relabelled in memory
    through its centroid file by the guard, as the census does, and set aside when the guard
    is not importable: a raw id read as a name is a plausible wrong answer."""
    import nibabel as nib
    import numpy as np

    vert = row["spineps_vert"]
    ctd = row.get("spineps_ctd") or find_ctd(vert)
    if row.get("spineps_ids") == "raw":
        if guard is None:
            raise SetAside("raw ids and no spineps_ids.py to relabel them through the centroid file")
        if not ctd or not os.path.exists(ctd):
            raise SetAside("raw ids and no centroid file")
        pts = guard.read_ctd(ctd)
        if not pts:
            raise SetAside("raw ids and an empty centroid file")
        a0, A0, _ = guard.load_mask(vert)
        semantic = None
        if row.get("spineps_spine") and os.path.exists(row["spineps_spine"]):
            sa, sA, _ = guard.load_mask(row["spineps_spine"])
            semantic = (sa, sA)
        try:
            arr, rep = guard.relabel_by_ctd(a0, A0, pts, semantic=semantic)
        except Exception as exc:                                # noqa: BLE001
            raise SetAside("relabel_by_ctd refused: %s" % str(exc)[:160]) from exc
        img = nib.Nifti1Image(np.asarray(arr).astype(np.int16), A0)
        note = "relabelled in memory"
    else:
        img = nib.load(vert)
        note = row.get("spineps_ids") or "as read"
    img = nib.as_closest_canonical(img)
    arr = np.asanyarray(img.dataobj).astype(np.int16)
    zoom = tuple(float(z) for z in img.header.get_zooms()[:3])
    return arr, img.affine, zoom, note


class SetAside(Exception):
    """A case the corpus leaves out, with its reason."""


def instances(arr, zoom):
    """[(VERIDAH id, superior centroid in mm, voxels)] cranial first, vertebrae only."""
    import numpy as np
    from scipy import ndimage

    ids = [int(v) for v in np.unique(arr) if v and int(v) in VERTEBRA_IDS]
    if not ids:
        return []
    coms = ndimage.center_of_mass(arr > 0, arr, ids)
    sizes = ndimage.sum(np.ones(arr.shape, np.int8), arr, ids)
    out = []
    for vid, com, size in zip(ids, coms, sizes):
        if size < MIN_VOXELS:
            continue
        out.append((vid, float(com[2]) * zoom[2], int(size)))
    out.sort(key=lambda t: -t[1])
    return out


def name_by_count(inst):
    """{VERIDAH id: count id} from C2 down, plus the facts the row records; SetAside when the
    column cannot be counted."""
    import numpy as np

    ids = [v for v, _, _ in inst]
    if C2_ID not in ids:
        raise SetAside("no C2 in the mask")
    pos = ids.index(C2_ID)
    if pos > 1:
        raise SetAside("%d instances above the one called C2" % pos)
    gaps = [inst[i][1] - inst[i + 1][1] for i in range(len(inst) - 1)]
    for i, g in enumerate(gaps):
        # against the neighbouring gaps, not the column's median: cervical bodies sit about half
        # as far apart as lumbar ones, so a missed cervical body is no wider than a lumbar gap
        near = [gaps[j] for j in range(max(0, i - GAP_NEIGHBOURS), min(len(gaps), i + GAP_NEIGHBOURS + 1)) if j != i]
        if near and g > GAP_FACTOR * float(np.median(near)):
            raise SetAside("a gap of %.0f mm between instances %d and %d (the spacing beside it %.0f mm)"
                           % (g, i + 1, i + 2, float(np.median(near))))
    mapping = {}
    for k, (vid, _, _) in enumerate(inst[pos:]):
        ordinal = 1 + k                                           # 1 is C2's place in STANDARD
        if ordinal >= len(STANDARD):
            raise SetAside("more than %d bodies below C2" % (len(STANDARD) - 2))
        mapping[vid] = STANDARD[ordinal]
    if pos == 1:
        mapping[ids[0]] = STANDARD[0]
    return mapping


def relabel(arr, mapping):
    import numpy as np

    out = np.zeros(arr.shape, np.int16)
    for src, dst in mapping.items():
        out[arr == src] = dst
    for sac in SACRUM_IDS:
        out[arr == sac] = 26
    return out


# ---- the ribs -----------------------------------------------------------------------------------

def read_ribs(moller_dir, row):
    """{VERIDAH vertebra id: longest rib in mm} from the Moller arm's table, upstream variant,
    or None when the arm never ran on this CT."""
    d = Path(moller_dir) / row["collection"]
    path = d / ("%s_rib_measurements.csv" % row["case_id"])
    if not path.exists():
        return None
    longest = defaultdict(float)
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("variant", "upstream") != "upstream":
                continue
            try:
                vid = int(float(r.get("vertebra", "")))
                length = float(r.get("rib_length") or 0.0)
            except ValueError:
                continue
            longest[vid] = max(longest[vid], length)
    return dict(longest)


def lumbosacral_class(n_lumbar, has_l6, has_sacrum):
    """What the count alone says of the lumbosacral end: a sixth lumbar body is one whether or
    not the sacrum is in view; four lumbar bodies, or the usual five, are a class only with the
    sacrum in view, since a field that ends at L4 says nothing about L5. Empty when it cannot."""
    if has_l6 or n_lumbar >= 6:
        return "six_lumbar"
    if not has_sacrum:
        return ""
    if n_lumbar == 4:
        return "four_lumbar"
    if n_lumbar == 5:
        return "typical"
    return ""


def phenotype_of(mapping, ribs, has_sacrum=True):
    """bordercall's five classes from the count names and the independent rib reading. ribs is
    None where the arm never ran on the CT and empty where its table holds no rib, which on a
    full spine means the reading failed; both leave the ribs unread."""
    present = set(mapping.values())
    lumbar = sorted(v for v in LUMBAR_IDS if v in present)
    r = {"n_lumbar": len(lumbar), "has_l6": int(25 in present), "has_t13": 0,
         "has_lumbar_rib": 0, "lowest_rib_bearing": "", "lowest_rib_bearing_id": "",
         "first_rib_bearing": "", "n_rib_bearing": "", "phenotype": "", "phenotype_known": 0}
    ls = lumbosacral_class(r["n_lumbar"], r["has_l6"], has_sacrum)
    if not ribs:
        # the count alone settles the lumbosacral anomalies; typical and the rib classes need ribs
        r["phenotype"] = ls if ls in ("six_lumbar", "four_lumbar") else ""
        return r
    bearing = [mapping[v] for v, length in ribs.items() if length > RIB_BEARING_MM and v in mapping]
    r["n_rib_bearing"] = len(bearing)
    r["phenotype_known"] = 1
    if bearing:
        low = max(bearing)
        r["lowest_rib_bearing"], r["lowest_rib_bearing_id"] = NAMES[low], low
        r["first_rib_bearing"] = NAMES[min(bearing)]
        r["has_lumbar_rib"] = int(low in LUMBAR_IDS)
    rb = r["lowest_rib_bearing"]
    if r["has_lumbar_rib"]:
        r["phenotype"] = "lumbar_rib"
    elif rb and rb != "T12":
        r["phenotype"] = "no_rib_T12"
    else:
        r["phenotype"] = ls                     # six_lumbar, four_lumbar, typical, or unknown without the sacrum
    return r


def veridah_record(inst, mapping, ribs):
    """What the labeller itself said, for the record: whether its names agree with the count
    at every level, how far its L1 sits from the count's, and its own lowest rib-bearing body."""
    agree = all(vid == cid for vid, cid in mapping.items())
    offset = ""
    if 20 in mapping:
        count_pos = [cid for _, cid in sorted(mapping.items(), key=lambda t: t[1])]
        offset = str(count_pos.index(mapping[20]) - count_pos.index(20)) if 20 in count_pos else ""
    low = ""
    if ribs:
        bearing = [v for v, length in ribs.items() if length > RIB_BEARING_MM and v in NAMES]
        if bearing:
            low = NAMES[max(bearing, key=lambda v: STANDARD.index(v) if v in STANDARD else 99)]
    return {"veridah_names_agree": int(agree), "veridah_l1_offset": offset,
            "veridah_lowest_rib_bearing": low}


# ---- one case --------------------------------------------------------------------------------------

def one(args):
    """One tier row -> its record, and its label volume written when it is countable."""
    row, moller_dir, labels_dir, write = args
    rec = {k: "" for k in ROW_FIELDS}
    rec.update(case=case_key(row), collection=row["collection"], case_id=row["case_id"],
               person_key=row["person_key"], tier=row["tier"], spineps_ids=row["spineps_ids"],
               spineps_store=row["spineps_store"], real_frames=row["real_frames"],
               registry_flags=row["registry_flags"], countable=0)
    guard = load_spineps_ids()
    try:
        if not os.path.exists(row["spineps_vert"]):
            raise SetAside("mask file missing")
        arr, affine, zoom, note = load_named_mask(row, guard)
        inst = instances(arr, zoom)
        rec["n_instances"] = len(inst)
        present = {v for v, _, _ in inst}
        rec["has_c1"] = int(1 in present)
        rec["has_c2"] = int(C2_ID in present)
        rec["has_sacrum"] = int(any((arr == s).any() for s in SACRUM_IDS))
        mapping = name_by_count(inst)
    except SetAside as exc:
        rec.update(status="set_aside", reason=str(exc))
        return rec
    except Exception as exc:                                        # noqa: BLE001
        rec.update(status="error", reason="%s: %s" % (type(exc).__name__, str(exc)[:160]))
        return rec
    count_ids = sorted(mapping.values())
    rec.update(status="countable", countable=1, n_from_c2=sum(1 for c in count_ids if c >= C2_ID),
               lowest_by_count=NAMES[max(count_ids)], topmost=NAMES[min(count_ids)], reason=note)
    ribs = read_ribs(moller_dir, row) if moller_dir else None
    rec.update(phenotype_of(mapping, ribs, has_sacrum=bool(rec["has_sacrum"])))
    rec.update(veridah_record(inst, mapping, ribs))
    if write:
        import nibabel as nib
        out = Path(labels_dir) / ("%s_label.nii.gz" % rec["case"])
        nib.save(nib.Nifti1Image(relabel(arr, mapping), affine), str(out))
        rec["label_file"] = str(out)
    return rec


# ---- the commands --------------------------------------------------------------------------------------

def write_rows(rows, path):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ROW_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_phenotype(rows, path, known_only):
    """bordercall's phenotype.csv, its own columns: every countable case, its phenotype empty
    where the ribs were not read and the count settles nothing, since bordercall's breakout and
    plot read a case absent from the file as a typical column; or only the ones whose ribs were
    read, for the record."""
    fields = ["case", "phenotype", "countable", "has_c2", "topmost", "n_lumbar", "has_l6",
              "has_t13", "has_lumbar_rib", "lowest_rib_bearing", "lowest_rib_bearing_id",
              "first_rib_bearing", "n_from_c2", "has_sacrum", "phenotype_known", "collection", "error"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            if r["countable"] and (r["phenotype_known"] or not known_only):
                w.writerow(dict(r, error=""))


def cmd_build(a):
    rows = read_tiers(a.tiers)
    if a.collections:
        keep = set(a.collections.split(","))
        rows = [r for r in rows if r["collection"] in keep]
    labels = Path(a.out) / "labels"
    labels.mkdir(parents=True, exist_ok=True)
    print("%d census rows with a SPINEPS mask; stopping after %s countable cases or %d rows"
          % (len(rows), a.limit or "every", a.scan or len(rows)), flush=True)
    rows = rows[: a.scan] if a.scan else rows
    records, countable, broken = [], 0, ""
    jobs = ((r, a.moller, str(labels), not a.inventory) for r in rows)
    try:
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            for i, rec in enumerate(ex.map(one, jobs, chunksize=2), 1):
                records.append(rec)
                countable += rec["countable"]
                if i % 100 == 0:
                    print("  %d rows read, %d countable" % (i, countable), flush=True)
                if a.limit and countable >= a.limit:
                    print("  the limit of %d countable cases is reached after %d rows" % (a.limit, i), flush=True)
                    ex.shutdown(cancel_futures=True)
                    break
    except BrokenProcessPool as exc:
        # a worker killed outside Python (out of memory, a crash in a C extension) ends the pool;
        # what was read is written, so the hours are not lost, and the build is still a failure
        broken = "the worker pool broke after %d rows (%s); the rows read so far are written" % (len(records), exc)
        print(broken, flush=True)
    records.sort(key=lambda r: r["case"])
    write_rows(records, Path(a.out) / "corpus.csv")
    write_phenotype(records, Path(a.out) / "phenotype.csv", known_only=False)
    write_phenotype(records, Path(a.out) / "phenotype_ribs_read.csv", known_only=True)
    print(summary(records))
    if broken:
        print("FAILED: " + broken)
        return 1
    return 0


def summary(records):
    """Counts with denominators, by store and overall, for the report."""
    lines = []
    n = len(records)
    c = Counter(r["status"] for r in records)
    lines.append("rows read %d: countable %d, set aside %d, errors %d"
                 % (n, c["countable"], c["set_aside"], c["error"]))
    # one line per kind of reason: the millimetres and instance numbers of a message are not kinds
    by_reason = Counter(re.sub(r"\d+(\.\d+)?", "N", r["reason"].split(" (")[0].split(":")[0])
                        for r in records if r["status"] != "countable")
    for reason, k in by_reason.most_common(12):
        lines.append("  set aside, %s: %d" % (reason, k))
    lines.append("by collection (rows / countable / with ribs read):")
    per = defaultdict(lambda: [0, 0, 0])
    for r in records:
        p = per[r["collection"]]
        p[0] += 1
        p[1] += r["countable"] or 0
        p[2] += (r["countable"] and r["phenotype_known"]) or 0
    for coll, (rows_n, cnt, ribs) in sorted(per.items(), key=lambda t: -t[1][1]):
        lines.append("  %-28s %6d %6d %6d" % (coll, rows_n, cnt, ribs))
    ids = Counter(r["spineps_ids"] for r in records if r["countable"])
    lines.append("countable by id state: " + ", ".join("%s %d" % t for t in ids.most_common()))
    ph = Counter(r["phenotype"] or ("unknown (no rib reading)" if not r["phenotype_known"]
                                    else "unknown (sacrum not in view)") for r in records if r["countable"])
    lines.append("phenotype of the countable cases (denominator %d):" % c["countable"])
    for k, v in ph.most_common():
        lines.append("  %-30s %6d" % (k, v))
    counts = Counter(int(r["n_from_c2"]) for r in records if r["countable"] and int(r["has_sacrum"] or 0))
    lines.append("bodies from C2 to the last presacral one, cases with the sacrum in view "
                 "(the true count; 23 is the usual column; a sacrum instance that swallowed the "
                 "lowest lumbar body, or two bodies fused into one instance, count one short unseen):")
    for k, v in sorted(counts.items()):
        lines.append("  %2d bodies: %d" % (k, v))
    vd = Counter((r["veridah_names_agree"], r["veridah_l1_offset"]) for r in records if r["countable"])
    lines.append("the labeller's own names against the count (agree at every level, its L1 offset in levels):")
    for (agree, off), v in sorted(vd.items(), key=lambda t: -t[1])[:8]:
        lines.append("  agree %s, L1 offset %-3s %d" % (agree, off or "-", v))
    return "\n".join(lines)


def cmd_report(a):
    with open(Path(a.out) / "corpus.csv", encoding="utf-8", newline="") as fh:
        records = list(csv.DictReader(fh))
    for r in records:
        for k in ("countable", "phenotype_known", "has_sacrum", "n_from_c2", "n_lumbar", "has_l6"):
            r[k] = int(r.get(k) or 0)
    print(summary(records))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, inventory in (("inventory", True), ("build", False)):
        p = sub.add_parser(name)
        p.add_argument("--tiers", required=True, help="the folder holding tier1.tsv and tier2.tsv")
        p.add_argument("--moller", default="", help="the Moller arm's root, arms/moller_fast")
        p.add_argument("--out", required=True)
        p.add_argument("--limit", type=int, default=0, help="stop after this many countable cases")
        p.add_argument("--scan", type=int, default=0, help="read at most this many rows")
        p.add_argument("--collections", default="", help="only these collections, comma-joined")
        p.add_argument("--workers", type=int, default=4)
        p.set_defaults(fn=cmd_build, inventory=inventory)
    p = sub.add_parser("report")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
