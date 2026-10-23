# The run report: CLAIM 2024, REFORMS and the data's licences

Source: the thread "Automatic report generation", 2026-10-23, issue #153, from the owner's ask of that day that the workflow, before training starts, build a record of every run showing complete CLAIM and REFORMS compliance and mapping the datasets a run trained on to their licences. Confidential, this repository only.

## What a run now leaves

`python tools/flow.py run` writes, after its last step, three files beside RUN.json in the run folder, and `tools/flow.py record` keeps them with the run's other small files:

- REPORT.md: the run's facts in one line, whether the report is complete, the data and licences section, and both checklists as tables, every item with its state and its evidence.
- claim.json and reforms.json: the same answers as data, each item with its id, section, what it asks, whether code or the owner answers it, its state (met, declared, not applicable, missing) and its evidence, with a tally and the sha256 of the study file it read.

`python3 tools/report.py write --run <folder>` writes them for any run folder, `write-recorded` for every run under docs/research/v1-demo/runs/, and the required check runs `check-recorded`, so a recorded run without its report, or a study answer changed without the reports written again, fails. `check --run <folder> --complete` fails while any item is missing: it is the gate to run before a number is published, not before a run starts, since a training run should never stop for a missing manuscript sentence.

## How each item is answered

data/reporting/checklists.json lists the 44 items of CLAIM 2024 (Tejani et al., Radiology: Artificial Intelligence 2024, doi 10.1148/ryai.240300, the short texts of its checklist table, read through a summarising fetch of the eScholarship copy since the session's proxy refused the journal and the PDF; check the wording against the published table once) and the 32 items of REFORMS (Kapoor et al., arXiv 2308.07832, with the code-or-declared split of artifacts/reforms-compliance-checklist-bpzdoi). Each item names a fact and who answers it:

- Code (20 CLAIM items and 18 REFORMS items, over 26 facts): read from the run's own files, RUN.json, split-check.json, train/checkpoint.json, train/MODEL.md, evaluate/results.json and the figures, and PROVENANCE.json. A met item quotes the file it rests on; a missing one names the file or step that would answer it, so each gap is a piece of work.
- Declared (24 CLAIM items and 14 REFORMS items, over 38 facts): data/reporting/study.json, one field per fact, the owner's own sentence. The code checks a field is there and cannot judge it. A field that does not apply starts with "Not applicable:" and its reason. Every field is empty today, on purpose: nothing was written for the owner.

A dirty tree, a split check that found a person or a frame in two parts, or a file the run does not hold never counts as met.

## The licences

The data and licences section reads PROVENANCE.json, which tools/licences.py provenance writes into the run folder (the thread "Training data licence provenance"), and never works a licence out itself: every source the run read with its licence text, class, commercial answer, whether the owner reviewed the class, and its frames by part; the run's least permissive class; whether the network may be used commercially; the licence recipe the catalog was cut by, if any; and the recipes the data would fit. CLAIM 7 and 10 and REFORMS 2a and 3a are met from it. Until that file is there the section says the licences were not recorded and commercial use is unknown.

## Where the two recorded runs stand

Both runs on the synthetic bank (a767a466f5c1, cd37124c487d) now carry their reports: 28 of the 76 items are met by their files (15 of CLAIM's, 13 of REFORMS'), and 48 are missing: the 38 declared items that wait on the owner's answers, four that wait on PROVENANCE.json (CLAIM 7 and 10, REFORMS 2a and 3a), and six that wait on files no step writes yet (CLAIM 12, 35 and 36, REFORMS 3f, 4a and 4b).

## What is not built yet

- exclusions.json (CLAIM 35, REFORMS 4a and 4b): the ingest and bank builders' excluded and unreadable samples with their reasons.
- missing.json (CLAIM 12, REFORMS 3f): missing fields per class, from the catalog.
- covariates.json (CLAIM 36): age, sex, pathology and device per part, from tools/covariates.py's census (#66).
- External testing (CLAIM 33, REFORMS 8a) stays declared until a set from another site is evaluated apart.
