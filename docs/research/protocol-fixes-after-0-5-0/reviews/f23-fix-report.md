# The fixer's report on bd99ad5 (F23)

F23 is fixed in one commit, bd99ad5 ("F23: a release comment GitHub may have written leaves the labels for the next run"), on claude/owner-decisions-f23-late-comment, parent 4c5e3f2 (main). 23 files changed, 821 insertions, 256 deletions.

The fix: `github.wrote_nothing(problem)` is true only for a status from 400 to 499. In `release_one`, when the re-read after a failed post lists none: after a 4xx, the labels go back, as before; after a 5xx or no answer, the new `not_listed` leaves the labels as the release left them and counts no release. It works like F20's `unsettled`; both now go through the new `labels_left`.

Red on main, then green: validation/traces/F23.json against the unfixed library: "red: step 16 G3L, step 18 G3L, step 20 G3L; mismatches: 25". Step 16 is "#1: the release comment stands and its labels were put back": a 502 after the write, and the re-read lists none. Step 18 is the same failure for #2, where the post got no answer at all. Step 20 is "the run could not tell whether its release comment stands and put the labels back" (a 500 that wrote nothing). claude/1 stayed held to the end of the trace, at hour 28. With the fix: "red: none; mismatches: 0". The runs at 25, 26 and 27 h leave the labels off, and the next run settles each. The run at 28 h gets a 422 and puts d's labels back. The new test_github tests also fail against main's github.py.

Mutants (120 now, bound widened to 130), each credited to the regression traces and also caught in tests/test_validation_invariants.py under its fault, for G3L alone:
- "a late comment's labels put back" (`wrote_nothing` always true, the old rule): F23.json step 16.
- "no answer taken for a refusal" (no answer read as a 4xx): step 18.
- "a refusal taken for a late comment" (`wrote_nothing` always false): step 22.
- F20's "an unsettled release put back" is remade as `release_one_as_before_f20`, which patches in both old rules, since the fix made the old mutant equivalent under F20's two faults, which are both 5xx. It is still red at F20.json steps 8 and 10.

Rendered strings: a new line `#<n>: release unsettled, the comment failed: <why>; its issue's comments list none yet, though GitHub may have written it before that failure and list it only later; the labels stay as the release left them`; `#<n>: not released, the comment failed: <why>; <labels> put back` now follows only a 4xx. F20's unsettled line is unchanged. The spec's Release paragraph is reworded.

Check: `bash scripts/check.sh` passed, 1471 tests OK (30 skipped, test_parity's template tests), on Python 3.13 and 3.12.

Choices the brief left open:
1. The re-read after a 4xx is kept, so a refused re-read is still unsettled, and a newer release comment still makes the release whole.
2. "No status" covers more than a timeout: http.client errors, an answer that was not JSON (which comes after GitHub acted) and a call never sent (met only at a run's first call). All of these leave the labels off; DESIGN.md says so. A 3xx is also not a 4xx, so it leaves them off too.
3. A `comment-422` fault was added, because #40's retry turns `comment-rate-limited` into a whole release. Where traces meant "GitHub refused", they moved from `comment-500` to `comment-422`: F8.json at step 101, F15.json at step 25, the shortest traces of three mutants in tests/test_validation_mutants.py. The invariants test makes no label assertion for `comment-rate-limited`, so it holds whether or not #40 lands.
4. `unsettled` keeps its signature, with `not_listed` and `labels_left` beside it, so the F20 mutants that patch `unsettled` still change one rule each.
5. The fake's `LISTED_LATE` answer hides only the comments lost in that run (`FakeGitHub.lost`), on one read.
6. The version stays 0.5.0, and known.json records F23 as fixed after "0.5.0". The canary tests now use `EVERY_FIX = "0.5.1"` for a copy with every fix.
7. `replay.FINDINGS` is F1 to F20 plus F23, since F21 and F22 are other pull requests'. GUARANTEES.md's stale "109 mutants" is corrected to 120.

Merge notes: when F21 (#39), F22 or #40 land, these conflict and need the counts reconciled: `FINDINGS`, test_validation_traces' `FIXED` and `UNDONE`, known.json, the mutant count and its bound, and the trace count in validation/README.md ("twenty-one"). The template's docs/agents/PROTOCOL.md needs the new Release clause when it vendors the release after 0.5.0.
