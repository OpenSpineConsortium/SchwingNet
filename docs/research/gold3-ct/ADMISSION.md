# Gold tier 3 CT: the admission by the field test

Written by `python3 tools/gold3_field.py write` from data/gold3-ct/admission.json; never edited by hand. The rule, its reasons and the definition of held are docs/research/gold3-ct/README.md. Confidential.

## The rule, version 3

A CT is admitted when its field holds the foot of C2 and the top of the sacrum, whatever its masks hold; a level its masks do not draw is completed by a segmenter, kept as a machine mask of its own. A drawn C2 is in view however the field's top cuts it, unless it cuts the level below C2 too, a sliver of C2, and the end is out; an undrawn C2 is in view when the field's top lies above where C2's foot lies in 95 of 100 spines. A drawn sacrum is in view however little of it the field holds; an undrawn one is in view when the field's foot lies below where the sacrum's top lies in 95 of 100 spines. The field is read over each level along the world's vertical line, and a padded grid's field ends where the CT's own constant slices begin once the census has read the CT (planes.json), else where the spinal cord and the column stop together. A name missing between two drawn levels is a level to add when their centres stand more than room_times the study's spacing of neighbours apart, else a count variant, flagged.

Asked: the owner, 2026-10-28 22:58 UTC (#443's question): "if the full spune is in view in the volume, and just missing a mask or two, that should just be completed using a segmentation software of choice ... i dont think i should leave out any spines that have ct volumes with the full spine in view"; and for version 3, 2026-10-29 12:58 UTC: "If the top of the sacrum is visible that is acceptable, which I believe is all of them but check" and "Same for the bottom c2".

## The verdicts

A study is admitted when both ends are drawn or in view; look means a border case at one end, admitted only after a person's look; not admitted means C2 or the sacrum is out of the field, or no vertebra is drawn above the sacrum (no column). Whole by masks means no level to add; to complete means a segmenter adds the levels listed below.

| member | studies | admitted | whole by masks | to complete | look | not admitted | admitted persons |
|---|---|---|---|---|---|---|---|
| enhance_pet | 1597 | 1561 | 1560 | 1 | 0 | 36 | - |
| verse | 374 | 21 | 0 | 21 | 6 | 347 | 21 |
| totalsegmentator | 1939 | 154 | 147 | 7 | 0 | 1785 | 154 |

## The head end

| member | C2 drawn | C2 in view, not drawn | border | out | no column |
|---|---|---|---|---|---|
| enhance_pet | 1560 | 1 | 0 | 36 | 0 |
| verse | 76 | 4 | 7 | 287 | 0 |
| totalsegmentator | 494 | 0 | 61 | 1222 | 162 |

## The foot end

| member | sacrum drawn | sacrum in view, not drawn | border | out | no column |
|---|---|---|---|---|---|
| enhance_pet | 1597 | 0 | 0 | 0 | 0 |
| verse | 0 | 294 | 2 | 78 | 0 |
| totalsegmentator | 901 | 8 | 0 | 899 | 131 |

## What a segmenter must draw

Levels to add over the admitted studies, by member: each a machine mask of its own, never pooled with SPINEPS or with the release's masks, never raising a tier. admission.json gives each border case the list its look would ask, should it admit the study.

| member | levels to add (studies) |
|---|---|
| enhance_pet | C2 1 |
| verse | C2 4, sacrum 21 |
| totalsegmentator | C4 1, C5 1, T4 1, T5 1, T6 2, T7 2, T8 3, T9 2, T10 1, T11 2, T12 2, L1 1, L4 3, L5 3, sacrum 2 |

## Flags on the admitted studies

| member | flags (studies) |
|---|---|
| enhance_pet | c2_at_field_top 17, name_skipped 2, no_l5 39, sacrum_at_field_foot 1, small_column 1 |
| verse | name_skipped 2, no_l5 3 |
| totalsegmentator | c2_at_field_top 6, child 23, cut_in_plane 4, label_spans_levels 12, level_past_sacrum_top 2, no_l5 2, sacrum_at_field_foot 17, small_column 17, stray_labels 10 |

What each flag means: c2_at_field_top, the field's top cuts C2; sacrum_at_field_foot, the field's foot cuts a sacrum label of any size; level_past_sacrum_top, the foot-most level above a drawn sacrum runs on past the sacrum's top to the field's foot, a label over the junction; name_skipped, one name the column's order expects is missing where its neighbours' centres stand no farther apart than its own spacing of neighbours allows (a count variant, as eleven thoracic and then L1, or a skipped label, within 1.4 times that spacing), so nothing is added for it and the count reads it; cut_in_plane, a level touches a side face of the grid; no_l5, L4 is the last lumbar, no L5 or L6 drawn, with the foot in view; stray_labels, a label of fewer voxels than the floor; child, under 18 at the scan; small_column, C2's top to L1's foot under 300 mm; label_spans_levels, a label more than 4 times the study's median level height, as one label drawn over several bodies. A flag asks for a look and leaves a study's verdict as it is.

## The head table

How far C2's top (a level's own row) and C2's foot (its row to C2's foot) lie above each level's top, in mm, in spines of all three members that draw both whole; the rule reads the rows to C2's foot.

| level | spines | p5 | median | p95 |
|---|---|---|---|---|
| C3 | 1975 | 20.0 | 30.0 | 37.5 |
| C3 to C2's foot | 1975 | -15.0 | -9.0 | -5.0 |
| C4 | 1967 | 33.0 | 45.0 | 55.0 |
| C4 to C2's foot | 1967 | -1.9 | 6.0 | 12.0 |
| C5 | 1962 | 43.5 | 60.0 | 70.7 |
| C5 to C2's foot | 1962 | 9.0 | 20.0 | 27.5 |
| C6 | 1958 | 52.5 | 75.0 | 87.0 |
| C6 to C2's foot | 1958 | 18.0 | 34.5 | 45.0 |
| C7 | 1957 | 60.8 | 86.8 | 102.0 |
| C7 to C2's foot | 1957 | 27.0 | 47.5 | 60.0 |
| T1 | 1945 | 72.0 | 100.0 | 117.4 |
| T1 to C2's foot | 1945 | 37.5 | 60.0 | 75.0 |
| T2 | 1915 | 85.0 | 114.0 | 135.0 |
| T2 to C2's foot | 1915 | 49.9 | 75.0 | 92.5 |
| T3 | 1872 | 102.5 | 135.0 | 157.5 |
| T3 to C2's foot | 1872 | 65.0 | 95.0 | 114.0 |
| T4 | 1809 | 121.4 | 155.0 | 180.0 |
| T4 to C2's foot | 1809 | 84.0 | 115.0 | 137.5 |
| T5 | 1750 | 140.0 | 175.0 | 202.5 |
| T5 to C2's foot | 1750 | 102.5 | 136.2 | 160.0 |
| T6 | 1731 | 161.7 | 198.0 | 227.5 |
| T6 to C2's foot | 1731 | 125.0 | 159.0 | 183.0 |
| T7 | 1729 | 181.4 | 220.5 | 252.0 |
| T7 to C2's foot | 1729 | 145.0 | 182.5 | 208.5 |
| T8 | 1723 | 205.0 | 246.0 | 278.0 |
| T8 to C2's foot | 1723 | 170.0 | 207.0 | 235.0 |
| T9 | 1722 | 230.0 | 271.6 | 306.0 |
| T9 to C2's foot | 1722 | 195.0 | 232.5 | 262.5 |
| T10 | 1722 | 252.5 | 297.0 | 332.5 |
| T10 to C2's foot | 1722 | 216.0 | 257.5 | 289.9 |
| T11 | 1717 | 276.8 | 322.5 | 362.5 |
| T11 to C2's foot | 1717 | 240.0 | 283.7 | 318.0 |
| T12 | 1711 | 300.0 | 352.0 | 393.0 |
| T12 to C2's foot | 1711 | 265.0 | 312.5 | 350.0 |
| T13 | 3 | - | - | - |
| T13 to C2's foot | 3 | - | - | - |
| L1 | 1710 | 330.0 | 382.5 | 426.0 |
| L1 to C2's foot | 1710 | 292.4 | 342.5 | 383.2 |
| L2 | 1712 | 357.0 | 415.0 | 462.0 |
| L2 to C2's foot | 1712 | 320.6 | 375.0 | 417.9 |
| L3 | 1710 | 385.0 | 447.5 | 497.5 |
| L3 to C2's foot | 1710 | 350.0 | 408.0 | 454.1 |
| L4 | 1706 | 415.0 | 480.0 | 532.4 |
| L4 to C2's foot | 1706 | 377.5 | 440.0 | 487.5 |
| L5 | 1660 | 437.5 | 507.5 | 562.5 |
| L5 to C2's foot | 1660 | 400.0 | 467.5 | 520.0 |
| L6 | 72 | 461.4 | 525.0 | 588.0 |
| L6 to C2's foot | 72 | 423.9 | 487.8 | 544.9 |

## The foot table

Where the sacrum's top lies against each level's foot-most voxel, in mm, positive above it, in spines that draw both whole; the last lumbar is whichever lumbar a spine draws last.

| level | spines | p5 | median | p95 |
|---|---|---|---|---|
| C1 | 1678 | -570.0 | -515.0 | -441.0 |
| C2 | 1689 | -549.0 | -495.0 | -425.0 |
| C3 | 1713 | -531.0 | -480.0 | -412.3 |
| C4 | 1713 | -513.0 | -462.5 | -398.4 |
| C5 | 1727 | -495.7 | -447.5 | -384.0 |
| C6 | 1746 | -480.0 | -432.5 | -370.0 |
| C7 | 1766 | -462.0 | -417.0 | -357.5 |
| T1 | 1853 | -441.0 | -399.0 | -342.9 |
| T2 | 1981 | -420.7 | -380.0 | -327.5 |
| T3 | 2005 | -400.0 | -360.0 | -310.6 |
| T4 | 2007 | -377.4 | -337.5 | -291.3 |
| T5 | 2010 | -347.5 | -310.0 | -267.0 |
| T6 | 2011 | -317.5 | -282.5 | -240.0 |
| T7 | 2023 | -290.0 | -256.5 | -216.0 |
| T8 | 2076 | -264.0 | -232.5 | -192.0 |
| T9 | 2139 | -240.0 | -210.0 | -171.0 |
| T10 | 2227 | -219.0 | -189.0 | -150.0 |
| T11 | 2308 | -192.5 | -165.0 | -127.5 |
| T12 | 2346 | -159.0 | -133.1 | -100.5 |
| L1 | 2370 | -121.5 | -100.0 | -72.0 |
| L2 | 2376 | -84.0 | -66.0 | -43.5 |
| L3 | 2384 | -48.0 | -35.0 | -18.0 |
| L4 | 2387 | -17.5 | -7.3 | 8.8 |
| L5 | 2361 | 9.0 | 24.0 | 37.5 |
| L6 | 91 | 17.5 | 30.0 | 40.2 |
| last lumbar | 2417 | 12.1 | 24.0 | 37.5 |

## Checks

The rule run with C1 and C2 hidden on spines that draw them whole and a level below them (it should find C2 in view or a border case, never out), with the sacrum hidden on spines that draw it and a level above it (it should find the sacrum in view), and, a check of the rule's own branch that reads no table, on spines whose head-most drawn level below C2 is cut by the field's top (no C2 fits above it, so the rule must call C2 out):

| check | result (studies) |
|---|---|
| head_with_c1_c2_hidden | enhance_pet: in_view 1543, totalsegmentator: in_view 364, verse: in_view 75 |
| foot_with_sacrum_hidden | enhance_pet: in_view 1596, totalsegmentator: in_view 791, totalsegmentator: out 1 |
| head_most_level_cut_at_the_top | enhance_pet: out 36, totalsegmentator: out 1193, verse: out 48 |

## How the counts move with S1_VIEW_MM (0 mm in the rule)

| s1 view mm | verdicts (studies) |
|---|---|
| 10 | admitted 1735, look 6, not_admitted 2169 |
| 20 | admitted 1733, look 7, not_admitted 2170 |
| 30 | admitted 1732, look 8, not_admitted 2170 |

## Unread

none
