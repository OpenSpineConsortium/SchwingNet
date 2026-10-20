# The adversarial review of coordbench#14 (commits 387ac4f and 187efd6), cut at 2026-10-14 14:50 UTC

Item 2 of the handoff of 2026-10-14c (docs/checkpoints/2026-10-14c/handoff.md):
review coordbench#14's last two commits, fold in what is real, merge #14,
#15 and #16, dispatch the fake run over the fixed list, update
docs/checkpoints/2026-10-14/cooperbench-run.md, stop short of the real run.
The thread stopped on the owner's word at 94% session usage, after the
review's finders had all reported and its refuters had judged two of the
twenty-one findings. Nothing was folded in, nothing merged in coordbench,
nothing dispatched; the "Checkpoint 2026-10-14d" section at the top of
coordbench#14's description is the state and names the next steps. This
note keeps the review's output, which would otherwise be lost with the
session: the finders' text as the workflow's journal recorded it, folded to
ASCII, and the refuters' votes that finished.

## Where it stands

- symphony-template#79 (the 2026-10-14c review notes) merged at 13:58 UTC
  as 54c4f75, on the handoff's instruction.
- coordbench#14, head 187efd6, draft, every check green (13:21 UTC), check.sh
  green locally at 187efd6 (1058 tests, 18 skipped). Not merged: the review
  below stands between it and ready.
- coordbench#15 (head 0a4f965) and #16 (head 64bcaf5): untouched, drafts,
  green. A trial merge (git merge-tree) shows #15 conflicts with #14 in
  bench/cooperbench/PLAN.md only; #16 merges clean onto #14. Both repositories'
  rulesets (coordbench 24827945, symphony-template 24827932) require the
  check "check" on a head up to date with main (strict), a pull request, and
  allow merge commits; so after #14 merges, each of #15 and #16 needs
  origin/main merged in and pushed before its check counts.
- The fake dispatch (tag fake-1) was not started.

## What the review was

The Workflow tool ran seven finders over `git diff 5390686 187efd6` at the
checkout of 187efd6, one per dimension (run-py, artifacts-plan,
workflow-shell, fake-and-drivers, tests, documents, scrub-security), each
told to report only defects confirmed by reading the code path end to end
or by running a command; then three refuters per finding with different
lenses (correctness, reproduction, intent), a finding standing when fewer
than half refuted it. All seven finders finished: 21 findings (7 of them
marked real, 14 minor by their finders), several the same defect seen
from different dimensions. The refuters finished for artifacts-plan-1
(stands, 3 of 3 could not refute, real) and artifacts-plan-2 (stands, 3 of
3, minor); those for run-py-1 were running when the workflow was killed.
Every other finding is a finder's claim with no second reader.

## The findings, grouped (the next session verifies each before acting)

1. A pair whose eval.json holds an error is never rescored (artifacts-plan-1,
   workflow-shell-1, scrub-security-2; real; the one group with refuter
   votes, 3 of 3 standing): artifacts.py pair_state calls such a pair
   "unscored" (finished exits 3, the job fetches it into logs/<run name>),
   but run.py run_one skips a finished directory whenever eval.json exists,
   error or not, so the attempt is moved in, "skipped", never scored,
   check-dir still says unscored, no marker is uploaded, and every later
   dispatch of the tag repeats the fetch. Fix proposed: in run.py run_one
   (and needs_scoring) treat eval.json as present only when it is a dict
   with no error, matching PLAN.md's "scoring failed ... is scored again";
   a test in tests/test_coordbench_run.py with an errored eval.json.
2. A timed-out pair, now kept, gets no __done marker and its job is red
   (workflow-shell-2, fake-and-drivers-1, scrub-security-1; real;
   unverified): run.py still exits 1 when an agent is in Error, timed out
   included, pair.sh passes the status on, the composite's "Run the pair"
   step fails, and the "Say whether the pair is finished" step (if:
   steps.scrub.outputs.publish == 'true', no status function) is skipped,
   so the finished pair is planned again by every dispatch (finished then
   skips it, costing a job, not usage) and the run shows red. Fix proposed:
   run.py's exit status reads agent_failed rather than status == Error,
   or the done step's condition gains !cancelled(); a test either way.
3. The pack scrub (run-py-1, run-py-3, tests-1; real; unverified):
   pack_contents yields each object's inflated bytes, so a credential
   inserted in a delta object whose insert run exceeds 127 bytes is split
   by an opcode byte and not seen; and it hands the whole remainder of the
   pack to the decompressor per object (unused_data copies), quadratic in
   the pack's size, which the three-object test pack cannot show. Fix
   proposed: parse delta instructions and search the inserted bytes joined;
   feed the decompressor in chunks; a test with a delta object and one with
   many objects timed.
4. record_failure on a full disk skips the teardown (run-py-2; real;
   unverified): when the plan's write failed on ENOSPC, record_failure's
   own write of result.json raises before teardown runs, leaving the
   containers up and no record. Fix proposed: tear down in a finally, or
   write the record after the teardown.
5. Documents (documents-1 to documents-5): PLAN.md's Resume and Primary
   outcome say "the newest finished attempt, else the newest" while
   artifacts.py now chooses newest finished, else newest unscored, else
   newest (real: a pre-registration that does not match the code); the
   kit README costs pairs.txt at 50 pairs where #14's tree holds 43 (#15
   makes it 50) and gives the pilot two totals (54 sessions / $23 and 42
   sessions / $18); the queue rule points at a list that does not show
   the tag; PARITY row 23's status "equivalent but for the time limit" is
   outside the file's legend; bench.yml's header says "a few pairs" where
   the check runs one pair under three arms.
6. Minor code findings: the listing is reported cut at exactly 5000
   artifacts when nothing was cut (artifacts-plan-2, 3 of 3 standing);
   free_disk.sh's guard reads GITHUB_ACTIONS, true on a self-hosted runner
   too; fake_claude's json_text leaves tabs and carriage returns in a JSON
   string; a symlink under the run directory is published by its target's
   content while the scrub never reads the target; the post-start failure
   path scrubs without waiting for the drivers' threads.
7. Test gaps (tests-2 to tests-7): the fake-tag test cannot tell the
   refusal comes before the listing; report.sh's arm-from-download code
   has no test with a dashed arm; the FakeAgent tests are not isolated from
   a user-level ignore file; no test drives a timed-out CLI agent through
   result.json to pair_finished and the score.

## Next steps, in order (from coordbench#14's Checkpoint 2026-10-14d)

1. Verify groups 1 to 4 against the code (a refuter's reading each), fix
   the real ones with a test each, correct PLAN.md's attempt rule and the
   README's pilot cost, bash scripts/check.sh, push to
   claude/coordbench-12-review-v7l66b (no --force), wait for every check,
   mark #14 ready, merge with a merge commit.
2. #15: merge origin/main into claude/coordbench-12-review-v7l66b-pairs
   (PLAN.md conflicts), check.sh, push, wait for check, mark ready, merge
   with a merge commit. #16 the same (origin/main merged in for the strict
   rule), then merge.
3. Dispatch Bench on main: mode fake, pairs @bench/cooperbench/pairs.txt,
   tag fake-1, survey_tag survey-1; read the report in the report job's
   log; expect every pair Submitted, 0 Errors.
4. Update docs/checkpoints/2026-10-14/cooperbench-run.md by pull request
   (the notes in docs/checkpoints/2026-10-14c/notes/coordbench-review.md
   and this file).
5. Stop short of the real run (the owner's items, handoff part 7).

## The finders' text and the refuters' votes, as recorded

FINDERS DONE: ['artifacts-plan', 'documents', 'fake-and-drivers', 'run-py', 'scrub-security', 'tests', 'workflow-shell']

## artifacts-plan: 2 findings
- artifacts-plan-1 [real] bench/cooperbench/actions/artifacts.py:155: An unscored pair whose eval.json holds an error is fetched for a rescore that run.py never performs, every dispatch
    claim: artifacts.py pair_state calls a pair "unscored" when its agents did not fail and eval.json is missing OR has an error (line 154-155), so `finished` exits 3 and the job fetches the attempt and moves it into logs/<run name> for run.py to score. But coordbench/run.py run_one (line 2522-2527) only rescores a finished directory when eval.json does not exist: `if (finished / "eval.json").exists(): return "skipped"`. An attempt with an errored eval.json is therefore moved in, reported "skipped" with eval_skipped, never scored, check-dir still says "unscored" so no __done marker is uploaded, and the next dispatch of the tag plans the item again and repeats the same fetch/skip/upload. PLAN.md (Resume
    fix: Make the two rules one. Either (a) in run.py run_one, skip only when eval.json is a dict with no error (`evaluation = read_json(finished / "eval.json"); if isinstance(evaluation, dict) and not evaluation.get("error"): return "skipped", ...`) and do the same in needs_scoring, which matches PLAN.md's promise; or (b) in artifacts.py pair_state return "unscored" only when `not isinstance(evaluation, dict)` and fix PLAN.md's "scoring failed" wording. Test for (a): in tests/test_coordbench_run.py, a r
- artifacts-plan-2 [minor] bench/cooperbench/actions/artifacts.py:93: The listing is reported as cut at exactly 5000 artifacts, when nothing was cut
    claim: list_artifacts returns cut=True whenever the fiftieth page is full, which is also the case when the repository holds exactly PAGE*MOST_PAGES (5000) artifacts and nothing lies beyond it. The plan's notes then say a finished item older than that may be planned again, the download prints a warning line into the report's "Artifacts left out" section, and list-finished writes to stderr, all for a cut that did not happen. At 5001 the cut is detected correctly; 4999 correctly says not cut. The API's total_count would settle it.
    fix: Read `answer.get("total_count")` on the first page and return `cut = total_count > PAGE * MOST_PAGES` (falling back to the current rule when it is absent), or after the loop fetch page MOST_PAGES+1 with per_page=1 and report cut only when it is non-empty. Test: extend test_a_listing_cut_short_is_said with a FakeGitHub of exactly PAGE*MOST_PAGES artifacts (its listing can serve total_count) and assert cut is False, and keep the +1 case asserting True.
  notes: Checked and found sound: (1) finished, fetch and download all choose through chosen_state(artifact_states(by_name(...)[name])), so they agree on the newest finished, else newest unscored, else newest, with each attempt's zip fetched once and its bytes reused (confirmed by the test counting 9 blob fetches for three attempts across three commands); by_name sorts by created_at descending with a stable sort, so artifacts sharing a timestamp keep GitHub's listing order, and names are grouped exactly so a shared name is the grouping itself. (2) pair_state reads TIMED_OUT as run.py's agent_failed doe

## run-py: 4 findings
- run-py-1 [real] coordbench/run.py:791: A credential inside a git delta object escapes the pack scrub when its insert run is longer than 127 bytes
    claim: pack_contents yields each object's raw inflated bytes, and for a delta object (kind 6 or 7) those are delta instructions, not file content. Git emits inserted data in chunks of at most 127 bytes, each behind a one-byte opcode, so a token whose inserted run (the line it sits on) is longer than 127 bytes is cut in two by an opcode byte and the plain substring search in git_object_holds does not find it. The docstring's claim "a value added whole to a file is seen" is not kept; unscrubbed returns nothing, command_scrub exits 0, and the run directory is published with the token recoverable by git show.
    fix: In git_object_holds (or pack_contents) treat kinds 6 and 7 specially: skip the delta's two size varints, walk the instructions, and search the concatenation of all insert payloads (adjacent inserts are adjacent in the target, so a split token rejoins); or, more conservatively, treat any pack holding a delta object as "could not be read" so the pair is not published. Test: build the pack with git as above (or hand-write a REF_DELTA object with `insert 127` + `insert N` carrying the token across t
- run-py-2 [real] coordbench/run.py:1961: record_failure on a full disk skips the teardown, leaving the started agents' containers up and no record written
    claim: The commit says a failure after the agents started (the plan's write on a full disk) tears them down and records the error. The new except in prepare_pair calls record_failure, whose try runs close_run, write_outputs, teardown, conclude, save_plan in that order with only scrub_pair in the finally. When write_outputs raises (the same ENOSPC that made save_plan fail, since result.json, patches, metrics.json and events.jsonl go to the same disk), teardown never runs: the containers, volume and git repo stay, the agents keep running under their 2-hour timeout, no result.json exists, and the OSError (not PairFailed) propagates out of prepare_pair, so run_pair's `except PairFailed` does not catch 
    fix: In record_failure, run teardown(plan) before, or in a finally alongside, the writes: e.g. `try: metrics, events, artifacts = close_run(...) finally: teardown(plan)` and then attempt write_outputs/conclude/save_plan, with scrub_pair last; and have prepare_pair's handler still raise PairFailed when record_failure itself raises. Test: patch write_outputs to raise OSError and assert docker `rm -f` ran and the pair's verdict is "error".
- run-py-3 [real] coordbench/run.py:815: pack_contents copies the rest of the pack per object, so reading a pack is quadratic in its size
    claim: Each iteration calls inflater.decompress(view[offset:]) on the whole remainder of the pack; CPython stores the bytes after the stream's end in unused_data as a fresh bytes copy, so a pack of N objects and S bytes copies about N*S/2 bytes. The scrub's read-back therefore takes minutes on a packed clone of a modest repository and hours on a large one, inside a job with a fixed timeout-minutes and after the agents' usage has already been spent.
    fix: Feed the decompressor bounded slices: loop `chunk = view[offset:offset+65536]; content += inflater.decompress(chunk); offset += len(chunk) - len(inflater.unused_data)` until inflater.eof (raising when the pack ends first). unused_data is then at most one chunk. Test: time pack_contents on a generated pack of 20k small objects and assert it stays under a second, or assert via a counting wrapper that no decompress call receives more than the chunk size.
- run-py-4 [minor] coordbench/run.py:1782: The post-start failure path scrubs the pair without waiting for the drivers' threads
    claim: When save_plan fails after start_agents, the new handler calls record_failure, which tears the containers down and scrubs, but never joins the CliRun threads that own the agents' stream files; finish_pair's own failure path calls settle(handles) before the scrub for exactly this reason (its docstring: "a file rewritten while a thread still writes it would keep its tail"). The handles are in scope in prepare_pair but are not passed on.
    fix: Keep `handles = {}` before the try, and in the except call settle(handles) between teardown and the scrub (e.g. pass handles to record_failure, or settle in prepare_pair before raising and have record_failure's scrub run after). Test: a FakeDriver whose start returns a handle with a thread that writes the credential after a short sleep, and assert the stream file is clean after the failure.
  notes: Checked and found sound: TIMED_OUT in drivers.py is the exact prefix CliRun.run writes on subprocess.TimeoutExpired, and CliRun.outcome copies self.problem into both error and end_reason, so agent_ran_out_of_time matches it; agent_failed/pair_finished and artifacts.py agent_failed/pair_state apply the identical rule (status == \"Error\" and end_reason not starting with the prefix), so a pair with one agent timed out and one in Error for another cause is unfinished in both and reruns, as the commit says; the top-level result error is still a rerun in both; end_reason is written into result.json

## workflow-shell: 3 findings
- workflow-shell-1 [real] bench/cooperbench/actions/pair.sh:35: A pair whose eval.json holds an error is fetched for rescoring on every dispatch but never scored
    claim: artifacts.py calls a pair "unscored" (exit 3, fetch and rescore) when its eval.json exists but carries an error (pair_state, lines 154-155), yet run.py's run_one returns "skipped" without scoring whenever eval.json exists at all (run.py 2523-2527). The rescore path this PR made reachable (fetch beside the clone, pair.sh moves the files into logs/$RUN_NAME after setup.sh) therefore re-uploads such a pair unchanged, with no marker, and the next dispatch plans it, fetches it and skips it again, forever: never scored, never run again, contrary to the workflow comment and PLAN.md's "scored again from the files its artifact holds".
    fix: Make the two rules agree: in run.py run_one, treat an eval.json whose "error" is set like a missing one (evaluation = read_json(finished / "eval.json"); if evaluation is None or evaluation.get("error"): return verdict({}, score(plan)), ...), or, in pair.sh after the mv, delete any eval.json under the moved directory whose "error" is non-null before run.py runs. Test: unpack an artifact whose eval.json holds {"error": "docker died"} into the logs, run `run.py run` with the fake scorer, and assert
- workflow-shell-2 [real] bench/cooperbench/actions/run-pair/action.yml:147: A kept timed-out pair gets no __done marker: run.py exits 1, so the composite's done step is skipped
    claim: The PR keeps a pair whose agent ran out its time (pair_finished, check-dir say finished), but run.py's verdict still returns "error" for any agent with status Error (run.py 1969-1972), so command_run exits 1 and pair.sh exits 1 (pair.sh 54), failing the "Run the pair" step. The "Say whether the pair is finished" step's condition `steps.scrub.outputs.publish == 'true'` names no status function, so GitHub evaluates it as success() && (...), and success() is false after a failed step of the composite action; the step is skipped, steps.done.outputs.finished is empty, and the job's marker upload (`steps.pair.outputs.finished == 'true'`) never runs. Without the marker, plan.py plans the pair on ev
    fix: Give the done step the same guard as the scrub step: `if: ${{ !cancelled() && steps.scrub.outputs.publish == 'true' }}` (it already runs only when publish is true, which the scrub step sets only on success). Alternatively make run.py's verdict not call a kept pair an error (use agent_failed instead of status == "Error"), so pair.sh exits 0 and the job is not red for a pair the kit keeps. Test: in tests/test_experiment_actions.py's Workflow class assert the done step's `if` carries `!cancelled()`
- workflow-shell-3 [minor] bench/cooperbench/actions/free_disk.sh:8: free_disk.sh's guard reads GITHUB_ACTIONS, which is also true on a self-hosted runner
    claim: The commit says free_disk.sh "runs only on a hosted runner" and the script's own message says it "is for a GitHub-hosted runner", but the check `[ "${GITHUB_ACTIONS:-}" != true ]` passes on every GitHub Actions runner, self-hosted ones included (GitHub sets GITHUB_ACTIONS=true on both). The variable that tells them apart is RUNNER_ENVIRONMENT (github-hosted or self-hosted). On a self-hosted runner the script would `sudo rm -rf` /usr/share/dotnet, /usr/local/lib/android, /opt/ghc and the rest and prune every unused Docker image on the owner's machine.
    fix: Check `[ "${RUNNER_ENVIRONMENT:-}" != github-hosted ]` (keeping the GITHUB_ACTIONS check if desired) and have the test run the script with GITHUB_ACTIONS=true RUNNER_ENVIRONMENT=self-hosted and assert it exits 0 with empty stdout and the message on stderr.
  notes: Checked and found sound: (1) the empty-matrix guards: plan.py writes count=<int> to GITHUB_OUTPUT, outputs are strings, and `needs.plan.outputs.count != '0'` is a string-to-string compare, so a finished tag (count 0) skips run, run-real and approve; the survey matrix cannot be empty (chosen_pairs raises on an unmatched entry) so it needs no guard; a skipped job does not evaluate its strategy, and the report job runs on `always() && needs.plan.result == 'success'` whether run/run-real/approve were skipped, failed or rejected. (2) scrub.sh: the `[c]oordbench/run.py run` pattern cannot match the 

## fake-and-drivers: 2 findings
- fake-and-drivers-1 [real] bench/cooperbench/actions/run-pair/action.yml:147: A kept (timed-out) pair never gets its __done marker: pair.sh exits 1, so the composite's marker step is skipped
    claim: For a pair whose agent ran out its time, run.py's verdict is "error" (any outcome with status Error), command_run returns 1, pair.sh exits with that status, and the composite step "Run the pair" fails. The "Say whether the pair is finished" step's condition `if: steps.scrub.outputs.publish == 'true'` carries no status-check function, so GitHub applies the implicit success(), which is false once an earlier step of the composite failed; the step is skipped, `finished` is never set, and the job's marker upload (`steps.pair.outputs.finished == 'true'`) never runs. artifacts.py check-dir would have said "finished" for that directory, but it is never asked. bench.yml's header, the kit README and P
    fix: Give the marker step a condition with a status function so it runs after a failed pair step, as the scrub step does: `if: ${{ !cancelled() && steps.scrub.outputs.publish == 'true' }}` (publish is false whenever the scrub failed, so nothing more is needed). Test: in tests/test_experiment_actions.py's workflow-guard test, assert the action text holds `if: ${{ !cancelled() && steps.scrub.outputs.publish == 'true' }}` for the done step, beside the existing assertion for the scrub step's condition.
- fake-and-drivers-2 [minor] bench/cooperbench/fake_claude:43: fake_claude's json_text leaves control characters other than newline in the JSON string, so an embedded tab breaks the event
    claim: json_text escapes backslashes and quotes and turns newlines into spaces, but a tab, carriage return or any other control character (U+0000-U+001F) passes through raw, which JSON forbids inside a string; Python's json.loads (strict by default, as drivers.json_lines uses it) rejects the line, so the event is dropped. The commit message's "speaks valid JSON whatever the texts hold" and the test of that name are not kept for these characters; only quotes, backslashes and newlines are covered.
    fix: Map every control character, not only newline, e.g. replace `tr '\n' ' '` with `tr '\001-\037' ' '` (POSIX tr octal ranges; busybox and GNU both take them), or escape \t and \r in the sed. Test: add a tab and a carriage return to the ANTHROPIC_MODEL and COORD_RPC_URL values in test_every_event_is_valid_json_whatever_the_texts_hold and json.loads every line.
  notes: Checked and found sound. fake_claude's reading of sdlc-ready: `answer=$(sdlc-ready N 2>&1) || status=$?` takes the command's status in sh/dash/bash; 0 breaks, 3 fetches team, merges team/main (falling back to --theirs), pushes and asks again up to three times, anything else fails with the code and the answer's first line, and the post-loop guard fails a third 3; this matches the vendored gate (EXIT_MAIN_MOVED = 3, gate.py:42) and cli.py's report()/exit_code() (refusal text on stderr, which 2>&1 captures; the tool's exit code passed through the hub's exitCode). Under the sdlc arm's POLICY (who_

## documents: 5 findings
- documents-1 [real] bench/cooperbench/PLAN.md:69: PLAN.md pre-registers an attempt-selection rule the report's download does not follow
    claim: PLAN.md's Resume (lines 69-70) and Primary outcome (lines 84-85), both rewritten by 387ac4f, say the report reads for each pair "the newest artifact of its name that holds a finished pair, else the newest" and that the rate takes each pair "by its newest finished attempt, else its newest". The same commit made artifacts.py choose a different attempt: chosen_state (bench/cooperbench/actions/artifacts.py lines 224-233) returns the newest finished, else the newest UNSCORED, else the newest, and command_download / chosen_artifact / command_finished / command_fetch all go through it. So the pre-registered document and the code disagree on which attempt stands for a pair whenever an older unscored
    fix: In PLAN.md's Resume and Primary outcome write the rule the code keeps: the newest finished attempt, else the newest whose agents did not fail (scored again from its files), else the newest. Test: extend tests/test_experiment_actions.py's Workflow README test to assert PLAN.md contains "else the newest unscored" (or the wording chosen) next to the artifacts.py rule, so the two cannot drift again.
- documents-2 [real] bench/cooperbench/README.md:274: The kit README costs pairs.txt at 50 pairs; the list in this tree holds 43, and the paragraph gives two totals for "the pilot"
    claim: 187efd6 rewrote the cost paragraph to say "pairs.txt's 50 pairs are 450 sessions, about $195 at the authors' rate". pairs.txt at 187efd6 names 17 tasks whose flash pairs sum to 43 (its own header says "These are the 43 pairs"; PLAN.md lines 19-20 and 119 say 43), so the cited inputs give 43 x 9 = 387 sessions, about $166 at $0.43, not 450 / $195. The same paragraph then says "the pilot on pallets_click 2068 (six pairs) 54 sessions, about $23" and three sentences later "The pilot is about 42 sessions, near $18": two different totals for the same pilot, the second being the four-arm cloud-session figure that no longer matches the five-arm dispatch the paragraph describes.
    fix: State the list's size from pairs.txt (43 pairs, 387 sessions, about $166) or make the sentence independent of the count ("nine sessions per pair of pairs.txt"), and keep one pilot figure (54 sessions, about $23, for the five arms; or label the 42 as the four-arm cloud-session pilot). A test can read pairs.txt's header count and assert the README's cost sentence names the same number.
- documents-3 [minor] bench/cooperbench/README.md:162: The queue rule points the owner at a list that does not show the tag, and the queue is shared across tags
    claim: 187efd6 tells the owner to "dispatch the same tag again only when no run of an earlier dispatch is still queued (Actions > Bench: no run of the tag in progress)". The Actions run list cannot show a dispatch's tag: bench.yml sets no `run-name`, so every workflow_dispatch run is listed as "Bench" (the one dispatch on main shows displayTitle "Bench"); the tag is only in the plan job's step summary inside each run. Also the cap the rule guards is GitHub's 100 pending jobs per concurrency group `bench-<account>`, which every real dispatch shares whatever its tag, so a queued real run of another tag also fills it; the parenthetical narrows the check to "the tag".
    fix: Either add `run-name: Bench ${{ inputs.mode }} ${{ inputs.tag }}` (or the run id) to bench.yml so the list shows the tag, or tell the owner to open the run and read the plan summary; and say the wait applies to any real dispatch still queued, not only the same tag. A Workflow test can assert the run-name line.
- documents-4 [minor] PARITY.md:1545: PARITY row 23's status word is outside the file's legend and names a deliberate difference as equivalence
    claim: PARITY.md's legend (lines 28-35) defines four statuses: same, equivalent, different ("deliberately not as CooperBench does, for the reason given") and not measured. 387ac4f set row 23 to "Status: equivalent but for the time limit" while its text says CooperBench reruns a pair whose agent was killed at the 7200 s timeout and coordbench keeps it, for a stated reason; by the legend that is "different". The row's closing "What differs" paragraph (lines 1564-1568) still lists only the harness-error rerun and the packing, not the time-limit keep the status alludes to.
    fix: Set the status to "different" (or "same" on the rerun with the time-limit keep listed as the difference) and add the time-limit keep to the row's "What differs" paragraph.
- documents-5 [minor] .github/workflows/bench.yml:13: bench.yml's header says a pull request runs "a few pairs"; the check runs one pair under three arms
    claim: 387ac4f changed the header to "a pull request that changes the kit, the workflow or the package coordbench/ runs a few pairs this way as its check". The plan step (lines 111-116) fixes a pull request to PAIRS 'pallets_click_task/2068/f1_f6' and ARMS 'solo,coop-git,sdlc': one pair, three (pair, arm) jobs. The kit README (187efd6, line 148-149) describes the same check as "one fake pair per arm of a smoke set", so the two documents disagree and the header is the wrong one.
    fix: Say in the header what the plan step's comment already says: one pair of pallets_click 2068 under three arms.
  notes: Checked against the code and found sound: the Resume/agent-failed vocabulary in PLAN.md, the kit README and bench.yml's header against run.py agent_failed/agent_ran_out_of_time, artifacts.py agent_failed/pair_state and drivers.TIMED_OUT (a timed-out CliRun is status Error with end_reason starting 'timed out after'; finish_pair still scores the pair, so 'its patch is scored' holds; a harness error leaves result.json error and no eval.json, so it reruns); the stopping rule's consequences (an errored or unscored attempt counts as a failure: report.py Pair.passed is False when unscored and the fir

## tests: 7 findings
- tests-1 [real] coordbench/run.py:815: pack_contents is quadratic in a pack's object count, which the three-object test pack cannot show
    claim: pack_contents hands the whole remainder of the pack to inflater.decompress(view[offset:]) for every object; CPython's zlib copies everything past the stream's end into unused_data on each call, so a pack of N objects and S bytes costs about N*S/2 bytes of copying. The scrub test's packfile() has three blobs, so it passes while a repository-sized pack takes minutes.
    fix: Feed the inflater bounded chunks until inflater.eof: `end = offset; while not inflater.eof: chunk = view[end:end + 65536]; if not chunk: raise ValueError("a truncated object"); content += inflater.decompress(chunk); end += len(chunk)` then `offset = end - len(inflater.unused_data)`, so unused_data is at most one chunk per object. Test: a pack of about 20000 one-kilobyte blobs parsed by pack_contents in well under a second (or assert the time for 2N objects is under three times that for N).
- tests-2 [minor] tests/test_experiment_actions.py:183: The fake-tag test cannot tell that the refusal comes before the listing
    claim: test_a_real_dispatch_with_a_fake_tag_is_refused_before_the_listing asserts only exit code 2 and 'fake-' in stderr. With the except fixed, a plan.py that lists first and checks the tag after satisfies both: the listing fails quietly on KeyError (GITHUB_REPOSITORY is unset locally; ci.yml sets no GITHUB_TOKEN), returns the note, and plan() then raises the same ValueError. The test fails against the pre-PR file only because of the nested-tuple TypeError, not the order.
    fix: In the test, `with mock.patch.object(plan, "listed_finished", side_effect=AssertionError("listed before the tag was refused")) as listing:` around plan.main(...), then `listing.assert_not_called()`; or patch artifacts.OPENER with an opener that raises and assert no request was made.
- tests-3 [minor] tests/test_experiment_actions.py:485: The report's arm from the download is tested with a dash-free arm only, and report.sh's new code has no test
    claim: The defect the commit fixes is report.sh taking the arm from the run name split on dashes, which mangles coop-git. The only test of the download's new `arm` field uses arm `coop`, for which `run_name_of(name).split("-")[1]` also gives `coop`, so a regression to a dash-blind extraction passes; and nothing runs or reads report.sh's two Python snippets (the arm/run_name loop at lines 66-73 and the 'Planned items with no artifact' section at lines 45-53), so the claim 'the report takes each run's arm from the download' rests on artifacts.py alone.
    fix: Use `u__coop-git__r__1__f1_f2` in test_an_older_unscored_attempt_is_scored_again... and assert `line["arm"] == "coop-git"` and `line["run_name"] == "u-coop-git-r-1-f1_f2"`; add a Workflow test that extracts report.sh's heredoc (the lines between `python3 -I - "$REPORT_DIR/artifacts.jsonl"` and `PY`) and runs it on an artifacts.jsonl with an error line, a coop-git line and a survey line plus a plan_matrix.json with one unmatched item, asserting the 'Planned items with no artifact' entry, and asse
- tests-4 [minor] tests/test_experiment_actions.py:613: The FakeAgent tests are isolated from the user's gitconfig but not from a user-level ignore file under HOME
    claim: GIT_CONFIG_GLOBAL=/dev/null and GIT_CONFIG_NOSYSTEM=1 do isolate the tests from ~/.gitconfig and /etc/gitconfig (a hooksPath and commit.gpgsign there leave all six tests passing), but HOME and XDG_CONFIG_HOME are inherited, and git reads core.excludesFile's default $XDG_CONFIG_HOME/git/ignore (or ~/.config/git/ignore) outside the config files; a pattern there that matches *.txt makes `git add -N` and `git add` refuse the fake agent's file, so patch.txt is empty and every FakeAgent test fails.
    fix: Add `"core.excludesFile": os.devnull` to GIT_SETTINGS (it travels through GIT_CONFIG_COUNT like the others), or set HOME and XDG_CONFIG_HOME to self.tmp in self.environment. Test: run the FakeAgent class once with XDG_CONFIG_HOME pointing at a directory whose git/ignore holds `*.txt`.
- tests-5 [minor] bench/cooperbench/fake_claude:43: fake_claude's JSON is not valid for every text: a tab or carriage return in a text breaks the event
    claim: json_text escapes backslashes and quotes and turns newlines into spaces, and the test feeds exactly those three; JSON forbids every unescaped control character below 0x20, so a tab or a carriage return in the agent name, the model, or the first line of sdlc-ready's output passes through and the line is not JSON. The commit says 'speaks valid JSON whatever the texts hold'.
    fix: In json_text, after the sed, `tr '\n\r\t' '   ' | tr -d '\000-\010\013\014\016-\037'` (POSIX tr, present in busybox). Test: add a tab and a carriage return to ANTHROPIC_MODEL in the valid-JSON test and keep `json.loads` over every line.
- tests-6 [minor] bench/cooperbench/actions/free_disk.sh:8: free_disk.sh's guard is 'inside GitHub Actions', not 'on a GitHub-hosted runner', and the test checks only the off path
    claim: GITHUB_ACTIONS is set to true on self-hosted runners as well as hosted ones (GitHub distinguishes them with RUNNER_ENVIRONMENT, github-hosted or self-hosted), so the script still runs `sudo rm -rf /usr/share/dotnet ...` and `docker image prune -af` on a self-hosted runner; the commit, the script's own message and the test's name all say 'hosted runner'. test_free_disk_runs_only_on_a_hosted_runner runs it only with GITHUB_ACTIONS unset.
    fix: Guard on `[ "${RUNNER_ENVIRONMENT:-}" != github-hosted ]` (keeping the GITHUB_ACTIONS check if wanted) and say so in the message; test: run with GITHUB_ACTIONS=true RUNNER_ENVIRONMENT=self-hosted and assert exit 0 with the refusal on stderr, and with RUNNER_ENVIRONMENT=github-hosted plus `sudo` and `docker` replaced by stubs on PATH that log their arguments, assert the removals were asked for.
- tests-7 [minor] tests/test_coordbench_run.py:1087: No test drives a timed-out CLI agent through result.json to pair_finished and the score
    claim: The commit's first claim, a pair whose agent ran out its time is kept and scored, is tested in two halves that meet only through the constant: TheRerunRule hand-writes `end_reason: f"{drivers.TIMED_OUT}7200 seconds"` into a result.json, and the driver test asserts only `"timed out" in outcome.error` and `end_reason == error`. No run-level test sets `self.docker.claude_times_out = True` and checks that the pair's result.json carries that end_reason, that eval.json is written, and that pair_finished is True.
    fix: In test_an_agent_past_its_time..., add `self.assertTrue(outcome.end_reason.startswith(drivers.TIMED_OUT))`; and add a RunnerCase test with `self.docker.claude_times_out = True` running `self.main(*self.run_arguments("coop", "--features", "1,6", "--driver", "claude-cli"))`, asserting result.json's agents have status Error with end_reason starting drivers.TIMED_OUT, eval.json exists, `runner.pair_finished(self.pair())` is True, and a second run of the same command skips the pair.
  notes: Ran `python3 -m unittest tests.test_experiment_actions tests.test_coordbench_run`: 177 tests, OK, 2 skipped (both pre-existing skips needing CooperBench's checkout). No test depends on docker, the network or a tool missing from ubuntu-24.04: the FakeAgent tests need git, sh/bash/dash (dash skipped when absent), sed, tr, cksum; the redirect test intercepts https_open with its own handler (works with and without the HTTPS_PROXY this container sets); free_disk.sh is run only with GITHUB_ACTIONS unset so it exits before sudo/docker, and CI (ubuntu-latest, python 3.12, no GITHUB_TOKEN in ci.yml's e

## scrub-security: 3 findings
- scrub-security-1 [real] bench/cooperbench/actions/run-pair/action.yml:147: A timed-out pair never gets its __done marker and fails its job, since run.py still exits 1 for it and the marker step is skipped on that failure
    claim: The commit makes a pair whose agent ran out its time 'finished' (run.py pair_finished, artifacts.py pair_state/check-dir), but the path that publishes the <artifact>__done marker never reaches check-dir for such a pair: run.py's verdict() still returns "error" for any agent whose status is Error (coordbench/run.py:1970 reads only o.status, not agent_failed), so command_run returns 1 (run.py:2729), pair.sh exits 1 (pair.sh:54), the composite step 'Run the pair' fails, and the step 'Say whether the pair is finished' has `if: steps.scrub.outputs.publish == 'true'` with no status function, so GitHub applies the implicit success() and skips it after the failed step. The action's `finished` output
    fix: Give the marker step the same status-function condition as the scrub step: `if: ${{ !cancelled() && steps.scrub.outputs.publish == 'true' }}` (so check-dir decides, as designed), and make run.py's verdict agree with pair_finished so a kept pair does not fail the job: in verdict(), use `o.status == "Error" and not str(o.end_reason or "").startswith(drivers.TIMED_OUT)`. Tests: in tests/test_experiment_actions.py Workflow, assert the done step's `if` carries `!cancelled()`; in tests/test_coordbench
- scrub-security-2 [real] coordbench/run.py:2525: The rescore path never scores a pair whose eval.json holds a scoring error: artifacts.py calls it unscored, run_one calls it done
    claim: The commit's rescore path (fetch into RUNNER_TEMP/rescore, pair.sh moves the files to the run directory, run.py run scores 'a pair whose agents did not fail but that was never scored') does not hold when the earlier attempt's eval.json exists but carries an error. score() always writes eval.json, with error set when the sandbox failed (run_cooperbench_tests returns {'error': ...}, evaluation_record keeps it, write_json at run.py:2408). artifacts.py pair_state calls that 'unscored' (`if not isinstance(evaluation, dict) or evaluation.get("error"): return "unscored"`), so `finished` exits 3 and the job fetches the files; but run_one's finished_run_dir branch returns 'skipped' whenever eval.json
    fix: In run_one, read the evaluation instead of testing the file's existence: `evaluation = read_json(finished / "eval.json"); if isinstance(evaluation, dict) and not evaluation.get("error"): return "skipped", ...` and otherwise fall through to `verdict({}, score(plan))`. Test (tests/test_coordbench_run.py): a finished pair directory whose eval.json is {'error': 'DockerError: x'} makes run_one call score once and return its verdict; one whose eval.json has no error is skipped without scoring.
- scrub-security-3 [minor] coordbench/run.py:837: A symlink under the run directory is published by its target's content while the scrub never reads that target
    claim: The scrub's rewrite and read-back both skip symlinks (`if not path.is_file() or path.is_symlink(): continue` in scrub_paths at run.py:718 and unscrubbed at run.py:837, and tests/test_coordbench_run.py test_a_symlink_is_not_followed asserts it), but actions/upload-artifact@v4 dereferences symlinks: @actions/artifact's zip.ts resolves `realpath(file.sourcePath)` when `file.stats.isSymbolicLink()` and zips the target's bytes, and upload-artifact's search uses `followSymbolicLinks: true`. The team arm's shared/ copy is made with `docker cp` of /workspace/shared/. (run.py:2296), which preserves symlinks, so a symlink an agent leaves in /workspace/shared lands in the published directory unread by 
    fix: In unscrubbed(), treat a symlink as a kept file (`kept.append(f"{path}: is a symlink, which the upload would follow")`) so command_scrub exits 2, or have command_scrub remove symlinks under the run directory before the read-back and say so. Test: a symlink under the run directory makes `run.py scrub --run-dir` exit 2 (or leaves no symlink behind), beside the existing test that the scrub does not follow it.
  notes: Traced the token from bench.yml (job-level env of run-real only; the plan job sees only `secrets.X != ''` booleans; the fake run job has none; pair.sh unsets it in fake mode) through pair.sh (`sudo -E`, no `set -x` anywhere in bench/), run.py (drivers.claude_exec_arguments passes it by `docker exec -e NAME` only; `docker run` for the container gets only the hub's agent token by name; hub and scorer subprocesses get environment_without_secrets; nothing writes environ values into config.json, summary.json, result.json or plan.json), to the upload. Files published are RUN_DIR = <cooperbench>/logs

REFUTER VOTES:
- artifacts-plan-1-1: refuted=False severity=real: Not refuted. Every premise of the scenario holds at 187efd6, and I reproduced it end to end through the repository's own test harness.

The two rules disagree, in the code:
- bench/cooperbench/actions/artifacts.py:154-155: `if not isinstance(evaluation, dict) or evaluation.get("error"): return "unsc
- artifacts-plan-1-2: refuted=False severity=real: Not refuted: the two rules disagree exactly as claimed, and I reproduced the loop's inner step against the repository's own fixture.

Code at 187efd6:
- bench/cooperbench/actions/artifacts.py:154-155: `if not isinstance(evaluation, dict) or evaluation.get("error"): return "unscored"`. command_finish
- artifacts-plan-1-3: refuted=False severity=real: Not refuted; the code at 187efd6 behaves as the finding says, and the PR is what made the path reachable.

1. The two rules disagree, by execution. I ran run.py run_one against a pair directory whose result.json has two Submitted agents, with score() and pair_report patched to record calls (script a
- artifacts-plan-2-1: refuted=False severity=minor: Not refuted; the finding reads the code correctly and its experiment reproduces.

Code path (bench/cooperbench/actions/artifacts.py at 187efd6, lines 89-95): the loop asks for pages 1..MOST_PAGES; the only early exit is `if len(answer.get("artifacts", [])) < PAGE: return found, False`; after the loo
- artifacts-plan-2-2: refuted=False severity=minor: Not refuted: the claimed behaviour reproduces exactly as described at 187efd6.

Code: /home/user/coordbench/bench/cooperbench/actions/artifacts.py lines 89-95. The loop stops only when a page comes back shorter than PAGE (`if len(answer.get("artifacts", [])) < PAGE: return found, False`), and after 
- artifacts-plan-2-3: refuted=False severity=minor: The finding is accurate as to the code and I could not refute it; its claimed severity, minor, is right.

Reproduced: a fake opener serving n artifacts in pages of 100 (each answer carrying total_count) through artifacts.list_artifacts at 187efd6 gives 4999 -> (4999, False), 5000 -> (5000, True), 50
