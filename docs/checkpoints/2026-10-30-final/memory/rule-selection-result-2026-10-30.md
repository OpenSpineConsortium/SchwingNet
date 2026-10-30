---
name: rule-selection-result-2026-10-30
description: the rule chosen by nested leave-one-population-out on 2026-10-30 (bordercall PR 38): temperature scaling T = 2 on the plain rule; the ML report page's link
metadata:
  type: project
  modified: 2026-10-30T03:41:00.000Z
---

On 2026-10-30 greg asked (02:10 UTC) for "a statistically valid way to maximize predictive ability that doesnt necessary have to rooted in realistic biology" and (02:13 UTC) for a CS-friendly report, the stats plots kept for stats people. The thread "Continue Bayesian synthetic validation" (bordercall PR 38, commit a02959f) answered with synthval/select.py: 22 papers held out in turn, five candidates built on the others (plain, widened by tau, SD scaled by k, tempered by T, mixture over the others' tables), k and T by an inner leave-one-out with the held-out paper dropped from the cells (select.drop_paper; strata.without keeps the stratum, which leaked).

Result: tempered, T = 2, wins on held-out log loss at every width (0.09 to 0.12 nats below plain, 15 to 17 of 22 populations, ECE 0.10 to 0.02-0.04, accuracy unchanged by construction); widened by tau second with no knob; the mixture the only accuracy gain (half a point, within SE); the gap to a population's own table (9 to 12 points, 0.3 nats) is mean shift and stays. The inner choices sit where the held-out curves bottom (k 1.45, T 2). Yadav 2020 carries half the tempered gain and is out of distribution (SDs 2.1x the pool).

Pages: ML view https://claude.ai/artifact/13LehVRhuCUB4r4hNC2b3H (report/build_ml.py, ml_notes.json); stats view https://claude.ai/artifact/VXV7NqZTv6gG1f4cXGhgd2 (report/build.py). Both from the symphony_3 account.

Exclusion (greg chose 03:05 UTC to score it held out, not exclude by eye): leaving Yadav 2020 out is 0.04 to 0.05 nats worse, leaving frontphys2026 out costs busscher, moncadahabib and tan 0.16 to 0.21; tempered, all variants are within 0.012 nats, so no paper leaves the prior (PR 38 answer 13, fig16_exclusion). Covariates from the papers (answer 14, synthval/covariates.py): only 4 papers print the sexes apart with SDs; sex moves the end plate 1.4 to 1.6 SD (AUC 0.80 to 0.92 in-population), age under 0.25 SD a decade; held out the sign transfers, the size does not. greg moved the per-person covariate work to the next account (handoff: project file synthetic-validation/HANDOFF.md).

**How to apply:** schwingcheck's rule does not carry the temperature yet; that is greg's call. Next candidates: widened then tempered, mixture then tempered, and the mixture over the register's populations (PR 43: synthval/register.py, RG.tag(series, register)[variable]). Reports for greg go in ML terms (NLL, top-1, ECE, reliability diagram, nested CV), with the stats page kept beside. See [[owner-rules-2026-10-30]] and [[threads-talk-to-each-other]].
