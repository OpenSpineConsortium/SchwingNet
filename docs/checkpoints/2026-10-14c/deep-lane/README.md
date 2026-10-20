# The deep lane thread's checkpoint, 2026-10-14c

What the thread for item 1 of the 2026-10-14b handoff (symphony-protocol#21, harness step 6, the deep lane) left when the owner asked for a checkpoint at 13:10 UTC. The state of the work itself is the "Checkpoint 2026-10-14c" section at the top of symphony-protocol#21's description; this folder keeps what did not fit there.

- review-findings.md: the 32 findings of the adversarial review of the branch at 74d1857, in the reviewers' own words, with the verdicts of the refuters that finished before the container's restart killed the rest (the first four findings). None is fixed yet; each is a claim the next session verifies before it changes code.
- fill.py: fills the `<<PLACEHOLDER>>` marks of symphony-protocol's validation/README.md and validation/DESIGN.md from a deep run's deep.json, the suite's test count and time; dry-run without `--write`. Run it from a checkout of symphony-protocol, with REPO at its top set to that checkout.
- run_readme.py: writes validation/runs/2026-10-14/README.md, the run of record's table, from the same deep.json. Both scripts were tried on validation/runs/2026-10-14-before-review/deep.json.
