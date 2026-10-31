---
name: qaloop-transformer-plan
description: The transformer QA-loop plan qa_transformer (kind qaloop_tx, SchwingNet #529) and how a grid gate word is sent
metadata:
  type: project
  modified: 2026-10-31T06:28:18.387Z
---

2026-10-31: SchwingNet #529 (merged d629a8c) adds grid/qaloop/qa_transformer.json, a TransUNet copy of qa_loop, run as its own kind qaloop_tx under docs/research/qa-loop-transformer/PREREG.md (frozen PREREGs on main are never edited; a new design is a new kind). bordercall #65 added transunet and unetr to the auto-anatomist.

Sending a gate word: symphony-template's .github/workflows/grid-accounts.yml, workflow_dispatch on main, action=job, job=schwingnet-<word with spaces as dashes, e.g. schwingnet-qaloop-qa_transformer>, request=a label of one's own; the answer lands on symphony-template branch grid at logs/job-<job>.json. job=schwingnet-status lists chains.

**Why:** greg asked for a transformer approach (04:41 UTC). Not sent yet: it waits on the QA thread's qa_smoke (chain 40903176) ending in exit 0, and since ~06:20 UTC GitHub Actions on the org's private repos refuses jobs for a billing failure that greg must fix.
**How to apply:** after both clear, dispatch job=schwingnet-qaloop-qa_transformer and watch it. See [[greg-merges-without-asking]].
