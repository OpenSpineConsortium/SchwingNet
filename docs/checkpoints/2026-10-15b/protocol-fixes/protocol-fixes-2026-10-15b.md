Copied on 2026-10-15 from the Project's shared folder (handoffs/), where the protocol fixes thread wrote it at 22:54 UTC, so that a session on another account can read it. The evidence for the two findings it names last is committed as docs/checkpoints/2026-10-15b/taxonomy/research/verify/02-claim-lock.txt.

# Protocol fixes: checkpoint 2026-10-15b

F8 merged as symphony-protocol #35 (merge b4c3c1a, head a6465a5; main still at version 0.4.1, unreleased). This is the checkpoint section of #35's description, for the next session.

Done: F8 with three rounds of fixes, head a6465a5, merged on the owner's standing permission once CI was green (check, mutants, consumers, the four downstreams, CodeQL). Locally: `bash scripts/check.sh` 1,432 tests OK, `python3.12 -m validation.mutants` 109 of 109 caught, `scripts/validate.py deep --quick` green.

Open, found by the round-three review and not fixed (the owner stopped the work at 22:52 UTC on 2026-10-15). The list is in the order to take it, and none of it makes main worse than 0.4.1, where the committer date always decided:
1. A claim's first push can still be released in the run it starts. If both activity reads come before GitHub lists the branch's making, each answers an empty list, there is no floor, and a commit dated back reads as idle. The next step is a follow-up pull request. The run's event names the branch and the sha it pushed (`GITHUB_EVENT_NAME` push or create, `GITHUB_REF_NAME`, `GITHUB_SHA`; the template's board.yml runs on every push). cli passes that pair down through `snapshot`, `collect` and `releases` to `head_since`. There, where no read dates the push of that head, the head is dated no earlier than the run's start, for that run alone. Add the spec's sentence, the oracle's reading, a trace step and a mutant.
2. Harness gaps, which the library handles but no lane catches:
   - No fault lists two different older entries across the two reads, so a library that keeps the first read's floor, or the earlier one, slips. Add a catching-up fault: two pushes behind, then one behind.
   - No fault lists a fresh delete, so a library that ignores the spec's "or deleted it" slips.
   - `Fault.then` can fire before its head's times are spent when the two links' matchers differ (validation/fake_github.py, `fault_for`).
3. Wording:
   - The docstrings of board.Release, `Release.last_commit` and `released_keys` should say that pushed_at may hold a fresh entry or the floor.
   - The log line should drop the why when the second read is a 404, unless a floor was taken. It should not say "read twice" after a refused read, or "later than its committer date" when GitHub does not show the commit.
   - The model.py docstrings and validation/README.md's canary entries do not mention C6's new activity record yet.
   - mutants.py says "which the build at 286ba37 held", which is false for the case where both reads lag.
   - DESIGN.md, under What it leaves, says a refusal for good leaves the committer date alone, but a refused second read keeps the first read's floor.

Then, in the owner's order: the stuck claim (branch claude/owner-decisions-stuck-claim, WIP 917f5e3; merge main, then reconcile `landed_release` with F8's `github.newer` and `board.release_counts`; this pull request raises the version to 0.5.0). Then the template's follow-up (vendor main ahead of the release; docs/agents/PROTOCOL.md Release still says "by the committer date of its head"). Then the measurement pass. Then the two findings the coordinator passed on at 21:25 UTC (the push guard reads the session's directory, not `git -C`'s; a reopened issue keeps claimed and in-review and is listed nowhere; evidence in the project's research/taxonomy/verify/02-claim-lock.md). Then tell the owner 0.5.0 is ready. Never approve or publish a release.

The full review findings of round three, unverified where the review was stopped, are in protocol-fixes-2026-10-15b-review3-findings.txt beside this file; the list above is the verified and plainly real part.
