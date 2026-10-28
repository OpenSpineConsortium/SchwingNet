# Gold tier 3 CT dataset: quality assurance

Written by `python3 tools/gold3_ct.py qa` from the committed files under data/gold3-ct/; do not edit it by hand, since `python3 tools/gold3_ct.py check` fails on a page that is not what the files give.

What the checks can show: that the release's names, the rib ladder and the label geometry hold together, study by study. They read two masks the same four readers checked, so a study that passes every one is consistent, not read: confirmed_by_masks is never a reader's read of the CT. No mask check can settle a lumbosacral question (sacralisation, lumbarisation, Castellvi), which waits for the CT and a person; reader_confirmed comes only from a recorded reader's verdict.

The ENHANCE.PET rows are not yet committed (data/gold3-ct/enhance-pet/facts.jsonl), so no check has run on them. VerSe's and TotalSegmentator's checks need their masks, which are on the grid.

## The checks

| Id | Version | Check | What it holds | Thresholds | Pass | Fail | Look | Not run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q01 | 1 | header | the mask is readable, of an integer type, its shape and affine sane, on the rib mask's grid. | AFFINE_TOLERANCE = 0.001 | 0 | 0 | 0 | 0 |
| Q02 | 1 | alphabet | vertebra ids 1 to 28 and rib ids 1 to 26 (the sternum counted apart), nothing outside the scheme. | none | 0 | 0 | 0 | 0 |
| Q03 | 1 | whole rule | C2 and the sacrum at LEVEL_MIN_VOXELS or more and every level from C2 to T12; a lumbar label missing other than L5 is whole by the owner's rule and a look; an absent L5 is excepted. | LEVEL_MIN_VOXELS = 200 | 0 | 0 | 0 | 0 |
| Q04 | 1 | head-foot order | neighbouring labels in head-foot order; a lower label whose top lies above the upper's is a look. | LEVEL_MIN_VOXELS = 200 | 0 | 0 | 0 | 0 |
| Q05 | 1 | gaps | a space over UNLABELLED_GAP_MM above T12 fails (a body with no label); below T12, or over LOOK_GAP_MM anywhere, it is a look. | UNLABELLED_GAP_MM = 20.0; LOOK_GAP_MM = 10.0 | 0 | 0 | 0 | 0 |
| Q06 | 1 | C2 in the field's top slice | C2 in the field's top slice, so its top may be cut off: a look. | half the mask's slice step | 0 | 0 | 0 | 0 |
| Q07 | 1 | L5 fragment | an L5 label under FRAGMENT_SHARE of L4's voxels over an L4 that meets the sacrum. | FRAGMENT_SHARE = 0.25; NO_L5_MEETS_MM = -5.0 | 0 | 0 | 0 | 0 |
| Q08 | 1 | lowest lumbar label touches the sacrum | the lowest lumbar label touches the sacrum in 3-D, so no body without a label lies between; and across a labelled L5, L4 stays as far from the sacrum as in every control. | TOUCH_MM = 1.5; CONTROL_NEAREST_ACROSS_L5_MM = 2.3 | 0 | 0 | 0 | 0 |
| Q09 | 1 | rib ladder | every rib with contacts leads on its own label, k + 7; more than SHIFT_SHARE of them one level off the same way is a shifted ladder and fails, fewer off is a look. | RIB_MIN_VOXELS = 50; SHIFT_SHARE = 0.5 | 0 | 0 | 0 | 0 |
| Q10 | 1 | lowest rib meets its own vertebra | each side's lowest rib meets its own vertebra; off its own fails, no contact or a tie is a look. | RIB_MIN_VOXELS = 50 | 0 | 0 | 0 | 0 |
| Q11 | 1 | split piece | a column label under SPLIT_SHARE of both neighbours' voxels is a piece split off a body. | SPLIT_SHARE = 0.4 | 0 | 0 | 0 | 0 |
| Q12 | 1 | fragments | a column label whose largest connected piece holds under COMPONENT_SHARE of its voxels. | COMPONENT_SHARE = 0.9 | 0 | 0 | 0 | 0 |
| Q13 | 1 | C7 against T1 | C7's voxels over T1's outside the controls' 1st to 99th percentile. | RATIO_PERCENTILES = (1, 99); MIN_CONTROLS_FOR_RATIO = 20 | 0 | 0 | 0 | 0 |
| Q14 | 1 | two implementations agree | an independent reading of the same masks (facts B) agrees on the inputs of Q08 to Q10. | DISTANCE_AGREEMENT_MM = 0.1 | 0 | 0 | 0 | 0 |
| Q15 | 1 | slice spacing against the table | the NIfTI's slice spacing no wider than the slice thickness CT-details.xlsx gives. | SLICE_TOLERANCE_MM = 0.05 | 0 | 0 | 0 | 0 |
| Q16 | 1 | bucket bytes | each mask's bytes are what the public bucket lists; a repaired vertebra mask is not listed. | none | 0 | 0 | 0 | 0 |

## Every fail and look

None.

