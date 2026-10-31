# Handoff: Continue Bayesian synthetic validation, 2026-10-31

This is the symphony_3 project thread that ran the gold tier 3 C2 and sacrum completion (the gate
word `totalseg complete`) and the gold tier 3 rescore on bordercall's bounds card. It was written on
greg's order of 2026-10-31 at 14:24 UTC to hand the project off for local continuation. Every change
of this thread is merged; no checkout holds uncommitted or unpushed work. It follows
docs/checkpoints/2026-10-30-totalseg-rerun/README.md, whose steps are all taken.

## What was done

- SchwingNet #505 (merged 2026-10-30 23:11 UTC, 45370ca) fixed the rerun's blocking faults listed in
  docs/research/gold3-ct/completion/RERUN-REVIEW.md (the weights guard, gpu to cuda for MOOSE, the
  MOOSE rerun's stale files, the segmenter in the refusal reasons, the gate's .sent mark) and set the
  sacrum rule: greg trusts no segmenter's S1 class, so every gold tier member's sacrum is one union
  mask of sacrum and S1, and a TotalSegmentator release's S1 is read as part of its sacrum
  (DEVIATIONS.md items 2 and 3).
- The rerun, job 40896342 at 45370ca, ended 0 at 2026-10-31 00:34 UTC. SchwingNet #510 records its
  counts in data/gold3-ct/members.json (completion.totalseg_arm.job_40896342) and
  docs/research/gold3-ct/README.md (sections 2c and 7): the sacrum kept in 26 of 27 VerSe series and 1
  of 5 TotalSegmentator subjects, C2 in 4 of 19 (1379 by MOOSE, verse561, verse588, verse607); PREREG
  H1 met, H2 not met; every refused C2 had 0 voxels. TOTALSEG_RERUNS is spent.
- bordercall #38 merged (greg, 00:21 UTC). bordercall #66 (merged 05:56 UTC, 1ef008f) rescored gold
  tier 3 on the bounds card from the covariates join job 40902924 (SchwingNet 9c160a9, rows of
  measuring code 1cee7ea83e4c28db, the engine pinned at bordercall #44): TotalSegmentator passes
  (steps 0.91 against the bar's 0.89); autoPET is four steps short (0.87); pedicle and canal steps rose
  from 0.64 and 0.70 to 0.81 and 0.86. research_notes/synthetic-validation/README.md answer 17 and
  section "Real CTs on the card" hold the numbers; synthval/gold3.py now names the card's cells the
  report prints no line for (cells_not_printed).

## Open, in rough order

1. The engine at bordercall #44 prints no pedicle sagittal angle on the gold tier 3 masks for 5
   people of a sex at any level, and reads the L5 pedicle for only 86 of autoPET's adults
   (bordercall morphometry/pedicle.py: the sagittal angle is NaN unless both walls and the body's
   posterior wall are read). Find out why on a few masks before trusting either measure.
2. The pedicle, its chord and the canal still leave the papers' range at T10 to T12 (height 5 to 7 mm
   high, chord 7 to 13 mm long, canal 4 mm wide).
3. The disc steps that fail (T10-T11, and L3-L4 to L4-L5) are unexplained; scoring the steps within
   age bands needs the per-person table, which stays on the grid.
4. Look at TotalSegmentator subject s1606's kept sacrum (434 voxels, 7.5 mm from its release's L4),
   which may be a stray fragment, and at verse018's refused sacrum (4 voxels).
5. RERUN-REVIEW.md items 7 and 8 are not fixed.
6. The ML artifact page (https://claude.ai/artifact/13LehVRhuCUB4r4hNC2b3H) still shows the numbers
   from before #66; rebuild with bordercall's report/build_ml.py and republish from an account that
   owns it, or publish a new link and record it there.

## How to reach things

- Grid words go through symphony-template's .github/workflows/grid-accounts.yml (action job, job
  schwingnet-<word>, a new request name); the answer lands on symphony-template's branch grid as
  logs/job-schwingnet-<word>.json, and a long report is read a page a send.
- bordercall's synthetic-validation tests need a virtual environment from
  requirements-schwingcheck.txt; run from research_notes/synthetic-validation with
  `python -I -m unittest discover -s tests`, `python -I tables.py --records records --check README.md
  --check MEASURES.md` and `python -I figures.py`.
- A change to data/gold3-ct/members.json needs `python3 tools/gold3_ct.py stats` and `page` rerun, or
  the check fails on STATS.md and page-data.json.
