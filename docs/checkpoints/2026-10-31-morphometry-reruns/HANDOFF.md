# Handoff: morphometry reruns on the gold tier 3 masks

Source: the thread "Resynthesize morphometry and run the reruns" of the claude.ai project symphony_3, 2026-10-30 to 31, written on the owner's word of 2026-10-31 14:24 UTC to hand every thread off for local continuation. Aggregates only; no mask, CT or per-study row.

## Done

- The resynthesis: docs/research/morphometry-resynthesis.md (#509). The engine at bordercall 9c85de1 is the current code; nothing found by the screens, pull requests or literature is left unfixed in it but the disc readings at L4-L5 and T10 to T12, which the age covariate is to test.
- bordercall #38 (bounds card) and #35 (census) merged on the owner's word of 2026-10-31 00:18 UTC; bordercall #42, a stale README rewrite that conflicts with main, is left open.
- #514 (merged 2026-10-31 01:43 UTC): grid/logs/HOLD holds one line per run, so several jobs pin one checkout side by side; only the DRR study's data dependency and the morphometry join and prior still wait.
- The owner's count of 2026-10-30 14:33 UTC is spent, every job on code stamp 1cee7ea83e4c28db:
  - enhance, job 40900765: 1,597 ENHANCE.PET studies, exit 0 at 01:19 UTC; 1,561 admitted, 36 not.
  - verse, job 40902026: VerSe 374 and TotalSegmentator 159, exit 0 at 01:52 UTC.
  - covariates, job 40902924: exit 0 at 04:48 UTC, checked against the earlier join 40878978; autoPET 857 persons, 11 blocks withheld where they differed slightly from that join; VerSe has no sex, so none of its blocks print.
- The old reports are set aside as grid/logs/MORPHOMETRY-<set>-<old job>.md on the grid, the old rows under /rs/rs_grp_oschome/go2432/morphometry/<set>/kept/<old job>/; the new rows, lines and frames are in /rs/rs_grp_oschome/go2432/morphometry/<set>/ (and verse/totalseg/).

## Next

1. The old rows against the new, per measure and level, as a grid job (the rows never leave the grid; only the plot and aggregates do). The four measures #44 reworked (interpedicular distance at L4, L5 and the neck, pedicle width and height in the neck, C7 and T1, mid-disc height in the neck and upper thorax, the pedicle's sagittal angle) are the ones expected to move.
2. bordercall #38's card scored again on the new rows: the pedicle and canal failures should go; the disc failures at L4-L5 and T10 to T12 are to be read against the covariates join's age slopes.
3. The correlation prior (#50, #52, the grid word `morphometry prior`) fitted again on the new rows; the thread "Train on randomized spine phantoms" was told at 05:15 UTC that both sets are in.

## How to read a report

The grid words go through symphony-template's .github/workflows/grid-accounts.yml (action job, job schwingnet-morphometry-<set>, request a short plain name with no spaces); the answer lands on symphony-template's branch grid as logs/job-schwingnet-morphometry-<set>.json. Sending a set's word again prints its report and queues nothing once its rerun is spent. From a local clone with grid access, `bash ~/SchwingNet/grid/gate.sh morphometry <set>` on the login node does the same.
