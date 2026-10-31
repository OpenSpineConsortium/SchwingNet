# The trimmed check of the gold tier 3 correlation prior: implementation spec

Source: the thread "Train on randomized spine phantoms" of the project symphony_3, 2026-10-31; the
design workflow's output and its three critiques (statistics, measurement, scope); the eleven
decisions of the task that asked for this spec. Written against SchwingNet origin/main d629a8c and
bordercall origin/main 1ef008f. Nothing here is committed, run on the grid or sent anywhere.

What the check is: descriptive lines printed after the fit by the same CPU job
(grid/morphometry-prior.sbatch), read jointly by a session with READING.md, which is frozen with
its sha256 before the first send. What it is not: no person-effect model P, no blend, no EM, no
fivefold model choice (the design's S7), no automatic choice and no flag that picks a model (the
design's S10). The check fits nothing beyond the published Kronecker form and its refits on level
subsets, and decides nothing; greg makes every choice.

Contents: 1 files; 2 data flow and reserve safety; 3 notation, nulls, bootstraps, seeds, formats,
floors; 4 the sections, in print order; 5 failure, time and line shape; 6 population_parts and the
counts line; 7 vendoring columns.py; 8 the sbatch; 9 the gate; 10 tests; 11 the research note, the
index line and the memory change; 12 line budget; 13 runtime; 14 deferred; 15 open questions.

Example lines below are made-up values in the right shape, never results; each carries its length
with the "- " the sbatch adds, readable (enhance_pet head, 28 characters) then worst (the
totalsegmentator head, 33, with the widest values). Every format was run through the gate's own
filters (grid/shape-words.awk, grid/report-shapes.awk, grid/redact.sed) and came out unchanged:
87 formats, the longest worst case 195 characters (scratch lines/catalog.py and catalog.json).


## 1. Files

| File | Change |
|---|---|
| grid/prior/prior_rows.py | new, standard library only: who is read (Split, Kept), the second reader of the rows (study_rows), the facts reader, protocol classes, plain names, the numpy-free lines and the line-shape guard |
| grid/prior/prior_check.py | new, numpy: the check's sections S0 to S15 and check_all |
| grid/prior/gold3_prior.py | membership through prior_rows.Split; population_parts fills members; the counts line split by reason; run writes report.lines and fit.rc, then check.lines; --draws |
| grid/prior/schwingcheck/columns.py | new, vendored byte for byte from bordercall 8ae5db9 |
| grid/prior/VENDORED | one line added for columns.py |
| grid/morphometry-prior.sbatch | facts.jsonl archived; PRIOR_DRAWS; check.lines printed; the fit's exit kept when the check ends the interpreter |
| grid/gate.sh | word_morphometry_prior: six more paths checked at the commit; READING.md held to its sha256; header comment |
| tests/test_gold3_prior.py | make_inputs extended; the counts substring; the tests of section 10 |
| tests/test_gate.py | prior_commit adds the reading guide; PRIOR_DRAWS; the new assertions and cases of section 10 |
| docs/research/gold3-prior-check/README.md | new: the research note (section 11) |
| docs/research/gold3-prior-check/READING.md, READING.md.sha256 | new: the reading guide (the draft beside this spec) and its freeze |
| docs/research/gold3-prior-check/truths/ | new: the matched truths' records the guide quotes, with a README naming their sources |
| docs/research/README.md | one line |
| docs/memory/the-correlation-prior.md, docs/memory/MEMORY.md | the correction of section 11 |

No new dependency: prior_rows.py is standard library; prior_check.py uses numpy, which the job's
interpreter already must import (the sbatch's take()). Both run on Python 3.8: no walrus, no
match, no dict union, no list[int] annotations at run time (from __future__ import annotations,
as gold3_prior.py has), dataclasses and namedtuple only.


## 2. Data flow and reserve safety

The rule: a study the fit may not read is dropped before any statistic is computed or any line is
written, and every reader the check adds reads only the studies the fit kept.

Today the rows file is parsed whole by CORR.read_rows, reserve persons included, and the reserve is
dropped afterwards (gold3_prior.py lines 123 and 131; scope critique [2.2]). That stays: parsing is
not reading for a statistic. The docstring's wording is corrected to say so ("the test reserve is
parsed with the file and dropped before any statistic is computed or any line is written").

The members. population_parts takes an optional dict `members` and fills, for each level set,
`members[name] = {"fit": [Kept, ...], "held": [Kept, ...]}`, each list in the order of the value
rows it returns (section 6). `Kept = namedtuple("Kept", "index raw sid person unit")`: index into
read_rows' order, the rows file's raw id, the admission's id, the person key, the unit (the repeat
group's unit, else the person). The person keys and ids stay in memory; no line holds one.

The readers of the check, each filtered by the members of the C3..L5 fit part:
- values: the fit part's array population_parts already returns (kept fit studies x 22 levels x 5
  measures, NaN where missing); the whole fit spines W are its rows with all 110 cells finite,
  CORR.complete's rule, which is the fit's own;
- study_rows(path, kept_raw, keys): a second pass over the rows file that skips every row whose
  study is not a kept raw id before it looks at the key, level or value, and keeps only the keys
  slice_mm (level "study"), code (level "study", the stamp in the note), flag:body_foramina
  (cervical levels, value empty) and canal_ap and canal_w (per level); these are the keys
  bordercall morphometry/__main__.py lines 131 to 133 and morphometry/anatomy.py line 352 write
  (at 9c85de1, the engine of stamp 1cee7ea83e4c28db; the same at 1ef008f);
- study_facts(records, population, kept_sids): enhance_pet only, data/gold3-ct/enhance-pet/
  facts.jsonl, keeping a line only when its "id" (zero-padded, "0001") is a kept sid, and from it
  only "site" and "scanner"'s "model" and "kernel"; other populations get no facts;
- the units: Kept.unit, which Split took from data/splits/latent-prior-repeat-groups.json through
  unit_map, as the fit's held-out hash does.

The held part is counted (whole held spines and held studies, for S0's line) and never read for
any statistic; it stays the fit's untouched score.

What is kept out, in this order, unchanged from today: not admitted (admission.json), a reserve
person (latent-prior-test-reserve.json), then the anomaly removals by reason, L6 first, then T13,
then no L5 row, each study counted once under its first reason; the rest are cut into fit and held
by the hash of the unit (held_out). The split by reason is new in the counts line only.


## 3. Notation, nulls, bootstraps, seeds, formats, floors

Levels C3..L5 are indices 0..21 (C3-C7 0-4, T1 5, T2-T12 6-16, L1-L4 17-20, L5 21; T2-L4 6-20;
T1-T4 5-8; T5-T12 9-16). Measures: e endplate 0, d endplate_depth 1, l endplate_lower 2, ld
endplate_lower_depth 3, h h_post 4. A cell is c(l, m) = 5 l + m. The ten pairs in order: ed el eld
eh dl dld dh lld lh ldh; the six plate pairs leave out h: ed el eld dl dld lld. The width pair is
el, the depth pair dld.

X: the whole fit spines in mm, (n, 22, 5). Z: X standardised per cell over those n spines with
ddof 1 (CORR.standardise). C = Zf' Zf / (n - 1), Zf = Z reshaped (n, 110); C has a unit diagonal.
(RL, RM) = CORR.flip_flop(Z), unshrunk correlations; K = kron(shrunk(RL, 0.05), shrunk(RM, 0.05)),
the prior as drawn. A statistic s computed on C and on K gives misfit m = s(C) - s(K). K's own
values are what the generator draws before its size factor and noise.

Shared definitions:
- same(S, R, i, j) = mean over levels l in R of S[c(l,i), c(l,j)];
- lag1(S, D, i, j) = mean over l in D of S[c(l,i), c(l+1,j)]; DISCS = the 14 discs inside T2..L4,
  l in 6..19;
- far(S, A, B, i, j, lag) = mean over a in A, b in B with b - a >= lag of
  0.5 (S[c(a,i), c(b,j)] + S[c(a,j), c(b,i)]), the two orders averaged;
- K's facing and far across a disc are equal (both RL(l,l+1) times RM(i,j), shrunk), so K's facing
  minus far is 0, and K's lag-one same-measure value is the same for every measure, so the range
  of the five is 0 under K;
- normal scores: Blom's, (rank - 3/8) / (n + 1/4) through the inverse normal, per cell; the inverse
  normal is statistics.NormalDist().inv_cdf, standard library;
- robust z: (x - median) / (1.4826 MAD) per cell.

Strata. pooled: W with Z as above. within: the classes with at least 30 whole fit spines pooled,
each cell standardised within its class (ddof 1), C_w = Zf' Zf / (n - k) for k classes; needs at
least 2 such classes and 60 spines. autopet: the whole fit spines of class 2.5 mm whose facts say
site autoPET, standardised within the stratum; needs 60 spines. Each stratum has its own (RL, RM)
and K from its own Z.

Parametric null, per stratum, B draws (B = --draws, default 200, 1 to 2000): draw n spines from
N(0, kron(RL_u, RM_u)) with that stratum's unshrunk refit (Cholesky factors of each; CORR.nearest_pd
first if a factor fails), standardise as the stratum does (within class for within, the same class
sizes), compute C_b, refit (flip_flop, shrunk) to K_b, and every null statistic of that stratum,
the subset refits included for pooled. Null mean and SD (ddof 1) over the draws; z = (m - null
mean) / null SD. The null treats spines as independent Gaussians, so z overstates (statistics
critique [0.9]); the reading rests on sizes and on the bootstrap.

Unit bootstrap, per stratum, B draws: the stratum's units (Kept.unit of its whole spines) drawn with
replacement, as many as it holds, each bringing all its whole spines; re-standardise as the stratum
does, recompute C, refit and the statistic. boot SE = SD over the draws (ddof 1); z_boot = (m -
null mean) / boot SE. A draw that raises (a cell with no spread) is skipped; with fewer than half
the draws left the line prints "boot se none" in place of the two numbers. Intervals are the 2.5
and 97.5 percentiles of the draws.

Seeds: seed_of(population, purpose) = int(sha256(("gold3-prior-check:%s:%s" % (population,
purpose)).encode()).hexdigest()[:8], 16), one numpy default_rng per purpose: null pooled, null
within, null autopet, boot pooled, boot within, boot autopet, boot levels, boot ratios, boot neck,
boot icc, boot corrected, generator. No seed is ever printed.

Formats: a correlation "%.2f" (by level "%d" in hundredths); a misfit, null mean or change "%+.3f";
an SD or SE "%.3f"; z "%+.1f" clipped to -999.9 and +999.9; mm "%.1f" clipped to 999.9; a share
"%.1f%%" or "%.2f%%" clipped to 99.9 and 9.99; a ratio SD "%.3f" clipped to 9.999. A number that
is not finite prints "none".

Floors: the check runs only where the C3..L5 fit took at least 30 whole spines; a class enters a
by-class line with at least 30 whole fit spines; a refit inside a class needs 60; a neck branch at
one level needs 10 vertebrae; a canal mean needs 15 levels with a value in that spine; S8 needs 10
units with at least two whole fit spines, and its corrected r 10 units wholly inside autopet.

Protocol class, from each kept study's slice_mm (the head-foot spacing, the same as facts.jsonl's
mask zooms at head_foot_axis): at most 1.5 mm (<= 1.5); 2.5 mm (over 1.5 to 2.6, holding Leipzig's
one 2.0 mm study); 2.8 mm (over 2.6 to 2.9); 3 mm (over 2.9 to 3.5); 5 mm (over 3.5; every such
study in facts.jsonl is at 5.0); no spacing row. TotalSegmentator's rows are on a 1.5 mm grid, so
it is one class. Expected among enhance_pet's 693 whole fit spines, by the facts' proportions
(the job alone sees the real mix): 2.5 mm about 355 to 365, 3 mm about 150, at most 1.5 mm about
100 to 110, 5 mm about 78 to 85, 2.8 mm about 8.

A by-class line packs "class values" items separated by "; " and splits before the item that
would pass 196 characters, the second line repeating the text before the colon; with the four
classes above none splits.


## 4. The sections, in print order

Print order: S0, S11, S12, S1, S2, S4, S5, S6, S13, S9, S14, S15, S8, done. Every line is the head
"<population> C3..L5 check: " and a text; below only the text is given. Section names keep the
design's numbering so the critiques' references still find them; S3, S7 and S10 are gone.

### S0 inputs and internal consistency

Inputs: the kept fit studies of C3..L5 (809 in enhance_pet), their code rows through study_rows,
W, the in-memory prior the fit just wrote (CORR.fit's result), the held counts.

Computation: the stamps are the notes of the kept fit studies' code rows; a note that is not 16
lowercase hex characters, or a kept fit study with no code row, counts as "not 16 hex", and the
note itself is never printed (the words carry no apostrophe, which check_line refuses, so the line
cannot fault S0 and end the check). The refit is shrunk(flip_flop(Z)) against the prior's r_level
and r_measure, the largest absolute difference, an internal consistency check only (statistics
critique [0.5]): it shows the check reads the spines the fit read and cannot catch a reading bug
the two share. The missing share is the NaN share of each measure over the kept fit studies' 22
cells, with the region holding the most.

Lines (3):
- stamp: "rows at one code stamp %s; whole fit spines %d of %d kept, whole held %d of %d; refit
  against the fitted prior, largest difference %.0e" e.g. "rows at one code stamp 1cee7ea83e4c28db;
  whole fit spines 693 of 809 kept, whole held 158 of 190; refit against the fitted prior, largest
  difference 0e+00" (182/191); or, with several stamps, "rows at %d code stamps, the commonest %s on
  %d of %d kept fit studies; whole fit spines %d, whole held %d; refit against the prior %.0e"
  (181/191); in either form a stamp that is not 16 hex is written "not 16 hex", e.g. "rows at 2
  code stamps, the commonest not 16 hex on 801 of 809 kept fit studies; ..." (175/185);
- legend: "legend: e endplate, d endplate_depth, l endplate_lower, ld endplate_lower_depth, h
  h_post; pairs ed el eld eh dl dld dh lld lh ldh; plate pairs leave out h" (183/188);
- missing: "missing cells of the kept fit studies: e 1.2%, d 0.8%, l 1.1%, ld 0.9%, h 2.0%; most in
  C3-C7, 4.1%; z is per cell over the whole fit spines" (168/180).

Expected for enhance_pet (scope critique [2.9]): fitted 693, held 158, the width pair 0.301 and
the depth pair 0.463 shrunk, stamp 1cee7ea83e4c28db (the covariates record of 04:42:22 UTC says
every set's rows are at it). A fault here ends the population's check (no later section runs).

### S11 protocol classes

Inputs: W's slice_mm (study_rows) and, for enhance_pet, facts by kept sid. Pooled Z for the mean z
lines; within-class z for the same-level-by-class line.

Lines, per class of at least 30 whole fit spines, in the class order of section 3:
- class: "class %s, %d spines: <site count, ...>; models %d, top %s %d; kernels %d, top %s %d"
  e.g. "class 2.5 mm, 365 spines: autoPET 364, Leipzig 1; models 2, top Biograph128 300; kernels 2,
  top I31f-2 200" (134/195). Names go through plain_name: runs of anything but letters and digits
  become "-", ends trimmed, cut at 21 characters, "unnamed" when empty or when the name would break
  a shape rule (a facts kernel is sometimes a list's text, "['I31f', '2']", which becomes I31f-2).
  For a population without facts: "class %s, %d whole fit spines: sites, models and kernels are
  read for enhance_pet alone" (127/132);
- meanz-a and meanz-b: each measure's mean pooled z by region: "class %s mean z by C3-C7 T1 T2-T12
  L1-L4 L5: e ..., d ..., l ..." (174/187) and "...: ld ..., h ..." (142/155); an offset of a class
  shows here (measurement critique [1.0]);
- same-by-class: within-class z, "same level, class %s, over C3-C7 T1-T4 T5-T12 L1-L4: el %s, dld
  %s; h with e d l ld %s" e.g. "same level, class 5 mm, over C3-C7 T1-T4 T5-T12 L1-L4: el 0.60 0.40
  0.30 0.35, dld 0.50 0.45 0.47 0.49; h with e d l ld 0.05 0.10 0.04 0.09" (167/194); the regions
  split at T4 because on thick slices the plates are read from slabs that share or abut a voxel
  layer down to about T4 (measurement critique [1.1]); the h pairs per class answer [1.6];
- once: hpost: h_post's SD in mm by class, sqrt of the mean over a region's levels of the per-level
  variance (ddof 1): "h_post SD in mm by class, C3-C7 then T2-L4: at most 1.5 mm 1.6 1.7; 2.5 mm 1.9
  2.0; 3 mm 2.0 2.1; 5 mm 2.6 2.7" (138/169);
- once, when any class is under 30: "classes under 30 whole fit spines, left out of every by-class
  line: 2.8 mm 8" (104/179);
- when only one class reaches 30: "one protocol class, so the by-class lines and the within-class
  reruns are the pooled ones and are not printed" (137/142), with the class line and hpost.

### S12 anchors outside the computation

Inputs: X in mm. Each measure's mean and SD (ddof 1) at each level. Two lines per measure:
- "anchors %s, mean then SD in mm, C3 to T6: %.1f %.1f, ..." (177/194) and "..., T7 to L5: ..."
  (178/194), eleven levels each.

Why: the only test of the reading code that does not share its inputs (statistics critique [0.5],
measurement [1.8]): the shape (widths and depths growing caudally, the step from C7 to T1, depth
below width in the lumbar spine), the card, the CT papers of bordercall
records/morphometry-2026-10-29/compare-229.csv, and the other population, level by level.

### S1 same level

Inputs: pooled C and K, plus the within and autopet strata.

Lines:
- pair, ten lines, one per pair: "same level %s: C3-C7 %.2f T1 %.2f T2-T12 %.2f L1-L4 %.2f L5 %.2f
  all %.2f ranks %.2f; drawn %.2f; misfit %+.3f null %+.3f sd %.3f z %+.1f": raw same(C, region),
  all over the 22 levels, ranks the all value on normal scores, drawn K's value (shrunk RM(i,j)),
  misfit all minus drawn with its pooled null; e.g. "same level el: C3-C7 0.21 T1 0.15 T2-T12 0.33
  L1-L4 0.35 L5 0.30 all 0.30 ranks 0.31; drawn 0.29; misfit +0.004 null +0.001 sd 0.004 z +0.8"
  (167/183);
- six: the mean over the six plate pairs of all, drawn and misfit, with null and boot: "same level,
  the six plate pairs: raw %.2f drawn %.2f misfit %+.3f null %+.3f sd %.3f z %+.1f, boot se %.3f z
  %+.1f" (144/155); it corroborates P1 and is not a primary (statistics critique [0.1]);
- by-level, two lines, el and dld: "same level el by level C3 to L5, in hundredths: 22 20 19 ..."
  (141/169) (statistics critique [0.11]);
- by-level-se: the unit bootstrap (boot levels) of each level's el and dld: "same level by level,
  unit bootstrap SE: median el %.3f dld %.3f; largest el %.3f at %s, dld %.3f at %s" (134/141);
- within-ten and within-six: "within class, %d spines in %d classes, same level ten pairs: %s"
  (139/154) and "within class, same level, the six plate pairs: raw ... boot se %.3f z %+.1f"
  (158/169), from the within stratum's own C, K, null and bootstrap;
- ap-ten and ap-six: "autoPET 2.5 mm alone, %d spines, same level ten pairs: %s" (134/149) and
  "autoPET 2.5 mm alone, same level, the six plate pairs: ..." (166/177);
- for each stratum under its floor, one line in place of that stratum's two lines here and its two
  in S4: "reruns within class, of the same-level and far-apart lines: not run, under two classes of
  30" (120/125), its one reason, since two classes of 30 already hold the stratum's 60 spines;
  "reruns in autoPET 2.5 mm alone, of the same-level and far-apart lines: not run, under 60 spines"
  (123/128), which totalsegmentator, with no site facts, always prints. A stratum that runs prints
  its four lines and no not-run line, so each stratum's state is read on its own.

### S2 one level apart and across a disc

Inputs: pooled C and K; the class strata for the by-class line.

Lines:
- lag-m, five lines, one per measure, raw lag1(C, group, m, m) by adjacent group, the upper level
  of each pair in C3-C7 0-3, C7-T2 4-5, T2-T12 6-15, T12-L4 16-19, L4-L5 20: "one level apart,
  same measure, e: C3-C7 0.62 C7-T2 0.31 T2-T12 0.71 T12-L4 0.69 L4-L5 0.40" (118/129);
- lag-core: lag1(C, DISCS, m, m) for the five and the range of the five, its misfit (K's range is
  0) with the pooled null: "one level apart in T2 to L4, same measure: e %.2f d %.2f l %.2f ld %.2f
  h %.2f; range of the five, misfit %+.3f null %+.3f sd %.3f z %+.1f" (169/180); a measure with its
  own noise, or a factor that leaves one measure out, widens the range;
- disc, two lines, widths then depths: facing = lag1(C, DISCS, l, e) (the lower plate of the upper
  body with the upper plate of the body below), far = lag1(C, DISCS, e, l); depths with ld and d:
  "across a disc in T2 to L4, widths: facing %.2f far %.2f, facing minus far %+.3f null %+.3f sd
  %.3f z %+.1f, boot se %.3f z %+.1f" (160/169); this is P2;
- disc-groups: facing minus far over the discs whose lower vertebra is T3 to T9 (the task's
  "T2-T9", the discs from T2-T3 to T8-T9), T10 to T12 and L1 to L4: "facing minus far by disc
  group, the lower vertebra T3-T9 T10-T12 L1-L4: widths %s; depths %s" (156/161);
- disc-class, two lines: within-class z, over DISCS then over the L1-L4 group: "facing minus far by
  class, widths over T2-L4 then L1-L4: at most 1.5 mm +0.05 +0.07; 2.5 mm ..." (167/192), and the
  same for depths.

### S4 far apart

Inputs: pooled, within and autopet C and K.

Lines:
- far-pairs: far(C) - far(K) over C3-C7 with L1-L4 for each plate pair, and whether all six share a
  sign (all above 0 or all below): "far apart, C3-C7 with L1-L4, misfit by plate pair ed el eld dl
  dld lld: %s; one sign" or "...; signs differ" (151/160);
- far-mean, only when one sign: "far apart, C3-C7 with L1-L4, mean of the six plate pairs: raw %.2f
  drawn %.2f misfit %+.3f null %+.3f sd %.3f z %+.1f, boot se %.3f z %+.1f" (169/180); this is P1;
  else "far apart, C3-C7 with L1-L4: the six plate pairs differ in sign, so no mean is taken"
  (112/117), never an average over pairs of opposite sign;
- far-core: over T2..L4 with b - a >= 6: "far apart in T2 to L4, six or more levels, misfit by plate
  pair: %s; mean %+.3f null %+.3f sd %.3f z %+.1f" (175/182), or "...; signs differ";
- within-pairs and within-mean, ap-pairs and ap-mean: the same two lines on the within and autopet
  strata (148/153, 163/172, 152/161, 171/180); these are P1's two reruns. A stratum under its floor
  prints neither; S1's not-run line for it stands for both sections.

### S5 refits over level subsets

Inputs: W; the subsets' cells of the same spines (standardising per cell, a subset's z are the
pooled z's cells).

Computation: flip_flop on each subset, unshrunk; the width pair change is RM_sub(e,l) - RM(e,l),
the C3..L5 refit unshrunk; each null draw refits the subsets too; the T1..L5 change also gets the
pooled bootstrap; by class, both refits inside a class of at least 60.

Lines:
- base: "refit C3..L5 unshrunk, ten pairs: %s" (112/126);
- sub, five lines, T1..L5, T2..L4, T1..L4, T2..L5, C3..C7: "refit %s on the same spines: %s; width
  pair change %+.3f null %+.3f sd %.3f z %+.1f" (166/181) (measurement critique [1.8]); the depth
  pair's change is read from the ten pairs against base;
- change: "width pair change from C3..L5 to T1..L5: %+.3f null %+.3f sd %.3f z %+.1f, boot se %.3f
  z %+.1f" (126/134); this is P3;
- change-class: "width pair change from C3..L5 to T1..L5 by class: at most 1.5 mm %+.3f; ..."
  (140/160).

### S6 tails and robustness, descriptions only

Inputs: X and Z of W.

Lines:
- tails: the share of cells beyond 4 robust SD by measure, the region with the most: "beyond 4 SD
  on robust z, median and MAD: e 0.30% d 0.25% l 0.28% ld 0.22% h 0.40%; most in C3-C7, 1.10%; a
  Gaussian gives 0.006%" (156/168); a description, never a trigger, since a t with 3 to 4 degrees
  of freedom reaches 0.5% and does not bias the fit (scope critique [2.11]);
- paired: within-class robust z; the share of vertebrae whose two widths are both beyond 3 on the
  same side, and of those whose two depths are, by class: "paired tails beyond 3 robust SD, widths
  depths, by class: at most 1.5 mm 0.10% 0.05%; ..." (168/193) (measurement critique [1.2]);
- winsor: robust z clipped at -4 and +4 per cell, mapped back as median + 1.4826 MAD z, then
  standardised and refitted unshrunk: "winsorised at 4 robust SD, refit C3..L5 unshrunk: width pair
  %.3f depth pair %.3f, change %+.3f %+.3f" (133/140) (statistics critique [0.10]);
- ns-refit: normal scores per cell, refitted unshrunk: "normal-scores refit C3..L5 unshrunk, ten
  pairs: %s" (126/140);
- ns-gap: normal-score same-level r over all levels minus Pearson's, the six plate pairs, signed,
  and the largest absolute: "normal scores minus Pearson, same level, six plate pairs: %s; largest
  absolute %.3f at %s" (157/163), read two-sided.

### S13 the canal test

Inputs: canal_ap and canal_w rows of W's studies at C3..L5 (study_rows). Per spine: the plates'
mean z, over the 88 plate cells (pooled z; within-class z for a class); the canal's mean z, over
the levels with a value of the canal z standardised per level over W's spines that have it (within
class for a class), only for spines with 15 such levels. r is Pearson over spines.

Lines: "canal test, r over spines of the plates mean z with canal_ap mean z: all %.2f of %d; at most
1.5 mm %.2f; ..." (173/193), and the same with canal_w; for one class, one line: "canal test, r
over spines of the plates mean z: with canal_ap %.2f, with canal_w %.2f, of %d spines" (129/136).
A per-scan shift of the mask's bone boundary moves every body measure one way and the canal the
other (measurement critique [1.7]).

### S9 the neck, by level, branch and class

Inputs: W's cervical cells C3..C7 and each one's branch: fallback where a flag:body_foramina row
exists at that study and level (no closed foramen transversarium was found, so the body is cut at
the canal's side walls and a millimetre beyond; bordercall morphometry/anatomy.py, clip_to_foramina,
applied from C2 to C7), else foramina. Within-class z; classes of at least 30.

Computation, per class and level: each branch's count, e's and l's mean z, the within-branch r of
e with l, and the share of vertebrae whose e and l agree within 1 mm; the pooled r over both
branches; the covariance of e and l in z split as T = W + B with divisor n, W = sum_b (n_b / n)
cov_b and B = sum_b (n_b / n)(mean_e,b - mean_e)(mean_l,b - mean_l); the difference of the
within-branch r, fallback minus foramina, averaged over C3-C7 with weights min(n_foramina,
n_fallback) at levels where both branches hold 10, with a unit bootstrap interval (boot neck); the
centred refit: e and l at C3..C7 centred in mm within (level, branch), the array re-standardised and
refitted unshrunk, the width pair before and after (statistics critique [0.6], measurement [1.4],
scope [2.6]). A branch under 10 prints "%s %d too few". Once, pooled over branches and classes: at
each of C3..C7 the mean in mm of canal_w (study_rows, over W's spines with a value there) beside
the means of e and l, so a reader sees where the fallback cut falls against each plate
(measurement critique, missing item on the cervical canal widths). The fallback keeps the body
within half the median width of the full rings' canal plus 1 mm each side of the midline
(anatomy.py clip_to_foramina), a span of about that width plus 2 mm; canal_w is the rows' own
canal width, read over the slabs across the body's middle half (scanimport geometry.py), close to
but not the same reading, so the line places the cut and does not measure it.

Lines:
- legend: "neck: foramina is the body cut at the foramina, fallback the cut at the canal side
  walls; e and l pooled mean z; r within a branch; agree, widths within 1 mm" (185/190);
- level, per class and level: "neck C5, 2.5 mm: pooled r 0.27; foramina 210 e -0.05 l +0.02 r 0.25
  agree 4%; fallback 155 e +0.10 l -0.03 r 0.40 agree 18%" (151/170);
- cov, per class: "neck widths covariance in z, within then between, C3 to C7, %s: +0.20 +0.05,
  ..." (159/172);
- diff, per class: "neck, %s: fallback minus foramina width-pair r over C3-C7, levels weighted by
  the smaller count: %+.2f, unit bootstrap %.2f to %.2f" (163/178);
- canal, once: "neck mean widths in mm, canal_w then e then l, C3 to C7: 24.1 25.2 19.3; 24.5 26.0
  19.6; 25.0 27.1 21.0; 25.3 28.0 23.9; 24.9 29.0 23.8" (163/183);
- centred, pooled: "neck widths centred within level and branch, refit width pair: %.3f before,
  %.3f after" (116/123);
- centred-class: "neck widths centred within level and branch, refit width pair change by class:
  ..." (169/174).

### S14 plate ratios, model-free

Inputs: X in mm.

Computation: per level, the SD (ddof 1) of log(e / l) and of log(d / ld); the medians over levels
of the depth ratio's SD in C3-C7 and L1-L4 and of the width ratio's in T2-L4, with unit bootstrap
SEs (boot ratios); the mismatch: a vertebra is off when |(e / l) / (mean_e / mean_l) - 1| > 0.2 at
its level (the level's ratio of means over W), likewise for depths, the same "excess" the design's
plate_mismatch.py used; the share of spines holding an off vertebra and of vertebrae off, over
C3..L5 and T2..L4.

Lines:
- ratio-w and ratio-d: "SD of log of e over l by level C3 to L5: %s" (178/184), "SD of log of d over
  ld by level C3 to L5: %s" (179/184);
- ratio-primary: "plate ratios, median SD of log ratio: depths C3-C7 %.3f L1-L4 %.3f, NHANES II 0.030
  to 0.036 and 0.017 to 0.019; widths T2-L4 %.3f; boot se %.3f %.3f %.3f" (188/193); this is P4;
  the NHANES II figures are fixed text (Hipp 2022, JBMR Plus, PMC9549721, Appendix S1: the CV of
  the upper over lower end-plate AP width ratio on lateral films, C3-C7 0.036 0.034 0.036 0.032
  0.030 and L1-L5 0.018 0.018 0.017 0.019 0.024, trimmed at 2 SD);
- ratio-class: "plate ratios by class, median SD of log ratio, depths L1-L4 then widths T2-L4: at
  most 1.5 mm %.3f %.3f; ..." (189/194);
- mismatch: "spines holding a vertebra over 20% off its level ratio of means, C3..L5: widths %.1f%%
  depths %.1f%% either %.1f%%; T2..L4: ..." (166/177);
- mismatch-v: "vertebrae over 20% off their level ratio of means, C3..L5: widths ...; T2..L4: ..."
  (145/156).

### S15 the generator check

Inputs: the in-memory C3..L5 prior (shrunk), the data's margins ref[m][level] = (mean, SD ddof 1)
over W in mm, the vendored generator. columns.draw_columns(ref, ["typical"], seed_of(population,
"generator"), 5000, MEASURES, noise_mm=1.0, scale_sd=0.07, correlation=prior), every other argument
at its default: power None is 1 for every measure, which is right since all five are lengths in
bordercall schwingcheck/data/panjabi_long.csv at 8ae5db9 (run_naming passes s.powers, the same
ones); rho, r_between and blend do not act with a prior and the typical column. The drawn values
are (5000, 22, 5) with no NaN, the typical column's levels being schwingcheck.LEVELS, C3 to L5.

Computation: the drawn cells standardised by their own means and SDs, then the same aggregates as
the data's: same-level el and dld by region (S1's); the lag profile, for k 1 to 5 the mean over
measures and over level pairs (l, l+k) of the same-measure correlation (S2's, the critiques' lag
profiles); the far-apart raw value over C3-C7 with L1-L4, the mean over the six plate pairs of
far(C) (S4's raw value, which the scope critique [2.3] asks to set beside the drawn); the plate
ratios' median SD of log ratio, depths at C3-C7 and L1-L4 and widths at T2-L4, from the drawn mm
values (S14's, which the statistics critique [0.3] and its missing item on a model-free plate test
ask for drawn as well); the mismatch shares of S14. The size factor cancels in a ratio, so the
drawn ratio SD shows what the prior's same-level coupling, the margins and the noise give a
phantom's plates, the plausibility the investigation was opened for. The variance shares per
cell are analytic: V = mu^2 Var(g) + sd^2 E(g^2) + noise^2 with Var(g) =
e^(2 s^2) - e^(s^2) = 0.004936 and E(g^2) = e^(2 s^2) = 1.009848 at s 0.07; size share mu^2 Var(g)
/ V, noise share 1 / V, drawn SD over data SD sqrt(V) / sd. This is the check the scope critique
asks for ([2.3]): the generator multiplies each column by its own size factor on top of a prior
that was fitted on spines that already carry whatever whole-spine factor they have.

Lines (8):
- legend: "generator check: 5000 typical columns from draw_columns with the fitted prior, size SD
  0.07 and noise 1.0 mm as run_naming, and the data cell means and SDs" (183/188);
- same, two lines, el and dld: "generator check, same level el, drawn then data: C3-C7 %.2f %.2f,
  T2-T12 ..., L1-L4 ..., all %.2f %.2f, data boot se %.3f" (162/176, 163/176);
- lags: "generator check, one to five levels apart, same measure, drawn %s, data %s" (146/161); this
  is P5;
- far: "generator check, far apart, C3-C7 with L1-L4, raw mean of the six plate pairs, drawn then
  data: %.2f %.2f" (133/140);
- ratios: "generator check, plate ratios, median SD of log ratio, drawn then data: depths C3-C7
  %.3f %.3f, L1-L4 %.3f %.3f; widths T2-L4 %.3f %.3f" (169/174);
- mismatch: "generator check, spines with a vertebra over 20% off, drawn then data: widths %.1f%%
  %.1f%%, depths ..., either ..." (157/168);
- variance: "generator check, a cell variance: size factor share median %.2f, range %.2f to %.2f;
  noise share median %.2f; drawn SD over data SD median %.2f" (171/177).

run_naming draws from the card's margins, not the data's, so its size share differs (the design's
results-phantom.json, card margins: 0.32 on average); the check uses the data's margins, as
decided.

### S8 the repeat units

Inputs: the units of W (Kept.unit) with at least two whole fit spines, all enhance_pet; none in the
other populations. The units were joined by matching vertebral volumes, spacings and ribs
(data/splits/latent-prior-repeat-groups.json, "probable repeat scans of one patient"), so pairs
agree on size by construction: every ICC is an upper bound on repeatability within one protocol
(statistics critique [0.4], measurement [1.5], scope [2.5]).

Computation:
- ICC(1) per cell in mm, one-way with unequal unit sizes: MSB = sum_g k_g (mean_g - mean)^2 / (g -
  1), MSW = sum_g sum_i (y - mean_g)^2 / (N - g), k0 = (N - sum_g k_g^2 / N) / (g - 1), ICC =
  (MSB - MSW) / (MSB + (k0 - 1) MSW); a region's ICC is the mean over its levels; T2-L4 also gets
  a unit bootstrap percentile interval (boot icc);
- the within-unit SD in mm: sqrt of the mean over a region's levels of MSW;
- the ratio ICCs: ICC(1) of log(e / l), log(d / ld) and log(h / d) per level, the mean over T2-L4,
  with a unit bootstrap interval;
- the within-unit error correlation of each pair: each spine's pooled z minus its unit's mean, the
  deviations of all levels pooled, Pearson per pair, with boot SEs for el and dld;
- the corrected r, in the autopet stratum only, over the units wholly inside it (10 at least), z
  standardised within the stratum: E(i,j) = sum over units and spines of the deviation products
  over sum of (k_g - 1), the pooled within-unit covariance, each a mean over T2..L4; corrected =
  (C(i,j) - E(i,j)) / sqrt((1 - E(i,i))(1 - E(j,j))), C the stratum's raw same-level value over
  T2..L4; "over 1" when the denominator is 0 or below or the value passes 1 in size;
- its unit bootstrap (boot corrected) for el and dld, as the statistics critique [0.4] asks: each
  draw resamples the stratum's units as the unit bootstrap does, singletons included, and
  recomputes C, E and the corrected value; a draw with fewer than 10 units of two or more spines is
  skipped, a draw past 1 in size or with no positive denominator enters the percentiles at 1 with
  its sign (or at 1 when the sign is not defined) and is counted, and with fewer than half the
  draws left the line prints "boot none" in place of its numbers.

Lines (12):
- units: "repeat units in the fit part: %d holding %d spines (%s); %d all autoPET 2.5 mm, %d of mixed
  classes, %d other" (165/191);
- caveat: "repeat units were found by matching volumes, spacings and ribs, so each ICC below is an
  upper bound on repeatability within one protocol" (164/169);
- icc, five lines: "ICC1 e by C3-C7 T1 T2-T12 L1-L4 L5: 0.85 0.80 0.90 0.92 0.88; T2-L4 0.91, unit
  bootstrap 0.86 to 0.94" (129/143);
- within-sd: "within-unit SD in mm, C3-C7 then T2-L4: e 1.5 1.2, d 0.9 0.8, l 1.4 1.1, ld 0.9 0.8, h
  1.3 1.0" (122/137);
- ratios: "ICC1 of size-free log ratios over T2-L4: e over l 0.40 (0.25 to 0.55), d over ld ..., h
  over d ..." (158/172);
- errcorr: "within-unit error correlation, ten pairs over every level: %s; boot se el %.2f dld %.2f"
  (162/177);
- corrected: "corrected r, autoPET 2.5 mm alone, %d units, same level over T2-L4, raw then corrected:
  el %.2f %.2f, dld ..., ed ..., lld ..." (172/190);
- corrected-boot: "corrected r, unit bootstrap 2.5 and 97.5 percentiles: el %.2f to %.2f, dld %.2f
  to %.2f; draws past 1 in size, el %d dld %d" (149/164); under 10 units wholly inside autopet, the
  two corrected lines are one: "corrected r: not run, fewer than 10 repeat units wholly inside
  autoPET 2.5 mm" (105/110);
- or, in place of all twelve when fewer than 10 units hold two whole fit spines or more (the floor
  of section 3; none at all in totalsegmentator): "repeat units: not run, %d in the fit part hold
  two whole spines or more, under 10" (108/116).

The design's counts, from the repeat-groups file and the published split (statistics critique
evidence): 47 groups in the fit part holding 113 studies (34 of 2, 9 of 3, 2 of 4, 2 of 5); 193 of
the 203 grouped studies are autoPET, 182 of them at 2.5 mm; 11 groups mix slice classes; 28 touch
the reserve. The line counts whole fit spines, so it may show fewer.

### done

"done in %d s, %d draws for each null and each unit bootstrap" (90/97), the seconds of this
population's check.


## 5. Failure, time and line shape

A check failure never fails the fit (decision 7):
- run writes report.lines (the fit's lines) and fit.rc (its exit, 0 or 3) before the check starts,
  then check.lines; it returns the fit's code whatever the check does;
- each section runs inside try/except Exception; a section's lines are printed only when it ends,
  else one line: "fault at S%s, an error of the kind %s" (79/108); later sections still run, except
  after a fault at S0, which ends that population's check (its done line still prints);
- the import of prior_check is inside the try: an import failure prints, for each population, "fault
  at S0, an error of the kind ImportError" (or the error's kind), from prior_rows, which needs no
  numpy;
- the Kind is the exception's class name, kept only when it is an identifier of at most 40
  characters with no run of five digits, no run of eight hex characters and none of the banned
  words; else "Exception";
- not run, one line: "not run, no rows for this population" (verse in the tests); "not run, the
  C3..L5 fit did not run" (verse on the grid, whose fit raises for too few spines); "not run, the
  C3..L5 fit took fewer than 30 whole spines" (83/88);
- the time guard: one budget of 90 minutes from the start of the first population's check, read
  before each section; the first section found late prints "S%s and every section after it not run,
  the check ran past 90 minutes" (96/102) and that population's check ends; a later population
  prints the same at S0. The fit takes 11 s (bordercall records/prior-2026-10-31/report.md) and the
  job's wall time is 2 hours, so the guard leaves half an hour.

The line shape (decision 8), held by prior_rows.check_line(head, text), which raises ValueError, so
the section faults rather than print a bad line:
- it starts "<population> C3..L5 check: " and is at most 194 characters (196 with the sbatch's "- ");
- every colon is followed by a space; no slash; no quote or backtick;
- no run of five or more digits (so no YYYYMMDD date and no seed);
- no run of eight or more hex characters other than one 16-hex stamp in S0's line;
- none of patient, institution, operators, physician, accession (any case), and none of the other
  words grid/redact.sed withholds a whole line for or masks a value after, in any case:
  stationname, deviceserial, instanceuid, studydate, seriesdate, acquisitiondate, contentdate,
  studytime, studyid, "invalid value for vr", bearer, basic, token, secret, credential, password,
  passwd, pwd, apikey, api_key, api-key, authorization, cookie (decision 8 names five; the rest
  keep a line the gate would change from being printed, since a plain name from facts.jsonl is
  free text);
- no "FAILED", "refused:" or "why:", the markers after which grid/report-shapes.awk judges a
  reason, so the gate's rule that nothing follows FAILED but "an error of the kind <Kind>" is never
  touched; no "(first ", "=", a parenthesised pair of four hex characters (a DICOM tag) or five
  numbers joined by dots (a UID), which redact.sed rewrites; printable ASCII only.

The whole report stays under 380 lines and 60,000 bytes (section 12).


## 6. population_parts and the counts line

prior_rows.py (standard library), with the helpers moved from gold3_prior.py and imported back
there under the same names (study_id, person_of, admitted, verse_patients, reserve_persons,
unit_map, held_out, HELD_SHARE, ADMISSION_MEMBER, VERSE_SERIES, TOTALSEG_SUBJECT), so
tests/test_gold3_prior.py's GP.held_out and GP.unit_map keep working:

```python
Kept = namedtuple("Kept", "index raw sid person unit")

def anomaly_sets(path) -> tuple:
    """(studies with an L6 row, with a T13 row, with an L5 row) of one rows file, by raw id."""

class Split:
    """Who of one population's studies the prior and its check may read, from the records."""
    def __init__(self, population: str, rows: Path, records: Path): ...
    def __call__(self, raw_ids: list) -> tuple:
        """(fit [Kept], held [Kept], counts) for read_rows' raw ids, in their order; counts holds
        read, not_admitted, reserved, anomalous and anomalous by reason (l6, t13, no_l5), each study
        counted once, under its first reason in the order not admitted, reserve, L6, T13, no L5."""

def study_rows(path, kept_raw: set, keys: set):
    """(raw, level, key, value, note) of the kept studies' rows with one of keys; any other study's
    row is passed over before its key, level or value is read."""

def study_facts(records: Path, population: str, kept_sids: set) -> dict:
    """{sid: (site, model, kernel)} of the kept enhance_pet studies, plain names; {} otherwise."""

def protocol_class(slice_mm: str) -> str
def plain_name(text, width: int = 21) -> str
def stamp_of(note: str) -> str            # the stamp when it is 16 lowercase hex, else ""
def check_head(population: str) -> str    # "<population> C3..L5 check: "
def check_line(head: str, text: str) -> str   # raises ValueError on a shape rule
def error_kind(exc: BaseException) -> str
def fault_text(section: str, exc: BaseException) -> str
def counts_line(head: str, counts: dict, fit: int, held: int) -> str
def stamp_line(stamps: list, whole_fit: int, fit: int, whole_held: int, held: int, refit: float) -> str
def class_line(name: str, n: int, facts: list) -> str     # facts: [(site, model, kernel)] or []
def units_line(sizes: list, kinds: list) -> str
```

gold3_prior.py:

```python
def population_parts(population: str, rows: Path, records: Path, tally: dict,
                     members: dict = None) -> dict:
    """{level set: (fit values, held values)} of one population; with members given, also
    members[level set] = {"fit": [Kept], "held": [Kept]} in the values' order, the only ids and
    units the check may read."""
    split = Split(population, rows, records)
    out = {}
    for name, levels in LEVEL_SETS.items():
        values, raw_ids = CORR.read_rows(str(rows), levels, MEASURES)
        fit, held, counts = split(raw_ids)
        tally[(population, name)] = counts
        out[name] = (values[[k.index for k in fit]], values[[k.index for k in held]])
        if members is not None:
            members[name] = {"fit": fit, "held": held}
    return out
```

(values[[]] of an empty list keeps the shape (0, L, M), as values[[]] does today with keep lists.)

The counts line, from

    "%s studies %d, not admitted %d, test reserve %d, L6 or T13 or no L5 %d, fit %d, held %d"

to

    "%s studies %d, not admitted %d, test reserve %d, L6 or T13 or no L5 %d (L6 %d, T13 %d, no L5 %d), fit %d, held %d"

e.g. "- enhance_pet C3..L5: studies 1591, not admitted 36, test reserve 514, L6 or T13 or no L5 42 (L6
30, T13 10, no L5 2), fit 809, held 190" (127 characters; the split shown is made up). The total
keeps its words, so a reader of older reports still finds it.

run(root, records, out, draws=200) -> int: as today up to report.lines; it also keeps, per
population, the C3..L5 fit values, members["C3..L5"], the held counts and the prior when the fit ran,
or the not-run reason; then writes report.lines, fit.rc ("0" or "3"), and check.lines from
checked(inputs, records, draws), which imports prior_check inside its try (section 5). It returns 3
when a population failed, else 0, as today. main gains --draws (int, 1 to 2000, default 200).

prior_check.py:

```python
def check_all(inputs: list, records: Path, draws: int, clock=time.monotonic,
              budget_s: float = 5400.0) -> list:
    """Every population's check lines in the order given, under one time budget."""

def check_lines(inp: dict, records: Path, draws: int, deadline: float, clock) -> list:
    """One population's lines: S0 builds the context; each later section returns texts that
    check_line shapes; a section that raises prints its fault line instead."""

SECTIONS = (("S0", inputs_and_consistency), ("S11", protocol_classes), ("S12", anchors),
            ("S1", same_level), ("S2", lags_and_discs), ("S4", far_apart), ("S5", refits),
            ("S6", tails), ("S13", canal), ("S9", neck), ("S14", plate_ratios),
            ("S15", generator), ("S8", repeat_units))
```

inp is a plain dict, so gold3_prior builds it without importing numpy-dependent types: population,
rows (Path or None), values (the C3..L5 fit array), fit ([Kept]), held_whole, held_total, prior
(CORR.Prior or None), not_run ("" or the reason). The context S0 builds holds W, X, Z, C, RL, RM, K,
the strata, the study rows, the facts and the units, and memoises each null and bootstrap with its
exception, so a failed null faults each section that needs it without being drawn again. Each
section is a short function of the context returning a list of texts; the shared statistics
(same, lag1, far, the refits, the null and bootstrap loops) are module functions with names that
read as what they compute.


## 7. Vendoring columns.py

Decision: vendor bordercall schwingcheck/columns.py from 8ae5db9, byte for byte, as
grid/prior/schwingcheck/columns.py, and add to grid/prior/VENDORED:

    21680d6b00c8ace03b39de6d464fa8891406dee87928afd934bca1a4bdc15b96  schwingcheck/columns.py

Why it resolves: its imports are math, dataclasses, typing and numpy, then `from . import LEVELS`
and `from . import correlation as CORR`; the vendored __init__.py at 8ae5db9 defines LEVELS (line
22, C3 to L5, the typical column's levels) and the vendored correlation.py is the module it names;
nothing else is imported. A scratch copy of the vendored package with columns.py added imported and
drew (scratch vendtest/). The file's sha256 is the same at 8ae5db9 and at origin/main 1ef008f, so
no later change is left behind. Nothing is edited in place; the generator is not reimplemented.

How the test holds it: tests/test_gold3_prior.py's Vendored test already hashes every line of
VENDORED after the first against the file it names, so the new line is held as soon as it is
added. One more test, with no numpy: parse columns.py with ast and assert that its imports are
exactly the standard library modules above, numpy and the two relative names, and that each
relative name exists in the vendored package (LEVELS in __init__.py's assignments,
correlation.py on disk), so a later re-vendoring that brings an unvendored import fails in CI.

If a later re-vendoring cannot resolve, S15 prints its fault line with the ImportError's kind; the
predictive check is then not run and is never written by hand.


## 8. The sbatch

grid/morphometry-prior.sbatch:
- the archive list (lines 63 and 64) adds data/gold3-ct/enhance-pet/facts.jsonl;
- DRAWS=${PRIOR_DRAWS:-200}; kept only when it matches ^[1-9][0-9]{0,3}$ and is at most 2000, else
  200; passed as --draws "$DRAWS" (the gate never sets it; a test does);
- after rc 0 or 3 with report.lines: report.lines, then check.lines when present (else one line,
  "the check wrote no lines"), then "the fit and its check: done in $seconds s" with today's tail;
- new, before today's FAILED lines: when rc is neither but fit.rc holds 0 or 3 and report.lines
  exists, the fit finished and the check ended the interpreter (a crash no try can catch):

```bash
fit_rc=$(head -c 2 "$OUT/fit.rc" 2>/dev/null | tr -cd '0-9')
if { [ "$fit_rc" = 0 ] || [ "$fit_rc" = 3 ]; } && [ -f "$OUT/report.lines" ]; then
  sed 's/^/- /' "$OUT/report.lines" >> "$REPORT.part"
  kind=$(error_kind "$OUT/fit.out")
  report "the check after the fit ended the interpreter with exit $rc${kind:+, an error of the kind $kind}; the fit's lines stand and the job's exit is the fit's"
  [ "$fit_rc" = 0 ] && finish 0
  finish 1
fi
```

- the TERM trap's line says "during the fit or its check";
- the header comment names the check, check.lines, fit.rc and PRIOR_DRAWS.

The check reads no file the archive does not hold: the rows under $MORPHOMETRY_ROOT, and the
records under $OUT/code/data.


## 9. The gate

grid/gate.sh, word_morphometry_prior (about lines 2612 to 2650):
- the path loop adds grid/prior/prior_check.py, grid/prior/prior_rows.py,
  grid/prior/schwingcheck/columns.py, data/gold3-ct/enhance-pet/facts.jsonl,
  docs/research/gold3-prior-check/READING.md and docs/research/gold3-prior-check/READING.md.sha256,
  each refused as today ("refusing: commit ... holds no <path>, which the job copies; nothing was
  queued"; the two reading files are not copied, so their refusal says "which the check is read
  by");
- after the loop, the freeze:

```bash
want=$(git -C "$REPO" show "$head:docs/research/gold3-prior-check/READING.md.sha256" 2>/dev/null | head -n 1 | cut -d' ' -f1)
have=$(git -C "$REPO" show "$head:docs/research/gold3-prior-check/READING.md" 2>/dev/null | sha256sum | cut -d' ' -f1)
[[ $want =~ ^[0-9a-f]{64}$ ]] && [ "$want" = "$have" ] || {
  echo "refusing: the reading guide at commit ${head:0:7} does not match the sha256 beside it, so it moved after it was frozen; nothing was queued"
  return 2
}
```

- the busy list stays enhance, verse and prior (the covariates are deferred, section 14);
- the header comment (about lines 206 to 209) adds that the job also prints the check of
  grid/prior/prior_check.py, descriptive lines read by docs/research/gold3-prior-check/READING.md,
  and that the gate sends only while that guide matches its sha256;
- the submitted message says "fits the priors and runs their check".

The freeze is held by the gate at the commit it sends from; git history is the only record that
READING.md and its sha256 were not rewritten together (section 15).


## 10. Tests

tests/test_gold3_prior.py. numpy tests keep @unittest.skipUnless(HAVE_NUMPY); the others run on
CI's Python, which has none.

make_inputs(base, n=400) keeps its signature, its ids and today's counts, and adds, for every study:
the stamp row's note 1cee7ea83e4c28db (in place of "stamp"); a slice_mm row by study number i (i %
5 of 0 or 1 at 2.5, 2 at 3.0, 3 at 1.0, 4 at 5.0, so 40, 20, 20 and 20 per cent, and the last six
studies, n - 5 to n, at 2.8); a flag:body_foramina row at C3 to C7 for a third of the studies, more
at C7; canal_ap and canal_w rows at every level; records/gold3-ct/enhance-pet/facts.jsonl with id,
site (autoPET for the 2.5 and 1.0 classes, Leipzig for 3.0, Careggi for 5.0 and 2.8) and scanner
{model, kernel}, one kernel written as a list's text; and n // 13 more repeat groups (30 at n 400,
11 at the gate test's n 150), of two then three persons in turn, taken in order from the 2.5 mm
studies numbered 20 and up, each a near copy of its first member (the same spine plus 0.3 SD of
noise per cell). The groups stay inside the 2.5 mm class at any n from 150 up and keep clear of
the special studies 2, 3, 6, 7 and 9; today's group, unit 0010 with 0011, is kept as it is (both
at 2.5 mm, i % 5 of 0 and 1), so test_a_repeat_group_is_one_unit and the leak list still hold. The
gate test copies only records/gold3-ct and keeps the repository's real data/splits, so there the
groups are the real file's and the near copies only shape the rows. The totalsegmentator rows get
slice_mm 1.5 and the stamp.

Existing tests, changed:
- test_fits_each_population_and_beats_the_assumed_structure: the substring becomes "studies 400,
  not admitted 1, test reserve 2, L6 or T13 or no L5 1 (L6 1, T13 0, no L5 0),"; run is called
  with draws=8.
- Vendored: unchanged; it now covers columns.py.

New, without numpy:
- ColumnsResolves: section 7's ast test.
- ReserveSafety (prior_rows only): a small rows file with kept, reserve, not admitted and L6 studies
  and their study, flag and canal rows, and a facts file; Split puts the reserve study only in
  counts; study_rows yields no row of a study outside kept_raw, and its result does not change when
  the reserve study's rows are rewritten (values, slice_mm, stamp, flags, canal) or when rows are
  added for it (a second code row at another 16-hex stamp, a flag:body_foramina row, canal rows,
  an L6 row: the reserve comes first, so the L6 count stays as it was), the scope critique [2.2]'s
  case of a row added for a reserve person; study_facts never returns the reserve id, and a facts
  line added or rewritten for it changes nothing; counts_line, stamp_line, class_line and
  units_line are identical before and after. This is decision 6's test.
- LineShape: check_line accepts every catalogued format (a copy of the examples) and refuses a line
  of 195 characters, a slash, "a:b", five digits, a date 20261031, an eight-hex run, a second stamp,
  each banned word, FAILED and a non-ASCII character; error_kind maps a 40-hex class name to
  Exception.
- ReadingFrozen: docs/research/gold3-prior-check/READING.md hashes to the first field of
  READING.md.sha256, and the file is ASCII with LF.
- CountsByReason: Split on raw ids with an L6 study, a T13 study and a study with no L5 row counts
  (l6 1, t13 1, no_l5 1), anomalous 3.

New, with numpy (each with its own seed; tolerances are about five sampling SDs):
- CheckShape: GP.run on make_inputs with draws 8; every check.lines line starts with a population's
  head and passes check_line; piping the lines, each with "- ", through `awk -v data=/rs/x -v
  runs=/rs/r -v models=/rs/m -v repo=/home/x -f grid/shape-words.awk -f grid/report-shapes.awk | sed
  -r -f grid/redact.sed` leaves them unchanged; enhance_pet prints at most 160 lines,
  totalsegmentator at most 90, verse exactly "verse C3..L5 check: not run, no rows for this
  population"; report.lines plus check.lines plus the sbatch's 5 lines stay under 380 lines and
  60,000 bytes; no id, person key or temporary path appears (today's leak list).
- FaultNeverFailsTheFit: S9's function patched to raise ZeroDivisionError: "enhance_pet C3..L5
  check: fault at S9, an error of the kind ZeroDivisionError" appears, S14 and S15 still print, run
  returns 3 (verse's rows are missing, as today) and report.lines is byte for byte the run without
  the fault; with sys.modules["prior_check"] set to None, every population prints "fault at S0, an
  error of the kind ImportError" and the return is unchanged; with S0 patched to raise, no later
  section prints and the done line does.
- LateSections: a clock that jumps past the budget after S2: "S4 and every section after it not
  run, the check ran past 90 minutes", then done.
- ReserveChangesNoLine: rewrite every row of the reserve study 0002 (values, slice_mm, stamp, flag,
  canal rows) and its facts line, and add rows for it (a code row at another stamp, flag and canal
  rows at C5); check.lines and report.lines are byte for byte the same.
- Determinism: two runs give the same check.lines.
- TwoStamps: ten kept studies at another 16-hex stamp give the "rows at 2 code stamps" line; a stamp
  "not-a-stamp" is never printed; with the note "not-a-stamp" on most kept studies the line reads
  "the commonest not 16 hex" and S0 does not fault (an apostrophe or the note itself there would).
- Signatures, the matched-truth families of the statistics critique (kron_sim.match_core's kinds),
  built in the test from its own separable base (R_level an AR(1) at 0.8 with a floor, R_measure
  with el 0.30, dld 0.46, h near 0), drawn at n 2000, the sample statistics compared with the
  test's own population limit (a population flip-flop on the exact covariance, about fifteen lines
  in the test) within 0.03, and the limits asserted to carry the sign and size the guide relies on:
  - separable: P1 within 0.02 of its shrink offset (about 0.004), P2 within 0.02 of 0, P3 within
    0.02 of 0, the lag-core range within 0.03 of 0;
  - size_wd at share 0.20 (one factor on the four plate measures): P1 at least 0.12 and the six
    pairs of one sign; lag-core range at least 0.12; P2 and P3 within 0.02 of 0;
  - size at 0.20 (one factor on all five): P1 at least 0.12; lag-core range within 0.03 of 0;
  - disc at 0.15: P2 at least 0.10 in widths and depths; P1 under 0.06;
  - vertebra_wd at 0.20: P1 at most -0.04 and the six-pair misfit below 0; P3 above 0;
  - cervical widths at 0.20 (e with l at C3-C7): P3 at most -0.06; the C3..C7 refit's change at
    least +0.15; P2 within 0.02 of 0.
- ProtocolOffset: three classes (50, 25, 25 per cent, the first labelled autoPET 2.5 mm), the
  separable base, the second class's plate cells shifted by 1 SD: pooled P1 above 0.10; within-class
  P1 and autopet P1 within 0.03 of the separable limit; S11's meanz lines show the class's offset
  near +1 in pooled z units of the class mean minus the rest's.
- CanalBoundary: in the 5 mm class a per-scan shift b of SD 0.6 added to every plate cell and taken
  from every canal cell: that class's canal r below -0.3; the other classes' within 0.15 of 0.
- NeckBetweenBranches: half the cervical vertebrae in the fallback branch, whose e and l are both
  shifted +0.8 SD, with the same within-branch r in both branches: the diff line within 0.1 of 0;
  the between part of the covariance above 0.1 at every level; the centred refit lowers the width
  pair by at least 0.03.
- Masking: 3 per cent of cells shifted 4 SD: the 4 SD share at least 0.5 per cent; the winsorised
  width pair above the Pearson refit's; the normal-scores gap at el above 0.
- ICC: a hand-computed example of three units of sizes 2, 2 and 3 matches to 1e-12; a planted ICC of
  0.8 over 40 units of three lands in [0.65, 0.92] with its interval covering 0.8.
- SharedError: units whose e and l errors correlate 0.6 give the errcorr el above 0.4; independent
  errors give it within 0.15 of 0.
- CorrectedR: C 0.5, E(i,j) 0.1, E(i,i) and E(j,j) 0.2 give 0.5; C 0.9, E(i,j) -0.2, E 0.3 prints
  "over 1".
- Generator: the test builds its own CORR.Prior (levels and measures of C3..L5, r_level an AR(1)
  at 0.8, r_measure the test's R_MEASURE with el set to 0.30; make_inputs' fitted prior has el
  near 0.48, so it is not used here) and calls S15's function on a context holding that prior and
  the margins below. With scale_sd 0 and noise_mm 0, the drawn same-level el is within 0.02 of the
  prior's 0.30; at the defaults with every cell's margin 30 mm and 3 mm and noise 1 mm, the
  variance line prints size share 0.31, noise share 0.07 and SD ratio 1.27 (analytic 0.3057,
  0.0688, 1.2707) and the drawn el is within 0.03 of (4.442 + 9.0886 x 0.30) / 14.531 = 0.493.
- RatioSD: e and l log-normal with CV 0.10 and r 0.3: the S14 SD within 10 per cent of sqrt(0.02 -
  0.006) = 0.118.
- Mismatch: one vertebra of 10 per cent of spines with e scaled by 1.3: the spine share at least 10
  per cent and the vertebra share near 10 per cent of one in 22.

tests/test_gate.py:
- prior_commit copies docs/research/gold3-prior-check (READING.md and its sha256) into self.repo
  and adds it to the commit; make_inputs' records already bring gold3-ct/enhance-pet/facts.jsonl.
- The job's env gains PRIOR_DRAWS=5. New assertions: "- enhance_pet C3..L5 check: rows at one code
  stamp 1cee7ea83e4c28db" and "- verse C3..L5 check: not run, no rows for this population" in the
  report; "the fit and its check: done in"; "5 draws for each null"; the gate's printed report
  carries the check lines as written (no "withheld").
- New: test_morphometry_prior_refuses_a_reading_guide_that_moved (READING.md edited after the
  sha256 at the commit: return 2, "does not match the sha256 beside it", nothing submitted);
  test_morphometry_prior_refuses_a_commit_without_the_facts (return 2 naming
  data/gold3-ct/enhance-pet/facts.jsonl); test_prior_job_keeps_the_fit_when_the_check_ends_the
  _interpreter (PRIOR_PYTHON a wrapper that runs the real interpreter and exits 139 after a script
  run: the report holds the fit's lines and "the check after the fit ended the interpreter with exit
  139", SN_PRIOR_RC=1 from the fit's 3).


## 11. The research note, the index line and the memory change

docs/research/gold3-prior-check/README.md, outline:
1. Source: the thread "Train on randomized spine phantoms", 2026-10-31; the design workflow that
   asked whether the fitted R_measure understates how one vertebra's own measures move together,
   and its three critiques (statistics, measurement, scope); greg's direction of 2026-10-30 and his
   later words on the latent encoding (scope critique [2.0]).
2. Where it stands: built, not sent; READING.md frozen at the commit that adds it, its sha256
   beside it; the send is `morphometry prior`, one CPU job, whenever GitHub Actions runs again.
3. What R_measure is: the measure part of a separable fit on values whitened by R_level, not the
   correlation of two measures at one level; the published values (bordercall
   records/prior-2026-10-31/report.md).
4. The design's verdict and its refutation: the separable fit's bias explains at most a third to a
   half of the gap to the literature, and only at the largest shared factor the published fits
   allow; the measures (their definitions, noise, the neck cut, the thick-slice slabs) are joint
   leading suspects with a whole-spine shared factor; never "mostly the Kronecker".
5. What the trimmed check prints: the sections of SPEC section 4 in a paragraph each, and what was
   cut (P, the blend, EM, S7, S10) and why (scope critique [2.0]).
6. The primary contrasts and the freeze: READING.md's five, and how it is held (the gate's sha256
   check, git history).
7. Holds and consumers: the measure part stays held (bordercall README line 192); the check does not
   hold #56 (scope critique [2.1]), whose primary answer is the same under the fitted prior and under
   plates coupled at 0.8; nothing in production draws from the prior. The same lesson reaches the
   latent encoding greg chose at 00:37 UTC on 2026-10-31 (scope critique, missing item on telling
   the latent-code work): any prior over levels by codes fitted in a separable form gives a code
   part whitened by its level part, not the codes' coupling at one level, and his word of 21:44 UTC
   on 2026-10-30 keeps exactly the correlations between levels (bordercall
   research_notes/open-vertebra-meshes/README.md). Whether that work is told now is greg's call
   (section 15).
8. Deferred: section 14 of this spec, with when each would be added.
9. Corrections carried: R_measure's meaning (the memory); the reserve wording (gold3_prior.py's
   docstring); the correlation.py docstring's claim that a draw keeps every cell's mean and SD, which
   the size factor breaks, to be corrected in bordercall, not here (scope critique [2.3]); and the
   three readings of the design's readers that the measurement critique [1.12] corrects, stated
   rightly: the end-plate slab holds two voxel layers, the layer at the plate and the next one into
   the body, about 10 mm of bone on 5 mm slices, 6 on 3 mm and 5 on 2.5 mm, not one slice of 5 mm
   (bordercall scanimport geometry.py 350 to 354 and 416 to 422); the canal-wall line's intercept,
   one number per vertebra subtracted from both depths, moves both depths one way and raises their
   correlation, while only its slope, set to 0 with too few rings, moves them apart (morphometry
   anatomy.py 281 to 288 and 304 to 305); and both neck branches cut the whole body at one pair of
   lines, the foramina's medial edges or the canal's side walls and 1 mm beyond, so neither branch
   alone couples the widths by construction, and "the canal-wall line" names the depths' anterior
   wall, not the neck's cut (anatomy.py 347 to 355).
10. The records to keep after the run: the report's check lines as the gate prints them, under a
   dated name in this folder (grid/logs is not committed).
11. truths/: the records the guide quotes, each with its source and how it was made:
   limit_check.jsonl and null_sd.jsonl (this thread: the check's statistics in the population limit
   for the matched truths, and the null spreads at n 693 and 67), the statistics critique's
   limit_stats.jsonl, rule_on_matched.jsonl, masking_max.jsonl, mixed_bound.json,
   regional_size_bound.json and width_factor_bound.txt, and the design's results-phantom.json, with
   a README.md naming each file's source; the scripts stay out (they import the critic's
   kron_sim.py, which is not here; section 15). In this session's scratchpad the critique's files
   are under priorcheck/review/, results-phantom.json under priorcheck/, and this thread's two under
   priorcheck2/truths/; each is checked ASCII before it is copied.

docs/research/README.md, one line in the Programmes list beside phantoms-and-the-gold-tier:

    - [The prior's measure check](gold3-prior-check/README.md): the thread "Train on randomized spine phantoms", 2026-10-31: why R_measure cannot be read as the same-level coupling of one vertebra's plates, the statistics critique that bounds the separable fit's share of the gap to the literature at a third to a half, the descriptive check the job `morphometry prior` prints after the fit, and READING.md, frozen with its sha256 before the first send; greg makes every choice.

docs/memory/the-correlation-prior.md, a bullet after the third:

    - R_measure is the measure part of a separable fit on values whitened by R_level, not the correlation of two measures at one level, so its low entries (endplate with endplate_lower 0.301 over C3 to L5 in enhance_pet, 0.164 over T1 to L5) do not say the plates of one vertebra are weakly coupled. The statistics critique of 2026-10-31 bounds the separable form's share of the gap to the literature at a third to a half; the measures and a whole-spine shared factor are the joint leading suspects. The measure part stays held (bordercall README, the limit "Independent measures") until the check of docs/research/gold3-prior-check/ reports and greg reads it with its frozen READING.md.

docs/memory/MEMORY.md line 51, replacing its last clause so the line barely grows (the index is
42,107 bytes, already over the 25 KB its rule states):

    - [The correlation prior](the-correlation-prior.md): the gold tier 3's correlation of body and end-plate measures across levels and measures, fitted per population by the grid word `morphometry prior` (grid/prior/, bordercall schwingcheck/correlation.py) and drawn by draw_columns(correlation=prior) in place of the assumed rho 0.5 (greg, 2026-10-30); R_measure is level-whitened and separable, not the same-level correlation, and its measure part waits on the check of docs/research/gold3-prior-check/.

`python3 flows/stage_registry.py check` reads flows/registry.txt and PREREG paths only, and
`frozen` watches PREREG.md and PREREG.md.sha256; a READING.md that belongs to no flow touches
neither, so both still pass.


## 12. Line budget

Lines each section prints, estimated from the class mix (four classes of 30 or more in
enhance_pet, one in totalsegmentator) and the formats above:

| Section | enhance_pet | totalsegmentator | verse |
|---|---|---|---|
| S0 inputs and consistency | 3 | 3 | |
| S11 protocol classes | 18 (4 class, 8 mean z, 4 same by class, hpost, too few) | 3 (no facts, one class, hpost) | |
| S12 anchors | 10 | 10 | |
| S1 same level | 18 (10 pairs, six, 2 by level, SE, 2 within, 2 autoPET) | 16 (14 pooled, 2 reruns off) | |
| S2 lags and discs | 11 (5 lag, core, 2 disc, groups, 2 by class) | 9 | |
| S4 far apart | 7 | 3 | |
| S5 refits | 8 | 7 | |
| S6 tails | 5 | 5 | |
| S13 canal | 2 | 1 | |
| S9 neck | 32 (legend, 20 level, 4 cov, 4 diff, canal, centred, by class) | 10 (legend, 5 level, cov, diff, canal, centred) | |
| S14 plate ratios | 6 | 5 | |
| S15 generator | 8 | 8 | |
| S8 repeat units | 12 | 1 (not run, no units) | |
| done | 1 | 1 | |
| total | 141 (cap 160) | 82 (cap 90) | 1 |

A fifth class of 30 spines would bring enhance_pet to about 152 (four S11 lines and seven S9
lines more). Bytes, from the catalogue's lengths at these counts with each population's own head
(scratch audit/budget.py): enhance_pet about 22 KB (about 24 KB if every line were at the
catalogue's widest), totalsegmentator about 13 KB (about 14 KB), verse about 60 bytes. The whole
report: today's 125 lines and 16,088 bytes (bordercall records/prior-2026-10-31/report.md), the
counts lines growing by about 30 bytes each, plus 224 check lines, about 349 lines and 52 KB (about
54 KB at the widest), under 380 lines and 60,000 bytes, and under the gate's head -n 400 and its
64,000 byte cut. A line added to the check later is costed against this table first.


## 13. Runtime

The fit takes 11 s. The check's cost is the nulls and bootstraps: per draw one flip-flop over 22
levels and, for the pooled null, five subset flip-flops, on at most 693 spines; with 200 draws for
each of the three strata, plus the level, ratio, neck, ICC and corrected-r bootstraps (no refit)
and 5000 generator columns, an estimate of 6 to 10 minutes for enhance_pet and about 1 minute for
totalsegmentator on one of the job's two CPUs. Not measured; the done lines will say.


## 14. Deferred

- Covariates (sex, stature): they need the covariates join's per-person table, which stays on the
  grid, and the covariates word's guard against differencing within-sex aggregates across reports;
  with them the gate's busy list would add morphometry_covariates and the archive would add the
  join. Added when a reading of P1 says a shared factor survives within protocol and within
  autoPET 2.5 mm alone, or when greg asks; autoPET alone has sex (861 of 867 persons) and
  TotalSegmentator has it, Leipzig and Careggi do not (scope critique [2.7]).
- The models the scope critique cut: the person-effect Kronecker P, the blend, EM, the fivefold
  choice (S7) and the flags (S10); any of them is greg's choice after a reading, as a design of its
  own.
- The design's S3 contrast ("size minus differences"), which noise drives as hard as a shared factor
  (statistics critique [0.1]).
- A count from C2 for transitional spines whose masks name no extra level (measurement critique
  [1.10]); the gold tier 3 completion's count is not in the rows.
- A stage_registry hold on READING.md like a PREREG's.
- Any change to the generator, to #56 or to the prior's hold: proposals only, greg's.


## 15. Open questions

- Should `flows/stage_registry.py frozen` also watch docs/research/gold3-prior-check/READING.md and
  its sha256? Today only the gate holds the freeze, and an edit of both files together in one pull
  request would pass it.
- Should the critic's and this thread's scripts be committed with their records under truths/? They
  import kron_sim.py and check_proto.py from the design's scratch, which are not in either
  repository.
- Is there a count from C2 for ENHANCE.PET that could drop or count transitional spines?
- The class mix of the whole fit spines is known only on the grid; the budget assumes four classes
  of 30 or more.
- Is a 12 MB facts.jsonl in each job's archive acceptable, or should a small derived table (id,
  site, model, kernel) replace it?
- How often does the engine set wall_slope to 0 (morphometry/anatomy.py line 303), and how often does
  the neck's fallback fire on thick slices and in TotalSegmentator? The check prints the counts; the
  rows alone cannot say why.
- Where the check's lines are kept after the run: the README proposes a dated copy in this folder,
  as the prior's own record went to bordercall records/prior-2026-10-31/.
- Which issue and claim carry this work (and whether bordercall's prior issue should link it).
- Whether later sends keep the same seeds (as specified) or name a new purpose per send.
- Who corrects correlation.py's docstring in bordercall.
- docs/memory/MEMORY.md is 42,107 bytes against the 25 KB its rule states; section 11 keeps the
  changed line about as long as it is, but trimming the index is greg's call, not this change's.
- The regional truths were tried with a shared factor of 0.20 to 0.45 and matched both fits from
  0.20 to 0.40 on the four plate measures and 0.20 to 0.35 on all five (the critique's
  regional_size_bound.json; the solver did not converge above); whether a regional structure with
  a smaller shared factor also reproduces both fits, and what its P1 would be, was not computed.
- Whether the latent-code work is told now that a separable prior over levels by codes has the
  same whitened code part (section 11, item 7); this change only records it.
- Two bands are judgments, not calibrations: P4's 0.038 (twice the films' highest L1-L4 ratio CV)
  and P5's +0.05 at every lag. Neither was run through matched truths by this code; greg may want
  them calibrated before the first send, which would change READING.md before its freeze.
