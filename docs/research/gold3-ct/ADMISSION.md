# Gold tier 3 CT: the admission by the field test

Written by `python3 tools/gold3_field.py write` from data/gold3-ct/admission.json; never edited by hand. The rule, its reasons and the definition of held are docs/research/gold3-ct/README.md. Confidential.

## The rule, version 2

A CT is admitted when its field holds C2 and the top of the sacrum, whatever its masks hold; a level its masks do not draw is completed by a segmenter, kept as a machine mask of its own. The head end is out when the field's top cuts C2 and the level below it alike, a sliver of C2; the foot end is out when the field's foot cuts the sacrum, with less than s1_view_mm of it in the field, and the foot-most level above it too, and a border case when it cuts the sacrum alone. The field is read over each level along the world's vertical line, and a padded grid's field ends where the spinal cord and the column stop together.

Asked: the owner, 2026-10-28 22:58 UTC (#443's question): "if the full spune is in view in the volume, and just missing a mask or two, that should just be completed using a segmentation software of choice ... i dont think i should leave out any spines that have ct volumes with the full spine in view".

## The verdicts

A study is admitted when both ends are drawn or in view; look means a border case at one end, admitted only after a person's look; not admitted means C2 or the sacrum is out of the field, or no level is drawn. Whole by masks means no level to add; to complete means a segmenter adds the levels listed below.

| member | studies | admitted | whole by masks | to complete | look | not admitted | admitted persons |
|---|---|---|---|---|---|---|---|
| enhance_pet | 1597 | 1560 | 1560 | 0 | 1 | 36 | - |
| verse | 374 | 18 | 0 | 18 | 9 | 347 | 18 |
| totalsegmentator | 1939 | 151 | 146 | 5 | 1 | 1787 | 151 |

## The head end

| member | C2 drawn | C2 in view, not drawn | border | out | no column |
|---|---|---|---|---|---|
| enhance_pet | 1560 | 0 | 1 | 36 | 0 |
| verse | 76 | 1 | 10 | 287 | 0 |
| totalsegmentator | 493 | 0 | 61 | 1223 | 162 |

## The foot end

| member | sacrum drawn | sacrum in view, not drawn | border | out | no column |
|---|---|---|---|---|---|
| enhance_pet | 1597 | 0 | 0 | 0 | 0 |
| verse | 0 | 293 | 3 | 78 | 0 |
| totalsegmentator | 880 | 5 | 5 | 918 | 131 |

## What a segmenter must draw

Levels to add over the admitted studies, by member: each a machine mask of its own, never pooled with SPINEPS or with the release's masks, never raising a tier.

| member | levels to add (studies) |
|---|---|
| enhance_pet | none |
| verse | C2 1, sacrum 18 |
| totalsegmentator | T4 1, T5 1, T6 2, T7 1, T8 2, T9 1, T10 1, T11 2, T12 2, L1 1, L4 3, L5 3, sacrum 2 |

## Flags on the admitted studies

| member | flags (studies) |
|---|---|
| enhance_pet | c2_at_field_top 17, name_skipped 1, no_l5 40, sacrum_at_field_foot 1, small_column 1 |
| verse | name_skipped 1, no_l5 3 |
| totalsegmentator | c2_at_field_top 5, child 22, cut_in_plane 4, label_spans_levels 12, name_skipped 1, no_l5 1, sacrum_at_field_foot 14, small_column 17, stray_labels 9 |

What each flag means: c2_at_field_top, the field's top cuts C2; sacrum_at_field_foot, the field's foot cuts a sacrum label of any size; name_skipped, a name the column's order expects is missing where its neighbours leave no room for a body (a count variant, as eleven thoracic and then L1, or a skipped label), so nothing is added for it and the count reads it; cut_in_plane, a level touches a side face of the grid; no_l5, L4 is the last lumbar with the foot in view; stray_labels, a label of fewer voxels than the floor; child, under 18 at the scan; small_column, C2's top to L1's foot under 300 mm; label_spans_levels, a label more than 4 times the study's median level height, as one label drawn over several bodies. A flag asks for a look and leaves a study's verdict as it is.

## The head table

How far C2's top lies above each level's top, in mm, in spines of all three members that draw both whole.

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
| T4 | 1805 | 121.3 | 155.0 | 180.0 |
| T4 to C2's foot | 1805 | 84.0 | 115.0 | 137.5 |
| T5 | 1750 | 140.0 | 175.0 | 202.5 |
| T5 to C2's foot | 1750 | 102.5 | 136.2 | 160.0 |
| T6 | 1731 | 161.7 | 198.0 | 227.5 |
| T6 to C2's foot | 1731 | 125.0 | 159.0 | 183.0 |
| T7 | 1728 | 181.3 | 220.5 | 252.0 |
| T7 to C2's foot | 1728 | 145.0 | 182.5 | 208.5 |
| T8 | 1722 | 205.0 | 246.0 | 278.0 |
| T8 to C2's foot | 1722 | 170.0 | 207.0 | 235.0 |
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
| C7 | 1765 | -462.0 | -417.0 | -357.5 |
| T1 | 1852 | -441.0 | -399.0 | -342.9 |
| T2 | 1981 | -420.7 | -380.0 | -327.5 |
| T3 | 2005 | -400.0 | -360.0 | -310.6 |
| T4 | 2007 | -377.4 | -337.5 | -291.3 |
| T5 | 2010 | -347.5 | -310.0 | -267.0 |
| T6 | 2011 | -317.5 | -282.5 | -240.0 |
| T7 | 2023 | -290.0 | -256.5 | -216.0 |
| T8 | 2076 | -264.0 | -232.5 | -192.0 |
| T9 | 2139 | -240.0 | -210.0 | -171.0 |
| T10 | 2227 | -219.0 | -189.0 | -150.0 |
| T11 | 2307 | -192.5 | -165.0 | -127.5 |
| T12 | 2346 | -159.0 | -133.1 | -100.5 |
| L1 | 2370 | -121.5 | -100.0 | -72.0 |
| L2 | 2376 | -84.0 | -66.0 | -43.5 |
| L3 | 2384 | -48.0 | -35.0 | -18.0 |
| L4 | 2385 | -17.5 | -7.3 | 8.9 |
| L5 | 2361 | 9.0 | 24.0 | 37.5 |
| L6 | 91 | 17.5 | 30.0 | 40.2 |
| last lumbar | 2417 | 12.1 | 24.0 | 37.5 |

## Checks

The rule run with C1 and C2 hidden on spines that draw them whole (it should find C2 in view), with the sacrum hidden on spines that draw it (it should find the sacrum in view), and on spines whose head-most drawn level is cut by the field's top (it must call C2 out):

| check | result (studies) |
|---|---|
| head_with_c1_c2_hidden | enhance_pet: border 11, enhance_pet: in_view 1532, totalsegmentator: border 12, totalsegmentator: in_view 352, totalsegmentator: no_column 2, verse: in_view 75 |
| foot_with_sacrum_hidden | enhance_pet: in_view 1596, totalsegmentator: in_view 791, totalsegmentator: no_column 7, totalsegmentator: out 1 |
| head_most_level_cut_at_the_top | enhance_pet: out 36, totalsegmentator: out 1193 |

## How the counts move with S1_VIEW_MM (20 mm in the rule)

| s1 view mm | verdicts (studies) |
|---|---|
| 10 | admitted 1731, look 10, not_admitted 2169 |
| 30 | admitted 1728, look 12, not_admitted 2170 |

## Unread

none
