# Symphony handoff, 2026-10-14 10:40 UTC (paste this as the first message of the next session)

Pick up Symphony from this checkpoint. The last account ran out of usage, so every thread pushed what it had to GitHub and wrote a "Checkpoint 2026-10-14b" section at the top of its pull request's description, or in a comment where it had no pull request. If a section is missing, the branch's last commit is the state. This message is newer than .claude/session.md.

**Where things live**
- Home repository: OpenSpineConsortium/symphony-template. Read its CLAUDE.md and .claude/session.md first.
- The previous handoff and everything before it: docs/checkpoints/2026-10-14/ on main.
- This session's files: docs/checkpoints/2026-10-14b/. Its notes/ folder holds the gh-aw comparison, its plans/ folder holds the compiled-workflows plan and the parked PR 1a patch, and handoff.md is this message. They land by the pull request titled "Checkpoint 2026-10-14b: handoff to a new account"; if it is still open, merge it first.
- Add other OpenSpineConsortium repositories to a thread when it needs them (symphony-protocol, coordbench, symphony-protocol-canary and the rest named in the previous handoff), and read each one's CLAUDE.md first.

**Done since the previous handoff**
- symphony-template#74 updated session.md from the previous handoff. #71 and #72 were already folded in by #73.
- symphony-template#70, F12's queue in the copies, merged as cb83274.
- symphony-protocol#24, harness step 7, the canary, merged with all ten checks green. "Main moved" is judged by state from the first run: a miss counts as known (F12) until a release carries the fix. The version is still 0.4.1.
- gh-aw was compared against Symphony. Keep the protocol: gh-aw's queue has no lock expiry and no notion of main moved, and its Claude engine refuses the subscription token. A few rows the usage limit skipped may still be marked unverified in the notes.
- My decisions of 2026-10-14: Candidate A, Symphony's own compiler generating all eleven workflows with claude-code-action on the subscription token, starts once 0.5.0's fixes have landed. A gh-aw pilot on the canary's three Claude workflows runs after I release 0.5.0. The plan is docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md.

**Do, in this order, one thread per item, at most three at once, and tell me as each lands**
1. symphony-protocol#21, harness step 6, the deep lane. Its three leads were faults of the harness's own model and are fixed, its searches resume from checkpoints, and the first deep run on the pre-review code found no violations. Finish the review's last confirmed findings, run check.sh, rerun the deep lane on the final code, fill in the docs' measurements, then merge when green.
2. The after-the-fact review of coordbench#12, CooperBench in Actions, just begun. Review it, read its smoke run's report, fix what the review finds by a new pull request, then carry on from docs/checkpoints/2026-10-14/cooperbench-run.md, short of the real run.
3. The protocol fixes in symphony-protocol, one pull request each, in this order: F4 (finish draft #23), F14, F9, F13, F2, F8, then the stuck claim. The last raises the version to 0.5.0. Details are in validation/DESIGN.md sections 13 and 14, validation/known.json and docs/checkpoints/2026-10-14/protocol-fixes.md. My decision of 2026-10-13 stands: the library fix on every finding, correctness over cost, no deadlock, no missed work, no orphaned worker.
4. Once the fixes are in: tell me release 0.5.0 is ready, since only I approve it. Then start the compiler from the plan, PR 1a to PR 7, and CooperBench (item 5 of the previous handoff). After my canary click below, run the canary's first live run and write the step 8 report.

**Mine, still open**
- Canary: install Symphony Setup at https://github.com/apps/symphony-setup/installations/new, pick Only select repositories and symphony-protocol-canary, then press Create on the form it opens with "Do not share" ticked. Once the adoption's pull request merges, uninstall Symphony Setup and press Run workflow at https://github.com/OpenSpineConsortium/symphony-protocol/actions/workflows/canary.yml. SymphonyBoard's Actions read is already done.
- CooperBench before a real run: environment bench in coordbench with me as required reviewer at https://github.com/OpenSpineConsortium/coordbench/settings/environments; organization secrets SYMPHONY_CLAUDE_1, 2 and so on from `claude setup-token`, limited to coordbench, at https://github.com/organizations/OpenSpineConsortium/settings/secrets/actions; variable SYMPHONY_CLAUDE_ACCOUNTS at https://github.com/organizations/OpenSpineConsortium/settings/variables/actions.
- Beethoven, spine-program and housekeeping: unchanged, listed in session.md and the previous handoff.

**Rules**
One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.

**Final state, 10:40 UTC**
- symphony-protocol#21: work pushed, checkpoint at the top of its description. Next: bring main in again, since #24 conflicts in four files; verify the runner review's eight findings; rerun the deep lane at the final head; fill in the docs; merge when green.
- symphony-protocol#23 (F4): main merged in and the deal tests added, pushed at c70354b, checkpoint at the top of its description. Next: F4's mutation run, the spec and design wording, the review, the template's workers.yml change, then F14 onward.
- coordbench#12: checkpoint in a comment on #12. The smoke run's three fake pairs ran with no errors, and the review stopped after one of seven reviewers with nine findings. Next: read gradeability survey run 38549172370, fix the findings by a new pull request, fix the pair list and run fake mode over it.
- SYMPHONY_CLAUDE_ACCOUNTS takes slot numbers separated by commas, for example 1,2,3.
