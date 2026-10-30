---
name: greg-anomaly-aware-splits
description: greg's rule of 2026-10-30 09:43 UTC: first runs use normal spines only; anomalies (four lumbar, six lumbar, T13, rib anomalies) are split by family across test and train; his 10:03 choice that full runs add anomaly training
metadata:
  type: feedback
  modified: 2026-10-30T10:51:31.161Z
---

greg, 2026-10-30 09:43 UTC: "The splits should be aware of the anomaly cases L sixes cases with only four lumbar vertebrae, and then all the thoracic rib anomalies and then T 13s for the initial run it should be constrained to only normal spines. The splits for the anomalous spines should stratify spines with only four lumbar vertebrae spines with six lumbar vertebra and spines with the T 13 across test and train."

At 10:03 UTC he chose, on a decision card, that the full run also trains on the anomaly train part. The smoke and the screen stay on normal spines only.

**Why:** a first run should learn normal anatomy cleanly. The anomalies are too few to waste on validation, so they go to test and train only.

**How to apply:**
- In any split for gold tier 3 training, read the families ribs first: 13 rib-bearing bodies is T13; 11 ribs or asymmetric ribs is a rib anomaly; with 12 ribs, judge by length (L6 is six lumbar; L4 on the sacrum is four lumbar).
- Put each anomaly stratum in test and train, never in validation.
- First runs take only the normals the masks confirm.
- Report the families apart. Never pool them with normals.

See [[latent-prior-test-reserve]].
