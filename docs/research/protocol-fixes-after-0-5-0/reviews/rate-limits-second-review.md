# Second review of PR #40's fixes (symphony-protocol, 1ea17863edaad33455c4e994f84cbe779a6d1ce3)

Eleven of the first review's twelve findings are fixed, and the sixth is deferred as the PR body says. Five findings remain, all low. None weakens a protocol guarantee or makes the library misbehave:

- the harness's fold of the client's tries over-folds;
- DESIGN.md's record of F8 still describes the behaviour that finding 1 removed;
- six mutants of the new client code slip every lane;
- two assumptions are stated as GitHub's word, or more narrowly than they reach;
- some counts are stale and two phrases overstate.

`bash scripts/check.sh` at 1ea1786 under Python 3.12 passes: "Ran 1485 tests in 518.475s, OK (skipped=30)", then "checks ok". The full log is /tmp/claude-0/-home-user/aa1ce0d8-44a1-5fed-bc11-4ed7e9c45b72/scratchpad/retry-review2/check-1ea1786.log.

Probes and their saved outputs are under /tmp/claude-0/-home-user/aa1ce0d8-44a1-5fed-bc11-4ed7e9c45b72/scratchpad/retry-review2/ (probes/, out-*.txt, extra-mutants-*.log). Nothing was edited, committed or pushed in any checkout, and the review worktree (retry-review2-tree) has been removed.

## Findings, most severe first

### 1. `answered` folds the library's own re-read into the client's tries whenever the client made fewer than three

- Kind: test or mutant gap.
- Where: validation/invariants.py:141-166 (`answered`, `asked_again`). The PR body's sentence "`invariants.answered` folds the client's tries at one call into the one call the run acted on" has the same problem.
- Evidence: probes/probe_overfold.py undoes finding 1's fix by putting back bfae623's `may_answer_later`, then runs a due claim's board run under three faults (out-overfold.txt):
  ```
  pushes-429-for-the-run (the lane's own)        re-read after a rate limit   push tries [429, 429, 429, 200]; reads the harness counts {'claude/1': 2}; violations [Violation(guarantee='G2', ...)]
  push read refused, retry-after 150             re-read after a rate limit   push tries [403, 403]; reads the harness counts {'claude/1': 1}; violations []
  branches 429 twice, then a push read 429 once  re-read after a rate limit   push tries [429, 200]; reads the harness counts {'claude/1': 1}; violations []
  ```
  As built, the second and third cases make one try each (`[403]` and `[429]`), and there are no violations.
- Why it matters: `answered` folds a call into the one before it when the two are adjacent, identical, and the earlier one was refused for a rate limit. It does not ask whether the client waited. The client gives up early when GitHub asks for a wait over 120 s, or when the run's 180 s are spent. In those cases the library's own second read of the push is counted as one of the client's tries, so `pushes_read_again` (G2) cannot see finding 1's regression. Only `pushes-429-for-the-run` catches it, because its three tries fill CLIENT_TRIES. Every check that reads calls through `answered` (`reads_failed`, `unsettling_reads`, `put_back_refused`, `names_not_freed`, `activity_reads`) inherits the same blind spot.
- Smallest fix: record the client's waits in the fake. For example, validation/cycle.py `api_for` could pass `sleep=lambda seconds: fake.waits.append(len(fake.calls))`. Then fold a call into the one before only across a recorded wait. Also add a push-read fault the client does not wait out to verbs.FAULTS: a 403 with the secondary message and `retry_after="150"`. If neither is done, `answered`'s docstring and the PR text should at least say that the fold assumes the client used all its tries.

### 2. DESIGN.md's record of F8 still says a rate limit's refusal earns a second read of the push

- Kind: document (an unfixed part of finding 1).
- Where: validation/DESIGN.md:837.
- Evidence: the record reads "or that GitHub gives no answer that holds (a 5xx, a 429, a rate limit's 403, or none at all; github.may_answer_later), is made once more after a pause (github.read_push, PUSH_RETRY_SECONDS)". At 1ea1786, sdlc_protocol/adapters/github.py:925-934 is `return problem.status is None or problem.status >= 500`, with the docstring "a rate limit's 429 or 403 too, which the client has waited out already ... is its answer for the run".
- Why it matters: the finding's record is where a later session reads what head_since does, and it states bfae623's behaviour, which this commit removed. The fixer corrected head_since's and read_push's docstrings (github.py:848-860, 905-920), G2's row (GUARANTEES.md:16, "a 5xx or none"), verbs.py:132-138 and README.md:69, but not this record. It is the only stale mention left; I searched every .md and .py file for it.
- Smallest fix: replace the parenthesis with "(a 5xx or none at all; a rate limit's refusal, which the client has waited out, is a refusal like any other; github.may_answer_later)".

### 3. Six mutants of the new client code slip every lane; only unit tests hold them

- Kind: test or mutant gap.
- Where:
  - validation/mutants.py has no mutant of `rate_wait`, of `GitHub.wait_before_again`, of either clause of `rate_limited`, or of `explain_refusal`'s skip.
  - validation/verbs.py FAULTS has no rename refused for a rate limit. The unit test in tests/test_validation_invariants.py patches one in instead ("rename-limited").
- Evidence: extra-mutants-all.log, judged by mutants.py's own judge over all 23 catchers, with every baseline at 0:
  ```
  SLIPPED  X1 retry-after before the hour's end (70 s)
  SLIPPED  X2 rate_limited without retry-after (68 s)
  SLIPPED  X3 rate_limited without the message (66 s)
  SLIPPED  X6 the client never waits (66 s)
  SLIPPED  X7 no budget for the waits (67 s)
  SLIPPED  X8 explain_refusal without the skip (69 s)
  ```
  - The lane does catch X4 ("rate_limited for any 403", G2) and X5 (finding 1 undone, G2 under `pushes-429-for-the-run`).
  - The unit tests in test_github, test_validation_invariants and test_validation_fake_github catch every one (out-unit-under-mutants.txt): X1 fails 3 of 263, X2 1, X3 17, X6 36, X7 5, X8 2. X2 rests on the single test `test_a_403_that_names_its_wait_is_a_rate_limit_s`.
  - With `verbs.FAULTS["rename-limited"] = Fault("POST", "/branches/*/rename", 403, times=3, message=verbs.SECONDARY)` added to "a released claim under every fault" (out-rename-fault.txt): as built `{}`; X3 and X8 give `('G10', 'a rename said refused on #1 with none refused for good')`; X2 still slips.
- Why it matters: the lane is the project's proof that the checks bite, and the client's waiting is invisible to it. The fake's sleep records nothing, and no check reads the waits. This is a gap in what the lane proves, not a defect in the library.
- Smallest fix: add "rename-limited" to verbs.FAULTS, which kills X3 and X8 in the lane. For X1, X2, X6 and X7, either add a check over recorded waits (finding 1's fix provides the record) or add one sentence to validation/README.md's new section saying that tests/test_github.py's RateLimits alone holds the client's waits.

### 4. Two assumptions are stated as GitHub's word, or more narrowly than they reach

- Kind: document.

(a) "retry-after comes only with a rate limit" is stated as fact.
- Where: tests/test_github.py:677, "GitHub sends retry-after with a rate limit's refusal alone, so a 403 that carries one is waited out whatever its message says"; and validation/invariants.py:128-133, "as GitHub's documentation tells one ("Exceeding the rate limit"): a 429, or a 403 with a retry-after header or a message that names a rate limit".
- What GitHub's text says (github/docs content/rest/using-the-rest-api/rate-limits-for-the-rest-api.md):
  - line 110, for the primary limit: "a `403` or `429` response, and the `x-ratelimit-remaining` header will be `0`";
  - line 112, for a secondary limit: "a `403` or `429` response and an error message that indicates that you exceeded a secondary rate limit. If the `retry-after` response header is present ...".
  - It never says that retry-after comes only with a rate limit, or that a bare 429 is one.
- Why it matters: the clause is worth keeping, because it reads a secondary limit whose message does not use the words "rate limit". GitHub's older "abuse detection mechanism" wording was one; that is from memory and unchecked. But it is a choice, and it decides two things: a wait, and `explain_refusal`'s silence (github.py:202, 1640).
- Smallest fix: call it an assumption, in DESIGN.md 3.2's list and in the two docstrings.

(b) The write-retry assumption's consequences are stated as a duplicate comment only.
- Where: validation/DESIGN.md:205, "Were GitHub to write a call it refuses, a run that met the limit would post that comment twice".
- Why it matters: the client makes every write again (`GitHub.request` serves post, put, patch and delete), not just comments:
  - the clerk would open a task twice (sdlc_protocol/team.py:587 calls `client.create_issue`, which is `GitHub.post` of /issues, github.py:528);
  - the merge gate's PUT /pulls/N/merge (github.py:1803) would be asked again of a pull request that may already be merged.
  - `written_once` counts only release and overlap comments.
- Smallest fix: one sentence in that bullet naming these writes, or keep POST /issues and the merge's PUT out of the client's retries.

### 5. Stale counts and two overstated phrases

- Kind: document.
- "the eight faults" on the read of a claim's push is stale. There are twelve pushes-* faults now: pushes-403, pushes-429-for-the-run, pushes-500, pushes-500-then-lagging, pushes-500-then-moved, pushes-catching-up, pushes-deleted, pushes-lagging, pushes-lagging-then-500, pushes-lagging-twice, pushes-moved, pushes-moved-twice.
  - It appears at validation/GUARANTEES.md:11, validation/README.md:67 and validation/DESIGN.md:520. The fixer's report names the first two; DESIGN.md:520 is a third.
  - The comment at validation/deep.py:89-102 names eight of the faults. It leaves out pushes-429-for-the-run (new in this PR), pushes-catching-up, pushes-500-then-lagging and pushes-deleted.
- validation/README.md:93 says "invariants.written_once holds every run, a faulted one too". It does not hold a failed run:
  - `cycle_checks` returns before `written_once` when the run exited non-zero (invariants.py:401-404);
  - `first_half_checks` returns before it when the first half raised (368-369);
  - so a run that wrote a comment twice and then failed is never checked.
  - Fix: say "every run that ends", or run `written_once` before those returns, since it needs only `effects_of(calls)`.
- validation/GUARANTEES.md:16 (G2) says "a rate limit's refusal has had the client's waits by then", and so does the commit message. But the client makes no wait at all when GitHub asks for more than 120 s, or after the run has waited 180 s. out-rate-table.txt shows it: "429, remaining 0, reset +3000 ... tries=1 waits=[]". `may_answer_later`'s docstring has the right form: "as long as GitHub asks and a run waits".

## The first review's twelve findings, one line each

1. head_since asked again after the client's waits: fixed. `may_answer_later` is now none or a 5xx, and the tests and G2's row follow. DESIGN.md:837 still says otherwise (finding 2), and the harness's check of it is partial (finding 1).
2. A 403 counted as a rate limit by its headers alone: fixed (`rate_limited`). The no-right 403 sent as the hour's last call is now one call with no wait.
3. retry-after obeyed alone when the hour is spent: fixed. The client waits the longer of the two, and remaining 0 with no reset fails at once.
4. The harness counted each try as a call: fixed for the faults the lane runs (`answered`). It over-folds when the client gave up early (finding 1).
5. No check of a write made twice: fixed. `written_once` was added, and the new mutant dies for its stated reason. It does not run on a failed run (finding 5).
6. Budgeted undercounts the tries: deferred. The PR body says so, though it calls this "The twelfth" when it is the first review's sixth.
7. No fault kept a write refused for the run: fixed (`comment-limited-for-the-run`, `comment-limited-then-unread`), and DESIGN.md's three passages are corrected.
8. Header names in any case: fixed. `next_link` and `count_answer` read through `header()`, and the tests cover Link, link, LINK and mixed-case limit headers.
9. "after K refusal(s)" counted waits: fixed. The line now reads "it waited for GitHub's rate limits N times, S s in all".
10. The write-retry stated as fact: fixed. It is called an assumption in `request`, in the test, in fake_github and in DESIGN.md 3.2, with C4. Its reach is understated (finding 4b).
11. Style: fixed.
12. A rename refused for a rate limit was said to be refused for good: fixed. `explain_refusal` now skips it, and the test expects waits [60, 120], three POSTs and no rules or comments calls. The lane has no fault for it (finding 3).

## Checked and found right

- `rate_limited` and `rate_wait` against GitHub's words, over sixteen refusal shapes (out-rate-table.txt):
  - bare 429: [60, 120];
  - retry-after 30: [30, 30];
  - remaining 0 with reset +30: [31, 31];
  - remaining 0 with a far reset: one try;
  - remaining 0 with no reset, even with retry-after: one try;
  - 403 with the primary message: waited;
  - 403 with remaining 0 and no message, the no-right 403 and a ruleset 403: one try;
  - 422 and 503 with retry-after: one try;
  - secondary 403 with retry-after 10 and reset +100: [101].
- `may_answer_later`'s guarantees. Its one caller is `read_push` (github.py:918).
  - In the run its push started, a head is still dated at the run's start, whatever the reads answer.
  - A rate limit's refusal is a refusal, after which the committer date stands in, as the spec allows where "GitHub refuses to read it".
  - No read goes out where 4c5e3f2 made none.
  - The F20 path still leaves the labels and counts no release where the comment is refused and the comments are unreadable; `comment-limited-then-unread` now exercises it.
- `explain_refusal`'s silence on a rate limit's 403 matches the spec, which has the board speak only of a refusal for good. `names_not_freed`'s skip uses the harness's own classifier, which agrees with the library's on every fault the fake can send, so a mutant of the library's classifier cannot blind the harness.
- The four new faults are faithful:
  - SECONDARY is the opening of GitHub's secondary-limit message;
  - `times=3` covers every try;
  - waits of 60 s and 120 s spend the 180-s budget, so the read after them is not waited out.
- The new mutant "a 5xx retried as a rate limit" dies for its stated reason (out-mutant-reason.txt): none as built; with the mutant, `Violation(guarantee='G3', detail='#1 heard claim-released 2 times in one run')` under `comment-lost`.
- Rendered strings: the run's line's new suffix, the dropped "; said so on #N" for a rename refused for a rate limit, and the harness's new violation wording are each named in the PR body.
- One client serves a whole board run (cli.py:207), so the 180-s budget is per run. The shortest job that uses the client, workers.yml's dealing job at 5 minutes, still ends with GitHub's own words.
- The template's `Budgeted` (tools/metrics.py at origin/main bea11e3), item 7 (out-budgeted.txt):
  - A 403 for a spent hour that ends within two minutes is waited out and answered. Budgeted counts 1 of the 2 calls GitHub answered, which is the deferred finding 6.
  - A 403 whose hour ends far off is OutOfBudget at once, as before.
  - A 429 near its reset is waited out and answered; it used to be a GitHubError.
  - A 429 far from its reset is a GitHubError, as before, because Budgeted matches only a 403.
  - A secondary 403 on every try is a GitHubError after three calls and 180 s.
  - The client's extra tries pass Budgeted's reserve check, at most two calls per request.
  - SpentHour's tests are unchanged.
  - One theoretical case, not counted as a finding: a 403 that names the primary limit but carries no x-ratelimit headers is waited 60 s and 120 s and asked twice more before OutOfBudget, where 4c5e3f2 stopped at once. GitHub sends those headers on every REST answer.
- Style: ASCII, LF and a final newline everywhere; Python lines within 120 characters; names and docstrings read as English; no new dependency.

## The PR body (noted, not counted)

- "The twelfth, that `Budgeted`'s own count of calls leaves out the tries the client made again, goes to the template's follow-up": this is the first review's sixth finding.
- "`invariants.answered` folds the client's tries at one call into the one call the run acted on": it folds any adjacent identical call that follows a rate limit's refusal, the library's own included (finding 1).
