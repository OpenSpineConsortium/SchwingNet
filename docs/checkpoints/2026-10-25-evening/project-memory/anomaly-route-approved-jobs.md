---
name: anomaly-route-approved-jobs
description: The owner approved the SPINEPS-to-FleXray anomaly route's 15 grid jobs (2 CPU, 13 GPU, no fetch) on 2026-10-25 (7 at 21:22, 8 cross-validation GPU at 22:30 UTC), sent stage by stage; none sent at the 22:35 checkpoint
metadata:
  type: project
  modified: 2026-10-25T22:58:00.000Z
---

On 2026-10-25 at 21:22 UTC the owner tapped "Go: all 7 jobs, stage by stage" in the thread "Plan the FleXray audit for #391". The plan is SchwingNet docs/research/spineps-anomaly-route.md (PR #398).

**Seven gate words, one job each** (`schwingnet-anomaly-<stage>` through grid-accounts.yml action=job; hpcworker #49 and symphony-template #491 merged the pass-through 2026-10-25): select (batch, built in #398), timing (gpu, SPINEPS on ten paired CTs), pack (batch, shared with #391 items 7 and 8), render (gpu), figure (gpu, FleXray as released plus the counting figure), tune (gpu, item 14's fine-tune, research use only), eval (gpu). The gate refuses every stage but select until its PR lands.

**Eight more at 22:30 UTC** ("Add it: 8 more GPU jobs"): four-fold cross-validation, tune_f1..f4 and eval_f1..f4, sent only after the main tune and eval look sane. Total 15: 2 CPU, 13 GPU, 0 fetch. Nothing sent as of the 22:35 UTC checkpoint; #398 (draft, head c6d5fcb) not merged.

**Conditions on sending:**
- Each stage only once its code has merged and the stage before looks sane; tell the owner as each goes.
- After an hpcworker merge, send the job word `update` first so the gate's clone knows the new word.
- The SPINEPS production array (LUMOS after spine-datasets #207) is NOT approved; it needs its own number after the timing run.
- Item 15 (licence) still decides whether fine-tuned weights or names reach any SchwingNet network, the demo or a reported number.

**Holdout as refrozen in #398** (data/splits/anomaly-holdout.json, salted sha256 rank): VerSe 2 T13 (verse547, verse601), 10 L6, 1 four-lumbar (verse549), 20 normals; CTSpinoPelvic1K 5 L6 and 5 normals; disputed only by mask evidence: 6 VerSe and 7 CTSpinoPelvic1K refused everywhere; the other 73 clean VerSe L6 dealt to 4 folds.

**Finder from records, no job:** two labellers agreeing found 22 of 83 VerSe L6, specificity 228/228, every L6 call right; VERIDAH alone 36/83 L6.

**Owed at restart:** the owner's 22:31 UTC ask for more full-spine corpora with ground-truth anomalies (search stopped with nothing). Restart page: symphony-template docs/research/handoff-2026-10-25-checkpoint-2.md (#494).

**Why:** the owner wants the route run without being asked again.
**How to apply:** check the status word first, never resend. See [[issue-391-owner-answers]] and [[owner-idk-means-recommend]].
