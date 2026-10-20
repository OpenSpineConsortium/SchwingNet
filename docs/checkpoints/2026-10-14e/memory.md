# The old Project's memory, as of 2026-10-14 23:45 UTC

The claude.ai Project the owner used until 2026-10-14 kept this memory outside GitHub, where the new account cannot read it. Save it as the new Project's memory before starting threads. It is newer than docs/checkpoints/2026-10-14c/handoff.md, part 6, and than docs/checkpoints/2026-10-14/memory/. Where a pull request's own description says otherwise, the description is newer.

## People

- The owner: greg, GitHub login Gregory-Schwing-MD-PhD, the only member of the private Project. Organization: OpenSpineConsortium.

## How the owner works

- Resumes work by pasting a dated handoff; each handoff is also a file, docs/checkpoints/<date><letter>/handoff.md in symphony-template, in its own files-only pull request. A paste can arrive cut short (the 2026-10-14d paste began part-way through), so threads read the full file from the repository.
- Three threads at most per handoff: the fixes stay in the thread on the handoff message, the deep lane and CooperBench run as sibling threads. The owner's own asks, such as the grant, get their own thread regardless of that cap (14c handoff, part 6).
- Uses more than one Claude account; commits show only the GitHub identity, so the Claude-Session trailer in a commit is how to tell which session made it.
- Asked about the pace twice on 2026-10-14 (18:54 UTC, whether the work ran on the owner's own computer; 20:27 UTC, what the day did for the product, what to expect and how much longer). The time goes into checking: each fix gets an adversarial review, a second review of that review's answers, and green checks, one pull request at a time per thread. Answer such questions in product terms (what users of Symphony get), not fix codes.
- Decision, 18:59 UTC 2026-10-14, on a decision card: keep the second review round on each fix rather than cut it for speed. Do not offer that trade again unless the owner raises it.
- At 20:30 UTC the owner was told 0.5.0 comes on 2026-10-15 at the earliest at that day's pace (a rough guess), F8 also needing the owner's canary adoption.
- Tell the owner in the project chat as each pull request lands, one line each.

## Where the work runs

- Every thread runs in the Project's cloud environment (Linux), never on the owner's computer. The owner's Windows computer serves Remote Control for a few folders of its own; none is used by this project. The desktop app's list of running Claude threads includes cloud threads, so many threads there does not mean local work.

## The owner's standing rules (verbatim)

One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.

- Conventions from the handoffs: merge with a merge commit; bring main into a branch by merging it in (no rebase, no forced push).

## Repositories (OpenSpineConsortium; push access confirmed 2026-10-14)

- symphony-template: the Project's repository; checkpoints and handoffs under docs/checkpoints/. Its main merges only a branch up to date with main whose check is green on the updated head (the ruleset's strict status checks), so merges go one at a time: bring main in (the update-branch call), wait for the check, merge.
- symphony-protocol: the library; v0.4.1 released 2026-10-13; the stuck-claim pull request raises it to 0.5.0; releases and the approval gate are the owner's.
- coordbench: CooperBench.
- spine-program: holds the AIDaS seed grant, 01_carm_level_detection/grants/aidas_2027/ (README.md, REVIEW_2026-10-14.md, HANDOFF_2026-10-14c.md and the revision's record). Due Fri 2026-10-16 11:59 p.m. ET.
- symphony-protocol-canary: not yet adopted; F8 waits on its check C5.
- symphony-template's branch claude/festive-edison-al7xu2: a leftover of 2026-10-10 on the owner's housekeeping list; theirs, leave it.

## The plan (14c handoff part 4, with the day's findings in their place)

1. The deep lane, symphony-protocol#21.
2. CooperBench: coordbench #14, #15, #16 (merged), #17, the fake run (tag fake-1), the checkpoint update; no real run before the owner's steps.
3. The protocol fixes. Merged 2026-10-14: template #82, #83, #81, #77 (15:54 UTC), #78 (16:10); library #25 F14 (16:13), #26 F9 (16:59), #27 F13 (18:04), #28 F15 (20:57), #29 F16 (21:07), #30 the owner's answers to F15's and F16's questions (21:14), #31 F17 (22:01). Open: F18 (#32), F19 (#33). Then F2, F8, the stuck claim (0.5.0).
3b. The measurement pass after the stuck-claim merge.
4. Tell the owner 0.5.0 is ready; the compiler; CooperBench's real run; the canary's first live run.

## What the fixes do (plain words)

- F4: a run deals all its workers from one look, so no two get the same issue (before, the second was refused after a wasted session).
- F14: Given to workers lists every open, unclaimed issue a worker's label names (before, worker:<name> alone showed nowhere).
- F9: a draft hears "main moved". F13: overlapping work is ordered by when it began, not by the lowest number.
- F15: a released task held by a worker's label alone gets todo back. F16: the spec follows GitHub on a pull request it calls clean while behind main. F17: a stranger's pull request from a fork is no longer taken for a claim's own, so it cannot hold a claim or hide from the board.
- F18: the clerk reads whose a claim is from its claim file, not the issue's labels alone, and a task several workers' labels give goes to the first of them with nothing else to do.
- F19: a stranger's pull request from a claim's own branch is no longer taken for the claim's own.
- F2: the issue stays the work's identity, so no duplicate notices. F8: idleness by the server's pushed_at, after canary C5, not the pusher's committer date. The stuck claim: a claim stuck by a lost reply is re-read on the next run (0.5.0).

## The grant (spine-program)

- A grant thread started at 20:03 UTC on the owner's message with the PI's and Co-PI's biosketches: the [DATA NEEDED] values looked up on the web (with source links), both PIs AIDaS-affiliated, more figures (the Beethoven extensions, the network, CT to X-ray), better writing, then the review, LaTeX for Overleaf and the PDF. Issue spine-program#94, draft pull request #95. The owner called the old figures weak and the grant poorly written.
- Decision, 22:05 UTC: the owner wants the VinDr and FluoroCap results kept in ("just do whatever gets better results"); the grant uses the stronger numbers (Figure 4: AP 90.8% with five of the device's cases, 98.1% with all, 98.2% from count and shape together), and RECORD.md quotes the owner.
- Settled, 22:16 UTC: the owner has permission to use any and all data and has filled out every data use agreement, so no session raises data permission or IRB scope again. That caveat came from spine-program's RESULTS_CATALOG.md line 126, which the grant thread marks settled in its pull request; directive D1 (the owner's, 2026-09-23) took FluoroCap out of training for quality (72.8% of its panels copy published figures), not permission.
- Decision, 22:29 UTC: rule 9 of spine-program's CLAUDE.md stays, so FluoroCap stays out of future training ("I don't think fluorocap will help"); the grant still reports the existing models' stronger results, and nothing is retrained.

## Symphony in brief (delivered to the owner at 21:25 UTC as an artifact the new account cannot open)

- A claim is the first push of the branch claude/N. The guarantees are bookkeeping safety, not code quality or speed: 17 on main, 12 checked by exhaustive small-world search and tests, 2 relying on honest commit dates, 1 known broken, 2 partly or not checked. It is the opposite design to the original CooperBench's blind pairs, and there is no outcome data until coordbench's pre-registered 50-pair run.

## Watch for

- Until symphony-protocol 0.5.0 is published, its weekly sync (Mondays 06:17 UTC, next 2026-10-19) opens a symphony-template pull request "Vendor symphony-protocol 0.4.1". It is a downgrade that would undo F4, F7, F12, F14 and the later fixes; its check stays red. The owner closes it (https://github.com/OpenSpineConsortium/symphony-template/pulls, open it, "Close pull request"); do not fix its check.
- Threads that search the web can stop on a WebSearch permission prompt; when one does, tell the owner in one line where to approve it.
- Do not tell the owner to press the canary's Run workflow (symphony-protocol actions/workflows/canary.yml) until a fix needs it. When F8 needs C5, say so; canary.yml takes a list of checks, so C5 can run alone.

## Lessons

- Leak or scrub tests: plant a stand-in token in an ordinary file; never link to /proc/self/environ or real environment files. That content made auto mode refuse every command for the rest of a thread (the first CooperBench thread, 2026-10-14 15:26 UTC).
- Work a safety check blocked moves to a fresh thread only on the owner's say-so.
- Auto mode refused a coordinator helper's write to the Project's shared folder ("Modify Shared Resources"). Do not route around it; deliver long text as a reply in a thread, or commit it to a repository.
- The coordinator session reads GitHub only for attached repositories. gh pr view fails (GraphQL is blocked); gh api REST works on attached repositories; symphony-protocol and coordbench need add_repo with push access before API reads.
- Repository notes can carry caveats the owner has since settled: on 2026-10-14 the grant thread repeated a stale data-use caveat from RESULTS_CATALOG.md twice and the owner objected. Check whether the owner settled a caveat before raising it.
