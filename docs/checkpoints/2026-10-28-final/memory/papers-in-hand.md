---
name: papers-in-hand
description: Where the 42 synthetic_spine papers and Panjabi's four are - in the old project's files only, never in git; which 20 a script may fetch again and which 19 greg uploads again in a new project
metadata:
  type: project
---

The 43 papers behind the generator are the 42 of spine-program synthetic_spine/sources.csv and Panjabi's articular facets paper of 1993. Panjabi's four are in bordercall under archive/bordercall/reference/papers/. The 42 were all in hand in the project symphony_4 by 2026-10-28 19:54 UTC, in its files (literature/synthetic_spine/ with a MANIFEST.md of sha256, pages and origin, and greg's uploads), and a new project starts with none of them. No PDF, page image or run of a paper's text goes in git, and a download stamp (the Hinck PDFs carry one) goes nowhere.

- 20 a script may fetch again with one plain GET (bordercall PR 21, research_notes/clinical-reread/HANDOFF.md, "Where the papers are"): 13 from PMC's Cloud Service, the public bucket pmc-oa-opendata, key <PMCID>.1/<PMCID>.1.pdf (abbas2021, arockiaraj2025, bonczar2024, busscher2010, cizmic2023, duman2026, frontphys2026, italianmri, masharawi2021, moncadahabib2025, otsuki2021, shin2024, vanderhouwen2009); yadav2020 and ahn2001 from their publishers' open copies; griffith2016, twomey1985, alonge2021, ahmed2019 and chaudhary2015 from the publisher addresses that handoff names. The thread's cloud environment needs full network access ([[cloud-environment]]).
- 19 greg uploads again: zindrick1987, krag1988, hou1993, olsewski1990, robertson2000, mitra2002, yu2015, tang2016, bach2019, hinck1966, gilad1985, amonookuofi1985, amonookuofi1982, kunkel2011, lien2007, makino2012, eisenstein1977, tan2004, chen2011. Springer answers a script with a JavaScript challenge, which is never passed, and PMC's terms leave its non-open-access papers to a person.
- Check every file against PR 21's tools/PAPERS.sha256 before reading it; the notes cite pages of exactly those bytes.
- 17 of the 42 also landed on the grid in the literature fetch of 2026-10-28 (job 40819848, landing /rs/rs_grp_oschome/go2432/data/literature_synthetic_spine/, Elsevier's files read only on greg's word); see [[literature-keys]].

**Why:** a thread in a new project that needs a paper must not refetch what a person must supply, or read a different copy than the notes cite.
**How to apply:** fetch the 20 when a thread needs them; ask greg for the 19 once, naming them; hash each before use. Related: [[clinical-reread]], [[closed-papers-check]].
