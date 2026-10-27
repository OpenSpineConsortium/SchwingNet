---
name: priority-panjabi-first
description: The owner's order of 2026-10-27 05:48 UTC, in force until the owner says otherwise - Panjabi's tables in bordercall (TODO.md item P) alone, then gold tier 1-3 data (item 5), nothing else, nothing to the grid
metadata:
  type: project
---

The owner, 2026-10-27 05:48 UTC, in the CNS thread: the new account is to "work on nothing else except fleshing out Panjabi until I say otherwise, then it should be on getting gold 1/2/3 tier data for segmentation based empirical testing of this bayesian generator"; the Panjabi work is to "extract the rest of the data/tables from all of these three panjabi papers, expanding beyond what is easily measurable on spineps segmentations to see how more measurements improves accuracy".

- Item P (bordercall TODO.md, main 7015802): inventory every table and figure value of the cervical (Spine 1991;16(8):861-869), thoracic (Spine 1991;16(8):888-901) and lumbar (Spine 1992;17(3):299-306) papers in archive/bordercall/reference/papers/, saying for each what can read it (SPINEPS mask, AP, lateral, CT only); transcribe from page images in two passes (never parse the scans' text: the thoracic canal table came out plausible and wrong; an SEM copied from the row above, VBHp L1, was caught); put values into build_panjabi.py's region tables and CANON map; SD = sem x sqrt(12); areas scale with s^2, angles not at all, left/right pairs averaged or correlated, never two independent measures; score without enumerating subsets: the seven-measure baseline, each family added, all-AP, all-lateral, all, and a greedy forward order chosen on selection columns of its own seed; report exact and at-0.99 shares with precision at 1, 3 and 9 bodies, plus the twelve-spine table worlds (exact.py's robust part), anomalous phenotypes apart; deliver builder, CSV, papers/README.md map, a record with command, seeds and digests, Benzel-style figures, README tables, tests (archive's 222 still pass).
- Out now (build_panjabi.py's own list): surface areas, angles, pars interarticularis, spinous and transverse processes, rib articulations, uncovertebral joints. Pedicle widths and heights are transcribed but unused (SPINEPS has no pedicle label).
- Gate: one thread only; work in archive/bordercall; findings stay in bordercall, nothing to symphony-template; no grid job, fetch or training; do not start TODO item 1 (schwingcheck/ package), chapter 36 (SchwingNet #416) or a new SchwingNet copy of bordercall. When item P has merged: report the results to the owner and stop.
- Item 5 only on the owner's word: it takes over the tiers thread's drafts (SchwingNet #420, symphony-template #500); the bordercall pilot (2 CPU, approved, unsent) belongs to it. See [[grid-words-and-counts]], [[findings-corpus-and-data]].

**Why:** the owner wants to see how far more measurements push accuracy before any other work.
**How to apply:** refuse other work until the owner says otherwise; every result of item P is synthetic until item 5. Baseline numbers are in [[findings-naming]].
