# The after-the-fact review of coordbench#12, paused 2026-10-14 13:20 UTC

Item 2 of the handoff of 2026-10-14 (docs/checkpoints/2026-10-14/HANDOFF.md):
review coordbench#12, CooperBench in Actions, read its smoke run's report,
fix what the review finds by a new pull request, then carry on from
docs/checkpoints/2026-10-14/cooperbench-run.md short of the real run. The
thread paused when the owner asked for a checkpoint to continue on another
account. The three pull requests each carry a "Checkpoint 2026-10-14c"
section at the top of their description, which is the state; this note
holds what those sections point at: the review's findings and where each
went, and the notes meant for the next update of cooperbench-run.md.

## Where it stands

- coordbench#14, the kit fix, branch claude/coordbench-12-review-v7l66b, head
  187efd6 (three commits: 5390686, 387ac4f, 187efd6). check.sh passes; Checks
  and the Bench smoke run were green at 387ac4f and run again on 187efd6.
  Merge first.
- coordbench#15, the pair list, branch claude/coordbench-12-review-v7l66b-pairs,
  head 0a4f965: pairs.txt is the flash subset whole, 20 tasks and 50 pairs,
  fixed from the survey dispatch survey-1 (run 38549172370, every task graded
  on a runner). Merge second; shares PLAN.md and the kit README with #14.
- coordbench#16, the Coordination section of report.py, branch
  claude/coordbench-12-review-v7l66b-coordination, head 64bcaf5. Merge third;
  shares PARITY.md with #14.
- coordbench#13 merged earlier (dd9aa2d): CI clones the library as
  symphony-protocol and does not check twice on a sync push.
- Of cooperbench-run.md's "Next, in order": the survey ran and the pair list
  is fixed (#15); the fake run over the fixed list is not dispatched yet; the
  Coordination section is #16; the real run is the owner's.
- Every branch is pushed and every working tree clean. Nothing is held
  outside GitHub but this session's scratchpad, whose one thing worth keeping
  is the review output rendered in coordbench-review-findings.md beside this.

## What the review was

The review workflow ran seven finders over the kit at a581d02, one per
dimension (actions, resume, scrub, statistics, tests, scripts, documents),
each told to refute the earlier review's nine findings and find its own, then
two skeptic lenses per dimension and one completeness critic. The finders
all finished (55 findings and the nine prior ones confirmed). Of the
skeptics only the two on the actions dimension finished; the other twelve
and the critic failed on the account's usage limit at 12:27 UTC, as did a
separate review of commit 387ac4f, which had read the commit and run the
tests but reported nothing. So: every finding below was checked by the
session itself against the code before it was acted on, but no finding of
the resume, scrub, statistics, tests, scripts or documents dimensions had a
second reader, and 387ac4f and 187efd6 have had no adversarial review. The
next session runs one over those two commits before marking #14 ready.

The one skeptic result worth carrying: on actions-prior-1 (one approval per
job under the environment plus concurrency) both lenses were uncertain
whether GitHub takes a job's concurrency slot before or after the
environment gate; the fix, one approve job that gates the dispatch once,
is right under either order, and a two-job matrix in one concurrency group
on a throwaway environment would settle the question if anyone needs it.

## Where each finding went

In 5390686 (round one, the commit message lists each): resume-1, resume-2,
resume-3, resume-5 and actions-9 (the survey_tag input), actions-prior-1
(the approve job), actions-prior-2 (the scrub-only step), actions-prior-3
(finished items left out before the caps), actions-prior-4 (the fake tag
prefix), actions-prior-5 (documented: the approval gates the jobs, the
secrets are named one by one), actions-prior-6 (the timeout bound),
actions-prior-7 (the self-review rule), actions-prior-9 (survey counts),
actions-1 and tests-5 (uploads overwrite on a re-run), actions-2 (exit 2
kept), actions-3 (a row per planned task), actions-4 (empty inputs fall to
the planner's defaults), actions-5 (slots checked in the plan job), actions-6
and tests-11 (arms refused in the plan), actions-7 (the skip check before
free_disk), actions-10 (the report printed to the log and uploaded whatever
happened), statistics-4 (the default pair list), statistics-5 (the survey
carried by tag), documents-5 (one approval).

In 387ac4f (round two): resume-4 (the newest finished attempt stands),
resume-6 (PLAN.md says the rate is over last attempts), resume-7 and tests-7
(the download says when its listing was cut at 5000), actions-prior-8 (a
failed read is its own answer), actions-8 and tests-2 (the workflow test
cuts each job at its own line), scrub-1 to scrub-4, statistics-2 (a timed-out
pair kept, PARITY.md row 23), statistics-3 (the planned items with no
artifact listed), tests-1, tests-3, tests-4, tests-6, tests-8, tests-9,
tests-10, scripts-1 to scripts-6.

In 187efd6 (the documents): documents-2 (the cost for five arms),
documents-4 (Repository access), documents-6 (the environment's three
clicks), documents-9 (the accounts a dispatch needs), documents-10 (nothing
waits for the queue by itself), documents-12 and documents-15 (the root
README and the smoke sentence).

In #15: statistics-1 and documents-1. In #16: statistics-7.

Left on purpose: documents-3 (restructure the kit README around the Actions
path; a larger rewrite than the fix should carry), documents-13 (bench.yml's
header as reasons only), documents-14 (the tag's 41-character limit, which
is GitHub's artifact-name bound less the longest suffix, unexplained in the
input's description), documents-11 (holds once survey_tag names the survey;
METRICS.md's row unchanged). Follow-up, not in any pull request:
statistics-6, a cluster-aware permutation test for the primary comparison,
since the pairs cluster by task and PLAN.md names the clustering without
using it; and committing the survey reports beside pairs.txt.

## Notes for the next update of cooperbench-run.md

- documents-7: the checkpoint's survey step said to survey pairs.txt, which
  cannot decide the three tasks the list left out; the survey was dispatched
  over the flash subset whole and decided them. Say the survey runs over the
  subset, the list is fixed from it.
- documents-8: the checkpoint sent a session to read the report artifact by
  its path. Constraint: a cloud session's proxy refuses GitHub's artifact
  blob store, so artifacts are unreadable from a session; the report job
  prints the report to its log, and a session reads it there.
- The survey result: all 20 flash tasks grade on GitHub's runners (the three
  that download at test time included), run 38549172370, tag survey-1.
- The next account dispatches the fake run with tag fake-1 (kept as given)
  and survey_tag survey-1, 250 run jobs, and reads the report job's log.

## The owner's own items, unchanged

The environment bench on coordbench with the owner as required reviewer
(Prevent self-review unticked, Deployment branches limited to main); the
organization secrets SYMPHONY_CLAUDE_1, SYMPHONY_CLAUDE_2 and so on, each
with Repository access set to Selected repositories and coordbench ticked;
the variable SYMPHONY_CLAUDE_ACCOUNTS; then the real dispatch and its
approval under Review deployments. The links are in HANDOFF.md of
2026-10-14 and the clicks in the kit README (#14).
