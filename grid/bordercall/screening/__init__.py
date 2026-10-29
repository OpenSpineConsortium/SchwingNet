"""One screening for any CT dataset's spine masks: which volumes show the whole spine, C2 to the
sacrum, what each mask draws, and how well a measure taken on the masks screens for what a reader
graded.

Source: the thread "Extract morphometrics from gold tier 3 CT" of the claude.ai project symphony_4,
29 October 2026, on the owner's words of 15:01 UTC ("make sure that this verse screening code is
written, reproducable, testable, follows my beethoven-qa requirements") and 15:12 UTC ("it shouldnt
only be the verse screening but pet.ct and totalsegmentator for the C2 and sacrum on CT volume ...
generalizing to any ct dataset"). Confidential, like the rest of bordercall: nothing here, and
nothing it writes, goes to a public place, and no mask or CT is ever copied into the repository.

Why one package. The gold tier 3 CT dataset has three members, and each came with a reader of its
own: holdings/count_enhance_pet.py and holdings/enhance_facts.py read ENHANCE.PET by raw label
number, holdings/fullspine_facts.py reads VerSe and TotalSegmentator by level name, and SchwingNet's
tools/gold3_field.py and tools/gold3_ct.py read each shape in its own way. A fourth dataset would
have needed a fourth reader. Here every dataset is read through scanimport's label schemes
(scanimport/schemes.py: verse, spineps, ctspinopelvic, moose, totalseg, enhance, or a label map of
the caller's) into one row of facts per study, in level names, and one rule reads the rows whatever
the dataset they came from. The holdings readers stay as the record of the counts already in
SchwingNet's data; this package reproduces their facts and their classes on the same masks (the
tests hold it to the count's own classes).

The three questions, each a command:

    python -m screening facts --masks DIR --scheme SCHEME --out facts.jsonl
        [--member NAME] [--persons MAP.json] [--label-map MAP.json] [--workers N] [--ids FILE]
    python -m screening whole --facts facts.jsonl --out verdicts.csv [--tables TABLES.json] [--ages MAP.json]
    python -m screening truth-from-riedel GRADES.csv --out truth.csv
    python -m screening join --rows rows.csv --truth truth.csv [--facts facts.jsonl] [--persons MAP.json] --out joined.csv
    python -m screening detect --joined joined.csv --out aggregates.json [--cut 0.8] [--boot 2000] [--seed 20261029]
    python -m screening neighbours --joined joined.csv --out neighbours.csv

1. facts (facts.py): each study's masks read once, a row per study: the files with their bytes and
   sha256, the grid, the field's head and foot edges, and for every level the scheme names its voxels,
   extent, centroid, pieces and the faces of the volume it reaches; the raw labels the scheme does not
   name are counted, never dropped silently. A run cut short is started again with the same command
   and reads only the studies it has not written.
2. whole (whole.py): two readings of the same rows. By the masks, rule version 1 of SchwingNet's
   data/gold3-ct/members.json: C2 and the sacrum drawn, every level from C2 to T12 drawn, no space
   wider than 20 mm above T12, a lumbar label missing or extra a variant and never a reason to drop a
   spine. By the field, rule version 3 of SchwingNet's tools/gold3_field.py: a CT is admitted when its
   field holds the foot of C2 and the top of the sacrum whatever its masks draw, the levels a segmenter
   must add listed, with the head and foot tables measured on the studies given or taken from a file.
3. truth (truth.py): a reader's per-vertebra truth (a Genant grade, a fracture call) joined to the
   measures morphometry took on the same masks, one reading per person's level, and what one measure
   screens: the AUC with ties counted half and a bootstrap over persons, sensitivity and specificity at
   a cut, the agreement of the grade a ratio implies with the reader's, and why a graded vertebra had
   no reading. Riedel's VerSe table is the first truth; a table of any dataset's reads joins the same
   way once it is in the truth form (study, level, truth, person).

The layering, as beethoven-qa's definition of done asks: every decision is a pure function over plain
Python values with its contracts (contracts.py), so CrossHair can run it and a person can review the
contracts rather than the lines; numpy, files and randomness stay at the edges, in private functions
or in __main__.py, the wiring. The tests run from the repository's root with
`python -m unittest discover -s screening/tests -t .`; each claim is checked against something it does
not share: a hand count, the holdings readers on the same toy spine, or SchwingNet's classes on a
recorded sample.
"""
from __future__ import annotations

CERVICAL = tuple("C%d" % i for i in range(1, 8))
# T13 is a thirteenth rib-bearing body, VerSe's label 28, named after T12 and before L1
THORACIC = tuple("T%d" % i for i in range(1, 14))
LUMBAR = tuple("L%d" % i for i in range(1, 7))
ORDER = (*CERVICAL, *THORACIC, *LUMBAR, "sacrum")
# the column the whole-spine rules read, C2 to the sacrum
COLUMN = ORDER[1:]
# the levels every spine has from C2 to L4: an undrawn one between two drawn ones is a gap to complete
# (the field rule). L5, T13 and L6 are left out, since four lumbar, a thirteenth thoracic and a sixth
# lumbar are variants the count reads, not masks to add; the mask rule counts L5 too (whole.COUNTED).
EXPECTED = tuple(n for n in ORDER if n not in ("C1", "T13", "L5", "L6", "sacrum"))
# a foot-most drawn lumbar that can be the last before the sacrum
LAST_LUMBARS = ("L4", "L5", "L6")
# a level is drawn when its label holds at least this many voxels (members.json's whole rule, version 1)
LEVEL_MIN_VOXELS = 200


def rank(level: str) -> int:
    """A level's place in the column's order, top down; a name the order lacks ranks after the sacrum."""
    return ORDER.index(level) if level in ORDER else len(ORDER)
