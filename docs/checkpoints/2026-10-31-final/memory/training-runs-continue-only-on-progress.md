---
name: training-runs-continue-only-on-progress
description: greg 2026-10-31 04:18 UTC: every training run tracks its objective and loss periodically, stops on insane answers, and continues only while it makes progress (about 50 epochs patience)
metadata:
  type: feedback
  modified: 2026-10-31T04:20:03.398Z
---

greg, 2026-10-31 04:18 UTC, before sleeping, about the QA loop's training: "I ABSOLUTELY NEED THIS TRAINING AND PRODUCING GOOD RESULTS BY THE TIME I WAKE UP THAT MEANS PERIODIC TRACKING OF THE OBJECTIVE FUNCTION AND LOSS AND MONITORING FOR OBVIOUS WRONG INSANE ANSWERS AND ONLY CONTINUING RUNS IF THEY ARE MAKING PROGRESS BY SAY 50 EPOCHS OR A REASONABLE NUMBER! ... IN THE HIGHLY POLISHED METAFLOW PIPELINE!"

**Why:** he wants overnight grid time spent only on runs that are improving, and wants wrong answers (NaN, exploding loss, collapsed outputs, anatomically impossible distances) caught by the pipeline, not by him in the morning.

**How to apply:**
- Every training flow logs its loss and its objective at a fixed period (progress page, W&B, a trend file in the run), not only at the end.
- Sanity guards run on every logged point: a non-finite loss, a loss far above its best, a collapsed output or an impossible value stops that run with a stated reason.
- A patience rule (about 50 epochs, or the equivalent in steps or rounds) ends a run whose objective has not improved by a stated margin; the flow records why it stopped.
- Threads watch their overnight runs themselves (scheduled check-ins) and fix and resend without asking. See [[greg-merges-without-asking]].
