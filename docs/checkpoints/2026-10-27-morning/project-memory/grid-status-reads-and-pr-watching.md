---
name: grid-status-reads-and-pr-watching
description: The newest grid status read (23:41 UTC 2026-10-25, sent by the anomaly-route thread), and that threads of this project cannot subscribe to pull request events
metadata:
  type: project
  modified: 2026-10-25T23:56:40.210Z
---

The grid status word was sent again at 2026-10-25 23:41:44 UTC by the anomaly-route thread (request anomaly-route-status-2342, commit on symphony-template branch grid, logs/job-schwingnet-status.json): room 4,416 GB of 21,990 GB, 0 running fetches, totalsegmentator_v201 43 GB present. A thread that needs the grid's state before a send reads that file first and sends the status word only when a stage needs a fresher read, never twice for one read (see [[symphony-project-memory]]).

The DRR comparison thread (2026-10-26 00:00 UTC) could not subscribe to pull request events: subscribe_pr_activity answered "Could not subscribe to this PR" for SchwingNet #401 and symphony-template #493, so a thread polls a pull request's checks itself (pull_request_read get_check_runs) rather than waiting for a wake.

**Why:** the grid status read costs a job; a failed subscription means CI results never wake the thread.
**How to apply:** read the record before any grid send; after a push, check the checks by hand before marking ready or merging.
