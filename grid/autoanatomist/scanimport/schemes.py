"""Which label means which vertebra, scheme by scheme: the one place a raw label value is read.

A label volume written under one scheme and read under another gives finite, plausible, wrong
names (archive/bordercall/scheme.py tells how that happened here once). So every reader in this
package resolves a raw value through `level_of(scheme, value)` and nothing else, and every
scheme says what it cannot express: a scheme with no L6 or T13 label cannot record those
anomalies, so a column read under it is never called typical on the strength of their absence.

The schemes, with where each map comes from:

- verse: the VerSe alphabet (C1 to C7 = 1 to 7, T1 to T12 = 8 to 19, L1 to L5 = 20 to 24, L6 =
  25, sacrum = 26, coccyx = 27, T13 = 28). VerSe's own masks and SPINEPS's instance masks with
  VERIDAH labelling are written in it (archive/bordercall/SPINEPS_MAPPING.md; SchwingNet
  src/schwingnet/segmenters.py, VERSE).
- spineps: the same alphabet for the instance volume, and SPINEPS's subregion labels for the
  parts of each vertebra (archive/bordercall/spineps_map.py).
- ctspinopelvic: CTSpinoPelvic1K v11, VerSe-native for the vertebrae, with ribs 34 to 46 left and
  47 to 59 right (rib n at 33 + n and 46 + n), lumbar ribs 60 and 61, and 29 a retired S1 read as
  sacrum (archive/bordercall/scheme.py).
- moose: MOOSE's stored ids as FleXray's configs/datasets/MOOSE.yml stores them (C1 to C7 = 59 to
  65, T1 to T12 = 66 to 77, L1 to L5 = 78 to 82, L6 = 83, sacrum = 86, ribs 32 to 57; no T13;
  SchwingNet src/schwingnet/segmenters.py, MOOSE_STORED, held equal to the file by its tests).
- totalseg: TotalSegmentator's structure names, read from a folder of one binary mask per
  structure (vertebrae_C1 ... vertebrae_L5, vertebrae_S1, sacrum, rib_left_1 ... rib_right_12),
  as its release ships them; it has no L6 and no T13 (TotalSegmentator's README, read in
  SchwingNet docs/research/flepp-and-killeen-critique.md). A multilabel TotalSegmentator volume
  is read with its own class map given as JSON (`--label-map`), never with ids assumed here,
  since the ids differ between its versions.
- enhance: ENHANCE.PET 1.6k's vertebra group, clin_ct_vertebrae in the release's labels.json (C1
  to C7 = 1 to 7, T1 to T12 = 8 to 19, L1 to L6 = 20 to 25, hips 26 and 27, sacrum 28; no T13;
  read from the public bucket enhance-pet-1-6k on 2026-10-27, holdings/gold-tier-3.md). Its ids up
  to 25 are VerSe's, and 26 to 28 are not: read as VerSe, its hips would be a sacrum and a coccyx
  and its sacrum a T13, so `problems` names a VerSe read that holds 26, 27 and 28 together.
"""
from __future__ import annotations

from typing import Dict, Optional

from . import CERVICAL, LUMBAR, THORACIC

SCHEMES = ("verse", "spineps", "ctspinopelvic", "moose", "totalseg", "enhance")

VERSE: Dict[int, str] = {**{n: "C%d" % n for n in range(1, 8)},
                         **{7 + n: "T%d" % n for n in range(1, 13)},
                         **{19 + n: "L%d" % n for n in range(1, 6)},
                         25: "L6", 26: "sacrum", 28: "T13"}

CTSPINOPELVIC: Dict[int, str] = {**VERSE, 29: "sacrum"}
CTSPINOPELVIC_RIBS: Dict[int, int] = {**{33 + n: n for n in range(1, 14)}, **{46 + n: n for n in range(1, 14)}}

ENHANCE: Dict[int, str] = {**{n: "C%d" % n for n in range(1, 8)},
                           **{7 + n: "T%d" % n for n in range(1, 13)},
                           **{19 + n: "L%d" % n for n in range(1, 7)},
                           28: "sacrum"}
CTSPINOPELVIC_LUMBAR_RIBS = (60, 61)

MOOSE: Dict[int, str] = {**{58 + n: "C%d" % n for n in range(1, 8)},
                         **{65 + n: "T%d" % n for n in range(1, 13)},
                         **{77 + n: "L%d" % n for n in range(1, 7)},
                         86: "sacrum"}
MOOSE_RIBS: Dict[int, int] = {**{31 + n: n for n in range(1, 14)}, **{44 + n: n for n in range(1, 14)}}

TOTALSEG_FILES: Dict[str, str] = {**{"vertebrae_C%d" % n: "C%d" % n for n in range(1, 8)},
                                  **{"vertebrae_T%d" % n: "T%d" % n for n in range(1, 13)},
                                  **{"vertebrae_L%d" % n: "L%d" % n for n in range(1, 6)},
                                  "vertebrae_S1": "sacrum", "sacrum": "sacrum"}
TOTALSEG_RIB_FILES: Dict[str, int] = {**{"rib_left_%d" % n: n for n in range(1, 13)},
                                      **{"rib_right_%d" % n: n for n in range(1, 13)}}

# SPINEPS subregion labels (archive/bordercall/spineps_map.py, from SPINEPS's README)
SUB_ARCUS, SUB_SPINOSUS, SUB_COSTAL_L, SUB_COSTAL_R = 41, 42, 43, 44
SUB_CORPUS, SUB_ENDPLATE_SUP, SUB_ENDPLATE_INF = 49, 52, 53
SUB_CANAL, SUB_CORD = 61, 60
SUB_BODY = (SUB_CORPUS, SUB_ENDPLATE_SUP, SUB_ENDPLATE_INF)

# what each scheme can say: a sixth lumbar body, a thirteenth rib-bearing body, ribs at all
EXPRESSES: Dict[str, Dict[str, bool]] = {
    "verse": {"L6": True, "T13": True, "ribs": False},
    "spineps": {"L6": True, "T13": True, "ribs": False},
    "ctspinopelvic": {"L6": True, "T13": True, "ribs": True},
    "moose": {"L6": True, "T13": False, "ribs": True},
    "totalseg": {"L6": False, "T13": False, "ribs": True},
    "enhance": {"L6": True, "T13": False, "ribs": False},
}

VERTEBRAE = set(CERVICAL + THORACIC + LUMBAR)


def table_of(scheme: str) -> Dict[int, str]:
    if scheme in ("verse", "spineps"):
        return VERSE
    if scheme == "ctspinopelvic":
        return CTSPINOPELVIC
    if scheme == "moose":
        return MOOSE
    if scheme == "enhance":
        return ENHANCE
    raise ValueError("scheme %r has no id table here; totalseg is read by file name or with --label-map" % scheme)


def level_of(scheme: str, value: int, label_map: Optional[Dict[int, str]] = None) -> Optional[str]:
    """The level a raw label value names under a scheme, None for anything that is not a
    vertebra or the sacrum. A label map given by the caller (a multilabel TotalSegmentator volume's
    class map, say) wins, its names read as TotalSegmentator's structure names."""
    if label_map is not None:
        name = label_map.get(int(value))
        return TOTALSEG_FILES.get(name, name if name in VERTEBRAE or name == "sacrum" else None)
    return table_of(scheme).get(int(value))


def rib_of(scheme: str, value: int) -> Optional[int]:
    """The rib number a raw value names, for the schemes that label ribs."""
    if scheme == "ctspinopelvic":
        return CTSPINOPELVIC_RIBS.get(int(value))
    if scheme == "moose":
        return MOOSE_RIBS.get(int(value))
    return None


def problems(scheme: str, present: Dict[int, int]) -> list:
    """In words, what about the values present in a volume does not fit the scheme: a value the
    scheme does not know among the low ids, or no vertebra at all. `present` maps value to voxels."""
    out = []
    if scheme not in SCHEMES:
        return ["unknown scheme %r (known: %s)" % (scheme, ", ".join(SCHEMES))]
    if scheme == "totalseg":
        return out
    table = table_of(scheme)
    named = [v for v in present if v in table]
    if not named:
        out.append("no value in the volume names a vertebra under %s; check the scheme" % scheme)
    if scheme in ("verse", "spineps"):
        odd = sorted(v for v in present if 0 < v < 100 and v not in table and v != 27)
        if odd:
            out.append("values %s are not VerSe vertebra ids; the volume may be in another scheme" % odd)
        if all(v in present for v in (26, 27, 28)):
            out.append("values 26, 27 and 28 together look like ENHANCE.PET's hips and sacrum, not a VerSe "
                       "sacrum, coccyx and T13; read the volume as enhance")
    return out
