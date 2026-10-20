# Deep lane: where it stopped (2026-10-14e)

The Deep lane thread stopped at about 23:45 UTC on 2026-10-14, on the owner's word (weekly usage nearly spent). Its one job is OpenSpineConsortium/symphony-protocol#21, "Validation harness, build step 6: the deep lane and the git world", through its merge. This folder holds what lived only in that session's container.

## State

- Branch `claude/validation-harness-step-6-mm6b8t`, head 01afc41, pushed; the pull request is a draft. Commits since acc83fb:
  - 0a99040 merges main at c17e34c (F15 #28, F16 #29, the owner's answers #30, F17 #31); six conflicts resolved by hand, its message says how.
  - b388b0c answers the tenth review (the review of that merge): nine findings.
  - 93b8c06 answers the eleventh review (the second review, of b388b0c): four findings, one blocking (a run in two halves over git was judged by the model's rule; RepoModel.copied_whole).
  - 01afc41 keeps the run of record's files in validation/runs/2026-10-14/ (deep.json, run.log, progress.log, started.txt, README.md).
- Checked at 93b8c06: `bash scripts/check.sh` green with 1,291 tests (run before the eleventh review's two doc nits, which change docstrings and Markdown only); the mutation lane 68 of 68; revert_check_all.py 42 of 42 (each fix of the fifth to the eleventh review, reverted alone, fails its test).
- Main was still at c17e34c at 23:40 UTC; no merge of main is owed unless it moved since.
- The run of record: the whole deep lane at acc83fb, green, 9,558.6 s on 4 processors, git 2.43.0. It measured the library as main held it at c2de8b1, 0.4.1 with F4, F7, F9, F12, F13 and F14 fixed, not F15, F16 and F17.
- The review verdicts of rounds five to eleven are posted on #21 (the comment "The review verdicts, rounds five to eleven").
- CI on 01afc41 at 23:45 UTC: check, consumers, the four downstream jobs and CodeQL green; mutants still running (validate.yml's deep job skipped, as on every push).
- Not done: the final code's run of every part but the searches is not made (a run at b388b0c was green in 484.7 s, but 93b8c06 changed the code after it, so it is not kept); the `<<PLACEHOLDER>>` marks in validation/README.md and DESIGN.md are not filled; the description still holds the Checkpoint 2026-10-14d section; nothing is marked ready or merged.

## Next steps

1. Read the checks on #21's head, mutants among them. If check or mutants is red, fix and push (merge main in if it moved; never rebase).
2. Run every part but the searches at the head, in a clean clone of the branch, with nothing else running: start_parts.sh here (set its `cd` to the clone). About 8 minutes with three jobs on 4 processors; it writes validation-out/ with started.txt naming the commit.
3. `python3 runs_readmes.py <clone>/validation-out <that commit> --write` (set REPO inside to the clone): it copies the run into validation/runs/2026-10-14-merged/ with its README and adds to the run of record's README which library it measured.
4. `python3 fill.py <clone>/validation/runs/2026-10-14/deep.json acc83fb <test count> 0 135 --final=<clone>/validation-out/deep.json --final-commit=<that commit> --repo=<clone> --write`, where the test count is check.sh's "Ran N tests" at the head (1,291 at 93b8c06). Then `grep -rn '<<' validation/` prints nothing, and every changed file is ASCII.
5. `bash scripts/check.sh`, commit the runs and the filled docs (not validation-out/), push, and read CI.
6. Replace #21's description with pr-body-final.md here: fill {{FINAL}} with the parts run's figures (fill.py prints the FINAL value), {{HEAD}} with the head and {{TEST_COUNT}} with the count; keep its first two lines and its footer as the file says.
7. Mark ready, and once every check is green merge with a merge commit on the owner's standing permission, the expected head sha copied from git; then check main's tree.

## Files

- fill.py: fills the marks from the run of record and the final code's run.
- runs_readmes.py: keeps the final code's run beside the run of record and corrects both READMEs.
- start_parts.sh: runs every part but the four searches at the checkout's head.
- revert_check_all.py: reverts each listed fix alone and runs its test with and without it (`python3.12 revert_check_all.py <clone>`; it edits and restores the clone's files, so nothing else may run there meanwhile).
- pr-body-final.md: the description to put on #21 once the figures are in.

Follow-up for after the merge, also in the description: a deep space for each of what the run of record predates, F15's task given by a label alone (where the two faults on posting an issue's labels fire), F16's lenient rules and F17's pull requests from a fork (DESIGN.md 6.8).
