---
name: beyond-cooperation-step-4
description: Where the beyond-cooperation programme stands after step 4 (epics #127-#130, tasks #131-#144) and why the coordinator did not plan them
metadata:
  type: project
  modified: 2026-10-17T15:13:18.066Z
---

Step 4 of docs/research/beyond-cooperation was opened on 2026-10-17 at the owner's word. There are four epics in symphony-template: #127 context, #128 tool calls, #129 reading and #130 strace profiling. Their 14 tasks are #131 to #144, labelled todo in the open queue. Steps 1-3 merged as #104, #116 and #125. The record of step 4 is PR #145.

**Why:** symphony-template holds no CLAUDE_CODE_OAUTH_TOKEN, so coordinator.yml's plan job skips every epic. The thread wrote the plans itself and ran `GITHUB_TOKEN=$(gh auth token) python3 tools/team.py --repo OpenSpineConsortium/symphony-template seed --epic N --plan plan.json --registry .github/symphony/workers` from a cloud session. It worked: `--repo` goes before `seed`.

**How to apply:** no worker is registered, so nothing picks the tasks up automatically; a session claims one by the claim skill. Each task's first PR builds the arm under docs/research/beyond-cooperation/arms/ARM/ and stops there. Any run that spends tokens waits for the owner's word and the number of runs. See [[control-panel-signin]] for the other thread's state.
