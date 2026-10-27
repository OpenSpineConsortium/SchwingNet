---
name: paused-threads
description: The six threads of the project symphony paused at the 2026-10-27 04:47 UTC checkpoint, each with its open PR, branch, handoff path and first step; none restarts until the owner says so
metadata:
  type: project
---

None of these restarts until the owner says so ([[priority-panjabi-first]]); item 5 alone takes over the tiers thread. Every handoff is in SchwingNet; a branch head may have moved, the PR is the record. Older handoffs on main come first, then the branch's.

1. FleXray audit of #391 and its anomaly route. Handoff docs/checkpoints/2026-10-27-morning/anomaly-route.md (main). No open PR. First step: one timing word (prints the failed report and requeues); tell the DRR thread first, its seg job holds the checkout. Design: docs/research/spineps-anomaly-route.md, docs/checkpoints/2026-10-26-morning/pack-stage-design.md.
2. DRR comparison (FleXray DRRs against real corpora). SchwingNet #418 draft, branch claude/project-thread-d14v3r (head 1c0b55d): the study rendered from the CT alone where no mask is needed (owner 2026-10-27 04:15 UTC). Handoff docs/checkpoints/2026-10-27-drr-comparison/HANDOFF.md and study-brief.md on that branch, after docs/checkpoints/2026-10-26-drr-comparison/HANDOFF.md on main. Steps: finish #418 (remove BENCH_SKIP_MASKS, the study part, review, merge); after 40799505 ends, one status word, the seg word once to read its report; if well, the gap word once.
3. CNS junction slides and the white paper. SchwingNet #416 draft, branch claude/project-thread-7qoboa (head b293efc): textbook chapter 36 with five figures (tools/schwingcheck_figures.py). About twenty confirmed review defects in the thread's own framing and figures (worst: rho described backwards; detect_v1 numbers quoted as current; the pilot cannot score the exact rule), none in the owner's text. Handoff docs/checkpoints/2026-10-27-cns-junction/README.md and review-findings.md on that branch; bordercall archive/HANDOFF.md steps 7-11.
4. The live door for other readers. Site draft https://github.com/OpenSpineConsortium/openspineconsortium.github.io/pull/147 (reader at /symphony/door/, no tests, no review) and SchwingNet #419 draft, branch claude/project-thread-24opi2 (.github/symphony/door.json). Handoff docs/checkpoints/2026-10-27-door-for-readers/HANDOFF.md on that branch: Playwright tests, three reviews (security first), merge, then the owner's one-time step.
5. Flux realism. Nothing open; #406 and #417 merged. Handoff docs/checkpoints/2026-10-26-flux-realism/HANDOFF.md, section "State at the second checkpoint". Steps: status read, the four fetches once each, the 9B fetch after the licence click, an hpcworker PR admitting realism then `update`, then edit, stats, lora, eval in turn.
6. Gold and silver tiers. SchwingNet #420 and symphony-template #500, drafts, branch claude/project-thread-cdwl0r (#420 head 828fb90). Handoff docs/checkpoints/2026-10-27-corpus-tiers/HANDOFF.md on that branch: apply the consistency lens's verdicts (data/corpus-tiers/work/critics.json, two conflicts first), rebuild, check.sh in a throwaway copy, adversarial review in both bodies, mark ready, merge, then one decision card for the census job. Bring main in again after #416 and #418 land.
- Done: fetch size readers for #163 (SchwingNet #400, symphony-template #496); what stays unverified is docs/research/exact-fetch-sizes.md.
- Not this project's: SchwingNet #264 (draft, branch claude/263 gone).

**Why:** a new account restarts each only from git.
**How to apply:** when the owner names a thread, read checkpoint-4 section 2 and that handoff before anything else.
