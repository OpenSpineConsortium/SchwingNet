# Symphony handoff, 2026-10-14 about 14:35 UTC (paste this as the first message of the next session)

Pick up Symphony from this checkpoint. The owner's session usage reached 94 percent at about 14:28 UTC on 2026-10-14 and the owner said: checkpoint, push everything, write a handoff, no more verification. Every thread was told to push every branch it held, write a section titled "Checkpoint 2026-10-14d" at the top of each of its open pull requests' descriptions, reply with where everything is and stop. Those sections are the state to trust: they are newer than this message where they differ, and where a section is missing the branch's last commit is the state. This message is newer than docs/checkpoints/2026-10-14c/handoff.md and than .claude/session.md, and its predecessor still holds for everything it says that this one does not change: where things live (its part 1), the owner's own items (its part 7) and the grant work (its part 8).

## 0. What this session did (13:45 to 14:35 UTC)

- Confirmed nothing was missing on the new account: the GitHub login is the owner's and every repository the handoff names is reachable with push. The handoff's own pull request, symphony-template#80, was merged by the owner at 13:39 UTC as e6cc54c.
- Merged the two files-only checkpoint pull requests: symphony-template#79 (the CooperBench review's notes) as 54c4f75 and #76 (the deep lane's 32 findings and the two fill scripts) as 52ac0d1. symphony-template's main is 52ac0d1.
- Learned how the template's main merges: the ruleset "Protect the default branch" requires the status "check" with strict required status checks, so a pull request merges only when its branch is up to date with main and the check is green on the updated head. The GitHub API's update-branch call (the GitHub tools' update_pull_request_branch) brings main in; the check takes about 80 seconds; then the merge, with a merge commit. Merges therefore go one at a time.
- Started three threads as the owner asked: item 1 (the deep lane) and item 2 (CooperBench) as sibling cloud sessions of this account, item 3 (the protocol fixes) in this session. Each sibling was told to send one line per landed pull request and to write its checkpoint section when told to stop.
- Item 3: started adversarial reviews, as workflows, of symphony-template#77, of F14 in both halves (symphony-protocol#25 and symphony-template#78) and of F9 (symphony-protocol#26); all three were stopped on the owner's word before any reported, so none of those reviews has run. Finished F9's remaining work and pushed it (below).

## 1. The state of every open pull request and branch, as last read

Read each pull request's "Checkpoint 2026-10-14d" section first; it has the exact next steps.

**symphony-template** (main 52ac0d1)

- #77, ready for review, the F4 counterpart, https://github.com/OpenSpineConsortium/symphony-template/pull/77, branch claude/protocol-fixes-xljomq, head b80b6ce, unchanged today; its check was green on b80b6ce against the old main. Not reviewed. Next: run the adversarial review (the lenses planned: the two changed step scripts of .github/workflows/workers.yml run with stubs for every case; the protocol semantics against the library's deal and the re-check's standing rules; GitHub Actions permissions and outputs; the documents and tests; compatibility across the vendored library versions), fold in what stands, update the branch, wait for the check, merge with a merge commit.
- #78, draft, the F14 counterpart, https://github.com/OpenSpineConsortium/symphony-template/pull/78, branch claude/protocol-fixes-f14-xljomq, head 7e18f2f, stacked on #77, unchanged today. Not reviewed. Next, after #77: update the branch, check, review, mark ready, merge; then symphony-protocol#25's downstream job.
- #82, this handoff's pull request, from branch claude/awesome-lovelace-7cm439: docs/checkpoints/2026-10-14d/handoff.md, files only. Merge it once its check is green, first of all; then #81, the CooperBench thread's review notes (below), files only too.
- Branch claude/festive-edison-al7xu2: the old leftover of 2026-10-10, on the owner's housekeeping list.

**symphony-protocol** (main 0b7185c, version 0.4.1, last release v0.4.1 of 2026-10-13)

- #25, draft, F14, https://github.com/OpenSpineConsortium/symphony-protocol/pull/25, branch claude/owner-decisions-f14, head 0deb3b9, unchanged today; green but for its downstream (symphony-template) job, red on purpose until #78 merges. Not reviewed. Next: #77, #78, then re-run its downstream job, review, mark ready, merge with a merge commit.
- #26, draft, F9, https://github.com/OpenSpineConsortium/symphony-protocol/pull/26, branch claude/owner-decisions-f9, head b09f5fe, pushed at about 14:20 UTC: the six test pins, the new tests in tests/test_github.py and tests/test_board.py, the F9 case of tests/test_validation_invariants.py rewritten under the model's opaque_pulls, the documents (validation/DESIGN.md, README.md, GUARANTEES.md, replay.py) and one added test in tests/test_validation_guarantees.py that holds every rule a GUARANTEES.md row cites to a callable of the library or the harness. Locally before the push, bash scripts/check.sh was green (1,105 tests) and python3 -m validation.mutants caught 33 of 33; GitHub's checks on b09f5fe were not read. Not reviewed. Cut from #25's commit, so after #25 merges, merge main into it (no rebase, no forced push), review, mark ready, merge with a merge commit.
- #21, draft, harness step 6, the deep lane, https://github.com/OpenSpineConsortium/symphony-protocol/pull/21, branch claude/validation-harness-step-6-mm6b8t, head 74aa6fe: the deep lane thread's, checkpointed at 14:52 UTC. c6f8c63 merged main (with F4) into the branch; 74aa6fe fixed the fourth review's 32 findings (docs/checkpoints/2026-10-14c/deep-lane/) with a test each: R1 to R21 verified by three refuters, R29 to R32 by one, R22 to R28 document fixes left unjudged. Pushed; the checks on 74aa6fe were not read; no deep run started. Its "Checkpoint 2026-10-14d" section and a verdicts comment are on #21. Next: read the checks on 74aa6fe, then run the deep lane at that head, detached (that thread's command: `setsid nohup python3.12 scripts/validate.py deep --jobs 4 --out validation-out > validation-out.log 2>&1 &`, about 2 h 10 min on 4 processors, --resume after a restart), then the run of record under validation/runs/2026-10-14/, the fill scripts, the review, ready, merge.
- Not started: F13, F2, F8, then the stuck claim, whose pull request raises the version to 0.5.0 (details: validation/DESIGN.md sections 13 and 14, validation/known.json, docs/checkpoints/2026-10-14/protocol-fixes.md).

**coordbench** (main dd9aa2d)

- #14, #15 and #16: the CooperBench thread's, checkpointed at 14:53 UTC with nothing unpushed. #14, draft, head 187efd6, every check green, unmerged; its description opens with a "Checkpoint 2026-10-14d" section that lists the cut review's findings in groups 1 to 4 (group 1, a pair whose eval.json holds an error is fetched for a rescore that run.py never performs, stood 3 of 3 refuters). #15 (head 0a4f965) and #16 (head 64bcaf5), drafts, green, untouched; #15 conflicts with #14 in PLAN.md only, #16 merges clean. No fake run was dispatched. The review's 21 findings and the two refuter verdicts are kept in symphony-template#81 (branch claude/coordbench-14-review-2026-10-14d, head 1854668, files only: docs/checkpoints/2026-10-14d/notes/coordbench-review-14.md), to merge once its check is green. Next: verify groups 1 to 4, fix the real ones with tests, check.sh, push, merge #14, then #15 and #16, then dispatch the fake run (tag fake-1), then the checkpoint update; stop short of the real run.

**spine-program** and **symphony-protocol-canary**: untouched today; the 2026-10-14c handoff's parts 3, 7 and 8 stand.

## 2. The plan, unchanged (docs/checkpoints/2026-10-14c/handoff.md, part 4)

1. The deep lane, symphony-protocol#21.
2. CooperBench: coordbench#14, #15, #16, the fake run, the checkpoint update; no real run before the owner's steps.
3. The protocol fixes: #77, #78, #25, #26 (F9), then F13, F2, F8, the stuck claim (0.5.0), each reviewed before it merges.
3b. The measurement pass after the stuck-claim merge.
4. Tell the owner 0.5.0 is ready; the compiler; CooperBench's real run; the canary's first live run.

## 3. How to resume

Make the next session on the account with usage to spare, with symphony-template as its repository, and paste this message whole. The session attaches symphony-protocol and coordbench with push access as needed. Three threads at most: it may start the deep lane and CooperBench threads again as sibling sessions (each reads its pull requests' checkpoint sections first) and keep the fixes in its own thread. The rules below are the owner's, verbatim.

## Rules

One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
