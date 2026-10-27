---
name: claude-session-limit-2026-10-26
description: The project's Claude account hit its session limit at about 01:00 UTC on 2026-10-26 (resets 04:10 UTC); Workflow subagents then fail with "You've hit your session limit", so fan-outs started near the limit lose their later agents
metadata:
  type: project
  modified: 2026-10-26T01:48:16.348Z
---

On 2026-10-26, between about 01:00 and 01:30 UTC, the adversarial-review Workflow of the #163 thread (47 agents, two at a time) lost its last 15 skeptic agents to "You've hit your session limit . resets 4:10am (UTC)": the size-readers and integration lenses' claims got no skeptic, and the thread verified them by hand. The main thread kept running. The container was also restarted around 01:30 UTC, which killed a background test run (the clone, the scratchpad and the uncommitted working tree survived).

**Why:** a fan-out of dozens of agents spends the account's five-hour window fast; agents that start after the limit fail at once, and the workflow's result counts them as missing votes, which its own tally can read as "refuted".

**How to apply:** before a large Workflow, size it to the window (fewer skeptics per claim, or fewer lenses) and read the result's `failures` list before trusting its tally; after a container restart, re-create background tasks and check `git status` in every clone. See [[symphony-project-memory]].
