"""Each measure morphometry takes, drawn where it was taken: on the vertebra's sagittal, coronal and
axial slices through its own mask.

A number a reader cannot see taken is a number a reader cannot check. Here every drawn line is
built again from the measuring modules' own functions (morphometry.body, canal, pedicle, column,
scanimport.geometry), its ends in the vertebra's frame, and the value its construction gives is
set beside the value morphometry.measure.vertebra_values wrote for the same vertebra. A line whose
value differs by more than a millionth of the value is not drawn, and the figure's table says it
was withheld, so no drawing shows a measure other than the one in the rows.

Lines are of four kinds (Line.rule): "length", the distance between the two ends, which is the
value; "dz", a disc's gap along the lower vertebra's axis, the ends at the two plates' bands;
"median", a pedicle's width or height, drawn on the isthmus slab nearest the median the value is
taken over, the width then times the cosine of the axis's transverse angle; and "angle", the
wedge between the end-plates drawn rim to rim.

    python -m morphoview render --labels MASK.nii.gz --scheme enhance --study 0004 --levels L3 T8 C5 --out DIR

The slices are drawn as a reader looks at them: the sagittal with the front to the left, the
coronal and the axial with the patient's right on the left, the axial with the front at the top.

The lines and frames the export writes (python -m morphometry run --lines) are carried onto the
X-rays FleXray renders from the same CT by morphoview.projection, FleXray's own camera, and
morphoview.shapes gives curves, planes, polygons, curved surfaces and volumes that project through
it; the research note research_notes/morphometry/README.md says, in its section "Carrying the
lines onto FleXray's X-rays", how each is held to what FleXray renders. A render of SchwingNet's
pipeline is named by its manifest and file, one of its realism programme by its folder, sample and
CT, with that sample's FLUX edits and the filter's verdicts on them listed where their folders are
given.

    python -m morphoview project --lines lines.csv --frames frames.csv --manifest manifest.json --file images/<stem>_v00.png --labels MASK.nii.gz --scheme enhance --out DIR
    python -m morphoview project --lines lines.csv --frames frames.csv --realism RENDER --sample <sample_id> --ct CT.nii.gz --edits EDIT --filter FILTER --labels MASK.nii.gz --scheme enhance --out DIR
"""
