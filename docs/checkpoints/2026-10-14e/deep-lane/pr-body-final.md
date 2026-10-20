(Keep the first two lines of the pull request's current body, the attribution comment and the "Requested by" line, as they are.)

Before: the harness had the fast lane, the mutation lane and the regression traces, all in the memory world. The searches stopped at depth 5, no scenario ran over git, the gate's guarantee was checked over MemoryWorld alone, and a counterexample could not be written to a file and replayed.

After: a deep lane runs weekly, by hand, and on a pull request labelled "deep validation". It has these parts:
- Depth-first searches with the depth-aware digest set, with no reduction applied: two issues on one shared file at depth 7, one issue at depth 8, the fault kinds from a held claim at depth 4, and the two faults on the repository's activity from two claims on one file at depth 5.
- A soak of 1,000 seeded walks.
- The gate's guarantee, all eight parts of G13: every part but part 7 over MemoryWorld (every interleaving of two agents' acts under four policies to depth 8), and every part but part 4 over BareGitWorld (S05g and forty seeded sequences).
- Every scenario and regression trace played over a real git repository, with the results known.json records for memory.
- Git's answers for the guard grammar recorded again.
- Conformance: every counterexample and 200 sampled paths played in both worlds and compared after every step.

Every violation is shortened and written as a trace file, which `scripts/validate.py replay <file> --world memory|git` plays. Each search writes a checkpoint as it goes, stamped with its search and code, so a run killed by a restart resumes with `--resume`.

What it changes: validation/git_store.py, deep.py, shrink.py, soak.py, gate_search.py and lanes.py are new. run.py and replay.py take a world. model.py and verbs.py gain a store and a skew. known.json gains "searches". scripts/validate.py gains `deep` and `--world git`. validate.yml gains the deep job. The docs and tests follow. The library sdlc_protocol/ is unchanged, so no version bump, sync or release follows.

How: a model attached to a GitStore mirrors the bare repository after every push, rename and delete. The fake GitHub still answers from the model, and git takes or refuses each push. A copy of the model is detached and answers from the mirror, with git's own word on each branch's standing. The search keeps each state's digest with the shallowest depth it was reached at, and expands a state again when it is reached shallower. A search that a budget stops is red. The runner puts each part in its own process and rewrites deep.json as each one ends.

## Measured

The run of record, at acc83fb on 4 processors with git 2.43.0, is green in 9,559 s (2 h 39 min) and kept in validation/runs/2026-10-14/. It measured the library as main held it at c2de8b1: 0.4.1 with F4, F7, F9, F12, F13 and F14 fixed.
- E-two, two workers on two issues that share a file, to depth 7: 18,787,930 states in 9,494 s, no violation.
- E-deep, one issue, to depth 8: 16,706,180 states in 7,563 s, no violation.
- E-faults, the fault kinds from a held claim, to depth 4: 41,415 states in 92 s, no violation.
- E-activity, the faults on the repository's activity from two claims on one file, to depth 5: 1,035,026 states in 1,040 s, no violation.
- The soak: 1,000 walks of 200 steps, no violation.
- The gate: four policies to depth 8 over MemoryWorld, 51,424 to 63,780 states each; S05g over git with no mismatch; 40 sequences over git with 480 acts, 18 merges, 5 main moved and 71 refusals; no violation.
- Conformance: 200 sampled paths in both worlds, no disagreement. The guard: 699 argument lists, none answered differently from guard_git.json.
- The git world: all 11 scenarios and 14 traces matching known.json.

{{FINAL}}

At {{HEAD}}, `bash scripts/check.sh` passes with {{TEST_COUNT}} tests, the fast lane's new ones adding about 135 seconds; the mutation lane catches 68 mutants of 68; and each of 42 fixes from the fifth to the eleventh review, reverted alone, fails its test.

## Reviews

The fourth review's verdicts are the comment below of that title. The fifth to the eleventh reviews, seven reviewers in the fifth and two in each after it, one lens each, are the comment titled "The review verdicts, rounds five to eleven": one line per finding, with the test that holds its fix.

## Follow-up

- A deep space for each of what the run of record predates: F15's task given by a label alone, where the two faults on posting an issue's labels fire; F16's lenient rules; and F17's pull requests from a fork. Until then the fast lane, the mutation lane's searches and the traces of F15 to F17 meet them (DESIGN.md 6.8).
- validate.yml's weekly deep job runs the four searches on main once this merges.

(Footer: the line "Generated with Claude Code" with its robot mark and link, then the session links of the current body, plus the new session's.)
