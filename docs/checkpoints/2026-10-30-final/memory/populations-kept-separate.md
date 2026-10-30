---
name: populations-kept-separate
description: greg's rule of 2026-10-29: synthetic populations stay separate strata, predictions are meta-analysis style, no large rebenchmark while the populations are volatile; PR 43 holds the register and subgroups, PR 38 rebases onto it
metadata:
  type: feedback
---

greg, 2026-10-29 23:43 UTC, on the bordercall synthetic validation (PRs 38 and 43): keep the published populations separate and make a meta-analysis-style prediction, never merge them all into one population; do no large-scale rebenchmarking (the 480-point grid search, the recut after PR 39) while the synthetic populations are volatile. At 23:54 UTC he extended it: split into every known population, by author, with race, sex and similar variables set up so subgroup analysis is easy, done professionally.

**Why:** a merged table hides the spread between populations (tau), and every number moves when the reread's series change, so a big rerun now is wasted.

**How to apply:** random-effects pooling per cell with tau and a prediction interval; strata by paper (bordercall synthval/strata.py on PR 38) and the population register with subgroup variables (PR 43, synthval/register.py, subgroups.py, data/populations.csv); quick lumbar runs only until greg gives the word and the job count. See [[owner-rules]].

State 2026-10-30 03:30 UTC: PR 43 merged to bordercall main at 9024b05 on greg's word. He asked for the covariate work and the full naming run (tan_strata.py --tables 8, local CPU, about 25 minutes) on the next account; the handoff with both is /mnt/project-files/tan-split/HANDOFF.md. One exclusion list for both PRs: synthval/literature.py EXCLUDED, empty; greg chose to score dropping Yadav 2020 held out in PR 38's select.py. Finding greg needs plainly: across papers the register's covariates explain almost none of the spread once Tan 2004 is out (only specimen, 0.24); real covariate effects need per-person data, and the within-paper ones on hand are Duman's sexes and Yu's ancestries.
