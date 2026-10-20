# The fixer's report on 1ea1786 (the first review's twelve findings)

All twelve findings are dealt with: eleven fixed, and finding 6 left alone (it goes to the template's follow-up: Budgeted counting its calls from the client's made). The fixes are one commit on top of bfae623. `bash scripts/check.sh` passed (1485 tests, up from 1476 at bfae623), and the full mutation lane caught all 118 mutants.

## Each finding and what changed
1. head_since asked again after the client's waits.
   - `may_answer_later` is now true only for no answer or a 5xx. Its docstring quotes GitHub's "may result in the banning of your integration".
   - `invariants.may_tell_more` follows: a non-200 answer may tell more only when it is a 5xx.
   - The head_since and releases docstrings are corrected: a rate limit's refusal has had the client's waits and is a refusal, after which the committer date stands in; a read is up to three calls.
   - head_since's test: a 429 on every try is now 3 reads with sleeps [60, 120] (it was 4 with a 3 s pause). Two cases are added: a 403 with `retry-after: 30` (3 reads, [30, 30]) and a primary-limit 403 whose reset is far off (1 read, no wait).
   - G2's row in GUARANTEES.md now says the same. spec/PROTOCOL.md is unchanged: it names no rate limit where it says "no answer that holds".
2. A 403 counted as a rate limit by its headers alone.
   - New `github.rate_limited(status, headers, detail)`: a 429, or a 403 with `retry-after` or a message naming a rate limit. `rate_wait` checks it first. A 429 keeps the remaining-0 rule.
   - `test_a_403_that_is_no_rate_limit_fails_at_once` adds the no-right 403 sent as the hour's last call (remaining 0, limit, reset) and a bare 403 with the same headers: one call, no wait, no "waited" in the run's line.
3. The longest wait.
   - `rate_wait` waits the longest of `retry-after` and the hour's end, where both apply, and still fails at once when that is over `RATE_LONGEST_WAIT`.
   - Tests: retry-after 10 and a reset in 100 s gives [101]; retry-after 90 and a reset in 30 s gives [90]; a 403 secondary with retry-after 10 and a reset in 200 s fails at once.
4. The harness counted each try as a call.
   - New `invariants.answered(calls)` folds a run of identical calls (same method, path, query and body), each before the last refused for a rate limit, at most `RATE_RETRIES + 1` long, into one call judged by its last try. `reads_failed` and `activity_reads` use it, and also `unsettling_reads`, `put_back_refused` and `names_not_freed` (which also skips a rename refused for a rate limit).
   - New faults `branches-429` and `pushes-429-for-the-run`.
5. No check of a write made twice.
   - New run check `invariants.written_once`: at most one claim-released comment per issue and one overlap comment per piece in one run; its violation reads "#N heard <kind> K times in one run", under G3 for a release comment and G7 for an overlap comment. It runs in `first_half_checks` and in the unsplit branch of `cycle_checks`.
   - New mutant "a 5xx retried as a rate limit". Mutant counts are now 118 in validation/README.md, DESIGN.md, GUARANTEES.md and the test's exact count.
6. Left for the template's follow-up.
7. No fault kept a write refused for the run: new faults `comment-limited-for-the-run` and `comment-limited-then-unread`; DESIGN.md's G15 row, its section 3.2 fault paragraph and its section 11 rate-limit bullet are corrected.
8. Header names in any case: `next_link` and `count_answer` read through `header()`; the header-case test covers the mixed-case limit headers and Link, link and LINK.
9. The run's line now ends "it waited for GitHub's rate limits N times, S s in all", using `many(n, "time")`.
10. Writes made again rest on an assumption, now called one in `GitHub.request`, the write-retry test, fake_github.py's docstring and DESIGN.md 3.2; C4 (a canary check) is named as what would settle it, and no canary code is added.
11. Style: `send()`'s docstring wrap; `rate_wait`'s docstring.
12. Rename refused for a rate limit: `explain_refusal` returns "" when `rate_limited` holds, so no "refused for good" comment or marker is written. New test `test_a_rename_refused_for_a_rate_limit_is_left_for_the_next_run_unsaid` expects waits [60, 120], three rename POSTs and no rules or comments calls.

## Where the fixer did something different from the brief, and why
- Spent hour with no reset: an answer with remaining 0, no reset and a `retry-after` now fails at once; bfae623 waited the `retry-after`. With the hour's end unsaid, the longest wait is unknown.
- A 403 with `retry-after` alone counts as a rate limit, whatever its message, since GitHub sends that header only with a rate limit's refusal.
- The harness has its own classifier, `invariants.rate_limited`, which reads the Fault rather than calling `github.rate_limited`, so a mutant of the library's classifier cannot blind the harness.
- The test for a rename refused for a rate limit patches in a fifth fault ("rename-limited") rather than adding it to `verbs.FAULTS`.
- Left unfixed: GUARANTEES.md line 11 and validation/README.md line 67 still say "the eight" faults on the push read, stale already at bfae623 (eleven pushes-* faults) and twelve now.
- Rendered strings: the run's line's suffix was `; it waited {S} s for GitHub's rate limits, after {N} refusal(s)` and is now `; it waited for GitHub's rate limits {N} time(s), {S} s in all`; a rename refused for a rate limit no longer posts the rename-refused comment, so the log line drops its "; said so on #N" there; harness only: the violation detail "#N heard <kind> K times in one run".
