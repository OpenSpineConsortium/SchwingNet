---
name: verse-genant-benchmark
description: bordercall's vertebral body ratios on VerSe's 374 masks scored against Riedel's Genant grades on 2026-10-29 (AUC 0.836, thoracic 0.93, lumbar 0.80); results and handoff in the project folder, never git
metadata:
  type: project
---

Thread "Benchmark VerSe heights against fracture grades", 2026-10-29. This was the benchmarked-dataset test in greg's 12:20 UTC ask.

- Where: /mnt/project-files/gold3-ct/morphometry/verse-2026-10-29/
  - README.md: the numbers, the rules and the sha256s.
  - HANDOFF.md: what is left.
  - Data: rows.csv, joined.csv, aggregates.json.
  - inputs/ and tools/: everything needed to run it again.
- What: bordercall 44e7402 (PR 30), code stamp 7bda317295ef9f5b. The smaller of body_index_ant_post and body_index_mid_post, set against Riedel's grades (osf zy68u).
  - 3,674 vertebrae of 320 patients; 3,622 read.
  - Codes 5 and 8 (24 cells) are left out.
  - 22 duplicate cells were dropped; none conflicted.
- Numbers (VerSe only, never pooled with ENHANCE.PET):
  - AUC for grade 1 or more: 0.836 (CI 0.780 to 0.887). For grade 2 or more: 0.843.
  - At 0.80: sensitivity 0.63, specificity 0.966.
  - Thoracic AUC 0.932, lumbar 0.802.
  - Kappa 0.614.
  - 52 vertebrae unread, 11 of them among the 68 grade 3.
- Open questions:
  - ant/post barely falls with grade, while mid/post carries the signal; render to see why.
  - 34 vertebrae have heights unread with no note.
  - The lumbar cut.
- Masks for a rerun: [[verse-masks-on-grid]]. Bordercall side: [[morphometry-state]].

**Why:** this is the one external benchmark of the heights so far.
**How to apply:**
- Quote these numbers only as VerSe's.
- Run again from the grid's masks, never by downloading VerSe again.
- Any new cut is chosen on a split, never on the whole set.
