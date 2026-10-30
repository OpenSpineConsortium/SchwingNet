# Final handoff of 2026-10-29, project symphony_2: one line per thread

Source: the thread "Rewrite the outdated bordercall README" in the claude.ai project symphony_2, 2026-10-29 about 23:15 UTC, on the owner's words of 23:13 UTC: "PLEASE CHECKPOINT ALL THREADS NOW AND PUSH WHATEVER THEY HAVE AND WRITE HANDOFFS ... SO ANOTHER ACCOUNT CAN CONTINUE!" The thread list is the coordinator's. The handoff of the project symphony_4 is the README one folder up; this file adds the symphony_2 threads. The owner's standing rules are in [memory/](memory/MEMORY.md).

Each line gives the work, its pull request with its branch, its handoff, and the next step. A handoff path is on that pull request's branch, unless it says main. Every pull request, branch and path below was checked to exist at 23:20 UTC. The exceptions are the lines marked "not checked".

| Thread | Pull request (branch) | Handoff | Next step |
| --- | --- | --- | --- |
| Auto-anatomist (top priority) | SchwingNet #483 (claude/project-thread-f0dity, head e1c6962); bordercall PR 40 (claude/project-thread-f0dity, head 7d5fecb: the architecture block and the probe) | SchwingNet docs/checkpoints/2026-10-29-autoanatomist-flow/HANDOFF.md, section 8; bordercall autoanatomist/README.md and research_notes/measures-to-2d/README.md | The network is a swappable block, and the dummy privileged-information probe runs first. The earlier drafts, SchwingNet #471 and bordercall PR 37 (claude/project-thread-wfwuc2), came before these. |
| Bayesian generator, synthetic validation of every measure | bordercall PR 38 (claude/project-thread-o3ng22-all-measures) | research_notes/synthetic-validation/HANDOFF.md | The grid job waits for the owner's word and count. |
| TAN split: Tan 2004 as a stratum of its own | bordercall PR 43 (claude/project-thread-2ja3ux) | none; the PR description and research_notes/synthetic-validation/README.md | |
| Clinical reread | bordercall PR 39 (claude/project-thread-r19vr5, marked ready) | research_notes/clinical-reread/HANDOFF.md; research_notes/prior-art-measurement/README.md | Add the six prior-art notes still to come. |
| Morphometry on the gold tier 3 masks | bordercall PR 44 (claude/project-thread-e89pjg) | research_notes/morphometry/handoff.md | Once the enhance job is gone, send the gate word `schwingnet-morphometry-verse` by hand. |
| Gold tier 3 census and completion | SchwingNet #489 (claude/project-thread-jpwjrf); bordercall PR 41, the same branch name | SchwingNet docs/checkpoints/2026-10-29-gold3-completion/HANDOFF.md, section 8 | |
| Metaflow pipeline | SchwingNet #490 (claude/project-thread-6b1r1p-handoff) | docs/checkpoints/2026-10-29-metaflow-pipeline/HANDOFF.md | |
| Organization map | SchwingNet #488 (claude/project-thread-kwvrqv); site openspineconsortium.github.io #150 and symphony-app #92 (not checked: neither repository is in this session) | docs/checkpoints/2026-10-29-organization-map/HANDOFF.md | Make the fixes to site #150 that the handoff's "Left open" names, then merge. |
| bordercall README | bordercall PR 42 (claude/project-thread-r4iyuy) | none needed | Only the owner's merge. |

The other open bordercall drafts, PR 30 (morphometry, older branch claude/project-thread-6o9umj) and PR 35 (census of every measure), belong to symphony_4's handoff one folder up.

## First prompt for the new account

Paste this as the first message in the new account's project chat:

```
You are the coordinator for the SchwingNet, bordercall, symphony-template and spine-program repositories.
Before anything else:
1. Read docs/checkpoints/2026-10-29-final/symphony-2/README.md on SchwingNet main, then
   docs/checkpoints/2026-10-29-final/README.md (the symphony_4 threads). Together they index every
   open thread, its pull request, its branch and its handoff file.
2. Load docs/checkpoints/2026-10-29-final/symphony-2/memory/owner-rules.md and the
   docs/checkpoints/2026-10-29-final/memory/ folder into project memory. Those rules bind every thread.
3. Start no thread until I name it. When I name one, start a thread that reads that thread's handoff
   on its branch and carries on from the branch's pull request.
Never run archived code, never send a grid job without my word and the number of jobs, and keep
reports to plots with short notes on how to read them.
```
