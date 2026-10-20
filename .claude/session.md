# Session checkpoint

Written 2026-10-14 at about 03:15 UTC by the Project thread for item 1 of
docs/checkpoints/2026-10-14/HANDOFF.md, the handoff the owner pasted as the
first message of the new claude.ai Project, and amended after its
adversarial review at about 04:05 UTC. It replaces the checkpoint of
2026-10-13 (symphony-template#65, #66, #71 to #73; its text is in main's
history at 1dda21d). The folder docs/checkpoints/2026-10-14/ holds what the
old Project held outside GitHub: the coordinator's checkpoint, the fixes,
CooperBench and housekeeping checkpoints, the old Project's memory, the
handoff page's files (PLAN.md and the designs) and three guides; its
README.md says what each file is. Every claim below was read from GitHub on
2026-10-14 between 03:00 and 03:15 UTC, and read again by the review.

## Completed work

Since the 2026-10-13 checkpoint, each merged with its checks green (the
site has no CI, so its #16 to #18 merged with no check run):

- symphony-protocol: #13 (the spec reads the board by a refspec), #14
  (README agrees with CLAUDE.md), #15 to #19 (validation harness steps 1 to
  5: the foundations, the mutation lane, the run as the workflow makes it,
  the fast lane, the regression traces and known.json), #20 (F7: the guard
  refuses a lease onto another worker's claim by its claim file) and #22
  (F12: "main moved" told by the state in whichever run finds a branch
  behind). main's version is still 0.4.1, so F7 and F12 are in the library
  and not released; the last release is v0.4.1 of 2026-10-13 13:39 UTC.
  Every consumer runs 0.4.1 and the plugin is 0.1.10; each VENDORED names
  438844f, the last commit that changed sdlc_protocol/, not the tag's
  commit 485d470, and the package is the same at both.
- symphony-template: #66 (the 2026-10-13 recheck), #67 (the pages brought
  to 0.4.1), #68 (the plan ladder), #69 (the hook hands the guard its
  claim-file reader, F7's fence in the copies), #73 (the 2026-10-14
  checkpoints committed under docs/checkpoints/2026-10-14/), and the
  checkpoint drafts #71 (Beethoven) and #72 (housekeeping), which #73
  merged in; GitHub marked them merged at 02:14 UTC, so they needed no
  closing.
- coordbench: #11 (the CooperBench kit on any Docker host, the token
  scrubbed from a pair's files) and #12 (CooperBench in coordbench's
  Actions: bench.yml with fake, survey and real modes, the environment gate
  and the report; merged 2026-10-14 01:38 UTC on the owner's "push it",
  with no review after its CodeQL fix 873c3a7; its smoke run, three fake
  pairs and the report job, passed).
- Beethoven 20.0.0, Claude's side: beethoven-extension #11 to #15 (the
  public listing's texts, release/20.0.0, the release workflow through the
  Chrome Web Store kit, the screenshots and the submission kit
  release/20.0.0/store-kit, the kit's subshell), site #17 and #18,
  beethoven-access#6. The first release from CI is extension-v20.0.0.102
  (2026-10-14 00:35 UTC); its store step says "Not configured" until the
  owner's secrets exist. Left on Claude's side, from #71's checkpoint: the
  e2e harness (extension/e2e) is behind 20.0.0's welcome texts, and a
  capture in a Chromium older than the manifest's Chrome 148 needs the two
  changes extension/store-assets/raw-20/LIST.txt names, in a copy of the
  package only. Not yet measured: a real upload through the kit, and
  20.0.0's screens on the real grid.
- spine-program: #86 (symphony-protocol 0.4.1 with a weekly self-update)
  and #88 (the record material moved to the grid); its checkpoint is the
  comment of 01:39 UTC on #88. The student Ashley (GitHub aschehr) has
  Write.
- Also merged: symphony-start#41 (an empty repository adopts: the run makes
  its first README) and #42 (the sweep removed; the form is the one way
  in), symphony-marketplace#14, symphony-app#13, site #16 (the Apps'
  privacy statement, version 7).

## Current state

Open pull requests, all of them (none in coordbench,
symphony-protocol-canary, beethoven-extension, beethoven-access,
symphony-start, symphony-app, symphony-marketplace or the site):

- symphony-template#70 (claude/owner-decisions-pnq7d9, head 58c8cbc):
  queue: max in board.yml, F12 in the copies. Ready, the check green on its
  head, no conflict, behind main since #73; no review on GitHub, the fixes
  thread's checkpoint says it reviewed it. Merge it first.
- symphony-protocol#21 (draft, claude/validation-harness-step-6-mm6b8t,
  head 126b9b9): harness step 6. It conflicts with main in
  validation/known.json, since #22 took F12 out of that file after #21
  branched; GitHub runs no pull_request workflow on a conflicted pull
  request, so its head carries no Checks or Validate run, only CodeQL, and
  the green check is its first commit's (0c4d495). Its description lists
  the three unjudged soak leads (G1, a claim shown under the wrong worker,
  on seeds 585 and 959; G9, a board run that wrote with nothing new, on
  seed 427) and the partial run under validation/runs/2026-10-14-partial.
- symphony-protocol#23 (draft, claude/owner-decisions-f4, head 45e301d):
  F4 in progress. Every check green, no conflict, no review.
- symphony-protocol#24 (draft, claude/harness-step-7-35acl6, head 5b33bc4):
  harness step 7, the canary. The required check is red on its head: one
  test in tests/test_canary.py (TheGitSide, the backdated commit) expects
  git's %cI as 2026-10-12T03:00:00+00:00 and the runner's git 2.55.0 prints
  2026-10-12T03:00:00Z (git 2.43 prints +00:00). Every other check is
  green; no conflict; no review. Its "Not done" list stands, with the open
  call on how the canary judges "main moved" while it vendors 0.4.1.
- spine-program#89 (draft, claude/25, by aschehr): the student's own claim
  on spine-program#25; not Symphony's to touch.

Where the handoff's "State at the checkpoint" differed from GitHub: #71 and
#72 were merged, not open; #70 is behind main; #21 conflicts and its head
has no run of the required check; #24's check is red.

Branches: the 69 merged branches of the housekeeping list are all still
there (symphony-start 15, the site 15, symphony-protocol 14 beside the three
drafts', symphony-marketplace 10, symphony-app 8 beside data, coordbench 6,
the template's claude/festive-edison-al7xu2), and coordbench's
claude/bench-kit-0fxuxy is now merged too, so it may go with them. Not
rechecked, since the five are outside a session's repository scope: whether
the old test repositories still exist; the housekeeping thread found all
five there at 00:10 UTC on 2026-10-14
(docs/checkpoints/2026-10-14/housekeeping-steps.md). Not readable by a
session: the App installations, the Apps' descriptions, the Actions box and
the secrets pages the owner's list names.

## Remaining tasks

For the session, the handoff's items in its own numbering, one thread per
item, at most three at once, each thread adding the repositories its item
needs and reading each one's CLAUDE.md first (the GitHub tools know some by
their old sdlc-* names), each pull request reviewed adversarially and
merged when green on the owner's standing permission:

1. Done: the recheck and this file.
2. Review and land what the last session left open: symphony-template#70
   first; symphony-protocol#21 (resolve validation/known.json against #22
   so the checks run again, replay, shorten and judge the three soak leads,
   each a fault of the harness's model or a library finding that joins
   item 3, then run the deep lane to the end and fill in the docs'
   measurements); symphony-protocol#24 (make the committer-date test hold
   on git 2.55, finish its "Not done" list, settle how the canary judges
   "main moved" and tell the owner which way); coordbench#12 (review after
   the fact, read the smoke run's report artifact from run 38493729698, fix
   what the review finds by a new pull request, then carry on from
   docs/checkpoints/2026-10-14/cooperbench-run.md).
3. The remaining fixes in symphony-protocol, one pull request each, in this
   order: F4 (finish #23: the mutation run, the review, the spec and design
   wording, more tests, the template's workers.yml change), F14, F9, F13,
   F2, F8, then the stuck claim; the last raises the version to 0.5.0.
   Details: validation/DESIGN.md sections 13 and 14, validation/known.json,
   docs/checkpoints/2026-10-14/protocol-fixes.md.
4. Harness step 7's first canary run on symphony-protocol-canary once the
   owner's canary clicks are done; then step 8, the report.
5. CooperBench with Symphony workers, reporting every statistic needed to
   compare with the CooperBench paper and its follow-ups; if it needs
   credentials or organisation secrets, say exactly what and stop.
6. When the fixes are in, tell the owner release 0.5.0 is ready; only the
   owner approves it.

After the six items, PLAN.md's order goes on
(docs/checkpoints/2026-10-14/handoff-page/PLAN.md, section 5): Phase 2, the
fresh test, once the owner has deleted the old test repositories, then
Phases 3 to 11; the owner's questions 6 to 14 of its section 3 come up as
their phases start.

Optional, not asked for: the sweep wording in CLAUDE.md's decisions and
constraints, docs/memory/the-front-door-is-one-press.md and its index line,
docs/start/claude-code.md and the marketplace's /symphony:new skill is stale
since symphony-start#42; and the GitHub Pro, Team and Enterprise Cloud
prices in docs/setup/free-or-paid.md are still to confirm.

For the owner, each with its link, since a session can do none of them:

- Canary: install Symphony Setup on symphony-protocol-canary only
  (https://github.com/apps/symphony-setup/installations/new); press Create
  on the form it opens (Kind Auto, Merge for me, Do not share); give
  SymphonyBoard Actions read at
  https://github.com/organizations/OpenSpineConsortium/settings/apps/symphonyboard/permissions,
  then accept it at
  https://github.com/organizations/OpenSpineConsortium/settings/installations.
- Beethoven: the hand test and the two st1234 curls from WSL; the upload as
  Public at https://chrome.google.com/webstore/devconsole; the Google Cloud
  and OAuth setup; the five CWS_ secrets and CWS_ON_PUSH=upload in
  beethoven-extension; one manual run of "Release the extension". The
  clicks are in
  docs/checkpoints/2026-10-14/guides/beethoven-store-upload-and-releases.md.
  Also from the 2026-10-13 list and left out of the handoff: the
  beethoven-qa tags v4.0.0 and v5.0.0 and beethoven-vscode#11 and #12, not
  rechecked, since neither repository is in this session.
- spine-program: git pull, then _ops/ship_archive.sh once from WSL; take
  spine-program off Symphony Setup's list (Configure, not Uninstall, since
  the canary needs the App); tick "Allow GitHub Actions to create and
  approve pull requests" at
  https://github.com/OpenSpineConsortium/spine-program/settings/actions;
  then try the student route once (a Project linked to spine-program,
  /board, one todo issue), the box still open on spine-program#72, and
  answer the onboarding document's open comment (spine-program#88's
  checkpoint comment names both).
- Symphony Setup's description: name the Actions setting the App applies
  (the 2026-10-13 list's step 6, not in the handoff and not recorded done)
  at https://github.com/organizations/OpenSpineConsortium/settings/apps/symphony-setup.
- CooperBench before a real run: the environment bench in coordbench with
  the owner as required reviewer
  (https://github.com/OpenSpineConsortium/coordbench/settings/environments);
  organisation secrets SYMPHONY_CLAUDE_1, SYMPHONY_CLAUDE_2, ... from
  claude setup-token, one per account
  (https://github.com/organizations/OpenSpineConsortium/settings/secrets/actions);
  the coordbench variable SYMPHONY_CLAUDE_ACCOUNTS listing the slots
  (https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions);
  later, once the real run works on those secrets, remove
  COORDBENCH_CLAUDE_TOKEN from the claude.ai cloud environment, which the
  Actions run never reads.
- Housekeeping (docs/checkpoints/2026-10-14/housekeeping-steps.md): limit
  the two organisation secrets to the repositories that use them; delete
  the five old test repositories; turn on automatic deletion of head
  branches in six repositories; delete the merged branches from the owner's
  own computer, since the cloud cannot.
- Approve each symphony-protocol release when GitHub emails: Review
  deployments, tick release, Approve and deploy.

## Decisions

The durable decisions are CLAUDE.md's block, word for word. Those of
2026-10-13 and 14, in brief: the library fix on every harness finding,
correctness over cost, no deadlock, no missed work, no orphaned worker, in
the order F7, F12, F4, F14, F9, F13, F2, F8, the stuck claim, with 0.5.0
raised by the last and approved by the owner alone; one thread per handoff
item, at most three at once, the owner told as each lands; and the rules in
force: one pull request per change from the thread's own branch, bash
scripts/check.sh first, an adversarial review before each substantive pull
request, merge once green on the owner's standing permission, never
approve, publish or change a symphony-protocol release or its approval gate
without the owner's words, never push to or force-push a default branch, no
API key or Claude credential anywhere, say exactly what is missing and
stop, ask before anything marked the owner's, every manual step with its
exact link.

## Constraints

The constraints are CLAUDE.md's block, word for word. Those of 2026-10-14,
in brief: a cloud session cannot approve deployments, create or edit
releases, delete branches or read GitHub App settings pages; the grid
reaches GitHub from a compute node, and a private repository needs the
student's own token, which Claude never handles; GitHub marks a draft
merged, not closed, when another pull request merges its branch; GitHub
runs no pull_request workflow on a conflicted pull request, so its head
shows no required check until the conflict is resolved; git 2.55 prints a
UTC date in %cI with Z where 2.43 prints +00:00.
