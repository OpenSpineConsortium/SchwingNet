"""From a scan to a column bordercall can name: the import pipeline for empirical data.

    python -m scanimport ingest-ct --labels seg.nii.gz --scheme verse --study s0001 --source verse \
                                   --annotation human --out imports/verse
    python -m scanimport ingest-xr --xr ap.json --xr lateral.json --study f0001 --source aasce \
                                   --annotation human --out imports/aasce
    python -m scanimport ingest-raw-ct --volume ct_dicom_folder --study s0002 --source enhance \
                                   --out imports/raw
    python -m scanimport ingest-image --image ap.dcm --corners ap.json --flexray ap_probabilities.npy \
                                   --study f0002 --source x --annotation human --out imports/x
    python -m scanimport check     imports/verse
    python -m scanimport tiers     imports/verse imports/aasce --out imports/tiers
    python -m scanimport compare   imports/verse --out imports/compare
    python -m scanimport name      imports/verse/fields/s0001.csv
    python -m scanimport score     imports/verse --n 1 3 5 9 --out imports/scores

The owner's ask of 27 October 2026, 09:44 UTC: "get 2D/3D scan to bordercall-importable data
pipeline done so i can start importing empirical data". A scan comes in as one of four things:

- a CT's label volume (NIfTI), whole-vertebra instance labels in one of the schemes in
  schemes.py (VerSe, SPINEPS, TotalSegmentator, MOOSE, CTSpinoPelvic1K), with SPINEPS's
  subregion volume where there is one (volume.py);
- a radiograph's annotation in SchwingNet's X-ray format, four corners per body with the level
  named (SchwingNet docs/research/xr-annotation-format.md, "schwingnet-spine-xr/1";
  radiograph.py);
- a CT with no labels at all, its chords taken from the intensities by published training-free
  rules, the owner's ask of 27 October 2026, 13:45 UTC (intensity.py, edges.py, the mask-free
  mode; its bodies are found but never named);
- one radiograph or frame, DICOM or a picture file, with its corners or FleXray's masks, measured
  at the scale its own header gives (film.py, readers.py).

Each leaves as one column (column.py): the study's bodies from the top down, each with
the name its labels give it, the measures taken on it in millimetres (NaN where a measure could
not be taken), how each was taken, and the study's facts the tiers are read from. A directory of
imports holds the columns as JSON, the bodies as one long CSV, one field file per study in the
format `python -m schwingcheck name` reads, and a manifest. bridge.py names a column with the
archive's exact rule (archive/bordercall/exact.py), extended to measures missing on some bodies
and to bodies with gaps between them, so an imported study can be named and, where its labels
were counted from C2, scored, today.

Nothing here reads a patient identifier. The imports hold per-body measurements of the source's
own case ids and stay where the data are (the grid); only aggregates come back to git.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVE = os.path.join(ROOT, "archive", "bordercall")

# The names a body can carry, top down: the count from C2 names a thirteenth rib-bearing body
# T13 only where the labels say so, and a sixth lumbar body L6; the archive's rule names only
# C3 to L5 (RULE_LEVELS), the twenty-two levels Panjabi measured every dimension of.
CERVICAL = ["C%d" % i for i in range(1, 8)]
THORACIC = ["T%d" % i for i in range(1, 14)]
LUMBAR = ["L%d" % i for i in range(1, 7)]
LEVELS = CERVICAL + THORACIC + LUMBAR + ["sacrum"]
RULE_LEVELS = CERVICAL[2:] + THORACIC[:12] + LUMBAR[:5]
# Named and kept, never measured: the rule's column starts at C3 and the sacrum carries no row.
NOT_MEASURED = ("C1", "C2", "sacrum")

# The archive's seven measures (covariance.SPINEPS_7), the only ones the rule and the comparison
# use; and two more a mask gives, kept in the record only: the reference table
# (archive/bordercall/reference/panjabi_full_spine.csv) has no row for either, and Panjabi's
# spinous process length (67.7 mm at L1, the lumbar paper's Table 5) runs from a landmark this
# chord does not use, so neither is ever set beside Panjabi. The pedicle is refused, as
# spineps_map.py refuses it, since no scheme here labels the pedicle on its own.
SEVEN = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth",
         "h_post", "canal_w", "canal_ap"]
EXTRA = ["tp_span", "spinous_length"]
MEASURES = SEVEN + EXTRA
PANJABI = {"endplate": "EPWu", "endplate_depth": "EPDu", "endplate_lower": "EPWl",
           "endplate_lower_depth": "EPDl", "h_post": "VBHp", "canal_w": "SCW", "canal_ap": "SCD"}
# Which view of a radiograph shows each measure. The archive's AP regime (neighbour.REGIMES)
# counts the posterior height too; an AP film shows the height of the body's side walls, not of
# its posterior wall, so here VBHp is read on the lateral alone.
PLANES = {"endplate": ("ap",), "endplate_lower": ("ap",), "canal_w": ("ap",),
          "endplate_depth": ("lateral",), "endplate_lower_depth": ("lateral",), "canal_ap": ("lateral",),
          "h_post": ("lateral",), "tp_span": ("ap",), "spinous_length": ("lateral",)}


def archive_path() -> str:
    """The archive's package folder, put on the import path once, so the exact rule and the
    table loader are imported from where they are and never copied."""
    if ARCHIVE not in sys.path:
        sys.path.insert(0, ARCHIVE)
    return ARCHIVE


def level_index(name: str) -> int:
    return LEVELS.index(name)


def rule_index(name: str):
    """A level's place in the rule's column (C3 = 0, L5 = 21), or None outside it."""
    return RULE_LEVELS.index(name) if name in RULE_LEVELS else None
