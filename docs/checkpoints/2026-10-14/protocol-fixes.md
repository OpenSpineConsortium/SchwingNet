# Protocol fixes for the owner's decisions: checkpoint, 2026-10-14 01:35 UTC

Thread: "Protocol fixes for the owner's decisions". Brief: one library fix per
pull request in OpenSpineConsortium/symphony-protocol, in the order F7, F12,
F4, F14, F9, F13, F2, F8, the stuck claim; version 0.5.0 only in the last
library pull request; the release approval is the owner's.

## Landed (merged, CI green)

- F7, the guard's fence on a lease: symphony-protocol#20 (32eef96) and
  symphony-template#69 (4419b89, the hook passes guard.claim_file_reader).
- F12, "main moved" by the state on any run: symphony-protocol#22 (3e98b88).

## Pushed, open, unmerged (for review next session)

- symphony-template#70, branch claude/owner-decisions-pnq7d9, head 58c8cbc:
  queue: max in board.yml. Reviewed, check green, mergeable; left unmerged on
  the owner's checkpoint request. Merge it first next session.
- symphony-protocol#23, draft, branch claude/owner-decisions-f4, head 45e301d:
  F4 work in progress. Built: team.deals (every worker's move from one
  Snapshot), next_for over it, team.deal_moves, cli `team deal --registry DIR
  [--workers JSON]` printing JSON worker->move and making take labels;
  validation/clerk.workflow_deals; dealing lane fails on any double deal; F4
  trace green, known.json F4 entry removed; mutant "each leg dealt from its
  own look" (31 mutants); GUARANTEES G14 checked. bash scripts/check.sh
  passes (1,027 tests).

## Next, in order

1. Finish F4 on #23: run `python3 -m validation.mutants` (expect 31/31);
   tests for team.deals, deal_moves and the deal subcommand (test_team.py,
   test_cli.py); spec/PROTOCOL.md Planning sentence ("dealt by one look at the
   repository, the run's first job"); DESIGN.md F4 table row (line 34),
   section 13 status, decision line 847, G14 row 120, line 575;
   validation/README.md dealing lines; adversarial review; mark ready; merge.
2. Template for F4, on claude/owner-decisions-pnq7d9 restarted from main after
   #70: workers.yml registry job gets issues: write and GITHUB_TOKEN, runs
   `python3 tools/team.py deal --registry .github/symphony/workers --workers
   "$workers"` once and outputs `deals`; each leg reads
   fromJSON(needs.registry.outputs.deals)[matrix.worker] in place of its own
   `next`; the "Go another round" step keeps `next`. Prose: WORKERS.md line
   17, docs/memory/workers.md ~line 40, docs/setup/claude-action.md ~line 69,
   the workflow's header comment. Note: the template's vendored library gains
   `deal` only after the release, so the workflow change waits for the sync or
   falls back to `next` when `deal` is missing.
3. Then F14, F9 (one REST GET of a draft's mergeable_state, canary C0, on
   OpenSpineConsortium/symphony-protocol-canary), F13, F2, F8 (behind the
   committer-date read until canary C5), the stuck-claim recovery, and 0.5.0
   in the last library pull request.

## Needs the owner

- Approve the next symphony-protocol release when 0.5.0 is raised (the
  environment "release"); no session can.
- The canary repository's permissions for C2 and C7 (the step 7 thread has
  the clicks).
