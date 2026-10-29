---
name: clinical-reread
description: greg's reread of every paper for clinical detail (2026-10-28 19:03 UTC) landed on bordercall main 2026-10-29 (PR 26, 6409164) with the 106-key measure set; stopped at his checkpoint of 17:22 UTC with the handoff on main (PR 36, 88e9cbd); next the round-2 data faults, validation, prior art
metadata:
  type: project
  modified: 2026-10-29T17:28:01.755Z
---

greg, 2026-10-28 19:03 UTC: Eisenstein's discussion is "priceless details" (LSTV prevalences, how to measure on a lateral film, level-specific pearls and pitfalls); reread all the PDFs for them, to direct "the autonomous anatomist" (19:05 UTC).

On bordercall main since PR 26 (6409164, 2026-10-29 17:1x UTC; PRs 24 and 21 closed as superseded), under research_notes/:
- clinical-reread/notes/ (43 notes, each checked against the whole PDF, with JSON records), papers/ (44 PDFs, in git by greg's choice of 03:30 UTC), synthesis/ (four parts, SYNTHESIS.md, anomaly-priors.md sent to the chain), HANDOFF.md.
- panjabi-endplate-inclination.md: the lumbar end-plate rows repeat the cervical C3 to C7 row; greg chose 09:01 UTC to keep all 32 as printed.
- paper-tables/: tools/vocabulary.csv, the 106 keys greg calls "all 102 unique measures"; synthesis/measures.md the recipes; data/readings/ 23,918 cells; data/series.csv 4,357 series; results/README.md the comparison with Panjabi; review/round-2-findings.json.

Checkpoint 17:22 UTC ("PUSH ALL WORK AND CHECKPOINT AND WRITE HANDOFFS NOW"): the thread stopped. The handoff, HANDOFF.md on main 88e9cbd (PR 36), carries the whole plan: 1. fix the fourteen round-2 data faults (series.csv changes; the auto-anatomist, chain, gold tier 3 morphometrics and validate threads wait for word of it; vocabulary.csv and measures.md do not change); 2. validation (blind re-read of the 468-cell sample tools/validation_sample.py draws, with a Wilson interval; plausibility flags; mapping audit); 3. how prior art measured them with public test sets and code. Nothing of 1 to 3 was run.

Waiting for greg: archive/bordercall calls Panjabi's specimens embalmed where his papers say fresh (SPINEPS_MAPPING.md line 88, covariance.py line 28).

**Why:** a later thread must not redo the reading; every other thread reads the measure set from main.
**How to apply:** read HANDOFF.md first; no page image or run of page text in git; quotes 12 words at most; tools/copycheck.py checks a file against the papers. Related: [[papers-in-hand]], [[owner-direction-2026-10-28]], [[item-p-state]], [[hold-lifted-2026-10-29]].
