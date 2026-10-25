---
name: cloud-session-operations
description: Operational facts of this project's cloud sessions learned 2026-10-25 - no board branch in symphony-template, Workflow agents capped at 2 concurrent, a worker restart kills a running Workflow
metadata:
  type: project
  modified: 2026-10-25T20:05:30.480Z
---

- symphony-template has NO `board` branch on origin (only `main` and `grid`); `git fetch origin +refs/heads/board:...` fails there. SchwingNet's board branch reads fine. The grid branch of symphony-template holds the gate's job logs (logs/job-<word>.json, keys at/lines/said/rc) including schwingnet-status and the bench jobs.
- A Workflow in the cloud container runs at most 2 agents at once (min(16, CPUs-2) with 4 CPUs), so a seven-reader fan-out takes 30+ minutes; and a session worker restart (context compaction) kills a running Workflow with no journal results. Relaunch with scriptPath; draft deliverables while it runs.
- Parallel Bash calls share one cwd: always `git -C /abs/path` and absolute paths.

**Why:** these cost this thread a lost workflow run and a mis-targeted fetch.
**How to apply:** read symphony-template's board from the grid branch logs or SchwingNet's board only; keep Workflow fan-outs small or expect the wait; see [[flexray-fork-facts]].
