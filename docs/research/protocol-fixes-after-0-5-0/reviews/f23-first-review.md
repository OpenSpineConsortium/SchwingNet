# Adversarial review of symphony-protocol PR #41 (F23), head bd99ad5, base main 4c5e3f2

The verdict: the fix's core rule is right. A 4xx with no comment listed puts the labels back. A 5xx, no answer, a 3xx or a body that is not JSON with no comment listed leaves them off. A listed comment makes the release whole. F23.json, the mutants and the every-fault deep space bear this out. I found three real findings before merge (1 to 3), one older bug next to this fix that is not a regression (4), and some smaller document and harness points (5 to 7). Line numbers are at bd99ad5, which is the checkout /home/user/proto-f23. The scratch scripts below are under /tmp/claude-0/-home-user/aa1ce0d8-44a1-5fed-bc11-4ed7e9c45b72/scratchpad/f23-review/. Each one adds its extra fault or mutant in memory only. Run them from a checkout of bd99ad5 with PYTHONPATH set to that checkout, PYTHONDONTWRITEBYTECODE=1 and python3.12.

## Findings, most severe first

### 1. The spec no longer says what a run does when its label step fails

- **Kind:** document. A rule the library enforces has dropped out of the normative text.
- **Where:**
  - /home/user/proto-f23/spec/PROTOCOL.md:67 (Release)
  - /home/user/proto-f23/validation/oracle.py:89 (SPEC["put back"])
  - /home/user/proto-f23/validation/GUARANTEES.md:18 (G3L spec words)
  - /home/user/proto-f23/validation/DESIGN.md:879 (F15 cites SPEC["put back"])
  - /home/user/proto-f23/README.md:65
  - /home/user/proto-f23/sdlc_protocol/coordinator.py:21-28
  - /home/user/proto-f23/validation/invariants.py:503-507 (docstring)
- **Evidence:** main has one general sentence: "A run that fails between the two puts back the labels it took off and takes off the todo it put on, so the issue is as it was and the next run starts the release over, unless the comment is there after all, ...". The PR replaces it with three sentences:
  - "A run that fails between the two reads the issue's comments, and the comment there after all ... makes the release whole."
  - "Where they list none and GitHub refused the comment, with an answer from 400 to 499, ... the run puts back the labels ..."
  - The sentence for an unread re-read or a 5xx / no answer.

  None of the three covers a failure while taking a label off or putting todo on. The code still handles that case (github.py:1268-1272 and 1309-1321) and so does the harness (label-delete-500, label-post-500, label-post-lost; F15's mutants; labels_put_back). label_step_line.py shows it:

  ```
  label-post-500 | comment posts [] | ... | labels ['claimed', 'worker:a']
      #1: not released, putting todo on failed: POST /repos/o/r/issues/1/labels: HTTP 500: injected; claimed, worker:a put back
  label-post-lost | comment posts [] | ... | labels ['claimed', 'worker:a']
      #1: not released, putting todo on failed: ... HTTP 502: injected; claimed, worker:a put back; todo taken off again
  ```

  README and the coordinator docstring now make putting back conditional on "where GitHub refused the comment" and drop this case too.
- **Why it matters:** the spec is the protocol. The template's docs/agents/PROTOCOL.md takes its Release text at vendoring, so it would lose the rule as well. SPEC["put back"] and G3L's spec words now quote the 4xx-comment sentence. Meanwhile labels_put_back, and DESIGN's F15 entry ("The spec's Release paragraph says so ... (SPEC["order"], SPEC["put back"])"), hold the library to the label-step rule. So tests/test_validation_guarantees.py can no longer notice that the spec has lost it.
- **Smallest fix:** add one sentence before "reads the issue's comments". For example: "A run that fails at the labels, taking one off or putting todo on, puts back the labels it took off and takes off the todo it put on, one GitHub answered with an error among them, so the issue is as it was and the next run starts the release over." Make the next sentence "A run whose comment fails reads ...". Point SPEC["put back"] (or a new key) and G3L's words at the new sentence, and say the same in README.md:65 and coordinator.py.

### 2. After a 4xx, a refused re-read leaves the labels off, but nothing tests that, and README and the coordinator docstring say the opposite

- **Kind:** test and mutant gap, and document.
- **Where:**
  - /home/user/proto-f23/sdlc_protocol/adapters/github.py:1280-1284 (the case) and 1350-1358 (unsettled's line)
  - /home/user/proto-f23/validation/verbs.py:71-95 (no fault with a 4xx and then a refused read)
  - /home/user/proto-f23/validation/mutants.py:824-835 and 1202-1205 (F20's mutant remade)
  - /home/user/proto-f23/validation/DESIGN.md:931 ("which made the old mutant equivalent")
  - /home/user/proto-f23/README.md:65
  - /home/user/proto-f23/sdlc_protocol/coordinator.py:21-28
  - /home/user/proto-f23/spec/PROTOCOL.md:67
- **Evidence:** extra_mutants.py and the lane's own catchers give these results:

  ```
  SLIPPED  a refusal's refused re-read put back: no catcher of ['the regression traces', ... 'every label mix on one issue'] caught it (73.4 s)
  SLIPPED  F20's mutant as it was on main: no catcher of [... same 23 ...] caught it (66.1 s)
  ```

  The first mutant also passes all 352 unit tests of the touched modules. With a fault comment-422-then-unread added (refusal_then_unread.py):

  ```
  library: labels ['todo'] violations []
  library, next run: labels ['todo'] False []
  F20's mutant as it was on main : labels ['claimed', 'todo', 'worker:a'] [('G3L', '#1: the run could not tell whether its release comment stands and put the labels back')]
  a refusal's refused re-read put back : labels ['claimed', 'todo', 'worker:a'] [('G3L', '#1: the run could not tell whether its release comment stands and put the labels back')]
  ```

  README:65 says the run "puts back the labels it took off where GitHub refused the comment with a 4xx", and leaves them only "where it cannot tell whether GitHub wrote the comment anyway". After a 4xx it can tell, so README describes the mutant, not the library. coordinator.py:22-28 says the same. The spec gives "the run cannot tell whether the comment stands" as the reason for leaving them, which wrote_nothing's premise makes untrue after a 4xx. The real reason, that a release comment someone else wrote meanwhile may stand, is given only in DESIGN.md:932. The run's line says (refusal_line.py):

  ```
  #1: release unsettled, the comment failed: ... HTTP 422: Validation Failed; its issue's comments could not be read to see whether GitHub wrote it anyway: ... HTTP 500: injected; the labels stay as the release left them
  ```
- **Why it matters:** this case is the only guard for a release comment that someone else wrote meanwhile, and for a write GitHub refused for a rate limit and made anyway (finding 3). A change that made the code match README would pass every check. DESIGN's claim that the one-rule F20 mutant became equivalent is untrue: it differs exactly here. Remaking it with two rules hid that it differs.
- **Smallest fix:**
  - Add `"comment-422-then-unread": Fault("POST", "/issues/*/comments", 422, message="Validation Failed", then=Fault("GET", "/issues/*/comments", 500))` to verbs.FAULTS and to AReleaseThatCannotReadItsComment.FAULTS, and add a Coordinate test in tests/test_github.py.
  - Keep F20's mutant as one rule (github.landed_release -> landed_release_finding_none_unread). The new fault catches it.
  - Make README.md:65 and coordinator.py:22-28 say the labels go back after a 4xx only where the comments, read after it, list none.
  - Give the reason that holds after a 4xx in the spec and in unsettled()'s line.
  - PR #40's comment-limited-then-unread (/home/user/proto-retry/validation/verbs.py:93-98) is this same case for a rate limit. Until both PRs land, nothing tests it.

### 3. The 4xx rule silently assumes PR #40's unverified C4: GitHub never makes a write it refuses for a rate limit

- **Kind:** weakened guarantee (conditional), and document.
- **Where:**
  - /home/user/proto-f23/sdlc_protocol/adapters/github.py:1395-1401 (wrote_nothing)
  - /home/user/proto-f23/spec/PROTOCOL.md:67 ("which GitHub gives in place of writing anything")
  - /home/user/proto-f23/validation/DESIGN.md:932 ("after a refusal, a 4xx, GitHub wrote nothing")
  - /home/user/proto-f23/validation/fake_github.py:31-34 (the assumptions list covers only a 5xx or no answer)
  - The commit message: "a refusal that reaches the release after a client's retries is a 4xx like any other"
- **Evidence:** PR #40's DESIGN (/home/user/proto-retry/validation/DESIGN.md:205) says: "A call GitHub refuses for a rate limit is one it did not act on: assumed. GitHub's documentation says ... nothing of whether a refused call took effect ... C4 would settle it ... and is not run". rate_limit_late.py makes a 403 secondary-rate-limit refusal that GitHub wrote, with the re-read LISTED_LATE:

  ```
  board ... ('comment-limited-late',) labels ['claimed', 'todo', 'worker:a'] claude/1 kept: True release comments: 1 [('G3L', '#1: the release comment stands and its labels were put back')]
  board ...                           labels ['claimed', 'todo', 'worker:a'] claude/1 kept: True release comments: 1 []
  (48 h later)                        labels ['claimed', 'todo', 'worker:a'] claude/1 kept: True release comments: 1 []
  ```
- **Why it matters:** if C4 is false, F23's own failure (a claim held for good) comes back for every 403 or 429 rate-limit refusal that outlasts #40's retries. The spec, DESIGN and the commit state as GitHub's behaviour something #40 records as unverified.
- **Smallest fix:** either say so, naming C4 beside the 4xx sentence, in wrote_nothing's docstring and in the fake's assumptions; or read a rate-limit refusal (429, or a 403 whose words name a rate limit) as may-have-written. The second costs one run and needs no assumption. #40's comment-limited-for-the-run text would then change with it.

### 4. Not a regression: a label removal GitHub made but answered with an error is not put back

- **Kind:** wrong rule. It predates this PR and is in the same family as F15 and F23.
- **Where:** /home/user/proto-f23/sdlc_protocol/adapters/github.py:1268-1272. The first except puts back only taken_off. take_label_off (1295-1306) raises on anything but a 404.
- **Evidence:** label_delete_lost.py, with the faults added in memory:

  ```
  label-delete-lost | board ... ('label-delete-lost',) | labels ['todo', 'worker:a'] | claude/1 kept: True | [('G3L', '#1: the release failed and its labels were not put back')]
  label-delete-lost | board ...                         | labels ['todo'] | claude/1 kept: False | []
  label-delete-unanswered | ... | labels ['todo', 'worker:a'] | claude/1 kept: True | [('G3L', '#1: the release failed and its labels were not put back')]
  ```

  label_delete_lost_main.py gives the same G3L on main 4c5e3f2.
- **Why it matters:** wrote_nothing's own premise (a 5xx or no answer may come after GitHub made the write) and F15's rule (a todo whose putting on failed is taken off again) both apply to the DELETE. Until the next run the issue has no claimed label while the claim is held, and a holder who pushes in between keeps it that way. The next run heals it, so this should not block F23.
- **Smallest fix:** also put back the label whose removal failed, unless wrote_nothing(problem). Putting on a label that is still there changes nothing. Add label-delete-lost to verbs.FAULTS, or record this as a new finding.

### 5. Smaller document points

- **Kind:** document.
- /home/user/proto-f23/validation/DESIGN.md:923: F20's Evidence still describes "an unsettled release put back" as "(landed_release as before the fix)".
- DESIGN.md:931 calls release_one_as_before_f20 "a copy of release_one". It is actually a wrapper that patches two attributes around ORIGINAL_RELEASE_ONE (mutants.py:824-835). mutants.py:4-6 says a mutant "changes one rule ... by patching one attribute", which this one does not.
- spec:67 names only a 4xx, a server error and no answer. wrote_nothing also leaves the labels after a 3xx (urllib raises HTTPError for a 307 or 308 on a POST) and after a 2xx whose body is not JSON (status None); DESIGN covers only the second. This is the safe direction; adding "or any other answer" would make the spec complete.
- DESIGN.md:934 (F23, What it leaves) says the board lists the claim as held between the runs. That is not so for a kept head, which the same run frees, as the Evidence entry and labels_left say.
- F23 widens F20's labels-off window to any single 5xx or timeout on the comment. A holder who pushes in that window keeps a claim whose issue has todo and no claimed or worker label until Finish, against Announce's "the labels name the holder alone". DESIGN says so; the spec says only that the push keeps the claim.
- DESIGN.md:9 says "no finding is open since F23's", and F23 takes the table rows after F20 (lines 51 and 432) and the place in section 13. F21 and F22, open in /home/user/proto-f21 and /home/user/proto-f22, take the same places. Whichever lands later must reconcile.

### 6. Harness: may_tell_more compares a status that may now be None

- **Kind:** harness.
- **Where:** /home/user/proto-f23/validation/invariants.py:1025: `return call.status >= 500 or call.status == 429 or (...)`
- **Evidence:** F23 makes a None status possible (a Fault with status None), and DESIGN.md:929 says "a call's status may be None, which the checks read as a failure (invariants.failed)". Here a None raises TypeError. Only an activity fault with no status reaches this line, and none exists yet. The library itself is safe: its only ordered status comparisons, github.py:806 and 1401, guard against None.
- **Smallest fix:** `call.status is None or call.status >= 500 or ...`.

### 7. Follow-ups outside this PR

- **Kind:** document.
- symphony-template, origin/main af8ec60:
  - docs/agents/PROTOCOL.md:49 still holds the old clause; DESIGN's "For the template" covers this. If finding 1 is not fixed first, the copy loses the label-step rule too.
  - CLAUDE.md:77, a durable decision, says "the labels put back when the comment fails, so a failed run is retried; symphony-protocol 0.4.1". That has been untrue since F20 and is more so after F23. It sits in the cswap block, so it should be corrected by a tagged Decision: line at that vendoring, not edited by hand.
- PR #40 (/home/user/proto-retry, 1ea1786):
  - validation/verbs.py:85-91 says comment-limited-for-the-run fails "as comment-500's is, so a release whose comment it is puts its labels back". Its new test's docstring says "fails as under comment-500, its labels go back". After F23 a 500 leaves the labels off.
  - Both PRs rewrite TheFixesOf041Hold.test_a_refused_release_comment_puts_the_labels_back and invariants.py. Whichever lands second should re-check release_rereads (it keeps the last failed post before the re-read) against #40's answered().

## Checked and found right

- F23.json is red on main at steps 16, 18 and 20 (25 mismatches) and green on bd99ad5.
- F23's three mutants die at steps 16, 18 and 22 for G3L. The remade F20 mutant is red at F20's steps 8 and 10.
- Mutants I added were caught: "a 500 taken for a refusal", "an unlisted release counted" and "labels_left not shown on the snapshot" by the lane, and "the re-read skipped after a refusal" by tests/test_github.py's call sequence.
- With no mutant, no catcher in the lane reports a violation.
- The E-faults deep space over every fault, F23's three new ones included, finished: 41,020 states, 163,845 transitions, 284 s, not stopped, no violation.
- Every answer to the comment's POST ends where the code means it to:
  - a 2xx makes the release whole;
  - a 401, 403, 404, 410, 422 or rate-limit refusal puts the labels back when no comment is listed;
  - a 5xx, timeout, reset, non-JSON body or unsent call leaves them, and so does a 3xx (a 307 or 308 raises on a POST);
  - a listed comment makes the release whole.
- After the labels are left off, the next run settles it in every case:
  - it counts the listed comment, or releases again (two comments only when the listing lag spans runs, as documented);
  - a holder's push keeps the claim;
  - a person putting claimed back undoes the release;
  - a kept head is freed in the same run by its earlier release.

  No path holds a claim for good, renames a branch twice, or frees a claim whose holder pushed.
- Board and clerk: not_listed goes through labels_left and after_labels exactly as F20's unsettled does. The page lists the claim as held, nothing is renamed, and the clerk still sends the holder to its claim.
- The fake:
  - a status-None Fault raises http.client's timeout, so the adapter reads it as no answer;
  - LISTED_LATE hides only that run's lost writes, on one read, and the next run's FakeGitHub lists them;
  - applied writes are recorded per run.
- The trace moves keep their meaning as a refusal: F15 step 6, F8 step 29 (hour 101), and three mutants' shortest traces, all moved from comment-500 to comment-422.
- Rendered strings:
  - the new not_listed line is said in the PR;
  - F20's unsettled line is unchanged;
  - the put-back line now follows only a 4xx;
  - no consumer test pins any of them (template grep; CI's downstream jobs green).
- Style and checks:
  - every changed file is ASCII with LF and a final newline;
  - 304 tests of the touched modules pass;
  - the 21 regression traces replay in 0.33 s;
  - CI's check and downstream jobs are green;
  - no gate file is changed and the version stays 0.5.0.
