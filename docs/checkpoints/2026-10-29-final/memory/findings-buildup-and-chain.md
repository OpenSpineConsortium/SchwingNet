---
name: findings-buildup-and-chain
description: Headline results of 2026-10-27 and 28 on synthetic columns - the build-up study over 32 measures, the table size, measurement error, L6/T13, the chain of levels, speed, the cadaver power note; all synthetic
metadata:
  type: project
---

Every number is from bordercall's generator, drawn from the table the rule assumes; none comes from a patient. Records: schwingcheck/README.md "The build-up study" (PR 18), PR 20's description, research_notes/cadaver-power/ (PR 19), archive/docs/EXACT_IDENTIFICATION_RESULTS.md. Older studies: [[findings-naming]].

- At three bodies one measure names 42.0% of fields exactly, the seven SPINEPS measures 73.1%, the greedy first seven 89.2%, all 32 98.3%; from 25 measures every 9-body field is named. The best seven (spinous length, lower end-plate area, transverse width, two interfacet measures, the inferior facet angle, pedicle width) share none of SPINEPS's seven, and no code measures most of them on a mask.
- A table from 12 people, as Panjabi's is, breaks the 0.99 promise: right 95.75% (seven measures) and 98.05% (32). From 50 or more people, 99.36% or more; about 50 come within 2 to 4 points of 2,000.
- Real error of 2 mm or 3 mm where the rule assumes 1 mm (3 bodies): 96.2% and 82.6% right at 0.99; told the error, 99.8% and 96.85%.
- Six-lumbar and T13 spines, all 32: 5.1 to 7.2% of the 0.99 answers wrong; the rule before PR 20 can never name an L6 or T13.
- Chain of levels (PR 20, 200 fields a cell, a step missing a body with probability 1/6): at 5 bodies with all 32, typical 98.0% exact against 88.0% for step d's consecutive rule; six lumbar 98.5 against 82.5; T13 98.0 against 76.5 (89.5 for gaps summed without anomaly states). The six-lumbar and T13 columns are the generator's own construction (chain.extended_table), so the chain is scored against the truth it was built from.
- Speed for one field, batch means with setup inside (not latency numbers by SchwingNet's rule, ONNX parity and a p95): the rule 0.31 to 9.68 ms at 3 bodies; NUTS 166 to 712 times as long for a field alone, and at 16 measures once silently wrong at R-hat 1.00; the chain, built once (PR 23), about 4 ms at 3 bodies, 10 at 5 and 81 at 9 on all 32 (path_logev about 24 s at 9), against SchwingNet's 97 ms budget.
- Cadaver power (greg's question of 2026-10-27 23:55 UTC): no meta-analysis of cadaver studies matches 2,000 CTs, however many; studies differ by a median 0.39 SD, so the pooled literature is worth about 2 to 16 scans a level; about 50 people of the population named suffice on synthetic columns.

**Why:** a later thread should quote these with their records, not re-derive them.
**How to apply:** quote a rate with its width, measure set, phenotype and record. See [[item-p-state]].
