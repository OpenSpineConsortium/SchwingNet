# Final handoff of 2026-10-30: every thread of symphony_3, its pull request and its handoff, for the next account

Source: the thread "Restart the auto-anatomist probe", claude.ai project symphony_3, on the owner's order of 2026-10-30 20:35 UTC ("write a handoff and checkpoint so another account can continue this work ... no adversarial review ... all the threads pushed, their state written in the handoffs, and a handoff which references each thread's handoff and all files/work checkpointed ... don't leave any files behind") and the coordinator's list of threads. It is the entry point for the next account and builds on docs/checkpoints/2026-10-29-final/README.md, which still holds for the threads of 2026-10-29; where they differ, this file holds. Confidential: it stays in SchwingNet. No secret, token or credential is in it.

## 0. Read this first

1. Read this file, then [memory/MEMORY.md](memory/MEMORY.md), then the handoff of the piece of work you are given (section 2).
2. The owner's standing rules are in memory/ (owner-rules-2026-10-30.md and MEMORY.md). Since 2026-10-30 16:59 UTC threads send grid jobs within their agreed work without asking him each time; the size rule still holds. Every deep learning job runs on a launched flow under a frozen PREREG; a frozen PREREG is never edited (a departure goes in DEVIATIONS.md, a new design is a new file with its own freeze).
3. Reports to the owner are plots with short notes in machine learning terms (posteriors, calibration, held-out accuracy); messages are short and plain.
4. Nothing here was reviewed after 20:35 UTC: the owner asked for no review, so treat each handoff's last items as unverified.

## 1. The owner's words that set this handoff

- 2026-10-30 18:05 UTC, going into the operating room: "assume I approve of whatever you need to get a training run on gold tier data going for when I'm out, whichever will me the most testable and likely to work".
- 20:35 UTC: the order quoted above, and "I have a few usage credits so be frugal".

## 2. The threads

| thread | state | pull requests | handoff |
|---|---|---|---|
| Restart the auto-anatomist probe | gold tier 3 screen merged; second smoke job 40885678 on galhp, not read since 19:12 UTC; demo and second screen's arms on a draft | SchwingNet #483 and #500 merged; bordercall #40 merged, #48 draft (branch claude/project-thread-5hj0q5) | [autoanatomist/HANDOFF.md](autoanatomist/HANDOFF.md) |
| Continue Bayesian synthetic validation | rule chosen (plain rule, T = 2); covariates first pass from the papers; totalseg complete job 40882547 failed on an import clash, the fix merged as SchwingNet #499 (b49583b), and the one rerun allowed was not sent: TotalSegmentator 2.18.0 would download four weight parts the job lacks, MOOSE refuses the device word gpu, and an S1-in-sacrum question waits for the owner; bordercall #38 waits on bordercall #44 for a gold tier 3 rescore | bordercall #38 draft (head 7817492); SchwingNet #499 merged, #503 ready with auto-merge; symphony-template #510 and hpcworker #53 merged | SchwingNet #503's docs/checkpoints/2026-10-30-totalseg-rerun/README.md, with the findings that block the rerun in docs/research/gold3-ct/completion/RERUN-REVIEW.md; the earlier pointer and figures 18 to 20 in [project-files/synthetic-validation/](project-files/synthetic-validation/HANDOFF.md) |
| Plan evaluating latent shape priors against explainable metrics (latent-prior planning; the pipeline sandbox) | test reserve, repeat groups and parts drawn at SchwingNet 3abc2fa; planning note finished as a draft | bordercall #45 draft (research_notes/latent-shape-prior-evaluation/) | that note's folder on PR 45's branch; the reserve's files in [project-files/latent-prior/](project-files/latent-prior/README.md); the sandbox in memory/pipeline-sandbox-2026-10-30.md |
| Continue the Tan 2004 stratum split | resolved: merged at 9024b05; the full naming run and the covariate work moved to the next account | bordercall #43 merged | [project-files/tan-split/HANDOFF.md](project-files/tan-split/HANDOFF.md) |

The two threads still open at 20:35 UTC were asked to push and send their handoff paths; where a path above differs from theirs, theirs holds.

## 3. What is on the grid

- autoanatomist gold3_latent_smoke, job 40885678 (galhp), sent 19:12 UTC at SchwingNet 432489a: state not read. The first send, job 40884715, failed on a V100's compile. What to do next is section 2 of [autoanatomist/HANDOFF.md](autoanatomist/HANDOFF.md).
- totalseg complete, job 40882547: failed on an import clash; the fix is merged (#499); the one rerun the owner allowed was not sent, for the findings in SchwingNet #503 (section 2). The morphometry join on the bounds card is memory/gold3-on-bounds-card.md.

## 4. What else is here

- memory/: the project memory as it stood at about 20:45 UTC, 20 files, verbatim except that MEMORY.md's line on the resynthesis inputs spells three non-ASCII characters in ASCII ("section 7", "-17 deg", "+23 deg"), as the docs check requires.
- project-files/: the claude.ai project's shared folder, every file of autoanatomist/, latent-prior/, synthetic-validation/ and tan-split/, copied as they were.
- autoanatomist/second-screen-wip.patch: the withdrawn first attempt at the second screen, kept so nothing is lost (its handoff, section 4, says what of it to use).

## 5. A first prompt for the next account

"Read SchwingNet docs/checkpoints/2026-10-30-final/README.md and memory/MEMORY.md beside it. First read the state of the auto-anatomist smoke (job 40885678) as its handoff's section 2 says, and send the screen if the smoke ended in exit 0. Then continue the threads the owner names, each from its own handoff, one thread per item."
