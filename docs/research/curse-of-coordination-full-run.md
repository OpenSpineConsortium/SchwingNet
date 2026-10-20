# The curse of coordination: the full run

Source: the thread "Curse of coordination full run" in the Project
symphony2, 2026-10-17, which carried on part 2.3 of
docs/checkpoints/2026-10-16/handoff.md. The record itself is in
OpenSpineConsortium/coordbench, bench/cooperbench/results/curse-1-full/
(pull request 28), with the experiment's notes beside it in
bench/cooperbench/results/curse-of-coordination-notes/. This note says
what was found and where it lives; the figures are those of coordbench.

These figures are the owner's to read first, and stay out of the grant
by the owner's rule of 2026-10-15 (18:01 UTC) until xblossom has been
tried.

## What ran

CooperBench's 43 gradable pairs, in the nested stratified order, under
five arms: solo (one agent does both features), coop (two agents who
talk, CooperBench's setting), sdlc (two agents under Symphony's claim
protocol), coop-git (two agents who talk and share a git remote) and
team (two agents with a task list). Every agent ran on
claude-sonnet-5-5 at effort xhigh, as subagents of the session on its
own subscription, with no API key. 215 runs from 2026-10-15 to
2026-10-17; the last 36 ran on 2026-10-17 on a fresh container after
the 179 earlier runs were restored from the bundles in git, which is
the checkpoint's design working across accounts. Every run is clean by
coordbench's audit.

## What it found

| arm | passed of 43 | cost per pair (list price) | naive-merge conflicts |
|---|---|---|---|
| solo | 33 | $0.61 | - |
| coop | 30 | $1.18 | 3 |
| sdlc | 32 | $1.33 | 1 |
| coop-git | 32 | $1.32 | 5 |
| team | 33 | $1.32 | 26 |

- The curse is there in coop, and small: 7 points below solo, against
  the 21 points CooperBench's paper reports for Claude. With 5 pairs
  only solo passed and 2 only coop passed, an exact McNemar test gives
  p 0.45, so it is not established at this size.
- sdlc closes most of the gap: 2 points below solo, 3 pairs passed that
  coop failed against 1 the other way (p 0.63), and the fewest
  naive-merge conflicts of the two-agent arms, at 1.6 times coop's wall
  time and 1.2 times its cost.
- Every two-agent arm costs about twice solo per pair for the same or
  fewer passes. On these pairs, with this model, one agent is still the
  cheapest way to a pass; what coordination buys here is closing the
  gap, not beating solo.
- No difference between arms is significant at 43 pairs. A claim that
  Symphony removes the curse needs more pairs, or pairs where one agent
  alone does worse.

## What comes next

The owner's choice: coordbench's trial-order.md names its steps 4 and 5
as the candidates, and the notes' "The next steps, in order" says what
is done. No bench run is queued.
