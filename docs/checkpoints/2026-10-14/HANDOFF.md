# Symphony handoff, 2026-10-14 (paste this as the first message of the next session)

Pick up Symphony from the checkpoint of 2026-10-14 01:36 UTC, corrected at 01:55. The last session ran out of usage, so every thread pushed what it had to draft pull requests and stopped. Nothing it left open has been reviewed yet.

**Where things live**
- Home repository: OpenSpineConsortium/symphony-template. Its CLAUDE.md and .claude/session.md are the source of truth, but session.md on main still describes 2026-10-13, so this message is newer.
- Everything the old claude.ai Project held is committed under docs/checkpoints/2026-10-14/ on main; its README.md says what each file is. PLAN.md and the designs are in its handoff-page/ folder (copied from https://claude.ai/artifact/XQj71up9dbJhwSStCVUe9T, which another account may not open). The old Project's memory is in its memory/ folder, and the threads' checkpoints are its other files.
- Add other OpenSpineConsortium repositories to a thread when its task needs them: symphony-protocol, coordbench, symphony-protocol-canary, spine-program, beethoven-extension, symphony-start, symphony-app, symphony-marketplace, openspineconsortium.github.io. Read each one's CLAUDE.md first. The GitHub tools may know some by their old sdlc-* names.

**Do, in this order, one thread per item, at most three at once, and tell me as each lands**
1. First, alone: list the open pull requests in those repositories and recheck this message against them. symphony-template#73 already folded the two checkpoint drafts (#71 Beethoven, #72 housekeeping) into .claude/session.md; close #71 and #72 as superseded if they are still open, and update session.md from this message by one pull request.
2. Review and land what the last session left open. Each gets the adversarial review, then merges when green.
   - symphony-template#70, the queue for F12 in the copies. It is already reviewed and green, so merge it first.
   - symphony-protocol#21, harness step 6, the deep lane. First replay, shorten and judge its three unjudged leads: two G1 (a claim shown under the wrong worker) and one G9 (a board run that wrote with nothing new). Each is either a fault in the harness's model or a real library finding, and a real finding joins the fixes in item 3. Then run the deep lane to the end, since a container restart cut the first run short, and fill in the docs' measurements.
   - symphony-protocol#24, harness step 7, the canary. Finish its "Not done" list, including its open call on how the canary judges "main moved", and tell me which way that call went.
   - coordbench#12, CooperBench in Actions, merged at 01:39 on my "push it" without a review after its CodeQL fix: review it after the fact, read its smoke run's report, and fix what the review finds by a new pull request. Then carry on from docs/checkpoints/2026-10-14/cooperbench-run.md.
3. The remaining fixes in symphony-protocol, one pull request each, in this order: F4 (finish draft #23: the mutation run, the review, the spec and design wording, more tests and the template's workflow change), F14, F9, F13, F2, F8, then the stuck claim. My decision of 2026-10-13: the library fix on every finding, correctness over cost, no deadlock, no missed work, no orphaned worker. Details are in validation/DESIGN.md sections 13 and 14, validation/known.json, and docs/checkpoints/2026-10-14/protocol-fixes.md. The last of these pull requests raises the version to 0.5.0.
4. Harness step 7's first canary run on symphony-protocol-canary, once my canary clicks below are done. Then step 8, the report.
5. CooperBench: run it with Symphony workers and report every statistic needed to compare with the CooperBench paper and its follow-ups. If it needs model credentials or organisation secrets, tell me exactly what and stop.
6. When the fixes are in, tell me release 0.5.0 of symphony-protocol is ready. Only I approve it.

**State at the checkpoint**
- symphony-protocol: last release 0.4.1. Merged since: #13 to #20 and #22. Harness steps 1 to 5 are #15 to #19. F7 (#20, the guard refuses a lease onto another worker's claim) and F12 (#22, "main moved" told by state) are fixed in the library but not released. Open drafts: #21 (step 6), #23 (F4), #24 (step 7).
- symphony-template: #66 to #69 merged (#69 wires F7's guard into the copies). Open: #70, #71, #72.
- coordbench: #11 merged (the CooperBench kit on any Docker host). #12 merged at 01:39, not reviewed after its CodeQL fix.
- Beethoven 20.0.0: Claude's side is done (beethoven-extension #11 to #15, site #17 and #18, beethoven-access#6). The store kit is in beethoven-extension under release/20.0.0/store-kit. Guide: https://claude.ai/code/artifact/faad8276-a633-4b1b-902b-0716790a0f26 (copied under guides/ in this folder if it could be read).
- spine-program: on 0.4.1 with a weekly self-update (#86) and slimmed for students (#88). Its checkpoint is a comment on spine-program#88. The student Ashley (GitHub aschehr) has Write. Ashley's guide to connect the grid to GitHub: https://claude.ai/code/artifact/8e18020d-4025-4aeb-b3e5-4cedf16343f4

**Known limits of a cloud session**
- It cannot approve deployments, create or edit releases, or delete branches, and it cannot read GitHub App settings pages. Tell me what to click instead, with the exact link.
- The grid reaches GitHub from a compute node. Private repositories need the student's own token, which Claude never handles.

**Mine, still open (remind me, with links)**
- Canary: install Symphony Setup on symphony-protocol-canary only (https://github.com/apps/symphony-setup/installations/new); press Create on the form it opens (Kind Auto, Merge for me, Do not share); give SymphonyBoard Actions read (https://github.com/organizations/OpenSpineConsortium/settings/apps/symphonyboard/permissions, then accept at https://github.com/organizations/OpenSpineConsortium/settings/installations).
- Beethoven: the hand test and the two st1234 curls from WSL; the upload as Public at https://chrome.google.com/webstore/devconsole; the Google Cloud and OAuth setup; the five CWS secrets and CWS_ON_PUSH=upload in beethoven-extension; one manual run of "Release the extension".
- spine-program: `git pull` then `_ops/ship_archive.sh` once from WSL; remove Symphony Setup from spine-program; tick "Allow GitHub Actions to create and approve pull requests" at https://github.com/OpenSpineConsortium/spine-program/settings/actions
- CooperBench before a real run: environment "bench" in coordbench with me as required reviewer; org secrets SYMPHONY_CLAUDE_1, 2, ... from `claude setup-token`, one per account; variable SYMPHONY_CLAUDE_ACCOUNTS listing the slots.
- Housekeeping (docs/checkpoints/2026-10-14/housekeeping-steps.md, and symphony-template#72): limit the two organisation secrets to the repositories that use them; delete the five old test repositories; turn on automatic deletion of head branches; delete the 69 merged branches, which needs a session on my own computer.

**Rules**
One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
