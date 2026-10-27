---
name: actions-billing-block-2026-10-26
description: RESOLVED 2026-10-27 ~03:10 UTC (owner raised the Actions budget); from ~21:00 UTC 2026-10-26 every org Actions job had failed unstarted on billing
metadata:
  type: project
  modified: 2026-10-27T04:00:00.000Z
---

RESOLVED: the owner said at 03:10 UTC 2026-10-27 "i updated the actions budget as well", and symphony-template grid-accounts.yml runs succeeded from 03:10 to 03:16 UTC. Grid words that failed unstarted before then never ran and may be sent again once (after a status read).

On 2026-10-26, every GitHub Actions job in OpenSpineConsortium started failing without starting. Each annotation reads: "The job was not started because recent account payments have failed or your spending limit needs to be increased."

Runs seen failing this way:
- SchwingNet Research loop, 21:05 UTC
- SchwingNet Board, 22:44 UTC
- symphony-template grid-accounts.yml, 22:31 UTC (the DRR thread's status word, request drr-status-2231-d14v3r)

The last runs that worked were at 19:40 UTC (SchwingNet #413's merge).

Effect:
- No grid word can be sent, since the dispatch job runs on ubuntu-latest.
- No status read can be made.
- No CI check can run, so nothing can merge.

Slurm jobs already queued on the grid, such as 40790826 bench_flexray_drr_seg, keep running there. Their reports simply cannot be fetched.

The DRR thread told the owner at about 22:55 UTC, with the billing link.

**Why:** the next sessions should not mistake these red runs for code failures, and should not resend grid words that never ran.
**How to apply:** before any dispatch, check the newest run's annotation. A failed dispatch spends nothing, and the word can be sent again once Actions runs again. The owner raises the limit at https://github.com/organizations/OpenSpineConsortium/settings/billing, or waits for the monthly reset. See [[drr-comparison-grid-count]].
