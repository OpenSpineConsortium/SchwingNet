Written by the protocol fixes thread at about 04:00 UTC on 2026-10-15, before docs/checkpoints/2026-10-15/handoff.md, which was read from GitHub ten minutes later, covers all four threads and is the place to start; this file stays for its decision and its lessons.

# Symphony handoff, 2026-10-15 about 04:00 UTC

Pick up from here. This file is newer than docs/checkpoints/2026-10-14e/handoff.md, whose memory.md and owner-todo.md still hold (the old Project's memory and the owner's own to-do list). The owner's credits were nearly spent at about 03:55 UTC and the owner asked for everything pushed and a handoff. Every branch below is pushed; no work lives only in a container.

## What this thread did (the protocol fixes thread, session_01GjBoZqAYEbXyTjnFTtg294)

- Started the three sibling threads at 01:10 UTC: the deep lane (session_01TxkNJhWGA7PvoJMHT3TC9t), CooperBench (session_0172Vev3K7caKhKxkffG7oqo) and the AIDaS grant (session_01W41DgnF8diKs6v4mKxRoUA). The first two stopped at once on a permission prompt to attach a repository and did no work; the grant thread worked (see below).
- F18's template counterpart, symphony-template#87 (https://github.com/OpenSpineConsortium/symphony-template/pull/87): workers in Actions take a task the labels give to several workers, the prompts read whose a claim is from the claim file, Announce takes the other workers' labels off, a worker label on an issue several workers hold wakes every worker. Two adversarial review rounds answered (its description lists both). Ready; if it is still open, its check was running at 03:55 UTC on head 7d1a532: merge it with a merge commit once the check is green.
- The plugin's copy of the claim skill, symphony-marketplace#15: merged at 03:54 UTC as 5f6be11 (plugin version 0.1.11).
- F18 in the library, symphony-protocol#32 (https://github.com/OpenSpineConsortium/symphony-protocol/pull/32), branch claude/owner-decisions-f18, head 002c1cb, still a draft: every finding of its first review is answered and pushed, CI green on 002c1cb (check, mutants 78 of 78, consumers, four downstream jobs, CodeQL), parity suite 30 OK with a template clone that has its history. Its description says what each answer is.

Decision: when a worker claims a task the labels of several workers gave, its Announce takes the other workers' labels off, so from the claim on the labels name the holder alone, as the claim file does; the claim file still decides whose a claim is where a label disagrees (spec/PROTOCOL.md on #32's branch, Labels and Announce).

## Where each open item stopped, and the next steps in order

1. **symphony-template#87**: merge once its check is green on 7d1a532 (merge commit, the expected head sha copied from git).
2. **symphony-protocol#32 (F18)**: its second adversarial review, of the answers in 002c1cb, was started twice and stopped twice (a container restart, then the owner's credit limit), with no result kept. Next: run that second review (three lenses: the answers against the first round's eight findings and the counts in DESIGN.md, README.md, GUARANTEES.md and F18.json; whether the second commit's tests bite under mutation; the Announce change's consequences across the oracle, the policies, the restructured F18 trace and F19's branch), answer what it finds, then a template pull request that vendors #32's final head (`python3 <symphony-protocol>/scripts/vendor.py <template> --consumer OpenSpineConsortium/symphony-template`), merged before #32; then mark #32 ready and merge it with a merge commit. The template's prose already hedges "once the vendored library carries F18", so the vendoring pull request drops those hedges.
3. **symphony-protocol#33 (F19)**: unchanged since the 14e handoff: after #32 merges, merge main into its branch (claude/owner-decisions-f19, never a rebase), fix the four tests failing on purpose, write the planned tests and documents, review twice, merge. Its description lists each step. Note for it: #32 restructured validation/traces/F18.json and validation/replay.py (an announce step takes a second argument, the labels to take off), which F19's branch also touches.
4. Then F2, F8 (after the canary's C5, owner-todo.md item 2), the stuck claim (0.5.0), the measurement pass, as the 14e handoff's part 2 says.
5. **The deep lane (symphony-protocol#21)** and **CooperBench (coordbench#17)**: not started this session. Their sessions are stopped at a repository-attach prompt; a new account starts them afresh from the 14e handoff's part 1 and docs/checkpoints/2026-10-14e/deep-lane/README.md and notes/coordbench-review-17-round4.md.
6. **The grant (spine-program#95, due Fri 2026-10-16 11:59 p.m. ET)**: its thread reported at 01:27 UTC that the 8-page draft is revised and checked and the 10-page submission PDF waits on the owner: the two biosketch PDFs (biosketch_han.pdf and biosketch_schwiebert.pdf) and each investigator's office, phone and e-mail (or fill the \tbd contact fields in Overleaf's contacts.tex). Read #95 and its branch claude/94 for the exact state; the thread's own resume file is 01_carm_level_detection/grants/aidas_2027/HANDOFF_2026-10-14e.md there.

## The owner's clicks

- Grant: attach the two biosketch PDFs and the contact lines in the grant thread, or a new one, and the other items of owner-todo.md item 1 (the allowability e-mail to aidas@wayne.edu, the eight [DATA NEEDED] items, the disclosure audit, the submission).
- A safety-net check-in of this thread is scheduled for 04:42 UTC (trigger trig_018mpw2s3Fj4mkLPgnj1jFSL); it costs a little usage when it fires. To stop it, open https://claude.ai/code/routines and delete "Re-check #87, #15 and #32 (2)".
- Everything else in docs/checkpoints/2026-10-14e/owner-todo.md stands.

## Lessons from this session

- A container restart kills running workflows and background checks; a review workflow's journal survives under ~/.claude/projects and its finished agents' results can be read from it, but a resume needs the script at a readable path, so copy the script into the scratchpad when it is launched.
- A sibling session started with create_session stops at its first add_repo prompt until the owner allows it; say so to the owner at once with the session's link.
- The stop hook wants commits authored as Claude <noreply@anthropic.com>: set user.name and user.email in each clone before the first commit.
