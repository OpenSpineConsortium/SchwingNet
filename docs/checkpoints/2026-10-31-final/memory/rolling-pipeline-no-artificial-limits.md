---
name: rolling-pipeline-no-artificial-limits
description: greg 2026-10-31 01:55-01:57 UTC: no artificial limits on the NMDID pipeline; no per-download check; size each block's output and RAM up front and set concurrency from it
metadata:
  type: feedback
  modified: 2026-10-31T01:57:54.609Z
---

On 2026-10-31 at 01:55 UTC greg read a checklist line about tying each person's download to the size rule's admission "one lane's landing at a time" and answered: "I DONT WANT ANY ARTIFICIAL LIMITATIONS ON THIS PROCESS!" At 01:57 UTC he said what he does want: "THE ONLY THING YOU SHOULD DO IS HAVE SOME UNDERSTANDING OF HOW MUCH SPACE IS NEEDED FOR THE OUTPUT OF EACH BLOCK THROUGHOUT THE TRAINING PROCESS SO MEMORY DOESNT CHOKE".

**Why:** he has 20 TB and wants NMDID streamed through as fast as the hardware allows; throttles and per-download gates a thread invents read to him as artificial.

**How to apply:** in the rolling pipeline and the training it feeds, no per-download admission, no lanes, no one-at-a-time, no reserved floor, no waiting loops. Instead a space plan: what each block writes (raw, converted NIfTI, masks, crops, projections, encodings, checkpoints) and the RAM it takes, measured per person, and the number of persons in flight set from it so disk and memory never fill. Describe any guard in plain words before adding it. See [[grid-use-not-restricted]].
