# Gold tier 3 CT: the admission by the field test

Written by `python3 tools/gold3_field.py write` from data/gold3-ct/admission.json; never edited by hand. The rule, its reasons and the definition of held are docs/research/gold3-ct/README.md. Confidential.

## The rule, version 2

A CT is admitted when its field holds C2 and the top of the sacrum, whatever its masks hold; a level its masks do not draw is completed by a segmenter, kept as a machine mask of its own.

Asked: the owner, 2026-10-28 22:58 UTC (#443's question): "if the full spune is in view in the volume, and just missing a mask or two, that should just be completed using a segmentation software of choice ... i dont think i should leave out any spines that have ct volumes with the full spine in view".

## The verdicts

A study is admitted when both ends are drawn or in view; look means a border case at one end, admitted only after a person's look; not admitted means C2 or the sacrum is out of the field, or no level is drawn. Whole by masks means no level to add; to complete means a segmenter adds the levels listed below.

| member | studies | admitted | whole by masks | to complete | look | not admitted | admitted persons |
|---|---|---|---|---|---|---|---|
| enhance_pet | 1600 | 1563 | 1560 | 3 | 1 | 36 | - |
| verse | 374 | 18 | 0 | 18 | 10 | 346 | 18 |
| totalsegmentator | 1939 | 156 | 149 | 7 | 10 | 1773 | 156 |

## The head end

| member | C2 drawn | C2 in view, not drawn | border | out | no column |
|---|---|---|---|---|---|
| enhance_pet | 1563 | 0 | 1 | 36 | 0 |
| verse | 76 | 1 | 11 | 286 | 0 |
| totalsegmentator | 496 | 1 | 73 | 1207 | 162 |

## The foot end

| member | sacrum drawn | sacrum in view, not drawn | border | out | no column |
|---|---|---|---|---|---|
| enhance_pet | 1600 | 0 | 0 | 0 | 0 |
| verse | 0 | 293 | 3 | 78 | 0 |
| totalsegmentator | 901 | 9 | 5 | 893 | 131 |

## What a segmenter must draw

Levels to add over the admitted studies, by member: each a machine mask of its own, never pooled with SPINEPS or with the release's masks, never raising a tier.

| member | levels to add (studies) |
|---|---|
| enhance_pet | T1 1, T9 1, T12 1 |
| verse | C2 1, T12 1, sacrum 18 |
| totalsegmentator | C4 1, C5 1, T4 1, T5 1, T6 2, T7 2, T8 3, T9 2, T10 1, T11 2, T12 2, L1 1, L4 3, sacrum 2 |

## Flags on the admitted studies

| member | flags (studies) |
|---|---|
| enhance_pet | c2_at_field_top 17, no_l5 40 |
| verse | no_l5 3 |
| totalsegmentator | c2_at_field_top 6, child 23, cut_in_plane 4, no_l5 3, sacrum_at_field_foot 3, stray_labels 10 |

## The head table

How far C2's top lies above each level's top, in mm, in spines of all three members that draw both whole.

| level | spines | p5 | median | p95 |
|---|---|---|---|---|
| C3 | 1987 | 20.0 | 30.0 | 37.5 |
| C3 to C2's foot | 1987 | -15.0 | -9.0 | -5.0 |
| C4 | 1979 | 32.5 | 45.0 | 55.0 |
| C4 to C2's foot | 1979 | -2.0 | 6.0 | 12.0 |
| C5 | 1975 | 43.4 | 60.0 | 70.7 |
| C5 to C2's foot | 1975 | 9.0 | 20.0 | 27.5 |
| C6 | 1970 | 52.4 | 74.9 | 87.0 |
| C6 to C2's foot | 1970 | 18.0 | 34.5 | 45.0 |
| C7 | 1969 | 60.1 | 86.0 | 102.0 |
| C7 to C2's foot | 1969 | 27.0 | 47.5 | 60.0 |
| T1 | 1959 | 72.0 | 100.0 | 117.0 |
| T1 to C2's foot | 1959 | 37.5 | 60.0 | 75.0 |
| T2 | 1931 | 85.0 | 114.0 | 135.0 |
| T2 to C2's foot | 1931 | 49.5 | 75.0 | 92.5 |
| T3 | 1888 | 102.0 | 135.0 | 157.5 |
| T3 to C2's foot | 1888 | 65.0 | 95.0 | 114.0 |
| T4 | 1830 | 121.4 | 155.0 | 180.0 |
| T4 to C2's foot | 1830 | 84.0 | 115.0 | 137.5 |
| T5 | 1769 | 140.0 | 175.0 | 202.5 |
| T5 to C2's foot | 1769 | 102.2 | 136.0 | 160.0 |
| T6 | 1743 | 160.6 | 198.0 | 227.5 |
| T6 to C2's foot | 1743 | 125.0 | 159.0 | 183.0 |
| T7 | 1735 | 180.0 | 220.5 | 252.0 |
| T7 to C2's foot | 1735 | 145.0 | 182.5 | 208.5 |
| T8 | 1729 | 205.0 | 246.0 | 278.0 |
| T8 to C2's foot | 1729 | 170.0 | 207.0 | 235.0 |
| T9 | 1727 | 230.0 | 271.5 | 306.0 |
| T9 to C2's foot | 1727 | 195.0 | 232.5 | 262.5 |
| T10 | 1728 | 252.5 | 297.0 | 332.5 |
| T10 to C2's foot | 1728 | 215.0 | 257.5 | 289.8 |
| T11 | 1723 | 276.0 | 322.5 | 362.5 |
| T11 to C2's foot | 1723 | 240.0 | 283.7 | 318.0 |
| T12 | 1716 | 300.0 | 351.7 | 393.0 |
| T12 to C2's foot | 1716 | 265.0 | 312.5 | 350.0 |
| T13 | 3 | - | - | - |
| T13 to C2's foot | 3 | - | - | - |
| L1 | 1715 | 330.0 | 382.5 | 426.0 |
| L1 to C2's foot | 1715 | 292.2 | 342.5 | 383.0 |
| L2 | 1717 | 357.0 | 415.0 | 462.0 |
| L2 to C2's foot | 1717 | 320.6 | 375.0 | 417.9 |
| L3 | 1715 | 385.0 | 447.5 | 497.5 |
| L3 to C2's foot | 1715 | 350.0 | 408.0 | 453.9 |
| L4 | 1711 | 415.0 | 480.0 | 532.2 |
| L4 to C2's foot | 1711 | 377.5 | 440.0 | 487.5 |
| L5 | 1665 | 437.5 | 507.5 | 562.5 |
| L5 to C2's foot | 1665 | 400.0 | 467.5 | 520.0 |
| L6 | 72 | 461.4 | 525.0 | 588.0 |
| L6 to C2's foot | 72 | 423.9 | 487.8 | 544.9 |

## The foot table

Where the sacrum's top lies against each level's foot-most voxel, in mm, positive above it, in spines that draw both whole; the last lumbar is whichever lumbar a spine draws last.

| level | spines | p5 | median | p95 |
|---|---|---|---|---|
| C1 | 1682 | -570.0 | -515.0 | -441.0 |
| C2 | 1694 | -549.0 | -495.0 | -425.0 |
| C3 | 1720 | -531.0 | -480.0 | -411.0 |
| C4 | 1721 | -513.0 | -462.5 | -397.5 |
| C5 | 1734 | -495.4 | -447.5 | -384.0 |
| C6 | 1763 | -480.0 | -432.5 | -370.0 |
| C7 | 1796 | -462.0 | -416.2 | -357.4 |
| T1 | 1868 | -441.0 | -399.0 | -342.6 |
| T2 | 1988 | -420.6 | -380.0 | -327.5 |
| T3 | 2008 | -400.0 | -360.0 | -310.7 |
| T4 | 2010 | -377.3 | -337.5 | -291.5 |
| T5 | 2016 | -347.5 | -310.0 | -267.0 |
| T6 | 2017 | -317.5 | -282.5 | -240.0 |
| T7 | 2037 | -290.0 | -256.5 | -216.0 |
| T8 | 2100 | -264.0 | -232.5 | -192.0 |
| T9 | 2170 | -240.0 | -210.0 | -170.0 |
| T10 | 2250 | -219.0 | -189.0 | -150.0 |
| T11 | 2322 | -192.5 | -165.0 | -127.5 |
| T12 | 2353 | -159.0 | -133.0 | -100.3 |
| L1 | 2373 | -121.5 | -100.0 | -72.0 |
| L2 | 2379 | -84.0 | -66.0 | -43.5 |
| L3 | 2392 | -48.0 | -35.0 | -18.0 |
| L4 | 2401 | -17.5 | -7.2 | 9.0 |
| L5 | 2368 | 9.0 | 24.0 | 37.5 |
| L6 | 91 | 17.5 | 30.0 | 40.2 |
| last lumbar | 2424 | 12.0 | 24.0 | 37.5 |

## Checks

The rule run with C1 and C2 hidden on spines that draw them whole (it should find C2 in view), with the sacrum hidden on spines that draw it (it should find the sacrum in view), and on spines whose head-most drawn level is cut by the field's top (it must call C2 out):

| check | result (studies) |
|---|---|
| head_with_c1_c2_hidden | enhance_pet: border 11, enhance_pet: in_view 1535, totalsegmentator: border 16, totalsegmentator: in_view 357, totalsegmentator: no_column 27, verse: in_view 75 |
| foot_with_sacrum_hidden | enhance_pet: in_view 1599, totalsegmentator: in_view 791, totalsegmentator: no_column 7, totalsegmentator: out 1 |
| head_most_level_cut_at_the_top | enhance_pet: out 36, totalsegmentator: out 1002 |

## How the counts move with S1_VIEW_MM (20 mm in the rule)

| s1 view mm | verdicts (studies) |
|---|---|
| 10 | admitted 1737, look 21, not_admitted 2155 |
| 30 | admitted 1736, look 22, not_admitted 2155 |

## Unread

none
