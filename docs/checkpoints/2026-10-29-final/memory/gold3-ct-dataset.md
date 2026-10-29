---
name: gold3-ct-dataset
description: The owner's 22:49 UTC 2026-10-27 ask for all gold tier 3 CT as its own dataset (index DB, artifact, workflow hooks, anomaly stats, QA); done and merged 2026-10-28
metadata:
  type: project
  modified: 2026-10-28T06:21:07.305Z
---

The owner, 2026-10-27 22:49 UTC: "well whenvever this finishes i want all the gold tier 3 CT data as its own dataset, with a indexable database, an artefact, and anything i need to use it in the workflow, including anomaly statistics, and quality assurance they are true anomalies". Thread "Finish scan import and tier counts".

- DONE 06:20 UTC 2026-10-28. Merged: SchwingNet #437 (5f2165c) and bordercall #17 (0ecb844, the mask readers holdings/enhance_facts*.py and enhance_views.py).
- Members: ENHANCE.PET 1,557 gold 3 of 1,597 (3 repaired at gold 4; 37 with no C2 are silver 3); VerSe 17 (provisional until each sacrum is seen on the grid); TotalSegmentator 142 (ids only, on the grid; no rows yet).
- Layout: SchwingNet data/gold3-ct/ (facts.jsonl and facts-b.jsonl are the two readings, FACTS.json, members, verse, totalsegmentator), tools/gold3_ct.py (stdlib: build a versioned SQLite store, query, stats, qa, export, page, check), docs/research/gold3-ct/ (README, STATS.md, QA.md).
- Both readings ran in full in the thread's container (1,597 each). compare holds; the cross-check against the count and touch.json holds. A double rounding in reading A was fixed at bordercall 0be8f0c, and 11 Careggi rows were re-read. The facts are committed, so a later grid run only checks reproduction (case B). The grid handoff is docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md. Nothing has gone to the grid.
- Private page "Gold Tier 3 CT": https://claude.ai/artifact/XDGjjGKVcdi2xDht7a689w. Its source and rebuild steps are in SchwingNet artifacts/gold-tier-3-ct-xdgjjg/. It carries a redacted store copy (no grid path; a base64 zip carrier, since .zip is not served), 194 mask views (191 bench studies, 3 repaired), and a reader bench. The bench's verdicts land in the page's db collection verdicts/{reader id} and are NOT yet imported into the store's qa_review table. That import is the natural next step.
- Source copies (masks, bucket listings, CT-details, count outputs) are in /mnt/project-files/gold3-ct/ (678 MB).
- Grid sizes for any later card: aws_enhance_pet_labels is 11,256,936,591 bytes (listing of 2026-10-27).

- OPEN, the owner 17:08 UTC 2026-10-28, moving to another account: "I DISAGREE THAT ONLY 17 VERSE SHOULS BE INCLUDED AND NO TOTALSEGMENTATOTR BUT ILL HANDLE THAT ON THE NEXT ACCOUTN". Every candidate pool is in SchwingNet docs/checkpoints/2026-10-28-gold3-ct-handoff/HANDOFF.md section 2 (draft PR #443, which also adds the restart kit's memory/gold3-ct-dataset.md). Container-only material is in /mnt/project-files/gold3-ct/thread-handoff-2026-10-28/.

**Why:** the owner wants one place to use gold 3 CT for training and testing, with the anomalies checked.
**How to apply:** no grid, fetch or training without the owner's word and count; see [[enhance-pet-whole-count]], [[grid-words-and-counts]], [[owner-science-rules]].
