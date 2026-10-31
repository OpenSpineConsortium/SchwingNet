"""SchwingCheck: the exact Bayes rule that names a run of vertebrae, lifted out of the archive.

The archive (archive/bordercall/exact.py) is the reference: it scores fields of consecutive
bodies on the seven measures a SPINEPS mask can read, with one loop per place and one per
measure. This package holds the same rule on data shaped for PyMC and for scale (TODO.md, item P
step c): the checked table of the four Panjabi papers as one long CSV written from the
provenance record (table.py), loaded into an xarray Dataset with named dimensions (level,
measure, side); columns, synthetic or real, as arrays (column, body, measure) with NaN for a
missing value and integer offsets for the gaps between bodies (columns.py); the rule as one
vectorised closed form over fields, places, measures and quadrature nodes at once (rule.py);
and every result as an ArviZ InferenceData written to NetCDF with the command, the seeds and
the digests in its attributes (records.py).

Nothing here is a patient: every column is drawn from Panjabi's tables until item 5 of TODO.md
brings real spines.
"""
from __future__ import annotations

__version__ = "0.1.0"

LEVELS_C2 = ["C%d" % i for i in range(2, 8)] + ["T%d" % i for i in range(1, 13)] + ["L%d" % i for i in range(1, 6)]
LEVELS = LEVELS_C2[1:]              # the rule's levels: C3 to L5, twenty-two, as the archive's
SIDES = ["whole", "right", "left"]
KINDS = ["length", "area", "angle"]
# how each kind scales with the patient's size s: a length as s, an area as s squared, an angle
# not at all (TODO.md, item P step 4)
SIZE_POWER = {"length": 1, "area": 2, "angle": 0}
UNITS = {"length": "mm", "area": "mm2", "angle": "deg"}
PLANES = ["mask", "ap", "lateral", "ct"]
