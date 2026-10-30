---
name: owner-rules-2026-10-30
description: greg's rules of 2026-10-29 23:43 and 23:54 UTC for the synthetic validation: no large rebenchmark, populations kept separate with meta-analysis-style prediction, split into every known population with easy subgroup analysis
metadata:
  type: feedback
  modified: 2026-10-30T00:15:39.435Z
---

greg's words of 2026-10-29 (symphony_3, threads "Continue the Tan 2004 stratum split" and "Continue Bayesian synthetic validation"):

1. 23:43 UTC: "dont do any large scale rebenchmakring because its volatile how the synthetic popuklations will end up". The quick records stay; no full naming rerun, no grid job without his word and count.
2. 23:43 UTC: keep the published populations separate and "do like a metaanalysis style prediction not merge them all together". The validation's pool is a random-effects meta-analysis (REML, Higgins' prediction interval); Tan 2004 is a stratum of its own (bordercall PR 43); PR 38's thread builds the per-paper stratum layer on the generator and predictor side (synthval/strata.py).
3. 23:54 UTC: "continue this splitting process into as many known populations their are, probably by author but if there are race variables and sex variables ect make sure you can do subgroup analysis very easily, and make sure its all professionally done". Done on PR 43 as data/populations.csv (the register, 26 cohorts) with synthval/register.py and synthval/subgroups.py: any variable, one call.

**Why:** the synthetic populations move with PR 38's rerun and PR 39's recut, so a benchmark run now is wasted; a merged population would hide Tan's distance and any population's.

**How to apply:** a new population variable is one column of the register, never new code; sex is read only as a within-paper contrast; no naming benchmark or grid job without greg's word. See [[owner-rules]].
