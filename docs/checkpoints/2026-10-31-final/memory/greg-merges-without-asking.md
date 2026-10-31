---
name: greg-merges-without-asking
description: No merge waits for greg (03:45 UTC 2026-10-31, "remove all owner required permission"); threads merge on green, owner gates being removed
metadata:
  type: feedback
  modified: 2026-10-31T04:20:09.628Z
---

2026-10-31 03:45 UTC, greg in the QA pipeline thread: "PLEASE FROM NOW REMOVE ALL OWNER REQUIRED PERMISSION FOR MERGING PRS!" This widens his word of 2026-10-30 22:55 UTC ("I am so tired of you asking me for permission to merge that was only for Ashley Schehr so she couldn't merge into my branch crap code. I am doing thorough testing by default.").

At 04:18 UTC, going to sleep, he widened it to everything: "I GIVE YPU ALL THE AUTHORITY YOU NEED TO PERMANENTLY PUSH PRS MAKE DECISIONS EVERYTHING I TRUST YOU!"

**Why:** asking him, or a gate that waits for his tap, costs him time and annoys him; he tests thoroughly by default and trusts the threads to decide.

**How to apply:**
- A thread pushes, merges its own pull request once its tests and CI pass, and makes the calls its work needs, never asking and never waiting for greg; it still reports what it did. Still his alone: anything public, usage credits, the patent dispute (sign nothing), NMDID image downloads, CT-RATE without his TB number, Radiopaedia by script. See [[training-runs-continue-only-on-progress]].
- Done 2026-10-31 ~04:15 UTC: owner-ok.yml now passes at once for admins AND bots (SchwingNet #524 merged, symphony-template #513), spine-program rule 10 lets a session of greg's merge on green (#245); the research loop merges on green. Kept carve-out: a non-admin person's PR (Ashley, students) still waits for greg. The org ruleset "Require owner approval to merge" was disabled by greg at 04:19 UTC. Original list of gates: .github/workflows/owner-ok.yml in SchwingNet and symphony-template (a bot's or non-admin's pull request waits for his Approve on the environment owner-ok; sessions' own pass at once via owner-self), the organization ruleset "Require owner approval to merge" (CONTRIBUTING.md), workflows whose pull requests "the owner merges" (synthesis, research loop, storage request, add-worker, workers with lands owner), and spine-program's "Greg merges".
- Open question raised with him: removing every gate also lets Ashley Schehr's pull requests merge on green without him.
- Grid jobs need no word either since 23:03 UTC (grid-use-not-restricted). The size rule still applies.
