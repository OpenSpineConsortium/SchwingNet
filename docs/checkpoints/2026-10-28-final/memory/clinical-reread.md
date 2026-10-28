---
name: clinical-reread
description: greg's ask of 2026-10-28 19:03-19:05 UTC to reread every paper for clinical detail to direct "the autonomous anatomist", and where it stopped - bordercall draft PR 21, 39 of 43 notes checked, the synthesis not run
metadata:
  type: project
---

greg, 2026-10-28:
- 19:03 UTC: "eisensteins entire discussion is about lstv, different indications and prevalences, radiographic projection of morphological metrics including how to measure certain things like the posterior canal using just a lateral xray and the intricacies all the way down to specfic levels and pearls and pitfalls, are you reading these papers for similar priceless details? if not you should do a reread of all the pdfs ive given you"
- 19:05 UTC: "given the broader scheme of my dfirection which i will tell you shortly i need those types of key details to at least direct the autoonomous anatomist"

Until then the papers had been read only for their printed values. The thread "Reread every paper for clinical detail" reread all 43 (the 42 of synthetic_spine and Panjabi's facets paper): transitional anatomy and its prevalence with each denominator; how and on which view each measure is taken, as a recipe for a 3D CT instance mask and for a radiograph alone; level-by-level detail and the junctions; measurement error; pearls and pitfalls; numbered instructions for the auto-anatomist; every detail with its printed and PDF page.

Where it stopped: bordercall draft PR 21 (branch claude/project-thread-y719tr, head 0d4b49b), research_notes/clinical-reread/ with README.md, HANDOFF.md, 43 notes and 39 records (notes/<id>.json), tools/check_notes.py, the Workflow scripts and PAPERS.sha256. 39 notes were checked against the whole PDF by a second reader; kunkel2011, moncadahabib2025, otsuki2021 and twomey1985 are drafted only. The synthesis (tools/synthesis.js) is written and not run. HANDOFF.md's next steps: check the four; run the synthesis; send its anomaly priors (only eisenstein1977, duman2026 and ahn2001 hold prevalences) to whoever holds PR 20; two corrections that wait for greg (Panjabi's specimens called embalmed in archive/bordercall, where the papers say fresh; how Eisenstein measured, for #239); the whole tables of decision 4.

**Why:** a later thread must not redo the reading, and the notes feed the auto-anatomist and the chain's anomaly priors.
**How to apply:** read research_notes/clinical-reread/ before any paper; no PDF or page text in git; quotes 12 words at most. Related: [[papers-in-hand]], [[owner-direction-2026-10-28]], [[item-p-state]].
