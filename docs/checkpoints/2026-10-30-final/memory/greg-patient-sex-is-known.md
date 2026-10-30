---
name: greg-patient-sex-is-known
description: greg, 2026-10-30 03:45 UTC: the patient's sex is known at imaging time, so naming rules and priors may condition on it as a given input
metadata:
  type: feedback
---

greg, 2026-10-30 03:45 UTC (thread "Continue Bayesian synthetic validation"), on the plan to test whether sex conditioning helps name a short field of view: "i think its total reasonable to expect to know the sex of the patient you are imaging".

**Why:** sex is in the imaging order and the DICOM header, so a rule that uses it asks for nothing a theatre does not already have; shape-to-sex prediction is then only a check, not a deliverable.

**How to apply:** treat sex as a given covariate at inference: the SchwingCheck table, the population-conditioned prior and any generative model take sex as an input, and the field-of-view test scores naming with the sex-conditioned table against the sexless one, held out as before. Age is not covered by this word; ask before assuming it is known. See [[populations-kept-separate]], [[rule-selection-result-2026-10-30]], [[owner-rules]].

State on 2026-10-30 13:10 UTC: morphometry enhance (40872077) and verse (40877151, 3 h 55 min) both ended exit 0. The join of their rows with sex and age is SchwingNet's gate word `morphometry covariates` (PR 497, merged at main c656299); greg's count of 08:55 UTC was ONE CPU job, sent at 13:07 UTC as job 40878978 at c656299. That count is spent: no second join without his new word (COVARIATES_RERUNS). Its report is read by sending the same word again once the job ends (logs/MORPHOMETRY-covariates.md, 300 lines a send). Literature result (bordercall PR 38, records/sex_naming): held out, telling the rule the sex gains nothing (+/-0.003 nats, 16 papers); with a population's own tables sex is worth 1 to 1.7 points, while the population's own table is worth 6 to 8.
