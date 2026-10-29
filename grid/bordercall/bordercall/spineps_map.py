"""Panjabi's measurements on a SPINEPS segmentation: what maps, and what does not.

    python spineps_map.py --table                       # print the mapping and stop
    python spineps_map.py --subregion sub.nii.gz --instance inst.nii.gz --out m.csv

SPINEPS (https://github.com/Hendrik-code/spineps) emits two masks. The subregion mask names
parts of a vertebra; the instance mask says which vertebra each voxel belongs to. Together
they give the structures Panjabi measured on dry bone, so his tables become a reference a
segmentation can be held against rather than a number in a paper.

THE IDENTIFIERS ALREADY AGREE. With VERIDAH labeling, SPINEPS writes 1 = C1, 2-7 = C2-C7,
8-19 = T1-T12, 28 = T13, 20 = L1, 21-25 = L2-L6, 26 = sacrum. That is the VerSe-native scheme
in `scheme.py`, identifier for identifier, so a SPINEPS+VERIDAH instance mask needs no
remapping for this package. Without VERIDAH the instance labels are arbitrary indices and
mean nothing anatomically -- `run.py scheme` will say so.

WHAT MAPS CLEANLY, AND THE ONE THAT DOES NOT. Five of Panjabi's structures have their own
SPINEPS label, so the measurement is a geometric extent of a labelled region. The PEDICLE
does not: SPINEPS labels the whole posterior arch as 41 Arcus_Vertebrae and never isolates
the pedicle, so PDW and PDH cannot be read off it. The arch includes the laminae and the
process bases, whose extents are larger than and unrelated to the pedicle waist. Measuring
41's extent and calling it a pedicle width would return a finite, plausible, wrong number --
the exact failure this programme keeps meeting. It is refused here, with the two honest ways
forward named in SPINEPS_MAPPING.md.

A MAXIMUM EXTENT IS NOT ALWAYS A DIAMETER. Panjabi measured named chords on dry bone with a
morphometer. For the end-plate widths and depths and for the canal, the named chord IS the
maximum extent of that structure in that axis, so an extent is faithful. For VBHp it is not:
that is the height of the body at its POSTERIOR wall, not the tallest column anywhere in the
body, and the two differ in a wedged or collapsed vertebra -- which is exactly where the
measurement matters. VBHp is therefore measured in a posterior slab, not as a maximum.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np

# ---- SPINEPS subregion labels (from its README) -----------------------------------------
ARCUS = 41
SPINOSUS = 42
COSTAL_L, COSTAL_R = 43, 44
SUP_ART_L, SUP_ART_R = 45, 46
INF_ART_L, INF_ART_R = 47, 48
CORPUS = 49
ENDPLATE_SUP = 52
ENDPLATE_INF = 53
SPINAL_CORD = 60
SPINAL_CANAL = 61
ENDPLATE_UNASSIGNED = 62
DISC = 100
SACRUM = 26
DENS = 51          # CT only

SUBREGION_NAMES = {
    41: "Arcus_Vertebrae", 42: "Spinosus_Process", 43: "Costal_Process_Left",
    44: "Costal_Process_Right", 45: "Superior_Articular_Left",
    46: "Superior_Articular_Right", 47: "Inferior_Articular_Left",
    48: "Inferior_Articular_Right", 49: "Vertebra_Corpus_border",
    51: "Dens_axis", 52: "Vertebral_Body_Endplate_Superior",
    53: "Vertebral_Body_Endplate_Inferior", 60: "Spinal_Cord", 61: "Spinal_Canal",
    62: "Endplate_unassigned", 100: "Vertebra_Disc", 26: "Sacrum",
    70: "Sacrum_Sacral_Ala_Left", 71: "Sacrum_Sacral_Ala_Right",
    72: "Sacrum_Posterior_Sacral_Elements", 73: "Sacrum_Body", 74: "Sacrum_Endplate",
    80: "Metal",
}

# ---- the mapping, which is the point of this file ---------------------------------------
# measure -> (Panjabi mnemonic, what he measured, SPINEPS label(s), how, computable)
MAPPING = [
    ("endplate", "EPWu", "upper end-plate width, left to right",
     (ENDPLATE_SUP,), "lateral extent of the superior end-plate label", True),
    ("endplate_depth", "EPDu", "upper end-plate depth, front to back",
     (ENDPLATE_SUP,), "anteroposterior extent of the superior end-plate label", True),
    ("endplate_lower", "EPWl", "lower end-plate width",
     (ENDPLATE_INF,), "lateral extent of the inferior end-plate label", True),
    ("endplate_lower_depth", "EPDl", "lower end-plate depth",
     (ENDPLATE_INF,), "anteroposterior extent of the inferior end-plate label", True),
    ("h_post", "VBHp", "body height at the POSTERIOR wall",
     (CORPUS,), "median column height in the posterior 20 % of the body, NOT a maximum",
     True),
    ("canal_w", "SCW", "spinal canal width",
     (SPINAL_CANAL,), "lateral extent of the canal label at this vertebra", True),
    ("canal_ap", "SCD", "spinal canal depth",
     (SPINAL_CANAL,), "anteroposterior extent of the canal label at this vertebra", True),
    ("tp_span", "TPW", "transverse process tip to tip",
     (COSTAL_L, COSTAL_R), "lateral extent of the two costal process labels together",
     True),
    ("spinous_length", "SPL", "spinous process length",
     (SPINOSUS,), "from the body centroid to the farthest spinous voxel", True),
    ("pedicle", "PDW", "pedicle width at its waist",
     (ARCUS,), "NOT COMPUTABLE: 41 is the whole arch, the pedicle is not labelled", False),
    ("pedicle_h", "PDH", "pedicle height at its waist",
     (ARCUS,), "NOT COMPUTABLE: 41 is the whole arch, the pedicle is not labelled", False),
]


def print_table():
    print("Panjabi measurement -> SPINEPS subregion label\n")
    print("  %-22s %-6s %-46s %s" % ("measure", "mnem", "SPINEPS label(s)", "ok"))
    for name, mnem, _what, labels, _how, ok in MAPPING:
        lab = ", ".join("%d %s" % (l, SUBREGION_NAMES.get(l, "?")) for l in labels)
        print("  %-22s %-6s %-46s %s" % (name, mnem, lab[:46], "yes" if ok else "NO"))
    print("\n  The two marked NO are refused rather than approximated. SPINEPS labels the")
    print("  whole posterior arch as 41 and never isolates the pedicle; an extent of 41 is")
    print("  not a pedicle width, and returning one would be a plausible wrong number.")
    print("  SPINEPS_MAPPING.md names the two honest ways to get the pedicle.")


# ---- measurement -------------------------------------------------------------------------
def _extent_mm(idx, axis, spacing):
    """Full extent of a voxel set along one axis, in mm."""
    if len(idx) < 2:
        return None
    return float(idx[:, axis].max() - idx[:, axis].min() + 1) * spacing[axis]


def measure_vertebra(sub, inst, vid, spacing, axes):
    """Panjabi-comparable measures for one vertebra, in mm. RAS axes assumed.

    `axes` maps anatomical direction to array axis: (lr, ap, si).
    """
    lr, ap, si = axes
    m = inst == vid
    if m.sum() < 50:
        return {}
    out = {}
    here = np.zeros_like(sub, dtype=bool)
    here[m] = True

    for name, mnem, _w, labels, _h, ok in MAPPING:
        if not ok:
            continue
        sel = np.zeros_like(here)
        for lab in labels:
            sel |= (sub == lab) & here
        idx = np.argwhere(sel)
        if len(idx) < 20:
            continue
        if name in ("endplate", "endplate_lower", "canal_w", "tp_span"):
            v = _extent_mm(idx, lr, spacing)
        elif name in ("endplate_depth", "endplate_lower_depth", "canal_ap"):
            v = _extent_mm(idx, ap, spacing)
        elif name == "h_post":
            v = _posterior_height(sel, ap, si, spacing)
        elif name == "spinous_length":
            body = np.argwhere((sub == CORPUS) & here)
            if len(body) < 20:
                continue
            c = body.mean(0)
            d = np.sqrt((((idx - c) * np.asarray(spacing)) ** 2).sum(1))
            v = float(d.max())
        else:
            continue
        if v is not None:
            out[name] = round(v, 2)
    return out


def _posterior_height(body, ap, si, spacing):
    """Height of the body at its posterior wall: the median column height in the
    posterior fifth, not the tallest column anywhere. Panjabi's VBHp is a named chord at
    the posterior wall, and in a wedged body the maximum is somewhere else entirely."""
    idx = np.argwhere(body)
    if len(idx) < 40:
        return None
    # posterior is the LOW end of the AP axis in RAS (+y is anterior)
    cut = np.percentile(idx[:, ap], 20)
    sel = idx[idx[:, ap] <= cut]
    if len(sel) < 20:
        return None
    cols = {}
    for row in sel:
        k = (row[0], row[1], row[2])
        key = tuple(v for a, v in enumerate(k) if a != si)
        lo, hi = cols.get(key, (row[si], row[si]))
        cols[key] = (min(lo, row[si]), max(hi, row[si]))
    heights = [(hi - lo + 1) * spacing[si] for lo, hi in cols.values()]
    return float(np.median(heights)) if heights else None


def axes_from(img):
    """(lr, ap, si) array axes of a canonicalised image. ANALYSE in RAS; never write back."""
    import nibabel as nib
    codes = nib.aff2axcodes(img.affine)
    want = {"R": 0, "L": 0, "A": 1, "P": 1, "S": 2, "I": 2}
    out = [None, None, None]
    for ax, c in enumerate(codes):
        out[want[c]] = ax
    if any(o is None for o in out):
        raise SystemExit("cannot read anatomical axes from %r" % (codes,))
    return tuple(out)


def run(subregion, instance, out_csv, levels=None):
    import nibabel as nib
    si = nib.as_closest_canonical(nib.load(subregion))     # ANALYSE only
    ii = nib.as_closest_canonical(nib.load(instance))
    sub = np.asanyarray(si.dataobj)
    inst = np.asanyarray(ii.dataobj)
    if sub.shape != inst.shape:
        raise SystemExit("subregion %s and instance %s have different shapes"
                         % (sub.shape, inst.shape))
    spacing = np.asarray(si.header.get_zooms()[:3], float)
    axes = axes_from(si)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import scheme as S

    ids = sorted({int(v) for v in np.unique(inst) if 0 < v < 100})
    rows = []
    for vid in ids:
        name = S.name_of(vid)
        if not name or (levels and name not in levels):
            continue
        d = measure_vertebra(sub, inst, vid, spacing, axes)
        if d:
            d["level"] = name
            rows.append(d)
    if not rows:
        raise SystemExit("no vertebra could be measured; check the instance labels "
                         "(VERIDAH labelling is required for them to mean anything)")
    cols = ["level"] + [n for n, _m, _w, _l, _h, ok in MAPPING if ok]
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("wrote %s  (%d vertebrae: %s)"
          % (out_csv, len(rows), ", ".join(r["level"] for r in rows)))
    print("  pedicle width and height are NOT in this file: see the mapping table")
    return 0


def main() -> int:
    ap_ = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap_.add_argument("--table", action="store_true", help="print the mapping and stop")
    ap_.add_argument("--subregion", help="SPINEPS subregion mask")
    ap_.add_argument("--instance", help="SPINEPS instance mask (VERIDAH labelled)")
    ap_.add_argument("--out", default="spineps_measures.csv")
    a = ap_.parse_args()
    if a.table or not (a.subregion and a.instance):
        print_table()
        return 0
    return run(a.subregion, a.instance, a.out)


if __name__ == "__main__":
    sys.exit(main())
