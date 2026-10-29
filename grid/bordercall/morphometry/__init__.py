"""Morphometrics read programmatically from labelled CT: the measures the 43 clinical papers of
the clinical reread (bordercall PR 21) and the paper-tables vocabulary name, taken on whole-vertebra
masks such as ENHANCE.PET's, each tested on a phantom whose every answer is known.

    python -m morphometry measure --labels 0001.nii.gz --scheme enhance --study 0001 --out rows.csv
    python -m morphometry run --masks DIR --scheme enhance --out DIR --workers 3
    python -m morphometry phantom

The families, one module each: body.py (heights, waist, end-plate areas, slopes and
concavity, volumes), canal.py (Eisenstein's least depth, the interpedicular distance both ways,
area, lateral depth, trefoil index, the lateral-film construction), pedicle.py (isthmus width,
height and area, the axis's angles, the chord), posterior.py (transverse and spinous processes,
laminae, facets), column.py (discs, segmental angles, slip, foramen, regional curves) and
pelvis.py (S1, acetabula, pelvic incidence, the crests' line, the L5 transverse processes' gaps).
anatomy.py reads the vertebra once for all of them; measure.py runs them over a volume.

Results are measurements of masks, not of bone: a machine mask, MOOSE's even when people
corrected it, never raises an evidence tier, and every comparison with a paper's mean says
which technique the paper used (research_notes/morphometry/README.md).
"""
