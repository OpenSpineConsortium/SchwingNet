# Handoff: the synthetic validation, the exclusion test and the covariates (bordercall PR 38), for the next account

Source: the thread "Continue Bayesian synthetic validation", project symphony_3, 2026-10-30 03:40 UTC.
The full handoff is in the repository: bordercall, branch claude/project-thread-o3ng22-all-measures
(PR 38, a draft, head 35de3be), file research_notes/synthetic-validation/HANDOFF.md. This page only
points to it.

## What is done

- PR 43 (the Tan split and the population register) merged to main at 9024b05; PR 38 has merged main in,
  and its diff against main is the note's folder alone. 122 tests pass.
- The rule to carry: the plain rule tempered by T = 2, chosen by nested leave-one-population-out (README
  answer 12, figure fig15_select).
- greg's choice of 03:05 UTC, "Score exclusion held out": no paper leaves the prior. Leaving Yadav 2020
  out is 0.04 to 0.05 nats worse; leaving Front. Phys. 2026 out costs three populations 0.16 to 0.21; once
  tempered, every variant is within 0.012 nats (answer 13, fig16_exclusion). literature.EXCLUDED stays
  empty.
- greg's ask of 02:55 UTC, the covariates both ways, first pass from the papers (answer 14,
  fig17_covariates, synthval/covariates.py). Only four papers print the sexes apart with SDs. Sex moves
  the end plate 1.4 to 1.6 within-sex SDs, and one end-plate measure separates the sexes at AUC 0.80 to
  0.92 in its population. Age moves a measure by under 0.25 SD a decade. Held out, an effect's sign
  transfers between papers and its size does not.
- The pages, from the symphony_3 account: the ML view https://claude.ai/artifact/13LehVRhuCUB4r4hNC2b3H
  (Version 2) and the stats view https://claude.ai/artifact/VXV7NqZTv6gG1f4cXGhgd2 (Version 4).

## What the next account does (greg moved the covariate work there, 03:26 UTC)

1. The covariates per person, on the gold tier 3 CTs measured by bordercall's morphometry on the grid,
   with each person's age and sex. VerSe's demographics table carries age and sex. TotalSegmentator's
   meta.csv carries age; whether it carries sex is not checked. covariates.py runs on one row a person.
   This needs greg's word and the number of grid jobs.
2. A population-conditioned prior: select.py's mixture candidate with the register's populations, or
   the covariates, as the component weights, scored by the same held-out protocol.
3. Delete the note's HANDOFF.md, write the adversarial review into PR 38's body, and mark it ready.
