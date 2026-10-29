---
name: gold3-ct-dataset
description: The gold tier 3 CT dataset (ENHANCE.PET 1,557, VerSe 17, TotalSegmentator 142 with no rows), built and merged 2026-10-28, its private page and bench, and the owner's open disagreement with 17 VerSe and no TotalSegmentator rows
metadata:
  type: project
---

The owner, 2026-10-27 22:49 UTC: "well whenvever this finishes i want all the gold tier 3 CT data as its own dataset, with a indexable database, an artefact, and anything i need to use it in the workflow, including anomaly statistics, and quality assurance they are true anomalies". Built in the thread "Finish scan import and tier counts"; its handoff is SchwingNet docs/checkpoints/2026-10-28-gold3-ct-handoff/HANDOFF.md, the programme docs/research/gold3-ct/README.md.

- Merged 2026-10-28 06:20 UTC: SchwingNet #437 (data/gold3-ct/, tools/gold3_ct.py, docs/research/gold3-ct/, artifacts/gold-tier-3-ct-xdgjjg/) and bordercall #17 (holdings/enhance_facts.py, enhance_facts_check.py, enhance_facts_cross.py, enhance_views.py, 113 tests).
- ENHANCE.PET's masks read twice in full in a cloud container: 1,557 whole of 1,597 (autoPET 979 = 865 to 900 persons, Leipzig 379, Careggi 199); 37 with no C2 are silver 3; 1134, 1283 and 1347 repaired, gold 4. Never exclude a four-lumbar spine (the owner, 17:10 UTC on 2026-10-27). The two readings agree on all 1,597 and match the count. The facts are committed, so a grid run only checks reproduction.
- The private page: https://claude.ai/artifact/XDGjjGKVcdi2xDht7a689w, from the gschwing account. Its reader bench saves verdicts in the page's collection verdicts, empty on 2026-10-28 17:15 UTC; nothing imports them into the store's qa_review yet. A publish from another account makes a new page with an empty bench.
- Open, the owner 2026-10-28 17:08 UTC: "I DISAGREE THAT ONLY 17 VERSE SHOULS BE INCLUDED AND NO TOTALSEGMENTATOTR BUT ILL HANDLE THAT ON THE NEXT ACCOUTN". The handoff's section 2 lists every candidate: VerSe 374 series of 355 persons (76 hold C2, 325 TUM subjects with neuroradiologist reads, 338 silver 3); TotalSegmentator 1,935 persons (142 clean, 156 with C2 and the sacrum, 70 with Hofmann's reads), whose subject list is on the grid only.
- Container-only material is in the Claude project's files under gold3-ct/thread-handoff-2026-10-28/, the masks under gold3-ct/enhance-pet-source/.

**Why:** the owner wants one place to use gold 3 CT for training and testing, with each anomaly's evidence checked.
**How to apply:** start by putting section 2 of the handoff to the owner as two decision cards. Then build the verdict import. Nothing goes to the grid without the owner's word and count. See [[owner-science-rules]], [[grid-words-and-counts]], [[findings-corpus-and-data]].
