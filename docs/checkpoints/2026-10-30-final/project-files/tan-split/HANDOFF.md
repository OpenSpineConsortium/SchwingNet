# Handoff: Tan split and population register (bordercall PR 43), for the next account

Source: the thread "Continue the Tan 2004 stratum split", project symphony_3, 2026-10-30 03:30 UTC.
PR 43 merged to bordercall main at 9024b05 on greg's word ("merge as it stands", 03:26 UTC).
greg: "do the covariate work and full run on the next account".

## 1. The full naming run (greg's word given, 03:26 UTC)

From research_notes/synthetic-validation/, with the pinned packages of requirements-schwingcheck.txt
(a venv; system python lacks scipy):

    python3 -I tan_strata.py --out records/tan-strata --tables 8     # about 25 minutes on 4 CPUs
    python3 -I tables.py --records records --write README.md
    python3 -I tables.py --records records --check README.md

Then correct the quick numbers in README answer 8 and the section "Tan's population apart" against
the full record. Only the naming rows change (the rule's loss on the rest's tables and on Tan's own);
the matched-cell, split and prediction numbers do not. This is a local CPU run, not a grid job.
Run the tests after: tests/test_synthval.py (39) and tests/test_subgroups.py (22).

## 2. The covariate work (greg, 02:55 UTC)

His ask: show demographic, sex, age and similar covariate effects on spine morphology, predict the
covariates from the measurements and the reverse, and integrate it into the project as a whole.

What PR 43 established, which the work must start from:
- Across published papers the covariates explain almost none of the between-population spread once
  Tan 2004 is out (records/subgroups/subgroups.json, analysis_without_tan): decade, modality and age
  band 0.00, region 0.10, ancestry 0.16, country 0.35; only specimen holds (0.24). Paper and
  covariate are confounded in published tables, so the literature cannot show covariate effects.
- The effects that stand are within-paper: Duman 2026's men have pedicles 0.07 to 0.21 SD wider
  within age bands (3 of 4 cells below 0.05); Yu 2015's ancestries differ -0.23 to 0.20 SD (3 of 10).
- Tools: data/populations.csv (26 cohorts, every covariate the papers state), synthval/register.py
  (load, tag, stratum_counts), synthval/subgroups.py (analysis, each_against_rest, paired_contrast).
  A new covariate is one column of the register.

What is not done and needs greg's decisions:
- Real covariate effects need per-person data: per-person measurements with age, sex and the like
  from one cohort. The candidates are the gold tier 3 CTs with bordercall's morphometry (SchwingNet
  memory: the grid word `morphometry <set>`), if their metadata carry age and sex; not checked.
  Any grid job needs greg's word and the number of jobs.
- The prediction side (which population, sex or age band a set of measurements resembles, held out)
  is the PR 38 thread's: the mixture rule's posterior over the register's populations as components.
- Integration across the project is the coordinator's plan.

## 3. Exclusions

synthval/literature.py EXCLUDED is empty: one list for a paper left out on greg's word. He chose to
score dropping Yadav 2020 held out (PR 38's select.py) rather than exclude it outright; the quick run
says neither drop helps.
