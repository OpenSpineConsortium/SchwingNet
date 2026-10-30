# Naming rule evaluation, with all 42 papers' tables

Oct 28, 2026 · @Someone

## The engines as they stand

Six engines name a field today, all on bordercall pull request 20's head (commit ede955b, the chain of levels, still a draft); the first four are unchanged from main (08b1a23), and the exact rule is what names, the rest are checked against it.

| Engine | File | What it computes | Held to |
| --- | --- | --- | --- |
| Exact rule, trapezoid nodes | schwingcheck/rule.py | The posterior over places, the patient's size integrated on 281 trapezoid nodes of log size; each measure its own error and its own power of size (length 1, area 2, angle 0) | The archive's exact.py within 1e-10, and a dense normal computed independently |
| Exact rule, Gauss-Hermite nodes | schwingcheck/rule.py | The same, on the archive's 161 Gauss-Hermite nodes | The archive's record of 2026-10-26, rate for rate |
| Compiled rule | schwingcheck/compiled.py | rule.py as one compiled PyTensor graph; takes several gap patterns, a size prior per field and a scaled mean per field | rule.py within 1e-10 at 1, 3 and 9 bodies |
| Naming model with NUTS | schwingcheck/model.py | The rule as one PyMC model whose only free variable is each field's log size, sampled by NUTS | Exact places within five Monte Carlo errors, R-hat under 1.02 (tests) |
| Chain of levels, NumPy | schwingcheck/chain.py | A sequence of bodies with a missed body allowed between two read (one at most), and typical, six-lumbar and T13 columns, summed out exactly over their paths | Itself on enumerated paths; the PyMC chain within 1e-10 |
| Chain of levels, PyMC | schwingcheck/chain\_pymc.py | The same as two PyMC models: (a) size and offsets sampled, the path summed by pymc-extras' forward algorithm; (b) offsets integrated in closed form, the path summed by a marginalisation of the package's own | chain.py within 1e-10 given the size |

The table every engine reads is Panjabi's four papers (cervical 1991, thoracic 1991, lumbar 1992, facets 1993): 32 measures over C3 to L5, 18 lengths, 6 areas and 8 angles, each a mean and a population SD from 12 cadaver spines (the SE printed times the root of 12). The generator that draws the test fields is the same table run forwards, so every rate below is the rule on its own world, except where a section says otherwise.

## Time to name a field

Re-timed on bordercall PR 20's head (ede955b), every exact engine names a field in 16 ms or less from one call on one thread, at any of 1 to 32 measures and 1, 3 or 9 bodies, half a video frame at 30 frames a second; the largest single call of all 9,000 timed took 36 ms.

&#91;embedded content: Re-timed on bordercall PR 20's head (ede955b) with python -m schwingcheck curve speed on a copy of records/curve-2026-10-28/curve.nc; group speed, median of 30 calls alone and of 5 batches of 128 (speed-2026-10-28.csv). Dotted line: one video frame at 30 frames a second.\]

Milliseconds a field, alone (median of 30 calls) / in a batch of 128 (median of 5 calls, per field), each engine's table built beforehand:

| Engine | Bodies | 1 measure | 7 measures | 16 measures | 32 measures |
| --- | --: | --: | --: | --: | --: |
| rule.py, trapezoid | 1 | 0.18 / 0.26 | 0.97 / 1.73 | 2.82 / 3.60 | 6.83 / 16.24 |
| rule.py, trapezoid | 3 | 0.32 / 0.27 | 1.50 / 1.61 | 4.46 / 3.60 | 8.75 / 13.33 |
| rule.py, trapezoid | 9 | 0.37 / 0.18 | 2.82 / 1.43 | 6.38 / 3.11 | 15.80 / 6.74 |
| rule.py, Gauss-Hermite | 1 | 0.12 / 0.11 | 0.56 / 0.92 | 1.87 / 1.90 | 3.29 / 4.64 |
| rule.py, Gauss-Hermite | 3 | 0.18 / 0.12 | 0.68 / 0.97 | 2.14 / 2.10 | 5.55 / 4.08 |
| rule.py, Gauss-Hermite | 9 | 0.21 / 0.10 | 1.81 / 0.67 | 4.38 / 1.78 | 7.87 / 3.99 |
| Compiled rule, trapezoid | 1 | 0.29 / 0.21 | 1.14 / 1.87 | 2.91 / 4.56 | 6.09 / 10.23 |
| Compiled rule, trapezoid | 3 | 0.54 / 0.21 | 2.42 / 1.91 | 4.89 / 4.21 | 9.94 / 11.67 |
| Compiled rule, trapezoid | 9 | 0.52 / 0.19 | 3.61 / 1.48 | 6.71 / 3.65 | 13.57 / 8.27 |

- Gauss-Hermite's 161 nodes run about twice as fast as the trapezoid's 281 at 32 measures; the build-up study used the trapezoid.
- A batch is faster per field than a call alone at nine bodies for every engine and count, and slower at one body from 7 measures on; why is not measured.
- Against the record of 28 October (commit a7dcf15, same code), the three-body times at 32 measures moved by under 1 ms (rule.py trapezoid 9.68 then, 8.75 now).
- Conditions: Linux, 4 CPUs, Python 3.13.17, numpy 2.5.4, scipy 1.18.1, PyTensor 3.3.4, every BLAS pool at one thread. The machine's load average was 2.6 to 2.9 while the paper tables were being read beside it, against 1.0 on 28 October, so these times may run slightly high; a run on a quiet machine follows.
- The chain of levels' own times, at up to nine bodies, are being taken by the chain-of-levels thread on a quiet machine and will be added here.

## NUTS on the naming model

NUTS names the same three-body fields 128 to 522 times slower than the exact rule, and at 16 measures sampled together it gave one field a posterior wholly unlike the exact one while its R-hat read 1.00. Re-timed on PR 20's head (ede955b), one thread, 2 chains of 500 draws after 500 tuning steps, seed 7; together = 20 fields in one model, alone = one field:

| Measures | Fields | Setup, s | NUTS loop, s a field | Times rule.py | Largest gap from the exact posterior | Largest R-hat | Divergences |
| --: | --- | --: | --: | --: | --: | --: | --: |
| 7 | 20 together | 38.2 | 0.33 | 205 | 1.2e-2 | 1.02 | 0 |
| 7 | 1 alone | 26.1 | 0.78 | 522 | 3.3e-4 | 1.00 | 0 |
| 16 | 20 together | 14.3 | 1.26 | 350 | 1.0 | 1.84 | 156 |
| 16 | 1 alone | 15.1 | 1.14 | 256 | 3.1e-2 | 1.02 | 0 |
| 32 | 20 together | 12.4 | 1.71 | 128 | 1.5e-2 | 1.01 | 0 |
| 32 | 1 alone | 16.1 | 1.31 | 149 | 9.8e-3 | 1.01 | 0 |

- Times rule.py: the NUTS loop's seconds a field over rule.py's (trapezoid, three bodies) median for one field, in a batch of 128 for the fields sampled together and alone for a field alone (table above).
- The 16-measure failure reproduces exactly at PR 20's head, as in the record of 28 October (commit a7dcf15): the field at L2 has R-hat 1.00 and a gap of 1.0, so one of the two posteriors puts nearly all its weight at a place where the other puts almost none; three other fields have R-hats of 1.46 to 1.84. Why that run fails is not measured.
- Setup is compiling the model, once per shape; the 7-measure runs, which came first, paid for PyTensor's cache (120 and 39 files written, against 4 later).
- A sampled answer is therefore checked against the exact rule field by field, never trusted on its R-hat.

## Naming as the measures are added

On Panjabi's own world, all 32 measures name 98.3% of three-body fields exactly and every nine-body field from 25 measures on; the seven in use today name 73.1%, and the first seven of the greedy order 89.2%. The scoring is the build-up study of 28 October (rule.py on the trapezoid, unchanged since), not re-run: its code has not moved.

&#91;embedded content: bordercall records/curve-2026-10-28/figures/curve\_accuracy.csv (from curve.nc, arm nominal, typical columns, 2,000 columns; buildup-2026-10-28.csv holds the points drawn). C is drawn where 1,000 or more fields were named at 0.99; dotted at 99 per cent. Crosses: the seven SPINEPS measures.\]

The arms move the share named more than the promise. Three-body fields of typical columns; exact = share named exactly, precision = share of the answers given at a posterior of 0.99 that were right:

| Arm | Seven: exact % | Seven: precision at 0.99 % | All 32: exact % | All 32: precision at 0.99 % |
| --- | --: | --: | --: | --: |
| As assumed | 73.1 | 99.78 | 98.3 | 99.96 |
| Every error halved | 76.8 | 99.77 | 99.2 | 99.98 |
| Every error doubled | 63.0 | 99.82 | 95.3 | 99.96 |
| Offsets correlated 0.4, rule unaware | 73.8 | 99.90 | 98.3 | 99.96 |
| Table from 12 people | 61.1 | 95.75 | 92.7 | 98.05 |
| Table from 12 people, SDs widened for a new person | 61.5 | 97.65 | 92.7 | 98.66 |
| Table from 50 people | 70.2 | 99.41 | 96.9 | 99.82 |
| Table from 2,000 people | 74.2 | 99.54 | 98.0 | 99.97 |

- A table from 12 people, as many as Panjabi measured, breaks the 0.99 promise (95.75% with the seven); from 50 people on it holds with all 32. The people arms are scored on 200 columns, the others on 2,000.
- Spines the rule has no name for break it too: with all 32 at three bodies, 94.47% of answers at 0.99 are right on six-lumbar spines (153 wrong) and 94.93% on spines with a T13 (137 wrong), nearly all of them fields holding the L6 or the T13. The chain of levels below is the answer being built.
- A rib on L1 or no rib on T12 (a body drawn half-way between) keeps 99.25% or more at three bodies with all 32, but falls to 98.38% and 98.66% at one body.

## The chain of levels

On spines with an L6 or a T13, the chain names three-body fields better than the consecutive rule (97.5% against 86.0% on six-lumbar spines, 94.5% against 84.5% with a T13, all 32 measures) and keeps its answers at 0.99 right (99.37% and 100%, against 90.3% and 92.0%). Fields here are drawn by the chain's own law: each step between two bodies read misses one body with probability 0.2, so the consecutive rule is also wrong about gaps.

| Column | Rule | Exact %, seven | Exact %, all 32 | Precision at 0.99 %, all 32 | Wrong at 0.99, all 32 |
| --- | --- | --: | --: | --: | --: |
| Typical | Consecutive (step d's rule) | 68.0 | 88.5 | 94.41 | 9 |
| Typical | Chain, typical column, gaps summed out | 72.0 | 96.0 | 100.0 | 0 |
| Typical | Whole chain (gaps and the three column types summed out) | 72.0 | 96.0 | 100.0 | 0 |
| Typical | Told the true gaps | 77.0 | 98.0 | 100.0 | 0 |
| Six lumbar | Consecutive | 66.0 | 86.0 | 90.3 | 16 |
| Six lumbar | Gaps only | 67.5 | 95.0 | 96.2 | 6 |
| Six lumbar | Whole chain | 69.0 | 97.5 | 99.37 | 1 |
| Six lumbar | Told the true gaps | 68.5 | 96.5 | 96.59 | 6 |
| T13 | Consecutive | 62.0 | 84.5 | 92.0 | 12 |
| T13 | Gaps only | 66.0 | 90.0 | 94.52 | 8 |
| T13 | Whole chain | 66.5 | 94.5 | 100.0 | 0 |
| T13 | Told the true gaps | 69.0 | 92.0 | 96.41 | 6 |

Three-body fields, 100 columns of each type, two fields a column (200 fields a cell; the exact share's SE is 1 to 3.5 points). The chain's L6 and T13 values are the generator's construction (a blend of the neighbours), so on those columns the chain is scored against the truth it was built from. The prior weights (0.9 typical, 0.05 six-lumbar, 0.05 T13) and the skip probability are stated choices; the clinical reread's priors by population go to the chain thread to replace them. Nine bodies, the chain's speed and the data axis are that thread's remaining steps.
