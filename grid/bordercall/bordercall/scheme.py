"""The identifier scheme, in one place, and a way to check a corpus against it.

EVERY OTHER FILE IMPORTS ITS IDENTIFIERS FROM HERE. That is the point: a fixed map scattered
through five files is how a corpus gets measured on the wrong bone. This programme has
already shipped a release whose pelvic incidence was computed against a legacy map, where the
only symptom was a quality flag reporting too few voxels in a structure that was plainly
there, and where resolving "femur_left" returned T4. A wrong map does not raise. It returns a
finite, plausible, wrong number.

So before measuring a new corpus, run

    python run.py scheme --labels /path/to/labels

which prints the identifiers actually present against what this file expects and says
plainly where they disagree. If they do, edit THIS FILE and nothing else.

The defaults are the CTSpinoPelvic1K v11 scheme (VerSe-native):
  1-7    C1-C7
  8-19   T1-T12
  20-25  L1-L6
  26     sacrum           (29 is retired: it was a carved S1, withdrawn in v11)
  28     T13
  34-46  left ribs 1-13   47-59 right ribs 1-13
  60/61  lumbar ribs, left and right
"""
from __future__ import annotations

N_CERVICAL = 7
N_THORACIC = 12
N_LUMBAR = 6

CERVICAL_FIRST = 1
THORACIC_FIRST = 8
LUMBAR_FIRST = 20
SACRUM_ID = 26
T13_ID = 28
L6_ID = 25

# 29 was a carved S1 in v10 and is RETIRED in v11, dissolved back into the sacrum (26).
# Both are accepted here and both are treated as sacrum, so a v10 volume and a v11 volume
# give the same answer. v11 retired the identifier rather than renumbering 30-68, because
# renumbering would rename the hips, femora and every rib under identifiers consumers are
# already keyed to. If a volume carries 29 it is v10; nothing purely vertebral differs.
S1_ID_V10 = 29
SACRUM_IDS = (SACRUM_ID, S1_ID_V10)

HIP_IDS = (30, 31)                              # left, right
FEMUR_IDS = (32, 33)                            # left, right

RIB_LEFT_OFFSET, RIB_RIGHT_OFFSET = 33, 46      # left rib n = 33+n, right rib n = 46+n
N_RIBS = 13
LUMBAR_RIB_IDS = (60, 61)
HARDWARE_IDS = tuple(range(62, 69))             # instrumentation, subtypes 62-68

CERVICAL_IDS = tuple(range(CERVICAL_FIRST, CERVICAL_FIRST + N_CERVICAL))
THORACIC_IDS = tuple(range(THORACIC_FIRST, THORACIC_FIRST + N_THORACIC))
LUMBAR_IDS = tuple(range(LUMBAR_FIRST, LUMBAR_FIRST + N_LUMBAR))
VERTEBRA_IDS = CERVICAL_IDS + THORACIC_IDS + LUMBAR_IDS + (T13_ID,)

NAMES = {}
for _i, _v in enumerate(CERVICAL_IDS, 1):
    NAMES[_v] = "C%d" % _i
for _i, _v in enumerate(THORACIC_IDS, 1):
    NAMES[_v] = "T%d" % _i
for _i, _v in enumerate(LUMBAR_IDS, 1):
    NAMES[_v] = "L%d" % _i
NAMES[T13_ID] = "T13"
NAMES[SACRUM_ID] = "sacrum"
NAMES[S1_ID_V10] = "sacrum_S1_v10"
NAMES[HIP_IDS[0]], NAMES[HIP_IDS[1]] = "hip_left", "hip_right"
NAMES[FEMUR_IDS[0]], NAMES[FEMUR_IDS[1]] = "femur_left", "femur_right"
for _h in HARDWARE_IDS:
    NAMES[_h] = "hardware_%d" % _h
for _n in range(1, N_RIBS + 1):
    NAMES[RIB_LEFT_OFFSET + _n] = "rib_left_%d" % _n
    NAMES[RIB_RIGHT_OFFSET + _n] = "rib_right_%d" % _n
NAMES[LUMBAR_RIB_IDS[0]] = "rib_left_lumbar"
NAMES[LUMBAR_RIB_IDS[1]] = "rib_right_lumbar"

# anatomical order, cranial first, used wherever levels are sorted
ORDER = ([NAMES[v] for v in CERVICAL_IDS] + [NAMES[v] for v in THORACIC_IDS]
         + ["T13"] + [NAMES[v] for v in LUMBAR_IDS])


def name_of(vid):
    return NAMES.get(int(vid)) if vid else None


def thoracic_id(n):
    """T-n -> its identifier."""
    return THORACIC_FIRST + n - 1


def rib_level(vid):
    """A numbered rib identifier -> 1..13, else None. Lumbar ribs return None."""
    vid = int(vid)
    if RIB_LEFT_OFFSET < vid <= RIB_LEFT_OFFSET + N_RIBS:
        return vid - RIB_LEFT_OFFSET
    if RIB_RIGHT_OFFSET < vid <= RIB_RIGHT_OFFSET + N_RIBS:
        return vid - RIB_RIGHT_OFFSET
    return None


def check(labels_dir, n=3):
    """Print what is in the volumes against what this file expects."""
    from pathlib import Path

    import nibabel as nib
    import numpy as np

    files = sorted(Path(labels_dir).glob("*.nii.gz"))[:n]
    if not files:
        raise SystemExit("no *.nii.gz under %s" % labels_dir)
    seen = set()
    for p in files:
        ids = {int(v) for v in np.unique(np.asanyarray(nib.load(str(p)).dataobj)) if v}
        seen |= ids
        known = sorted(i for i in ids if i in NAMES)
        unknown = sorted(i for i in ids if i not in NAMES)
        print("\n%s" % p.name)
        print("  %d identifiers; vertebrae: %s"
              % (len(ids), ", ".join(NAMES[i] for i in known if i in VERTEBRA_IDS) or "none"))
        if unknown:
            print("  NOT IN THE SCHEME: %s" % unknown)
    stray = sorted(i for i in seen if i not in NAMES)
    print("\n" + "-" * 68)
    if stray:
        print("STOP. %d identifier(s) are not in scheme.py: %s" % (len(stray), stray))
        print("Edit scheme.py to match this corpus before measuring anything. A wrong map")
        print("does not raise; it returns a finite, plausible, wrong number.")
        return 1
    if not (seen & set(VERTEBRA_IDS)):
        print("STOP. No identifier in this corpus matches a vertebra in scheme.py.")
        return 1
    print("every identifier seen is in scheme.py. Check the NAMES above read correctly")
    print("for this corpus before going on: matching numbers is not the same as matching")
    print("anatomy, and only your eye can tell them apart.")
    return 0
