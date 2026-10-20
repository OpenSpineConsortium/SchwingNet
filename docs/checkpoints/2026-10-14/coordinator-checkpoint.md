# Symphony checkpoint, 2026-10-14 01:10 UTC

The owner ran low on usage at 01:10 and asked for a checkpoint: push all progress now and review it in the next session. Every running thread was told to push what it has to a draft pull request, say where it stopped, and stop. Project memory (MEMORY.md) holds the same state with the thread ids.

## Next session, first

1. Read this file and MEMORY.md. Then fold this checkpoint into symphony-template's .claude/session.md by one pull request; that file still describes 2026-10-13 plus #66.
2. Review the open pull requests below before anything new merges.
3. Restart each stopped thread from its own last reply. The fixes thread and the harness step 7 thread both had a failed turn at about 01:10.

## Open pull requests to review

| Pull request | What it does | State at 01:10 |
|---|---|---|
| symphony-template#70 | F12 in the copies: the board's concurrency group queues runs instead of cancelling the waiting one | open |
| symphony-template#69 | F7 hook wiring in the template | draft at 00:36; missing from the 01:10 listing, so check whether it merged, closed or went into #70 |
| symphony-protocol#21 | Harness step 6: the deep lane and the git world | draft; the full deep lane, about two hours, was still running |
| coordbench#12 | CooperBench on Symphony's protocol in coordbench's Actions | draft; the owner said at 01:10 that it is green and to push it |
| harness step 7 | canary.yml and scripts/canary.py | no pull request seen yet; the thread stopped at 01:08 |

## What landed on 2026-10-13 and 14

- symphony-protocol: #13, #14, #15 to #19 (harness steps 1 to 5), #20 (F7 guard fence), #22 (F12, "main moved" told by state). No release since 0.4.1.
- symphony-template: #66 (checkpoint recheck), #67 (0.4.1 follow-up), #68 (plan ladder).
- symphony-marketplace#14, symphony-app#13, symphony-start#42 (sweep removed), site #16, #17, #18.
- spine-program #86 (0.4.1 with a weekly self-update), #88 (slimmed for students).
- beethoven-extension #9, #11 to #15, and beethoven-access#6 (20.0.0 public listing, store kit, automatic releases).
- coordbench#11 (the CooperBench kit on any Docker host).

## Workstreams

### Validation harness, symphony-protocol validation/DESIGN.md, eight steps

- Steps 1 to 5: merged.
- Step 6, the deep lane: draft #21. Left: the deep lane's measurements into the docs, the adversarial review, merge when green.
- Step 7, the monthly canary on OpenSpineConsortium/symphony-protocol-canary: canary.yml and scripts/canary.py in progress. Needs the owner's three canary clicks below.
- Step 8, the report: starts after steps 6 and 7.

### Fixes for the harness findings

The owner decided on 2026-10-13 at 23:48: the library fix on every finding, correctness over cost, no deadlock, no missed work, no orphaned worker. Order: F7, F12, F4, F14, F9, F13, F2, F8, then the stuck claim.

- Done: F7 (#20, the guard refuses a lease onto another worker's claim by reading the claim file on origin) and F12 (#22, "main moved" told by state; template#70 queues the copies' runs).
- Left: F4 (one dealer job feeds the whole matrix), F14 (show every open, unclaimed issue a worker's label names under Given to workers), F9 (one GET as canary C0, then drafts hear "main moved"), F13 (order overlaps by when the work began), F2 (the issue stays the work's identity for the whole claim), F8 (idleness by the server's pushed_at, after canary C5), and the stuck claim (a claim held when a release comment's reply is lost and the re-read fails gets re-read on the next run; noted in protocol#16).
- Every library fix rides one release, with the version raised by the last fix. Only the owner approves it.

### CooperBench, coordbench

- #11 merged. #12 is the draft that runs CooperBench on Symphony's protocol in Actions.
- Left: review #12, run it, and report every statistic needed to compare with the CooperBench paper and its follow-ups.

### Beethoven 20.0.0, Claude's side done

- Submission kit: /mnt/project-files/beethoven/store-kit-20.0.0.zip
- Guide for the upload and the automatic releases: https://claude.ai/code/artifact/faad8276-a633-4b1b-902b-0716790a0f26
- The first automatic GitHub release exists: extension-v20.0.0.102. Its store step reads "Not configured" until the secrets are in.

### spine-program and the student, Ashley (GitHub aschehr)

- Ashley has Write on spine-program.
- Ashley's guide to connect the grid to GitHub: https://claude.ai/code/artifact/8e18020d-4025-4aeb-b3e5-4cedf16343f4
- A Beethoven session on a compute node cloned public repositories at 00:54, so the grid reaches GitHub. spine-program is private, so the clone needs Ashley's own token, stored by Ashley; Claude never handles it.

## Waiting on the owner

1. **Canary repository**, three clicks in order:
   - Install Symphony Setup on symphony-protocol-canary only: https://github.com/apps/symphony-setup/installations/new
   - Press Create on the form it opens: Kind Auto, Merge for me, "Do not share" ticked.
   - Actions read for SymphonyBoard: https://github.com/organizations/OpenSpineConsortium/settings/apps/symphonyboard/permissions, then accept it at https://github.com/organizations/OpenSpineConsortium/settings/installations
2. **The symphony-protocol release**, when the fixes thread says the library is ready.
3. **Beethoven**, six steps in order: the hand test and the two st1234 curls from WSL; the dashboard upload with Visibility Public, trusted testers empty, then Submit for review; Google Cloud (Chrome Web Store API, OAuth consent screen, Web application client); the OAuth Playground refresh token; the five CWS_ secrets and the variable CWS_ON_PUSH=upload in beethoven-extension; one manual run of "Release the extension".
4. **spine-program**: run `git pull` then `_ops/ship_archive.sh` once from WSL in the laptop clone; remove Symphony Setup from spine-program; tick "Allow GitHub Actions to create and approve pull requests" at https://github.com/OpenSpineConsortium/spine-program/settings/actions
5. **Housekeeping**: /mnt/project-files/owner/housekeeping-steps.md. The cloud cannot delete branches, so the 68 merged branches wait on the owner's Allow on the device-session card in the thread "Owner's manual steps, verified with links".

## Optional, not yet asked for

- Clear the stale sweep wording in symphony-template's docs/start/claude-code.md and CLAUDE.md, and in symphony-marketplace's /symphony:new skill.
- Confirm the GitHub Pro, Team and Enterprise Cloud prices in docs/setup/free-or-paid.md.

## Rules in force

One pull request per change from the thread's own branch. Run bash scripts/check.sh first. Run an adversarial review before each substantive pull request. Merge once green on the owner's standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without the owner's words. Never push to a default branch. No API key or Claude credential anywhere.
