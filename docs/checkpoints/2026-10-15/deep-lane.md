# Deep lane: done (2026-10-15)

The deep lane thread of the 2026-10-14e handoff finished its one job on 2026-10-15 at about 02:40 UTC, and the owner then asked every thread to push and prepare a handoff (about ten dollars of credit left). Nothing of this thread is unpushed.

## What landed

- OpenSpineConsortium/symphony-protocol#21, "Validation harness, build step 6: the deep lane and the git world", merged with a merge commit as c7f0d84 (parents c17e34c and 90c05b0) at about 02:38 UTC, every check green on 90c05b0 (check, mutants, consumers, the four downstream jobs, CodeQL; deep skipped as on every push). Main's tree equals the branch's; the version stays 0.4.1, and no release or approval gate was touched.
- The last commit, 90c05b0, followed docs/checkpoints/2026-10-14e/deep-lane/README.md steps 2 to 5: every part but the four searches ran again at 01afc41 in 442.8 s with three jobs, green, and is kept in validation/runs/2026-10-14-merged/ (its README dated 2026-10-15, the day it ran); the two older runs' READMEs say where each stands; the 27 placeholder marks in validation/README.md and DESIGN.md are filled from the run of record (acc83fb, 9,559 s) and that run; bash scripts/check.sh passed twice with 1,291 tests. The description is the prepared pr-body-final.md with the figures.

## Follow-up (from #21's description)

- A deep space for each of what the run of record predates: F15's task given by a label alone, where the two faults on posting an issue's labels fire; F16's lenient rules; and F17's pull requests from a fork (symphony-protocol validation/DESIGN.md 6.8). Until then the fast lane, the mutation lane's searches and the traces of F15 to F17 meet them.
- validate.yml's weekly deep job now runs the four searches on main.

## Notes for the next thread

- The scripts under docs/checkpoints/2026-10-14e/deep-lane/ are spent; nothing else of #21 remains.
- The PR subscription tool answered "Could not subscribe" for symphony-protocol#21; checks were read with `gh api repos/<repo>/commits/<sha>/check-runs` instead, which works on an attached repository.
- The fixes thread owns symphony-protocol#32 (F18) and #33 (F19); this thread touched neither.
