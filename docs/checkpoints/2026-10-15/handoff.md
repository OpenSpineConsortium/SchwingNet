# Symphony handoff, 2026-10-15 about 04:10 UTC

This replaces docs/checkpoints/2026-10-14e/handoff.md as the place to
start. That file still holds for where things live, the owner's rules,
memory.md (the Project's memory) and owner-todo.md (the owner's own
steps). This one says where each of the four threads stopped, read
from GitHub at about 04:05 UTC on 2026-10-15, and how to resume each.

The Fable usage limit was reached on 2026-10-15 at about 03:55 UTC;
start the new threads on another model (Opus) until it resets.

## 1. Where each thread stopped

### Deep lane (symphony-protocol#21): done

Merged at 02:19 UTC on 2026-10-15. Nothing is left on it. Its
follow-ups (a deep space for F15, F16 and F17; the weekly deep job on
main) are listed in #21's description and need no thread now.

### AIDaS grant (spine-program#95): packet merged, submission left

#95 merged at 01:25 UTC on 2026-10-15 (head 75b5672). The resume file
is 01_carm_level_detection/grants/aidas_2027/HANDOFF_2026-10-14e.md on
spine-program's main. Due Friday 2026-10-16 at 11:59 p.m. ET.

Left, all outside git:
- Build the Overleaf zip and the 10-page submission PDF. They need the
  two biosketch PDFs and the filled contacts, which are never
  committed, so the owner attaches the biosketches again in the new
  grant thread.
- The owner's own items (owner-todo.md item 1 and the resume file):
  send the allowability e-mail to aidas@wayne.edu (its text is in the
  resume file), fill the [DATA NEEDED] items in RECORD.md section 3,
  run the disclosure audit, decide what reviewers may see of Figure 3a,
  and submit.

spine-program#89 (claude/25) is the student aschehr's: not ours.

### CooperBench (coordbench#17): fix pushed, one review round left

https://github.com/OpenSpineConsortium/coordbench/pull/17, draft on
purpose, branch claude/coordbench-scrub-layers-8d9veg, head e3dc418.
e3dc418 fixes every finding of round four's review, the blocker
included, each with a test that fails on 21f5382. Three review rounds
of those fixes ran and were answered. The fourth stopped on the usage
limit with no report. `bash scripts/check.sh` passes locally on
Python 3.12 (1114 tests); CI on e3dc418 had not been read.

Next, in order:
1. Merge symphony-template#89 (this handoff and the CooperBench notes)
   once its check is green.
2. Read CI on coordbench e3dc418.
3. Run the fourth review round again on e3dc418: break zip_covers_tar
   and zip_extent, past_unread_blocks, and the stopped-short rule in
   layers_through, with mutants of those lines. Fix what it finds,
   each with a test.
4. Run `bash scripts/check.sh` with Python 3.12 first on PATH, mark #17
   ready, and merge it with a merge commit, the expected head sha
   copied from git. Check main's tree after.
5. Dispatch the fake run: Actions > Bench > Run workflow on main, mode
   fake, pairs @bench/cooperbench/pairs.txt, tag fake-1, survey_tag
   survey-1. Read its report in the report job's log.
6. Update docs/checkpoints/2026-10-14/cooperbench-run.md here by pull
   request.
7. Stop. The real run waits on the owner's steps (owner-todo.md item 3).

Notes: docs/checkpoints/2026-10-14e/notes/coordbench-review-17-round5.md.

### Protocol fixes (symphony-protocol#32, #33; symphony-template#87)

- symphony-template#87, ready, branch claude/symphony-handoff-2026-10-14-yo9pzb,
  head dc7aa11: the template's half of F18 (workers in Actions take a
  task several workers' labels give). Two review rounds answered;
  check.sh green at 7d1a532. It is behind main: bring main in by the
  update-branch call, wait for its check, merge. It must merge before
  any release that carries F18.
- symphony-protocol#32 (F18), draft, branch claude/owner-decisions-f18,
  head 002c1cb: fix, lane, 78 of 78 mutants caught, check.sh green.
  Left: the second adversarial review of its answers (it was to run
  once #87's review was done); then a template pull request that
  vendors the final head; then ready and merge with a merge commit.
- symphony-protocol#33 (F19), draft, branch claude/owner-decisions-f19,
  head b580243, work in progress, built on F18's first commit. Four
  tests fail on purpose; #33's description lists the steps. After #32
  merges: merge main into the branch, fix the four tests, write the
  tests and documents, check.sh, review and second round, ready, merge.
- Then F2, F8 (waits on the canary's C5, owner-todo.md item 2), then
  the stuck claim, which raises the version to 0.5.0. Then the
  measurement pass, then telling the owner 0.5.0 is ready. Only the
  owner approves a release.

### Watch for

- The weekly sync (Mondays 06:17 UTC, next 2026-10-19) opens a
  symphony-template pull request "Vendor symphony-protocol 0.4.1". It is
  a downgrade; the owner closes it.

## 2. How to resume (the owner)

1. Open https://claude.ai/code and the symphony Project. If the session
   picker offers a model, pick Opus.
2. Start three threads, one per line below, each by pasting its message
   as the first message. The deep lane needs no thread.
3. Allow the repository prompts each thread raises when it attaches
   coordbench, symphony-protocol or spine-program with push access.
4. In the grant thread, attach the two biosketch PDFs again.

Grant thread:

```
Resume the AIDaS grant. Read docs/checkpoints/2026-10-15/handoff.md in OpenSpineConsortium/symphony-template, part 1 "AIDaS grant", then the resume file 01_carm_level_detection/grants/aidas_2027/HANDOFF_2026-10-14e.md on OpenSpineConsortium/spine-program's main (#95 is merged). Build the Overleaf zip and the 10-page submission PDF; I attach the two biosketches here. Never commit the biosketches or the contacts. Due Friday 2026-10-16 11:59 p.m. ET. Tell me exactly what is left for me, with links.
```

CooperBench thread:

```
Resume CooperBench. Read docs/checkpoints/2026-10-15/handoff.md in OpenSpineConsortium/symphony-template, part 1 "CooperBench", and do its numbered steps in order, starting by merging symphony-template#89 once green. Attach OpenSpineConsortium/coordbench with push access and read its CLAUDE.md and #17's description first. Leak tests plant only the stand-in PLANTED in ordinary files, never /proc/self/environ or an environment file. No real run, and no Claude credential anywhere.
```

Protocol thread:

```
Resume the protocol fixes. Read docs/checkpoints/2026-10-15/handoff.md in OpenSpineConsortium/symphony-template, part 1 "Protocol fixes", then symphony-template#87 and symphony-protocol#32 and #33's descriptions. First merge #87 (bring main in, wait for green). Then finish #32, then #33, then F2, F8 and the stuck claim, one pull request each, each with an adversarial review and a second round. Attach symphony-protocol with push access. Never approve or publish a release.
```

Every thread follows the Rules below and tells the owner in one line as
each pull request lands.

## Rules

One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
